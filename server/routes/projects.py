#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目档案与经营数据路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from models.project import ProjectMemory
from server.schemas import (
    ActionTaskCreate,
    ActionTaskUpdate,
    DailyOperationEntry,
    FranchiseConstraintsUpdate,
    IntegrationUpdate,
    OperationListResponse,
    ProjectProfileUpdate,
    SiteTransferUpdate,
)


router = APIRouter(prefix="/projects", tags=["projects"])


def _get_or_create_project(project_id: str) -> ProjectMemory:
    memory = ProjectMemory.load(project_id)
    if memory is None:
        memory = ProjectMemory.create(project_id)
    return memory


@router.get("/{project_id}")
async def get_project(project_id: str):
    """读取项目档案，不存在则创建空档案。"""
    memory = _get_or_create_project(project_id)
    return memory


@router.get("/{project_id}/cockpit")
async def get_project_cockpit(project_id: str, days: int = Query(7, ge=1, le=366)):
    """生命周期驾驶舱唯一数据入口。"""
    memory = _get_or_create_project(project_id)
    return memory.cockpit_summary(days=days)


@router.put("/{project_id}/profile")
async def update_project_profile(project_id: str, req: ProjectProfileUpdate):
    memory = _get_or_create_project(project_id)
    memory.update_profile(req.profile)
    return {"success": True, "project": memory}


@router.put("/{project_id}/franchise-constraints")
async def update_franchise_constraints(project_id: str, req: FranchiseConstraintsUpdate):
    memory = _get_or_create_project(project_id)
    memory.update_franchise_constraints(req.constraints)
    return {"success": True, "project": memory}


@router.put("/{project_id}/site-transfer")
async def update_site_transfer(project_id: str, req: SiteTransferUpdate):
    memory = _get_or_create_project(project_id)
    memory.update_site_transfer(req.site_transfer)
    return {"success": True, "project": memory}


@router.get("/{project_id}/tasks")
async def list_tasks(project_id: str):
    memory = _get_or_create_project(project_id)
    return {"tasks": memory.action_tasks}


@router.post("/{project_id}/tasks")
async def create_task(project_id: str, req: ActionTaskCreate):
    memory = _get_or_create_project(project_id)
    payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    task = memory.add_task(payload)
    return {"success": True, "task": task, "cockpit": memory.cockpit_summary(days=7)}


@router.patch("/{project_id}/tasks/{task_id}")
async def update_task(project_id: str, task_id: str, req: ActionTaskUpdate):
    memory = _get_or_create_project(project_id)
    payload = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    try:
        task = memory.update_task(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    return {"success": True, "task": task, "cockpit": memory.cockpit_summary(days=7)}


@router.get("/{project_id}/integrations")
async def list_integrations(project_id: str):
    memory = _get_or_create_project(project_id)
    return {"integrations": memory.integration_status()}


@router.patch("/{project_id}/integrations/{integration_id}")
async def update_integration(project_id: str, integration_id: str, req: IntegrationUpdate):
    memory = _get_or_create_project(project_id)
    payload = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    integration = memory.update_integration(integration_id, payload)
    return {"success": True, "integration": integration, "integrations": memory.integration_status()}


@router.get("/{project_id}/operations", response_model=OperationListResponse)
async def list_operations(project_id: str, days: int = Query(30, ge=1, le=366)):
    memory = _get_or_create_project(project_id)
    entries = memory.daily_operations[-days:]
    return {"entries": entries, "summary": memory.operation_summary(days=days)}


@router.post("/{project_id}/operations")
async def add_operation(project_id: str, entry: DailyOperationEntry):
    if not entry.date:
        raise HTTPException(status_code=400, detail="date is required")
    memory = _get_or_create_project(project_id)
    payload = entry.model_dump() if hasattr(entry, "model_dump") else entry.dict()
    memory.add_daily_operation(payload)
    return {
        "success": True,
        "entry": payload,
        "summary": memory.operation_summary(days=7),
    }


@router.get("/{project_id}/operations/summary")
async def operation_summary(project_id: str, days: int = Query(7, ge=1, le=366)):
    memory = _get_or_create_project(project_id)
    return memory.operation_summary(days=days)
