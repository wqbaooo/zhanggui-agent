#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目档案与经营数据路由。"""

from __future__ import annotations

import time

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from models.project import _compute_source_quality, ProjectMemory
from models.utilities import load_utilities, upsert_utility
from server.schemas import (
    ActionTaskCreate,
    ActionTaskUpdate,
    DailyOperationEntry,
    DeliveryImportCreate,
    FranchiseConstraintsUpdate,
    IntegrationUpdate,
    MonthlyOperatingUpdate,
    OperationListResponse,
    ProjectProfileUpdate,
    SiteTransferUpdate,
    UtilityRecord,
)


router = APIRouter(prefix="/projects", tags=["projects"])


def _get_or_create_project(project_id: str) -> ProjectMemory:
    memory = ProjectMemory.load(project_id)
    if memory is None:
        memory = ProjectMemory.create(project_id)
    return memory


@router.get("/{project_id}")
async def get_project(project_id: str):
    """读取项目档案，不存在则创建空档案。"""
    memory = _get_or_create_project(project_id)
    return memory


@router.get("/{project_id}/cockpit")
async def get_project_cockpit(project_id: str, days: int = Query(7, ge=1, le=366)):
    """生命周期驾驶舱唯一数据入口。"""
    memory = _get_or_create_project(project_id)
    return memory.cockpit_summary(days=days)


@router.put("/{project_id}/profile")
async def update_project_profile(project_id: str, req: ProjectProfileUpdate):
    memory = _get_or_create_project(project_id)
    memory.update_profile(req.profile)
    return {"success": True, "project": memory}


@router.put("/{project_id}/franchise-constraints")
async def update_franchise_constraints(project_id: str, req: FranchiseConstraintsUpdate):
    memory = _get_or_create_project(project_id)
    memory.update_franchise_constraints(req.constraints)
    return {"success": True, "project": memory}


@router.put("/{project_id}/site-transfer")
async def update_site_transfer(project_id: str, req: SiteTransferUpdate):
    memory = _get_or_create_project(project_id)
    memory.update_site_transfer(req.site_transfer)
    return {"success": True, "project": memory}


@router.get("/{project_id}/tasks")
async def list_tasks(project_id: str):
    memory = _get_or_create_project(project_id)
    return {"tasks": memory.action_tasks}


@router.post("/{project_id}/tasks")
async def create_task(project_id: str, req: ActionTaskCreate):
    memory = _get_or_create_project(project_id)
    payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    task = memory.add_task(payload)
    return {"success": True, "task": task, "cockpit": memory.cockpit_summary(days=7)}


