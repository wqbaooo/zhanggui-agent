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
    scope: str = Field("master", description="会话范围：master / finance / inventory 等")
    client_message_id: Optional[str] = Field(None, description="前端消息 ID，用于防止重复写入")


class AgentSessionCreate(BaseModel):
    id: Optional[str] = None
    title: str = "新对话"
    scope: str = "master"
    messages: List[Dict[str, Any]] = Field(default_factory=list)


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


class MonthlyOperatingEntry(BaseModel):
    year: int = Field(..., ge=2000, le=2100, description="经营数据年份")
    month: int = Field(..., ge=1, le=12, description="经营数据月份")
    revenue: Optional[float] = Field(None, ge=0, description="当月营业额；未知时留空")
    net_profit: Optional[float] = Field(None, description="当月已实现净利润；未知时留空")
    review_status: str = Field("confirmed", description="confirmed / needs_human_review")
    source_type: str = Field("image_confirmed", description="image_confirmed / manual / import")
    source_file_name: str = Field("", description="来源图片或文件名")
    source_raw_text: str = Field("", description="OCR 原文，供审计追溯")


class MonthlyOperatingUpdate(BaseModel):
    entries: List[MonthlyOperatingEntry] = Field(default_factory=list)
    monthly_rent: Optional[float] = Field(None, ge=0)
    monthly_utility_min: Optional[float] = Field(None, ge=0)
    monthly_utility_max: Optional[float] = Field(None, ge=0)
    wage_per_person: Optional[float] = Field(None, ge=0)
    previous_staff_count: Optional[int] = Field(None, ge=0)
    current_staff_count: Optional[int] = Field(None, ge=0)
    owner_operates: Optional[bool] = None


