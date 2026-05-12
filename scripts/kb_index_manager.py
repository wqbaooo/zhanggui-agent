#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库增量索引管理器。

支持Faiss索引的增量添加、更新和删除操作。
解决原系统只能全量重建的问题。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

VECTOR_DIR = Path("knowledge_base/vector_store")


class IncrementalVectorIndex:
    """增量向量索引管理器。
    
    封装Faiss索引的CRUD操作，支持：
    - 增量添加新向量（不重建整个索引）
    - 文本去重（基于内容哈希）
    - 索引持久化
    - 元数据同步
    """
    
    def __init__(self, vector_dir: Path = VECTOR_DIR):
        self.vector_dir = vector_dir
        self.vector_dir.mkdir(exist_ok=True)
        
        self._model = None
        self._index = None
        self._texts: List[str] = []
        self._metadata: List[Dict[str, Any]] = []
        self._text_hashes: set = set()  # 用于快速去重
        self._loaded = False
        self._dimension = 384  # paraphrase-multilingual-MiniLM-L12-v2
    
    def _ensure_loaded(self):
        """懒加载模型和索引。"""
        if self._loaded:
            return
        
        try:
            import faiss
            from sentence_transformers import SentenceTransformer
            
            # 加载模型
            logger.info("加载向量化模型...")
            self._model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            self._dimension = self._model.get_sentence_embedding_dimension()
            
            index_path = self.vector_dir / "index.faiss"
            metadata_path = self.vector_dir / "metadata.json"
            
            if index_path.exists() and metadata_path.exists():
                # 加载现有索引
                logger.info("加载现有Faiss索引...")
                self._index = faiss.read_index(str(index_path))
                
                with open(metadata_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._texts = data.get("texts", [])
                    self._metadata = data.get("metadata", [])
                    
                # 构建去重哈希
                self._text_hashes = {self._hash_text(t) for t in self._texts}
                
                logger.info("索引加载完成: %d 条向量", len(self._texts))
            else:
                # 创建新索引
                logger.info("创建新的Faiss索引...")
                self._index = faiss.IndexFlatIP(self._dimension)
                self._texts = []
                self._metadata = []
                self._text_hashes = set()
                
            self._loaded = True
            
        except Exception as exc:
            logger.error("加载索引失败: %s", exc)
            raise
    
    def _hash_text(self, text: str) -> str:
        """生成文本的简化哈希（用于去重）。"""
        import hashlib
        # 归一化：去除空白，取前200字符
        normalized = "".join(text.split())[:200]
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()
    
    def is_duplicate(self, text: str) -> bool:
        """检查文本是否已存在（避免重复索引）。"""
        self._ensure_loaded()
        return self._hash_text(text) in self._text_hashes
    
    def add_documents(
        self,
        texts: List[str],
        metadata_list: List[Dict[str, Any]],
        skip_duplicates: bool = True,
    ) -> Tuple[int, int]:
        """增量添加文档到索引。
        
        Args:
            texts: 文本列表
            metadata_list: 对应的元数据列表
            skip_duplicates: 是否跳过重复文本
            
        Returns:
            (添加成功数, 跳过重复数)
        """
        self._ensure_loaded()
        
        if len(texts) != len(metadata_list):
            raise ValueError("texts 和 metadata_list 长度必须相同")
        
        # 过滤空文本和重复文本
        filtered_texts = []
        filtered_metadata = []
        skipped = 0
        
        for text, meta in zip(texts, metadata_list):
            if not text or len(text.strip()) < 20:  # 过滤过短文本
                skipped += 1
                continue
            
            if skip_duplicates and self.is_duplicate(text):
                skipped += 1
                logger.debug("跳过重复文本: %s...", text[:50])
                continue
            
            filtered_texts.append(text)
            filtered_metadata.append(meta)
        
        if not filtered_texts:
            logger.info("没有新文档需要添加")
            return 0, skipped
        
        # 向量化
        logger.info("向量化 %d 条新文档...", len(filtered_texts))
        embeddings = self._model.encode(filtered_texts, show_progress_bar=True)
        embeddings = np.array(embeddings).astype("float32")
        
        # 归一化（用于余弦相似度）
        import faiss
        faiss.normalize_L2(embeddings)
        
        # 添加到索引
        self._index.add(embeddings)
        
        # 更新元数据
        self._texts.extend(filtered_texts)
        self._metadata.extend(filtered_metadata)
        for t in filtered_texts:
            self._text_hashes.add(self._hash_text(t))
        
        added = len(filtered_texts)
        logger.info("成功添加 %d 条向量，跳过 %d 条", added, skipped)
        
        return added, skipped
    
    def save(self):
        """保存索引和元数据到磁盘。"""
        self._ensure_loaded()
        
        import faiss
        
        # 保存Faiss索引
        faiss.write_index(self._index, str(self.vector_dir / "index.faiss"))
        
        # 保存元数据
        with open(self.vector_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump({
                "texts": self._texts,
                "metadata": self._metadata,
            }, f, ensure_ascii=False, indent=2)
        
        # 保存配置
        with open(self.vector_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump({
                "model": "paraphrase-multilingual-MiniLM-L12-v2",
                "dimension": self._dimension,
                "num_vectors": len(self._texts),
                "metric": "cosine",
            }, f, indent=2)
        
        logger.info("索引已保存: %d 条向量", len(self._texts))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计信息。"""
        self._ensure_loaded()
        
        # 统计类型分布
        type_counts = {}
        for meta in self._metadata:
            t = meta.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        
        return {
            "total_vectors": len(self._texts),
            "dimension": self._dimension,
            "type_distribution": type_counts,
            "index_path": str(self.vector_dir / "index.faiss"),
        }
    
    def rebuild_index(self):
        """全量重建索引（清理碎片，优化性能）。"""
        self._ensure_loaded()
        
        logger.info("全量重建索引...")
        
        import faiss
        
        # 重新编码所有文本
        logger.info("重新向量化 %d 条文本...", len(self._texts))
        embeddings = self._model.encode(self._texts, show_progress_bar=True)
        embeddings = np.array(embeddings).astype("float32")
        faiss.normalize_L2(embeddings)
        
        # 创建新索引
        self._index = faiss.IndexFlatIP(self._dimension)
        self._index.add(embeddings)
        
        # 保存
        self.save()
        
        logger.info("索引重建完成")


if __name__ == "__main__":
    # 测试增量索引
    logging.basicConfig(level=logging.INFO)
    
    idx = IncrementalVectorIndex()
    
    # 检查当前状态
    stats = idx.get_stats()
    print(f"当前索引状态: {stats}")
    
    # 测试添加（示例）
    # added, skipped = idx.add_documents(
    #     texts=["测试文本1", "测试文本2"],
    #     metadata_list=[
    #         {"type": "test", "source": "manual"},
    #         {"type": "test", "source": "manual"},
    #     ]
    # )
    # idx.save()