@router.patch("/{project_id}/tasks/{task_id}")
async def update_task(project_id: str, task_id: str, req: ActionTaskUpdate):
    memory = _get_or_create_project(project_id)
    payload = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    try:
        task = memory.update_task(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    return {"success": True, "task": task, "cockpit": memory.cockpit_summary(days=7)}


@router.get("/{project_id}/integrations")
async def list_integrations(project_id: str):
    memory = _get_or_create_project(project_id)
    return {"integrations": memory.integration_status()}


@router.patch("/{project_id}/integrations/{integration_id}")
async def update_integration(project_id: str, integration_id: str, req: IntegrationUpdate):
    memory = _get_or_create_project(project_id)
    payload = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    integration = memory.update_integration(integration_id, payload)
    return {"success": True, "integration": integration, "integrations": memory.integration_status()}


@router.get("/{project_id}/delivery-imports")
async def list_delivery_imports(project_id: str):
    memory = _get_or_create_project(project_id)
    return {"imports": memory.delivery_imports[-30:]}


@router.post("/{project_id}/delivery-imports")
async def create_delivery_import(project_id: str, req: DeliveryImportCreate):
    memory = _get_or_create_project(project_id)
    payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    entry = memory.add_delivery_import(payload)
    return {"success": True, "import": entry, "imports": memory.delivery_imports[-30:]}


@router.get("/{project_id}/operations", response_model=OperationListResponse)
async def list_operations(project_id: str, days: int = Query(30, ge=1, le=366)):
    memory = _get_or_create_project(project_id)
    entries = memory.daily_operations[-days:]
    return {"entries": entries, "summary": memory.operation_summary(days=days)}


@router.get("/{project_id}/utilities")
async def list_utilities(project_id: str):
    return {"records": load_utilities(project_id)}


@router.put("/{project_id}/utilities/{month}")
async def update_utility(project_id: str, month: str, req: UtilityRecord):
    if month != req.month:
        raise HTTPException(status_code=400, detail="month path and payload must match")
    payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    records = upsert_utility(project_id, payload)
    return {"success": True, "record": payload, "records": records}


@router.post("/{project_id}/operations")
async def add_operation(project_id: str, entry: DailyOperationEntry):
    if not entry.date:
        raise HTTPException(status_code=400, detail="date is required")
    memory = _get_or_create_project(project_id)
    payload = entry.model_dump() if hasattr(entry, "model_dump") else entry.dict()
    memory.add_daily_operation(payload)

    # 写入审计日志
    memory.add_capture_audit_log({
        "source_type": payload.get("source_type", "manual"),
        "file_name": payload.get("source_file_name", ""),
        "capture_kind": "operation",
        "recognized_fields": [
            {"key": k, "value": v} for k, v in payload.items()
            if k in {"revenue", "orders", "food_cost", "labor", "platform_fee", "marketing_cost"}
            and v and isinstance(v, (int, float)) and v > 0
        ],
        "human_modified_fields": payload.get("human_modified_fields", []),
        "review_status": "written",
        "write_target": "daily_operations",
        "date": payload.get("date"),
    })

    # 异常检测 → 自动生成行动项
    summary = memory.operation_summary(days=7)
    alerts = _detect_operation_alerts(summary, memory)
    new_tasks = []
    for alert in alerts:
        existing = any(t.get("title") == alert["title"] for t in memory.action_tasks)
        if not existing:
            task = memory.add_task({
                "title": alert["title"],
                "target": alert.get("target", "工作台"),
                "priority": alert.get("priority", "medium"),
                "source": "auto_alert",
                "status": "todo",
                "notes": alert.get("message", ""),
            })
            new_tasks.append(task)

    return {
        "success": True,
        "entry": payload,
        "summary": summary,
        "alerts": alerts,
        "new_tasks": new_tasks,
    }


def _detect_operation_alerts(summary: dict, memory: ProjectMemory) -> list:
    """检测经营异常，返回需要创建的行动项列表。"""
    from models.sku import SkuCatalog
    alerts = []

    # 亏损预警
    if (
        summary.get("profit_ready", True)
        and summary.get("net_profit", 0) < 0
        and summary.get("entry_count", 0) >= 3
    ):
        alerts.append({
            "level": "high",
            "title": "检查亏损原因",
            "message": f"近{summary['days']}天净亏损 ¥{abs(summary['net_profit']):.0f}，先检查食材成本、人工和平台活动是否吃掉毛利。",
            "target": "利润分析",
            "priority": "high",
        })

    # 食材成本率预警
    if summary.get("profit_ready", True) and summary.get("food_cost_rate", 0) > 0.4:
        alerts.append({
            "level": "medium",
            "title": "核对食材成本率",
            "message": f"食材成本率 {summary['food_cost_rate']*100:.1f}% 超过 40%，需要核对总部供货价、损耗和套餐毛利。",
            "target": "进货库存",
            "priority": "medium",
        })

    # Prime Cost 预警
    if summary.get("profit_ready", True) and summary.get("prime_cost_rate", 0) > 0.65:
        alerts.append({
            "level": "medium",
            "title": "控制 Prime Cost",
            "message": f"食材+人工合计 {summary['prime_cost_rate']*100:.1f}%，压缩利润空间。",
            "target": "利润分析",
            "priority": "medium",
        })

    # 外卖渠道依赖度预警
    if summary.get("delivery_revenue", 0) > 0 and summary.get("total_revenue", 0) > 0:
        delivery_rate = summary["delivery_revenue"] / summary["total_revenue"]
        if delivery_rate > 0.6:
            alerts.append({
                "level": "medium",
                "title": "渠道依赖度过高",
                "message": f"外卖占比 {delivery_rate*100:.1f}% 超过 60%，平台抽点和配送费会吃掉毛利，需加强堂食引流。",
                "target": "渠道分析",
                "priority": "medium",
            })

    # 客单价下降预警
    if summary.get("avg_order_value", 0) > 0 and summary.get("prev_avg_order_value", 0) > 0:
        if summary["avg_order_value"] < summary["prev_avg_order_value"] * 0.85:
            alerts.append({
                "level": "medium",
                "title": "客单价下降",
                "message": f"客单价从 ¥{summary['prev_avg_order_value']:.0f} 降至 ¥{summary['avg_order_value']:.0f}，检查套餐搭配和促销力度。",
                "target": "商品分析",
                "priority": "medium",
            })

    # 连续多日未录入预警（仅在完全没有数据时提示）
    if summary.get("entry_count", 0) == 0 and summary.get("days", 7) >= 7:
        alerts.append({
            "level": "low",
            "title": "补充经营数据",
            "message": f"近 {summary['days']} 天没有录入经营数据，请先上传客如云日报或平台后台截图。",
            "target": "资料入库",
            "priority": "low",
        })

    # 库存预警（从 SkuCatalog 获取）
    catalog = SkuCatalog.load(memory.project_id)
    if catalog:
        for sku in catalog.skus:
            if sku.get("risk_level") in ("high", "urgent"):
                alerts.append({
                    "level": sku.get("risk_level"),
                    "title": f"备货：{sku.get('name', '某SKU')}",
                    "message": f"预计 {sku.get('stockout_date', '近日')} 断货，建议采购 {sku.get('suggested_qty', '?')}。",
                    "target": "进货库存",
                    "priority": "high" if sku.get("risk_level") == "urgent" else "medium",
                })

    return alerts


@router.get("/{project_id}/operations/summary")
async def operation_summary(project_id: str, days: int = Query(7, ge=1, le=366)):
    memory = _get_or_create_project(project_id)
    return memory.operation_summary(days=days)


@router.get("/{project_id}/capture-audit-log")
async def get_capture_audit_log(project_id: str, limit: int = Query(50, ge=1, le=200)):
    """获取录入操作审计日志。"""
    memory = _get_or_create_project(project_id)
    logs = memory.capture_audit_log[:limit]
    return {"logs": logs, "total": len(memory.capture_audit_log)}


@router.get("/{project_id}/monthly")
async def get_monthly_revenue(project_id: str):
    """月度经营汇总：营业额与净利润分别建模。"""
    memory = _get_or_create_project(project_id)
    return memory.monthly_summary()


@router.put("/{project_id}/monthly")
async def update_monthly_operating(project_id: str, req: MonthlyOperatingUpdate):
    """确认并幂等写入月度经营记录与成本基线。"""
    entries = [item.model_dump() if hasattr(item, "model_dump") else item.dict() for item in req.entries]
    if not entries:
        raise HTTPException(status_code=400, detail="至少需要一条月度经营记录")
    if any(item.get("revenue") is None and item.get("net_profit") is None for item in entries):
        raise HTTPException(status_code=400, detail="每条记录至少填写营业额或净利润")
    payload = req.model_dump(exclude={"entries"}) if hasattr(req, "model_dump") else req.dict(exclude={"entries"})
    memory = _get_or_create_project(project_id)
    memory.upsert_monthly_operating(entries, payload)
    return {
        "success": True,
        "updated_periods": [{"year": item["year"], "month": item["month"]} for item in entries],
        "summary": memory.monthly_summary(),
        "cockpit": memory.cockpit_summary(days=7),
    }


@router.post("/{project_id}/import-csv/preview")
async def preview_delivery_csv(project_id: str, file: UploadFile = File(...)):
    """上传 CSV 后只解析预览，不写入。返回列映射、预览行、警告。"""
    import csv
    import io

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="只支持 CSV 文件")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("gbk")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="无法识别 CSV 编码")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV 为空")

    col_map = _detect_csv_columns(reader.fieldnames)
    if not col_map:
        raise HTTPException(status_code=400, detail=f"未识别有效列。当前列：{', '.join(reader.fieldnames[:8])}")

    rows = list(reader)
    preview_rows = []
    warnings: List[str] = []
    seen_dates: set = set()
    source_platform = _detect_platform_from_columns(reader.fieldnames)

    for i, row in enumerate(rows):
        date_val = row.get(col_map.get("date", ""), "").strip()
        normalized = _normalize_date(date_val)
        if not date_val:
            warnings.append(f"行 {i + 1}: 日期缺失")
            continue
        if not normalized:
            warnings.append(f"行 {i + 1}: 日期无法解析 '{date_val}'")
            continue
        if normalized in seen_dates:
            warnings.append(f"行 {i + 1}: 日期 '{normalized}' 重复")
        seen_dates.add(normalized)

        revenue = _parse_float(row.get(col_map.get("revenue", ""), "0"))
        orders = _parse_int(row.get(col_map.get("orders", ""), "0"))
        delivery_revenue = _parse_float(row.get(col_map.get("delivery_revenue", ""), "0"))
        delivery_orders = _parse_int(row.get(col_map.get("delivery_orders", ""), "0"))
        platform_fee = _parse_float(row.get(col_map.get("platform_fee", ""), "0"))
        marketing_cost = _parse_float(row.get(col_map.get("marketing_cost", ""), "0"))
        packaging_cost = _parse_float(row.get(col_map.get("packaging_cost", ""), "0"))

        # 校验警告
        if revenue <= 0 and orders <= 0:
            warnings.append(f"行 {i + 1}: 营收和订单均为 0")
        if revenue > 0 and delivery_revenue > revenue:
            warnings.append(f"行 {i + 1}: 外卖营收({delivery_revenue}) > 总营收({revenue})")
        if delivery_revenue > 0 and delivery_orders <= 0:
            warnings.append(f"行 {i + 1}: 外卖营收 > 0 但外卖单量为 0")
        if platform_fee < 0 or marketing_cost < 0:
            warnings.append(f"行 {i + 1}: 存在负数金额")

        if revenue > 0 and delivery_revenue <= 0:
            delivery_revenue = round(revenue * 0.4, 2)

        dine_in_revenue = max(0, revenue - delivery_revenue)
        dine_in_orders = max(0, orders - delivery_orders)

        preview_rows.append({
            "date": normalized,
            "revenue": revenue,
            "orders": orders,
            "dine_in_revenue": round(dine_in_revenue, 2),
            "dine_in_orders": dine_in_orders,
            "delivery_revenue": round(delivery_revenue, 2),
            "delivery_orders": delivery_orders,
            "platform_fee": round(platform_fee, 2),
            "marketing_cost": round(marketing_cost, 2),
            "packaging_cost": round(packaging_cost, 2),
            "source_quality_score": _compute_source_quality({
                "source_type": "csv", "source_confidence": "high",
                "revenue": revenue, "orders": orders,
                "food_cost": 0, "labor": 0,
            }),
        })

    return {
        "success": True,
        "columns_detected": list(col_map.keys()),
        "source_platform": source_platform,
        "preview_rows": preview_rows[:50],
        "total_rows": len(rows),
        "preview_count": len(preview_rows),
        "warnings": warnings[:20],
        "file_name": file.filename,
    }


