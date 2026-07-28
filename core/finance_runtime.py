"""Independent, durable runtime boundary for the store Finance Agent."""

from __future__ import annotations

import json
import logging
import hashlib
from dataclasses import dataclass
from typing import Any, Callable

from core.conversation_policy import plan_conversation_turn
from core.finance_agent import FinanceModelGateway, answer_finance_question
from core.finance_execution import FinanceExecutionService
from core.finance_intelligence import classify_finance_topic
from core.finance_skills import public_skill_records
from core.finance_text_intake import parse_finance_text
from models.agent_sessions import AgentSessionStore
from models.finance_ledger import FinanceLedger


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FinanceTurnRoute:
    mode: str
    reply: str = ""
    source: str = "fallback"
    error: str | None = None
    goal: str = ""
    target_agent: str | None = None


_FINANCE_AGENT_IDENTITY = (
    "我是这家店的财务 Agent，负责收入、到账、支出、成本、利润和凭证核对。"
    "需要数字时我会查店铺台账；普通交流不会强行查账；涉及库存、排班或 SOP 时会明确交给对应 Agent。"
)


def _fallback_route(query: str, turn: Any, history: list[dict[str, str]] | None = None) -> FinanceTurnRoute:
    """Safe routing when the reasoning model is unavailable.

    Unknown language is conversation, never a default metric query.
    """
    normalized = "".join(query.lower().split()).strip("，。！？,.!?")
    identity_markers = ("你是谁", "你叫什么", "介绍一下你自己", "你负责什么", "你能做什么", "你有什么用")
    if any(marker in normalized for marker in identity_markers):
        return FinanceTurnRoute("conversation", _FINANCE_AGENT_IDENTITY, "safe_fallback")
    if not turn.load_business_context:
        return FinanceTurnRoute(
            "conversation",
            turn.direct_reply or "我在。你可以直接跟我说财务上想查或想做的事。",
            "safe_fallback",
        )
    capabilities = set(turn.allowed_tools)
    looks_like_question = any(marker in query for marker in ("？", "?", "哪些", "哪几", "有没有", "是否", "多少", "为什么", "怎么", "如何"))
    if turn.intent == "business_action" and "finance" in capabilities and not looks_like_question:
        return FinanceTurnRoute(
            "finance_action",
            "这是一个财务录入或修改操作。我会先整理成待确认内容，你确认后才能写入正式台账。",
            "safe_fallback",
            goal="整理财务动作并等待确认",
        )
    other_domains = capabilities - {"finance", "store"}
    if other_domains and "finance" not in capabilities:
        return FinanceTurnRoute(
            "cross_module",
            "这个问题的主要事实不归财务模块。我可以保留财务影响，并交给对应的专业 Agent 核对。",
            "safe_fallback",
            target_agent=next(iter(other_domains)),
        )
    recent_user_context = " ".join(
        item.get("content", "") for item in (history or [])[-4:] if item.get("role") == "user"
    )
    finance_context = any(
        token in f"{recent_user_context} {query}"
        for token in ("财务", "收入", "到账", "支出", "成本", "利润", "资金", "账", "凭证", "分析")
    )
    continuation = any(token in normalized for token in ("那你帮我", "你帮我分析", "继续", "就这个", "然后呢"))
    if "finance" in capabilities or finance_context or (continuation and recent_user_context):
        return FinanceTurnRoute("finance_question", source="safe_fallback", goal="核对并回答财务问题")
    return FinanceTurnRoute(
        "conversation",
        "我是财务 Agent。这句话我还不确定你是想闲聊，还是要查某笔账；你可以继续直接说。",
        "safe_fallback",
    )


