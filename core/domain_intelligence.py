"""Conversation-time domain routing and evidence gathering for the operating store.

The user-facing Agent owns the conversation. Domain modules only return raw,
structured reports; they never speak to the user directly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List
import json
import re

from config import PROJECT_DATA_DIR
from models.labor import LaborTracking
from models.project import ProjectMemory
from models.sku import SkuCatalog
from models.sop import SopLibrary


DOMAIN_LABELS = {
    "procurement": "总部物料与采购",
    "inventory": "门店库存",
    "labor": "员工与工资",
    "finance": "利润与经营台账",
    "channel": "外卖渠道",
    "sop": "SOP与门店规则",
    "risk": "食品安全与经营风险",
    "general": "门店经营档案",
}

DOMAIN_KEYWORDS = {
    "procurement": ("采购", "进货", "买", "物料", "耗材", "供应商", "平替", "总部", "袋", "盒", "订书机"),
    "inventory": ("库存", "剩", "缺货", "断货", "补货", "盘点", "安全库存"),
    "labor": ("工资", "员工", "兼职", "全职", "排班", "工时", "加班", "人工", "守店"),
    "finance": ("利润", "营收", "成本", "保本", "赚钱", "亏损", "现金流", "账"),
    "channel": ("外卖", "美团", "淘宝闪购", "抖音", "平台", "佣金", "满减", "退款", "配送"),
    "sop": ("SOP", "流程", "出餐", "培训", "操作", "标准", "打烊", "开店"),
    "risk": ("食品安全", "卫生", "健康证", "效期", "过期", "商场规则", "合同", "检查"),
}

GENERIC_DELIVERY_TOOLS = ["订书机", "订书钉", "封口贴", "标签纸", "记号笔", "小票纸"]

FOLLOW_UP_MARKERS = (
    "刚才",
    "上面",
    "这些",
    "那些",
    "它们",
    "里面",
    "那还",
    "还缺",
    "还有吗",
    "然后呢",
    "接着",
    "继续",
)


@dataclass
class DomainReport:
    domain: str
    label: str
    known_facts: List[Dict[str, Any]] = field(default_factory=list)
    hard_rules: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)
    professional_guidance: List[str] = field(default_factory=list)
    proposed_actions: List[Dict[str, str]] = field(default_factory=list)
    evidence: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def route_domains(message: str, previous_domains: List[str] | None = None) -> List[str]:
    """Deterministically select all relevant verticals for a user turn."""
    text = message.strip()
    if not text:
        return ["general"]
    selected = [
        domain
        for domain, keywords in DOMAIN_KEYWORDS.items()
        if any(keyword.lower() in text.lower() for keyword in keywords)
    ]
    if "channel" in selected and any(
        domain in selected for domain in ("procurement", "inventory")
    ):
        strong_channel_terms = ("美团", "淘宝闪购", "抖音", "平台", "佣金", "满减", "退款", "配送", "渠道", "外卖利润")
        if not any(term in text for term in strong_channel_terms):
            selected.remove("channel")
    if "labor" in selected and any(domain in selected for domain in ("sop", "risk")):
        labor_specific_terms = ("工资", "兼职", "全职", "排班", "工时", "加班", "人工", "守店")
        if not any(term in text for term in labor_specific_terms):
            selected.remove("labor")
    if _is_contextual_follow_up(text) and previous_domains:
        for domain in previous_domains:
            if domain not in selected:
                selected.append(domain)
    return selected or ["general"]


def _is_contextual_follow_up(message: str) -> bool:
    """Recognize short owner follow-ups that depend on the previous domain."""
    return any(marker in message for marker in FOLLOW_UP_MARKERS)


def build_domain_context(
    project_id: str,
    message: str,
    previous_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return the raw evidence bundle used by both cloud and local models."""
    previous_domains = (
        previous_context.get("route", {}).get("domains", [])
        if previous_context
        else []
    )
    domains = route_domains(message, previous_domains)
    previous_query = str(previous_context.get("query", "")) if previous_context else ""
    is_follow_up = _is_contextual_follow_up(message)
    effective_message = f"{previous_query}；{message}" if is_follow_up and previous_query else message
    reports: List[DomainReport] = []
    for domain in domains:
        if domain in {"procurement", "inventory"}:
            if not any(report.domain == "procurement_inventory" for report in reports):
                reports.append(_procurement_inventory_report(project_id, effective_message, domains))
        elif domain == "labor":
            reports.append(_labor_report(project_id))
        elif domain in {"finance", "channel"}:
            reports.append(_operations_report(project_id, domain))
        elif domain in {"sop", "risk"}:
            reports.append(_sop_risk_report(project_id, domain, effective_message))
        else:
            reports.append(_general_report(project_id))

    gaps = _unique(item for report in reports for item in report.gaps)
    conflicts = [item for report in reports for item in report.conflicts]
    status = "conflict" if conflicts else "needs_input" if gaps else "answered"
    pending_handoffs: List[Dict[str, Any]] = []
    try:
        from models.agent_sessions import AgentSessionStore

        pending_handoffs = [
            {
                key: item.get(key)
                for key in (
                    "id", "source_agent", "target_agent", "summary", "reason", "status",
                )
            }
            for item in AgentSessionStore.for_project(project_id).list_handoffs(
                project_id,
                coordinator_agent="master",
                status="queued_for_master",
                limit=5,
            )
        ]
    except Exception:
        # A temporary coordination-store failure must not take down conversation.
        pending_handoffs = []
    return {
        "query": effective_message,
        "route": {
            "domains": domains,
            "consulted_modules": [report.label for report in reports],
        },
        "status": status,
        "reports": [report.to_dict() for report in reports],
        "agent_coordination": {
            "current_agent": "master",
            "authority": "coordinate_only",
            "queued_handoffs": pending_handoffs,
        },
        "response_contract": {
            "relationship": "用户是门店老板和经营决策者；你是与老板持续交流的经营助手，不扮演顾客、店员或门店。",
            "priority": ["硬性规则", "总部主数据", "本店已确认数据", "专业常识", "明确标注的推断"],
            "required_sections": ["直接回答", "本店已知", "规则或风险", "还需确认"],
            "rules": [
                "先回答用户真正的问题，再补充本店数据。",
                "专业模块只提供报告，由当前对话 Agent 统一回复。",
                "没有记录时明确说未录入并提出一个最小追问。",
                "不得虚构商品、库存、口味、政策或经营事实。",
                "总部管控物料不得推荐本地平替。",
                "未出现在总部目录匹配结果中，不等于允许本地采购。",
                "只有目录占位且没有采购、消耗或盘点记录时，不得表述为真实库存为零。",
            ],
        },
    }


