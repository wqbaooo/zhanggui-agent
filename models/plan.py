#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开店计划模型：Plan、Phase、Task、Milestone等。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class TaskStatus(Enum):
    """任务状态。"""
    PENDING = "pending"           # 待办
    IN_PROGRESS = "in_progress"   # 进行中
    BLOCKED = "blocked"           # 被阻塞
    COMPLETED = "completed"       # 已完成
    SKIPPED = "skipped"           # 已跳过


class PhaseType(Enum):
    """阶段类型。"""
    IDEA_VALIDATION = "idea_validation"       # 想法验证
    SITE_SELECTION = "site_selection"         # 选址筹备
    PREPARATION = "preparation"               # 开店准备
    OPERATION = "operation"                   # 运营增长


@dataclass
class Task:
    """单个任务。"""
    id: str
    title: str
    description: str
    phase: PhaseType
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5  # 1-10，越高越重要
    estimated_hours: Optional[int] = None
    deadline: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)  # 依赖的任务ID
    acceptance_criteria: List[str] = field(default_factory=list)
    assigned_tools: List[str] = field(default_factory=list)  # 需要的工具
    result: Optional[str] = None  # 执行结果
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


@dataclass
class Phase:
    """一个阶段（包含多个任务）。"""
    id: str
    name: str
    phase_type: PhaseType
    description: str
    tasks: List[Task] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    estimated_days: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    go_no_go_criteria: List[str] = field(default_factory=list)  # 阶段通过条件


@dataclass
class Milestone:
    """里程碑。"""
    id: str
    name: str
    description: str
    phase: PhaseType
    criteria: List[str]  # 达成条件
    status: TaskStatus = TaskStatus.PENDING
    achieved_at: Optional[str] = None


