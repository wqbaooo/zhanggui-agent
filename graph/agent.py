#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真正的Agent核心：LLM驱动的ReAct循环 + 苏格拉底追问。

架构：bind_tools + ToolNode + interrupt()
- LLM自己决定调什么工具、传什么参数
- LLM自己决定是否追问用户、追问什么
- ReAct循环：LLM → 工具 → 观察 → 再判断（循环直到完成）
-_human-in-the-loop：ask_user工具使用interrupt()暂停执行

不再是"关键词路由伪装的Agent"，而是LLM真正推理驱动的Agent。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from graph.prompts import SYSTEM_PROMPT
from graph.tools import get_all_tools

logger = logging.getLogger(__name__)


# ============ LLM初始化 ============

_llm_instance = None
_llm_with_tools = None


def _create_llm():
    """创建绑定工具的LLM实例。懒加载，单例模式。"""
    global _llm_instance, _llm_with_tools

    if _llm_with_tools is not None:
        return _llm_with_tools

    tools = get_all_tools()

    try:
        if DEEPSEEK_API_KEY:
            _llm_instance = ChatOpenAI(
                model=DEEPSEEK_MODEL,
                base_url=DEEPSEEK_BASE_URL,
                api_key=DEEPSEEK_API_KEY,
                temperature=0.3,
                max_tokens=2000,
            )
        else:
            import os
            openai_key = os.environ.get("OPENAI_API_KEY", "")
            if openai_key:
                _llm_instance = ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0.3,
                    max_tokens=2000,
                )
            else:
                logger.error("无LLM API key配置（DeepSeek或OpenAI），Agent将无法工作")
                return None

        _llm_with_tools = _llm_instance.bind_tools(tools)
        return _llm_with_tools

    except Exception as exc:
        logger.error("LLM初始化失败: %s", exc)
        return None


# ============ Agent节点 ============

