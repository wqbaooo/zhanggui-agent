#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库增强系统：视频结构化提取 + QA对生成 + 向量化索引。

处理流程：
1. 读取视频转写JSON
2. 结构化提取（实体/关系/方法论/案例）
3. 生成QA对
4. 文本向量化（sentence-transformers）
5. 构建Faiss索引
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

import numpy as np

logger = logging.getLogger(__name__)

# ============ 配置 ============
VIDEO_KB_DIR = Path("knowledge_base/video_knowledge")
STRUCTURED_DIR = Path("knowledge_base/structured")
VECTOR_DIR = Path("knowledge_base/vector_store")
QA_FILE = Path("knowledge_base/qa_pairs.json")

STRUCTURED_DIR.mkdir(exist_ok=True)
VECTOR_DIR.mkdir(exist_ok=True)


# ============ 数据模型 ============

@dataclass
class Entity:
    """实体：地点、价格、流程、方法论、风险点等。"""
    text: str
    type: str  # location / price / process / method / risk / brand / category / tool
    start: int = 0
    end: int = 0
    context: str = ""


@dataclass
class Relation:
    """关系：实体之间的关系。"""
    source: str
    relation: str  # applies_to / requires / leads_to / depends_on / conflicts_with
    target: str
    context: str = ""


@dataclass
class Methodology:
    """方法论：步骤化的操作流程。"""
    name: str
    steps: List[str]
    conditions: List[str]  # 适用条件
    context: str = ""


@dataclass
class Case:
    """案例：背景→决策→结果→经验教训。"""
    title: str
    background: str
    decision: str
    result: str
    lesson: str
    context: str = ""


@dataclass
class StructuredVideo:
    """结构化后的视频知识。"""
    title: str
    category: str
    transcript: str
    entities: List[Entity] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)
    methodologies: List[Methodology] = field(default_factory=list)
    cases: List[Case] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)  # 关键要点
    actionable_tips: List[str] = field(default_factory=list)  # 行动建议


@dataclass
class QAPair:
    """问答对。"""
    question: str
    answer: str
    source: str  # 视频标题
    category: str
    evidence: str  # 原文引用
    qa_type: str  # what / how / why / when / where


# ============ 提取规则 ============

# 实体提取模式（规则版）
ENTITY_PATTERNS = {
    "location": [
        r"([\u4e00-\u9fa5]{2,6}(?:商圈|街道|路口|地铁口|学校|社区|写字楼|医院|菜场|商场))",
        r"(县城|乡镇|市区|郊区|开发区|工业区)",
    ],
    "price": [
        r"(\d+(?:\.\d+)?\s*(?:万|元|w|W))",
        r"(\d+(?:\.\d+)?%)",
        r"(毛利率|净利润率|租金营收比)[^\d]*(\d+(?:\.\d+)?)",
    ],
    "process": [
        r"(?:第[一二三四五六七八九十]步|第一步|首先|然后|接着|最后|接下来)",
        r"(?:流程|步骤|环节|顺序)",
    ],
    "method": [
        r"([\u4e00-\u9fa5]{2,8}(?:法|模型|原则|法则|策略|技巧|方法论))",
        r"(360度|人-流-场|金角银边|蹲点|竞品分析)",
    ],
    "risk": [
        r"(?:风险|坑|陷阱|问题|隐患|注意|警惕|避免|千万不要)",
        r"(?:骗局|套路|虚假宣传|合同陷阱)",
    ],
    "brand": [
        r"(蜜雪冰城|喜茶|奈雪|瑞幸|星巴克|肯德基|麦当劳|华莱士|正新鸡排|绝味鸭脖)",
    ],
    "category": [
        r"(早餐店|粉面馆|小吃店|奶茶店|快餐店|火锅店|烧烤店|烘焙店)",
        r"(包子|豆浆|米粉|螺蛳粉|麻辣烫|炸鸡|奶茶|咖啡)",
    ],
}


