#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SKU 与进货路由：商品/物料管理和补货预测。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models.sku import (
    InventoryCount,
    ProductionBatch,
    PurchaseRecord,
    SkuAlias,
    SkuCatalog,
    SkuItem,
    UsageLog,
)
from server.schemas import (
    InventoryCountCreate,
    InventoryTransferCreate,
    InventoryUsageCreate,
    InventoryWasteCreate,
    ProductionBatchClose,
    ProductionBatchCreate,
    PurchaseCreate,
    PurchaseReceiptCreate,
    SkuAliasBatchMatchRequest,
    SkuAliasCreate,
    SkuAliasUpdate,
    SkuCreate,
    SkuUpdate,
)

router = APIRouter(prefix="/projects", tags=["skus"])


def _catalog(project_id: str) -> SkuCatalog:
    catalog = SkuCatalog.load(project_id)
    if catalog is None:
        catalog = SkuCatalog.create(project_id)
    return catalog


# ── 列表与创建 ──

@router.get("/{project_id}/skus")
async def list_skus(
    project_id: str,
    category: Optional[str] = Query(None, description="按品类筛选"),
):
    catalog = _catalog(project_id)
    if category:
        grouped = catalog.by_category()
        skus = grouped.get(category, [])
    else:
        skus = catalog.skus
    return {
        "skus": skus,
        "categories": list(catalog.by_category().keys()),
        "total": len(catalog.skus),
    }


@router.post("/{project_id}/skus")
async def create_sku(project_id: str, req: SkuCreate):
    catalog = _catalog(project_id)
    sku = SkuItem(
        name=req.name,
        category=req.category,
        unit=req.unit,
        safety_stock=req.safety_stock,
        current_stock=req.current_stock,
        unit_cost=req.unit_cost,
        supplier=req.supplier,
        batch_cycle_days=req.batch_cycle_days,
        consumption_per_day=req.consumption_per_day,
        stock_by_location=req.stock_by_location,
        count_units=req.count_units,
        tracking_mode=req.tracking_mode,
        daily_usage_group=req.daily_usage_group,
        daily_usage_sort=req.daily_usage_sort,
        display_unit=req.display_unit,
        store_target_days=req.store_target_days,
        supplier_lead_days=req.supplier_lead_days,
        reorder_enabled=req.reorder_enabled,
        usage_integer_only=req.usage_integer_only,
        notes=req.notes,
        status="正常",
    )
    saved = catalog.add_sku(sku)
    return {"success": True, "sku": saved.to_dict()}


# ── 固定路径子资源（必须在 /{sku_id} 之前注册，避免路由冲突）──

@router.get("/{project_id}/skus/forecast")
async def get_forecast(project_id: str, revenue_growth: float = Query(1.0, ge=0.5, le=3.0, description="月营收增长率因子")):
    catalog = _catalog(project_id)
    forecast = catalog.forecast(revenue_growth_factor=revenue_growth)
    return {"forecast": forecast, "total_skus": len(catalog.skus)}


@router.post("/{project_id}/skus/purchase")
async def create_purchase(project_id: str, req: PurchaseCreate):
    catalog = _catalog(project_id)
    purchase = PurchaseRecord(
        date=req.date,
        supplier=req.supplier,
        items=[item.model_dump() if hasattr(item, "model_dump") else item.dict() for item in req.items],
        payment_status=req.payment_status,
        paid_amount=req.paid_amount,
        fulfillment_status=req.fulfillment_status,
        external_order_id=req.external_order_id,
        location=req.location,
        notes=req.notes,
        platform=req.platform,
        freight=req.freight,
        discount_amount=req.discount_amount,
        refund_amount=req.refund_amount,
        evidence_file=req.evidence_file,
        accounting_status=req.accounting_status,
    )
    saved = catalog.record_purchase(purchase)
    return {
        "success": True,
        "purchase": saved.to_dict(),
        "forecast": catalog.forecast(),
    }


@router.get("/{project_id}/skus/purchases")
async def list_purchases(project_id: str, limit: int = Query(30, ge=1, le=200)):
    catalog = _catalog(project_id)
    purchases = catalog.get_purchases(limit=limit)
    return {"purchases": purchases, "total": len(catalog.purchases)}


@router.post("/{project_id}/skus/purchases/{purchase_id}/receive")
async def receive_purchase(project_id: str, purchase_id: str, req: PurchaseReceiptCreate):
    catalog = _catalog(project_id)
    try:
        purchase = catalog.record_receipt(
            purchase_id=purchase_id,
            date=req.date,
            items=[item.model_dump() for item in req.items],
            source=req.source,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "purchase": purchase,
        "summary": catalog.inventory_summary(),
        "forecast": catalog.forecast(),
    }


@router.get("/{project_id}/production-batches")
async def list_production_batches(project_id: str, limit: int = Query(60, ge=1, le=365)):
    catalog = _catalog(project_id)
    batches = catalog.get_production_batches(limit=limit)
    return {"batches": batches, "total": len(catalog.production_batches)}


