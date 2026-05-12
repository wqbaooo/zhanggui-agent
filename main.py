#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开店Agent - 新入口（LangGraph v3.0）。

支持三种使用方式：
1. CLI 交互式对话
2. 命令行单次查询
3. 总助理结构化调用（通过 handle_assistant_request）

架构：优先使用 LangGraph/ReAct（有 API key 时），降级到旧状态机（无 API key 时）。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import DEEPSEEK_API_KEY
from models.schemas import AssistantRequest, AssistantResponse

logger = logging.getLogger(__name__)


# ============================================================
# LangGraph 可用性检测
# ============================================================

def _langgraph_available() -> bool:
    """检测 LangGraph 是否可用（需要 LLM API key）。"""
    if DEEPSEEK_API_KEY:
        return True
    if os.environ.get("OPENAI_API_KEY", ""):
        return True
    return False


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
    agent = 开店Agent(project_id=request.project_id)

    # 构建增强消息：注入 context + task_type 引导
    enhanced_message = _build_enhanced_message(
        user_message=request.user_message,
        context=request.context,
        task_type=request.task_type,
    )

    text = agent.get_response(enhanced_message)

    # 构建结构化响应
    response = AssistantResponse(
        response_text=text,
        summary=text[:200] if text else "",
        decision=_infer_decision(text),
    )
    return response.to_dict()


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
# 统一的 开店Agent 类（LangGraph 优先 + 旧架构降级）
# ============================================================

class 开店Agent:
    """统一入口：优先使用 LangGraph/ReAct，无 API key 时降级到旧状态机。"""

    def __init__(
        self,
        knowledge_base_path: Optional[str] = None,
        video_knowledge_path: Optional[str] = None,
        document_knowledge_path: Optional[str] = None,
        deepseek_api_key: Optional[str] = None,
        project_id: Optional[str] = None,
    ):
        self._use_langgraph = _langgraph_available()
        self._project_id = project_id

        if self._use_langgraph:
            try:
                import uuid
                from graph.agent import build_agent
                from graph.state import clear_state, get_state

                self._graph = build_agent()
                prefix = f"{project_id}_" if project_id else ""
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

            self._session = Session()
            logger.info("旧状态机模式已激活")

    def get_response(self, user_input: str) -> str:
        """获取回复（纯文本）。"""
        if self._use_langgraph:
            return self._langgraph_get_response(user_input)
        return self._session.get_response(user_input)

    def _langgraph_get_response(self, user_input: str) -> str:
        """使用 LangGraph 获取回复。

        每次只传入新的 HumanMessage，让 MemorySaver 自动管理完整消息历史。
        避免手动维护 state.messages 与 checkpoint 状态冲突。
        """
        from langchain_core.messages import AIMessage, HumanMessage

        state = self._get_state(self._session_id)

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
            return {
                "response_text": text,
                "decision": "needs_more_data",
                "summary": text[:200] if text else "",
                "facts": [],
                "assumptions": [],
                "risks": [],
                "scores": {
                    "site": None,
                    "finance": None,
                    "category_fit": None,
                    "execution_difficulty": None,
                },
                "next_actions": [],
                "questions_for_user": [],
                "sources": [],
                "artifacts": [],
                "memory_updates": {},
            }
        return self._session.get_structured_response(user_input)

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
    agent = 开店Agent()

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
    print("开店做生意 Agent (v2 - 状态机架构)")
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
