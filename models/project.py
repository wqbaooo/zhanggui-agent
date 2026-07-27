#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ProjectMemory：项目档案持久化模型。"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import PROJECT_DATA_DIR
from models.json_store import atomic_write_json, load_json


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
    monthly_revenue: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, str]] = field(default_factory=list)
    capture_audit_log: List[Dict[str, Any]] = field(default_factory=list)

    def monthly_summary(self) -> Dict[str, Any]:
        """月度经营汇总。

        营业额与净利润是不同指标，只允许各自与上年同指标比较。
        """
        entries = sorted(
            self.monthly_revenue,
            key=lambda item: (int(item.get("year", 0)), int(item.get("month", 0))),
        )
        rent = self.profile.get("monthly_rent", 0)
        wage_per_person = self.profile.get("wage_per_person", 0)
        current_staff_count = self.profile.get("current_staff_count", 0)
        previous_staff_count = self.profile.get("previous_staff_count", 0)
        labor = self.profile.get("monthly_labor", wage_per_person * current_staff_count)
        utility_avg = (
            (self.profile.get("monthly_utility_min", 0) + self.profile.get("monthly_utility_max", 0)) / 2
        )
        estimated_monthly_cost = rent + labor + utility_avg

        years = sorted({int(e["year"]) for e in entries if e.get("year") is not None})
        revenue_years = sorted({
            int(e["year"]) for e in entries
            if e.get("year") is not None and e.get("revenue") is not None
        })
        current_year = revenue_years[-1] if revenue_years else (years[-1] if years else None)
        baseline_years = sorted({
            int(e["year"]) for e in entries
            if e.get("year") is not None
            and e.get("net_profit") is not None
            and (current_year is None or int(e["year"]) < current_year)
        })
        baseline_year = baseline_years[-1] if baseline_years else (
            current_year - 1 if current_year is not None else None
        )

        by_period = {
            (int(e.get("year", 0)), int(e.get("month", 0))): e
            for e in entries
            if e.get("year") is not None and e.get("month") is not None
        }
        months = []
        ytd_revenue = 0
        ytd_last_profit = 0

        for month in range(1, 13) if entries else []:
            current = by_period.get((current_year, month), {}) if current_year is not None else {}
            baseline = by_period.get((baseline_year, month), {}) if baseline_year is not None else {}
            revenue = current.get("revenue")
            current_net_profit = current.get("net_profit")
            last_profit = baseline.get("net_profit")
            if last_profit is None:
                # 兼容旧结构：去年利润曾与今年营业额混存在同一条记录中。
                last_profit = current.get("last_year_profit")
            if revenue is not None:
                ytd_revenue += revenue
            if last_profit is not None:
                ytd_last_profit += last_profit

            days_in_month = _days_in_month(current_year or 2026, month)
            daily_avg = round(revenue / days_in_month, 0) if revenue else None
            last_daily_avg = round(last_profit / days_in_month, 0) if last_profit else 0
            profit_yoy_pct = None
            if current_net_profit is not None and last_profit not in (None, 0):
                profit_yoy_pct = round((current_net_profit - last_profit) / last_profit * 100, 1)

            months.append({
                "year": current_year,
                "month": month,
                "revenue": revenue,
                "net_profit": current_net_profit,
                "last_year_profit": last_profit or 0,
                "daily_avg": daily_avg,
                "last_daily_avg": last_daily_avg,
                "estimated_profit": current_net_profit,
                "yoy_pct": profit_yoy_pct,
                "profit_yoy_pct": profit_yoy_pct,
                "days_in_month": days_in_month,
                "revenue_review_status": current.get("review_status"),
                "profit_review_status": baseline.get("review_status"),
            })

        months_with_revenue = [m for m in months if m["revenue"] is not None]
        total_revenue = sum(m["revenue"] for m in months_with_revenue)
        total_last = sum(m["last_year_profit"] for m in months)
        avg_monthly_revenue = round(total_revenue / len(months_with_revenue), 0) if months_with_revenue else 0
        avg_monthly_last = round(total_last / len(months), 0) if months else 0

        return {
            "months": months,
            "entry_count": len(months),
            "months_with_revenue": len(months_with_revenue),
            "total_revenue": total_revenue,
            "total_last_year": total_last,
            "avg_monthly_revenue": avg_monthly_revenue,
            "avg_monthly_last": avg_monthly_last,
            "estimated_monthly_cost": round(estimated_monthly_cost, 0),
            "rent": rent,
            "labor": labor,
            "utility_avg": round(utility_avg, 0),
            "wage_per_person": wage_per_person,
            "current_staff_count": current_staff_count,
            "previous_staff_count": previous_staff_count,
            "ytd_revenue": ytd_revenue,
            "ytd_last_profit": ytd_last_profit,
            "current_year": current_year,
            "baseline_year": baseline_year,
            "records": entries,
        }

    def upsert_monthly_operating(
        self,
        entries: List[Dict[str, Any]],
        cost_baseline: Optional[Dict[str, Any]] = None,
    ) -> None:
        """按年月幂等写入已确认的月度经营记录，并更新成本基线。"""
        indexed = {
            (int(item.get("year", 0)), int(item.get("month", 0))): dict(item)
            for item in self.monthly_revenue
            if item.get("year") is not None and item.get("month") is not None
        }
        for item in entries:
            key = (int(item["year"]), int(item["month"]))
            previous = indexed.get(key, {})
            indexed[key] = {**previous, **item}
        self.monthly_revenue = sorted(indexed.values(), key=lambda item: (item["year"], item["month"]))

        baseline = {k: v for k, v in (cost_baseline or {}).items() if v is not None}
        self.profile.update(baseline)
        wage = self.profile.get("wage_per_person", 0)
        if "current_staff_count" in self.profile and wage:
            self.profile["monthly_labor"] = wage * self.profile["current_staff_count"]
        if "previous_staff_count" in self.profile and wage:
            self.profile["previous_monthly_labor"] = wage * self.profile["previous_staff_count"]
        self.save()

    @property
    def data_dir(self) -> Path:
        return PROJECT_DATA_DIR / self.project_id

    def save(self):
        """持久化到磁盘。"""
        self.updated_at = time.time()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / "memory.json"
        atomic_write_json(path, asdict(self))

    @classmethod
    def load(cls, project_id: str) -> Optional["ProjectMemory"]:
        """从磁盘加载，不存在返回 None。"""
        path = PROJECT_DATA_DIR / project_id / "memory.json"
        if not path.exists():
            return None
        data = load_json(path)
        return cls(**data) if data is not None else None

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
            "monthly_comparison": self._monthly_yo_y_comparison(),
            "agent_signals": self._generate_agent_signals(operations),
            "data_quality": data_quality,
            "decision": decision,
            "next_actions": _next_actions(data_quality, decision, current_stage, self.action_tasks),
            "tasks": self.action_tasks,
            "integrations": self.integration_status(),
            "evidence": _evidence(self, operations, baseline),
        }

    def _monthly_yo_y_comparison(self) -> Dict[str, Any]:
        """本月经营摘要；不同指标不计算伪同比。"""
        from datetime import datetime
        now = datetime.now()
        current_month = now.month
        rent = self.profile.get("monthly_rent", 0)
        labor = self.profile.get("monthly_labor", 0)
        utility_avg = (
            (self.profile.get("monthly_utility_min", 0) + self.profile.get("monthly_utility_max", 0)) / 2
        )
        est_cost = round(rent + labor + utility_avg, 0)

        current_entry = next(
            (e for e in self.monthly_revenue if e.get("year") == now.year and e.get("month") == current_month),
            None,
        )
        if not current_entry:
            return {
                "current_month": current_month,
                "available": False,
                "estimated_monthly_cost": est_cost,
                "comparison_metric": "net_profit",
            }

        revenue = current_entry.get("revenue")
        previous_entry = next(
            (
                e for e in self.monthly_revenue
                if e.get("year") == now.year - 1 and e.get("month") == current_month
            ),
            {},
        )
        last_profit = previous_entry.get("net_profit", current_entry.get("last_year_profit", 0))
        current_profit = current_entry.get("net_profit")
        yoy_pct = None
        if current_profit is not None and last_profit and last_profit > 0:
            yoy_pct = round((current_profit - last_profit) / last_profit * 100, 1)

        return {
            "current_month": current_month,
            "available": True,
            "revenue": revenue,
            "net_profit": current_profit,
            "last_year_profit": last_profit,
            "yoy_pct": yoy_pct,
            "estimated_profit": current_profit,
            "estimated_monthly_cost": est_cost,
            "comparison_metric": "net_profit",
        }

    def _generate_agent_signals(self, operations: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成 Agent 主动信号：从经营数据 + 月度对比中提取预警。"""
        signals: List[Dict[str, Any]] = []

        # 财务 Agent 信号
        if not operations.get("profit_ready", True):
            signals.append({
                "source": "财务 Agent",
                "title": "利润等待成本补齐",
                "body": "营业收入已确认；食材、包装、人工、房租或水电尚未完整录入。",
                "tone": "watch",
                "target": "/profit",
            })
        elif operations.get("net_profit", 0) < 0:
            signals.append({
                "source": "财务 Agent",
                "title": "近7天亏损",
                "body": f"净利 ¥{operations['net_profit']:,.0f}，先检查食材成本率和外卖佣金。",
                "tone": "risk",
                "target": "/profit",
            })
        elif operations.get("food_cost_rate", 0) > 0.38:
            signals.append({
                "source": "财务 Agent",
                "title": f"食材成本率 {operations['food_cost_rate']:.0%}",
                "body": "超过 38%，核对采购价、损耗和低毛利套餐。",
                "tone": "watch",
                "target": "/inventory",
            })

        # 月度同比信号
        monthly = self._monthly_yo_y_comparison()
        if monthly.get("available") and monthly.get("yoy_pct") is not None:
            yoy = monthly["yoy_pct"]
            if yoy < -20:
                signals.append({
                    "source": "情报 Agent",
                    "title": f"本月营收同比暴跌 {yoy}%",
                    "body": f"去年同月 ¥{monthly['last_year_profit']:,} → 今年 ¥{monthly['revenue']:,}。",
                    "tone": "risk",
                    "target": "/monthly",
                })
            elif yoy > 100:
                signals.append({
                    "source": "情报 Agent",
                    "title": f"本月营收同比增长 {yoy}%",
                    "body": "增速偏高，确认是否有特殊原因或数据录入问题。",
                    "tone": "info",
                    "target": "/monthly",
                })

        # 库存 Agent 信号
        recent_months = [e for e in self.monthly_revenue if e.get("revenue") is not None]
        if len(recent_months) >= 2 and recent_months[-1]["revenue"] > recent_months[-2]["revenue"] * 1.3:
            signals.append({
                "source": "库存 Agent",
                "title": "月营收跃升，建议检查库存",
                "body": "本月营收较上月增长超30%，食材和耗材可能吃紧。",
                "tone": "watch",
                "target": "/inventory",
            })

        # 风控信号
        if (
            operations.get("profit_ready", True)
            and operations.get("takeout_ratio", 0) > 0.45
            and operations.get("net_profit", 0) <= 0
        ):
            signals.append({
                "source": "风控 Agent",
                "title": "外卖依赖 + 亏损",
                "body": f"外卖占比{operations['takeout_ratio']:.0%}但净利润为负，平台佣金可能侵蚀所有利润。",
                "tone": "risk",
                "target": "/channels",
            })

        # SOP 差评联动
        if operations.get("bad_review_rate", 0) > 0.03:
            total_bad = operations.get("total_bad_reviews", 0)
            signals.append({
                "source": "SOP Agent",
                "title": f"差评率 {operations['bad_review_rate']:.1%}，建议复核 SOP",
                "body": f"近7天 {total_bad} 条差评，拆解出餐速度、口味、包装原因，更新相关 SOP。",
                "tone": "risk" if operations["bad_review_rate"] > 0.05 else "watch",
                "target": "/sop",
            })

        return signals

    def add_daily_operation(self, entry: Dict[str, Any], strategy: str = "overwrite"):
        """添加或覆盖单日经营数据。

        strategy:
        - overwrite: 直接替换同日期旧数据（默认）
        - merge: 保留旧数据非零字段，用新数据填充零或缺失字段，且不覆盖 source_trace
        - skip_duplicates: 同日期已有数据则跳过
        """
        date = entry.get("date")
        entry["created_at"] = entry.get("created_at", time.time())
        entry["updated_at"] = time.time()

        # 自动填充来源字段
        if "source_imported_at" not in entry or not entry.get("source_imported_at"):
            from datetime import datetime as dt
            entry["source_imported_at"] = dt.now().isoformat()
        if "source_type" not in entry or not entry.get("source_type"):
            entry["source_type"] = "manual"
        if "source_platform" not in entry or not entry.get("source_platform"):
            entry["source_platform"] = "unknown"
        if "source_quality_score" not in entry or not entry.get("source_quality_score"):
            entry["source_quality_score"] = _compute_source_quality(entry)

        if not date:
            self.daily_operations.append(entry)
            self.save()
            return

        existing = None
        for old in self.daily_operations:
            if old.get("date") == date:
                existing = old
                break

        if strategy == "skip_duplicates" and existing is not None:
            return  # 已有数据，跳过

        if strategy == "merge" and existing is not None:
            # 合并：新数据填充零/缺失字段，保留旧 source_trace
            old_source = {
                k: existing.get(k) for k in [
                    "source_type", "source_platform", "source_file_name",
                    "source_raw_text", "source_confidence", "source_imported_at",
                    "source_quality_score",
                ]
            }
            numeric_fields = [
                "revenue", "orders", "dine_in_revenue", "dine_in_orders",
                "delivery_revenue", "delivery_orders", "food_cost", "packaging_cost",
                "labor", "rent_allocated", "utility", "other_cost",
                "takeout_orders", "platform_fee", "marketing_cost", "inventory_loss",
                "bad_reviews", "repeat_orders", "new_members",
                "original_amount", "actual_revenue", "merchant_discount", "refund_amount",
                "refund_orders", "service_fee", "delivery_fee", "surcharge",
                "items_sold", "customers",
                "avg_order_value_before_discount", "avg_order_value_after_discount",
            ]
            for key in numeric_fields:
                old_val = existing.get(key, 0) or 0
                new_val = entry.get(key, 0) or 0
                # 保留非零旧值，新数据只填充零值字段
                if old_val > 0 and new_val <= 0:
                    entry[key] = old_val
                elif old_val <= 0 and new_val > 0:
                    entry[key] = new_val
                elif old_val > 0 and new_val > 0:
                    # 都有值：取新高置信度源的值
                    entry[key] = new_val if _source_priority(entry) >= _source_priority(existing) else old_val
            # 保留旧来源信息（旧数据优先级高说明旧数据更可靠）
            for k, v in old_source.items():
                if v and not entry.get(k):
                    entry[k] = v
            # 重新计算质量分
            entry["source_quality_score"] = _compute_source_quality(entry)
            # 标记合并
            entry["notes"] = (existing.get("notes", "") + " | " + entry.get("notes", "")).strip(" |")

        # 删除旧条目
        self.daily_operations = [
            old for old in self.daily_operations if old.get("date") != date
        ]
        self.daily_operations.append(entry)
        self.daily_operations.sort(key=lambda item: item.get("date", ""))
        self.save()

    def add_capture_audit_log(self, record: Dict[str, Any]) -> None:
        """记录录入操作审计日志。

        record 应包含：
        - timestamp: 操作时间
        - source_type: 来源类型（image/speech/csv/text）
        - file_name: 文件名（图片/语音/CSV）
        - capture_kind: 识别分类（operation/document/unknown）
        - recognized_fields: 识别出的字段摘要
        - human_modified_fields: 人工修改的字段（确认后回填）
        - review_status: 状态（recognized/confirmed/written/failed）
        - write_target: 写入目标（daily_operations/documents/sops）
        - error_message: 错误信息（如有）
        """
        record["id"] = f"cap-{len(self.capture_audit_log) + 1}-{int(time.time())}"
        record["timestamp"] = record.get("timestamp", time.time())
        self.capture_audit_log.append(record)
        self.capture_audit_log.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        if len(self.capture_audit_log) > 500:
            self.capture_audit_log = self.capture_audit_log[:500]
        self.save()

    def operation_summary(self, days: int = 7) -> Dict[str, Any]:
        """汇总最近 N 条经营数据。"""
        entries = self.daily_operations[-days:] if days > 0 else self.daily_operations
        prev_entries = self.daily_operations[-(days*2):-days] if len(self.daily_operations) >= days*2 else []

        required_cost_fields = [
            "food_cost",
            "packaging_cost",
            "labor",
            "rent_allocated",
            "utility",
        ]
        missing_cost_fields = [
            field
            for field in required_cost_fields
            if any(
                float(entry.get("actual_revenue", 0) or entry.get("revenue", 0) or 0) > 0
                and field not in entry
                for entry in entries
            )
        ]
        # 字段存在不代表成本已确认。估算值只能辅助观察，不能据此宣称真实净利。
        if any(entry.get("cost_status") != "confirmed" for entry in entries):
            missing_cost_fields = list(required_cost_fields)
        if self.profile.get("monthly_utility_status") == "unknown" and "utility" not in missing_cost_fields:
            missing_cost_fields.append("utility")
        profit_ready = bool(entries) and not missing_cost_fields

        def operating_cost(entry: Dict[str, Any]) -> float:
            """Return costs not already netted from the recorded income.

            客如云 actual_revenue/营业收入已经是结算后收入。服务费和商户优惠
            保留作经营漏斗分析，但不能再从实际收入中重复扣减。
            """
            base = (
                float(entry.get("food_cost", 0) or 0)
                + float(entry.get("packaging_cost", 0) or 0)
                + float(entry.get("labor", 0) or 0)
                + float(entry.get("rent_allocated", 0) or 0)
                + float(entry.get("utility", 0) or 0)
                + float(entry.get("other_cost", 0) or 0)
                + float(entry.get("inventory_loss", 0) or 0)
            )
            is_net_settlement = (
                entry.get("revenue_basis") == "net_settlement"
                or float(entry.get("actual_revenue", 0) or 0) > 0
            )
            if not is_net_settlement:
                base += float(entry.get("platform_fee", 0) or 0)
                base += float(entry.get("marketing_cost", 0) or 0)
            return base

        total_revenue = sum(float(e.get("actual_revenue", 0) or e.get("revenue", 0) or 0) for e in entries)
        total_original_amount = sum(float(e.get("original_amount", 0) or 0) for e in entries)
        total_merchant_discount = sum(float(e.get("merchant_discount", 0) or 0) for e in entries)
        total_refund_amount = sum(float(e.get("refund_amount", 0) or 0) for e in entries)
        total_service_fee = sum(float(e.get("service_fee", 0) or 0) for e in entries)
        total_delivery_fee = sum(float(e.get("delivery_fee", 0) or 0) for e in entries)
        total_surcharge = sum(float(e.get("surcharge", 0) or 0) for e in entries)
        total_items_sold = sum(int(e.get("items_sold", 0) or 0) for e in entries)
        total_customers = sum(int(e.get("customers", 0) or 0) for e in entries)
        total_visitors = sum(int(e.get("visitors", 0) or 0) for e in entries)
        total_dining_customers = sum(int(e.get("dining_customers", 0) or 0) for e in entries)
        total_sales_transactions = sum(int(e.get("sales_transactions", 0) or 0) for e in entries)
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
        # 外卖营收
        total_delivery_revenue = sum(float(e.get("delivery_revenue", 0) or 0) for e in entries)

        # 截图没有给出渠道拆分时，写入层会保留 0 作为兼容值，并在
        # unknown_fields 中标记真实状态。汇总不能把这个兼容值当成真实的零。
        unknown_fields = sorted({
            field
            for entry in entries
            for field in (entry.get("unknown_fields") or [])
        })
        unknown_field_entries = {
            field: sum(1 for entry in entries if field in (entry.get("unknown_fields") or []))
            for field in unknown_fields
        }

        settlement_totals: Dict[str, float] = {
            "current_owner": 0.0,
            "former_owner": 0.0,
            "cash_on_hand": 0.0,
        }
        settlement_status_totals: Dict[str, float] = {}
        product_sales_map: Dict[str, Dict[str, float]] = {}
        former_owner_methods = {"美团外卖", "淘宝闪购餐饮", "美团团购券", "抖音团购券"}
        for entry in entries:
            breakdown = entry.get("settlement_breakdown") or []
            if breakdown:
                for item in breakdown:
                    amount = float(item.get("amount", 0) or 0)
                    owner = item.get("owner", "")
                    status = item.get("status", "unknown")
                    if owner in settlement_totals:
                        settlement_totals[owner] += amount
                    if status == "cash_on_hand":
                        settlement_totals["cash_on_hand"] += amount
                    settlement_status_totals[status] = (
                        settlement_status_totals.get(status, 0.0) + amount
                    )
            else:
                for payment in entry.get("payment_methods", []) or []:
                    method = payment.get("method", "")
                    amount = float(payment.get("amount", 0) or 0)
                    if method in former_owner_methods:
                        settlement_totals["former_owner"] += amount
                        settlement_status_totals["pending_reconciliation"] = (
                            settlement_status_totals.get("pending_reconciliation", 0.0)
                            + amount
                        )
                    elif method == "现金":
                        settlement_totals["current_owner"] += amount
                        settlement_totals["cash_on_hand"] += amount
                        settlement_status_totals["cash_on_hand"] = (
                            settlement_status_totals.get("cash_on_hand", 0.0)
                            + amount
                        )
                    else:
                        settlement_totals["current_owner"] += amount
                        settlement_status_totals["expected_settled_unconfirmed"] = (
                            settlement_status_totals.get("expected_settled_unconfirmed", 0.0)
                            + amount
                        )

            for product in entry.get("product_sales", []) or []:
                name = str(product.get("name", "")).strip()
                if not name:
                    continue
                current = product_sales_map.setdefault(name, {"quantity": 0.0, "amount": 0.0})
                current["quantity"] += float(product.get("quantity", 0) or 0)
                current["amount"] += float(product.get("amount", 0) or 0)

        prime_cost = total_food_cost + total_labor
        total_cost = sum(operating_cost(entry) for entry in entries)
        calculated_net_profit = total_revenue - total_cost
        avg_order_value = total_revenue / total_orders if total_orders else 0
        prev_total_revenue = sum(float(e.get("actual_revenue", 0) or e.get("revenue", 0) or 0) for e in prev_entries)
        prev_total_original_amount = sum(float(e.get("original_amount", 0) or 0) for e in prev_entries)
        prev_total_orders = sum(int(e.get("orders", 0) or 0) for e in prev_entries)
        prev_total_cost = sum(operating_cost(entry) for entry in prev_entries)
        prev_profit_ready = bool(prev_entries) and all(
            entry.get("cost_status") == "confirmed" for entry in prev_entries
        )
        prev_calculated_net_profit = prev_total_revenue - prev_total_cost
        prev_avg_order_value = prev_total_revenue / prev_total_orders if prev_total_orders else 0

        food_cost_rate = total_food_cost / total_revenue if total_revenue else 0
        labor_cost_rate = total_labor / total_revenue if total_revenue else 0
        prime_cost_rate = prime_cost / total_revenue if total_revenue else 0
        platform_fee_rate = total_platform / total_revenue if total_revenue else 0
        bad_review_rate = total_bad_reviews / total_orders if total_orders else 0
        takeout_ratio = None if "takeout_orders" in unknown_fields else (total_takeout / total_orders if total_orders else 0)
        delivery_rate = None if "delivery_revenue" in unknown_fields else (total_delivery_revenue / total_revenue if total_revenue else 0)

        alerts: List[Dict[str, str]] = []
        if profit_ready and calculated_net_profit < 0:
            alerts.append({
                "level": "high",
                "message": "最近经营数据为亏损，先检查食材成本、人工和平台活动是否吃掉毛利。",
            })
        if profit_ready and food_cost_rate > 0.4:
            alerts.append({
                "level": "medium",
                "message": "食材成本率超过 40%，需要核对总部供货价、损耗和套餐毛利。",
            })
        if profit_ready and prime_cost_rate > 0.65:
            alerts.append({
                "level": "medium",
                "message": "Prime Cost 超过 65%，食材和人工合计已经压缩利润空间。",
            })
        if bad_review_rate > 0.03:
            alerts.append({
                "level": "medium",
                "message": "差评率超过 3%，需要拆解出餐、包装、口味和配送原因。",
            })
        if takeout_ratio is not None and takeout_ratio > 0.5 and total_platform + total_marketing > total_revenue * 0.12:
            alerts.append({
                "level": "medium",
                "message": "外卖占比高且平台/活动成本偏重，需要单独核算外卖单均利润。",
            })

        return {
            "days": days,
            "entry_count": len(entries),
            "total_revenue": round(total_revenue, 2),
            "total_original_amount": round(total_original_amount, 2),
            "total_merchant_discount": round(total_merchant_discount, 2),
            "total_refund_amount": round(total_refund_amount, 2),
            "total_service_fee": round(total_service_fee, 2),
            "total_delivery_fee": round(total_delivery_fee, 2),
            "total_surcharge": round(total_surcharge, 2),
            "total_items_sold": total_items_sold,
            "total_customers": total_customers,
            "total_visitors": total_visitors,
            "total_dining_customers": total_dining_customers,
            "total_sales_transactions": total_sales_transactions,
            "total_orders": total_orders,
            "avg_order_value": round(avg_order_value, 2),
            "prev_total_revenue": round(prev_total_revenue, 2),
            "prev_total_original_amount": round(prev_total_original_amount, 2),
            "prev_total_orders": prev_total_orders,
            "prev_net_profit": round(prev_calculated_net_profit, 2) if prev_profit_ready else None,
            "prev_avg_order_value": round(prev_avg_order_value, 2),
            "delivery_revenue": round(total_delivery_revenue, 2),
            "delivery_rate": round(delivery_rate, 4) if delivery_rate is not None else None,
            "unknown_fields": unknown_fields,
            "unknown_field_entries": unknown_field_entries,
            "field_coverage": {
                field: round(
                    sum(1 for entry in entries if field not in (entry.get("unknown_fields") or [])) / len(entries),
                    4,
                ) if entries else 0
                for field in ("takeout_orders", "delivery_orders", "delivery_revenue", "payment_methods", "cash_count")
            },
            "settlement_summary": {
                "current_owner": round(settlement_totals["current_owner"], 2),
                "former_owner": round(settlement_totals["former_owner"], 2),
                "cash_on_hand": round(settlement_totals["cash_on_hand"], 2),
                "by_status": {
                    key: round(value, 2)
                    for key, value in settlement_status_totals.items()
                },
                "method": "销售收入按支付方式归属；前老板代收不影响收入确认，但在转账核销前保留为应核对款。",
            },
            "product_sales": sorted(
                [
                    {
                        "name": name,
                        "quantity": round(values["quantity"], 2),
                        "amount": round(values["amount"], 2),
                    }
                    for name, values in product_sales_map.items()
                ],
                key=lambda item: item["amount"],
                reverse=True,
            ),
            "total_cost": round(total_cost, 2) if profit_ready else None,
            "net_profit": round(calculated_net_profit, 2) if profit_ready else None,
            "profit_ready": profit_ready,
            "profit_status": "confirmed" if profit_ready else "missing_costs",
            "missing_cost_fields": missing_cost_fields,
            "cost_coverage": round(
                (len(required_cost_fields) - len(missing_cost_fields)) / len(required_cost_fields),
                4,
            ),
            "food_cost_rate": round(food_cost_rate, 4) if profit_ready else None,
            "labor_cost_rate": round(labor_cost_rate, 4) if profit_ready else None,
            "prime_cost": round(prime_cost, 2) if profit_ready else None,
            "prime_cost_rate": round(prime_cost_rate, 4) if profit_ready else None,
            "platform_fee_rate": round(platform_fee_rate, 4) if "service_fee" not in unknown_fields else None,
            "total_bad_reviews": total_bad_reviews,
            "bad_review_rate": round(bad_review_rate, 4),
            "takeout_ratio": round(takeout_ratio, 4) if takeout_ratio is not None else None,
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
    elif not operations.get("profit_ready", True):
        contradiction = "收入已确认但成本未补齐，暂不能判断真实利润"
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


def _days_in_month(year: int, month: int) -> int:
    import calendar
    return calendar.monthrange(year, month)[1]


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


def _compute_source_quality(entry: Dict[str, Any]) -> str:
    """计算数据质量评分 A/B/C/D。

    A: OCR/CSV 高置信 + 核心字段完整（revenue, orders, food_cost, labor）
    B: OCR/CSV 中置信 + 至少 revenue + orders
    C: manual 或 estimated，或核心字段不全
    D: 严重缺失数据
    """
    source_type = entry.get("source_type", "manual")
    confidence = entry.get("source_confidence", "low")
    revenue = entry.get("revenue", 0) or 0
    orders = entry.get("orders", 0) or 0
    food_cost = entry.get("food_cost", 0) or 0
    labor = entry.get("labor", 0) or 0

    core_fields_count = sum(1 for v in [revenue, orders, food_cost, labor] if v > 0)

    if source_type in ("manual", "estimated"):
        return "C" if core_fields_count >= 2 else "D"

    if confidence == "high" and core_fields_count >= 4:
        return "A"
    if confidence in ("high", "medium") and core_fields_count >= 2:
        return "B"
    if core_fields_count >= 2:
        return "C"
    return "D"


def _source_priority(entry: Dict[str, Any]) -> int:
    """数据来源优先级：A > B > C > D，同级别 csv > ocr > manual > estimated。"""
    quality = entry.get("source_quality_score", "D")
    source_type = entry.get("source_type", "manual")
    base = {"A": 400, "B": 300, "C": 200, "D": 100}.get(quality, 0)
    type_bonus = {"csv": 30, "ocr": 20, "manual": 10, "estimated": 0}.get(source_type, 0)
    return base + type_bonus


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