def extract_entities(text: str) -> List[Entity]:
    """从文本中提取实体。"""
    entities = []
    seen = set()
    
    for entity_type, patterns in ENTITY_PATTERNS.items():
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                entity_text = match.group(0)
                if entity_text not in seen and len(entity_text) >= 2:
                    seen.add(entity_text)
                    # 获取上下文
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    context = text[start:end]
                    
                    entities.append(Entity(
                        text=entity_text,
                        type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        context=context,
                    ))
    
    return entities


def extract_methodology(text: str) -> List[Methodology]:
    """提取方法论（步骤化流程）。"""
    methodologies = []
    
    # 查找"步骤"关键词附近的段落
    step_keywords = ["第一步", "第二步", "第三步", "第四步", "第五步", 
                     "第1步", "第2步", "第3步", "第4步", "第5步",
                     "首先", "然后", "接着", "最后", "接下来"]
    
    # 分段
    paragraphs = text.split("\n")
    
    for i, para in enumerate(paragraphs):
        if any(kw in para for kw in ["步骤", "流程", "方法"]):
            # 提取后续包含步骤关键句的段落
            steps = []
            conditions = []
            
            for j in range(i, min(i + 10, len(paragraphs))):
                line = paragraphs[j].strip()
                if any(kw in line for kw in step_keywords):
                    steps.append(line)
                if "适用" in line or "条件" in line or "前提" in line:
                    conditions.append(line)
            
            if steps:
                # 提取方法论名称（通常是段落开头或标题）
                name = para[:50] if len(para) > 10 else "方法论"
                methodologies.append(Methodology(
                    name=name,
                    steps=steps[:8],  # 最多8步
                    conditions=conditions[:3],
                    context=para,
                ))
    
    return methodologies


def extract_cases(text: str) -> List[Case]:
    """提取案例（背景→决策→结果→经验教训）。"""
    cases = []
    
    # 案例关键词
    case_markers = ["案例", "例子", "比如", "像", "有个", "有一位", "早餐哥", "脸盆姐"]
    
    paragraphs = text.split("\n")
    
    for i, para in enumerate(paragraphs):
        if any(marker in para for marker in case_markers):
            # 提取案例段落（当前段+后续2段）
            context_parts = [para]
            for j in range(i + 1, min(i + 3, len(paragraphs))):
                context_parts.append(paragraphs[j])
            
            context = "\n".join(context_parts)
            
            # 尝试提取结构
            background = para
            decision = ""
            result = ""
            lesson = ""
            
            for part in context_parts[1:]:
                if any(kw in part for kw in ["决定", "选择", "做了"]):
                    decision = part
                elif any(kw in part for kw in ["结果", "后来", "最后", "赚了", "亏了"]):
                    result = part
                elif any(kw in part for kw in ["教训", "经验", "启示", "总结"]):
                    lesson = part
            
            title = para[:40] if len(para) > 10 else "案例"
            cases.append(Case(
                title=title,
                background=background,
                decision=decision,
                result=result,
                lesson=lesson,
                context=context,
            ))
    
    return cases


def extract_key_points(text: str) -> List[str]:
    """提取关键要点。"""
    points = []
    
    # 关键句模式
    key_patterns = [
        r"(?:关键|核心|重点|本质|根本)[^\n]*?(?:是|在于|就是)[^\n]+",
        r"(?:必须|一定|要|不要|千万别)[^\n]+",
        r"(?:记住|牢记|注意|警惕)[^\n]+",
        r"(?:公式|计算方法|等于)[^\n]+",
    ]
    
    for pattern in key_patterns:
        for match in re.finditer(pattern, text):
            point = match.group(0).strip()
            if len(point) > 10 and len(point) < 200 and point not in points:
                points.append(point)
    
    return points[:10]


