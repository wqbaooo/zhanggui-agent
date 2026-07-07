#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi.testclient import TestClient

from server.main import app
from server.routes.capture import (
    _detect_source_type,
    _enrich_capture_result,
    _normalize_result_shape,
    _redact_sensitive_text,
)
import server.routes.capture as capture_route
from server.model_routing import ModelRoute


def test_contract_capture_builds_review_artifact_and_redacts_id():
    raw_text = """
    店铺转让协议
    转让方（甲方）：张三
    身份证号：360100199001011234
    受让方（乙方）：李四
    一、店铺基本情况 建筑面积为 10 平方米
    二、租金及费用结算 乙方定期交纳租金及水电费
    甲方结清员工工资、供应商货款等债务，不得隐瞒。
    四、设施归属 营业设备全部归乙方。
    """

    result = _enrich_capture_result({
        "source_type": _detect_source_type(raw_text),
        "fields": [],
        "raw_text": raw_text,
    })

    assert result["source_type"] == "店铺转让协议"
    assert result["capture_kind"] == "document"
    assert result["recommended_destination"] == "合同/风险档案"
    assert result["structured_artifact"]["type"] == "contract_review"
    assert result["structured_artifact"]["schema_version"] == "capture_artifact_v1"
    assert result["structured_artifact"]["document_class"] == "合同/协议"
    assert "资料箱" in result["structured_artifact"]["write_targets"]
    assert "manual_review" in result["structured_artifact"]["canonical_sections"]
    assert any(fact["label"] == "建筑面积" for fact in result["document_facts"])
    assert any(item["key"] == "transfer_fee" for item in result["structured_artifact"]["required_manual_fields"])
    assert "199001011234" not in _redact_sensitive_text(raw_text)
    assert "已隐藏" in _redact_sensitive_text(raw_text)


def test_shelf_life_capture_builds_inventory_sop_artifact():
    raw_text = """
    大口效期管理
    常用酱料 原味酱 酱瓶内3天，开封常温7天
    青芥末酱 酱瓶内7天，开封常温7天
    奶酪酱 开封后冷藏3天
    面浆 冷藏保存 6-9月12h，12-2月36h，其余时间24h
    """

    result = _enrich_capture_result({
        "source_type": _detect_source_type(raw_text),
        "fields": [],
        "raw_text": raw_text,
    })

    artifact = result["structured_artifact"]
    assert result["source_type"] == "效期管理表"
    assert result["recommended_destination"] == "SOP作业库/库存效期"
    assert artifact["schema_version"] == "capture_artifact_v1"
    assert artifact["document_class"] == "库存/食品安全"
    assert "SOP作业库" in artifact["write_targets"]
    assert artifact["type"] == "shelf_life_policy"
    assert artifact["suggested_sop"]["category"] == "检查"
    assert len(artifact["items"]) >= 10
    assert len(artifact["canonical_sections"]["line_items"]) >= 10
    assert any(item["name"] == "原味酱" for item in artifact["items"])


def test_training_capture_builds_employee_training_sop_artifact():
    raw_text = """
    出餐岗前培训
    口味 步骤 注意事项
    原味 原味酱13克 香甜酱8-10克 中火加热木鱼花
    肉松 香甜酱8-10克 中心放肉松
    """

    result = _enrich_capture_result({
        "source_type": _detect_source_type(raw_text),
        "fields": [],
        "raw_text": raw_text,
    })

    artifact = result["structured_artifact"]
    assert result["source_type"] == "总部/SOP资料"
    assert result["recommended_destination"] == "SOP作业库/员工训练"
    assert artifact["schema_version"] == "capture_artifact_v1"
    assert artifact["document_class"] == "SOP/员工训练"
    assert "员工训练" in artifact["write_targets"]
    assert artifact["type"] == "training_sop"
    assert artifact["suggested_sop"]["category"] == "培训"
    assert len(artifact["canonical_sections"]["line_items"]) >= 3
    assert any(recipe["flavor"] == "原味" for recipe in artifact["recipes"])


def test_unknown_capture_still_uses_universal_template():
    raw_text = "一张暂时无法归类的门店现场照片，只有少量说明文字。"

    result = _enrich_capture_result({
        "source_type": _detect_source_type(raw_text),
        "fields": [],
        "raw_text": raw_text,
    })

    artifact = result["structured_artifact"]
    assert artifact["schema_version"] == "capture_artifact_v1"
    assert artifact["document_class"] == "通用资料"
    assert artifact["review_status"] == "needs_human_review"
    assert artifact["canonical_sections"]["ai_next_actions"]


