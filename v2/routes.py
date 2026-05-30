#!/usr/bin/env python3
"""V2 Server Routes — Case Management API."""

from fastapi import APIRouter, HTTPException
from typing import Optional

from v2.state import (
    DecisionCaseState, CasePhase, DecisionMode, SprintStage,
    FranchiseConstraint, Opportunity, Evidence, ActionMission,
)
from v2.workflow import build_graph, resume_after_interrupt, get_interrupt_state
from v2.engines import GateEngine, BlockerEngine
from v2.alpha import AlphaStore, AlphaFeedback, AlphaReport, FeedbackType, Severity

router = APIRouter(prefix="/api/v2/cases", tags=["cases"])

_workflow = build_graph()

@router.post("/new")
async def create_case(project_name: str, constraints: Optional[dict] = None):
    """创建新的加盟决策案件"""
    state = DecisionCaseState(project_name=project_name)
    if constraints:
        state.constraints = FranchiseConstraint(**constraints)

    config = {"configurable": {"thread_id": state.case_id or "new"}}
    result = _workflow.invoke({
        "project_name": project_name,
        "constraints": state.constraints,
        "current_phase": CasePhase.CONSTRAINTS,
    }, config)

    return {"case_id": result.get("case_id", ""),
            "next_best_action": result.get("next_best_action", "开始吧")}


@router.post("/{case_id}/chat")
async def case_chat(case_id: str, message: str):
    """向案件对话"""
    config = {"configurable": {"thread_id": case_id}}
    result = _workflow.invoke({
        "messages": [{"role": "human", "content": message}],
    }, config)
    return {"response": result.get("next_best_action", ""),
            "phase": result.get("current_phase", "").value if hasattr(result.get("current_phase", ""), 'value') else str(result.get("current_phase", "")),
            "momentum": result.get("decision_momentum", 0),
            "signability": result.get("signability", 0)}


@router.get("/{case_id}")
async def get_case(case_id: str):
    """获取案件状态"""
    config = {"configurable": {"thread_id": case_id}}
    try:
        state = _workflow.get_state(config)
        if state and state.values:
            return state.values
        return {"status": "not_found", "case_id": case_id}
    except Exception:
        return {"status": "error", "case_id": case_id}


@router.post("/{case_id}/evidence")
async def add_evidence(case_id: str, claim: str, source: str, weight: str = "medium", supports: bool = True):
    """添加证据"""
    config = {"configurable": {"thread_id": case_id}}
    evidence = Evidence(
        claim=claim, source=source,
        weight=weight, supports=supports,
    )
    result = _workflow.invoke({"evidence_bank": [evidence]}, config)
    return {"status": "added", "momentum": result.get("decision_momentum", 0)}


@router.post("/{case_id}/mission/{mission_id}/complete")
async def complete_mission(case_id: str, mission_id: str):
    """标记验证任务完成"""
    config = {"configurable": {"thread_id": case_id}}
    state = _workflow.get_state(config)
    if not state or not state.values:
        raise HTTPException(404, "Case not found")

    missions = state.values.get("missions", [])
    updated = []
    for m in missions:
        if m.id == mission_id:
            m.status = "done"
        updated.append(m)

    result = _workflow.invoke({"missions": updated}, config)
    return {"status": "completed", "signability": result.get("signability", 0)}


@router.get("/{case_id}/workspace")
async def get_workspace(case_id: str):
    """Case Workspace 三栏数据"""
    config = {"configurable": {"thread_id": case_id}}
    try:
        state = _workflow.get_state(config)
        if not state or not state.values:
            return {"status": "not_found"}

        vals = state.values
        gates = vals.get("gates", GateEngine.init_gates())
        evidence_bank = vals.get("evidence_bank", [])
        missions = vals.get("missions", [])

        gate_list = []
        for g in gates:
            gate_list.append({
                "id": g.id.value if hasattr(g.id, 'value') else str(g.id),
                "label": g.label,
                "status": g.status.value if hasattr(g.status, 'value') else str(g.status),
                "emoji": "🟢" if (hasattr(g, 'status') and g.status.value == "passed") else ("🟡" if "partial" in str(getattr(g, 'status', '')) else "🔴"),
                "why": g.why_matters,
            })

        missions_done = sum(1 for m in missions if (hasattr(m, 'status') and m.status == "done"))
        blocker = BlockerEngine.find_blocker(gates, missions_done, len(missions) or 1, vals.get("last_action_time"))

        ev_list = []
        for ev in evidence_bank[-5:]:
            ev_list.append({
                "claim": getattr(ev, 'claim', str(ev))[:80],
                "source": getattr(ev, 'source_type', 'system'),
                "ok": getattr(ev, 'verified', False),
            })

        m_list = []
        for m in missions:
            m_list.append({
                "id": getattr(m, 'id', ''),
                "title": getattr(m, 'title', str(m)),
                "done": hasattr(m, 'status') and m.status == "done",
            })

        return {
            "project_name": vals.get("project_name", ""),
            "current_phase": vals.get("current_phase", "constraints"),
            "signability": vals.get("signability", 0),
            "gates": gate_list,
            "blocker": blocker.title,
            "evidence": ev_list,
            "missions": m_list,
            "next_action": blocker.to_next_action(),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/{case_id}/interrupt")
async def check_interrupt(case_id: str):
    """检查是否有中断等待用户输入"""
    state = get_interrupt_state(case_id)
    return state


@router.post("/{case_id}/resume")
async def resume_case(case_id: str, user_input: str):
    """HITL: 用户确认后恢复工作流"""
    try:
        result = resume_after_interrupt(user_input, case_id)
        return {
            "status": "resumed",
            "next_best_action": result.get("next_best_action", ""),
            "phase": result.get("current_phase", ""),
            "signability": result.get("signability", 0),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ============ Alpha Testing ============

alpha_router = APIRouter(prefix="/api/alpha", tags=["alpha"])


@alpha_router.post("/{case_id}/feedback")
async def record_feedback(case_id: str, type: str, notes: str, context: str = "", severity: str = "medium"):
    """记录一条 Alpha 观察"""
    store = AlphaStore(case_id)
    fb = store.record(AlphaFeedback(
        type=FeedbackType(type),
        severity=Severity(severity),
        context=context,
        notes=notes,
    ))
    return {"recorded": True, "id": fb.id, "total": len(store.list_all())}


@alpha_router.get("/{case_id}/feedback")
async def list_feedback(case_id: str):
    """列出所有观察记录"""
    store = AlphaStore(case_id)
    return {"feedbacks": [fb.to_dict() for fb in store.list_all()]}


@alpha_router.get("/{case_id}/report")
async def get_report(case_id: str):
    """自动生成 Alpha 测试报告"""
    store = AlphaStore(case_id)
    report = AlphaReport(store)
    return report.generate()


@alpha_router.delete("/{case_id}/feedback")
async def clear_feedback(case_id: str):
    """清空观察记录"""
    store = AlphaStore(case_id)
    store.clear()
    return {"cleared": True}