def generate_qa_pairs(title: str, category: str, text: str, entities: List[Entity], 
                     methodologies: List[Methodology], cases: List[Case]) -> List[QAPair]:
    """生成问答对。"""
    qa_pairs = []
    
    # 基于实体生成What/How/Why问题
    for entity in entities[:3]:
        if entity.type == "method":
            qa_pairs.append(QAPair(
                question=f"什么是{entity.text}？",
                answer=entity.context[:200],
                source=title,
                category=category,
                evidence=entity.text,
                qa_type="what",
            ))
        elif entity.type == "price":
            qa_pairs.append(QAPair(
                question=f"{title}中提到了什么价格/成本？",
                answer=entity.context[:200],
                source=title,
                category=category,
                evidence=entity.text,
                qa_type="what",
            ))
        elif entity.type == "location":
            qa_pairs.append(QAPair(
                question=f"{title}中提到了哪些选址要点？",
                answer=entity.context[:200],
                source=title,
                category=category,
                evidence=entity.text,
                qa_type="where",
            ))
    
    # 基于方法论生成How问题
    for method in methodologies[:2]:
        steps_text = "；".join(method.steps[:3])
        qa_pairs.append(QAPair(
            question=f"如何{method.name[:20]}？",
            answer=f"步骤：{steps_text}",
            source=title,
            category=category,
            evidence=method.context[:200],
            qa_type="how",
        ))
    
    # 基于案例生成What/Why问题
    for case in cases[:1]:
        if case.background:
            qa_pairs.append(QAPair(
                question=f"{title}中有什么案例？",
                answer=case.background[:200],
                source=title,
                category=category,
                evidence=case.context[:200],
                qa_type="what",
            ))
        if case.lesson:
            qa_pairs.append(QAPair(
                question=f"从这个案例中可以学到什么？",
                answer=case.lesson[:200],
                source=title,
                category=category,
                evidence=case.lesson,
                qa_type="why",
            ))
    
    # 生成通用问题
    qa_pairs.append(QAPair(
        question=f"{title}的核心内容是什么？",
        answer=text[:300],
        source=title,
        category=category,
        evidence=text[:100],
        qa_type="what",
    ))
    
    return qa_pairs[:5]


# ============ 主处理流程 ============

def process_video_json(json_path: Path) -> Optional[Tuple[StructuredVideo, List[QAPair]]]:
    """处理单个视频JSON文件。"""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        
        video_info = data.get("video_info", {})
        title = video_info.get("title", json_path.stem)
        category = video_info.get("category", "其他")
        
        # 获取转写文本
        transcript_data = data.get("transcript", {})
        if not transcript_data:
            return None
        
        text = transcript_data.get("text", "")
        if not text or len(text) < 100:
            return None
        
        # 结构化提取
        entities = extract_entities(text)
        methodologies = extract_methodology(text)
        cases = extract_cases(text)
        key_points = extract_key_points(text)
        
        # 生成行动建议
        actionable_tips = [p for p in key_points if any(kw in p for kw in ["要", "不要", "必须", "建议"])]
        
        structured = StructuredVideo(
            title=title,
            category=category,
            transcript=text,
            entities=entities,
            methodologies=methodologies,
            cases=cases,
            key_points=key_points,
            actionable_tips=actionable_tips,
        )
        
        # 生成QA对
        qa_pairs = generate_qa_pairs(title, category, text, entities, methodologies, cases)
        
        return structured, qa_pairs
    
    except Exception as exc:
        logger.error("处理文件失败 %s: %s", json_path, exc)
        return None


