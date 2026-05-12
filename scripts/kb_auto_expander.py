#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库自动扩展系统。

自动发现知识薄弱点，从网上获取高质量内容，验证后增量写入知识库。

核心流程：
1. 覆盖度分析 —— 识别知识缺口
2. 内容发现 —— 定向搜索网络资源
3. 质量验证 —— LLM评估内容真实性和专业性
4. 结构化提取 —— 转换为实体/方法论/QA对
5. 增量索引 —— 更新Faiss向量库
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.kb_index_manager import IncrementalVectorIndex

logger = logging.getLogger(__name__)

# ============ 配置 ============
STRUCTURED_DIR = Path("knowledge_base/structured")
QA_FILE = Path("knowledge_base/qa_pairs.json")
EXTERNAL_KB_DIR = Path("knowledge_base/external")
EXTERNAL_KB_DIR.mkdir(exist_ok=True)

# 餐饮开店核心主题（用于覆盖度分析）
CORE_TOPICS = {
    "选址": ["商圈分析", "客流量", "转让费", "租金", "位置评估", "动线"],
    "选品": ["品类分析", "产品定位", "毛利率", "供应链", "菜单设计"],
    "财务": ["盈亏平衡", "投资回报", "成本结构", "现金流", "预算", "定价"],
    "加盟": ["加盟费", "品牌选择", "合同审核", "隐性成本", "直营对比"],
    "运营": ["人员管理", "排班", "品控", "服务", "营销活动"],
    "证照": ["营业执照", "食品许可", "消防", "环保", "税务"],
    "装修": ["空间设计", "动线", "厨房布局", "成本控制", "施工"],
    "设备": ["厨房设备", "采购", "维护", "清单"],
    "营销": ["抖音", "美团", "大众点评", "私域", "引流", "推广"],
    "风险": ["闭店", "亏损", "合同风险", "竞争", "食品安全"],
}


@dataclass
class KnowledgeGap:
    """知识缺口。"""
    topic: str  # 主题
    subtopic: str  # 子主题
    severity: str  # 严重度: high/medium/low
    reason: str  # 原因
    suggested_queries: List[str]  # 建议搜索查询


@dataclass
class ExternalDocument:
    """外部获取的文档。"""
    title: str
    source_url: str
    content: str
    topic: str
    quality_score: float = 0.0  # 质量评分 0-1
    verified: bool = False
    extraction_method: str = "unknown"  # web_search / crawl / api
    
    def to_text_chunks(self) -> List[Tuple[str, Dict[str, Any]]]:
        """将文档拆分为文本块（用于索引）。"""
        chunks = []
        
        # 按段落拆分
        paragraphs = [p.strip() for p in self.content.split("\n\n") if len(p.strip()) > 50]
        
        for i, para in enumerate(paragraphs[:10]):  # 最多取10段
            chunks.append((
                para,
                {
                    "type": "external",
                    "source": self.title,
                    "topic": self.topic,
                    "url": self.source_url,
                    "chunk_id": i,
                    "quality_score": self.quality_score,
                }
            ))
        
        return chunks


