#!/usr/bin/env python3
"""经营复盘：用 DuckDB 分析 + 周期对比 + 异常检测。"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import PROJECT_DATA_DIR
from models.analytics import StoreAnalytics, detect_monthly_anomalies
from models.json_store import atomic_write_json, load_json


@dataclass
class Report:
    id: str = ""
    report_type: str = "weekly"
    period_start: str = ""
    period_end: str = ""
    generated_at: str = ""
    status: str = "draft"

    total_days: int = 0
    total_revenue: float = 0.0
    avg_daily_revenue: float = 0.0
    total_orders: int = 0
    avg_order_value: float = 0.0
    net_profit: float = 0.0
    food_cost_rate: float = 0.0
    labor_cost_rate: float = 0.0
    takeout_ratio: float = 0.0
    platform_fee_total: float = 0.0

    prev_revenue: float = 0.0
    revenue_change_pct: float = 0.0
    prev_net_profit: float = 0.0
    profit_change_pct: float = 0.0

    changes: List[Dict[str, Any]] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    sections: Dict[str, Any] = field(default_factory=dict)
    actions: List[Dict[str, str]] = field(default_factory=list)
    narrative: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReportArchive:
    project_id: str
    reports: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    @property
    def data_file(self) -> Path:
        return PROJECT_DATA_DIR / self.project_id / "reports.json"

    def save(self):
        self.updated_at = time.time()
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.data_file, asdict(self))

    @classmethod
    def load(cls, pid: str) -> Optional["ReportArchive"]:
        p = PROJECT_DATA_DIR / pid / "reports.json"
        if not p.exists():
            return None
        data = load_json(p)
        return cls(**data) if data is not None else None

    @classmethod
    def create(cls, pid: str) -> "ReportArchive":
        a = cls(project_id=pid); a.save(); return a

    def _period(self, rt: str, offset: int = 1):
        today = datetime.now()
        if rt == "weekly":
            mon = today - timedelta(days=today.weekday() + 7 * offset)
            sun = mon + timedelta(days=6)
            prev_mon = mon - timedelta(days=7)
            prev_sun = mon - timedelta(days=1)
            return mon.strftime("%Y-%m-%d"), sun.strftime("%Y-%m-%d"), prev_mon.strftime("%Y-%m-%d"), prev_sun.strftime("%Y-%m-%d")
        else:
            y, m = today.year, today.month - offset
            while m <= 0: m += 12; y -= 1
            first = datetime(y, m, 1)
            last = (datetime(y, m + 1, 1) - timedelta(days=1)) if m < 12 else datetime(y + 1, 1, 1) - timedelta(days=1)
            prev_first = (first - timedelta(days=1)).replace(day=1)
            prev_last = first - timedelta(days=1)
            return first.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d"), prev_first.strftime("%Y-%m-%d"), prev_last.strftime("%Y-%m-%d")

    def generate(self, report_type: str, project_memory: Any, sku_catalog: Any = None, labor_tracking: Any = None) -> Report:
        start, end, prev_start, prev_end = self._period(report_type)

        ana = StoreAnalytics()
        if project_memory and project_memory.daily_operations:
            ana.load(project_memory.daily_operations)

        # 周期对比
        cmp = ana.compare_periods(start, end, prev_start, prev_end)
        curr = cmp["current"]
        prev = cmp["previous"]

        total_rev = curr.get("total_revenue", 0) or 0
        total_ord = curr.get("total_orders", 0) or 0
        days = curr.get("days", 0) or 0
        net = curr.get("net_profit", 0) or 0

        # 变化率
        rev_change = 0.0
        profit_change = 0.0
        prev_rev = prev.get("total_revenue", 0) or 0
        prev_net = prev.get("net_profit", 0) or 0
        if prev_rev > 0:
            rev_change = round((total_rev - prev_rev) / prev_rev * 100, 1)
        if prev_net != 0:
            profit_change = round((net - prev_net) / abs(prev_net) * 100, 1)

        # 异常检测
        findings = ana.find_anomalies(start, end)

        # 月度异常检测
        if project_memory and project_memory.monthly_revenue and report_type == "monthly":
            monthly_findings = detect_monthly_anomalies(
                project_memory.monthly_revenue, project_memory.profile
            )
            findings.extend(monthly_findings)

        # SKU 库存
        sku_alerts = []
        if sku_catalog:
            fc = sku_catalog.forecast()
            urg = [f for f in fc if f["action"] == "urgent"]
            rec = [f for f in fc if f["action"] == "recommend"]
            if urg:
                findings.append({"type": "stock_urgent", "level": "risk",
                    "title": f"{len(urg)} 项库存告急",
                    "body": "、".join(f"{f['name']}剩{f['current_stock']}{f.get('unit','')}" for f in urg[:3]),
                    "target": "/inventory"})
                for f in urg[:3]:
                    sku_alerts.append(f)
            elif rec:
                findings.append({"type": "stock_low", "level": "watch",
                    "title": f"{len(rec)} 项建议补货",
                    "body": "、".join(f["name"] for f in rec[:3]),
                    "target": "/inventory"})

        # 人工
        labor_findings = []
        if labor_tracking:
            try:
                ym = end[:7]
                wage = labor_tracking.wage_summary(ym)
                certs = labor_tracking.health_cert_alerts(days=30)
                if wage.get("total_wage", 0) > 0:
                    findings.append({"type": "labor", "level": "info",
                        "title": f"月工资 ¥{wage['total_wage']:,.0f}",
                        "body": f"{wage.get('staff_count', 0)} 人在岗",
                        "target": "/training"})
                for c in certs:
                    findings.append({"type": "health_cert", "level": "risk" if c["days_remaining"] < 15 else "watch",
                        "title": f"{c['name']} 健康证到期",
                        "body": f"{c['expiry_date']}，剩 {c['days_remaining']} 天",
                        "target": "/training"})
                    labor_findings.append(c)
            except Exception:
                pass

        # 动作
        actions = []
        for f in findings:
            target = f.get("target", "")
            lvl = f.get("level", "info")
            title = f.get("title", "")
            if target and lvl in ("risk", "watch"):
                acts = {
                    "food_cost_high": ("核对供货价", "/inventory"),
                    "prime_cost_high": ("拆解成本结构", "/profit"),
                    "loss": ("查亏损原因", "/profit"),
                    "takeout_margin": ("核算外卖利润", "/channels"),
                    "bad_reviews": ("查差评原因", "/channels"),
                    "stock_urgent": ("立即补货", "/inventory"),
                    "stock_low": ("安排补货", "/inventory"),
                    "health_cert": ("安排体检", "/training"),
                }
                if f["type"] in acts:
                    label, tgt = acts[f["type"]]
                    actions.append({"action": label, "target": tgt, "priority": "high" if lvl == "risk" else "medium"})

        # 板块
        sections = {
            "revenue": {"title": "营收概览", "metrics": {
                "total_revenue": total_rev, "total_orders": total_ord,
                "avg_daily_revenue": round(total_rev / max(days, 1), 0),
                "avg_order_value": curr.get("avg_order_value", 0),
            }},
            "cost": {"title": "成本结构", "metrics": {
                "food_cost_rate": curr.get("food_cost_rate", 0),
                "labor_cost_rate": curr.get("labor_cost_rate", 0),
                "prime_cost_rate": curr.get("prime_cost_rate", 0),
            }},
            "channel": {"title": "渠道外卖", "metrics": {
                "takeout_ratio": curr.get("takeout_ratio", 0),
                "takeout_orders": curr.get("takeout_orders", 0),
                "platform_fee": curr.get("platform_fee", 0),
                "marketing_cost": curr.get("marketing_cost", 0),
                "bad_reviews": curr.get("bad_reviews", 0),
            }},
        }
        if sku_catalog:
            sections["inventory"] = {"title": "库存", "metrics": {"total_skus": len(sku_catalog.skus), "alerts": sku_alerts[:5]}}
        if labor_tracking:
            try:
                sections["labor"] = {"title": "人工", "metrics": {"staff_count": len(labor_tracking.staff), "cert_alerts": labor_findings[:5]}}
            except Exception:
                pass

        report = Report(
            id=f"rpt-{int(time.time() * 1000)}-{len(self.reports)}",
            report_type=report_type,
            period_start=start, period_end=end,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            status="generated",
            total_days=days,
            total_revenue=round(total_rev, 2),
            avg_daily_revenue=round(total_rev / max(days, 1), 2),
            total_orders=total_ord,
            avg_order_value=round(curr.get("avg_order_value", 0), 2),
            net_profit=round(net, 2),
            food_cost_rate=round(curr.get("food_cost_rate", 0), 4),
            labor_cost_rate=round(curr.get("labor_cost_rate", 0), 4),
            takeout_ratio=round(curr.get("takeout_ratio", 0), 4),
            platform_fee_total=round(curr.get("platform_fee", 0), 2),
            prev_revenue=round(prev_rev, 2),
            revenue_change_pct=rev_change,
            prev_net_profit=round(prev_net, 2),
            profit_change_pct=profit_change,
            changes=cmp.get("changes", []),
            findings=findings,
            sections=sections,
            actions=actions,
            narrative=_build_narrative(findings, total_rev, net, rev_change, profit_change, days),
        )
        self.reports.append(report.to_dict())
        self.save()
        return report

    def latest(self, rt: Optional[str] = None) -> Optional[Dict[str, Any]]:
        r = self.reports
        if rt:
            r = [x for x in r if x.get("report_type") == rt]
        return sorted(r, key=lambda x: x.get("generated_at", ""), reverse=True)[0] if r else None

    def list_reports(self, report_type: Optional[str] = None, limit: int = 12) -> List[Dict[str, Any]]:
        r = self.reports
        if report_type:
            r = [x for x in r if x.get("report_type") == report_type]
        return sorted(r, key=lambda x: x.get("generated_at", ""), reverse=True)[:limit]

    def get(self, rid: str) -> Optional[Dict[str, Any]]:
        for r in self.reports:
            if r.get("id") == rid:
                return r
        return None


def _build_narrative(findings: List[Dict[str, Any]], total_rev: float, net: float,
                     rev_change: float, profit_change: float, days: int) -> str:
    """从 findings 生成老板可读的叙事段落。"""
    parts: List[str] = []

    # 营收概述
    direction = "增长" if rev_change > 0 else "下降"
    parts.append(
        f"本期{days}天总营收 ¥{total_rev:,.0f}，较上期{direction}{abs(rev_change):.1f}%。"
        f"净利润 ¥{net:,.0f}，{'盈利' if net >= 0 else '亏损'}{abs(profit_change):.1f}%。"
    )

    # 高优发现
    risks = [f for f in findings if f.get("level") == "risk"]
    watches = [f for f in findings if f.get("level") == "watch"]

    if risks:
        parts.append("⚠️ 需要关注：")
        for f in risks[:3]:
            parts.append(f"  • {f['title']}：{f['body']}")

    if watches:
        parts.append("📋 建议核查：")
        for f in watches[:3]:
            parts.append(f"  • {f['title']}：{f['body']}")

    if not risks and not watches:
        parts.append("本期经营正常，未发现明显异常。")

    return "\n".join(parts)