@router.post("/{project_id}/import-csv/confirm")
async def confirm_delivery_csv(project_id: str, file: UploadFile = File(...),
                                strategy: str = Query("overwrite", description="overwrite / merge / skip_duplicates")):
    """确认导入 CSV：解析后写入 daily_operations，记录 source_trace。"""
    import csv
    import io
    from datetime import datetime as dt

    if strategy not in ("overwrite", "merge", "skip_duplicates"):
        raise HTTPException(status_code=400, detail="strategy 必须是 overwrite / merge / skip_duplicates")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("gbk")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="无法识别 CSV 编码")

    reader = csv.DictReader(io.StringIO(text))
    col_map = _detect_csv_columns(reader.fieldnames or [])
    if not col_map:
        raise HTTPException(status_code=400, detail="未识别有效列")

    source_platform = _detect_platform_from_columns(reader.fieldnames)
    now_iso = dt.now().isoformat()
    memory = _get_or_create_project(project_id)
    imported = 0
    skipped = 0

    for row in reader:
        date_val = row.get(col_map.get("date", ""), "").strip()
        normalized = _normalize_date(date_val)
        if not normalized:
            skipped += 1
            continue

        revenue = _parse_float(row.get(col_map.get("revenue", ""), "0"))
        orders = _parse_int(row.get(col_map.get("orders", ""), "0"))
        delivery_revenue = _parse_float(row.get(col_map.get("delivery_revenue", ""), "0"))
        delivery_orders = _parse_int(row.get(col_map.get("delivery_orders", ""), "0"))
        platform_fee = _parse_float(row.get(col_map.get("platform_fee", ""), "0"))
        marketing_cost = _parse_float(row.get(col_map.get("marketing_cost", ""), "0"))
        packaging_cost = _parse_float(row.get(col_map.get("packaging_cost", ""), "0"))

        if revenue > 0 and delivery_revenue <= 0:
            delivery_revenue = round(revenue * 0.4, 2)

        dine_in_revenue = max(0, revenue - delivery_revenue)
        dine_in_orders = max(0, orders - delivery_orders)

        entry = {
            "date": normalized,
            "revenue": revenue,
            "orders": orders,
            "dine_in_revenue": round(dine_in_revenue, 2),
            "dine_in_orders": dine_in_orders,
            "delivery_revenue": round(delivery_revenue, 2),
            "delivery_orders": delivery_orders,
            "food_cost": 0, "packaging_cost": round(packaging_cost, 2),
            "labor": 0, "rent_allocated": 0, "utility": 0, "other_cost": 0,
            "takeout_orders": delivery_orders,
            "platform_fee": round(platform_fee, 2),
            "marketing_cost": round(marketing_cost, 2),
            "inventory_loss": 0, "bad_reviews": 0, "repeat_orders": 0, "new_members": 0,
            "notes": f"CSV导入: {file.filename}",
            # source_trace
            "source_type": "csv",
            "source_platform": source_platform,
            "source_file_name": file.filename,
            "source_confidence": "high",
            "source_imported_at": now_iso,
        }
        memory.add_daily_operation(entry, strategy=strategy)
        imported += 1

    return {
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "strategy": strategy,
        "summary": memory.operation_summary(days=7),
    }


