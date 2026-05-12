#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""证据检索节点：从知识库检索相关证据，支持联网搜索。

优先使用向量语义检索（解决OOV问题），BM25作为降级方案。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.state_machine import NodeResult
from models.state import AgentState, Evidence, TurnState
from tools.rag_tool import RagTool
from tools.vector_search_tool import VectorSearchTool
from tools.web_search_tool import WebSearchTool, should_search

logger = logging.getLogger(__name__)


# 意图对应的专业术语映射（去口语化，聚焦底层逻辑）
PROFESSIONAL_TERMS = {
    "选址诊断": "商圈评估 人流动线 聚客点 商铺硬件",
    "财务测算": "单店模型 盈亏平衡 投产比 ROI 成本结构",
    "风险控制": "加盟合规 合同陷阱 止损机制",
    "选品决策": "品类竞争 市场饱和度 刚需高频",
}


class EvidenceRetrieverNode:
    """证据检索节点。

    优先使用向量语义检索，BM25作为降级。
    检索策略：向量检索(query) → BM25降级 → 联网搜索补充
    """

    name = "retrieve_evidence"

    def __init__(self, rag_tool: RagTool, web_search_tool: Optional[WebSearchTool] = None,
                 vector_search_tool: Optional[VectorSearchTool] = None):
        self.rag_tool = rag_tool
        self.web_search_tool = web_search_tool
        self.vector_search_tool = vector_search_tool

    def execute(self, agent_state: AgentState, turn_state: TurnState) -> NodeResult:
        # 构建检索查询
        query = self._build_query(turn_state.user_input, turn_state.classified_intent, agent_state)

        all_evidence: list = []

        # ─── 优先向量语义检索（解决OOV问题） ───
        vector_ok = False
        if self.vector_search_tool and self.vector_search_tool.available():
            try:
                vs_result = self.vector_search_tool.execute({
                    "query": query,
                    "limit": 8,
                    "hybrid": True,
                })
                if vs_result.success and vs_result.data:
                    all_evidence.extend(vs_result.data)
                    vector_ok = True
                    logger.info("[evidence] 向量搜索获取 %d 条结果", len(vs_result.data))
            except Exception as exc:
                logger.warning("[evidence] 向量搜索失败，降级到BM25: %s", exc)

        # ─── BM25降级 ───
        if not vector_ok:
            result = self.rag_tool.execute({"query": query, "limit": 10})
            if result.success and result.data:
                all_evidence.extend(result.data)

        # 智能触发联网搜索
        web_search_count = 0
        if should_search(turn_state.user_input, turn_state.classified_intent):
            web_search_count = self._execute_web_search(turn_state.user_input, all_evidence)

        if all_evidence:
            # 审计：过滤低相关性或状态不佳的内容
            high_quality_evidence = [ev for ev in all_evidence if ev.status == "usable" and len(ev.text) > 30]

            # 分别保留不同来源的证据
            kb_evidence = [ev for ev in high_quality_evidence if ev.source_type not in ("web_search",)]
            web_evidence = [ev for ev in high_quality_evidence if ev.source_type == "web_search"]

            # 合并：最多5条知识库 + 3条web_search
            selected = (kb_evidence[:5] + web_evidence[:3])
            turn_state.retrieved_evidence = selected
            
            # 加入全局证据池（去重）
            existing_ids = {e.id for e in agent_state.evidence_pool}
            for ev in selected:
                if ev.id not in existing_ids:
                    agent_state.evidence_pool.append(ev)
                    existing_ids.add(ev.id)

        return NodeResult(
            next_node="select_tools",
            log_summary=f"vector={vector_ok}, kb={len(all_evidence)}, web={web_search_count}, filtered={len(turn_state.retrieved_evidence)}",
        )

    def _execute_web_search(self, query: str, all_evidence: list) -> int:
        """执行联网搜索，返回搜索结果数量。"""
        if not self.web_search_tool:
            return 0

        try:
            web_result = self.web_search_tool.execute({
                "query": query,
                "max_results": 5
            })
            if web_result.success and web_result.data:
                all_evidence.extend(web_result.data)
                logger.info("联网搜索获取 %d 条结果", len(web_result.data))
                return len(web_result.data)
        except Exception as exc:
            logger.warning("联网搜索失败: %s", exc)

        return 0

    def _build_query(self, user_input: str, intent: str, agent_state: AgentState) -> str:
        """构建更精准的检索查询，强化垂直领域匹配与通用化表达。"""
        parts = [user_input]
        
        # 意图对应的专业术语映射（去口语化，聚焦底层逻辑）
        professional_terms = {
            "选址诊断": "商圈评估 人流动线 聚客点 商铺硬件",
            "财务测算": "单店模型 盈亏平衡 投产比 ROI 成本结构",
            "风险控制": "加盟合规 合同陷阱 止损机制",
            "选品决策": "品类竞争 市场饱和度 刚需高频",
        }
        if intent in professional_terms:
            parts.append(professional_terms[intent])
        
        # 画像加权：如果用户确定了品类，强制加入品类相关的底层逻辑词
        profile = agent_state.get_profile_dict()
        if profile.get("品类"):
            parts.append(f"{profile['品类']} 经营逻辑")
            
        return " ".join(parts)