def test_common_image_types_use_universal_template():
    cases = [
        ("客如云日报 今日营收 1200 订单数 60 差评 1", "operation_record", "经营数据", "经营日报"),
        ("进货单 章鱼粒 5kg 付款 300 元", "purchase_order", "进货/库存", "采购记录"),
        ("食品经营许可证 有效期至 2027 年 6 月", "compliance_document", "证照/合规", "证照到期提醒"),
        ("排班表 张三 6月27日 工时 8 小时 工资 160", "labor_record", "排班/工资", "工资核算"),
        ("美团差评 顾客投诉 配送超时 申请退款", "incident_report", "投诉/异常", "风险事件"),
        ("冰柜库存照片 章鱼粒 2袋 酱料若干", "inventory_observation", "库存/现场", "库存盘点"),
    ]

    for raw_text, artifact_type, document_class, target in cases:
        result = _enrich_capture_result({
            "source_type": _detect_source_type(raw_text),
            "fields": [],
            "raw_text": raw_text,
        })
        artifact = result["structured_artifact"]
        assert artifact["schema_version"] == "capture_artifact_v1"
        assert artifact["type"] == artifact_type
        assert artifact["document_class"] == document_class
        assert target in artifact["write_targets"]


def test_material_count_sheet_routes_to_inventory_review():
    raw_text = """
    大口章鱼烧物料盘点表
    类型 品名 单位 数量 使用数量 总数量
    常温货 章鱼预制粉 箱/10包/2千克 5 2 3
    调料包 箱/50包/200千克 5 2 3
    冷藏货 章鱼粒 箱/10包/1千克 12 2 10
    """

    result = _enrich_capture_result({
        "source_type": _detect_source_type(raw_text),
        "fields": [],
        "raw_text": raw_text,
    })

    assert result["source_type"] == "库存盘点表"
    assert result["capture_kind"] == "document"
    assert result["recommended_destination"] == "库存盘点/补货任务"
    assert result["structured_artifact"]["type"] == "inventory_observation"
    assert "库存盘点" in result["structured_artifact"]["write_targets"]


def test_capture_returns_review_draft_when_all_models_fail(monkeypatch):
    monkeypatch.setattr(capture_route, "_make_local_ocr_call", lambda *_: None)
    monkeypatch.setattr(capture_route, "_make_ollama_vision_call", lambda *_: None)
    monkeypatch.setattr(capture_route, "paid_vision_route", lambda: ModelRoute(
        agent="capture_agent",
        capability="image_vision_paid",
        provider="deepseek",
        model="deepseek-chat",
        configured=False,
    ))

    response = TestClient(app).post(
        "/api/capture/recognize",
        files={"image": ("test.jpg", b"not-a-real-image", "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["capture_kind"] == "unknown"
    assert payload["recommended_destination"] == "待人工确认"
    assert payload["structured_artifact"]["review_status"] == "needs_human_review"
    assert "人工确认" in payload["parse_error"]


def test_real_store_financial_and_order_documents_are_not_daily_revenue():
    cases = [
        (
            "转账汇款 金额 40,000.00元 交易时间 2026-06-27 14:29:50 交易成功 用途 其他 附言 转让费",
            "银行转账凭证",
            "payment_voucher",
            "财务/付款",
        ),
        (
            "大口章鱼烧王府井购物中心店 取餐号T10192 商品 原味章鱼烧 单价16.00 数量1 合计16.00 实付金额16.00 操作2026/06/27 19:20",
            "POS销售小票",
            "sale_receipt",
            "销售/订单",
        ),
        (
            "大口餐饮供应链 销售订单 单据日期2026-06-21 商品名称 章鱼预拌粉 数量12 单价265 合计3180 合计16108",
            "进货单",
            "purchase_order",
            "进货/库存",
        ),
        (
            "内用POS T10190 1/1 小龙虾鸡蛋汉堡 11.90 大口章鱼烧王府井购物中心店 2026/06/27 19:16",
            "出餐标签",
            "kitchen_ticket",
            "出餐/订单",
        ),
    ]

    for raw_text, source_type, artifact_type, document_class in cases:
        result = _enrich_capture_result({
            "source_type": _detect_source_type(raw_text),
            "fields": [],
            "raw_text": raw_text,
        })
        assert result["source_type"] == source_type
        assert result["capture_kind"] == "document"
        assert result["can_write_operation"] is False
        assert result["structured_artifact"]["type"] == artifact_type
        assert result["structured_artifact"]["document_class"] == document_class
        assert "资料箱" in result["structured_artifact"]["write_targets"]


def test_recognition_shape_normalizes_model_object_fields_and_preserves_line_items():
    result = _normalize_result_shape({
        "source_type": "进货单",
        "fields": {"date": "2026-06-21", "amount": 16108},
        "document_facts": {"供应商": "大口餐饮供应链"},
        "line_items": [
            {"name": "章鱼预拌粉", "quantity": 12, "unit_cost": 265, "total": 3180},
        ],
    })

    assert result["fields"] == [
        {"key": "date", "label": "日期", "value": "2026-06-21", "confidence": "low"},
        {"key": "amount", "label": "金额", "value": 16108, "confidence": "low"},
    ]
    assert result["document_facts"][0]["label"] == "供应商"
    assert result["line_items"][0]["total"] == 3180
