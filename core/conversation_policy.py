"""Turn-level conversation policy for the store Agent.

The policy runs before domain reports or tools are loaded.  Its job is not to
answer business questions; it prevents lightweight conversation from being
mistaken for a request to audit the whole store and gives the orchestrator a
small, explicit capability budget for the current turn.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ConversationTurnPlan:
    intent: str
    load_business_context: bool
    allowed_tools: tuple[str, ...]
    direct_reply: str | None = None


_GREETINGS = {
    "你好",
    "你好呀",
    "您好",
    "嗨",
    "哈喽",
    "hello",
    "hi",
    "早",
    "早上好",
    "下午好",
    "晚上好",
}
_THANKS = {"谢谢", "谢谢你", "感谢", "好的谢谢", "好谢谢", "明白了谢谢"}
_ACKNOWLEDGEMENTS = {"好", "好的", "行", "可以", "知道了", "明白了", "收到", "嗯", "哦"}

_CAPABILITY_KEYWORDS = {
    "finance": (
        "钱", "账", "收入", "营收", "支出", "成本", "利润", "到账", "结算",
        "银行卡", "现金", "借款", "工资", "房租", "水电", "还款", "消费",
    ),
    "inventory": (
        "库存", "盘点", "进货", "采购", "补货", "缺货", "原料", "物料",
        "耗材", "章鱼粉", "包装", "报损", "临期",
    ),
    "channel": ("美团", "淘宝闪购", "抖音", "京东", "外卖", "团购", "平台", "客如云"),
    "labor": ("员工", "排班", "工时", "加班", "全职", "兼职", "人工"),
    "sop": ("SOP", "流程", "开店", "打烊", "卫生", "培训", "食品安全"),
}
_ACTION_KEYWORDS = (
    "记一笔", "记账", "录入", "登记", "上传", "导入", "确认写入", "确认记入",
    "修改这笔", "删除这笔", "帮我记", "新增一笔", "补录",
)


def _normalize_short_text(message: str) -> str:
    return re.sub(r"[\s，。！？、,.!?~～]+", "", message.strip()).lower()


def _selected_capabilities(message: str) -> tuple[str, ...]:
    lowered = message.lower()
    return tuple(
        capability
        for capability, keywords in _CAPABILITY_KEYWORDS.items()
        if any(keyword.lower() in lowered for keyword in keywords)
    )


def plan_conversation_turn(message: str) -> ConversationTurnPlan:
    """Classify a turn before loading store evidence or enabling tools."""
    normalized = _normalize_short_text(message)
    if not normalized:
        return ConversationTurnPlan(
            intent="social",
            load_business_context=False,
            allowed_tools=(),
            direct_reply="我在。你可以直接告诉我想看哪件店里的事。",
        )
    if normalized in _GREETINGS:
        return ConversationTurnPlan(
            intent="social",
            load_business_context=False,
            allowed_tools=(),
            direct_reply="你好，老板。今天想先看店里的哪件事？",
        )
    if normalized in _THANKS:
        return ConversationTurnPlan(
            intent="social",
            load_business_context=False,
            allowed_tools=(),
            direct_reply="不客气。还有哪件店里的事需要我一起看？",
        )
    if normalized in _ACKNOWLEDGEMENTS:
        return ConversationTurnPlan(
            intent="social",
            load_business_context=False,
            allowed_tools=(),
            direct_reply="好，我们接着来。",
        )

    capabilities = _selected_capabilities(message)
    is_action = any(keyword in message for keyword in _ACTION_KEYWORDS)
    return ConversationTurnPlan(
        intent="business_action" if is_action else "business_question",
        load_business_context=True,
        allowed_tools=capabilities or ("store",),
    )


def conversation_only_context(message: str, plan: ConversationTurnPlan) -> dict:
    """Return metadata for a turn that intentionally queried no business data."""
    return {
        "query": message,
        "intent": plan.intent,
        "allowed_tools": list(plan.allowed_tools),
        "route": {"domains": [], "consulted_modules": []},
        "status": "conversation",
        "reports": [],
        "response_contract": {
            "relationship": "用户是门店老板；你是与老板持续交流的掌柜助手。",
            "required_sections": [],
            "rules": ["自然简短回应当前话语，不主动生成经营报告，不调用业务工具。"],
        },
    }
