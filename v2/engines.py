#!/usr/bin/env python3
"""V2 Hardened Engines — Gate, Blocker, Evidence, Explain.

P0 核心引擎。替代 V2 workflow 中的硬编码逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum


# ============================================================
# Gate System (P0-A)
# ============================================================

class GateStatus(str, Enum):
    """🚦 traffic-light 状态"""
    BLOCKED = "blocked"     # 🔴 必须完成，阻塞 GO
    PARTIAL = "partial"     # 🟡 部分完成，影响 confidence
    PASSED = "passed"       # 🟢 已通过


class GateID(str, Enum):
    """5 个强制决策门"""
    FRANCHISEE_VALIDATION = "franchisee_validation"
    EX_FRANCHISEE = "ex_franchisee"
    FINANCIAL_REALITY = "financial_reality"
    LEGAL_REVIEW = "legal_review"
    REVENUE_VALIDATION = "revenue_validation"


@dataclass
class MandatoryGate:
    """一个强制决策门"""
    id: GateID
    label: str                          # 中文名
    why_matters: str                    # 为什么这个门很重要
    status: GateStatus = GateStatus.BLOCKED
    evidence_required: List[str] = field(default_factory=list)  # 需要的证据类型
    evidence_collected: List[str] = field(default_factory=list)  # 已收集的证据 id
    how_to_pass: str = ""               # 怎么通过这个门
    blocker_reason: str = ""            # 当前阻塞原因

    @property
    def emoji(self) -> str:
        return {"blocked": "🔴", "partial": "🟡", "passed": "🟢"}[self.status]


# 5 个预定义门
MANDATORY_GATES = [
    MandatoryGate(
        id=GateID.FRANCHISEE_VALIDATION,
        label="在营加盟商验证",
        why_matters="在营加盟商最了解真实成本和利润。总部给的是理想数字，加盟商说的是实际数字。",
        how_to_pass="联系至少2家在营加盟商，确认：实际投资额、回本时间、月均利润、总部支持情况。",
    ),
    MandatoryGate(
        id=GateID.EX_FRANCHISEE,
        label="退出加盟商验证",
        why_matters="退出加盟商没有利益关系。他们会告诉你为什么不做、亏了多少、总部怎么处理的。这是最有价值的反面信号。",
        how_to_pass="找到至少1家退出加盟商，了解：退出原因、亏损金额、合同纠纷、总部回复态度。",
    ),
    MandatoryGate(
        id=GateID.FINANCIAL_REALITY,
        label="财务真实性验证",
        why_matters="总部 claim 的'8个月回本''日均流水5000'必须用真实数据验证。不能靠总部的 Excel。",
        how_to_pass="基于加盟商实际数据做逆向单店模型。至少有一份加盟商流水证明。",
    ),
    MandatoryGate(
        id=GateID.LEGAL_REVIEW,
        label="合同条款审核",
        why_matters="加盟合同里有很多坑：加盟费不退、品牌方单方解约权、区域保护模糊。签了就是法律义务。",
        how_to_pass="逐条核对合同关键条款：区域保护、退出条款、续约条件、转让限制、罚款条款。建议请律师审阅。",
    ),
    MandatoryGate(
        id=GateID.REVENUE_VALIDATION,
        label="真实流水验证",
        why_matters="流水是加盟的核心。总部说的'日均流水'和实际看到的可能差30%-50%。必须亲眼看到真实数据。",
        how_to_pass="实地观察2-3家门店，记录不同时段的客流量和客单价。至少有一份加盟商的POS流水截图。",
    ),
]


class GateEngine:
    """决策门引擎 — 检查 Gate 状态，强制执行硬阻塞"""

    @staticmethod
    def init_gates() -> List[MandatoryGate]:
        """初始化 5 个强制门，全部 BLOCKED"""
        return [MandatoryGate(
            id=g.id, label=g.label, why_matters=g.why_matters,
            how_to_pass=g.how_to_pass, status=GateStatus.BLOCKED,
        ) for g in MANDATORY_GATES]

    @staticmethod
    def check_all(gates: List[MandatoryGate]) -> Dict[str, Any]:
        """检查所有门的状态"""
        blocked = [g for g in gates if g.status == GateStatus.BLOCKED]
        partial = [g for g in gates if g.status == GateStatus.PARTIAL]
        passed = [g for g in gates if g.status == GateStatus.PASSED]

        return {
            "blocked_count": len(blocked),
            "partial_count": len(partial),
            "passed_count": len(passed),
            "blocked_gates": [g.id.value for g in blocked],
            "can_go": len(blocked) == 0,
            "summary": f"{'🟢' * len(passed)}{'🟡' * len(partial)}{'🔴' * len(blocked)}"
        }

    @staticmethod
    def find_first_blocker(gates: List[MandatoryGate]) -> Optional[MandatoryGate]:
        """找到第一个阻塞的门"""
        for g in gates:
            if g.status == GateStatus.BLOCKED:
                return g
        for g in gates:
            if g.status == GateStatus.PARTIAL:
                return g
        return None

    @staticmethod
    def pass_gate(gates: List[MandatoryGate], gate_id: GateID, evidence_id: str) -> List[MandatoryGate]:
        """标记一个门为通过"""
        for g in gates:
            if g.id == gate_id:
                g.status = GateStatus.PASSED
                g.evidence_collected.append(evidence_id)
                g.blocker_reason = ""
        return gates


# ============================================================
# Blocker Engine (P0-B)
# ============================================================

@dataclass
class CurrentBlocker:
    """当前最大阻塞"""
    title: str                          # 阻塞描述
    why_important: str                  # 为什么这个阻塞重要
    what_to_do: str                     # 具体怎么做
    blocker_type: str                   # gate_blocked / evidence_gap / mission_pending / stalled

    def to_next_action(self) -> Dict[str, str]:
        """转为 next_best_action 输出格式"""
        return {
            "next_best_action": self.what_to_do,
            "next_action_why": self.why_important,
            "blocker_title": self.title,
        }


class BlockerEngine:
    """阻塞检测引擎 — 替代硬编码 next_best_action"""

    @staticmethod
    def find_blocker(
        gates: List[MandatoryGate],
        missions_done: int,
        missions_total: int,
        last_action_time: Optional[str],
    ) -> CurrentBlocker:
        """找到当前最大的阻塞，生成唯一下一步行动"""

        # 优先 1: Hard Gate 阻塞 → 最高优先级
        first_blocker = GateEngine.find_first_blocker(gates)
        if first_blocker:
            return CurrentBlocker(
                title=f"决策门阻塞：{first_blocker.label}",
                why_important=first_blocker.why_matters,
                what_to_do=f"今天：{first_blocker.label}\n怎么做：{first_blocker.how_to_pass}",
                blocker_type="gate_blocked",
            )

        # 优先 2: 验证任务未完成
        undone = missions_total - missions_done
        if undone > 0:
            return CurrentBlocker(
                title=f"还有 {undone} 个验证任务未完成",
                why_important="线下验证是加盟决策最可靠的依据。",
                what_to_do=f"今天：完成一个验证任务。还有 {undone} 个待办。",
                blocker_type="mission_pending",
            )

        # 优先 3: 停滞检测
        if last_action_time:
            try:
                last = datetime.fromisoformat(last_action_time)
                days_since = (datetime.now() - last).days
                if days_since >= 3:
                    return CurrentBlocker(
                        title=f"已 {days_since} 天没有推进",
                        why_important="加盟决策不能无限犹豫。拖延不会让风险变小。",
                        what_to_do="今天：回顾当前证据，做出阶段性判断。",
                        blocker_type="stalled",
                    )
            except Exception:
                pass

        # 默认：可以前进
        return CurrentBlocker(
            title="当前没有阻塞",
            why_important="所有门已通过，可以进入最终决策。",
            what_to_do="今天：回顾所有证据，确认签约条件是否成熟。",
            blocker_type="gate_blocked",
        )


# ============================================================
# Evidence Engine (P0-C)
# ============================================================

@dataclass
class StructuredEvidence:
    """结构化证据 — 支持多对多关系"""
    id: str = ""
    claim: str = ""                     # 主张内容
    source_type: str = ""               # hq | franchisee | ex_franchisee | field | public | legal | financial
    source_name: str = ""              # 来源名称（如"加盟商张三"）
    supports: List[str] = field(default_factory=list)    # 支持的论点 ID
    contradicts: List[str] = field(default_factory=list) # 反对的论点 ID
    reliability: float = 0.5           # 0-1 可信度
    collected_at: str = ""
    verified: bool = False
    notes: str = ""

    def summary(self) -> str:
        return f"[{self.source_type}/{self.source_name}] {self.claim} (可信度:{self.reliability:.0%})"


class EvidenceEngine:
    """证据引擎 — 管理证据关系图"""

    @staticmethod
    def add_evidence(
        bank: List[StructuredEvidence],
        claim: str, source_type: str, source_name: str,
        supports: Optional[List[str]] = None,
        contradicts: Optional[List[str]] = None,
        reliability: float = 0.5,
    ) -> List[StructuredEvidence]:
        """添加一条新证据"""
        ev = StructuredEvidence(
            id=f"ev_{len(bank)+1}",
            claim=claim,
            source_type=source_type,
            source_name=source_name,
            supports=supports or [],
            contradicts=contradicts or [],
            reliability=min(max(reliability, 0), 1),
            collected_at=datetime.now().isoformat(),
        )
        bank.append(ev)
        return bank

    @staticmethod
    def find_contradictions(bank: List[StructuredEvidence]) -> List[Dict[str, str]]:
        """Rule-based：找同一主张的不同说法"""
        contradictions = []
        by_claim: Dict[str, List[StructuredEvidence]] = {}
        for ev in bank:
            key = ev.claim[:30]  # 简化：用前30字分组
            if key not in by_claim:
                by_claim[key] = []
            by_claim[key].append(ev)

        for key, evs in by_claim.items():
            if len(evs) < 2:
                continue
            highs = [e for e in evs if e.reliability > 0.6]
            if len(highs) < 2:
                continue
            sources = set(e.source_type for e in highs)
            if len(sources) >= 2:
                contradictions.append({
                    "claim": key,
                    "sources": [f"{e.source_name}({e.source_type})" for e in highs],
                    "note": "不同来源对同一主张有差异，需要进一步验证",
                })
        return contradictions

    @staticmethod
    def detect_franchise_contradictions(
        hq_claims: Dict[str, str],
        franchisee_data: Dict[str, str],
    ) -> List[Dict[str, str]]:
        """加盟专用：对比总部说法 vs 加盟商数据"""
        contradictions = []
        for key in hq_claims:
            if key in franchisee_data:
                hq_val = hq_claims[key]
                fr_val = franchisee_data[key]
                if hq_val != fr_val:
                    contradictions.append({
                        "field": key,
                        "hq_says": hq_val,
                        "franchisee_says": fr_val,
                        "note": f"总部说'{hq_val}'，加盟商说'{fr_val}'。可能原因：城市不同、商圈不同、店型不同、时间不同。",
                    })
        return contradictions

    @staticmethod
    def score_reliability(evidence: StructuredEvidence) -> float:
        """根据来源类型计算基础可信度"""
        base = {
            "field": 0.8,         # 实地观察 → 高可信
            "ex_franchisee": 0.7, # 退出加盟商 → 可信
            "franchisee": 0.6,    # 在营加盟商 → 较可信
            "financial": 0.6,     # 财务数据 → 较可信
            "public": 0.4,        # 公开数据 → 中等
            "legal": 0.9,         # 法律文件 → 最高可信
            "hq": 0.3,            # 总部说法 → 低可信
        }
        return base.get(evidence.source_type, 0.5)


# ============================================================
# Explain Engine (P0-D)
# ============================================================

class ExplainEngine:
    """解释引擎 — 为每个行动生成 why_matters + how_to_verify"""

    @staticmethod
    def explain_gate(gate: MandatoryGate) -> Dict[str, str]:
        """为决策门生成解释"""
        return {
            "why_important": gate.why_matters,
            "how_to_pass": gate.how_to_pass,
            "blocker_status": {
                "blocked": "这一步必须完成，否则不能进入签约阶段。",
                "partial": "还需要补充更多信息。",
                "passed": "已通过。",
            }.get(gate.status, ""),
        }

    @staticmethod
    def explain_mission(
        title: str, category: str, city: str, brand: str
    ) -> Dict[str, str]:
        """为验证任务动态生成解释 — 基于用户约束"""
        templates = {
            "访谈在营加盟商": {
                "why_matters": f"在{city}做{brand}的加盟商最了解真实情况。总部给的是理想数字，加盟商说的是{city}的实际数字。",
                "how_to_verify": f"联系2-3个{city}附近的{brand}加盟商。问：实际投资超了多少？{city}的真实回本周期？总部支持到位吗？",
            },
            "访谈退出加盟商": {
                "why_matters": "退出加盟商没有利益关系，会说真话。他们能告诉你加盟最大的坑在哪。",
                "how_to_verify": "找1-2个做过的。问：为什么不做？亏了多少钱？总部怎么处理的？如果有人重来会怎么做？",
            },
            "实地观察门店": {
                "why_matters": f"亲眼看到的客流和总部说的可能差30%-50%。{category}品类在不同时段差异很大。",
                "how_to_verify": f"去{city}的{brand}门店，午餐和晚餐时段各观察1小时。记录客流量、客单价、外卖取餐量。",
            },
            "验证区域保护": {
                "why_matters": "如果总部在你附近再开店，你的店就没有区域保护。很多加盟商因为这个亏损。",
                "how_to_verify": "问加盟商：\"附近还会继续开吗？\" 问总部：\"区域保护的具体条款是什么？\" 确认是写在合同里还是口头承诺。",
            },
        }
        return templates.get(title, {
            "why_matters": f"完成{title}是推进加盟决策的关键一步。",
            "how_to_verify": f"执行{title}，收集相关证据并标记完成。",
        })


# ============================================================
# Mission Engine
# ============================================================

class MissionEngine:
    """动态验证任务生成 — 基于约束和知识库，替代硬编码 3 个 mission"""

    @staticmethod
    def generate_missions(
        category: str, city: str, brand: str, budget: Optional[int]
    ) -> List[Dict[str, str]]:
        """根据用户约束动态生成验证任务"""
        missions = [
            {
                "title": "访谈在营加盟商",
                "description": f"联系2-3个{city}附近的{brand}加盟商",
                "why_matters": ExplainEngine.explain_mission("访谈在营加盟商", category, city, brand)["why_matters"],
                "how_to_verify": ExplainEngine.explain_mission("访谈在营加盟商", category, city, brand)["how_to_verify"],
            },
            {
                "title": "访谈退出加盟商",
                "description": "找到1-2个退出的加盟商了解原因",
                "why_matters": ExplainEngine.explain_mission("访谈退出加盟商", category, city, brand)["why_matters"],
                "how_to_verify": ExplainEngine.explain_mission("访谈退出加盟商", category, city, brand)["how_to_verify"],
            },
            {
                "title": "实地观察门店",
                "description": f"在饭点和非饭点各观察1小时",
                "why_matters": ExplainEngine.explain_mission("实地观察门店", category, city, brand)["why_matters"],
                "how_to_verify": ExplainEngine.explain_mission("实地观察门店", category, city, brand)["how_to_verify"],
            },
            {
                "title": "验证区域保护",
                "description": "确认合同中的区域保护条款",
                "why_matters": ExplainEngine.explain_mission("验证区域保护", category, city, brand)["why_matters"],
                "how_to_verify": ExplainEngine.explain_mission("验证区域保护", category, city, brand)["how_to_verify"],
            },
        ]

        # 基于品类追加
        if category in ("茶饮", "奶茶"):
            missions.append({
                "title": "验证供应链成本",
                "description": "确认原材料和配送成本",
                "why_matters": "茶饮品牌的利润大头在供应链。总部供应的原料价格直接影响你的毛利率。",
                "how_to_verify": "问加盟商：\"原材料占营收多少？总部涨价频率？能否自采替代品？\"",
            })

        if category in ("火锅", "正餐"):
            missions.append({
                "title": "验证人工成本",
                "description": "确认实际人工占比",
                "why_matters": "正餐和火锅人工占比高，总部给的数字通常是理想情况。",
                "how_to_verify": "问加盟商：\"需要多少人？实际工资多少？淡旺季怎么排班？\"",
            })

        if budget and budget < 300000:
            missions.append({
                "title": "验证隐性成本",
                "description": f"预算{budget/10000:.0f}万比较紧，确认没有额外费用",
                "why_matters": "预算紧张时，任何额外费用都可能成为致命问题。总部报的价格通常不含设备、装修、保证金。",
                "how_to_verify": "问加盟商：\"实际总投资比总部报的高多少？哪些费用总部没提？\"",
            })

        return missions
