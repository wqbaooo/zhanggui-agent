#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""掌柜Agent - 新入口（LangGraph v3.0）。

支持三种使用方式：
1. CLI 交互式对话
2. 命令行单次查询
3. 总助理结构化调用（通过 handle_assistant_request）

架构：优先使用 LangGraph/ReAct（有 API key 时），降级到旧状态机（无 API key 时）。
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.domain_intelligence import (
    build_domain_context,
    context_for_client,
    context_for_prompt,
    render_grounded_fallback,
    validate_grounded_answer,
)
from core.conversation_policy import conversation_only_context, plan_conversation_turn
from core.readiness import build_readiness_structured, merge_readiness_overlay
from models.project import ProjectMemory
from models.schemas import AssistantRequest, AssistantResponse
from models.channel_goal import analyze_channel_goal, find_goal_amount, render_channel_goal_answer
from core.finance_answers import answer_finance_question

logger = logging.getLogger(__name__)
DEFAULT_PROJECT_ID = "xinyu-hengtai-dakou"


def build_store_context(project_id: Optional[str]) -> Dict[str, Any]:
    """Load a compact, current store snapshot for every conversation turn."""
    if not project_id:
        return {}
    memory = ProjectMemory.load(project_id)
    if memory is None:
        return {
            "project_id": project_id,
            "store_name": "新余恒太城五楼大口章鱼烧",
            "data_status": "门店档案尚未建立",
        }

    summary = memory.operation_summary(days=7)
    open_tasks = [
        task.get("title", "")
        for task in memory.action_tasks
        if task.get("status") not in {"done", "completed"}
    ][:3]
    latest_operations = [
        {
            key: entry.get(key)
            for key in (
                "date",
                "revenue",
                "orders",
                "food_cost",
                "labor",
                "platform_fee",
                "bad_reviews",
                "notes",
            )
            if entry.get(key) not in (None, "")
        }
        for entry in memory.daily_operations[-3:]
    ]
    return {
        "project_id": project_id,
        "store_name": "新余恒太城五楼大口章鱼烧",
        "store_status": memory.profile.get("stage") or memory.profile.get("店铺状态") or "operating",
        "profile": {
            key: memory.profile.get(key)
            for key in (
                "category",
                "city",
                "location",
                "monthly_rent",
                "monthly_labor",
                "current_staff_count",
            )
            if memory.profile.get(key) not in (None, "")
        },
        "last_7_days": {
            key: summary.get(key)
            for key in (
                "entry_count",
                "total_revenue",
                "total_orders",
                "net_profit",
                "food_cost_rate",
                "labor_cost_rate",
                "takeout_ratio",
                "bad_review_rate",
            )
        },
        "latest_operations": latest_operations,
        "open_tasks": open_tasks,
        "context_rule": "这是已开业且正在经营的真实门店。回答任何问题前先结合以上门店事实；没有数据时明确指出缺口，不得臆测为未开业。",
    }


# ============================================================
# LangGraph 可用性检测
# ============================================================

def _langgraph_available() -> bool:
    """检测 LangGraph 是否可用（需要 LLM API key）。"""
    from server.model_routing import chat_route, local_text_route

    return chat_route().configured or local_text_route().configured


# ============================================================
# 总助理接口
# ============================================================

def handle_assistant_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """总助理结构化调用入口。

    输入：AssistantRequest 格式的字典
    输出：AssistantResponse 格式的字典

    支持 context 注入：将总助理传递的上下文（城市/品类/预算等）注入到 Agent 对话中，
    使 Agent 无需追问已有信息即可直接进入分析。
    """
    request = AssistantRequest.from_dict(request_data)
    agent = 掌柜Agent(project_id=request.project_id)

    # 构建增强消息：注入 context + task_type 引导
    enhanced_message = _build_enhanced_message(
        user_message=request.user_message,
        context=request.context,
        task_type=request.task_type,
    )

    response = agent.get_structured_response(enhanced_message)
    response["decision"] = response.get("decision") or _infer_decision(response.get("response_text", ""))
    return response


