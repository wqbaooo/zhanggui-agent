#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""请求/响应 Pydantic 模型。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话 ID，空则创建新会话")
    project_id: Optional[str] = Field(None, description="项目 ID")
    context: Dict[str, Any] = Field(default_factory=dict, description="注入的上下文（城市/品类/预算等）")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Agent 回复文本")
    session_id: str = Field(..., description="会话 ID")


class AuditResponse(BaseModel):
    chunks: int
    by_type: Dict[str, int]
    by_status: Dict[str, int]


class HealthResponse(BaseModel):
    status: str
    service: str


class ProjectProfileUpdate(BaseModel):
    profile: Dict[str, Any] = Field(default_factory=dict)


class FranchiseConstraintsUpdate(BaseModel):
    constraints: Dict[str, Any] = Field(default_factory=dict)


class SiteTransferUpdate(BaseModel):
    site_transfer: Dict[str, Any] = Field(default_factory=dict)


class ActionTaskCreate(BaseModel):
    id: Optional[str] = Field(None, description="任务 ID；不传则自动生成")
    title: str = Field(..., description="任务标题")
    target: str = Field("工作台", description="关联工具/页面")
    priority: str = Field("medium", description="high/medium/low")
    source: str = Field("manual", description="任务来源")
    status: str = Field("todo", description="todo/in_progress/done/blocked")
    due_date: str = Field("", description="截止日期，YYYY-MM-DD，可为空")
    notes: str = Field("", description="任务备注")


class ActionTaskUpdate(BaseModel):
    title: Optional[str] = None
    target: Optional[str] = None
    priority: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None


class IntegrationUpdate(BaseModel):
    name: Optional[str] = None
    scope: Optional[str] = None
    status: Optional[str] = None
    status_label: Optional[str] = None
    fallback: Optional[str] = None
    available_paths: Optional[List[str]] = None
    notes: Optional[str] = None


class DailyOperationEntry(BaseModel):
    date: str = Field(..., description="日期，YYYY-MM-DD")
    revenue: float = Field(0, description="营业额")
    orders: int = Field(0, description="订单数")
    food_cost: float = Field(0, description="食材成本")
    labor: float = Field(0, description="人工成本")
    rent_allocated: float = Field(0, description="当天摊销租金")
    utility: float = Field(0, description="水电")
    other_cost: float = Field(0, description="其他成本")
    takeout_orders: int = Field(0, description="外卖订单数")
    platform_fee: float = Field(0, description="平台扣点/服务费")
    marketing_cost: float = Field(0, description="营销/满减成本")
    inventory_loss: float = Field(0, description="库存/报损")
    notes: str = Field("", description="当天动作、异常和复盘")


class OperationListResponse(BaseModel):
    entries: List[Dict[str, Any]]
    summary: Dict[str, Any]