def _detect_platform_from_columns(headers: list) -> str:
    lowered = " ".join(h.lower() for h in headers)
    if "美团" in lowered or "meituan" in lowered:
        return "meituan"
    if "饿了么" in lowered or "eleme" in lowered:
        return "eleme"
    if "淘宝闪购" in lowered or "闪购" in lowered or "taobao" in lowered:
        return "taobao_flash"
    if "客如云" in lowered or "pos" in lowered or "收银" in lowered:
        return "pos"
    return "unknown"


def _detect_csv_columns(headers: List[str]) -> Dict[str, str]:
    """自动检测 CSV 列名映射。"""
    lowered = [h.strip().lower() for h in headers]
    mapping: Dict[str, str] = {}

    date_candidates = ["日期", "订单日", "日期时间", "下单日期", "date", "day", "时间"]
    revenue_candidates = ["营收", "实收", "销售额", "总金额", "收入", "流水", "revenue", "amount", "total"]
    orders_candidates = ["订单数", "有效订单", "总单量", "orders", "count"]
    delivery_rev_candidates = ["外卖营收", "外卖实收", "平台营收", "外卖收入", "美团实收", "闪购实收", "delivery"]
    delivery_orders_candidates = ["外卖订单", "外卖单", "平台订单", "delivery_orders"]
    platform_candidates = ["平台费", "佣金", "服务费", "扣点", "抽成", "platform", "commission", "fee"]
    marketing_candidates = ["营销", "推广费", "满减", "推广通", "美团券", "活动", "marketing", "promotion"]
    packaging_candidates = ["包装", "餐盒", "打包", "packaging"]

    for i, h in enumerate(lowered):
        original = headers[i].strip()
        if any(c in h for c in date_candidates):
            mapping.setdefault("date", original)
        if any(c in h for c in revenue_candidates):
            mapping.setdefault("revenue", original)
        if any(c in h for c in orders_candidates):
            mapping.setdefault("orders", original)
        if any(c in h for c in delivery_rev_candidates):
            mapping.setdefault("delivery_revenue", original)
        if any(c in h for c in delivery_orders_candidates):
            mapping.setdefault("delivery_orders", original)
        if any(c in h for c in platform_candidates):
            mapping.setdefault("platform_fee", original)
        if any(c in h for c in marketing_candidates):
            mapping.setdefault("marketing_cost", original)
        if any(c in h for c in packaging_candidates):
            mapping.setdefault("packaging_cost", original)

    if "date" not in mapping or ("revenue" not in mapping and "orders" not in mapping):
        return {}
    return mapping


