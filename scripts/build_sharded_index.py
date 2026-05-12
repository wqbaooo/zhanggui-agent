#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将统一向量索引按 category 分片，生成阶段级索引。

运行前提: pip install faiss-cpu sentence-transformers numpy
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, List

import faiss
import numpy as np


def load_index(vector_dir: Path):
    """加载现有索引和元数据。"""
    index = faiss.read_index(str(vector_dir / "index.faiss"))
    with open(vector_dir / "metadata.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return index, data["texts"], data["metadata"]


def build_sharded_indices(vector_dir: Path, output_dir: Path):
    """按 category 分片生成独立 Faiss 索引。"""
    index, texts, metadata = load_index(vector_dir)

    # 按 category 分组
    groups: Dict[str, List[int]] = {}
    for idx, meta in enumerate(metadata):
        cat = meta.get("category", "other")
        groups.setdefault(cat, []).append(idx)

    # 导出全量向量（避免重复 reconstruct）
    vectors = index.reconstruct_n(0, index.ntotal)

    output_dir.mkdir(parents=True, exist_ok=True)

    for cat, indices in groups.items():
        cat_vectors = np.array([vectors[i] for i in indices], dtype="float32")
        cat_texts = [texts[i] for i in indices]
        cat_metadata = [metadata[i] for i in indices]

        # 创建独立索引
        dim = cat_vectors.shape[1]
        shard_index = faiss.IndexFlatIP(dim)  # 内积 = cosine（已归一化）
        shard_index.add(cat_vectors)

        cat_dir = output_dir / cat
        cat_dir.mkdir(exist_ok=True)
        faiss.write_index(shard_index, str(cat_dir / "index.faiss"))

        with open(cat_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump({"texts": cat_texts, "metadata": cat_metadata}, f, ensure_ascii=False, indent=2)

        with open(cat_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump({
                "model": "paraphrase-multilingual-MiniLM-L12-v2",
                "dimension": dim,
                "num_vectors": len(indices),
                "metric": "cosine"
            }, f, ensure_ascii=False, indent=2)

        print(f"  {cat}: {len(indices)} 条 → {cat_dir}")

    # 复制全局索引作为 fallback
    global_dir = output_dir / "global"
    global_dir.mkdir(exist_ok=True)
    shutil.copy(vector_dir / "index.faiss", global_dir / "index.faiss")
    shutil.copy(vector_dir / "metadata.json", global_dir / "metadata.json")
    shutil.copy(vector_dir / "config.json", global_dir / "config.json")
    print(f"  global: {len(texts)} 条 → {global_dir} (fallback)")
    print(f"\n分片完成，输出目录: {output_dir}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="构建分片向量索引")
    parser.add_argument("--input", "-i", default="knowledge_base/vector_store", help="输入向量目录")
    parser.add_argument("--output", "-o", default="knowledge_base/vector_store_sharded", help="输出分片目录")
    args = parser.parse_args()

    build_sharded_indices(Path(args.input), Path(args.output))
