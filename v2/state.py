#!/usr/bin/env python3
"""V2 State Schema — DecisionCaseState.

核心转变：从 message history → decision case。
加盟决策不是一个对话，是一个持续数周的案件。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from enum import Enum

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from typing import Annotated


class CasePhase(str, Enum):
    """案件阶段 — 冻结的 5 步流程"""
    CONSTRAINTS = "constraints"
    OPPORTUNITY_INTAKE = "opportunity_intake"
    CANDIDATE_STACK = "candidate_stack"
    DECISION_SPRINT = "decision_sprint"
    DECISION_GATE = "decision_gate"


class SprintStage(str, Enum):
    """Decision Sprint 子阶段"""
    KILL_FAST = "kill_fast"
    CORE_VALIDATION = "core_validation"
    DECISION_LOCK = "decision_lock"


class EvidenceSource(str, Enum):
    """证据来源"""
    BRAND_OFFICIAL = "brand_official"
    FRANCHISOR_CLAIM = "franchisor_claim"
    FRANCHISEE_INTERVIEW = "franchisee_interview"
    EX_FRANCHISEE = "ex_franchisee"
    STORE_OBSERVATION = "store_observation"
    FINANCIAL_MODEL = "financial_model"
    MARKET_DATA = "market_data"
    USER_OBSERVATION = "user_observation"


class EvidenceWeight(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GateType(str, Enum):
    HARD = "hard"   # 必须验证
    SOFT = "soft"   # 影响 confidence


class DecisionMode(str, Enum):
    GO = "GO"
    WATCH = "WATCH"
    NO_GO = "NO_GO"


@dataclass
class FranchiseConstraint:
    """用户约束"""
    budget: Optional[int] = None          # 总投资预算（元）
    city: Optional[str] = None            # 目标城市
    max_rent: Optional[int] = None        # 能承受的最高月租
    category_preference: List[str] = field(default_factory=list)  # 品类偏好
    risk_tolerance: str = "medium"        # low / medium / high
    time_to_decide: str = "3_months"     # 1_month / 3_months / 6_months
    prior_experience: str = "none"       # none / employee / manager / owner
    team_size: int = 1                    # 可用人数


@dataclass
class Opportunity:
    """一个加盟机会"""
    id: str = ""
    brand_name: str = ""
    source: str = ""                     # 加盟网站 / 博主 / 朋友 / 自己发现
    category: str = ""                   # 品类
    investment_min: Optional[int] = None
    investment_max: Optional[int] = None
    initial_impression: str = ""         # 初步印象
    status: str = "new"                  # new / researching / eliminated / advancing
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Evidence:
    """一条证据"""
    id: str = ""
    claim: str = ""                      # 主张（如"8个月回本"）
    source: EvidenceSource = EvidenceSource.BRAND_OFFICIAL
    source_detail: str = ""              # 具体来源（如"XX加盟商张三"）
    collected_at: str = ""
    weight: EvidenceWeight = EvidenceWeight.MEDIUM
    verified: bool = False
    supports: bool = True                # True=支持加盟, False=反对
    notes: str = ""


@dataclass
class ClaimToProve:
    """总部说法 → 需要求证"""
    claim: str                           # 原话
    source: str                          # 谁说（总部/招商经理）
    proof_required: str                  # 需要的证据类型
    status: str = "unverified"           # unverified / partially_verified / verified / contradicted
    evidence_ids: List[str] = field(default_factory=list)
    verification_method: str = ""        # 怎么验证


@dataclass
class DecisionGate:
    """一个决策门"""
    id: str = ""
    label: str = ""
    type: GateType = GateType.HARD
    status: str = "pending"              # pending / passed / failed / skipped
    evidence_ids: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class ActionMission:
    """一个行动任务 — 线下验证任务"""
    id: str = ""
    title: str = ""
    description: str = ""
    why_matters: str = ""                # 为什么重要
    how_to_verify: str = ""              # 怎么验证
    status: str = "pending"              # pending / in_progress / done / skipped
    deadline: Optional[str] = None
    evidence_ids: List[str] = field(default_factory=list)


@dataclass
class Contradiction:
    """矛盾分析"""
    id: str = ""
    description: str = ""                # 矛盾描述
    side_a: str = ""                     # 支持加盟的证据
    side_b: str = ""                     # 反对加盟的证据
    resolution: str = ""                 # 解释/解决方向
    impact: str = "medium"               # low / medium / high / blocker


@dataclass
class UnitEconomics:
    """单店经济模型（逆向推导）"""
    min_daily_revenue: float = 0         # 最低日流水（盈亏平衡）
    healthy_daily_revenue: float = 0     # 健康日流水（目标利润）
    rent_ratio: float = 0                # 租金占比
    labor_ratio: float = 0               # 人工占比
    food_cost_ratio: float = 0           # 食材成本率
    assumed_margin: float = 0            # 假设毛利率
    notes: str = ""


@dataclass
class DecisionCaseState:
    """加盟决策案件状态 — V2 核心对象"""
    
    # === 案件元数据 ===
    case_id: str = ""
    project_name: str = ""               # 如"霸王茶姬 · 新余"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = ""
    
    # === 对话历史（仅交互层） ===
    messages: Annotated[List[BaseMessage], add_messages] = field(default_factory=list)
    
    # === 当前阶段 ===
    current_phase: CasePhase = CasePhase.CONSTRAINTS
    sprint_stage: Optional[SprintStage] = None
    turn_count: int = 0
    
    # === 约束 ===
    constraints: FranchiseConstraint = field(default_factory=FranchiseConstraint)
    
    # === 候选栈 ===
    opportunities: List[Opportunity] = field(default_factory=list)
    advancing_candidates: List[str] = field(default_factory=list)  # opportunity ids
    
    # === 深度分析对象 ===
    primary_candidate_id: Optional[str] = None   # 当前正在深度分析的机会
    
    # === 证据图 ===
    evidence_bank: List[Evidence] = field(default_factory=list)
    claims_to_prove: List[ClaimToProve] = field(default_factory=list)
    
    # === 决策门 ===
    gates: List[DecisionGate] = field(default_factory=list)
    
    # === 行动任务 ===
    missions: List[ActionMission] = field(default_factory=list)
    
    # === 矛盾分析 ===
    contradictions: List[Contradiction] = field(default_factory=list)
    
    # === 经济模型 ===
    unit_economics: Optional[UnitEconomics] = None
    
    # === 情景规划 ===
    best_case_revenue: Optional[float] = None
    base_case_revenue: Optional[float] = None
    worst_case_revenue: Optional[float] = None
    
    # === 总部质量评估 ===
    franchisor_quality_score: float = 0  # 0-10
    franchisor_quality_notes: str = ""
    
    # === 地域环境 ===
    geo_notes: str = ""
    competitor_density: str = "unknown"  # low / medium / high
    
    # === 人际关系 ===
    hito_interrupt: bool = False          # 需要人工干预
    interrupt_reason: str = ""
    interrupt_options: List[str] = field(default_factory=list)
    user_decision: str = ""               # 用户在中断点的选择
    
    # === 决策动量 ===
    decision_momentum: int = 0            # 0-100, 越接近决策
    last_action_time: str = ""
    stalled_warning: bool = False
    
    # === 签约准备度 ===
    signability: int = 0                  # 0-100
    decision: DecisionMode = DecisionMode.WATCH
    
    # === 下一步行动 ===
    next_best_action: str = ""            # 唯一最重要的下一步
    next_action_why: str = ""             # 为什么这一步最重要
    
    # === 快照 ===
    phase_snapshots: Dict[str, Any] = field(default_factory=dict)  # 阶段快照
    
    def to_dict(self) -> Dict[str, Any]:
        """导出为可序列化的字典"""
        return {
            "case_id": self.case_id,
            "project_name": self.project_name,
            "current_phase": self.current_phase.value,
            "constraints": {
                "budget": self.constraints.budget,
                "city": self.constraints.city,
                "category_preference": self.constraints.category_preference,
            },
            "opportunities_count": len(self.opportunities),
            "advancing_candidates": self.advancing_candidates,
            "evidence_count": len(self.evidence_bank),
            "verified_claims": sum(1 for c in self.claims_to_prove if c.status == "verified"),
            "total_claims": len(self.claims_to_prove),
            "gates_passed": sum(1 for g in self.gates if g.status == "passed"),
            "total_gates": len(self.gates),
            "missions_done": sum(1 for m in self.missions if m.status == "done"),
            "total_missions": len(self.missions),
            "signability": self.signability,
            "decision": self.decision.value,
            "next_best_action": self.next_best_action,
        }


@dataclass
class CaseEvent:
    """案件时间线事件 — 用于 frontend 展示"""
    timestamp: str = ""
    phase: str = ""
    event_type: str = ""                  # constraint_set / opportunity_added / evidence_collected / gate_passed / decision_made
    title: str = ""
    detail: str = ""
