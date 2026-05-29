#!/usr/bin/env python3
"""V2 Server Routes — Case Management API."""

from fastapi import APIRouter, HTTPException
from typing import Optional

from v2.state import (
    DecisionCaseState, CasePhase, DecisionMode, SprintStage,
    FranchiseConstraint, Opportunity, Evidence, ActionMission,
)
from v2.workflow import build_graph

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