def context_for_client(context: Dict[str, Any]) -> Dict[str, Any]:
    """Return safe, concise run metadata for the frontend."""
    return {
        "intent": context.get("intent", "business_question"),
        "allowed_tools": context.get("allowed_tools", []),
        "status": context.get("status", "answered"),
        "domains": context.get("route", {}).get("domains", []),
        "consulted_modules": context.get("route", {}).get("consulted_modules", []),
        "gaps": _unique(
            gap
            for report in context.get("reports", [])
            for gap in report.get("gaps", [])
        )[:4],
        "conflict_count": sum(
            len(report.get("conflicts", []))
            for report in context.get("reports", [])
        ),
    }


def context_for_prompt(context: Dict[str, Any]) -> Dict[str, Any]:
    """Compact the evidence bundle to fit small local-model context windows."""
    compact_reports = []
    for report in context.get("reports", [])[:2]:
        compact_facts = []
        for fact in report.get("known_facts", [])[:2]:
            compact = dict(fact)
            if isinstance(compact.get("items"), list):
                compact["items"] = compact["items"][:3]
            compact_facts.append(compact)
        compact_reports.append({
            "domain": report.get("domain"),
            "known_facts": compact_facts,
            "hard_rules": report.get("hard_rules", [])[:1],
            "conflicts": report.get("conflicts", [])[:1],
            "gaps": report.get("gaps", [])[:2],
            "professional_guidance": report.get("professional_guidance", [])[:1],
        })
    return {
        "intent": context.get("intent", "business_question"),
        "allowed_tools": context.get("allowed_tools", []),
        "route": context.get("route", {}),
        "status": context.get("status", "answered"),
        "reports": compact_reports,
        "agent_coordination": context.get("agent_coordination", {}),
        "response_contract": {
            "relationship": "用户是门店老板；你是经营助手，不扮演顾客或店员。",
            "priority": "硬规则 > 总部主数据 > 本店事实 > 专业常识 > 推断",
            "rules": "先直接回答；说明本店事实和缺口；禁止虚构；总部管控物料禁止推荐平替。",
        },
    }


