"""Progressively disclosed finance skills available to the Finance Agent.

These are product-owned accounting procedures, not third-party prompts.  The
language model sees the compact catalog and selects a skill; authoritative
facts and permissions remain in the store ledger implementation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FinanceSkill:
    name: str
    tool: str
    description: str
    risk_level: str = "read_only"
    source_pattern: str = "product"


READ_ONLY_FINANCE_SKILLS: tuple[FinanceSkill, ...] = (
    FinanceSkill(
        "daily-ledger-completeness",
        "finance_date_coverage",
        "逐日检查完全空缺、缺营业收入、缺平台明细和未完成日结。",
        source_pattern="hermes-progressive-skill",
    ),
    FinanceSkill(
        "fund-location-tracing",
        "finance_funds_status",
        "区分平台结算、前老板代收、店铺可控资金和银行卡实际余额。",
        source_pattern="store-accounting",
    ),
    FinanceSkill(
        "profit-integrity-check",
        "finance_profit_readiness",
        "检查食材、包装、人工、房租、水电等成本是否足以确认真实利润。",
        source_pattern="store-accounting",
    ),
    FinanceSkill(
        "financial-performance-analysis",
        "finance_metric_summary",
        "基于台账公式分析营业收入、毛利、净利润和保本指标。",
        source_pattern="pi-tool-loop",
    ),
    FinanceSkill(
        "voucher-evidence-audit",
        "finance_evidence_audit",
        "核对原始凭证数量、状态、日期、文件与账目溯源完整性。",
        source_pattern="store-accounting",
    ),
    FinanceSkill(
        "settlement-reconciliation",
        "finance_settlement_reconciliation",
        "核对各渠道销售、平台结算和应收资金，识别未闭环金额。",
        source_pattern="store-accounting",
    ),
)

ACTION_FINANCE_SKILLS: tuple[FinanceSkill, ...] = (
    FinanceSkill(
        "transaction-draft-and-post",
        "finance_transaction_draft",
        "把自然语言或凭证整理成可核验的财务执行方案；只有老板本轮确认后才正式入账。",
        risk_level="confirmation_required",
        source_pattern="hermes-approval-gate",
    ),
)

FINANCE_SKILLS = (*READ_ONLY_FINANCE_SKILLS, *ACTION_FINANCE_SKILLS)
SKILL_BY_TOOL = {skill.tool: skill for skill in FINANCE_SKILLS}


def compact_skill_catalog() -> str:
    return "\n".join(
        f"- {skill.tool} [{skill.name}]：{skill.description}"
        for skill in READ_ONLY_FINANCE_SKILLS
    )


def public_skill_records(tools: tuple[str, ...]) -> list[dict[str, str]]:
    return [asdict(SKILL_BY_TOOL[tool]) for tool in tools if tool in SKILL_BY_TOOL]