def _model_route(
    query: str,
    history: list[dict[str, str]],
    turn: Any,
    gateway: FinanceModelGateway,
) -> FinanceTurnRoute:
    payload = gateway.json_completion(
        """你是新余恒太城五楼大口章鱼烧的财务 Agent，不是报表按钮。
结合最近对话理解省略、代词和追问，再判断当前话语应该怎样处理：
- conversation：问候、身份、能力、边界、普通交流或需要澄清的模糊表达。直接自然回答，不查账。
- finance_question：需要读取这家店台账才能回答，或老板要求分析财务状况。reply留空，交给财务工具；不能因为当前一句省略了“财务/账”等词就否决上一轮明确目标。
- finance_action：要录入、修改、删除或确认财务记录。说明可以生成待确认内容，不宣称已经写入。
- cross_module：主要需要库存、排班、SOP、渠道运营等其他模块事实。可以说明需要哪个专业 Agent 的已确认事实，但不要声称已经联系成功。
你知道自己是独立财务 Agent，掌柜 Agent 是全店总协调者。
读取和分析已确认事实可以自动进行；录入、修改、删除、付款等正式动作必须等待用户确认。
conversation/finance_action/cross_module 的 reply 要像真实助手，简短自然；不得伪造店铺数字，不输出思维过程。
只返回 JSON：{"mode":"conversation|finance_question|finance_action|cross_module","goal":"本轮真实目标","target_agent":"inventory|store-operations|operations|null","reply":"..."}。""",
        json.dumps({"recent_finance_conversation": history[-8:], "message": query}, ensure_ascii=False),
        max_tokens=900,
    )
    mode = str(payload.get("mode") or "")
    if mode not in {"conversation", "finance_question", "finance_action", "cross_module"}:
        raise ValueError("模型返回了未授权的对话路由")
    reply = str(payload.get("reply") or "").strip()
    goal = str(payload.get("goal") or "").strip()[:240]
    target_agent = str(payload.get("target_agent") or "").strip() or None
    if target_agent not in {None, "inventory", "store-operations", "operations"}:
        target_agent = None
    if mode in {"conversation", "cross_module"} and not reply:
        raise ValueError("非查账路由没有返回可见回答")
    return FinanceTurnRoute(mode, reply, "model", goal=goal, target_agent=target_agent)