def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LLM决策节点：决定下一步是调用工具、追问用户、还是回复。

    这是Agent的核心——LLM看到对话历史和工具描述，
    自己决定要做什么。不是硬编码路由，是真正的推理。
    """
    # 兼容dict和GraphState dataclass
    messages = state.get("messages", []) if isinstance(state, dict) else getattr(state, 'messages', [])
    profile = state.get("profile", {}) if isinstance(state, dict) else getattr(state, 'profile', {})

    # 构建系统提示（包含画像上下文）
    system_content = SYSTEM_PROMPT
    if profile:
        profile_lines = [f"- {k}: {v}" for k, v in profile.items()
                         if k not in ("__intent__", "__intent_confidence__")]
        if profile_lines:
            system_content += f"\n\n## 当前用户画像\n" + "\n".join(profile_lines)

    # 确保系统提示在最前面
    conv_messages = []
    has_system = False
    for msg in messages:
        if isinstance(msg, SystemMessage):
            has_system = True
            conv_messages.append(SystemMessage(content=system_content))
        else:
            conv_messages.append(msg)

    if not has_system:
        conv_messages = [SystemMessage(content=system_content)] + conv_messages

    # 调用LLM
    llm = _create_llm()
    if llm is None:
        return {
            "messages": [AIMessage(
                content=f"⚠️ LLM服务未配置。请在 `.env` 文件中设置 `DEEPSEEK_API_KEY`。\n\n"
                        f"当前接收到您的问题，但无法进行推理。请检查API key配置后重试。"
            )],
        }

    try:
        response = llm.invoke(conv_messages)
    except Exception as exc:
        logger.error("LLM调用失败: %s", exc)
        return {
            "messages": [AIMessage(content=f"抱歉，LLM服务暂时不可用：{exc}")],
        }

    return {"messages": [response]}


# ============ 宪法审查 ============

# 违宪模式定义：(违规类型, 正则/关键词列表, 修正提示)
_CONSTITUTION_VIOLATIONS = [
    (
        "利润承诺",
        ["肯定能赚钱", "放心做", "包赚", "稳赚", "一定能盈利", "保证回本", "躺着赚", "闭眼入"],
        "【宪法修正】已删除盈利承诺。根据利润中性原则，Agent不得承诺盈利。修正为保守情景假设。",
    ),
    (
        "品牌推荐",
        ["推荐加盟", "强烈推荐", "选这个品牌", "选XX", "就选", "建议你做", "我建议你加盟"],
        "【宪法修正】已删除品牌推荐。根据专业边界原则，Agent不做具体品牌推荐，只提供分析框架。",
    ),
    (
        "风险弱化",
        ["不过只要", "当然如果", "但只要", "其实不用太担心", "问题不大", "基本没风险", "风险很小"],
        "【宪法修正】已删除风险弱化表述。根据风险前置原则，Critical风险不可被转折词弱化。",
    ),
    (
        "数据造假",
        ["数据显示", "据统计", "行业平均", "一般来说"],
        "【宪法修正】已标注推断性质。根据事实-建议分离原则，无数据来源的统计推断必须标注为假设。",
    ),
]


def _check_constitution(text: str) -> tuple:
    """扫描文本是否违反宪法。返回 (是否违规, 违规类型, 修正提示)。"""
    if not text:
        return False, "", ""

    for vtype, keywords, fix_hint in _CONSTITUTION_VIOLATIONS:
        for kw in keywords:
            if kw in text:
                return True, vtype, fix_hint

    return False, "", ""


def constitution_check_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """宪法审查节点：检查LLM输出是否违反宪法约束。

    如果发现违规，在消息前添加宪法警告，提醒LLM（和用户）注意。
    不直接修改原始内容（保留审计痕迹），但附加修正提示。
    """
    messages = state.get("messages", []) if isinstance(state, dict) else getattr(state, 'messages', [])
    if not messages:
        return {}

    last_message = messages[-1]

    # 只审查纯文本回复（不审查工具调用）
    if not isinstance(last_message, AIMessage):
        return {}
    if last_message.tool_calls:
        return {}  # 工具调用交给 ToolNode，不审查

    content = last_message.content or ""
    is_violation, vtype, fix_hint = _check_constitution(content)

    if is_violation:
        logger.warning("[宪法审查] 检测到违规: 类型=%s", vtype)
        # 在消息前附加修正提示（不删除原内容，保留审计）
        corrected_content = f"{fix_hint}\n\n---\n\n{content}"
        corrected_msg = AIMessage(
            content=corrected_content,
            id=last_message.id,
        )
        # 只返回修正后的消息；add_messages reducer 会按 id 替换原消息
        return {"messages": [corrected_msg]}

    return {}


def personality_inject_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """在Agent回复末尾注入人格追问。扫描已评估维度，追加未评估维度的情境问题。"""
    import random
    
    messages = state.get("messages", []) if isinstance(state, dict) else getattr(state, 'messages', [])
    
    if not messages:
        return {}
    
    # 扫描已评估的人格维度
    assessed = set()
    for msg in messages:
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get('name') == 'update_profile':
                    args = tc.get('args', {})
                    dim_map = {
                        'personality_achievement_drive': '成就动机',
                        'personality_resilience': '抗压韧性',
                        'personality_risk_tolerance': '风险偏好',
                        'personality_learning_agility': '学习敏捷性',
                        'personality_social_intelligence': '社交能力',
                        'personality_financial_literacy': '财务素养',
                    }
                    for param, dim in dim_map.items():
                        if args.get(param):
                            assessed.add(dim)
    
    # 找最后一个 AI 消息（跳过 ToolMessage 和 HumanMessage）
    target_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if not isinstance(messages[i], AIMessage):
            continue
        if getattr(messages[i], 'content', None) and not getattr(messages[i], 'tool_call_id', None):
            tc = getattr(messages[i], 'tool_calls', None)
            if not tc:  # None or empty list = pure text response
                target_idx = i
                break
    
    if target_idx is None:
        return {}
    
    # 找下一个未评估的维度
    from graph.prompts import PERSONALITY_DIMENSION_ORDER, PERSONALITY_QUESTIONS
    
    next_dim = None
    for dim in PERSONALITY_DIMENSION_ORDER:
        if dim not in assessed:
            next_dim = dim
            break
    
    if next_dim is None:
        return {}  # 全部已评估
    
    # 选择一个模板问题
    questions = PERSONALITY_QUESTIONS.get(next_dim, [])
    if not questions:
        return {}
    
    question = random.choice(questions)
    
    # 追加到最后一个 AI 消息的 content
    new_messages = list(messages)
    old_msg = new_messages[target_idx]
    new_content = (old_msg.content or "").rstrip() + f"\n\n{question}"
    
    # 使用相同 ID 创建替换消息（add_messages reducer 会按 ID 替换）
    new_messages[target_idx] = AIMessage(content=new_content, id=getattr(old_msg, 'id', None))
    
    return {"messages": new_messages, "response": new_content}


def should_continue(state: Dict[str, Any]) -> Literal["tools", "__end__"]:
    """路由函数：LLM要调用工具还是回复用户？"""
    messages = state.get("messages", []) if isinstance(state, dict) else getattr(state, 'messages', [])
    if not messages:
        return "__end__"

    last_message = messages[-1]

    # 检查是否有工具调用
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return "__end__"


# ============ 画像更新辅助 ============

def extract_profile_from_messages(messages: list) -> Dict[str, str]:
    """从ToolMessage中提取update_profile的调用结果，更新画像。"""
    profile_updates = {}

    for msg in messages:
        if isinstance(msg, ToolMessage):
            # 检查是否是update_profile工具的返回
            if "已更新画像信息" in str(msg.content):
                # 从返回文本中提取字段（在遇到标点符号或逗号时停止）
                import re
                fields = re.findall(r'(\w+):\s*([^,，。；;!！?？\n]+)', msg.content)
                for field, value in fields:
                    profile_updates[field] = value.strip()

    return profile_updates


# ============ 构建Agent图 ============

def build_agent():
    """构建真正的Agent图：LLM驱动的ReAct循环。"""
    from langgraph.graph import StateGraph, START, END
    from langgraph.prebuilt import ToolNode, tools_condition
    from langgraph.checkpoint.memory import MemorySaver

    from graph.state import GraphState

    tools = get_all_tools()
    tool_node = ToolNode(tools, handle_tool_errors=True)

    # 定义图
    workflow = StateGraph(GraphState)

    # 添加节点
    workflow.add_node("agent", agent_node)
    workflow.add_node("constitution_check", constitution_check_node)
    workflow.add_node("personality_inject", personality_inject_node)
    workflow.add_node("tools", tool_node)

    # 定义边
    workflow.add_edge(START, "agent")

    # agent输出后先经过宪法审查
    workflow.add_edge("agent", "constitution_check")

    # 注入人格追问
    workflow.add_edge("constitution_check", "personality_inject")

    # 审查后决定是否继续调工具
    workflow.add_conditional_edges(
        "personality_inject",
        should_continue,
        {"tools": "tools", "__end__": END},
    )

    # 工具结果回到LLM，继续推理
    workflow.add_edge("tools", "agent")

    # 编译（带检查点支持interrupt）
    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory)

    return graph


# ============ CLI入口 ============

def run_cli():
    """交互式CLI：真正的Agent对话体验。"""
    from graph.state import GraphState, get_state, clear_state

    print("=" * 60)
    print("开店Agent v3.0 — 真正的餐饮开店Agent")
    print("吕哥餐饮顾问 · 苏格拉底辩证式对话")
    print("=" * 60)
    print()
    print("输入您的问题开始对话。")
    print("命令: quit=退出, reset=重置, profile=查看画像")
    print("-" * 60)

    agent = build_agent()
    session_id = "cli_session"
    config = {"configurable": {"thread_id": session_id}}

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "退出"):
            print("再见！")
            break

        if user_input.lower() in ("reset", "重置"):
            clear_state(session_id)
            print("会话已重置。")
            continue

        if user_input.lower() in ("profile", "画像"):
            state = get_state(session_id)
            if state.profile:
                print("\n当前画像：")
                for k, v in state.profile.items():
                    if k not in ("__intent__", "__intent_confidence__"):
                        print(f"  - {k}: {v}")
            else:
                print("\n暂无画像信息。")
            continue

        # 构建输入
        state = get_state(session_id)
        state.user_input = user_input

        messages = list(state.messages) if state.messages else []
        messages.append(HumanMessage(content=user_input))

        # 调用Agent
        try:
            result = agent.invoke(
                {"messages": messages, "profile": state.profile},
                config=config,
            )

            # 提取回复
            new_messages = result.get("messages", [])
            # 更新画像
            profile_updates = extract_profile_from_messages(new_messages)
            if profile_updates:
                state.update_profile(profile_updates)

            # 打印最后的AI回复
            for msg in reversed(new_messages):
                if isinstance(msg, AIMessage) and msg.content:
                    print(f"\nAgent:\n{msg.content}")
                    break

        except Exception as exc:
            logger.error("Agent执行异常: %s", exc)
            print(f"\n抱歉，处理时出现异常：{exc}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_cli()