@dataclass
class Plan:
    """开店主计划。"""
    id: str
    title: str
    description: str
    phases: List[Phase] = field(default_factory=list)
    milestones: List[Milestone] = field(default_factory=list)
    current_phase_id: Optional[str] = None
    overall_status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 方案对比（支持A/B/C方案）
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    selected_alternative: Optional[int] = None
    
    def get_current_phase(self) -> Optional[Phase]:
        """获取当前阶段。"""
        if not self.current_phase_id:
            return None
        for phase in self.phases:
            if phase.id == self.current_phase_id:
                return phase
        return None
    
    def get_pending_tasks(self) -> List[Task]:
        """获取所有待办任务。"""
        tasks = []
        for phase in self.phases:
            for task in phase.tasks:
                if task.status == TaskStatus.PENDING:
                    tasks.append(task)
        return sorted(tasks, key=lambda t: t.priority, reverse=True)
    
    def get_completed_tasks(self) -> List[Task]:
        """获取所有已完成任务。"""
        tasks = []
        for phase in self.phases:
            for task in phase.tasks:
                if task.status == TaskStatus.COMPLETED:
                    tasks.append(task)
        return tasks
    
    def progress_percentage(self) -> float:
        """计算计划完成百分比。"""
        all_tasks = []
        for phase in self.phases:
            all_tasks.extend(phase.tasks)
        if not all_tasks:
            return 0.0
        completed = sum(1 for t in all_tasks if t.status == TaskStatus.COMPLETED)
        return (completed / len(all_tasks)) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "phases": [
                {
                    "id": p.id,
                    "name": p.name,
                    "phase_type": p.phase_type.value,
                    "description": p.description,
                    "status": p.status.value,
                    "tasks": [
                        {
                            "id": t.id,
                            "title": t.title,
                            "status": t.status.value,
                            "priority": t.priority,
                        }
                        for t in p.tasks
                    ],
                }
                for p in self.phases
            ],
            "milestones": [
                {
                    "id": m.id,
                    "name": m.name,
                    "status": m.status.value,
                }
                for m in self.milestones
            ],
            "current_phase_id": self.current_phase_id,
            "overall_status": self.overall_status.value,
            "progress": self.progress_percentage(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def generate_plan(profile: Dict[str, Any]) -> Plan:
    """根据用户画像生成开店计划。"""
    plan = Plan(
        id="plan_001",
        title=f"{profile.get('城市', '未知城市')}{profile.get('品类', '餐饮')}店开店计划",
        description="基于用户画像自动生成的开店执行计划",
    )
    
    # Phase 1: 想法验证
    phase1 = Phase(
        id="phase_1",
        name="想法验证",
        phase_type=PhaseType.IDEA_VALIDATION,
        description="验证开店想法的可行性",
        estimated_days=7,
        go_no_go_criteria=[
            "品类与目标客群匹配度>60%",
            "保守测算下12个月内可回本",
            "无重大风险信号（加盟骗局、硬件硬伤等）",
        ],
    )
    phase1.tasks = [
        Task(id="t1_1", title="品类市场调研", description="分析目标品类在当地的市场容量和竞争强度", phase=PhaseType.IDEA_VALIDATION, priority=10),
        Task(id="t1_2", title="预算结构规划", description="明确总投资、资金来源、备用金比例", phase=PhaseType.IDEA_VALIDATION, priority=9, dependencies=["t1_1"]),
        Task(id="t1_3", title="财务保守测算", description="基于保守假设计算盈亏平衡点和回本周期", phase=PhaseType.IDEA_VALIDATION, priority=10, dependencies=["t1_2"]),
        Task(id="t1_4", title="风险评估", description="识别加盟风险、选址风险、经营风险", phase=PhaseType.IDEA_VALIDATION, priority=8),
        Task(id="t1_5", title="Go/No-Go决策", description="综合评估后做出是否继续的决定", phase=PhaseType.IDEA_VALIDATION, priority=10, dependencies=["t1_1", "t1_3", "t1_4"]),
    ]
    
    # Phase 2: 选址筹备
    phase2 = Phase(
        id="phase_2",
        name="选址筹备",
        phase_type=PhaseType.SITE_SELECTION,
        description="找到合适的商铺位置",
        estimated_days=14,
        go_no_go_criteria=[
            "有效客流经实地验证",
            "租金营收比<20%",
            "无硬件硬伤（消防、排烟、排污）",
            "转让费/租金在预算内",
        ],
    )
    phase2.tasks = [
        Task(id="t2_1", title="商圈扫描", description="使用地图工具分析目标区域的商圈结构", phase=PhaseType.SITE_SELECTION, priority=10),
        Task(id="t2_2", title="竞品调研", description="实地调研周边竞品，收集价格/客流/评价数据", phase=PhaseType.SITE_SELECTION, priority=9, dependencies=["t2_1"]),
        Task(id="t2_3", title="候选铺位筛选", description="根据商圈分析筛选3-5个候选铺位", phase=PhaseType.SITE_SELECTION, priority=10, dependencies=["t2_1"]),
        Task(id="t2_4", title="实地蹲点", description="对候选铺位进行分时段蹲点，记录有效客流", phase=PhaseType.SITE_SELECTION, priority=10, dependencies=["t2_3"]),
        Task(id="t2_5", title="铺位硬件评估", description="检查消防、排烟、排污、电力、面积等硬件条件", phase=PhaseType.SITE_SELECTION, priority=9, dependencies=["t2_3"]),
        Task(id="t2_6", title="选址财务测算", description="基于实际租金测算各候选铺位的盈利模型", phase=PhaseType.SITE_SELECTION, priority=10, dependencies=["t2_4"]),
        Task(id="t2_7", title="合同审核", description="审核租赁合同/转让合同的关键条款", phase=PhaseType.SITE_SELECTION, priority=8, dependencies=["t2_5"]),
        Task(id="t2_8", title="选址决策", description="对比A/B/C方案，选定最终铺位", phase=PhaseType.SITE_SELECTION, priority=10, dependencies=["t2_6", "t2_7"]),
    ]
    
    # Phase 3: 开店准备
    phase3 = Phase(
        id="phase_3",
        name="开店准备",
        phase_type=PhaseType.PREPARATION,
        description="完成装修、证照、设备、人员准备",
        estimated_days=30,
    )
    phase3.tasks = [
        Task(id="t3_1", title="证照办理", description="营业执照、食品经营许可证、消防验收等", phase=PhaseType.PREPARATION, priority=10),
        Task(id="t3_2", title="装修设计", description="确定平面布局、动线设计、装修风格", phase=PhaseType.PREPARATION, priority=9),
        Task(id="t3_3", title="设备采购", description="厨房设备、前厅设备、POS系统、监控等", phase=PhaseType.PREPARATION, priority=9),
        Task(id="t3_4", title="人员招聘", description="招聘厨师、服务员、店长，制定薪资结构", phase=PhaseType.PREPARATION, priority=8),
        Task(id="t3_5", title="供应链搭建", description="确定食材供应商、签订供货协议", phase=PhaseType.PREPARATION, priority=9),
        Task(id="t3_6", title="菜单定价", description="确定菜品结构、定价策略、毛利率控制", phase=PhaseType.PREPARATION, priority=10),
        Task(id="t3_7", title="开业筹备", description="开业活动策划、物料准备、试营业", phase=PhaseType.PREPARATION, priority=10, dependencies=["t3_1", "t3_2", "t3_3", "t3_4"]),
    ]
    
    # Phase 4: 运营增长
    phase4 = Phase(
        id="phase_4",
        name="运营增长",
        phase_type=PhaseType.OPERATION,
        description="开业后的日常运营和持续增长",
        estimated_days=90,
    )
    phase4.tasks = [
        Task(id="t4_1", title="开业活动", description="执行开业营销活动，吸引首批客流", phase=PhaseType.OPERATION, priority=10),
        Task(id="t4_2", title="抖音同城运营", description="建立抖音账号，发布同城内容，达人合作", phase=PhaseType.OPERATION, priority=9),
        Task(id="t4_3", title="美团/大众点评运营", description="优化店铺页面、设计团购套餐、管理评价", phase=PhaseType.OPERATION, priority=9),
        Task(id="t4_4", title="成本控制", description="建立成本监控体系，优化食材损耗和人力成本", phase=PhaseType.OPERATION, priority=10),
        Task(id="t4_5", title="会员体系", description="建立储值、积分、复购机制", phase=PhaseType.OPERATION, priority=8),
        Task(id="t4_6", title="数据分析", description="建立营业额、成本、客流的日常追踪和分析", phase=PhaseType.OPERATION, priority=9),
    ]
    
    plan.phases = [phase1, phase2, phase3, phase4]
    plan.current_phase_id = "phase_1"
    
    # 里程碑
    plan.milestones = [
        Milestone(id="m1", name="可行性确认", description="完成市场调研和财务测算，确认项目可行", phase=PhaseType.IDEA_VALIDATION, criteria=["市场调研完成", "财务测算通过", "风险评估完成"]),
        Milestone(id="m2", name="选址锁定", description="完成选址，签订租赁合同", phase=PhaseType.SITE_SELECTION, criteria=["候选铺位实地验证", "合同审核通过", "最终选址确定"]),
        Milestone(id="m3", name="开业准备完成", description="装修、证照、设备、人员全部到位", phase=PhaseType.PREPARATION, criteria=["证照齐全", "装修验收", "设备到位", "人员培训完成"]),
        Milestone(id="m4", name="首月盈亏平衡", description="开业首月达到盈亏平衡点", phase=PhaseType.OPERATION, criteria=["日单量达到盈亏平衡点", "现金流为正"]),
    ]
    
    return plan