class UtilityRecord(BaseModel):
    month: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    water: float = Field(0, ge=0)
    electricity: float = Field(0, ge=0)
    notes: str = ""


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
    revenue: float = Field(0, description="总营业额（向后兼容，优先等于 actual_revenue）")
    orders: int = Field(0, description="总订单数")
    dine_in_revenue: float = Field(0, description="堂食营收")
    dine_in_orders: int = Field(0, description="堂食订单数")
    delivery_revenue: float = Field(0, description="外卖营收")
    delivery_orders: int = Field(0, description="外卖订单数")
    food_cost: float = Field(0, description="食材成本")
    packaging_cost: float = Field(0, description="包装成本")
    labor: float = Field(0, description="人工成本")
    rent_allocated: float = Field(0, description="当天摊销租金")
    utility: float = Field(0, description="水电")
    other_cost: float = Field(0, description="其他成本")
    takeout_orders: int = Field(0, description="外卖订单数（兼容旧字段，同 delivery_orders）")
    platform_fee: float = Field(0, description="平台扣点/服务费")
    marketing_cost: float = Field(0, description="营销/满减成本")
    inventory_loss: float = Field(0, description="库存/报损")
    bad_reviews: int = Field(0, description="差评数量")
    repeat_orders: int = Field(0, description="复购订单数")
    new_members: int = Field(0, description="新增会员数")
    notes: str = Field("", description="当天动作、异常和复盘")
    # ── 日结清算字段（2026-07-04）──
    original_amount: float = Field(0, description="订单原价/订单金额（折扣前）")
    actual_revenue: float = Field(0, description="实际收入/销售实收（到账）")
    merchant_discount: float = Field(0, description="商户优惠/满减金额")
    refund_amount: float = Field(0, description="退款金额")
    refund_orders: int = Field(0, description="退款订单数")
    service_fee: float = Field(0, description="平台服务费/佣金")
    delivery_fee: float = Field(0, description="订单配送支出")
    surcharge: float = Field(0, description="附加费/包装费等")
    items_sold: int = Field(0, description="销售数量（商品件数）")
    customers: int = Field(0, description="就餐人数")
    visitors: int = Field(0, description="来客人数")
    dining_customers: int = Field(0, description="实际就餐人数")
    sales_transactions: int = Field(0, description="销货交易笔数，不等同于商品件数")
    avg_order_value_before_discount: float = Field(0, description="折前单均价")
    avg_order_value_after_discount: float = Field(0, description="折后单均价")
    payment_methods: List[Dict[str, Any]] = Field(default_factory=list, description="支付方式明细")
    channel_breakdown: List[Dict[str, Any]] = Field(default_factory=list, description="渠道来源明细（堂食/美团外卖/抖音团购等）")
    product_sales: List[Dict[str, Any]] = Field(default_factory=list, description="商品销量明细")
    settlement_breakdown: List[Dict[str, Any]] = Field(default_factory=list, description="资金归属与到账状态")
    revenue_basis: str = Field("gross_sales", description="收入口径：net_settlement/gross_sales")
    cost_status: str = Field("incomplete", description="成本完整度：incomplete/confirmed")
    # ── 数据溯源 ──
    source_type: Optional[str] = Field(None, description="数据来源类型：ocr / csv / manual / estimated")
    source_platform: Optional[str] = Field(None, description="来源平台：meituan / taobao_flash / pos / unknown")
    source_file_name: Optional[str] = Field(None, description="来源文件名")
    source_raw_text: Optional[str] = Field(None, description="原始识别文本（OCR 用）")
    source_confidence: Optional[str] = Field(None, description="识别置信度：high / medium / low")
    source_imported_at: Optional[str] = Field(None, description="导入时间 ISO format")
    source_quality_score: Optional[str] = Field(None, description="数据质量评分：A / B / C / D")


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
    stock_by_location: Dict[str, float] = Field(default_factory=dict, description="门店/仓库/待分配库存")
    count_units: List[Dict[str, Any]] = Field(default_factory=list, description="总部与盘点单位换算")
    tracking_mode: str = Field("periodic_count", description="open_pack/periodic_count")
    daily_usage_group: str = Field("", description="每日使用表的营业动作分组，不替代仓储品类")
    daily_usage_sort: int = Field(0, ge=0, description="每日使用表内排序")
    display_unit: str = Field("", description="老板查看和台账使用的单位")
    store_target_days: float = Field(0.0, ge=0, description="门店目标覆盖天数，0 表示未配置")
    supplier_lead_days: int = Field(3, ge=0, description="供应商到货周期")
    reorder_enabled: bool = Field(True, description="是否纳入补货预测")
    usage_integer_only: bool = Field(True, description="每日开封/领用是否只允许整数")
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
    stock_by_location: Optional[Dict[str, float]] = None
    count_units: Optional[List[Dict[str, Any]]] = None
    tracking_mode: Optional[str] = None
    daily_usage_group: Optional[str] = None
    daily_usage_sort: Optional[int] = Field(None, ge=0)
    display_unit: Optional[str] = None
    store_target_days: Optional[float] = Field(None, ge=0)
    supplier_lead_days: Optional[int] = Field(None, ge=0)
    reorder_enabled: Optional[bool] = None
    usage_integer_only: Optional[bool] = None
    active: Optional[bool] = None
    last_purchase_date: Optional[str] = None
    notes: Optional[str] = None
    hq_code: Optional[str] = None
    hq_name: Optional[str] = None
    hq_image: Optional[str] = None
    standard_unit: Optional[str] = None


class SkuAliasCreate(BaseModel):
    sku_id: str = Field(..., description="关联的 SKU ID")
    alias: str = Field(..., description="别名（供应商品名）")
    supplier: str = Field("", description="供应商")
    unit_conversion: float = Field(1.0, description="单位换算系数")
    alias_unit: str = Field("", description="别名单位")
    source: str = Field("manual", description="来源")


class SkuAliasUpdate(BaseModel):
    sku_id: Optional[str] = None
    alias: Optional[str] = None
    supplier: Optional[str] = None
    unit_conversion: Optional[float] = None
    alias_unit: Optional[str] = None
    source: Optional[str] = None


class SkuAliasBatchMatchItem(BaseModel):
    name: str = Field(..., description="品名")
    supplier: str = Field("", description="供应商")


class SkuAliasBatchMatchRequest(BaseModel):
    items: List[SkuAliasBatchMatchItem] = Field(default_factory=list)


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
    paid_amount: float = Field(0.0, ge=0, description="已付款金额")
    fulfillment_status: str = Field("ordered", description="ordered/received")
    external_order_id: str = Field("", description="供应链订单号")
    location: str = Field("warehouse", description="兼容旧字段；实际位置在清点收货时确认")
    notes: str = Field("", description="备注")
    platform: str = Field("", description="总部/拼多多/淘宝/淘宝闪购/1688等")
    freight: float = Field(0.0, ge=0, description="订单采购运费")
    discount_amount: float = Field(0.0, ge=0, description="订单优惠")
    refund_amount: float = Field(0.0, ge=0, description="订单退款")
    evidence_file: str = Field("", description="原始凭证文件")
    accounting_status: str = Field("inventory_asset", description="库存资产/低值耗材/设备资产等会计口径")