def _normalize_date(raw: str) -> str:
    """标准化日期格式为 YYYY-MM-DD。"""
    raw = raw.strip()
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%m/%d/%Y", "%d/%m/%Y", "%Y年%m月%d日"]:
        try:
            from datetime import datetime
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def _parse_float(raw: str) -> float:
    try:
        return float(raw.strip().replace(",", "").replace("¥", "").replace("￥", "").replace("元", ""))
    except (ValueError, AttributeError):
        return 0.0


def _parse_int(raw: str) -> int:
    try:
        return int(float(raw.strip().replace(",", "")))
    except (ValueError, AttributeError):
        return 0


# ── 进货单写入 ──

from pydantic import BaseModel, Field


class PurchaseItemCapture(BaseModel):
    name: str
    quantity: float = 0.0
    unit_cost: float = 0.0


class PurchaseOrderCaptureItem(BaseModel):
    name: str = Field("", description="商品名称")
    quantity: float = Field(0.0, description="数量")
    unit_cost: float = Field(0.0, description="单价")
    sku_id: str = Field("", description="已匹配的 SKU ID（人工匹配时传入）")
    unit_conversion: float = Field(1.0, description="单位换算系数")
    is_ignored: bool = Field(False, description="是否忽略（非商品行）")


class PurchaseOrderCapture(BaseModel):
    date: str = Field("", description="进货日期 YYYY-MM-DD")
    supplier: str = Field("", description="供应商")
    items: list[PurchaseOrderCaptureItem] = Field(default_factory=list)
    file_name: str = Field("", description="原始文件名")
    source_type: str = Field("进货单", description="识别后的单据类型")
    human_modified_fields: list[str] = Field(default_factory=list)
    auto_create_aliases: bool = Field(True, description="人工匹配后是否自动写入别名库")