def main():
    """主函数：批量处理所有视频。"""
    print("=" * 60)
    print("知识库增强系统")
    print("视频结构化提取 + QA对生成 + 向量化索引")
    print("=" * 60)
    
    # 扫描所有视频JSON
    video_jsons = list(VIDEO_KB_DIR.glob("**/*.json"))
    video_jsons = [p for p in video_jsons if p.name not in 
                   {"master_knowledge_base.json", "transcription_status.json"}]
    
    print(f"\n找到 {len(video_jsons)} 个视频JSON文件")
    
    all_structured = []
    all_qa_pairs = []
    processed = 0
    skipped = 0
    
    for i, json_path in enumerate(video_jsons, 1):
        if i % 20 == 0:
            print(f"  进度: {i}/{len(video_jsons)} (成功:{processed}, 跳过:{skipped})")
        
        result = process_video_json(json_path)
        if result:
            structured, qa_pairs = result
            all_structured.append(structured)
            all_qa_pairs.extend(qa_pairs)
            processed += 1
            
            # 保存结构化结果
            output_path = STRUCTURED_DIR / f"{json_path.stem}_structured.json"
            output_path.write_text(
                json.dumps({
                    "title": structured.title,
                    "category": structured.category,
                    "entities": [{"text": e.text, "type": e.type} for e in structured.entities],
                    "methodologies": [{"name": m.name, "steps": m.steps} for m in structured.methodologies],
                    "cases": [{"title": c.title, "lesson": c.lesson} for c in structured.cases],
                    "key_points": structured.key_points,
                    "actionable_tips": structured.actionable_tips,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            skipped += 1
    
    print(f"\n处理完成: 成功 {processed}, 跳过 {skipped}")
    print(f"提取实体: {sum(len(s.entities) for s in all_structured)} 个")
    print(f"提取方法论: {sum(len(s.methodologies) for s in all_structured)} 个")
    print(f"提取案例: {sum(len(s.cases) for s in all_structured)} 个")
    print(f"生成QA对: {len(all_qa_pairs)} 个")
    
    # 保存QA对
    QA_FILE.write_text(
        json.dumps([
            {"question": q.question, "answer": q.answer, "source": q.source, 
             "category": q.category, "qa_type": q.qa_type}
            for q in all_qa_pairs
        ], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nQA对已保存: {QA_FILE}")
    
    # 构建向量化索引
    print("\n" + "=" * 60)
    print("构建向量化索引...")
    build_vector_index(all_structured, all_qa_pairs)
    
    print("\n" + "=" * 60)
    print("知识库增强完成！")
    print("=" * 60)


def build_vector_index(structured_videos: List[StructuredVideo], qa_pairs: List[QAPair]):
    """构建Faiss向量化索引。"""
    from sentence_transformers import SentenceTransformer
    import faiss
    
    # 加载模型
    print("  加载向量化模型...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    # 准备文本
    texts = []
    metadata = []
    
    # 1. 视频关键要点
    for sv in structured_videos:
        for kp in sv.key_points[:3]:
            texts.append(kp)
            metadata.append({"type": "key_point", "source": sv.title, "category": sv.category})
        
        for tip in sv.actionable_tips[:2]:
            texts.append(tip)
            metadata.append({"type": "tip", "source": sv.title, "category": sv.category})
        
        # 方法论步骤
        for method in sv.methodologies:
            method_text = f"{method.name}: {'；'.join(method.steps[:3])}"
            texts.append(method_text)
            metadata.append({"type": "methodology", "source": sv.title, "category": sv.category})
        
        # 案例教训
        for case in sv.cases:
            if case.lesson:
                texts.append(case.lesson)
                metadata.append({"type": "case", "source": sv.title, "category": sv.category})
    
    # 2. QA对
    for qa in qa_pairs:
        qa_text = f"Q: {qa.question}\nA: {qa.answer}"
        texts.append(qa_text)
        metadata.append({"type": "qa", "source": qa.source, "category": qa.category})
    
    print(f"  索引文本数量: {len(texts)}")
    
    # 向量化
    print("  向量化文本...")
    embeddings = model.encode(texts, show_progress_bar=True)
    embeddings = np.array(embeddings).astype("float32")
    
    # 构建Faiss索引
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)  # 内积索引（余弦相似度）
    
    # 归一化（用于余弦相似度）
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    
    # 保存索引
    faiss.write_index(index, str(VECTOR_DIR / "index.faiss"))
    
    # 保存元数据
    with open(VECTOR_DIR / "metadata.json", "w", encoding="utf-8") as f:
        json.dump({"texts": texts, "metadata": metadata}, f, ensure_ascii=False, indent=2)
    
    # 保存模型信息
    with open(VECTOR_DIR / "config.json", "w", encoding="utf-8") as f:
        json.dump({
            "model": "paraphrase-multilingual-MiniLM-L12-v2",
            "dimension": dimension,
            "num_vectors": len(texts),
            "metric": "cosine",
        }, f, indent=2)
    
    print(f"  索引已保存: {VECTOR_DIR}/index.faiss")
    print(f"  维度: {dimension}, 向量数: {len(texts)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()
