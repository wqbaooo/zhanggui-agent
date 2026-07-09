#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI 应用入口 — 掌柜Agent 产品化后端。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.routes import analyze, chat, audit, documents, finance, labor, projects, capture, model_routing, operating_ledger, reports, skus, sops, speech, weather, amap

try:
    from v2.routes import router as v2_router
    _v2_available = True
except ImportError:
    _v2_available = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("掌柜Agent 后端启动")
    yield
    logger.info("掌柜Agent 后端关闭")


app = FastAPI(
    title="掌柜Agent API",
    description="新余恒太城大口章鱼烧 AI 单店经营 Agent 后端服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3005",
        "http://127.0.0.1:3005",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(finance.router, prefix="/api")  # deprecated: 筹备期口径残留
app.include_router(projects.router, prefix="/api")
app.include_router(operating_ledger.router, prefix="/api")
app.include_router(capture.router, prefix="/api")
app.include_router(speech.router, prefix="/api")
app.include_router(model_routing.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(skus.router, prefix="/api")
app.include_router(sops.router, prefix="/api")
app.include_router(labor.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(weather.router, prefix="")
app.include_router(amap.router, prefix="/api")
if _v2_available:
    app.include_router(v2_router)
    from v2.routes import alpha_router
    app.include_router(alpha_router)


@app.get("/")
async def root():
    return {
        "service": "掌柜Agent API",
        "status": "ok",
        "message": "这是后端 API 服务，不是前端页面。请打开前端地址 http://127.0.0.1:3005/overview",
        "frontend_url": "http://127.0.0.1:3005/overview",
        "health_url": "http://127.0.0.1:8000/health",
        "docs_url": "http://127.0.0.1:8000/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "store-agent"}