@router.post("/{project_id}/capture/purchase-order")
async def write_capture_purchase_order(project_id: str, req: PurchaseOrderCapture):
    """将进货单识别结果写入采购单，并自动更新 SKU 库存。

    匹配优先级：用户手动指定 sku_id > 别名库（同供应商优先）> SKU 名模糊匹配。
    人工匹配的条目默认自动写入别名库（auto_create_aliases=True）。
    """
    from models.sku import PurchaseRecord, SkuAlias, SkuCatalog

    if not req.date:
        raise HTTPException(status_code=400, detail="进货日期不能为空")
    if not req.items:
        raise HTTPException(status_code=400, detail="至少需要一条进货明细")

    catalog = SkuCatalog.load(project_id)
    if catalog is None:
        catalog = SkuCatalog.create(project_id)

    purchase_items = []
    match_details = []
    matched_count = 0
    unmatched_count = 0
    ignored_count = 0

    for idx, item in enumerate(req.items):
        if item.is_ignored:
            ignored_count += 1
            match_details.append({
                "index": idx,
                "name": item.name,
                "matched": False,
                "ignored": True,
                "match_type": "ignored",
                "sku_id": "",
                "sku_name": "",
                "quantity": item.quantity,
                "unit_cost": item.unit_cost,
                "stock_after": None,
            })
            continue

        sku_id = ""
        sku_name = ""
        match_type = "none"
        unit_conversion = item.unit_conversion or 1.0
        used_alias_id = ""

        if item.sku_id:
            sku = catalog.get_sku(item.sku_id)
            if sku:
                sku_id = sku["id"]
                sku_name = sku.get("name", "")
                match_type = "manual"
                if req.auto_create_aliases and req.supplier:
                    existing = catalog.match_alias(item.name, req.supplier)
                    if not existing:
                        alias = SkuAlias(
                            sku_id=sku_id,
                            alias=item.name,
                            supplier=req.supplier,
                            unit_conversion=unit_conversion,
                            alias_unit="",
                            source="auto_learn",
                        )
                        catalog.add_alias(alias)
        else:
            alias_match = catalog.match_alias(item.name, req.supplier)
            if alias_match:
                sku_id = alias_match.get("sku_id", "")
                sku = catalog.get_sku(sku_id)
                sku_name = sku.get("name", "") if sku else ""
                unit_conversion = alias_match.get("unit_conversion", 1.0)
                match_type = "alias"
                used_alias_id = alias_match.get("id", "")
            else:
                fuzzy_sku = next(
                    (s for s in catalog.skus if item.name in s.get("name", "") or s.get("name", "") in item.name),
                    None,
                )
                if fuzzy_sku:
                    sku_id = fuzzy_sku["id"]
                    sku_name = fuzzy_sku.get("name", "")
                    match_type = "fuzzy"

        base_qty = float(item.quantity) * unit_conversion

        if sku_id:
            matched_count += 1
            sku = catalog.get_sku(sku_id)
            current_stock = float(sku.get("current_stock", 0)) if sku else 0.0
            stock_after = round(current_stock + base_qty, 4)
        else:
            unmatched_count += 1
            stock_after = None

        purchase_items.append({
            "sku_id": sku_id,
            "name": item.name,
            "quantity": base_qty,
            "unit_cost": float(item.unit_cost) / unit_conversion if unit_conversion != 1.0 else item.unit_cost,
            "original_quantity": item.quantity,
            "original_unit_cost": item.unit_cost,
            "unit_conversion": unit_conversion,
            "match_type": match_type,
        })

        match_details.append({
            "index": idx,
            "name": item.name,
            "matched": bool(sku_id),
            "ignored": False,
            "match_type": match_type,
            "sku_id": sku_id,
            "sku_name": sku_name,
            "alias_id": used_alias_id,
            "quantity": base_qty,
            "original_quantity": item.quantity,
            "unit_cost": item.unit_cost,
            "unit_conversion": unit_conversion,
            "stock_after": stock_after,
        })

    active_items = [p for p in purchase_items if p.get("match_type") != "ignored_non_sku"]

    purchase = PurchaseRecord(
        date=req.date,
        supplier=req.supplier or "待确认",
        items=active_items,
        payment_status="未付",
    )
    saved = catalog.record_purchase(purchase)

    memory = _get_or_create_project(project_id)
    memory.add_capture_audit_log({
        "source_type": req.source_type,
        "file_name": req.file_name,
        "capture_kind": "document",
        "recognized_fields": [
            {"key": "total_items", "value": len(req.items)},
            {"key": "matched", "value": matched_count},
            {"key": "unmatched", "value": unmatched_count},
            {"key": "ignored", "value": ignored_count},
        ],
        "human_modified_fields": req.human_modified_fields,
        "review_status": "written" if unmatched_count == 0 else "partial_match",
        "write_target": "purchase_orders + inventory",
        "date": req.date,
    })

    total_amount = round(sum(float(i.get("original_quantity", 0)) * float(i.get("original_unit_cost", 0)) for i in match_details if not i.get("ignored")), 2)
    matched_amount = round(sum(float(i.get("quantity", 0)) * float(i.get("unit_cost", 0)) for i in match_details if i.get("matched")), 2)

    return {
        "success": True,
        "purchase_id": saved.id,
        "purchase_date": req.date,
        "supplier": req.supplier,
        "total_items": len(req.items),
        "matched_count": matched_count,
        "unmatched_count": unmatched_count,
        "ignored_count": ignored_count,
        "total_amount": total_amount,
        "matched_amount": matched_amount,
        "match_details": match_details,
    }


