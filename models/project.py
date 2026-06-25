#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ProjectMemory：项目档案持久化模型。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import PROJECT_DATA_DIR


@dataclass
class ProjectMemory:
    """独立于会话的项目档案，支持跨会话持久化。"""
    project_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    profile: Dict[str, Any] = field(default_factory=dict)
    franchise_constraints: Dict[str, Any] = field(default_factory=dict)
    site_transfer: Dict[str, Any] = field(default_factory=dict)
    candidate_sites: List[Dict[str, Any]] = field(default_factory=list)
    financial_models: List[Dict[str, Any]] = field(default_factory=list)
    daily_operations: List[Dict[str, Any]] = field(default_factory=list)
    field_observations: List[Dict[str, Any]] = field(default_factory=list)
    risk_register: List[Dict[str, Any]] = field(default_factory=list)
    action_tasks: List[Dict[str, Any]] = field(default_factory=list)
    experiment_log: List[Dict[str, Any]] = field(default_factory=list)
    review_reports: List[Dict[str, Any]] = field(default_factory=list)
    integrations: List[Dict[str, Any]] = field(default_factory=list)
    delivery_imports: List[Dict[str, Any]] = field(default_factory=list)
    decisions_log: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, str]] = field(default_factory=list)

    @property
    def data_dir(self) -> Path:
        return PROJECT_DATA_DIR / self.project_id

    def save(self):
        """持久化到磁盘。"""
        self.updated_at = time.time()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / "memory.json"
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, project_id: str) -> Optional["ProjectMemory"]:
        """从磁盘加载，不存在返回 None。"""
        path = PROJECT_DATA_DIR / project_id / "memory.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**data)
        except Exception:
            return None

    @classmethod
    def create(cls, project_id: str) -> "ProjectMemory":
        """创建新项目档案。"""
        memory = cls(project_id=project_id)
        memory.save()
        return memory

    def update_profile(self, profile_dict: Dict[str, Any]):
        """更新项目画像。"""
        self.profile.update(profile_dict)
        self.save()

    def update_franchise_constraints(self, constraints: Dict[str, Any]):
        """更新加盟约束。"""
        self.franchise_constraints.update(constraints)
        self.save()

    def update_site_transfer(self, site_transfer: Dict[str, Any]):
        """更新转租/铺位接手信息。"""
        self.site_transfer.update(site_transfer)
        self.save()

    def add_site(self, site_data: Dict[str, Any]):
        """添加候选铺位。"""
        site_data["added_at"] = time.time()
        self.candidate_sites.append(site_data)
        self.save()

    def add_financial_model(self, model_data: Dict[str, Any]):
        """添加财务测算版本。"""
        model_data["created_at"] = time.time()
        self.financial_models.append(model_data)
        self.save()

    def cockpit_summary(self, days: int = 7) -> Dict[str, Any]:
        """生命周期驾驶舱：统一筹备假设、经营流水、风险和下一步动作。"""
        operations = self.operation_summary(days=days)
        baseline = self.financial_models[-1] if self.financial_models else {}
        current_stage = self.profile.get("current_stage") or self.profile.get("阶段") or "开业计划"
        stages = _lifecycle_stages(current_stage)
        comparison = _baseline_comparison(baseline, operations)
        data_quality = _data_quality(self, operations, baseline)
        decision = _decision_brief(operations, baseline, data_quality)

        return {
            "project_id": self.project_id,
            "profile": self.profile,
            "current_stage": current_stage,
            "stages": stages,
            "baseline": baseline,
            "baseline_comparison": comparison,
            "operations": operations,
            "recent_operations": self.daily_operations[-days:] if days > 0 else self.daily_operations,
            "data_quality": data_quality,
            "decision": decision,
            "next_actions": _next_actions(data_quality, decision, current_stage, self.action_tasks),
            "tasks": self.action_tasks,
            "integrations": self.integration_status(),
            "evidence": _evidence(self, operations, baseline),
        }

    def add_daily_operation(self, entry: Dict[str, Any]):
        """添加或覆盖单日经营数据。"""
        date = entry.get("date")
        entry["created_at"] = entry.get("created_at", time.time())
        entry["updated_at"] = time.time()
        if date:
            self.daily_operations = [
                old for old in self.daily_operations if old.get("date") != date
            ]
        self.daily_operations.append(entry)
        self.daily_operations.sort(key=lambda item: item.get("date", ""))
        self.save()

    def operation_summary(self, days: int = 7) -> Dict[str, Any]:
        """汇总最近 N 条经营数据。"""
        entries = self.daily_operations[-days:] if days > 0 else self.daily_operations
        total_revenue = sum(float(e.get("revenue", 0) or 0) for e in entries)
        total_orders = sum(int(e.get("orders", 0) or 0) for e in entries)
        total_food_cost = sum(float(e.get("food_cost", 0) or 0) for e in entries)
        total_labor = sum(float(e.get("labor", 0) or 0) for e in entries)
        total_rent = sum(float(e.get("rent_allocated", 0) or 0) for e in entries)
        total_utility = sum(float(e.get("utility", 0) or 0) for e in entries)
        total_other = sum(float(e.get("other_cost", 0) or 0) for e in entries)
        total_takeout = sum(int(e.get("takeout_orders", 0) or 0) for e in entries)
        total_marketing = sum(float(e.get("marketing_cost", 0) or 0) for e in entries)
        total_platform = sum(float(e.get("platform_fee", 0) or 0) for e in entries)
        total_loss = sum(float(e.get("inventory_loss", 0) or 0) for e in entries)
        total_bad_reviews = sum(int(e.get("bad_reviews", 0) or 0) for e in entries)
        prime_cost = total_food_cost + total_labor
        total_cost = (
            total_food_cost + total_labor + total_rent + total_utility +
            total_other + total_marketing + total_platform + total_loss
        )
        net_profit = total_revenue - total_cost
        avg_order_value = total_revenue / total_orders if total_orders else 0
        food_cost_rate = total_food_cost / total_revenue if total_revenue else 0
        labor_cost_rate = total_labor / total_revenue if total_revenue else 0
        prime_cost_rate = prime_cost / total_revenue if total_revenue else 0
        platform_fee_rate = total_platform / total_revenue if total_revenue else 0
        bad_review_rate = total_bad_reviews / total_orders if total_orders else 0
        takeout_ratio = total_takeout / total_orders if total_orders else 0

        alerts: List[Dict[str, str]] = []
        if entries and net_profit < 0:
            alerts.append({
                "level": "high",
                "message": "最近经营数据为亏损，先检查食材成本、人工和平台活动是否吃掉毛利。",
            })
        if food_cost_rate > 0.4:
            alerts.append({
                "level": "medium",
                "message": "食材成本率超过 40%，需要核对总部供货价、损耗和套餐毛利。",
            })
        if prime_cost_rate > 0.65:
            alerts.append({
                "level": "medium",
                "message": "Prime Cost 超过 65%，食材和人工合计已经压缩利润空间。",
            })
        if bad_review_rate > 0.03:
            alerts.append({
                "level": "medium",
                "message": "差评率超过 3%，需要拆解出餐、包装、口味和配送原因。",
            })
        if takeout_ratio > 0.5 and total_platform + total_marketing > total_revenue * 0.12:
            alerts.append({
                "level": "medium",
                "message": "外卖占比高且平台/活动成本偏重，需要单独核算外卖单均利润。",
            })

        return {
            "days": days,
            "entry_count": len(entries),
            "total_revenue": round(total_revenue, 2),
            "total_orders": total_orders,
            "avg_order_value": round(avg_order_value, 2),
            "total_cost": round(total_cost, 2),
            "net_profit": round(net_profit, 2),
            "food_cost_rate": round(food_cost_rate, 4),
            "labor_cost_rate": round(labor_cost_rate, 4),
            "prime_cost": round(prime_cost, 2),
            "prime_cost_rate": round(prime_cost_rate, 4),
            "platform_fee_rate": round(platform_fee_rate, 4),
            "total_bad_reviews": total_bad_reviews,
            "bad_review_rate": round(bad_review_rate, 4),
            "takeout_ratio": round(takeout_ratio, 4),
            "latest_entry": entries[-1] if entries else None,
            "alerts": alerts,
        }

    def add_decision(self, decision: Dict[str, Any]):
        """记录决策。"""
        decision["timestamp"] = time.time()
        self.decisions_log.append(decision)
        self.save()

    def add_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """创建行动任务。"""
        now = time.time()
        normalized = {
            "id": task.get("id") or f"task-{int(now * 1000)}",
            "title": task.get("title", "未命名任务"),
            "target": task.get("target", "工作台"),
            "priority": task.get("priority", "medium"),
            "source": task.get("source", "manual"),
            "status": task.get("status", "todo"),
            "due_date": task.get("due_date", ""),
            "notes": task.get("notes", ""),
            "created_at": task.get("created_at", now),
            "updated_at": now,
        }
        existing_ids = {item.get("id") for item in self.action_tasks}
        if normalized["id"] in existing_ids:
            self.update_task(normalized["id"], normalized)
            return next(item for item in self.action_tasks if item.get("id") == normalized["id"])
        existing_key = _task_key(normalized["title"], normalized["target"])
        for task in self.action_tasks:
            if _task_key(task.get("title", ""), task.get("target", "")) == existing_key:
                return self.update_task(task["id"], {**normalized, "id": task["id"]})
        self.action_tasks.append(normalized)
        self.save()
        return normalized

    def update_task(self, task_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """更新行动任务。"""
        for task in self.action_tasks:
            if task.get("id") == task_id:
                task.update({key: value for key, value in patch.items() if value is not None})
                task["updated_at"] = time.time()
                self.save()
                return task
        raise KeyError(task_id)

    def integration_status(self) -> List[Dict[str, Any]]:
        """返回门店系统接入状态，补齐默认连接器但不伪造已接入。"""
        by_id = {item.get("id"): item for item in self.integrations}
        result = []
        for default in _default_integrations():
            merged = {**default, **by_id.get(default["id"], {})}
            result.append(merged)
        for item in self.integrations:
            if item.get("id") not in {default["id"] for default in _default_integrations()}:
                result.append(item)
        return result

    def update_integration(self, integration_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """更新系统接入状态。"""
        now = time.time()
        default_by_id = {item["id"]: item for item in _default_integrations()}
        base = default_by_id.get(integration_id, {"id": integration_id, "name": integration_id})
        for integration in self.integrations:
            if integration.get("id") == integration_id:
                integration.update({key: value for key, value in patch.items() if value is not None})
                integration["updated_at"] = now
                self.save()
                return {**base, **integration}
        created = {
            **base,
            **{key: value for key, value in patch.items() if value is not None},
            "id": integration_id,
            "updated_at": now,
        }
        self.integrations.append(created)
        self.save()
        return created

    def add_delivery_import(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """记录外卖平台笨办法导入，保留原始文本和解析摘要。"""
        now = time.time()
        entry = {
            "id": payload.get("id") or f"delivery-import-{int(now * 1000)}",
            "source": payload.get("source", "manual"),
            "raw_text": payload.get("raw_text", ""),
            "parsed": payload.get("parsed", {}),
            "created_at": now,
        }
        self.delivery_imports.append(entry)
        self.save()
        return entry


def _lifecycle_stages(current_stage: str) -> List[Dict[str, Any]]:
    labels = [
        "想开店念头",
        "选址诊断",
        "合同与加盟",
        "财务测算",
        "装修证照",
        "开业计划",
        "运营接管",
        "复购增长",
        "连锁拓展",
    ]
    current_index = labels.index(current_stage) if current_stage in labels else 1
    result = []
    for index, label in enumerate(labels):
        if index < current_index:
            status = "done"
        elif index == current_index:
            status = "current"
        else:
            status = "pending"
        result.append({
            "label": label,
            "status": status,
            "battlefield": "core" if 1 <= index <= 5 else "extension",
        })
    return result


def _baseline_comparison(baseline: Dict[str, Any], operations: Dict[str, Any]) -> Dict[str, Any]:
    projected_daily_revenue = _first_number(
        baseline,
        ["daily_revenue", "expected_daily_revenue", "日均营业额", "预期日营收"],
    )
    projected_orders = _first_number(
        baseline,
        ["daily_orders", "expected_daily_orders", "日均订单", "预期日订单"],
    )
    actual_daily_revenue = (
        operations["total_revenue"] / operations["entry_count"]
        if operations.get("entry_count") else None
    )
    actual_daily_orders = (
        operations["total_orders"] / operations["entry_count"]
        if operations.get("entry_count") else None
    )
    return {
        "projected_daily_revenue": projected_daily_revenue,
        "actual_daily_revenue": round(actual_daily_revenue, 2) if actual_daily_revenue is not None else None,
        "revenue_gap": (
            round(actual_daily_revenue - projected_daily_revenue, 2)
            if actual_daily_revenue is not None and projected_daily_revenue is not None else None
        ),
        "projected_daily_orders": projected_orders,
        "actual_daily_orders": round(actual_daily_orders, 2) if actual_daily_orders is not None else None,
        "orders_gap": (
            round(actual_daily_orders - projected_orders, 2)
            if actual_daily_orders is not None and projected_orders is not None else None
        ),
    }


def _data_quality(memory: ProjectMemory, operations: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    missing = []
    if not baseline:
        missing.append("财务测算 baseline")
    if not memory.franchise_constraints:
        missing.append("加盟合同/总部约束")
    if not memory.site_transfer:
        missing.append("转租费、押金、租金结构")
    if operations.get("entry_count", 0) < 7:
        missing.append("连续 7 天经营流水")
    if not memory.candidate_sites:
        missing.append("选址/竞品验证记录")
    return {
        "level": "weak" if missing else "usable",
        "missing": missing,
        "has_real_operations": operations.get("entry_count", 0) > 0,
        "operation_days": operations.get("entry_count", 0),
        "has_baseline": bool(baseline),
    }


def _decision_brief(operations: Dict[str, Any], baseline: Dict[str, Any], data_quality: Dict[str, Any]) -> Dict[str, Any]:
    if not operations.get("entry_count"):
        contradiction = "缺真实经营流水，无法验证筹备期假设"
    elif operations.get("entry_count", 0) < 7:
        contradiction = "样本周期太短，先补齐 7 天流水"
    elif operations.get("net_profit", 0) < 0:
        contradiction = "经营现金流为负，优先查毛利、人工和平台成本"
    elif operations.get("food_cost_rate", 0) > 0.4:
        contradiction = "食材成本率偏高，核对总部供货价与损耗"
    else:
        contradiction = "进入持续优化阶段，重点验证复购和可复制性"

    return {
        "decision": "Needs Data" if data_quality["missing"] else "Monitor",
        "primary_contradiction": contradiction,
        "summary": "当前判断只基于统一项目账本；没有录入的数据不会用 mock 数字替代。",
    }


def _next_actions(
    data_quality: Dict[str, Any],
    decision: Dict[str, Any],
    current_stage: str,
    saved_tasks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    actions = []
    for item in data_quality["missing"][:4]:
        actions.append({
            "id": f"fill-{len(actions) + 1}",
            "title": f"补齐：{item}",
            "priority": "high" if item in {"财务测算 baseline", "连续 7 天经营流水"} else "medium",
            "target": _action_target(item),
            "source": "data_quality",
            "status": "pending",
        })
    actions.append({
        "id": "stage-review",
        "title": f"复核当前阶段：{current_stage}",
        "priority": "medium",
        "target": "工作台",
        "source": decision["primary_contradiction"],
        "status": "pending",
    })
    by_key = {
        _task_key(task.get("title", ""), task.get("target", "")): task
        for task in saved_tasks
    }
    for action in actions:
        saved = by_key.get(_task_key(action["title"], action["target"]))
        if not saved:
            continue
        action["task_id"] = saved.get("id")
        action["status"] = saved.get("status", "todo")
        action["due_date"] = saved.get("due_date", "")
    return actions


def _evidence(memory: ProjectMemory, operations: Dict[str, Any], baseline: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence = []
    evidence.append({
        "label": "经营流水",
        "source_type": "user_store_ledger",
        "confidence": "high" if operations.get("entry_count") else "missing",
        "detail": f"{operations.get('entry_count', 0)} 天记录",
    })
    evidence.append({
        "label": "筹备期财务 baseline",
        "source_type": "project_memory",
        "confidence": "medium" if baseline else "missing",
        "detail": "已保存" if baseline else "未保存",
    })
    evidence.append({
        "label": "加盟/合同约束",
        "source_type": "project_memory",
        "confidence": "medium" if memory.franchise_constraints else "missing",
        "detail": "已录入" if memory.franchise_constraints else "未录入",
    })
    return evidence


def _first_number(data: Dict[str, Any], keys: List[str]) -> Optional[float]:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            return float(str(value).replace("¥", "").replace(",", "").replace("元", ""))
        except ValueError:
            continue
    return None


def _action_target(missing_item: str) -> str:
    if "财务" in missing_item:
        return "财务测算"
    if "流水" in missing_item:
        return "收支记账"
    if "加盟" in missing_item or "合同" in missing_item:
        return "合同与加盟"
    if "转租" in missing_item or "租金" in missing_item:
        return "项目总览"
    if "选址" in missing_item or "竞品" in missing_item:
        return "选址诊断"
    return "工作台"


def _task_key(title: str, target: str) -> str:
    return f"{title.strip()}::{target.strip()}"


def _default_integrations() -> List[Dict[str, Any]]:
    return [
        {
            "id": "meituan",
            "name": "美团",
            "scope": "外卖/团购/评价",
            "status": "pending_auth",
            "status_label": "待授权接入",
            "fallback": "先支持手工录入、商家后台导出和截图/OCR。",
            "available_paths": ["manual", "csv_export", "screenshot_ocr", "official_api_later"],
        },
        {
            "id": "taobao_flash",
            "name": "淘宝闪购",
            "scope": "外卖订单/平台费",
            "status": "pending_auth",
            "status_label": "待授权接入",
            "fallback": "先按日汇总录入订单、平台费、活动成本。",
            "available_paths": ["manual", "csv_export", "screenshot_ocr", "official_api_later"],
        },
        {
            "id": "douyin",
            "name": "抖音",
            "scope": "同城内容/团购核销",
            "status": "pending_auth",
            "status_label": "待授权接入",
            "fallback": "先记录内容链接、投流成本、团购核销和评论反馈。",
            "available_paths": ["manual", "creator_link", "export_file", "rpa_later"],
        },
        {
            "id": "xiaohongshu",
            "name": "小红书",
            "scope": "种草笔记/搜索占位",
            "status": "semi_manual",
            "status_label": "半自动采集",
            "fallback": "先录入笔记链接、互动数、关键词排名和到店反馈。",
            "available_paths": ["manual", "link_capture", "screenshot_ocr"],
        },
        {
            "id": "private_domain",
            "name": "私域",
            "scope": "微信群/会员/集章",
            "status": "manual_ready",
            "status_label": "可先手工运营",
            "fallback": "先建顾客触达台账，记录入群、复购、券核销。",
            "available_paths": ["manual", "spreadsheet_import"],
        },
        {
            "id": "pos",
            "name": "收银/POS",
            "scope": "营业额/订单",
            "status": "import_ready",
            "status_label": "待导入",
            "fallback": "先支持收银截图、CSV/Excel 导入和每日总账录入。",
            "available_paths": ["manual", "csv_import", "screenshot_ocr"],
        },
    ]