def render_grounded_fallback(message: str, context: Dict[str, Any]) -> str:
    """Produce a factual answer when the configured model is unavailable or slow."""
    reports = context.get("reports", [])
    if not reports:
        return "我还没有查到足够的本店资料。你希望我先从哪一部分开始核对？"

    report = reports[0]
    parts: List[str] = []
    guidance = report.get("professional_guidance", [])
    if report.get("domain") == "procurement_inventory" and any(
        term in message for term in ("哪些必须", "总部买", "必须从总部")
    ):
        parts.append("总部目录内的食材、包装和耗材都必须从总部或总部认可供应链采购，不能自行买平替。")
    elif _has_domains(reports, "finance", "channel") and any(
        term in message for term in ("赚不赚钱", "利润", "挣钱")
    ):
        finance_values = _first_operation_values(reports)
        net_profit = finance_values.get("net_profit")
        if net_profit is not None:
            parts.append(
                f"近7日全店净利润为¥{float(net_profit):,.0f}；但现有台账不能证明外卖渠道单独赚钱。"
            )
        else:
            parts.append("全店净利润目前待核算，当前底账也不能证明外卖渠道单独赚钱，需要先补齐渠道成本。")
    elif report.get("domain") == "finance":
        parts.append("全店净利润目前待核算；我先按统一财务底账核对营收、成本、资金和应收。")
    elif guidance:
        parts.append(guidance[0])
    elif report.get("domain") == "labor":
        parts.append("可以，我先按员工工资标准、实际工时和加班记录核算。")
    elif report.get("domain") == "channel":
        parts.append("可以，我先按外卖流水、平台费、活动成本和退款情况核算真实到手利润。")
    elif report.get("domain") in {"sop", "risk"}:
        parts.append("可以，我先按本店已录入的SOP和强制规则核对。")
    else:
        parts.append("可以，我先结合本店已确认的数据回答。")

    facts = _dedupe_dicts([
        fact
        for domain_report in reports[:2]
        for fact in domain_report.get("known_facts", [])[:2]
    ])
    rendered_values = False
    for fact in facts[:3]:
        items = fact.get("items", [])
        if items:
            names = [str(item.get("name") or item.get("title") or "") for item in items]
            source = str(fact.get("source") or "本店资料")
            parts.append(f"{source}中查到：{'、'.join(name for name in names if name)}。")
        elif fact.get("values"):
            if rendered_values:
                continue
            values = fact["values"]
            readable = _format_operation_values(values)
            parts.append(f"本店已记录：{readable}。")
            rendered_values = True
        elif fact.get("count") is not None:
            parts.append(f"{fact.get('fact')}：{fact.get('count')}。")

    rules = [rule for domain_report in reports for rule in domain_report.get("hard_rules", [])]
    if rules:
        parts.append(f"必须遵守：{rules[0].get('rule', '')}")
    conflicts = [item for domain_report in reports for item in domain_report.get("conflicts", [])]
    if conflicts:
        parts.append(f"现在有一处需要先核对：{conflicts[0].get('message', '')}")
    gaps = _unique(gap for domain_report in reports for gap in domain_report.get("gaps", []))
    if gaps:
        parts.append(f"目前还缺：{gaps[0]}。你补充这一项后，我再给你最终清单。")
    else:
        parts.append("你希望我继续整理成可直接执行的清单吗？")
    return "\n\n".join(part for part in parts if part)