def _build_enhanced_message(
    user_message: str,
    context: Dict[str, Any],
    task_type: str,
) -> str:
    """将总助理上下文和任务类型注入用户消息，帮助 Agent 更快定位。"""
    parts = []

    # 注入已知画像（避免 Agent 重复追问）
    profile_hints = []
    context_map = {
        "city": "城市", "category": "品类", "budget": "预算",
        "business_mode": "经营方式", "experience": "经验",
    }
    for ctx_key, label in context_map.items():
        if ctx_key in context and context[ctx_key]:
            profile_hints.append(f"{label}: {context[ctx_key]}")
    if "profile" in context and isinstance(context["profile"], dict):
        for k, v in context["profile"].items():
            if v:
                profile_hints.append(f"{k}: {v}")

    if profile_hints:
        parts.append("已知信息：" + "，".join(profile_hints) + "。")

    # 注入任务类型引导
    task_guides = {
        "profile": "请帮我补充和完善开店画像信息。",
        "site_eval": "请帮我评估选址，分析商圈和竞品。",
        "finance": "请帮我做财务测算，分析成本和回本周期。",
        "permit": "请告诉我开店需要办理哪些证照和流程。",
        "marketing": "请帮我策划开业营销方案。",
        "risk_review": "请帮我做风险评估和避坑分析。",
    }
    if task_type in task_guides:
        parts.append(task_guides[task_type])

    if user_message:
        parts.append(user_message)

    return "\n".join(parts)


def _infer_decision(text: str) -> str:
    """从回复文本推断决策类型。"""
    if not text:
        return "needs_more_data"
    high_risk_keywords = ["不建议", "风险极高", "无法回本", "亏损", "No-Go"]
    go_keywords = ["可行", "建议推进", "可以开", "条件成熟"]
    for kw in high_risk_keywords:
        if kw in text[:500]:
            return "no_go"
    for kw in go_keywords:
        if kw in text[:500]:
            return "conditional_go"
    return "needs_more_data"


# ============================================================
# 统一的 掌柜Agent 类（LangGraph 优先 + 旧架构降级）
# ============================================================

