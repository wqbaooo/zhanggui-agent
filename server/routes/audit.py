#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计路由 — GET /api/audit。"""

from __future__ import annotations

from fastapi import APIRouter

from server.deps import get_agent

router = APIRouter(tags=["audit"])


@router.get("/audit")
async def audit_endpoint():
    """知识库审计端点。"""
    agent = get_agent()
    return agent.audit_sources()
