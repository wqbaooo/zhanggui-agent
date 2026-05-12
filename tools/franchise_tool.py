#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加盟分析工具：结构化评估加盟品牌的真实成本和风险。

核心价值：给 LLM 一个分析框架，确保加盟分析覆盖所有关键指标，
避免用户被官方宣传数据误导。

数据来源：
- 用户提供的品牌信息（加盟费、合同条款等）
- 联网搜索（真实闭店率、加盟商评价、投诉记录）
- 财务测算（真实回本周期，含隐性成本）
- 知识库（加盟防骗经验、合同陷阱案例）
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from tools.base import BaseTool, ToolMeta, ToolResult

logger = logging.getLogger(__name__)


# ============ 加盟隐性成本清单（行业常见） ============

HIDDEN_COST_ITEMS = [
    ("保证金", "通常3-10万，合同期满可退但条件苛刻"),
    ("管理费/品牌使用费", "通常营业额的3-8%，或固定月费"),
    ("设备强制采购", "必须从总部采购，通常比市场价高20-50%"),
    ("装修标准", "必须使用总部指定装修队，单价通常高于市场价"),
    ("首批物料", "开业前强制采购，可能积压"),
    ("培训费", "含差旅、食宿、人均数千到上万"),
    ("系统使用费", "POS系统、会员系统、供应链系统年费"),
    ("营销基金", "部分品牌强制抽取营业额1-3%用于品牌广告"),
    ("续约费", "合同到期后续约费用，通常数万元"),
    ("违约金", "提前解约的赔偿条款，注意计算方式"),
]

# 加盟 vs 自营核心差异点
FRANCHISE_VS_SELF = {
    "初期投入": "加盟通常高10-30万（加盟费+保证金+强制装修/设备）",
    "运营成本": "加盟多3-8%管理费/品牌费，自营无此支出",
    "产品自由度": "加盟严格按总部配方和SOP，自营可自由调整",
    "供应链": "加盟强制从总部采购，自营可多渠道比价",
    "品牌背书": "加盟有品牌认知度（但可能负面），自营从零开始",
    "闭店损失": "加盟解约时保证金可能不退，设备也难转手",
    "学习成本": "加盟有培训体系，自营靠自己摸索或请顾问",
}


@dataclass
class FranchiseAnalysis:
    """加盟分析结果。"""
    brand_name: str = ""
    city: str = ""           # 意向城市
    category: str = ""       # 品类
    
    # 官方数据（用户提供或搜索获得）
    official_franchise_fee: float = 0.0      # 加盟费（万）
    official_guarantee: float = 0.0          # 保证金（万）
    official_management_fee: float = 0.0     # 管理费（万/年或%）
    official_total_investment: float = 0.0   # 官方宣称总投资（万）
    official_payback_months: int = 0         # 官方宣称回本周期（月）
    
    # 真实成本估算
    hidden_costs: Dict[str, float] = field(default_factory=dict)
    real_total_investment: float = 0.0       # 真实总投资（含隐性成本）
    
    # 风险评估
    closure_rate: Optional[float] = None     # 闭店率（%）
    closure_rate_source: str = ""            # 数据来源
    risk_flags: List[str] = field(default_factory=list)
    
    # 对比分析
    franchise_vs_self: Dict[str, str] = field(default_factory=dict)
    
    # 建议
    recommendation: str = ""               # Conditional Go / No-Go / Needs More Data
    key_questions: List[str] = field(default_factory=list)


