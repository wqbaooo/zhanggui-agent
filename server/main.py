#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI 应用入口 — 开店 Agent 产品化后端。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.routes import chat, audit, finance, projects

try:
    from v2.routes import router as v2_router
    _v2_available = True
except ImportError:
    _v2_available = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("开店 Agent 后端启动")
    yield
    logger.info("开店 Agent 后端关闭")


app = FastAPI(
    title="开店 Agent API",
    description="餐饮开店智能顾问 — LangGraph/ReAct 后端服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(finance.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
if _v2_available:
    app.include_router(v2_router)


@app.get("/")
async def root():
    return {
        "service": "开店 Agent API",
        "status": "ok",
        "message": "这是后端 API 服务，不是前端页面。请打开前端地址 http://127.0.0.1:3001/",
        "frontend_url": "http://127.0.0.1:3001/",
        "health_url": "http://127.0.0.1:8000/health",
        "docs_url": "http://127.0.0.1:8000/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "store-agent"}