class FinanceAgentRuntime:
    scope = "finance"

    def __init__(
        self,
        ledger: FinanceLedger,
        store: AgentSessionStore,
        gateway_factory: Callable[[], FinanceModelGateway] = FinanceModelGateway,
    ):
        self.ledger = ledger
        self.store = store
        self.gateway_factory = gateway_factory

    def run(
        self,
        project_id: str,
        query: str,
        start: str,
        end: str,
        *,
        session_id: str | None = None,
        use_model: bool = True,
    ) -> dict[str, Any]:
        session_id = self.store.ensure_session(
            project_id, session_id, scope=self.scope, title="新对话", runtime="finance-agent-v2-skill-loop",
        )
        existing = self.store.get_session(project_id, session_id) or {"messages": []}
        history = [
            {"role": str(item["role"]), "content": str(item["content"])}
            for item in existing.get("messages", [])[-8:]
            if item.get("role") in {"user", "assistant"}
        ]
        self.store.append_message(session_id, "user", query, metadata={"scope": self.scope})
        pending_plan_id = self._pending_plan_id(existing)
        if pending_plan_id and self._is_explicit_confirmation(query):
            return self._confirm_pending_plan(
                project_id, session_id, pending_plan_id, start, end,
            )
        turn = plan_conversation_turn(query)
        route: FinanceTurnRoute
        gateway: FinanceModelGateway | None = None
        if use_model:
            try:
                gateway = self.gateway_factory()
                route = _model_route(query, history, turn, gateway)
            except Exception as exc:
                logger.warning("财务 Agent 对话路由降级: %s", exc)
                fallback = _fallback_route(query, turn, history)
                route = FinanceTurnRoute(
                    fallback.mode, fallback.reply, fallback.source, str(exc),
                    fallback.goal, fallback.target_agent,
                )
        else:
            route = _fallback_route(query, turn, history)

        if route.mode == "finance_question":
            result = answer_finance_question(
                self.ledger, project_id, query, start, end,
                use_model=use_model, conversation_history=history,
                gateway_factory=(lambda: gateway) if gateway is not None else self.gateway_factory,
            )
            result["conversation_mode"] = "finance"
            topic = classify_finance_topic(query, str(result.get("intent") or ""))
            self.store.record_preference_signal(project_id, self.scope, topic)
            result["learned_topic"] = topic
            result["turn_route"] = route.source
        elif route.mode == "finance_action":
            result = self._draft_finance_action(
                project_id, session_id, query, start, end, gateway, route,
            )
        else:
            provider = getattr(getattr(gateway, "route", None), "provider", "product-policy")
            model = getattr(getattr(gateway, "route", None), "model", "safe-conversation-fallback")
            result = {
                "answer": route.reply,
                "period": {"start": start, "end": end},
                "intent": "social" if turn.intent == "social" else route.mode,
                "conversation_mode": "social" if route.mode == "conversation" else route.mode,
                "metrics": [], "formula_trace": [], "evidence_ids": [],
                "completeness": "confirmed", "warnings": [], "follow_up_inputs": [],
                "execution_trace": [], "sources": [],
                "turn_route": route.source,
                "agent": {
                    "id": "finance", "scope": self.scope, "label": "财务 Agent",
                    "role": "店铺会计与资金守门人",
                    "provider": provider, "model": model,
                    "mode": "DeepSeek 对话" if route.source.startswith("model") else "安全对话兜底",
                    "model_used": route.source.startswith("model"),
                    "fallback_reason": route.error,
                },
            }

        result["session_id"] = session_id
        result["agent_decision"] = {
            "mode": route.mode,
            "goal": route.goal,
            "source": route.source,
        }
        handoff = self._handoff(query, turn.allowed_tools, route.target_agent)
        if route.mode == "cross_module" and handoff:
            queued = self.store.create_handoff(
                project_id,
                session_id=session_id,
                source_agent=self.scope,
                target_agent=str(handoff["target_agent"]),
                summary=str(handoff["summary"]),
                reason=str(handoff["reason"]),
                coordinator_agent="master",
            )
            handoff = {
                **handoff,
                "id": queued["id"],
                "status": queued["status"],
                "coordinator_agent": queued["coordinator_agent"],
            }
        result["handoff"] = handoff
        self.store.append_message(
            session_id, "assistant", str(result["answer"]),
            metadata={
                "scope": self.scope, "intent": result.get("intent"),
                "conversation_mode": result.get("conversation_mode"),
                "learned_topic": result.get("learned_topic"),
                "execution_plan_id": (result.get("execution_plan") or {}).get("plan_id"),
                "execution_plan_status": (result.get("execution_plan") or {}).get("status"),
            },
        )
        return result

    @staticmethod
    def _is_explicit_confirmation(query: str) -> bool:
        normalized = "".join(query.split()).strip("，。！？,.!?")
        return normalized in {"确认", "确认执行", "确认记账", "确认入账", "确认提交"}

    @staticmethod
    def _pending_plan_id(session: dict[str, Any]) -> str | None:
        for message in reversed(session.get("messages", [])):
            if message.get("role") != "assistant":
                continue
            metadata = message.get("run") or {}
            if metadata.get("execution_plan_status") == "awaiting_confirmation":
                return str(metadata.get("execution_plan_id") or "") or None
        return None

    def _draft_finance_action(
        self,
        project_id: str,
        session_id: str,
        query: str,
        start: str,
        end: str,
        gateway: FinanceModelGateway | None,
        route: FinanceTurnRoute,
    ) -> dict[str, Any]:
        parsed = parse_finance_text(
            query, today=end, accounts=self.ledger.list_fund_accounts(project_id),
        )
        fields = parsed["fields"]
        source_hash = hashlib.sha256(f"{session_id}|{query}".encode("utf-8")).hexdigest()[:20]
        payload = {
            "event_type": fields.get("fact_type"),
            "transaction_date": fields.get("business_date"),
            "amount_minor": round(float(fields.get("amount") or 0) * 100),
            "account_key": fields.get("account_key"),
            "channel": fields.get("counterparty") if fields.get("fact_type") == "merchant_net_sale" else None,
            "settlement_state": None,
            "category_code": fields.get("category_code"),
            "category_name": fields.get("category_name"),
            "business_category_key": fields.get("business_category_key"),
            "counterparty": fields.get("counterparty"),
            "source_basis": fields.get("source_basis"),
            "source_reference": f"finance-agent:{source_hash}",
            "notes": fields.get("notes"),
        }
        plan = FinanceExecutionService(self.ledger).preview(project_id, payload)
        field_labels = {
            "event_type": "账目类型", "transaction_date": "日期", "amount_minor": "金额",
            "account_key": "收付款账户", "channel": "营业渠道", "settlement_state": "资金状态",
        }
        if plan["status"] == "awaiting_confirmation":
            amount = int(plan["normalized_fact"]["amount_minor"]) / 100
            answer = (
                f"**已整理为待确认账目**\n\n"
                f"- 类型：{plan['title']}\n"
                f"- 日期：{plan['normalized_fact']['transaction_date']}\n"
                f"- 金额：¥{amount:,.2f}\n"
                f"- 处理：{plan['accounting_effect'].get('explanation', '')}\n\n"
                "回复“确认执行”即可正式入账；需要修改时直接说要改哪一项。"
            )
        elif plan["status"] == "needs_input":
            missing = "、".join(field_labels.get(item, item) for item in plan.get("missing_fields", []))
            answer = f"**还不能生成可执行账目**\n\n还缺：{missing}。你直接补充这些信息，我会继续整理，不需要重新描述整笔账。"
        else:
            failed = [item["message"] for item in plan.get("checks", []) if item.get("status") == "failed"]
            answer = "**这笔账暂时不能执行**\n\n" + "\n".join(f"- {item}" for item in failed)
        provider = getattr(getattr(gateway, "route", None), "provider", "product-policy")
        model = getattr(getattr(gateway, "route", None), "model", "safe-action-fallback")
        return {
            "answer": answer,
            "period": {"start": start, "end": end},
            "intent": "finance_action",
            "conversation_mode": "finance_action",
            "metrics": [], "formula_trace": [], "evidence_ids": [],
            "completeness": "partial" if plan["status"] != "awaiting_confirmation" else "confirmed",
            "warnings": [], "follow_up_inputs": plan.get("missing_fields", []),
            "execution_trace": [
                {"step": "理解任务", "status": "completed", "detail": route.goal or "识别财务动作"},
                {"step": "生成执行方案", "status": "completed", "detail": "校验分类、日期、金额、账户和重复来源"},
                {"step": "等待确认", "status": plan["status"], "detail": "正式台账尚未写入"},
            ],
            "sources": [],
            "skills_used": public_skill_records(("finance_transaction_draft",)),
            "execution_plan": plan,
            "turn_route": route.source,
            "agent": {
                "id": "finance", "scope": self.scope, "label": "财务 Agent",
                "role": "店铺会计与资金守门人", "provider": provider, "model": model,
                "mode": "财务执行草稿", "model_used": route.source.startswith("model"),
                "fallback_reason": route.error,
            },
        }

    def _confirm_pending_plan(
        self, project_id: str, session_id: str, plan_id: str, start: str, end: str,
    ) -> dict[str, Any]:
        plan = FinanceExecutionService(self.ledger).execute(
            project_id, plan_id, confirmed_by="owner",
        )
        answer = (
            f"**已完成：{plan['title']}**\n\n"
            f"方案已正式执行并回读，状态为“已完成”。"
            + (f"\n记录号：{plan['record_id']}" if plan.get("record_id") else "")
        )
        result = {
            "answer": answer,
            "period": {"start": start, "end": end},
            "intent": "finance_action_completed",
            "conversation_mode": "finance_action_completed",
            "metrics": [], "formula_trace": [], "evidence_ids": [],
            "completeness": "confirmed", "warnings": [], "follow_up_inputs": [],
            "execution_trace": [
                {"step": "确认权限", "status": "completed", "detail": "老板在当前会话明确确认"},
                {"step": "执行财务任务", "status": "completed", "detail": "已写入正式记录"},
                {"step": "回读结果", "status": "completed", "detail": "执行方案状态已核对为完成"},
            ],
            "sources": [], "skills_used": public_skill_records(("finance_transaction_draft",)),
            "execution_plan": plan, "turn_route": "confirmed_action",
            "agent_decision": {"mode": "finance_action", "goal": "确认并执行上一笔财务方案", "source": "session_confirmation"},
            "handoff": None, "session_id": session_id,
            "agent": {
                "id": "finance", "scope": self.scope, "label": "财务 Agent",
                "role": "店铺会计与资金守门人", "provider": "product-policy",
                "model": "confirmed-execution", "mode": "已确认执行", "model_used": False,
                "fallback_reason": None,
            },
        }
        self.store.append_message(
            session_id, "assistant", answer,
            metadata={
                "scope": self.scope, "intent": result["intent"],
                "conversation_mode": result["conversation_mode"],
                "execution_plan_id": plan_id, "execution_plan_status": plan["status"],
            },
        )
        return result

    @staticmethod
    def _handoff(
        query: str, allowed_tools: tuple[str, ...], model_target: str | None = None,
    ) -> dict[str, Any] | None:
        targets = set(allowed_tools)
        if model_target:
            targets.add(model_target)
        if "inventory" in targets:
            return {
                "target_agent": "inventory", "status": "suggested",
                "reason": "该问题需要库存或采购的正式事实；财务 Agent 不会越权推定。",
                "summary": query[:160],
            }
        if "labor" in targets or "store-operations" in targets:
            return {
                "target_agent": "store-operations", "status": "suggested",
                "reason": "该问题需要排班、考勤或加班事实，再由财务 Agent 核算人工成本。",
                "summary": query[:160],
            }
        if "channel" in targets or "operations" in targets:
            return {
                "target_agent": "operations", "status": "suggested",
                "reason": "该问题需要渠道运营明细；财务 Agent 只接收其中已确认的收入、佣金、退款和结算事实。",
                "summary": query[:160],
            }
        if "sop" in targets:
            return {
                "target_agent": "store-operations", "status": "suggested",
                "reason": "该问题属于店务 SOP；财务 Agent 只负责核对其中产生的成本或资金影响。",
                "summary": query[:160],
            }
        return None
