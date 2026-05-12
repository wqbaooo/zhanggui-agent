#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开店Agent v3.0 — 真正的AI餐饮开店顾问。

架构：LangGraph + bind_tools + ReAct循环 + 苏格拉底辩证对话
- LLM自己决定调什么工具、传什么参数（不是硬编码路由）
- LLM自己决定是否追问用户、追问什么
- ReAct循环：LLM → 工具 → 观察 → 再判断（循环直到完成）

启动方式：
    python3 agent_v3.py              # 交互式对话
    python3 agent_v3.py "提问内容"    # 单次查询
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from graph.agent import build_agent
from graph.state import GraphState, get_state, clear_state


class StoreOpeningAgent:
    """餐饮开店Agent — LLM驱动的真正Agent。"""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or "default"
        self.graph = build_agent()
        self.state = get_state(self.session_id)

    def process(self, user_input: str) -> Dict[str, Any]:
        """处理用户输入。

        注意：这是一个简化的同步接口。实际使用中，
        如果LLM调用了 ask_user 工具，需要走 interrupt/resume 流程。
        """
        config = {"configurable": {"thread_id": self.session_id}}

        messages = list(self.state.messages) if hasattr(self.state, 'messages') else []
        messages.append(HumanMessage(content=user_input))

        try:
            result = self.graph.invoke(
                {
                    "messages": messages,
                    "profile": getattr(self.state, 'profile', {}),
                },
                config=config,
            )
        except Exception as exc:
            return {
                "response": f"处理异常: {exc}",
                "needs_human_input": False,
            }

        # 提取AI回复
        out_messages = result.get("messages", [])
        response_text = ""
        needs_human = False

        for msg in reversed(out_messages):
            if isinstance(msg, AIMessage) and msg.content:
                response_text = msg.content
                break

        # 更新画像
        self._update_profile_from_messages(out_messages)

        return {
            "response": response_text or "（无回复）",
            "needs_human_input": needs_human,
            "profile": self.state.profile,
        }

    def _update_profile_from_messages(self, messages: list):
        """从工具消息中提取画像更新。"""
        import re
        for msg in messages:
            if isinstance(msg, ToolMessage) and "已更新画像" in str(msg.content):
                fields = re.findall(r'(\S+):\s*([^,]+)', msg.content)
                updates = {k.strip(): v.strip() for k, v in fields if k.strip() and v.strip()}
                if updates:
                    self.state.update_profile(updates)

    def reset(self):
        clear_state(self.session_id)
        self.state = get_state(self.session_id)


def main():
    """交互式CLI。"""
    print("=" * 60)
    print("  开店Agent v3.0 — 真正的餐饮开店顾问")
    print("  LangGraph + ReAct + 苏格拉底辩证对话")
    print("=" * 60)
    print()
    print("输入您的问题开始对话。")
    print("命令: quit=退出, reset=重置, profile=查看画像")
    print("-" * 60)

    agent = StoreOpeningAgent(session_id="cli")

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        lower = user_input.lower()
        if lower in ("quit", "exit", "退出", "q"):
            print("再见！")
            break
        if lower in ("reset", "重置"):
            agent.reset()
            print("会话已重置。")
            continue
        if lower in ("profile", "画像", "p"):
            profile = agent.state.profile if hasattr(agent.state, 'profile') else {}
            if profile:
                print("\n当前画像：")
                for k, v in profile.items():
                    if k not in ("__intent__", "__intent_confidence__"):
                        print(f"  - {k}: {v}")
            else:
                print("\n暂无画像信息。")
            continue

        result = agent.process(user_input)
        print(f"\nAgent:\n{result['response']}")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    main()