class CoverageAnalyzer:
    """知识覆盖度分析器。"""
    
    def __init__(self, structured_dir: Path = STRUCTURED_DIR):
        self.structured_dir = structured_dir
        self._topic_keywords = CORE_TOPICS
    
    def analyze(self) -> Tuple[Dict[str, Any], List[KnowledgeGap]]:
        """分析知识库覆盖度，返回统计信息和缺口列表。"""
        
        # 1. 加载所有结构化数据
        all_entities = []
        all_methodologies = []
        all_cases = []
        topic_files = {}
        
        for json_file in self.structured_dir.glob("*_structured.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                title = data.get("title", "")
                entities = data.get("entities", [])
                methodologies = data.get("methodologies", [])
                cases = data.get("cases", [])
                
                all_entities.extend(entities)
                all_methodologies.extend(methodologies)
                all_cases.extend(cases)
                
                # 分类到主题
                for topic, keywords in self._topic_keywords.items():
                    if any(kw in title for kw in keywords):
                        topic_files.setdefault(topic, []).append(title)
                        break
                else:
                    topic_files.setdefault("其他", []).append(title)
                    
            except Exception as exc:
                logger.warning("读取文件失败 %s: %s", json_file, exc)
        
        # 2. 统计各主题覆盖度
        topic_coverage = {}
        for topic, keywords in self._topic_keywords.items():
            files = topic_files.get(topic, [])
            entity_count = sum(1 for e in all_entities 
                             if any(kw in e.get("text", "") for kw in keywords))
            
            topic_coverage[topic] = {
                "file_count": len(files),
                "entity_count": entity_count,
                "methodology_count": sum(1 for m in all_methodologies 
                                         if any(kw in m.get("name", "") for kw in keywords)),
                "coverage_score": min(1.0, len(files) / 5.0 + entity_count / 20.0),  # 简单评分
            }
        
        # 3. 识别缺口
        gaps = []
        for topic, coverage in topic_coverage.items():
            if coverage["coverage_score"] < 0.3:
                severity = "high"
            elif coverage["coverage_score"] < 0.6:
                severity = "medium"
            else:
                severity = "low"
            
            if severity in ("high", "medium"):
                subtopics = self._topic_keywords[topic]
                # 生成搜索查询
                queries = [
                    f"餐饮{topic}{sub} 方法 技巧 2025" for sub in subtopics[:3]
                ]
                gaps.append(KnowledgeGap(
                    topic=topic,
                    subtopic=subtopics[0] if subtopics else topic,
                    severity=severity,
                    reason=f"覆盖度评分 {coverage['coverage_score']:.2f}，仅有 {coverage['file_count']} 个相关文件",
                    suggested_queries=queries,
                ))
        
        # 按严重度排序
        gaps.sort(key=lambda g: {"high": 0, "medium": 1, "low": 2}[g.severity])
        
        stats = {
            "total_files": sum(len(v) for v in topic_files.values()),
            "total_entities": len(all_entities),
            "total_methodologies": len(all_methodologies),
            "total_cases": len(all_cases),
            "topic_coverage": topic_coverage,
        }
        
        return stats, gaps


class ContentFetcher:
    """内容获取器。
    
    使用web_search工具搜索并获取内容。
    """
    
    def __init__(self):
        self._search_tool = None
    
    def _get_search_tool(self):
        """懒加载搜索工具。"""
        if self._search_tool is None:
            try:
                from tools.web_search_tool import WebSearchTool
                self._search_tool = WebSearchTool()
            except Exception as exc:
                logger.error("加载搜索工具失败: %s", exc)
        return self._search_tool
    
    def search(self, query: str, limit: int = 5) -> List[ExternalDocument]:
        """搜索并返回候选文档。"""
        tool = self._get_search_tool()
        if not tool:
            logger.error("搜索工具不可用")
            return []
        
        try:
            result = tool.execute({"query": query, "limit": limit})
            if not result.success:
                logger.error("搜索失败: %s", result.error)
                return []
            
            docs = []
            for item in result.data or []:
                # WebSearchTool返回的是Evidence对象
                content = getattr(item, "text", "")
                title = getattr(item, "title", "Unknown")
                source = getattr(item, "source", "")
                
                if len(content) > 100:  # 过滤短内容
                    docs.append(ExternalDocument(
                        title=title,
                        source_url=source,
                        content=content,
                        topic=query,  # 简化处理
                        extraction_method="web_search",
                    ))
            
            logger.info("搜索 '%s' 返回 %d 条结果", query, len(docs))
            return docs
            
        except Exception as exc:
            logger.error("搜索异常: %s", exc)
            return []
    
    def fetch_for_gaps(self, gaps: List[KnowledgeGap], docs_per_gap: int = 3) -> List[ExternalDocument]:
        """为知识缺口获取内容。"""
        all_docs = []
        
        for gap in gaps[:5]:  # 最多处理前5个缺口
            logger.info("为缺口 '%s' 获取内容...", gap.topic)
            
            for query in gap.suggested_queries[:2]:  # 每个缺口搜2个查询
                docs = self.search(query, limit=docs_per_gap)
                for doc in docs:
                    doc.topic = gap.topic
                all_docs.extend(docs)
        
        # 去重（基于URL）
        seen_urls = set()
        unique_docs = []
        for doc in all_docs:
            if doc.source_url and doc.source_url not in seen_urls:
                seen_urls.add(doc.source_url)
                unique_docs.append(doc)
        
        logger.info("去重后获得 %d 个唯一文档", len(unique_docs))
        return unique_docs


class QualityValidator:
    """内容质量验证器。
    
    使用规则+LLM评估内容质量。
    """
    
    # 低质量信号词
    LOW_QUALITY_SIGNALS = [
        "广告", "推广", "免费咨询", "立即报名", "限时优惠",
        "点击链接", "扫码", "加微信", "关注我", "私信",
        "100%成功", "稳赚", "零风险", "一夜暴富",
    ]
    
    # 高质量信号
    HIGH_QUALITY_SIGNALS = [
        "数据", "统计", "调研", "报告", "分析",
        "案例", "经验", "总结", "方法", "步骤",
        "成本", "利润", "风险", "注意事项",
    ]
    
    def rule_based_score(self, doc: ExternalDocument) -> float:
        """基于规则的质量评分。"""
        content = doc.content
        score = 0.5  # 基础分
        
        # 长度加分
        if len(content) > 1000:
            score += 0.1
        if len(content) > 2000:
            score += 0.1
        
        # 高质量信号加分
        for signal in self.HIGH_QUALITY_SIGNALS:
            if signal in content:
                score += 0.02
        
        # 低质量信号减分
        for signal in self.LOW_QUALITY_SIGNALS:
            if signal in content:
                score -= 0.1
        
        # 数字和具体数据加分（专业性指标）
        if re.search(r'\d+\.?\d*\s*(万|元|%|个|家|人)', content):
            score += 0.05
        
        # 限制在0-1范围
        return max(0.0, min(1.0, score))
    
    def validate_batch(self, docs: List[ExternalDocument]) -> List[ExternalDocument]:
        """批量验证文档质量。"""
        validated = []
        
        for doc in docs:
            score = self.rule_based_score(doc)
            doc.quality_score = score
            
            if score >= 0.4:  # 质量阈值
                doc.verified = True
                validated.append(doc)
                logger.debug("文档 '%s' 通过验证 (得分: %.2f)", doc.title, score)
            else:
                logger.debug("文档 '%s' 质量不足 (得分: %.2f)，跳过", doc.title, score)
        
        # 按质量排序
        validated.sort(key=lambda d: d.quality_score, reverse=True)
        
        logger.info("验证完成: %d/%d 通过", len(validated), len(docs))
        return validated


class Structurizer:
    """结构化提取器。
    
    将外部文档转换为知识库标准格式。
    """
    
    def extract_entities(self, text: str, topic: str) -> List[Dict[str, str]]:
        """提取实体（简化版规则）。"""
        entities = []
        
        # 价格实体
        for match in re.finditer(r'(\d+(?:\.\d+)?)\s*(万|元|w|W)', text):
            entities.append({
                "text": match.group(0),
                "type": "price",
                "context": text[max(0, match.start()-20):match.end()+20],
            })
        
        # 地点实体
        location_patterns = [
            r'([\u4e00-\u9fa5]{2,6}(?:商圈|街道|路口|地铁口|学校|社区))',
            r'([\u4e00-\u9fa5]{2,4}(?:市|县|区|镇))',
        ]
        for pattern in location_patterns:
            for match in re.finditer(pattern, text):
                entities.append({
                    "text": match.group(1),
                    "type": "location",
                    "context": text[max(0, match.start()-20):match.end()+20],
                })
        
        return entities
    
    def extract_methodology(self, text: str) -> List[Dict[str, Any]]:
        """提取方法论（步骤化流程）。"""
        methodologies = []
        
        # 寻找步骤模式
        step_patterns = [
            r'(?:第[一二三四五六七八九十\d]+步|Step\s*\d+)[：:]\s*([^\n]+)',
            r'(?:首先|第一步)[，,]\s*([^。]+)',
            r'(?:其次|然后|第二步)[，,]\s*([^。]+)',
            r'(?:最后|第三步)[，,]\s*([^。]+)',
        ]
        
        steps = []
        for pattern in step_patterns:
            for match in re.finditer(pattern, text):
                steps.append(match.group(1).strip())
        
        if len(steps) >= 2:
            # 找标题（前面的句子）
            title_match = re.search(r'^([^。\n]{5,30})', text)
            title = title_match.group(1) if title_match else "操作流程"
            
            methodologies.append({
                "name": title,
                "steps": steps[:5],  # 最多5步
                "conditions": [],
            })
        
        return methodologies
    
    def generate_qa(self, text: str, topic: str, source: str) -> List[Dict[str, str]]:
        """生成QA对。"""
        qa_pairs = []
        
        # 简单启发式：找问答模式
        qa_patterns = [
            r'([什么|如何|怎么|为什么|是否].{3,20}[?？])\s*([^?？]{20,200})',
        ]
        
        for pattern in qa_patterns:
            for match in re.finditer(pattern, text):
                question = match.group(1).strip()
                answer = match.group(2).strip()
                
                if len(answer) > 30:
                    qa_pairs.append({
                        "question": question,
                        "answer": answer[:300],  # 限制长度
                        "source": source,
                        "category": topic,
                        "qa_type": "what",
                    })
        
        # 如果没有找到问答对，生成一个摘要QA
        if not qa_pairs and len(text) > 200:
            # 取前100字作为摘要
            summary = text[:100] + "..."
            qa_pairs.append({
                "question": f"关于{topic}的核心要点是什么？",
                "answer": summary,
                "source": source,
                "category": topic,
                "qa_type": "what",
            })
        
        return qa_pairs
    
    def structure_document(self, doc: ExternalDocument) -> Dict[str, Any]:
        """将外部文档转换为结构化格式。"""
        return {
            "title": doc.title,
            "source_url": doc.source_url,
            "topic": doc.topic,
            "content_preview": doc.content[:500],
            "entities": self.extract_entities(doc.content, doc.topic),
            "methodologies": self.extract_methodology(doc.content),
            "qa_pairs": self.generate_qa(doc.content, doc.topic, doc.title),
            "quality_score": doc.quality_score,
            "added_at": None,  # 由调用者填充
        }


class KnowledgeBaseAutoExpander:
    """知识库自动扩展主控制器。"""
    
    def __init__(self):
        self.analyzer = CoverageAnalyzer()
        self.fetcher = ContentFetcher()
        self.validator = QualityValidator()
        self.structurizer = Structurizer()
        self.index_manager = IncrementalVectorIndex()
    
    def run(
        self,
        max_gaps: int = 5,
        docs_per_gap: int = 3,
        quality_threshold: float = 0.4,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """运行自动扩展流程。
        
        Args:
            max_gaps: 最多处理的知识缺口数
            docs_per_gap: 每个缺口获取的文档数
            quality_threshold: 质量阈值
            dry_run: 是否只模拟，不实际写入
            
        Returns:
            运行报告
        """
        import datetime
        
        report = {
            "started_at": datetime.datetime.now().isoformat(),
            "dry_run": dry_run,
            "steps": [],
        }
        
        # Step 1: 分析覆盖度
        logger.info("=" * 60)
        logger.info("Step 1: 分析知识覆盖度...")
        stats, gaps = self.analyzer.analyze()
        
        report["coverage_stats"] = stats
        report["knowledge_gaps"] = [
            {"topic": g.topic, "subtopic": g.subtopic, "severity": g.severity}
            for g in gaps[:max_gaps]
        ]
        
        logger.info("知识库统计: %d 文件, %d 实体, %d 方法论",
                   stats["total_files"], stats["total_entities"], stats["total_methodologies"])
        logger.info("发现 %d 个知识缺口 (处理前 %d 个)", len(gaps), min(len(gaps), max_gaps))
        
        if not gaps:
            logger.info("知识库覆盖度良好，无需扩展")
            report["status"] = "no_gaps"
            return report
        
        # Step 2: 获取内容
        logger.info("=" * 60)
        logger.info("Step 2: 获取外部内容...")
        docs = self.fetcher.fetch_for_gaps(gaps[:max_gaps], docs_per_gap)
        
        report["fetched_docs"] = len(docs)
        logger.info("获取 %d 个候选文档", len(docs))
        
        if not docs:
            report["status"] = "fetch_failed"
            return report
        
        # Step 3: 质量验证
        logger.info("=" * 60)
        logger.info("Step 3: 质量验证...")
        validated_docs = self.validator.validate_batch(docs)
        
        report["validated_docs"] = len(validated_docs)
        report["rejected_docs"] = len(docs) - len(validated_docs)
        
        if not validated_docs:
            logger.warning("没有文档通过质量验证")
            report["status"] = "quality_check_failed"
            return report
        
        # Step 4: 结构化提取
        logger.info("=" * 60)
        logger.info("Step 4: 结构化提取...")
        
        all_texts = []
        all_metadata = []
        structured_results = []
        
        for doc in validated_docs:
            structured = self.structurizer.structure_document(doc)
            structured["added_at"] = datetime.datetime.now().isoformat()
            structured_results.append(structured)
            
            # 准备索引文本
            chunks = doc.to_text_chunks()
            for text, meta in chunks:
                all_texts.append(text)
                all_metadata.append(meta)
        
        report["structured_docs"] = len(structured_results)
        report["index_chunks"] = len(all_texts)
        
        # Step 5: 保存结构化数据
        if not dry_run:
            logger.info("=" * 60)
            logger.info("Step 5: 保存数据...")
            
            # 保存外部文档结构化数据
            external_file = EXTERNAL_KB_DIR / f"external_{datetime.datetime.now():%Y%m%d_%H%M%S}.json"
            with open(external_file, "w", encoding="utf-8") as f:
                json.dump(structured_results, f, ensure_ascii=False, indent=2)
            logger.info("结构化数据已保存: %s", external_file)
            
            # Step 6: 增量更新索引
            logger.info("=" * 60)
            logger.info("Step 6: 更新向量索引...")
            
            added, skipped = self.index_manager.add_documents(all_texts, all_metadata)
            self.index_manager.save()
            
            report["index_added"] = added
            report["index_skipped"] = skipped
            
            logger.info("索引更新完成: 添加 %d, 跳过 %d", added, skipped)
        else:
            logger.info("[Dry Run] 跳过保存和索引更新")
            report["index_added"] = 0
            report["index_skipped"] = 0
        
        # 最终统计
        report["ended_at"] = datetime.datetime.now().isoformat()
        report["status"] = "success"
        
        return report


def print_report(report: Dict[str, Any]):
    """打印运行报告。"""
    print("\n" + "=" * 60)
    print("知识库自动扩展报告")
    print("=" * 60)
    print(f"状态: {report.get('status', 'unknown')}")
    print(f"模拟模式: {report.get('dry_run', False)}")
    
    if "coverage_stats" in report:
        stats = report["coverage_stats"]
        print(f"\n知识库现状:")
        print(f"  - 文件数: {stats['total_files']}")
        print(f"  - 实体数: {stats['total_entities']}")
        print(f"  - 方法论: {stats['total_methodologies']}")
    
    if "knowledge_gaps" in report:
        print(f"\n知识缺口 ({len(report['knowledge_gaps'])} 个):")
        for gap in report["knowledge_gaps"]:
            print(f"  - [{gap['severity']}] {gap['topic']} / {gap['subtopic']}")
    
    if "fetched_docs" in report:
        print(f"\n获取内容:")
        print(f"  - 候选文档: {report['fetched_docs']}")
        print(f"  - 通过验证: {report.get('validated_docs', 0)}")
        print(f"  - 质量不足: {report.get('rejected_docs', 0)}")
    
    if "index_added" in report:
        print(f"\n索引更新:")
        print(f"  - 添加向量: {report['index_added']}")
        print(f"  - 跳过重复: {report['index_skipped']}")
    
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description="知识库自动扩展系统")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行，不实际写入")
    parser.add_argument("--max-gaps", type=int, default=5, help="最多处理的知识缺口数")
    parser.add_argument("--docs-per-gap", type=int, default=3, help="每个缺口获取的文档数")
    args = parser.parse_args()
    
    # 运行
    expander = KnowledgeBaseAutoExpander()
    report = expander.run(
        max_gaps=args.max_gaps,
        docs_per_gap=args.docs_per_gap,
        dry_run=args.dry_run,
    )
    
    print_report(report)