def validate_grounded_answer(answer: str, context: Dict[str, Any]) -> List[str]:
    """Detect high-risk claims that contradict evidence or turn unknown into allowed."""
    issues: List[str] = []
    reports = context.get("reports", [])
    has_procurement = any(
        report.get("domain") == "procurement_inventory"
        for report in reports
    )
    if has_procurement:
        unsupported_permission_phrases = (
            "可以放心买",
            "可以自行采购",
            "可以从本地",
            "可以自己从本地买",
            "如果可以本地买",
            "还是可以自己",
            "总部一般不管控",
            "总部不管控",
        )
        if any(phrase in answer for phrase in unsupported_permission_phrases):
            issues.append("把未知采购权限表述为允许")
        has_catalog_only_gap = any(
            "只有目录信息" in gap or "尚未录入相关物料库存" in gap
            for report in reports
            for gap in report.get("gaps", [])
        )
        if has_catalog_only_gap and any(
            phrase in answer
            for phrase in ("库存为0", "库存 0", "当前库存0", "当前库存为零")
        ):
            issues.append("把总部目录占位表述为真实零库存")
        has_pending_stock = any(
            item.get("quantity_status") == "unknown"
            for report in reports
            for fact in report.get("known_facts", [])
            for item in fact.get("items", [])
        )
        zero_quantity_claim = re.search(
            r"(?:库存|数量|均为|都是|为)\s*(?:0(?:\.0+)?\s*(?:kg|g|个|包|瓶|桶|支)?|零)",
            answer,
            re.IGNORECASE,
        )
        if has_pending_stock and zero_quantity_claim:
            issues.append("把待盘点库存表述为零")
    return issues


