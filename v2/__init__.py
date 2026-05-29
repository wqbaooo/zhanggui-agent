#!/usr/bin/env python3
"""V2 — Franchise Decision OS.

从 Chat-first Agent 升级为 Case-first Workflow。
模块化子图，固定 5 阶段流程。
"""

from v2.state import (
    DecisionCaseState, CasePhase, SprintStage, DecisionMode,
    FranchiseConstraint, Opportunity, Evidence, ClaimToProve,
    DecisionGate, ActionMission, Contradiction, UnitEconomics,
)
from v2.workflow import build_graph

__all__ = [
    "DecisionCaseState", "CasePhase", "SprintStage", "DecisionMode",
    "FranchiseConstraint", "Opportunity", "Evidence", "ClaimToProve",
    "DecisionGate", "ActionMission", "Contradiction", "UnitEconomics",
    "build_graph",
]
