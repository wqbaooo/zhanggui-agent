#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门店资料箱路由：合同、证照、协议的归档与检索。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from models.document_box import DocumentBox, StoreDocument
from server.schemas import (
    DocumentCreate,
    DocumentUpdate,
    DocumentListResponse,
    DocumentResponse,
)

router = APIRouter(prefix="/projects", tags=["documents"])


def _box(project_id: str) -> DocumentBox:
    box = DocumentBox.load(project_id)
    if box is None:
        box = DocumentBox.create(project_id)
    return box


@router.get("/{project_id}/documents")
async def list_documents(
    project_id: str,
    doc_type: Optional[str] = Query(None, description="按文档类型筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    expiring_days: Optional[int] = Query(None, description="到期提醒，N 天内"),
):
    box = _box(project_id)
    if expiring_days is not None:
        docs = box.expiring_soon(days=expiring_days)
    elif keyword:
        docs = box.search(keyword)
    elif doc_type:
        docs = box.by_type(doc_type)
    else:
        docs = box.documents
    return {"documents": docs, "summary": box.summary()}


@router.post("/{project_id}/documents")
async def create_document(project_id: str, req: DocumentCreate):
    box = _box(project_id)
    doc = StoreDocument(
        title=req.title,
        doc_type=req.doc_type,
        tags=req.tags,
        source=req.source,
        file_ref=req.file_ref,
        status="原始",
        parties=req.parties,
        sign_date=req.sign_date or "",
        expiry_date=req.expiry_date or "",
        key_terms=req.key_terms,
        extracted_fields=req.extracted_fields,
        risk_flags=req.risk_flags,
        related_to=req.related_to,
        notes=req.notes,
    )
    saved = box.add(doc)
    return {"success": True, "document": saved.to_dict()}


@router.get("/{project_id}/documents/{document_id}")
async def get_document(project_id: str, document_id: str):
    box = _box(project_id)
    doc = box.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    return {"document": doc}


@router.patch("/{project_id}/documents/{document_id}")
async def update_document(project_id: str, document_id: str, req: DocumentUpdate):
    box = _box(project_id)
    payload = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    updated = box.update(document_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="document not found")
    return {"success": True, "document": updated}


@router.delete("/{project_id}/documents/{document_id}")
async def delete_document(project_id: str, document_id: str):
    box = _box(project_id)
    if not box.delete(document_id):
        raise HTTPException(status_code=404, detail="document not found")
    return {"success": True}