class 掌柜Agent:
    """统一入口：优先使用 LangGraph/ReAct，无 API key 时降级到旧状态机。"""

    def __init__(
        self,
        knowledge_base_path: Optional[str] = None,
        video_knowledge_path: Optional[str] = None,
        document_knowledge_path: Optional[str] = None,
        deepseek_api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        reasoning_runtime: Any = None,
    ):
        self._use_langgraph = _langgraph_available()
        self._project_id = project_id or DEFAULT_PROJECT_ID
        self._last_domain_context: Dict[str, Any] = {}
        self._last_answer_guardrail: List[str] = []
        self._last_answer_source = "not_run"
        self._reasoning_runtime = reasoning_runtime
        self._last_runtime_provider: Optional[str] = None
        self._last_runtime_model: Optional[str] = None
        self._runtime_fallback_reason: Optional[str] = None

        if self._use_langgraph:
            try:
                import uuid
                from graph.agent import build_agent
                from graph.state import clear_state, get_state

                self._graph = build_agent()
                prefix = f"{self._project_id}_"
                self._session_id = f"{prefix}session_{uuid.uuid4().hex[:8]}"
                self._config = {"configurable": {"thread_id": self._session_id}}
                self._get_state = get_state
                self._clear_state = clear_state
                logger.info("LangGraph 模式已激活 (project=%s)", project_id or "default")
            except Exception as exc:
                logger.warning("LangGraph 初始化失败，降级到旧状态机: %s", exc)
                self._use_langgraph = False

        if not self._use_langgraph:
            from core.session import Session

            self._session = Session(project_id=self._project_id)
            logger.info("旧状态机模式已激活")

    def get_response(self, user_input: str) -> str:
        """获取回复（纯文本）。"""
        turn_plan = plan_conversation_turn(user_input)
        self._runtime_fallback_reason = None
        if turn_plan.direct_reply is not None:
            self._last_domain_context = conversation_only_context(user_input, turn_plan)
            self._last_answer_guardrail = []
            self._last_answer_source = "conversation_policy"
            self._last_runtime_provider = None
            self._last_runtime_model = None
            return turn_plan.direct_reply

        previous_context = self._last_domain_context
        self._last_domain_context = build_domain_context(
            self._project_id,
            user_input,
            previous_context=previous_context,
        )
        self._last_domain_context["intent"] = turn_plan.intent
        self._last_domain_context["allowed_tools"] = list(turn_plan.allowed_tools)
        target_revenue = find_goal_amount(user_input)
        if target_revenue is not None and any(
            term in user_input for term in ("堂食", "外卖", "订单", "多少单", "客单价")
        ):
            memory = ProjectMemory.load(self._project_id)
            result = analyze_channel_goal(
                memory.daily_operations if memory else [],
                target_revenue=target_revenue,
            )
            self._last_answer_guardrail = []
            self._last_answer_source = "deterministic_channel_analysis"
            return render_channel_goal_answer(result)
        previous_query = str(previous_context.get("query", "")) if previous_context else ""
        finance_answer = answer_finance_question(user_input, self._project_id, previous_query)
        if finance_answer is not None:
            self._last_answer_guardrail = []
            self._last_answer_source = "deterministic_finance_analysis"
            return finance_answer
        if self._reasoning_runtime is not None:
            try:
                runtime_answer = self._reasoning_runtime.get_response(
                    user_input,
                    context_for_prompt(self._last_domain_context),
                )
                text = runtime_answer.text
                self._last_runtime_provider = runtime_answer.provider
                self._last_runtime_model = runtime_answer.model
                self._last_answer_source = runtime_answer.provider
            except Exception as exc:
                logger.warning("外部 Agent 运行时失败，回退可信链: %s", exc)
                self._runtime_fallback_reason = str(exc)
                text = self._trusted_runtime_response(user_input)
                self._last_answer_source = "runtime_fallback"
        else:
            text = self._trusted_runtime_response(user_input)
        self._last_answer_guardrail = validate_grounded_answer(
            text,
            self._last_domain_context,
        )
        if self._last_answer_guardrail:
            logger.warning(
                "回答触发事实守卫，改用结构化可信回复: %s",
                "；".join(self._last_answer_guardrail),
            )
            text = render_grounded_fallback(
                user_input,
                context_for_prompt(self._last_domain_context),
            )
        return merge_readiness_overlay(user_input, text)

    def _trusted_runtime_response(self, user_input: str) -> str:
        """Run the existing trusted chain when Hermes is disabled or unhealthy."""
        self._last_runtime_provider = None
        self._last_runtime_model = None
        if self._use_langgraph:
            text = self._langgraph_get_response(user_input)
            self._last_answer_source = "langgraph"
        else:
            text = self._session.get_response(user_input)
            self._last_answer_source = "legacy_session"
        return text

    def get_run_metadata(self) -> Dict[str, Any]:
        """Return the latest structured routing/evidence summary for the UI."""
        from server.model_routing import chat_route

        metadata = context_for_client(self._last_domain_context)
        route = chat_route()
        if self._last_answer_source == "conversation_policy":
            metadata["model_provider"] = "conversation_policy"
            metadata["model"] = "lightweight_social_turn"
        elif self._last_answer_source.startswith("deterministic_"):
            metadata["model_provider"] = "deterministic_store_analysis"
            metadata["model"] = self._last_answer_source
        elif self._last_answer_source in {"hermes", "pi"}:
            metadata["model_provider"] = self._last_runtime_provider or self._last_answer_source
            metadata["model"] = self._last_runtime_model or "external-agent"
        elif self._use_langgraph and route.configured:
            metadata["model_provider"] = route.provider
            metadata["model"] = route.model
        else:
            metadata["model_provider"] = "legacy_fallback"
            metadata["model"] = "core.session"
        metadata["answer_source"] = self._last_answer_source
        metadata["guardrail_applied"] = bool(self._last_answer_guardrail)
        requested_runtime = getattr(self._reasoning_runtime, "provider", None)
        metadata["requested_runtime"] = requested_runtime or "trusted"
        metadata["runtime_fallback"] = bool(self._runtime_fallback_reason)
        metadata["runtime_fallback_reason"] = self._runtime_fallback_reason
        return metadata

    def _langgraph_get_response(self, user_input: str) -> str:
        """使用 LangGraph 获取回复。

        每次只传入新的 HumanMessage，让 MemorySaver 自动管理完整消息历史。
        避免手动维护 state.messages 与 checkpoint 状态冲突。
        """
        from langchain_core.messages import AIMessage, HumanMessage

        state = self._get_state(self._session_id)
        store_context = build_store_context(self._project_id)
        if store_context and not self._last_domain_context:
            state.profile["__store_context__"] = store_context
        if self._last_domain_context:
            state.profile.pop("__store_context__", None)
            state.profile["__domain_context__"] = context_for_prompt(self._last_domain_context)

        try:
            # 只传入新消息 + 当前画像；MemorySaver 负责恢复历史
            result = self._graph.invoke(
                {"messages": [HumanMessage(content=user_input)], "profile": state.profile},
                config=self._config,
            )
        except Exception as exc:
            logger.error("LangGraph 调用失败: %s", exc)
            return f"抱歉，处理时出现问题：{exc}"

        new_messages = result.get("messages", [])

        # 提取画像更新（从 ToolMessage 中解析 update_profile 结果）
        from graph.agent import extract_profile_from_messages

        profile_updates = extract_profile_from_messages(new_messages)
        if profile_updates:
            state.update_profile(profile_updates)

        # 返回最后一条 AI 消息
        for msg in reversed(new_messages):
            if isinstance(msg, AIMessage) and msg.content:
                return msg.content
        return "抱歉，没有收到回复。"

    def get_structured_response(self, user_input: str) -> Dict[str, Any]:
        """获取结构化回复（总助理格式）。"""
        if self._use_langgraph:
            text = self.get_response(user_input)
            readiness = build_readiness_structured(user_input)
            return {
                "response_text": text,
                "decision": readiness.get("decision", "needs_more_data"),
                "summary": text[:200] if text else "",
                "facts": readiness.get("facts", []),
                "assumptions": readiness.get("assumptions", []),
                "risks": readiness.get("risks", []),
                "scores": {
                    "site": None,
                    "finance": None,
                    "category_fit": None,
                    "execution_difficulty": None,
                },
                "next_actions": readiness.get("next_actions", []),
                "questions_for_user": readiness.get("questions_for_user", []),
                "sources": [],
                "artifacts": [],
                "memory_updates": readiness.get("memory_updates", {}),
            }
        structured = self._session.get_structured_response(user_input)
        structured["response_text"] = merge_readiness_overlay(
            user_input,
            structured.get("response_text", ""),
        )
        readiness = build_readiness_structured(user_input)
        if readiness:
            for key in ("facts", "assumptions", "risks", "next_actions", "questions_for_user"):
                structured[key] = readiness.get(key, [])
            structured["decision"] = readiness["decision"]
            structured["memory_updates"] = readiness.get("memory_updates", {})
        return structured

    def reset_conversation(self):
        """重置对话（清空 MemorySaver checkpoint + 本地状态）。"""
        if self._use_langgraph:
            import uuid
            self._clear_state(self._session_id)
            # 换新 thread_id，确保 MemorySaver 不会恢复旧对话
            self._session_id = f"session_{uuid.uuid4().hex[:8]}"
            self._config = {"configurable": {"thread_id": self._session_id}}
        else:
            self._session.reset()

    def audit_sources(self) -> Dict[str, Any]:
        """审计知识库状态。"""
        if self._use_langgraph:
            # LangGraph 模式下复用旧 Session 的 audit
            from core.session import Session

            return Session().audit_sources()
        return self._session.audit_sources()


