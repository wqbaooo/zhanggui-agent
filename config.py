#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全局配置：环境变量加载、路径常量、运行参数。"""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

# 知识库路径
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge_base"
DEFAULT_KB_PATH = KNOWLEDGE_BASE_DIR / "掌柜Agent知识库.md"
DEFAULT_VIDEO_KB_DIR = KNOWLEDGE_BASE_DIR / "video_knowledge"
DEFAULT_DOCUMENT_KB_DIR = KNOWLEDGE_BASE_DIR / "document_knowledge"
DEFAULT_RAG_INDEX_PATH = KNOWLEDGE_BASE_DIR / "rag_index.json"

# 项目数据持久化目录
PROJECT_DATA_DIR = PROJECT_ROOT / "project_data"

# 提示词模板目录
PROMPTS_DIR = PROJECT_ROOT / "prompts"


def load_env(path: Path = PROJECT_ROOT / ".env"):
    """从 .env 文件加载环境变量（不覆盖已有变量）。"""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


# 启动时自动加载
load_env()


# DeepSeek / LLM 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# 高德地图配置
AMAP_WEBSERVICE_KEY = os.getenv("AMAP_WEBSERVICE_KEY", "")
AMAP_REQUEST_INTERVAL = float(os.getenv("AMAP_REQUEST_INTERVAL", "0.35"))

# 联网搜索配置
SEARCH_BACKEND = os.getenv("SEARCH_BACKEND", "auto")  # auto | duckduckgo | serper | tavily
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
