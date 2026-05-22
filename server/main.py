#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI 应用入口 — 开店 Agent 产品化后端。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.routes import chat, audit, finance

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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(finance.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "store-agent"}