def _procurement_inventory_report(
    project_id: str,
    message: str,
    routed_domains: List[str],
) -> DomainReport:
    report = DomainReport(
        domain="procurement_inventory",
        label="总部物料、采购与门店库存",
    )
    memory = ProjectMemory.load(project_id)
    catalog = SkuCatalog.load(project_id)
    hq_items = _load_hq_catalog(project_id)
    store_skus = list(catalog.skus) if catalog else []

    delivery_question = any(word in message for word in ("外卖", "打包", "配送"))
    if delivery_question:
        relevant_hq = [
            item for item in hq_items
            if item.get("internal_category") in {"包装", "耗材"}
        ]
        relevant_store = [
            sku for sku in store_skus
            if sku.get("category") in {"包装", "耗材"}
            and not _is_catalog_placeholder(sku)
        ]
        report.professional_guidance.append(
            "外卖基础工具通常包括：" + "、".join(GENERIC_DELIVERY_TOOLS) + "；是否可自行采购仍需服从总部规则。"
        )
        relevant_hq.sort(
            key=lambda item: (
                0 if "外卖" in _item_text(item) else
                1 if "盒" in _item_text(item) else
                2
            )
        )
        relevant_store.sort(
            key=lambda item: (
                0 if any(term in _item_text(item) for term in ("外卖", "塑料袋", "打包袋")) else
                1 if "盒" in _item_text(item) else
                2
            )
        )
    else:
        query_terms = [
            term for term in ("袋", "盒", "纸", "酱", "粉", "章鱼", "手套", "清洁")
            if term in message
        ]
        relevant_hq = [
            item for item in hq_items
            if not query_terms or any(term in _item_text(item) for term in query_terms)
        ]
        relevant_store = [
            sku for sku in store_skus
            if not query_terms or any(term in _item_text(sku) for term in query_terms)
        ]

    hq_fact_items = [
            {
                "name": item.get("hq_name"),
                "category": item.get("hq_category"),
                "spec": item.get("spec"),
            }
            for item in relevant_hq[:10]
        ]
    if hq_fact_items:
        report.known_facts.append({
            "fact": "总部目录匹配物料",
            "items": hq_fact_items,
            "source": "总部订货目录",
        })
    store_fact_items = [
            {
                "name": sku.get("name"),
                "current_stock": (
                    None
                    if sku.get("status") in {"待盘点", "未盘点", "unknown"}
                    else sku.get("current_stock")
                ),
                "unit": sku.get("unit"),
                "supplier": sku.get("supplier"),
                "status": sku.get("status"),
                "quantity_status": (
                    "unknown"
                    if sku.get("status") in {"待盘点", "未盘点", "unknown"}
                    else "observed"
                ),
            }
            for sku in relevant_store[:12]
        ]
    if store_fact_items:
        report.known_facts.append({
            "fact": "本店已记录库存",
            "items": store_fact_items,
            "source": "门店SKU库存",
        })

    constraints = (memory.franchise_constraints if memory else {}) or {}
    procurement_policy = constraints.get("procurement_policy", {})
    hq_substitution_forbidden = (
        procurement_policy.get("hq_material_substitution") == "forbidden"
        or project_id == "xinyu-hengtai-dakou"
    )
    if hq_substitution_forbidden:
        report.hard_rules.append({
            "rule": "总部目录内食材、包装和耗材禁止自行采购平替。",
            "source": "门店确认的总部采购规则",
        })
    else:
        report.gaps.append("总部物料是否允许平替的规则尚未结构化确认")

    for sku in relevant_store:
        if sku.get("hq_name") and sku.get("supplier") not in {"总部", "大口餐饮供应链"}:
            report.conflicts.append({
                "type": "supplier_policy_conflict",
                "item": sku.get("name"),
                "hq_item": sku.get("hq_name"),
                "recorded_supplier": sku.get("supplier"),
                "message": "已映射总部商品，但门店库存记录的供应商不是总部，需要人工核对。",
            })

    if hq_substitution_forbidden and relevant_hq and any(term in message for term in ("平替", "本地买", "本地采购", "自己买")):
        report.conflicts.append({
            "type": "supplier_policy_conflict",
            "item": "、".join(
                str(item.get("hq_name") or item.get("name") or "总部物料")
                for item in relevant_hq[:3]
            ),
            "message": "总部目录内匹配到相关物料，不得推荐本地平替，需从总部或总部认可供应链采购。",
        })

    if not relevant_hq:
        report.gaps.append("总部目录中没有找到与本次问题匹配的物料")
    if not relevant_store:
        report.gaps.append("本店尚未录入相关物料库存")
    elif any(
        item.get("hq_name")
        not in {sku.get("hq_name") for sku in relevant_store if sku.get("hq_name")}
        for item in relevant_hq
    ):
        report.gaps.append("部分总部物料只有目录信息，尚未关联本店实际库存和消耗")

    report.proposed_actions.extend([
        {"label": "核对总部物料目录", "target": "/products"},
        {"label": "补录或盘点库存", "target": "/inventory"},
    ])
    report.evidence.extend([
        {"label": "总部订货目录", "source": f"project_data/{project_id}/hq_skus/hq_sku_catalog.json"},
        {"label": "门店库存", "source": f"project_data/{project_id}/skus.json"},
        {"label": "总部采购规则", "source": f"project_data/{project_id}/memory.json"},
    ])
    return report


def _labor_report(project_id: str) -> DomainReport:
    report = DomainReport(domain="labor", label=DOMAIN_LABELS["labor"])
    tracking = LaborTracking.load(project_id)
    if not tracking:
        report.gaps.append("尚未建立员工与工资档案")
        return report
    active = [item for item in tracking.staff if item.get("status") == "在岗"]
    report.known_facts.append({
        "fact": "在岗员工",
        "count": len(active),
        "items": [
            {
                "name": item.get("name"),
                "pay_type": item.get("pay_type"),
                "monthly_base": item.get("monthly_base"),
                "hourly_wage": item.get("hourly_wage"),
            }
            for item in active
        ],
        "source": "员工档案",
    })
    report.known_facts.append({
        "fact": "已录入考勤",
        "count": len(tracking.work_records),
        "source": "工时记录",
    })
    if not tracking.work_records:
        report.gaps.append("尚未录入可用于工资核算的考勤工时")
    for item in active:
        if (
            item.get("pay_type") in {"hourly", "auto"}
            and not item.get("hourly_wage")
            and not item.get("monthly_base")
        ):
            report.gaps.append(f"{item.get('name', '员工')}缺少工资标准")
    report.proposed_actions.append({"label": "核对员工与工时", "target": "/training"})
    report.evidence.append({"label": "员工工资档案", "source": f"project_data/{project_id}/labor.json"})
    return report


