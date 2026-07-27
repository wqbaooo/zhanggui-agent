#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi.testclient import TestClient

from server.main import app
from server.routes.capture import (
    _detect_source_type,
    _enrich_capture_result,
    _normalize_result_shape,
    _redact_sensitive_text,
    _source_type_to_platform,
)
import server.routes.capture as capture_route
from server.model_routing import ModelRoute
from models.finance_ledger import FinanceLedger
from models.operating_ledger import OperatingLedger
from models.project import ProjectMemory
import config
import models.project as project_model


def test_all_store_revenue_platform_screenshots_keep_distinct_sources():
    cases = {
        "客如云 营业收入 128.50": ("客如云日报", "keyun"),
        "美团外卖 当日实收 88.20": ("美团外卖后台", "meituan_delivery"),
        "美团团购 商家实收 75.00": ("美团团购后台", "meituan_group"),
        "淘宝闪购 外卖实收 96.00": ("淘宝闪购后台", "taobao_flash"),
        "京东外卖 当日营业额 59.30": ("京东外卖后台", "jd_delivery"),
        "抖音团购 核销实收 120.00": ("抖音团购后台", "douyin_group"),
    }
    for raw_text, (source_type, platform) in cases.items():
        detected = _detect_source_type(raw_text)
        assert detected == source_type
        assert _source_type_to_platform(detected) == platform


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


def test_keruyun_daily_report_extracts_finance_fields_for_pending_facts():
    raw_text = """
    客如云 营业日报 2026-07-09
    订单金额 1119.83 营业收入 882.89
    订单数 56 店内营业收入 704.88 第三方营业收入 178.01
    商户优惠 91.76 订单配送支出 36.45 服务费 91.89 补贴 -16.84
    微信 513 现金 77 支付宝 32 美团外卖 97.25 淘宝闪购餐饮 80.76 抖音团购券 69.01
    """

    result = _enrich_capture_result({
        "source_type": _detect_source_type(raw_text),
        "fields": [],
        "raw_text": raw_text,
    })

    assert result["source_type"] == "客如云日报"
    assert result["capture_kind"] == "operation"
    artifact = result["structured_artifact"]
    assert artifact["schema_version"] == "capture_artifact_v1"
    assert artifact["type"] == "operation_record"
    assert artifact["write_payloads"]["business_fact_source"] == "keruyun_daily_report"
    fields = {field["key"]: field["value"] for field in result["fields"]}
    assert fields["order_amount"] == 1119.83
    assert fields["operating_income"] == 882.89
    assert fields["delivery_fee"] == 36.45
    assert fields["cash_amount"] == 77
    assert fields["taobao_flash_amount"] == 80.76


def test_supplier_credit_receipt_routes_to_payable_not_cash_spend():
    raw_text = """
    客户名称：章鱼烧
    商品名 下单数 实际出货 销售单价 小计
    包菜 6斤 6斤 7.50 11.55
    大葱 1个 1个 2.50 3.60
    合计：15.15
    挂账 未结账
    """

    result = _enrich_capture_result({
        "source_type": _detect_source_type(raw_text),
        "fields": [],
        "raw_text": raw_text,
    })

    assert result["source_type"] == "菜场挂账小票"
    assert result["capture_kind"] == "document"
    artifact = result["structured_artifact"]
    assert artifact["type"] == "supplier_credit_receipt"
    assert artifact["document_class"] == "采购/应付"
    assert "应付账款" in artifact["write_targets"]
    assert artifact["write_payloads"]["supplier_credit"]["amount"] == 15.15
    assert artifact["write_payloads"]["supplier_credit"]["cash_impact"] == 0


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


def test_confirmed_utility_bill_posts_once_to_finance_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    project_id = "capture-finance-store"
    memory = ProjectMemory.create(project_id)
    memory.update_profile({"store_name": "测试门店", "transfer_date": "2026-07-01"})
    payload = {
        "file_name": "7月电费.png",
        "source_type": "水电单",
        "capture_kind": "document",
        "recognized_fields": [
            {"key": "date", "value": "2026-07-10"},
            {"key": "utility", "value": 12.34},
        ],
        "write_target": "资料箱 + 成本记录",
        "date": "2026-07-10",
    }

    client = TestClient(app)
    first = client.post(f"/api/capture/confirm/{project_id}", json=payload)
    ledger = FinanceLedger.for_project(project_id)
    entries_after_first = ledger.count_posted_entries(project_id)
    second = client.post(f"/api/capture/confirm/{project_id}", json=payload)
    entries_after_second = ledger.count_posted_entries(project_id)

    assert first.status_code == 200
    assert first.json()["posted_expenses"][0]["amount_minor"] == 1234
    assert first.json()["posted_expenses"][0]["business_fact_id"]
    assert second.json()["posted_expenses"][0]["journal_entry_id"] == first.json()["posted_expenses"][0]["journal_entry_id"]
    assert second.json()["posted_expenses"][0]["business_fact_id"] == first.json()["posted_expenses"][0]["business_fact_id"]
    operating = OperatingLedger.load(project_id)
    expense_fact = operating.find_fact(first.json()["posted_expenses"][0]["business_fact_id"])
    assert expense_fact["fact_type"] == "operating_expense"
    assert expense_fact["ledger_status"] == "posted"
    assert expense_fact["metadata"]["finance_account_code"] == "6003"
    assert entries_after_second == entries_after_first
    assert ledger.overview(project_id, "2026-07-10", "2026-07-10")["costs_minor"]["utility"] == 1234


def test_confirmed_purchase_order_is_not_expensed_as_period_cost(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(project_model, "PROJECT_DATA_DIR", tmp_path)
    project_id = "capture-purchase-store"
    memory = ProjectMemory.create(project_id)
    memory.update_profile({"store_name": "测试门店", "transfer_date": "2026-07-01"})
    operating = OperatingLedger(project_id)
    operating.seed_real_store()
    operating.save()

    response = TestClient(app).post(
        f"/api/capture/confirm/{project_id}",
        json={
            "file_name": "进货单.png",
            "source_type": "进货单",
            "capture_kind": "document",
            "recognized_fields": [{"key": "food_cost", "value": 300}],
            "write_target": "采购记录 + 库存入库 + 应付账款",
            "date": "2026-07-10",
            "structured_artifact": {
                "type": "purchase_order",
                "write_payloads": {
                    "purchase_order": {
                        "date": "2026-07-10",
                        "supplier": "大口供应链",
                        "items": [{"name": "章鱼粒", "quantity": 2, "unit_cost": 60}],
                    }
                },
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["posted_expenses"] == []
    assert {item["fact_type"] for item in response.json()["posted_business_facts"]} == {
        "purchase_confirmation",
        "stock_in",
    }
    assert not any(
        fact["fact_type"] == "operating_expense"
        for fact in OperatingLedger.load(project_id).business_facts
    )
    ledger = FinanceLedger.for_project(project_id)
    assert ledger.overview(project_id, "2026-07-10", "2026-07-10")["costs_minor"]["food_cost"] == 0
    assert ledger.overview(project_id, "2026-07-10", "2026-07-10")["assets_minor"]["inventory"] == 12000