class FranchiseTool(BaseTool):
    """加盟分析工具。"""
    
    meta = ToolMeta(
        name="analyze_franchise",
        description="分析加盟品牌的真实成本、风险和可行性。输入品牌名称和已知信息，输出结构化分析报告。",
        applicable_intents=["加盟分析", "选品决策", "风险控制", "开店规划"],
        required_profile_fields=["brand_name"],
        optional_profile_fields=["city", "category", "franchise_fee", "guarantee", "management_fee", "total_investment", "store_area", "rent_monthly"],
        priority=70,
    )
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        brand_name = params.get("brand_name", "")
        city = params.get("city", "")
        category = params.get("category", "")
        
        # 解析数字参数
        franchise_fee = self._parse_money(params.get("franchise_fee", 0))
        guarantee = self._parse_money(params.get("guarantee", 0))
        management_fee = self._parse_money(params.get("management_fee", 0))
        total_investment = self._parse_money(params.get("total_investment", 0))
        store_area = self._parse_money(params.get("store_area", 0))
        rent_monthly = self._parse_money(params.get("rent_monthly", 0))
        
        analysis = FranchiseAnalysis(
            brand_name=brand_name,
            city=city,
            category=category,
            official_franchise_fee=franchise_fee,
            official_guarantee=guarantee,
            official_management_fee=management_fee,
            official_total_investment=total_investment,
        )
        
        # 1. 估算隐性成本
        analysis.hidden_costs = self._estimate_hidden_costs(
            franchise_fee, guarantee, management_fee, total_investment, store_area
        )
        analysis.real_total_investment = total_investment + sum(analysis.hidden_costs.values())
        
        # 2. 风险标记检查
        analysis.risk_flags = self._check_risk_flags(
            brand_name, franchise_fee, guarantee, total_investment, analysis.real_total_investment
        )
        
        # 3. 加盟 vs 自营对比
        analysis.franchise_vs_self = self._build_comparison(category)
        
        # 4. 生成建议
        analysis.recommendation, analysis.key_questions = self._generate_recommendation(analysis)
        
        # 5. 构建报告
        report = self._build_report(analysis)
        
        return ToolResult(success=True, data=report)
    
    def _parse_money(self, value) -> float:
        """解析金额（支持字符串如'5万'、'8%'）。"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            v = value.strip().replace("万", "").replace("元", "").replace(",", "")
            try:
                return float(v)
            except ValueError:
                return 0.0
        return 0.0
    
    def _estimate_hidden_costs(
        self, franchise_fee: float, guarantee: float, management_fee: float,
        total_investment: float, store_area: float
    ) -> Dict[str, float]:
        """估算隐性成本。"""
        hidden = {}
        
        # 如果用户没提供，按行业常规估算
        if franchise_fee > 0 and guarantee == 0:
            hidden["保证金（估算）"] = franchise_fee * 0.5  # 通常加盟费的50%
        
        if management_fee == 0:
            hidden["管理费（估算，按营业额5%）"] = 0  # 标记为待确认
        
        # 设备强制采购溢价
        if total_investment > 0:
            equipment_estimate = total_investment * 0.15
            hidden["设备强制采购溢价（估算比市场价高30%）"] = equipment_estimate * 0.30
        
        # 装修标准溢价
        if store_area > 0:
            hidden["装修标准溢价（估算比市场价高20%）"] = store_area * 0.15 * 0.20
        
        # 首批物料
        if total_investment > 0:
            hidden["首批物料（估算）"] = total_investment * 0.08
        
        # 培训费（估算）
        hidden["培训及差旅（估算）"] = 0.5  # 固定估算
        
        # 系统使用费（年费）
        hidden["系统年费（估算）"] = 0.3
        
        return {k: round(v, 2) for k, v in hidden.items() if v > 0}
    
    def _check_risk_flags(
        self, brand_name: str, franchise_fee: float, guarantee: float, total_investment: float,
        real_total: float
    ) -> List[str]:
        """检查风险标记。"""
        flags = []
        
        if franchise_fee > 20:
            flags.append("加盟费超过20万，需重点考察品牌真实力和闭店率")
        
        if total_investment > 0 and real_total > total_investment * 1.3:
            flags.append("真实成本比官方宣称高30%以上，存在隐性成本陷阱")
        
        if franchise_fee > 0 and guarantee == 0:
            flags.append("用户未提供保证金信息，通常保证金=加盟费的30-100%")
        
        # 知名品牌黑名单关键词（示意）
        scam_keywords = ["快招", "割韭菜", "爆雷", "跑路"]
        # 注意：这里不直接判断品牌，只是提醒 LLM 去搜索
        flags.append(f"建议联网搜索'{brand_name} 加盟 闭店率/投诉/骗'验证口碑")
        
        return flags
    
    def _build_comparison(self, category: str) -> Dict[str, str]:
        """构建加盟 vs 自营对比。"""
        return dict(FRANCHISE_VS_SELF)
    
    def _generate_recommendation(self, analysis: FranchiseAnalysis) -> tuple:
        """生成建议。"""
        if analysis.official_franchise_fee == 0 and analysis.official_total_investment == 0:
            return "Needs More Data", [
                f"请提供{analysis.brand_name}的加盟费、总投资等官方数据",
                "请确认意向城市和门店面积",
                "建议先通过 search_web 搜索该品牌的真实闭店率和加盟商评价",
            ]
        
        if len(analysis.risk_flags) >= 3:
            return "Conditional Go", [
                "在确认以下风险可控前，不建议签约",
                "必须实地考察3家以上该品牌真实门店（非样板店）",
                "必须审查合同中的退出条款和保证金退还条件",
            ]
        
        if analysis.real_total_investment > analysis.official_total_investment * 1.2:
            return "Conditional Go", [
                "真实成本显著高于官方宣传，需重新评估资金准备",
                "建议同时考察同品类的自营方案作为对比",
            ]
        
        return "Needs More Data", [
            "需要搜索该品牌的真实闭店率和加盟商投诉记录",
            "需要了解当地该品类的市场竞争情况",
        ]
    
    def _build_report(self, analysis: FranchiseAnalysis) -> str:
        """构建结构化文本报告。"""
        lines = [
            f"# 加盟分析报告：{analysis.brand_name}",
            "",
            "## 一、官方数据",
            f"- 加盟费：{analysis.official_franchise_fee} 万",
            f"- 保证金：{analysis.official_guarantee} 万",
            f"- 管理费：{analysis.official_management_fee} 万/年（或%）",
            f"- 官方宣称总投资：{analysis.official_total_investment} 万",
            f"- 官方宣称回本周期：{analysis.official_payback_months} 个月" if analysis.official_payback_months else "- 官方宣称回本周期：未提供",
            "",
            "## 二、隐性成本估算",
        ]
        
        if analysis.hidden_costs:
            for item, cost in analysis.hidden_costs.items():
                lines.append(f"- {item}：{cost} 万")
            lines.append(f"- **真实总投资估算**：{analysis.real_total_investment:.1f} 万（比官方多 {analysis.real_total_investment - analysis.official_total_investment:.1f} 万）")
        else:
            lines.append("- 信息不足，无法估算")
        
        lines.extend([
            "",
            "## 三、风险提示",
        ])
        
        if analysis.risk_flags:
            for flag in analysis.risk_flags:
                lines.append(f"- 🟠 {flag}")
        else:
            lines.append("- 暂无明确风险标记（但信息可能不完整）")
        
        lines.extend([
            "",
            "## 四、加盟 vs 自营对比",
        ])
        for dim, desc in analysis.franchise_vs_self.items():
            lines.append(f"- **{dim}**：{desc}")
        
        lines.extend([
            "",
            "## 五、专业建议",
            f"- **阶段性判断**：{analysis.recommendation}",
            "- **必须追问的问题**：",
        ])
        for q in analysis.key_questions:
            lines.append(f"  - {q}")
        
        lines.extend([
            "",
            "## 六、常用隐性成本清单（供参考）",
        ])
        for item, desc in HIDDEN_COST_ITEMS:
            lines.append(f"- **{item}**：{desc}")
        
        lines.append("")
        lines.append("---")
        lines.append("⚠️ 本分析基于用户提供和估算数据，实际成本可能因品牌政策、城市级别、谈判能力而异。签约前务必审查正式合同并咨询律师。")
        
        return "\n".join(lines)


# 兼容 BaseTool 接口
class FranchiseAnalysisTool(FranchiseTool):
    """兼容旧接口的别名。"""
    pass
