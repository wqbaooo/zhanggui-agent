#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SOP 文档库路由：标准作业流程的增删改查。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models.sop import SopDocument, SopLibrary
from server.schemas import SopCreate, SopUpdate

router = APIRouter(prefix="/projects", tags=["sops"])


def _library(project_id: str) -> SopLibrary:
    lib = SopLibrary.load(project_id)
    if lib is None:
        lib = SopLibrary.create(project_id)
    return lib


@router.get("/{project_id}/sops")
async def list_sops(
    project_id: str,
    category: Optional[str] = Query(None, description="按分类筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    stale: Optional[bool] = Query(None, description="只看过期待复核"),
):
    lib = _library(project_id)
    if keyword:
        docs = lib.search(keyword)
    elif stale:
        docs = lib.stale()
    elif status:
        docs = lib.by_status(status)
    elif category:
        docs = lib.by_category(category)
    else:
        docs = lib.documents
    return {"documents": docs, "summary": lib.categories_summary()}


@router.post("/{project_id}/sops")
async def create_sop(project_id: str, req: SopCreate):
    lib = _library(project_id)
    doc = SopDocument(
        category=req.category,
        title=req.title,
        status="草稿",
        source=req.source,
        description=req.description,
        steps=req.steps,
        related_sku_ids=req.related_sku_ids,
        related_training_skills=req.related_training_skills,
        review_cycle_days=req.review_cycle_days,
        notes=req.notes,
    )
    saved = lib.add(doc)
    return {"success": True, "document": saved.to_dict()}


@router.get("/{project_id}/sops/{sop_id}")
async def get_sop(project_id: str, sop_id: str):
    lib = _library(project_id)
    doc = lib.get(sop_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="sop not found")
    return {"document": doc}


@router.patch("/{project_id}/sops/{sop_id}")
async def update_sop(project_id: str, sop_id: str, req: SopUpdate):
    lib = _library(project_id)
    payload = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    updated = lib.update(sop_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="sop not found")
    return {"success": True, "document": updated}


@router.delete("/{project_id}/sops/{sop_id}")
async def delete_sop(project_id: str, sop_id: str):
    lib = _library(project_id)
    if not lib.delete(sop_id):
        raise HTTPException(status_code=404, detail="sop not found")
    return {"success": True}