# ============================================================
# CLI 入口
# ============================================================

def main():
    agent = 掌柜Agent()

    # --audit 模式
    if "--audit" in sys.argv:
        print(json.dumps(agent.audit_sources(), ensure_ascii=False, indent=2))
        return

    # --json 模式（总助理测试）
    if "--json" in sys.argv:
        import sys as _sys
        data = json.loads(_sys.stdin.read())
        result = handle_assistant_request(data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 单次查询模式
    if len(sys.argv) > 1:
        args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
        if args:
            user_input = " ".join(args)
            print(agent.get_response(user_input))
            return

    # stdin 管道模式
    if not sys.stdin.isatty():
        for line in sys.stdin:
            user_input = line.strip()
            if user_input:
                print(agent.get_response(user_input))
                print("\n" + "-" * 50 + "\n")
        return

    # 交互式对话模式
    print("掌柜Agent (v3 - LangGraph/ReAct)")
    print("输入问题，输入 '退出' 结束，输入 '重置' 清空对话。")
    print("可先说：我想在某城市/商圈，用多少预算，做什么品类，帮我规划。")
    print("-" * 50)

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if user_input in {"退出", "quit", "exit"}:
            break
        if user_input in {"重置", "reset"}:
            agent.reset_conversation()
            print("对话已重置。")
            continue
        if not user_input:
            continue

        print("\nAgent:")
        response = agent.get_response(user_input)
        print(response)


if __name__ == "__main__":
    main()
