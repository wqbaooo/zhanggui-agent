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


class DeliveryImportCreate(BaseModel):
    source: str = Field("manual", description="meituan/taobao_flash/douyin/manual/csv/screenshot")
    raw_text: str = Field("", description="原始导入文本或 OCR 文本")
    parsed: Dict[str, Any] = Field(default_factory=dict, description="前端或适配器解析出的摘要字段")


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
    bad_reviews: int = Field(0, description="差评数量")
    notes: str = Field("", description="当天动作、异常和复盘")


class OperationListResponse(BaseModel):
    entries: List[Dict[str, Any]]
    summary: Dict[str, Any]


# ── 门店资料箱 ──

class DocumentCreate(BaseModel):
    title: str = Field(..., description="文档标题")
    doc_type: str = Field("其他", description="文档类型")
    tags: List[str] = Field(default_factory=list)
    source: str = Field("", description="来源")
    file_ref: str = Field("", description="文件引用")
    parties: List[str] = Field(default_factory=list, description="相关方")
    sign_date: Optional[str] = Field(None, description="签署日期 YYYY-MM-DD")
    expiry_date: Optional[str] = Field(None, description="到期日期 YYYY-MM-DD")
    key_terms: List[str] = Field(default_factory=list, description="关键条款")
    extracted_fields: Dict[str, Any] = Field(default_factory=dict, description="提取字段")
    risk_flags: List[str] = Field(default_factory=list, description="风险标记")
    related_to: Dict[str, str] = Field(default_factory=dict, description="关联对象")
    notes: str = Field("", description="备注")


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    doc_type: Optional[str] = None
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    file_ref: Optional[str] = None
    status: Optional[str] = None
    parties: Optional[List[str]] = None
    sign_date: Optional[str] = None
    expiry_date: Optional[str] = None
    key_terms: Optional[List[str]] = None
    extracted_fields: Optional[Dict[str, Any]] = None
    risk_flags: Optional[List[str]] = None
    related_to: Optional[Dict[str, str]] = None
    notes: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: List[Dict[str, Any]]
    summary: Dict[str, Any]


class DocumentResponse(BaseModel):
    document: Dict[str, Any]


# ── SKU 与进货 ──

class SkuCreate(BaseModel):
    name: str = Field(..., description="SKU 名称")
    category: str = Field("食材", description="品类：食材/包装/耗材/清洁/其他")
    unit: str = Field("个", description="单位")
    safety_stock: float = Field(0.0, description="安全库存")
    current_stock: float = Field(0.0, description="当前库存")
    unit_cost: float = Field(0.0, description="单位成本")
    supplier: str = Field("", description="供应商")
    batch_cycle_days: int = Field(14, description="批次周期（天）")
    consumption_per_day: float = Field(0.0, description="日均消耗")
    notes: str = Field("", description="备注")


class SkuUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    safety_stock: Optional[float] = None
    current_stock: Optional[float] = None
    unit_cost: Optional[float] = None
    supplier: Optional[str] = None
    batch_cycle_days: Optional[int] = None
    consumption_per_day: Optional[float] = None
    last_purchase_date: Optional[str] = None
    notes: Optional[str] = None


class PurchaseItemInput(BaseModel):
    sku_id: str = Field(..., description="SKU ID")
    name: str = Field("", description="品名")
    quantity: float = Field(0.0, description="数量")
    unit_cost: float = Field(0.0, description="单价")


class PurchaseCreate(BaseModel):
    date: str = Field(..., description="进货日期 YYYY-MM-DD")
    supplier: str = Field("", description="供应商")
    items: List[PurchaseItemInput] = Field(default_factory=list, description="进货明细")
    payment_status: str = Field("未付", description="付款状态")
    notes: str = Field("", description="备注")


# ── SOP 文档库 ──

class SopCreate(BaseModel):
    category: str = Field("产品制作", description="SOP 分类")
    title: str = Field(..., description="SOP 标题")
    source: str = Field("", description="来源")
    description: str = Field("", description="描述")
    steps: List[Dict[str, Any]] = Field(default_factory=list, description="步骤列表")
    related_sku_ids: List[str] = Field(default_factory=list, description="关联 SKU")
    related_training_skills: List[str] = Field(default_factory=list, description="关联训练技能")
    review_cycle_days: int = Field(90, description="复核周期（天）")
    notes: str = Field("", description="备注")


class SopUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None
    related_sku_ids: Optional[List[str]] = None
    related_training_skills: Optional[List[str]] = None
    last_reviewed: Optional[str] = None
    review_cycle_days: Optional[int] = None
    notes: Optional[str] = None
    bump_version: Optional[bool] = None


# ── 工时工资 ──

class StaffCreate(BaseModel):
    name: str = Field(..., description="姓名")
    role: str = Field("员工", description="岗位")
    phone: str = Field("", description="电话")
    health_cert_expiry: Optional[str] = Field(None, description="健康证到期日 YYYY-MM-DD")
    skills: List[str] = Field(default_factory=list, description="技能标签")
    hourly_wage: float = Field(0.0, description="时薪")
    monthly_base: float = Field(0.0, description="月底薪")
    hire_date: Optional[str] = Field(None, description="入职日期 YYYY-MM-DD")
    notes: str = Field("", description="备注")


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    health_cert_expiry: Optional[str] = None
    skills: Optional[List[str]] = None
    hourly_wage: Optional[float] = None
    monthly_base: Optional[float] = None
    hire_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class WorkRecordCreate(BaseModel):
    staff_id: str = Field(..., description="员工 ID")
    date: str = Field(..., description="日期 YYYY-MM-DD")
    shift: str = Field("全天", description="班次：早班/晚班/全天")
    hours: float = Field(0.0, description="工时（小时）")
    overtime_hours: float = Field(0.0, description="加班（小时）")
    notes: str = Field("", description="备注")


class WorkRecordListParams(BaseModel):
    staff_id: Optional[str] = None
    date_from: str = ""
    date_to: str = ""
    limit: int = 60