# ── 考勤工时写入 ──

class WorkRecordCapture(BaseModel):
    staff_name: str
    date: str = Field("", description="工作日期 YYYY-MM-DD")
    hours: float = Field(0.0, description="工时")
    shift: str = Field("", description="班次")
    overtime_hours: float = Field(0.0, description="加班工时")


@router.post("/{project_id}/capture/work-records")
async def write_capture_work_records(project_id: str, records: list[WorkRecordCapture]):
    """将考勤表识别结果批量写入工时记录。"""
    from models.labor import LaborTracking, WorkRecord
    tracking = LaborTracking.load(project_id)
    if tracking is None:
        tracking = LaborTracking.create(project_id)

    if not records:
        raise HTTPException(status_code=400, detail="至少需要一条工时记录")

    written = []
    for rec in records:
        if not rec.staff_name or not rec.date:
            continue
        # 尝试匹配员工
        staff = next((s for s in tracking.staff if s.get("name") == rec.staff_name), None)
        staff_id = str(staff.get("id", "")) if staff else ""
        work_record = WorkRecord(
            staff_id=staff_id,
            date=rec.date,
            shift=rec.shift,
            hours=rec.hours,
            overtime_hours=rec.overtime_hours,
        )
        saved = tracking.record_work(work_record)
        written.append(saved.to_dict())

    # 写入审计日志
    memory = _get_or_create_project(project_id)
    memory.add_capture_audit_log({
        "source_type": "image",
        "file_name": "",
        "capture_kind": "document",
        "recognized_fields": [{"key": "work_records", "value": len(written)}],
        "human_modified_fields": [],
        "review_status": "written",
        "write_target": "work_records",
    })

    return {
        "success": True,
        "written_count": len(written),
        "records": written,
    }