class PurchaseReceiptItem(BaseModel):
    sku_id: str
    received_quantity: float = Field(..., ge=0)
    allocations: Dict[str, float] = Field(
        default_factory=dict,
        description="实收后分配到 store/warehouse/freezer 的数量",
    )


class PurchaseReceiptCreate(BaseModel):
    date: str
    items: List[PurchaseReceiptItem]
    source: str = "owner_confirmed"
    notes: str = ""


class InventoryMovementItem(BaseModel):
    sku_id: str
    quantity: float = Field(..., gt=0)


class InventoryTransferCreate(BaseModel):
    date: str
    from_location: str = Field(..., description="store/warehouse/unallocated")
    to_location: str = Field(..., description="store/warehouse")
    items: List[InventoryMovementItem]
    source: str = "manual"
    notes: str = ""


class InventoryUsageItem(BaseModel):
    sku_id: str
    quantity: float = Field(..., ge=0)
    name: str = ""
    unit: str = ""


class InventoryUsageCreate(BaseModel):
    date: str
    location: str = "store"
    items: List[InventoryUsageItem]
    source: str = "paper_ledger"
    notes: str = ""


class InventoryWasteCreate(BaseModel):
    date: str
    location: str = "store"
    items: List[InventoryMovementItem]
    reason: str = Field(..., min_length=1, description="撒漏/变质/过期/破损/其他")
    source: str = "owner_confirmed"
    notes: str = ""


class InventoryCountLineInput(BaseModel):
    sku_id: str
    counted_quantity: float = Field(..., ge=0)
    counted_unit: str = Field("", description="盘点时使用的单位；空则按 SKU display_unit 自动换算")
    components: List[Dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


class InventoryCountCreate(BaseModel):
    date: str
    location: str = Field("store", description="store/warehouse/freezer")
    count_type: str = Field("weekly", description="weekly/biweekly/monthly/spot")
    lines: List[InventoryCountLineInput]
    source: str = "manual"
    notes: str = ""


class ProductionInput(BaseModel):
    sku_id: str
    quantity: float = Field(..., gt=0)
    name: str = ""
    unit: str = ""


class ProductionBatchCreate(BaseModel):
    date: str
    name: str
    location: str = "store"
    inputs: List[ProductionInput]
    output_quantity: float = Field(..., gt=0)
    output_unit: str = "批"
    pan_cycle_minutes: float = Field(0.0, ge=0)
    source: str = "manual"
    notes: str = ""


class ProductionBatchClose(BaseModel):
    used_quantity: float = Field(..., ge=0)
    waste_quantity: float = Field(0.0, ge=0)
    actual_pan_cycles: float = Field(0.0, ge=0)
    notes: str = ""


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
    hourly_wage: float = Field(0.0, ge=0, description="时薪")
    monthly_base: float = Field(0.0, ge=0, description="月底薪或老板守店月度成本")
    pay_type: str = Field("auto", pattern="^(auto|hourly|monthly|owner)$", description="计薪方式")
    standard_monthly_work_days: int = Field(26, ge=1, le=31, description="月薪标准出勤天数")
    overtime_multiplier: float = Field(1.5, ge=1, le=5, description="加班工资倍数")
    overtime_hourly_rate: float = Field(0.0, ge=0, description="固定加班时薪；大于 0 时优先于加班倍数")
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
    pay_type: Optional[str] = Field(None, pattern="^(auto|hourly|monthly|owner)$")
    standard_monthly_work_days: Optional[int] = Field(None, ge=1, le=31)
    overtime_multiplier: Optional[float] = Field(None, ge=1, le=5)
    overtime_hourly_rate: Optional[float] = Field(None, ge=0)
    hire_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class WorkRecordCreate(BaseModel):
    staff_id: str = Field(..., description="员工 ID")
    date: str = Field(..., description="日期 YYYY-MM-DD")
    shift: str = Field("全天", description="班次：早班/晚班/全天")
    hours: float = Field(0.0, ge=0, le=24, description="工时（小时）")
    overtime_hours: float = Field(0.0, ge=0, le=24, description="加班（小时）")
    notes: str = Field("", description="备注")


class WorkRecordListParams(BaseModel):
    staff_id: Optional[str] = None
    date_from: str = ""
    date_to: str = ""
    limit: int = 60
