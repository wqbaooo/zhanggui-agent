#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库通用化重构脚本：弱化个人 IP，强化行业方法论标签。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIDEO_KB_DIR = PROJECT_ROOT / "knowledge_base" / "video_knowledge"
DOCUMENT_KB_DIR = PROJECT_ROOT / "knowledge_base" / "document_knowledge"

# IP 词汇映射表
IP_REPLACEMENTS = {
    "勇哥": "资深餐饮顾问",
    "勇哥说餐饮": "餐饮经营实战指南",
    "我建议": "建议",
    "我的经验是": "行业经验表明",
    "大家记住": "请注意",
    "听我的": "建议",
}

def normalize_text(text: str) -> str:
    """清洗文本中的个人 IP 表述。"""
    if not text:
        return text
    for old, new in IP_REPLACEMENTS.items():
        text = text.replace(old, new)
    return text

def process_video_json(file_path: Path):
    """处理单个视频知识 JSON 文件。"""
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return

    modified = False
    
    # 1. 标题通用化
    if "video_info" in data and "title" in data["video_info"]:
        old_title = data["video_info"]["title"]
        new_title = re.sub(r"勇哥|说餐饮|课程", "", old_title).strip()
        if new_title and new_title != old_title:
            data["video_info"]["title"] = new_title
            modified = True

    # 2. 摘要与转写内容清洗
    if "knowledge" in data and "summary" in data["knowledge"]:
        data["knowledge"]["summary"] = normalize_text(data["knowledge"]["summary"])
        modified = True
    
    if "transcript" in data and isinstance(data["transcript"], dict):
        if "text" in data["transcript"]:
            data["transcript"]["text"] = normalize_text(data["transcript"]["text"])
            modified = True

    if modified:
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ 已通用化处理: {file_path.name}")

def main():
    print("🚀 开始知识库通用化重构...")
    
    # 处理视频库
    for file_path in VIDEO_KB_DIR.glob("**/*.json"):
        if file_path.name in {"master_knowledge_base.json", "transcription_status.json"}:
            continue
        process_video_json(file_path)

    # 处理文档库
    for file_path in DOCUMENT_KB_DIR.glob("*.json"):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if "chunks" in data:
                for chunk in data["chunks"]:
                    if "text" in chunk:
                        chunk["text"] = normalize_text(chunk["text"])
                file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"✅ 已通用化处理文档: {file_path.name}")
        except Exception:
            continue

    print("✨ 重构完成！请运行 `python3 scripts/build_rag_index.py` 更新索引。")

if __name__ == "__main__":
    main()