def _operations_report(project_id: str, domain: str) -> DomainReport:
    label = DOMAIN_LABELS[domain]
    report = DomainReport(domain=domain, label=label)
    memory = ProjectMemory.load(project_id)
    if not memory or not memory.daily_operations:
        report.gaps.append("尚未录入真实经营流水")
        return report
    if domain == "finance":
        from models.finance_ledger import FinanceLedger

        finance = FinanceLedger.for_project(project_id).finance_overview(project_id)
        report.known_facts.append({
            "fact": "期间经营摘要",
            "values": {
                "entry_count": finance.get("sales_days"),
                "total_revenue": (finance.get("revenue_minor") or 0) / 100,
                "total_orders": finance.get("orders"),
                "net_profit": finance.get("net_profit_minor") / 100 if finance.get("net_profit_minor") is not None else None,
            },
            "source": "SQLite 财务账本",
        })
        if finance.get("missing_inputs"):
            report.gaps.extend(str(item) for item in finance["missing_inputs"])
            report.conflicts.append({
                "type": "finance_incomplete",
                "message": "营业收入已确认，但成本和打烊数据未闭合，暂不能确认净利润和保本额。",
            })
        report.professional_guidance.append(
            "收入、到账、应收和利润分开核算；任何未知成本不能按 0 处理。"
        )
        report.proposed_actions.append({"label": "查看统一财务台", "target": "/profit"})
        report.evidence.append({"label": "SQLite 财务账本", "source": f"project_data/{project_id}/finance.db"})
        return report
    summary = memory.operation_summary(days=7)
    keys = (
        "entry_count",
        "total_revenue",
        "total_orders",
        "net_profit",
        "food_cost_rate",
        "labor_cost_rate",
        "takeout_ratio",
        "platform_fee_rate",
        "bad_review_rate",
    )
    report.known_facts.append({
        "fact": "近7日经营摘要",
        "values": {key: summary.get(key) for key in keys},
        "source": "经营台账",
    })
    if domain == "channel" and not any(
        entry.get("delivery_revenue") or entry.get("takeout_orders")
        for entry in memory.daily_operations[-7:]
    ):
        report.gaps.append("缺少外卖渠道拆分数据")
        report.gaps.append("现有台账未把食材和人工成本按渠道分摊，暂不能确认外卖渠道单独净利润")
        report.professional_guidance.append(
            "判断外卖是否赚钱，需要用外卖收入减去平台费、活动成本、包装、退款以及分摊后的食材和人工成本。"
        )
    elif domain == "channel":
        report.gaps.append("现有台账未把食材和人工成本按渠道分摊，暂不能确认外卖渠道单独净利润")
        report.professional_guidance.append(
            "判断外卖是否赚钱，需要用外卖收入减去平台费、活动成本、包装、退款以及分摊后的食材和人工成本。"
        )
    report.proposed_actions.append({
        "label": "查看渠道外卖" if domain == "channel" else "查看利润与保本",
        "target": "/channels" if domain == "channel" else "/profit",
    })
    report.evidence.append({"label": "经营台账", "source": f"project_data/{project_id}/memory.json"})
    return report


