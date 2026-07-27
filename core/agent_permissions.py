"""掌柜 Agent 的角色与工具权限策略。

业务角色用于明确责任边界；真正的写入授权必须由服务端根据当前用户原话判断，
不能只依赖提示词或模型自行声称“用户已确认”。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


DEFAULT_PROJECT_ID = "xinyu-hengtai-dakou"


@dataclass(frozen=True)
class ToolPolicy:
    owner: str
    level: int
    mutates: bool = False
    external: bool = False


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    required_level: int


# L0 查询，L1 计算/诊断，L2 生成草稿，L3 内部写入，L4 外部执行。
TOOL_POLICIES: dict[str, ToolPolicy] = {
    "search_knowledge": ToolPolicy("经营参谋", 0),
    "search_web": ToolPolicy("经营参谋", 0),
    "analyze_local_trends": ToolPolicy("经营参谋", 1),
    "analyze_channel_sales_target": ToolPolicy("经营参谋", 1),
    "get_financial_context": ToolPolicy("会计", 0),
    "preview_finance_plan": ToolPolicy("会计", 2),
    "execute_finance_plan": ToolPolicy("会计", 3, mutates=True),
    "list_pending_facts": ToolPolicy("掌柜", 0),
    "get_fact_detail": ToolPolicy("掌柜", 0),
    "explain_anomaly": ToolPolicy("经营参谋", 1),
    "confirm_fact": ToolPolicy("会计", 3, mutates=True),
    "reject_fact": ToolPolicy("会计", 3, mutates=True),
    "modify_fact_amount": ToolPolicy("会计", 3, mutates=True),
    "mark_fact": ToolPolicy("会计", 3, mutates=True),
}


_MARK_CONFIRMATION_PHRASES: dict[str, tuple[str, ...]] = {
    "former_owner_collected": ("前老板代收", "标记前老板代收"),
    "former_owner_transfer": ("前老板回款", "前老板转给我", "标记前老板回款"),
    "platform_unsettled": ("平台未结算", "标记未结算"),
    "refund": ("标记退款", "这笔是退款"),
    "purchase": ("确认采购", "标记采购", "这笔是采购"),
    "stock_in": ("确认入库", "标记入库", "这笔只入库存"),
    "non_operating": ("非经营性", "非经营收支"),
    "keruyun_settlement": ("客如云结算", "归入客如云"),
    "cash": ("标记现金", "这笔是现金"),
    "group_coupon": ("团购券", "标记团购"),
    "needs_reconciliation": ("需要对账", "标记对账"),
    "defer": ("暂不处理", "先不处理", "稍后处理"),
}


def enforce_project_scope(project_id: str | None) -> str:
    """锁定唯一真实门店，禁止模型把工具调用路由到其他项目。"""
    normalized = (project_id or DEFAULT_PROJECT_ID).strip()
    if normalized != DEFAULT_PROJECT_ID:
        raise PermissionError(
            f"当前产品只允许访问门店 {DEFAULT_PROJECT_ID}，拒绝访问 {normalized}。"
        )
    return normalized


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _normalized_numbers(text: str) -> set[Decimal]:
    values: set[Decimal] = set()
    for raw in re.findall(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?", text):
        try:
            values.add(Decimal(raw.replace(",", "")).quantize(Decimal("0.01")))
        except InvalidOperation:
            continue
    return values


def _amount_is_explicit(user_text: str, args: Mapping[str, Any]) -> bool:
    try:
        requested = Decimal(str(args.get("new_amount"))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return False
    return requested in _normalized_numbers(user_text)


def authorize_tool_call(
    tool_name: str,
    args: Mapping[str, Any] | None,
    user_text: str,
    recent_context: str = "",
) -> AuthorizationDecision:
    """判断本轮模型生成的工具调用是否获得了当前用户原话授权。"""
    call_args = args or {}
    policy = TOOL_POLICIES.get(tool_name)
    if policy is None:
        return AuthorizationDecision(False, "该工具不在当前单店权限白名单中。", 4)
    if policy.external:
        return AuthorizationDecision(False, "当前版本不允许 Agent 执行外部付款、采购或改价。", 4)

    try:
        enforce_project_scope(str(call_args.get("project_id") or DEFAULT_PROJECT_ID))
    except PermissionError as exc:
        return AuthorizationDecision(False, str(exc), policy.level)

    if not policy.mutates:
        return AuthorizationDecision(True, "只读或计算操作。", policy.level)

    text = (user_text or "").strip()
    target_id = str(
        call_args.get("fact_id") or call_args.get("plan_id") or ""
    ).strip()
    target_is_visible = bool(target_id) and (
        target_id in text or target_id in (recent_context or "")
    )
    if not target_is_visible:
        return AuthorizationDecision(
            False,
            "需要先展示并明确关联这条事实，再执行写入。",
            policy.level,
        )

    if tool_name == "execute_finance_plan":
        allowed = _contains_any(
            text,
            ("确认执行", "执行该方案", "确认这个方案", "按方案入账"),
        )
        reason = "需要先展示方案编号、会计影响和核销明细，再由店主明确说“确认执行”。"
    elif tool_name == "confirm_fact":
        allowed = text == "确认" or _contains_any(
            text, ("确认入账", "确认这条", "这条没问题", "可以入账", "确认事实")
        )
        reason = "需要店主明确说“确认入账”后才能写入正式账本。"
    elif tool_name == "reject_fact":
        allowed = _contains_any(text, ("驳回", "不入账", "这条不对", "这个不算"))
        reason = "需要店主明确说“驳回”或“不入账”。"
    elif tool_name == "modify_fact_amount":
        has_edit_intent = _contains_any(
            text, ("金额改", "改成", "修改为", "实际是", "正确金额", "修正为")
        )
        allowed = has_edit_intent and _amount_is_explicit(text, call_args)
        reason = "需要店主明确说出修改动作和与 new_amount 一致的新金额。"
    elif tool_name == "mark_fact":
        action = str(call_args.get("action") or "")
        phrases = _MARK_CONFIRMATION_PHRASES.get(action, ())
        allowed = bool(phrases) and _contains_any(text, phrases)
        reason = "需要店主明确说出要标记的业务属性。"
    else:
        allowed = False
        reason = "当前写入动作没有匹配到明确授权规则。"

    return AuthorizationDecision(
        allowed,
        "已从当前用户原话获得明确授权。" if allowed else reason,
        policy.level,
    )


def permission_prompt(tool_name: str, reason: str) -> str:
    """生成简短确认提示，不暴露内部权限术语。"""
    labels = {
        "confirm_fact": "入账",
        "reject_fact": "驳回",
        "modify_fact_amount": "修改金额",
        "mark_fact": "标记业务属性",
        "execute_finance_plan": "执行财务方案",
    }
    action = labels.get(tool_name, "执行该操作")
    return f"这一步会{action}并改变门店记录。{reason}"
