#!/usr/bin/env python3
"""V2 Hardened Workflow — Franchise Decision OS.

集成 GateEngine / BlockerEngine / EvidenceEngine / ExplainEngine。
每个阶段由引擎驱动，不是硬编码。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from v2.state import (
    DecisionCaseState, CasePhase, SprintStage, DecisionMode,
    FranchiseConstraint, Opportunity,
)
from v2.engines import (
    GateEngine, BlockerEngine, EvidenceEngine, ExplainEngine, MissionEngine,
    MandatoryGate, GateStatus, GateID, StructuredEvidence,
)

logger = logging.getLogger(__name__)

# ============ LLM ============
_llm = None

def _get_llm():
    global _llm
    if _llm is not None:
        return _llm
    from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
    from langchain_openai import ChatOpenAI
    _llm = ChatOpenAI(
        model=DEEPSEEK_MODEL, base_url=DEEPSEEK_BASE_URL,
        api_key=DEEPSEEK_API_KEY, temperature=0.3, max_tokens=2000,
    )
    return _llm


# ============ Constraint Gate ============

CONSTRAINT_SYSTEM = """你是加盟约束收集助手。提取用户约束：

预算、城市、品类偏好、风险偏好(low/medium/high)。

够了输出"CONSTRAINTS_COMPLETE" + JSON。
不够就追问。只输出问或JSON，不要闲聊。"""


def constraint_node(state: DecisionCaseState) -> Dict[str, Any]:
    """P0-B: 使用 BlockerEngine 替代硬编码 next_best_action"""
    user_msgs = [m for m in state.messages if isinstance(m, HumanMessage)]
    if not user_msgs:
        return _blocker_response(state)

    last = str(user_msgs[-1].content)
    resp = _get_llm().invoke([SystemMessage(content=CONSTRAINT_SYSTEM), HumanMessage(content=last)])
    text = str(resp.content) if hasattr(resp, 'content') else str(resp)

    if "CONSTRAINTS_COMPLETE" in text:
        try:
            data = json.loads(text[text.index("{"):])
            c = FranchiseConstraint(**data)
            return {
                "constraints": c,
                "current_phase": CasePhase.OPPORTUNITY_INTAKE,
                "last_action_time": datetime.now().isoformat(),
                "next_best_action": "约束已记录。现在告诉我：你在考虑哪些加盟品牌？",
            }
        except Exception:
            pass
    return {"next_best_action": text}


# ============ Opportunity Intake ============

OPPORTUNITY_PROMPT = """从消息提取加盟机会。JSON数组：
[{"brand_name":"","source":"","category":"","investment_min":数字|null,"initial_impression":""}]
没有就空数组。"""


def opportunity_intake_node(state: DecisionCaseState) -> Dict[str, Any]:
    user_msgs = [m for m in state.messages if isinstance(m, HumanMessage)]
    if not user_msgs:
        return _blocker_response(state)

    last = str(user_msgs[-1].content)
    try:
        resp = _get_llm().invoke([SystemMessage(content=OPPORTUNITY_PROMPT), HumanMessage(content=last)])
        text = str(resp.content) if hasattr(resp, 'content') else str(resp)
        data = json.loads(text[text.index("["):])
        if not data:
            return {"next_best_action": "没发现品牌名。你有在考虑的品牌吗？说名字就行。"}

        opps = []
        for item in data:
            opps.append(Opportunity(
                id=f"opp_{len(state.opportunities)+1}",
                brand_name=item["brand_name"],
                source=item.get("source", "用户录入"),
                category=item.get("category", ""),
                investment_min=item.get("investment_min"),
                initial_impression=item.get("initial_impression", ""),
            ))
        return {
            "opportunities": state.opportunities + opps,
            "current_phase": CasePhase.CANDIDATE_STACK,
            "last_action_time": datetime.now().isoformat(),
            "next_best_action": f"收录 {len(opps)} 个机会。要比较还是深入分析某一个？",
        }
    except Exception:
        return {"next_best_action": "告诉我品牌名字，我帮你记录。"}


# ============ Candidate Stack ============

def candidate_stack_node(state: DecisionCaseState) -> Dict[str, Any]:
    opps = state.opportunities
    if not opps:
        return {"next_best_action": "还没有候选。告诉我你想了解的品牌。"}

    active = [o for o in opps if o.status != "eliminated"]
    if not active:
        return {"next_best_action": "所有候选淘汰。要重新找吗？"}

    if len(active) == 1:
        o = active[0]
        return {
            "primary_candidate_id": o.id,
            "advancing_candidates": [o.id],
            "current_phase": CasePhase.DECISION_SPRINT,
            "sprint_stage": SprintStage.KILL_FAST,
            "last_action_time": datetime.now().isoformat(),
            "next_best_action": f"只有一个候选：{o.brand_name}。开始尽调。",
        }

    summary = "候选栈：\n"
    for i, o in enumerate(active, 1):
        b = f"约{o.investment_min/10000:.0f}万" if o.investment_min else "?"
        summary += f"  {i}. {o.brand_name} | {o.category} | {b} | {o.source}\n"
    return {
        "hito_interrupt": True,
        "interrupt_reason": "选择候选",
        "interrupt_options": [f"分析 {o.brand_name}" for o in active] + ["全部淘汰重新找"],
        "next_best_action": summary + "\n淘汰哪个？还是分析某一个？",
    }


# ============ Decision Sprint ============

KILL_FAST_PROMPT = """加盟尽调 Kill Fast。找致命问题：
1. 成立<1年？→ 快招风险
2. 无商务部备案？→ 不合法
3. 回本<6月？→ 几乎肯定造假
4. 加盟费远低于行业？→ 骗局可能
5. 区域保护模糊？→ 风险
致命问题→建议NO-GO。无致命→输出"PASS_KILL_FAST"。"""


def decision_sprint_node(state: DecisionCaseState) -> Dict[str, Any]:
    pid = state.primary_candidate_id
    if not pid:
        return {"next_best_action": "先选一个候选。"}

    opp = next((o for o in state.opportunities if o.id == pid), None)
    if not opp:
        return {"next_best_action": "候选不存在。"}

    stage = state.sprint_stage or SprintStage.KILL_FAST

    if stage == SprintStage.KILL_FAST:
        return _kill_fast(opp, state)
    elif stage == SprintStage.CORE_VALIDATION:
        return _core_validation(state)
    elif stage == SprintStage.DECISION_LOCK:
        return _decision_lock(state)

    return {"next_best_action": "未知阶段。"}


def _kill_fast(opp: Opportunity, state: DecisionCaseState) -> Dict[str, Any]:
    """P0-C: 使用 StructuredEvidence + EvidenceEngine"""
    ctx = f"品牌:{opp.brand_name} 品类:{opp.category} 投资:{opp.investment_min}-{opp.investment_max}"
    try:
        kb = ""
        try:
            from tools.vector_search_tool import VectorSearchTool
            vec = VectorSearchTool()
            if vec.available():
                r = vec.execute({"query": f"{opp.brand_name} 加盟 风险 快招", "limit": 3, "hybrid": True})
                if r.success and r.data:
                    kb = "知识库：\n" + "\n---\n".join(str(e)[:300] for e in r.data[:3])
        except Exception:
            pass

        text = str(_get_llm().invoke(
            f"{KILL_FAST_PROMPT}\n\n预算{state.constraints.budget} 城市{state.constraints.city}\n{ctx}\n{kb}"
        ).content)

        if "PASS_KILL_FAST" in text:
            return {
                "sprint_stage": SprintStage.CORE_VALIDATION,
                "evidence_bank": state.evidence_bank + [
                    StructuredEvidence(id=f"ev_{len(state.evidence_bank)+1}",
                                       claim="Kill Fast通过", source_type="system",
                                       source_name="AI分析", notes=text, reliability=0.5)
                ],
                "last_action_time": datetime.now().isoformat(),
                "next_best_action": "快速淘汰通过。进入核心验证。",
            }
        return {
            "sprint_stage": SprintStage.DECISION_LOCK,
            "evidence_bank": state.evidence_bank + [
                StructuredEvidence(id=f"ev_{len(state.evidence_bank)+1}",
                                   claim="发现致命问题", source_type="system",
                                   source_name="AI分析", notes=text, reliability=0.5)
            ],
            "hito_interrupt": True, "interrupt_reason": "致命风险",
            "interrupt_options": ["坚持继续", "放弃", "重新找"],
            "last_action_time": datetime.now().isoformat(),
            "next_best_action": text + "\n\n建议NO-GO。要继续吗？",
        }
    except Exception as e:
        logger.error(f"Kill fast error: {e}")
        return {"next_best_action": f"分析出错：{e}。"}


def _core_validation(state: DecisionCaseState) -> Dict[str, Any]:
    """P0-A + P0-D: 初始化 Hard Gates + 动态生成 Missions"""
    c = state.constraints
    opp = next((o for o in state.opportunities if o.id == state.primary_candidate_id), None)
    brand = opp.brand_name if opp else "未知"

    # 初始化 5 个强制门
    gates = GateEngine.init_gates()

    # 动态生成验证任务
    missions = MissionEngine.generate_missions(
        category=c.category_preference[0] if c.category_preference else "",
        city=c.city or "", brand=brand, budget=c.budget,
    )

    # 使用 BlockerEngine 生成唯一下一步
    blocker = BlockerEngine.find_blocker(
        gates=gates,
        missions_done=0,
        missions_total=len(missions),
        last_action_time=state.last_action_time,
    )
    action = blocker.to_next_action()

    return {
        "gates": gates,
        "missions": missions,
        "sprint_stage": SprintStage.DECISION_LOCK,
        "last_action_time": datetime.now().isoformat(),
        "next_best_action": action["next_best_action"],
        "next_action_why": action["next_action_why"],
    }


def _decision_lock(state: DecisionCaseState) -> Dict[str, Any]:
    """P0-A: 使用 GateEngine 检查门状态，替代纯 signability 计算"""
    gates = state.gates or GateEngine.init_gates()

    # 统计 mission 完成
    missions_done = sum(1 for m in state.missions if hasattr(m, 'status') and m.status == "done")
    missions_total = len(state.missions) or 1

    # Gate 检查
    gate_check = GateEngine.check_all(gates)

    # 使用 BlockerEngine
    blocker = BlockerEngine.find_blocker(gates, missions_done, missions_total, state.last_action_time)

    # signability 基于 gate 通过率
    signability = int((gate_check["passed_count"] / 5) * 70 + (missions_done / missions_total) * 30)

    action = blocker.to_next_action()

    return {
        "signability": signability,
        "current_phase": CasePhase.DECISION_GATE,
        "next_best_action": action["next_best_action"],
        "next_action_why": action["next_action_why"],
        "stalled_warning": blocker.blocker_type == "stalled",
        "last_action_time": datetime.now().isoformat(),
        "gates": gates,
    }


# ============ Decision Gate ============

def decision_gate_node(state: DecisionCaseState) -> Dict[str, Any]:
    """P0-A: 阻塞式最终决策 — 必须有 gate 通过，不能纯看 signability 数字"""
    gates = state.gates or GateEngine.init_gates()
    check = GateEngine.check_all(gates)

    if check["blocked_count"] > 0:
        b = GateEngine.find_first_blocker(gates)
        return {
            "decision": DecisionMode.WATCH,
            "hito_interrupt": True,
            "interrupt_reason": "决策门阻塞",
            "interrupt_options": [
                f"完成 {b.label}" if b else "完成阻塞的门",
                "重新评估", "放弃",
            ],
            "next_best_action": f"🔴 {b.label} 未完成。不能签约。\n为什么：{b.why_matters}\n怎么做：{b.how_to_pass}",
        }

    signability = state.signability
    if signability >= 70:
        return {
            "decision": DecisionMode.GO,
            "hito_interrupt": True,
            "interrupt_reason": "最终决策",
            "interrupt_options": ["确认签约准备", "继续收集", "放弃"],
            "next_best_action": "🟢 条件成熟，可以签约。建议签约前再次确认合同条款。",
        }
    elif signability >= 40:
        return {
            "decision": DecisionMode.WATCH,
            "next_best_action": "🟡 还需要更多证据。建议完成线下验证任务后再决定。",
        }
    return {
        "decision": DecisionMode.NO_GO,
        "next_best_action": "🔴 不建议签约。风险过高或信息不足。建议重新找其他机会。",
    }


# ============ Blocker Response Helper ============

def _blocker_response(state: DecisionCaseState) -> Dict[str, Any]:
    """P0-B: 无用户输入时，用 BlockerEngine 生成响应"""
    gates = state.gates or GateEngine.init_gates()
    missions_done = sum(1 for m in state.missions if hasattr(m, 'status') and m.status == "done")
    blocker = BlockerEngine.find_blocker(gates, missions_done, len(state.missions) or 1, state.last_action_time)
    a = blocker.to_next_action()
    return {
        "next_best_action": a["next_best_action"],
        "next_action_why": a["next_action_why"],
        "stalled_warning": blocker.blocker_type == "stalled",
    }


# ============ Main Graph ============

def build_graph() -> StateGraph:
    wf = StateGraph(DecisionCaseState)

    wf.add_node("constraints", constraint_node)
    wf.add_node("opportunity_intake", opportunity_intake_node)
    wf.add_node("candidate_stack", candidate_stack_node)
    wf.add_node("decision_sprint", decision_sprint_node)
    wf.add_node("decision_gate", decision_gate_node)

    wf.set_entry_point("constraints")

    wf.add_edge("constraints", "opportunity_intake")
    wf.add_edge("opportunity_intake", "candidate_stack")
    wf.add_edge("candidate_stack", "decision_sprint")
    wf.add_edge("decision_sprint", "decision_gate")
    wf.add_edge("decision_gate", END)

    return wf.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["candidate_stack", "decision_gate"],
    )


def resume_after_interrupt(user_input: str, thread_id: str = "default"):
    """HITL: 用户确认后恢复工作流"""
    from langchain_core.messages import HumanMessage
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_graph()
    result = graph.invoke(
        {"messages": [HumanMessage(content=user_input)]},
        config,
    )
    return result


def get_interrupt_state(thread_id: str = "default"):
    """检查是否有中断等待用户输入"""
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_graph()
    try:
        state = graph.get_state(config)
        if state and state.next:
            return {
                "interrupted": True,
                "next_node": state.next,
                "values": state.values,
            }
        return {"interrupted": False}
    except Exception:
        return {"interrupted": False}