@router.post("/{project_id}/production-batches")
async def create_production_batch(project_id: str, req: ProductionBatchCreate):
    catalog = _catalog(project_id)
    try:
        batch = catalog.record_production(ProductionBatch(
            date=req.date,
            name=req.name,
            location=req.location,
            inputs=[item.model_dump() for item in req.inputs],
            output_quantity=req.output_quantity,
            output_unit=req.output_unit,
            pan_cycle_minutes=req.pan_cycle_minutes,
            source=req.source,
            notes=req.notes,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "batch": batch.to_dict(),
        "summary": catalog.inventory_summary(),
    }


@router.post("/{project_id}/production-batches/{batch_id}/close")
async def close_production_batch(
    project_id: str,
    batch_id: str,
    req: ProductionBatchClose,
):
    catalog = _catalog(project_id)
    try:
        batch = catalog.close_production(
            batch_id=batch_id,
            used_quantity=req.used_quantity,
            waste_quantity=req.waste_quantity,
            actual_pan_cycles=req.actual_pan_cycles,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "batch": batch,
        "summary": catalog.inventory_summary(),
    }


@router.get("/{project_id}/skus/inventory-summary")
async def get_inventory_summary(project_id: str):
    catalog = _catalog(project_id)
    return catalog.inventory_summary()


@router.get("/{project_id}/skus/inventory-events")
async def list_inventory_events(project_id: str, limit: int = Query(100, ge=1, le=500)):
    catalog = _catalog(project_id)
    events = catalog.get_events(limit=limit)
    return {"events": events, "total": len(catalog.inventory_events)}


@router.post("/{project_id}/skus/transfer")
async def create_inventory_transfer(project_id: str, req: InventoryTransferCreate):
    catalog = _catalog(project_id)
    try:
        events = catalog.record_transfer(
            date=req.date,
            from_location=req.from_location,
            to_location=req.to_location,
            items=[item.model_dump() for item in req.items],
            source=req.source,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "events": events, "summary": catalog.inventory_summary()}


@router.get("/{project_id}/skus/usage-logs")
async def list_inventory_usage(project_id: str, limit: int = Query(60, ge=1, le=365)):
    catalog = _catalog(project_id)
    logs = catalog.get_usage_logs(limit=limit)
    return {"logs": logs, "total": len(catalog.usage_logs)}


@router.get("/{project_id}/skus/usage-summary/{date}")
async def get_inventory_usage_summary(project_id: str, date: str):
    return _catalog(project_id).daily_usage_summary(date)


@router.post("/{project_id}/skus/usage-logs")
async def create_inventory_usage(project_id: str, req: InventoryUsageCreate):
    catalog = _catalog(project_id)
    try:
        saved = catalog.record_usage(UsageLog(
            date=req.date,
            location=req.location,
            items=[item.model_dump() for item in req.items],
            source=req.source,
            notes=req.notes,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "log": saved.to_dict(), "summary": catalog.inventory_summary()}


@router.put("/{project_id}/skus/usage-logs/{date}")
async def replace_inventory_usage(project_id: str, date: str, req: InventoryUsageCreate):
    if req.date != date:
        raise HTTPException(status_code=400, detail="路径日期与表单日期必须一致")
    catalog = _catalog(project_id)
    try:
        saved = catalog.replace_daily_usage(UsageLog(
            date=req.date,
            location=req.location,
            items=[item.model_dump() for item in req.items],
            source=req.source,
            notes=req.notes,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "log": saved.to_dict(),
        "usage_summary": catalog.daily_usage_summary(date),
        "summary": catalog.inventory_summary(),
    }


@router.post("/{project_id}/skus/waste")
async def create_inventory_waste(project_id: str, req: InventoryWasteCreate):
    catalog = _catalog(project_id)
    try:
        events = catalog.record_waste(
            date=req.date,
            location=req.location,
            items=[item.model_dump() for item in req.items],
            reason=req.reason,
            source=req.source,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "events": events, "summary": catalog.inventory_summary()}


@router.get("/{project_id}/skus/counts")
async def list_inventory_counts(project_id: str, limit: int = Query(30, ge=1, le=200)):
    catalog = _catalog(project_id)
    counts = catalog.get_counts(limit=limit)
    return {"counts": counts, "total": len(catalog.inventory_counts)}


@router.post("/{project_id}/skus/counts")
async def create_inventory_count(project_id: str, req: InventoryCountCreate):
    catalog = _catalog(project_id)
    try:
        saved = catalog.record_count(InventoryCount(
            date=req.date,
            location=req.location,
            count_type=req.count_type,
            lines=[line.model_dump() for line in req.lines],
            source=req.source,
            notes=req.notes,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "count": saved.to_dict(),
        "summary": catalog.inventory_summary(),
        "variance": catalog.variance_analysis(),
    }


@router.get("/{project_id}/skus/variance-analysis")
async def get_inventory_variance(project_id: str, limit: int = Query(12, ge=1, le=100)):
    catalog = _catalog(project_id)
    return catalog.variance_analysis(limit=limit)


@router.get("/{project_id}/skus/consumption-variance")
async def get_consumption_variance(
    project_id: str,
    period_start: str = Query(..., description="期间开始日期 YYYY-MM-DD"),
    period_end: str = Query(..., description="期间结束日期 YYYY-MM-DD"),
):
    """SKU 期间实际消耗 vs 理论消耗差异。

    实际消耗 = 期初库存 + 采购 - 领用 - 损耗 - 期末盘点
    理论消耗 = 商品销量 × BOM（BOM 或销量缺失时标记为暂不可核验）。
    """
    catalog = _catalog(project_id)
    return catalog.consumption_variance_analysis(
        period_start=period_start,
        period_end=period_end,
    )


@router.get("/{project_id}/skus/menu-analysis")
async def get_menu_analysis(project_id: str):
    catalog = _catalog(project_id)
    return {"items": catalog.menu_analysis(), "total": len(catalog.skus)}


# ── SKU 别名映射 ──

@router.get("/{project_id}/skus/aliases")
async def list_aliases(
    project_id: str,
    sku_id: Optional[str] = Query(None, description="按 SKU 筛选"),
    supplier: Optional[str] = Query(None, description="按供应商筛选"),
):
    catalog = _catalog(project_id)
    aliases = catalog.list_aliases(sku_id=sku_id, supplier=supplier)
    return {"aliases": aliases, "total": len(aliases)}


@router.post("/{project_id}/skus/aliases")
async def create_alias(project_id: str, req: SkuAliasCreate):
    catalog = _catalog(project_id)
    if catalog.get_sku(req.sku_id) is None:
        raise HTTPException(status_code=404, detail="sku not found")
    alias = SkuAlias(
        sku_id=req.sku_id,
        alias=req.alias,
        supplier=req.supplier,
        unit_conversion=req.unit_conversion,
        alias_unit=req.alias_unit,
        source=req.source,
    )
    saved = catalog.add_alias(alias)
    return {"success": True, "alias": saved.to_dict()}


@router.post("/{project_id}/skus/aliases/batch-match")
async def batch_match_aliases(project_id: str, req: SkuAliasBatchMatchRequest):
    """批量匹配供应商品名到 SKU，返回每条的匹配结果。"""
    catalog = _catalog(project_id)
    results = []
    for item in req.items:
        matched = catalog.match_alias(item.name, item.supplier)
        sku_name = ""
        sku_id = ""
        if matched:
            sku_id = matched.get("sku_id", "")
            sku = catalog.get_sku(sku_id)
            sku_name = sku.get("name", "") if sku else ""
        results.append({
            "name": item.name,
            "supplier": item.supplier,
            "matched": matched is not None,
            "sku_id": sku_id,
            "sku_name": sku_name,
            "alias_id": matched.get("id", "") if matched else "",
            "unit_conversion": matched.get("unit_conversion", 1.0) if matched else 1.0,
            "match_type": "alias" if matched else "none",
        })
    return {"results": results}


@router.get("/{project_id}/skus/aliases/{alias_id}")
async def get_alias(project_id: str, alias_id: str):
    catalog = _catalog(project_id)
    alias = catalog.get_alias(alias_id)
    if alias is None:
        raise HTTPException(status_code=404, detail="alias not found")
    return {"alias": alias}


@router.patch("/{project_id}/skus/aliases/{alias_id}")
async def update_alias(project_id: str, alias_id: str, req: SkuAliasUpdate):
    catalog = _catalog(project_id)
    payload = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    updated = catalog.update_alias(alias_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="alias not found")
    return {"success": True, "alias": updated}


@router.delete("/{project_id}/skus/aliases/{alias_id}")
async def delete_alias(project_id: str, alias_id: str):
    catalog = _catalog(project_id)
    if not catalog.delete_alias(alias_id):
        raise HTTPException(status_code=404, detail="alias not found")
    return {"success": True}


# ── 单条 SKU CRUD（/{sku_id} 参数化路由）──

@router.get("/{project_id}/skus/{sku_id}")
async def get_sku(project_id: str, sku_id: str):
    catalog = _catalog(project_id)
    sku = catalog.get_sku(sku_id)
    if sku is None:
        raise HTTPException(status_code=404, detail="sku not found")
    return {"sku": sku}


@router.patch("/{project_id}/skus/{sku_id}")
async def update_sku(project_id: str, sku_id: str, req: SkuUpdate):
    catalog = _catalog(project_id)
    payload = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    updated = catalog.update_sku(sku_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="sku not found")
    return {"success": True, "sku": updated}


@router.delete("/{project_id}/skus/{sku_id}")
async def delete_sku(project_id: str, sku_id: str):
    catalog = _catalog(project_id)
    if not catalog.delete_sku(sku_id):
        raise HTTPException(status_code=404, detail="sku not found")
    return {"success": True}