def _sop_risk_report(project_id: str, domain: str, message: str) -> DomainReport:
    report = DomainReport(domain=domain, label=DOMAIN_LABELS[domain])
    library = SopLibrary.load(project_id)
    documents = list(library.documents) if library else []
    relevant = [
        {
            "title": item.get("title"),
            "category": item.get("category"),
            "status": item.get("status"),
            "source": item.get("source"),
        }
        for item in documents[:10]
    ]
    if relevant:
        report.known_facts.append({
            "fact": "已录入SOP与规则",
            "items": relevant,
            "source": "SOP作业库",
        })
        steps = []
        for item in documents:
            for step in item.get("steps", []):
                text = f"{step.get('title', '')}{step.get('description', '')}"
                if any(term in text for term in ("卫生", "打烊", "效期", "清洁", "开封", "过期")):
                    steps.append(f"{step.get('title')}：{step.get('description')}")
        if steps:
            report.professional_guidance.append(
                "按本店已录入SOP执行：" + "；".join(
                    step.rstrip("。；") for step in steps[:5]
                ) + "。"
            )
    else:
        report.gaps.append("尚未录入可查询的SOP或门店规则")
    report.hard_rules.append({
        "rule": "食品安全、健康证、总部和商场规则优先于利润优化。",
        "source": "产品经营约束",
    })
    report.proposed_actions.append({"label": "查看SOP作业库", "target": "/sop"})
    report.evidence.append({"label": "SOP作业库", "source": f"project_data/{project_id}/sops.json"})
    return report


def _general_report(project_id: str) -> DomainReport:
    report = DomainReport(domain="general", label=DOMAIN_LABELS["general"])
    memory = ProjectMemory.load(project_id)
    if not memory:
        report.gaps.append("门店经营档案不存在")
        return report
    report.known_facts.append({
        "fact": "门店身份",
        "values": memory.profile,
        "source": "门店经营档案",
    })
    report.evidence.append({"label": "门店经营档案", "source": f"project_data/{project_id}/memory.json"})
    return report


def _load_hq_catalog(project_id: str) -> List[Dict[str, Any]]:
    path = PROJECT_DATA_DIR / project_id / "hq_skus" / "hq_sku_catalog.json"
    try:
        return list(json.loads(path.read_text(encoding="utf-8")).get("skus", []))
    except (OSError, ValueError, TypeError):
        return []


def _item_text(item: Dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key, ""))
        for key in ("name", "hq_name", "notes", "category", "hq_category")
    )


def _is_catalog_placeholder(sku: Dict[str, Any]) -> bool:
    return bool(
        sku.get("hq_name")
        and float(sku.get("current_stock", 0) or 0) == 0
        and float(sku.get("consumption_per_day", 0) or 0) == 0
        and not sku.get("last_purchase_date")
    )


def _format_operation_values(values: Dict[str, Any]) -> str:
    labels = {
        "entry_count": "记录天数",
        "total_revenue": "营收",
        "total_orders": "订单",
        "net_profit": "全店净利润",
        "food_cost_rate": "食材成本率",
        "labor_cost_rate": "人工成本率",
        "takeout_ratio": "外卖占比",
        "platform_fee_rate": "平台费率",
        "bad_review_rate": "差评率",
    }
    percent_keys = {
        "food_cost_rate",
        "labor_cost_rate",
        "takeout_ratio",
        "platform_fee_rate",
        "bad_review_rate",
    }
    currency_keys = {"total_revenue", "net_profit"}
    parts = []
    for key, value in values.items():
        if value in (None, ""):
            continue
        if key in percent_keys:
            rendered = f"{float(value) * 100:.1f}%"
        elif key in currency_keys:
            rendered = f"¥{float(value):,.0f}"
        else:
            rendered = str(value)
        parts.append(f"{labels.get(key, key)}{rendered}")
    return "，".join(parts)


def _has_domains(reports: List[Dict[str, Any]], *domains: str) -> bool:
    present = {str(report.get("domain")) for report in reports}
    return all(domain in present for domain in domains)


def _first_operation_values(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    for report in reports:
        for fact in report.get("known_facts", []):
            if isinstance(fact.get("values"), dict):
                return fact["values"]
    return {}


def _dedupe_dicts(values: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    seen = set()
    for value in values:
        marker = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


def _unique(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
