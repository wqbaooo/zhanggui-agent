#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Markdown、文档入库结果、视频知识结果构建统一 RAG 索引。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rag_engine import DEFAULT_INDEX_PATH, RagChunk, RagIndex, chunk_text  # noqa: E402


def markdown_chunks(path: Path) -> List[Tuple[str, str]]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    chunks: List[Tuple[str, str]] = []
    sections = re.split(r"^##\s+", content, flags=re.MULTILINE)
    for section in sections[1:]:
        lines = section.strip().splitlines()
        if not lines:
            continue
        section_title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        subsections = re.split(r"^###\s+", body, flags=re.MULTILINE)
        if len(subsections) == 1:
            chunks.append((section_title, body))
            continue
        for subsection in subsections[1:]:
            sub_lines = subsection.strip().splitlines()
            if sub_lines:
                chunks.append((f"{section_title} / {sub_lines[0].strip()}", "\n".join(sub_lines[1:]).strip()))
    return chunks


def add_markdown(index: RagIndex, path: Path):
    for i, (title, text) in enumerate(markdown_chunks(path), 1):
        for j, part in enumerate(chunk_text(text), 1):
            index.add(
                RagChunk(
                    id=f"md:{path.name}:{i}:{j}",
                    source_type="core_markdown",
                    source_path=str(path),
                    title=title,
                    text=part,
                    metadata={"section": i, "chunk": j},
                )
            )


def add_documents(index: RagIndex, document_dir: Path):
    if not document_dir.exists():
        return
    for file_path in sorted(document_dir.glob("*.json")):
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        source = payload.get("source", str(file_path))
        for item in payload.get("chunks", []):
            status = item.get("status", payload.get("status", "usable"))
            index.add(
                RagChunk(
                    id=f"doc:{file_path.stem}:{item.get('page')}:{item.get('chunk')}",
                    source_type="document",
                    source_path=source,
                    title=item.get("title", file_path.stem),
                    text=item.get("text", ""),
                    metadata={"page": item.get("page"), "chunk": item.get("chunk"), "ingested_file": str(file_path)},
                    status=status,
                )
            )


def video_text(data: Dict[str, Any], file_path: Path) -> tuple[str, str, Dict[str, Any], str]:
    info = data.get("video_info", {})
    knowledge = data.get("knowledge", {})
    transcript = data.get("transcript")
    title = info.get("title") or knowledge.get("title") or file_path.stem
    
    # 提取并标准化标签
    raw_keywords = knowledge.get("keywords", [])
    category = info.get("category") or knowledge.get("category") or file_path.parent.name
    
    metadata = {
        "category": category,
        "video_path": info.get("path", ""),
        "topic_tags": raw_keywords, # 使用 topic_tags 作为检索加权依据
        "source_type": "video_transcript" if transcript else "video_index"
    }
    
    if transcript:
        text = transcript.get("text", "") if isinstance(transcript, dict) else str(transcript)
        summary = knowledge.get("summary", "")
        # 将摘要放在最前面，提高检索权重
        text = f"【课程摘要】{summary}\n\n【详细内容】{text}".strip()
        return title, text, metadata, "usable"
    
    text = "\n".join(
        [
            f"课程标题：{title}",
            f"分类：{category}",
            f"核心知识点：{', '.join(raw_keywords)}",
            "注意：该视频尚未完成语音转写，目前仅能作为课程目录线索。",
        ]
    )
    return title, text, metadata, "title_index_only"


def add_videos(index: RagIndex, video_dir: Path):
    if not video_dir.exists():
        return
    
    # 定义需要排除的分类（如纯制作类）
    excluded_categories = {"小吃制作", "拍摄剪辑"}
    
    for file_path in sorted(video_dir.glob("**/*.json")):
        if file_path.name == "master_knowledge_base.json":
            continue
        
        # 检查文件路径是否包含排除的分类
        if any(ex_cat in str(file_path) for ex_cat in excluded_categories):
            continue
            
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        title, text, metadata, status = video_text(data, file_path)
        for j, part in enumerate(chunk_text(text), 1):
            index.add(
                RagChunk(
                    id=f"video:{file_path.parent.name}:{file_path.stem}:{j}",
                    source_type="video",
                    source_path=str(file_path),
                    title=title,
                    text=part,
                    metadata={**metadata, "chunk": j},
                    status=status,
                )
            )


def build_index(output: Path = DEFAULT_INDEX_PATH) -> RagIndex:
    index = RagIndex()
    add_markdown(index, PROJECT_ROOT / "knowledge_base" / "开店Agent知识库.md")
    add_documents(index, PROJECT_ROOT / "knowledge_base" / "document_knowledge")
    add_videos(index, PROJECT_ROOT / "knowledge_base" / "video_knowledge")
    index.save(output)
    return index


def main():
    parser = argparse.ArgumentParser(description="构建统一 RAG 索引")
    parser.add_argument("--output", default=str(DEFAULT_INDEX_PATH), help="索引输出路径")
    args = parser.parse_args()
    index = build_index(Path(args.output))
    print(json.dumps(index.audit(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
