"""First-stage trusted operating ledger for the real Xinyu store."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

import config
from models.json_store import atomic_write_json, load_json


FactType = Literal[
    "pos_sale",
    "net_operating_income",
    "dine_in_income",
    "third_party_income",
    "payment_method_breakdown",
    "channel_sales_breakdown",
    "merchant_discount",
    "delivery_cost",
    "service_fee",
    "subsidy_adjustment",
    "cash_sale",
    "meituan_delivery_sale",
    "taobao_delivery_sale",
    "jd_delivery_sale",
    "douyin_group_sale",
    "meituan_group_sale",
    "platform_fee",
    "promotion_cost",
    "refund",
    "platform_settlement",
    "former_owner_collected",
    "former_owner_transfer",
    "purchase",
    "supplier_invoice",
    "supplier_credit_purchase",
    "purchase_confirmation",
    "operating_expense",
    "stock_in",
    "inventory_count_photo",
    "stock_count",
    "stock_usage",
    "stock_adjustment",
    "stock_loss",
    "manual_note",
    "non_operating",
    "unknown",
]


MONEY_FACT_TYPES = {
    "pos_sale",
    "net_operating_income",
    "dine_in_income",
    "third_party_income",
    "payment_method_breakdown",
    "channel_sales_breakdown",
    "merchant_discount",
    "delivery_cost",
    "service_fee",
    "subsidy_adjustment",
    "cash_sale",
    "meituan_delivery_sale",
    "taobao_delivery_sale",
    "jd_delivery_sale",
    "douyin_group_sale",
    "meituan_group_sale",
    "platform_fee",
    "promotion_cost",
    "refund",
    "platform_settlement",
    "former_owner_collected",
    "former_owner_transfer",
    "purchase",
    "supplier_invoice",
    "supplier_credit_purchase",
    "purchase_confirmation",
    "operating_expense",
    "non_operating",
}
INVENTORY_FACT_TYPES = {"stock_in", "inventory_count_photo", "stock_count", "stock_usage", "stock_adjustment", "stock_loss"}

REAL_FIXTURE_DATE = "2026-07-04"
FIXTURE_VERSION = "evidence-chain-dedupe-v2"


def now_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()


def project_path(project_id: str):
    return config.PROJECT_DATA_DIR / project_id / "operating_ledger.json"


def reconciliation_path(project_id: str):
    return config.PROJECT_DATA_DIR / project_id / "platform_reconciliations.json"


@dataclass
class RawMaterial:
    id: str
    shop_id: str
    uploaded_at: str
    source_type: str
    source_platform: str
    title: str
    ocr_text: str = ""
    ai_summary: str = ""
    file_url: str = ""
    status: str = "parsed"


@dataclass
class BusinessFact:
    id: str
    raw_material_id: str
    fact_type: FactType
    date: str
    amount: float
    platform: str
    account_location: str
    business_owner: str
    confidence: str
    review_status: str
    ledger_status: str
    state: str = "need_review"
    title: str = ""
    description: str = ""
    affects: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    needs_owner_confirmation: bool = True
    period_start: str | None = None
    period_end: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    posting_key: str = ""
    evidence_role: str = "primary"
    primary_evidence_id: str = ""
    supporting_evidence_ids: list[str] = field(default_factory=list)
    duplicate_of: str = ""
    source_type: str = ""
    source_platform: str = ""
    source_date: str = ""
    evidence_image_url: str = ""
    evidence_file_ref: str = ""
    extracted_fields: dict[str, Any] = field(default_factory=dict)
    posted_at: str = ""
    posted_by: str = "owner"
    affects_accounts: list[str] = field(default_factory=list)
    affects_inventory_items: list[str] = field(default_factory=list)
    source_group: str = ""
    anomaly_reason: str = ""
    auto_posted: bool = False


@dataclass
class LedgerEntry:
    id: str
    fact_id: str
    date: str
    entry_type: str
    amount: float
    account: str
    counterparty: str
    status: str
    confirmed_by_owner: bool
    platform: str = ""
    business_owner: str = "my_shop"
    notes: str = ""


@dataclass
class InventoryItem:
    id: str
    name: str
    category: str
    unit: str
    current_quantity: float
    latest_unit_cost: float
    safe_stock: float
    shelf_life_days: int | None = None
    storage_location: str = "门店"


@dataclass
class InventoryMovement:
    id: str
    item_id: str
    date: str
    movement_type: str
    quantity: float
    unit_cost: float
    source_fact_id: str
    confirmed_by_owner: bool
    notes: str = ""


@dataclass
class Product:
    id: str
    name: str
    flavor: str


@dataclass
class ProductVariant:
    id: str
    product_id: str
    name: str
    pieces: int
    packaging_item_id: str


@dataclass
class ChannelPrice:
    id: str
    variant_id: str
    channel: str
    listed_price: float
    expected_net_price: float | None = None
    notes: str = ""


@dataclass
class ProductBOM:
    id: str
    product_name: str
    variant: str
    ingredient_item_id: str
    quantity_per_unit: float | None
    unit: str
    waste_rate: float = 0
    confirmed_by_owner: bool = False
    missing_reason: str = ""


class OperatingLedger:
    def __init__(self, project_id: str, payload: dict[str, Any] | None = None):
        self.project_id = project_id
        self.raw_materials: list[dict[str, Any]] = []
        self.business_facts: list[dict[str, Any]] = []
        self.ledger_entries: list[dict[str, Any]] = []
        self.inventory_items: list[dict[str, Any]] = []
        self.inventory_movements: list[dict[str, Any]] = []
        self.products: list[dict[str, Any]] = []
        self.product_variants: list[dict[str, Any]] = []
        self.channel_prices: list[dict[str, Any]] = []
        self.product_boms: list[dict[str, Any]] = []
        self.platform_reconciliations: dict[str, Any] = {}
        self.cash_movements: list[dict[str, Any]] = []
        if payload:
            for key in [
                "raw_materials",
                "business_facts",
                "ledger_entries",
                "inventory_items",
                "inventory_movements",
                "products",
                "product_variants",
                "channel_prices",
                "product_boms",
            ]:
                setattr(self, key, payload.get(key, []))
        reconciliation = load_json(reconciliation_path(project_id), expected_type=dict)
        if reconciliation:
            self.platform_reconciliations = reconciliation

    @classmethod
    def load(cls, project_id: str, seed_if_missing: bool = False) -> "OperatingLedger":
        payload = load_json(project_path(project_id), expected_type=dict)
        if payload is None:
            ledger = cls(project_id)
            if seed_if_missing:
                ledger.seed_real_store()
                ledger.save()
            return ledger
        return cls(project_id, payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "fixture_version": FIXTURE_VERSION,
            "default_date": today(),
            "raw_materials": self.raw_materials,
            "business_facts": self.business_facts,
            "ledger_entries": self.ledger_entries,
            "inventory_items": self.inventory_items,
            "inventory_movements": self.inventory_movements,
            "products": self.products,
            "product_variants": self.product_variants,
            "channel_prices": self.channel_prices,
            "product_boms": self.product_boms,
        }

    def save(self) -> None:
        atomic_write_json(project_path(self.project_id), self.to_dict())

    def reconciliation_view(self, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        """Return platform reconciliation facts without adding them to store revenue."""
        records = list(self.platform_reconciliations.get("records") or [])
        if start:
            records = [item for item in records if item.get("business_date", "") >= start]
        if end:
            records = [item for item in records if item.get("business_date", "") <= end]
        by_platform: dict[str, dict[str, Any]] = {}
        for item in records:
            platform = str(item.get("platform") or "unknown")
            summary = by_platform.setdefault(platform, {"platform": platform, "amount": 0.0, "records": 0, "counted_in_store_revenue": 0.0})
            amount = float(item.get("amount") or 0)
            summary["amount"] += amount
            summary["records"] += 1
            if item.get("counted_in_store_revenue"):
                summary["counted_in_store_revenue"] += amount
        return {
            "source_file": self.platform_reconciliations.get("source_file", ""),
            "source_period": self.platform_reconciliations.get("source_period", {}),
            "aggregation_rule": self.platform_reconciliations.get("aggregation_rule", ""),
            "records": records,
            "by_platform": [
                {**item, "amount": round(item["amount"], 2), "counted_in_store_revenue": round(item["counted_in_store_revenue"], 2)}
                for item in by_platform.values()
            ],
            "missing_platform_evidence": self.platform_reconciliations.get("missing_platform_evidence", []),
            "not_a_second_revenue_total": True,
        }

    def cash_flow_view(self, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        """Return cash-flow readiness without treating missing cash input as zero."""
        movements = list(self.cash_movements)
        if start:
            movements = [item for item in movements if item.get("date", "") >= start]
        if end:
            movements = [item for item in movements if item.get("date", "") <= end]
        return {
            "status": "awaiting_cash_inputs" if not movements else "partial",
            "movements": movements,
            "cash_balance": None,
            "known_accounts": ["platform_unsettled", "former_owner_account", "owner_cash", "owner_bank"],
            "missing_inputs": ["opening_cash", "daily_cash_count", "cash_expenses", "owner_bank_balance", "former_owner_transfer_receipts"],
            "rules": [
                "平台经营收入不等于已到账现金",
                "前老板代收不等于当前老板已收款",
                "没有现金盘点证据时不显示现金余额为 0",
                "现金流按经营、投资、筹资三类归集",
            ],
        }

    def next_id(self, prefix: str, collection: list[dict[str, Any]]) -> str:
        return f"{prefix}-{len(collection) + 1:04d}"

    def find_fact(self, fact_id: str) -> dict[str, Any]:
        for fact in self.business_facts:
            if fact["id"] == fact_id:
                return fact
        raise KeyError(f"经营事实不存在：{fact_id}")

    def raw_by_id(self, raw_id: str) -> dict[str, Any] | None:
        return next((item for item in self.raw_materials if item["id"] == raw_id), None)

    def list_facts(self, review_status: str | None = None) -> list[dict[str, Any]]:
        facts = self.business_facts
        if review_status:
            facts = [fact for fact in facts if fact.get("review_status") == review_status]
        return [self.enrich_fact(fact) for fact in facts]

    def enrich_fact(self, fact: dict[str, Any]) -> dict[str, Any]:
        return {
            **fact,
            "raw_material": self.raw_by_id(fact.get("raw_material_id", "")),
            "impact_ledger": self.fact_impact(fact),
            "profit_impact": self.profit_impact(fact),
        }

    def update_fact(self, fact_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        fact = self.find_fact(fact_id)
        editable = {
            "fact_type",
            "date",
            "amount",
            "platform",
            "account_location",
            "business_owner",
            "confidence",
            "review_status",
            "title",
            "description",
            "period_start",
            "period_end",
            "metadata",
        }
        key_fields = {"fact_type", "date", "account_location", "platform"}
        needs_recompute = any(k in patch for k in key_fields)
        for key, value in patch.items():
            if key in editable and value is not None:
                fact[key] = value
        if needs_recompute:
            fact["posting_key"] = self.compute_posting_key(fact)
        fact["state"] = "need_review" if fact.get("review_status") == "need_review" else fact.get("state", "parsed")
        self.save()
        return self.enrich_fact(fact)

    def mark_fact(self, fact_id: str, action: str) -> dict[str, Any]:
        fact = self.find_fact(fact_id)
        if action == "former_owner_collected":
            fact["fact_type"] = "former_owner_collected"
            fact["account_location"] = "former_owner_account"
            fact["platform"] = fact.get("platform") or "former_owner"
        elif action == "former_owner_transfer":
            fact["fact_type"] = "former_owner_transfer"
            fact["account_location"] = "owner_cmb_bank"
            fact["business_owner"] = "my_shop"
        elif action == "platform_unsettled":
            fact["account_location"] = platform_account(fact.get("platform", "unknown"))
        elif action == "refund":
            fact["fact_type"] = "refund"
            fact["account_location"] = "refund_deduction"
        elif action == "purchase":
            fact["fact_type"] = "purchase"
            fact["account_location"] = "owner_cmb_bank"
        elif action == "non_operating":
            fact["fact_type"] = "non_operating"
            fact["business_owner"] = "non_operating"
            fact["account_location"] = "non_operating"
        elif action == "defer":
            fact["review_status"] = "deferred"
            fact["state"] = "parsed"
        elif action == "keruyun_settlement":
            fact["account_location"] = "keruyun_pending_settlement"
        elif action == "cash":
            fact["account_location"] = "owner_cash"
            fact["platform"] = "cash"
        elif action == "group_coupon":
            fact["account_location"] = "platform_unsettled"
        elif action == "needs_reconciliation":
            fact["review_status"] = "need_review"
            fact["state"] = "need_review"
            fact["missing_fields"] = sorted(set((fact.get("missing_fields") or []) + ["需要对账确认资金位置"]))
        elif action == "pending_allocation":
            fact["metadata"] = {**(fact.get("metadata") or {}), "allocation_status": "pending_allocation"}
        elif action == "link_period":
            fact["period_start"] = fact.get("period_start") or "2026-07-01"
            fact["period_end"] = fact.get("period_end") or "2026-07-04"
        elif action == "stock_in":
            fact["fact_type"] = "stock_in"
        elif action == "purchase_not_stocked":
            fact["metadata"] = {**(fact.get("metadata") or {}), "stock_status": "purchase_record_only"}
        elif action == "stock_count":
            fact["fact_type"] = "stock_count"
        elif action == "stock_loss":
            fact["fact_type"] = "stock_loss"
        elif action == "stock_usage":
            fact["fact_type"] = "stock_usage"
        else:
            raise ValueError(f"不支持的标记动作：{action}")
        self.save()
        return self.enrich_fact(fact)

    def ingest_capture_artifact(
        self,
        *,
        source_type: str,
        fields: list[dict[str, Any]] | None = None,
        structured_artifact: dict[str, Any] | None = None,
        file_name: str = "",
        raw_text: str = "",
        evidence_image_url: str = "",
    ) -> dict[str, Any]:
        """Turn a reviewed capture artifact into pending business facts."""
        fields = fields or []
        structured_artifact = structured_artifact or {}
        payloads = structured_artifact.get("write_payloads") or {}
        field_map = {str(field.get("key")): field.get("value") for field in fields if isinstance(field, dict)}
        date = str(field_map.get("date") or "")
        if not date:
            date = str((payloads.get("purchase_order") or {}).get("date") or "")
        if not date:
            for fact_item in structured_artifact.get("facts") or []:
                if str(fact_item.get("label")) in {"单据日期", "采购日期", "日期"} and fact_item.get("value"):
                    date = str(fact_item.get("value"))
                    break
        date = date or today()
        evidence_fingerprint = hashlib.sha256(json.dumps({
            "source_type": source_type,
            "file_name": file_name,
            "fields": fields,
            "structured_artifact": structured_artifact,
            "raw_text": raw_text,
        }, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]
        raw_id = f"raw-capture-{evidence_fingerprint}"
        if any(item.get("id") == raw_id for item in self.raw_materials):
            existing = [
                self.enrich_fact(item)
                for item in self.business_facts
                if item.get("raw_material_id") == raw_id
            ]
            return {
                "raw_material": next(item for item in self.raw_materials if item.get("id") == raw_id),
                "facts": existing,
                "created": 0,
                "reused": len(existing),
            }
        source_platform = "keruyun" if source_type == "客如云日报" else "supplier" if source_type == "菜场挂账小票" else "unknown"
        raw = asdict(RawMaterial(
            id=raw_id,
            shop_id="xinyu-hengtai-dakou",
            uploaded_at=now_iso(),
            source_type="capture_screenshot",
            source_platform=source_platform,
            title=file_name or structured_artifact.get("title") or source_type,
            ocr_text=raw_text[:4000],
            ai_summary=structured_artifact.get("summary", ""),
            status="parsed",
        ))
        self.raw_materials.append(raw)

        created: list[dict[str, Any]] = []

        def number(key: str) -> float | None:
            value = field_map.get(key)
            if value in {"", None}:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def add_fact(
            fact_type: FactType,
            amount: float,
            platform: str,
            account_location: str,
            title: str,
            metadata: dict[str, Any] | None = None,
            source_group: str = "",
            confidence: str = "medium",
            missing_fields: list[str] | None = None,
        ) -> None:
            created.append(fact(
                self.next_id("fact", self.business_facts + created),
                raw_id,
                fact_type,
                date,
                round(float(amount), 2),
                platform,
                account_location,
                "my_shop",
                title,
                review_status="need_review",
                ledger_status="not_posted",
                state="need_review",
                metadata=metadata or {},
                source_group=source_group,
                source_type="capture_screenshot",
                source_platform=source_platform,
                confidence=confidence,
                missing_fields=missing_fields,
            ))

        if source_type == "客如云日报":
            op_income = number("operating_income") or number("revenue")
            if op_income is not None:
                add_fact("net_operating_income", op_income, "keruyun", "keruyun_pending_settlement", "客如云营业收入", {"revenue_basis": "net_operating_income"}, "daily_report", "high")
            order_amount = number("order_amount")
            if order_amount is not None:
                add_fact("pos_sale", order_amount, "keruyun", "keruyun_pending_settlement", "客如云订单金额", {"revenue_basis": "gross_order_amount"}, "daily_report")
            dine_in = number("dine_in_revenue")
            if dine_in is not None:
                add_fact("dine_in_income", dine_in, "keruyun", "keruyun_pending_settlement", "客如云店内营业收入", {}, "daily_report")
            third_party = number("delivery_revenue") or number("third_party_income")
            if third_party is not None:
                add_fact("third_party_income", third_party, "keruyun", "platform_unsettled", "客如云第三方营业收入", {"requires_platform_bill": True}, "daily_report")
            deductions = [
                ("merchant_discount", "merchant_discount", "商户优惠"),
                ("delivery_fee", "delivery_cost", "订单配送支出"),
                ("service_fee", "service_fee", "平台/客如云服务费"),
                ("subsidy", "subsidy_adjustment", "平台补贴调整"),
            ]
            for key, fact_type, title in deductions:
                amount = number(key)
                if amount is not None:
                    add_fact(fact_type, amount, "keruyun", "refund_deduction", title, {}, "daily_report")
            payment_methods = [
                ("cash_amount", "cash", "owner_cash", "现金收款"),
                ("wechat_amount", "wechat", "keruyun_pending_settlement", "微信收款"),
                ("alipay_amount", "alipay", "keruyun_pending_settlement", "支付宝收款"),
                ("meituan_amount", "meituan", "platform_unsettled", "美团相关收款"),
                ("taobao_flash_amount", "taobao_flash", "platform_unsettled", "淘宝闪购相关收款"),
                ("douyin_coupon_amount", "douyin", "platform_unsettled", "抖音团购券收款"),
            ]
            for key, platform, account, title in payment_methods:
                amount = number(key)
                if amount is not None:
                    add_fact("payment_method_breakdown", amount, platform, account, title, {"payment_method": platform, "not_new_revenue": True}, "payment_method")

        if source_type == "菜场挂账小票":
            supplier_credit = payloads.get("supplier_credit") or {}
            amount = supplier_credit.get("amount")
            if amount is None:
                for fact_item in structured_artifact.get("facts") or []:
                    if str(fact_item.get("label")) == "挂账金额":
                        amount = fact_item.get("value")
                        break
            try:
                payable_amount = float(amount)
            except (TypeError, ValueError):
                payable_amount = 0
            supplier = "菜场供应商"
            for fact_item in structured_artifact.get("facts") or []:
                if str(fact_item.get("label")) in {"供应商/客户", "供应商"} and fact_item.get("value"):
                    supplier = str(fact_item.get("value"))
            if payable_amount > 0:
                add_fact("supplier_invoice", payable_amount, "supplier", "supplier_payable", "菜场挂账采购应付", {"supplier": supplier, "payment_status": "unpaid", "cash_impact": 0}, "supplier_credit", "medium")
            for item in supplier_credit.get("items") or structured_artifact.get("items") or []:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                item_name = str(item.get("name") or "")
                quantity = float(item.get("quantity") or 0)
                unit_cost = float(item.get("unit_cost") or 0)
                item_id = item_id_by_name(self.inventory_items, item_name)
                missing = []
                if not item_id:
                    missing.append("item_id")
                if quantity <= 0:
                    missing.append("quantity")
                if unit_cost <= 0:
                    missing.append("unit_cost")
                add_fact(
                    "stock_in",
                    float(item.get("total") or 0),
                    "supplier",
                    "inventory",
                    f"挂账采购入库：{item.get('name')}",
                    {
                        "item_id": item_id or "",
                        "item_name": item_name,
                        "quantity": quantity,
                        "unit_cost": unit_cost,
                        "supplier": supplier,
                        "payment_status": "unpaid",
                    },
                    "supplier_credit",
                    "medium",
                    missing,
                )

        if source_type == "进货单":
            purchase_order = payloads.get("purchase_order") or {}
            supplier = str(purchase_order.get("supplier") or "待确认")
            purchase_items = [
                item for item in purchase_order.get("items") or structured_artifact.get("items") or []
                if isinstance(item, dict) and item.get("name")
            ]
            total = round(sum(
                float(item.get("quantity") or 0) * float(item.get("unit_cost") or 0)
                for item in purchase_items
            ), 2)
            if purchase_items:
                add_fact(
                    "purchase_confirmation",
                    total,
                    "supplier",
                    "inventory_pending_receipt",
                    "进货单采购确认",
                    {
                        "supplier": supplier,
                        "payment_status": "unpaid",
                        "cash_impact": 0,
                        "inventory_accounting": "asset_not_period_expense",
                        "items": purchase_items,
                    },
                    "purchase_order",
                    "medium",
                )
            for item in purchase_items:
                item_name = str(item.get("name") or "")
                quantity = float(item.get("quantity") or 0)
                unit_cost = float(item.get("unit_cost") or 0)
                missing = []
                item_id = item_id_by_name(self.inventory_items, item_name)
                if not item_id:
                    missing.append("item_id")
                if quantity <= 0:
                    missing.append("quantity")
                if unit_cost <= 0:
                    missing.append("unit_cost")
                add_fact(
                    "stock_in",
                    round(quantity * unit_cost, 2),
                    "supplier",
                    "inventory",
                    f"采购入库：{item_name}",
                    {
                        "item_id": item_id or "",
                        "item_name": item_name,
                        "quantity": quantity,
                        "unit_cost": unit_cost,
                        "supplier": supplier,
                        "payment_status": "unpaid",
                        "cash_impact": 0,
                    },
                    "purchase_order",
                    "medium",
                    missing,
                )

        if source_type in {"库存照片", "库存盘点表"}:
            observations = structured_artifact.get("items") or structured_artifact.get("facts") or []
            add_fact(
                "inventory_count_photo",
                0,
                "manual",
                "inventory_observation",
                "库存盘点证据待复核",
                {
                    "observations": observations,
                    "summary": structured_artifact.get("summary") or "",
                    "evidence_only": True,
                },
                "inventory_observation",
                "low" if source_type == "库存照片" else "medium",
                ["item_id", "quantity"],
            )

        self.business_facts.extend(created)
        self.save()
        return {"raw_material": raw, "facts": [self.enrich_fact(item) for item in created], "created": len(created)}

    def ingest_expense_candidates(
        self,
        *,
        document_key: str,
        source_type: str,
        file_name: str,
        date: str,
        expenses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Create idempotent pending facts for owner-reviewed expense fields."""
        raw_id = f"raw-capture-expense-{document_key}"
        if not any(item.get("id") == raw_id for item in self.raw_materials):
            self.raw_materials.append(asdict(RawMaterial(
                id=raw_id,
                shop_id=self.project_id,
                uploaded_at=now_iso(),
                source_type="capture_document",
                source_platform="document",
                title=file_name or source_type,
                ocr_text="",
                ai_summary=f"{source_type}老板已确认费用字段",
                status="reviewed",
            )))

        candidates: list[dict[str, Any]] = []
        for expense in expenses:
            field_key = str(expense["field"])
            fact_id = f"fact-capture-expense-{document_key}-{field_key}"
            existing = next((item for item in self.business_facts if item.get("id") == fact_id), None)
            if existing:
                candidates.append(self.enrich_fact(existing))
                continue
            candidate = fact(
                fact_id,
                raw_id,
                "operating_expense",
                date,
                float(expense["amount_minor"]) / 100,
                "document",
                "accrued_payable",
                "my_shop",
                str(expense.get("title") or source_type),
                review_status="need_review",
                ledger_status="not_posted",
                state="need_review",
                metadata={
                    "finance_account_code": str(expense["account"]),
                    "source_field": field_key,
                    "document_key": document_key,
                },
                source_group=f"capture_expense:{field_key}",
                source_type="capture_document",
                source_platform="document",
                confidence="high",
            )
            candidate["posting_key"] = f"capture:{document_key}:{field_key}"
            self.business_facts.append(candidate)
            candidates.append(self.enrich_fact(candidate))
        self.save()
        return candidates

    def compute_posting_key(self, fact: dict[str, Any]) -> str:
        return compute_posting_key_static(
            shop_id="xinyu-hengtai-dakou",
            business_date=fact.get("date", ""),
            metric_name=fact.get("fact_type", ""),
            fact_type=fact.get("fact_type", ""),
            source_platform=fact.get("source_platform") or fact.get("platform", ""),
            source_group=fact.get("source_group", ""),
            account_location=fact.get("account_location", ""),
        )

    def find_duplicate_posted(self, fact: dict[str, Any]) -> dict[str, Any] | None:
        key = fact.get("posting_key") or self.compute_posting_key(fact)
        for existing in self.business_facts:
            if existing["id"] == fact["id"]:
                continue
            if existing.get("posting_key") == key and existing.get("ledger_status") == "posted" and existing.get("evidence_role") != "supporting":
                return existing
            if existing.get("posting_key") == key and existing.get("duplicate_of"):
                return existing
        return None

    def link_supporting_evidence(self, primary_id: str, supporting_id: str) -> dict[str, Any]:
        primary = self.find_fact(primary_id)
        supporting = self.find_fact(supporting_id)
        if abs(float(primary.get("amount", 0)) - float(supporting.get("amount", 0))) > 0.01:
            supporting["evidence_role"] = "discrepancy"
            supporting["primary_evidence_id"] = primary_id
            supporting["review_status"] = "need_review"
            supporting["state"] = "need_review"
            supporting["missing_fields"] = sorted(set(
                (supporting.get("missing_fields") or []) + ["与主证据金额不一致，需人工核对"]
            ))
            if "supporting_evidence_ids" not in primary:
                primary["supporting_evidence_ids"] = []
            primary["supporting_evidence_ids"].append(supporting_id)
            self.save()
            return {"status": "discrepancy", "primary": self.enrich_fact(primary), "supporting": self.enrich_fact(supporting)}
        if primary.get("confidence") == "high" and supporting.get("confidence") == "high":
            primary["confidence"] = "high"
        elif primary.get("confidence") in {"medium", "high"} and supporting.get("confidence") in {"medium", "high"}:
            primary["confidence"] = "high"
        supporting["evidence_role"] = "supporting"
        supporting["primary_evidence_id"] = primary_id
        supporting["ledger_status"] = "duplicate_suppressed"
        supporting["review_status"] = "confirmed"
        supporting["state"] = "confirmed"
        if "supporting_evidence_ids" not in primary:
            primary["supporting_evidence_ids"] = []
        if supporting_id not in primary["supporting_evidence_ids"]:
            primary["supporting_evidence_ids"].append(supporting_id)
        self.save()
        return {"status": "linked", "primary": self.enrich_fact(primary), "supporting": self.enrich_fact(supporting)}

    def reject_fact(self, fact_id: str) -> dict[str, Any]:
        fact = self.find_fact(fact_id)
        fact["review_status"] = "rejected"
        fact["state"] = "rejected"
        fact["ledger_status"] = "not_posted"
        self.save()
        return self.enrich_fact(fact)

    def confirm_fact(self, fact_id: str) -> dict[str, Any]:
        fact = self.find_fact(fact_id)
        if fact.get("review_status") == "posted" or fact.get("ledger_status") == "posted":
            stored_result = (fact.get("metadata") or {}).get("posting_result") or {}
            return {
                "fact": self.enrich_fact(fact),
                "ledger_entries": [],
                "inventory_movements": [],
                **stored_result,
            }

        if fact.get("evidence_role") == "supporting":
            fact["review_status"] = "confirmed"
            fact["state"] = "confirmed"
            fact["ledger_status"] = "duplicate_suppressed"
            self.save()
            return {"fact": self.enrich_fact(fact), "ledger_entries": [], "inventory_movements": [], "note": "辅助证据不重复入账"}

        if not fact.get("posting_key"):
            fact["posting_key"] = self.compute_posting_key(fact)

        duplicate = self.find_duplicate_posted(fact)
        if duplicate:
            fact["duplicate_of"] = duplicate["id"]
            fact["ledger_status"] = "duplicate_suppressed"
            fact["review_status"] = "confirmed"
            fact["state"] = "confirmed"
            fact["evidence_role"] = "supporting"
            fact["primary_evidence_id"] = duplicate["id"]
            dup_support = duplicate.get("supporting_evidence_ids") or []
            if fact["id"] not in dup_support:
                dup_support.append(fact["id"])
                duplicate["supporting_evidence_ids"] = dup_support
            self.save()
            return {
                "fact": self.enrich_fact(fact),
                "ledger_entries": [],
                "inventory_movements": [],
                "duplicate_of": duplicate["id"],
                "note": "与已入账事实重复，已标记为辅助证据",
            }

        fact["review_status"] = "confirmed"
        fact["state"] = "confirmed"
        ledger_entries: list[dict[str, Any]] = []
        inventory_movements: list[dict[str, Any]] = []
        if fact["fact_type"] in MONEY_FACT_TYPES:
            ledger_entries = self.post_money_fact(fact)
            fact["affects_accounts"] = list({e["account"] for e in ledger_entries})
        if fact["fact_type"] in INVENTORY_FACT_TYPES:
            inventory_movements = self.post_inventory_fact(fact)
            fact["affects_inventory_items"] = list({m["item_id"] for m in inventory_movements})
        from core.posting_coordinator import PostingCoordinator

        finance_result = PostingCoordinator(self.project_id).sync_confirmed_fact(
            fact=fact,
            inventory_movements=inventory_movements,
            inventory_items=self.inventory_items,
        )
        fact["metadata"] = {
            **(fact.get("metadata") or {}),
            "posting_result": finance_result,
        }
        fact["ledger_status"] = "posted"
        fact["review_status"] = "posted"
        fact["state"] = "posted"
        fact["posted_at"] = now_iso()
        self.save()
        return {
            "fact": self.enrich_fact(fact),
            "ledger_entries": ledger_entries,
            "inventory_movements": inventory_movements,
            **finance_result,
        }

    def post_money_fact(self, fact: dict[str, Any]) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        fact_type = fact["fact_type"]
        amount = float(fact.get("amount") or 0)
        platform = fact.get("platform", "")
        meta = fact.get("metadata") or {}

        def add(entry_type: str, account: str, value: float, counterparty: str, notes: str = ""):
            entry = asdict(LedgerEntry(
                id=self.next_id("ledger", self.ledger_entries + entries),
                fact_id=fact["id"],
                date=fact["date"],
                entry_type=entry_type,
                amount=round(value, 2),
                account=account,
                counterparty=counterparty,
                status="posted",
                confirmed_by_owner=True,
                platform=platform,
                business_owner=fact.get("business_owner", "my_shop"),
                notes=notes,
            ))
            entries.append(entry)

        if fact_type == "net_operating_income":
            add("revenue", "keruyun_pending_settlement", amount, "客如云", "客如云营业收入，资金归属仍需按支付方式复核")
        elif fact_type == "pos_sale":
            add("revenue", "keruyun_pending_settlement", amount, "客如云", "线下销售先进入客如云待结算")
        elif fact_type == "dine_in_income":
            add("revenue", "keruyun_pending_settlement", amount, "客如云", "堂食收入先进入客如云待结算")
        elif fact_type == "third_party_income":
            add("revenue", fact.get("account_location") or "platform_unsettled", amount, "第三方平台", "第三方平台收入，资金归属待确认")
        elif fact_type == "cash_sale":
            add("revenue", "owner_cash", amount, "现金", "现金当天在老板现金")
        elif fact_type == "payment_method_breakdown":
            add("payment_method_breakdown", fact.get("account_location") or "keruyun_pending_settlement", amount, platform, "支付方式明细，只解释资金位置，不重复计营业收入")
        elif fact_type in {"meituan_delivery_sale", "taobao_delivery_sale", "jd_delivery_sale", "douyin_group_sale", "meituan_group_sale"}:
            expected = float(meta.get("expected_settlement") or amount)
            add("revenue", platform_account(platform), amount, platform, "销售发生，不等于老板已到账")
            if expected != amount:
                add("platform_deduction", "refund_deduction", round(amount - expected, 2), platform, "平台费/活动/退款等差额")
        elif fact_type in {"merchant_discount", "delivery_cost", "service_fee", "subsidy_adjustment", "platform_fee", "promotion_cost", "refund"}:
            add(fact_type, "refund_deduction", amount, platform, "平台扣款或退款")
        elif fact_type == "platform_settlement":
            add("platform_settlement", "former_owner_account", amount, platform, "平台结算进入前老板银行卡")
        elif fact_type == "former_owner_collected":
            add("receivable_from_former_owner", "former_owner_account", amount, "前老板", "前老板代收待核销")
        elif fact_type == "former_owner_transfer":
            add("receivable_repayment", "former_owner_account", -amount, "前老板", "不是新销售，冲减应收前老板（资金转移）")
            add("internal_transfer", "owner_cmb_bank", amount, "前老板", "前老板代收回款进入老板招商银行卡（资金转移，非营业收入）")
        elif fact_type == "purchase":
            add("purchase_cost", "owner_cmb_bank", -amount, meta.get("supplier", "供应商"), "采购支出")
        elif fact_type in {"supplier_invoice", "supplier_credit_purchase"}:
            add("supplier_payable", "supplier_payable", -amount, meta.get("supplier", "供应商"), "挂账采购形成应付账款，未付款前不影响现金")
        elif fact_type == "operating_expense":
            add(
                "operating_expense",
                str(meta.get("finance_account_code") or "operating_expense"),
                amount,
                str(meta.get("counterparty") or fact.get("source_platform") or "经营费用"),
                "老板确认的费用凭证",
            )
        elif fact_type == "non_operating":
            add("non_operating", "non_operating", amount, meta.get("counterparty", "未知"), "非经营款不计入销售")

        self.ledger_entries.extend(entries)
        return entries

    def post_inventory_fact(self, fact: dict[str, Any]) -> list[dict[str, Any]]:
        meta = fact.get("metadata") or {}
        movements: list[dict[str, Any]] = []
        item_id = meta.get("item_id") or item_id_by_name(self.inventory_items, meta.get("item_name", ""))
        if not item_id:
            return []
        item = next((candidate for candidate in self.inventory_items if candidate["id"] == item_id), None)
        if item is None:
            return []
        quantity = float(meta.get("quantity") or 0)
        unit_cost = float(meta.get("unit_cost") or item.get("latest_unit_cost") or 0)
        movement_type = "stock_in"
        signed_quantity = quantity
        if fact["fact_type"] == "stock_count":
            movement_type = "count_adjustment"
            signed_quantity = quantity - float(item.get("current_quantity") or 0)
        elif fact["fact_type"] == "stock_loss":
            movement_type = "loss"
            signed_quantity = -abs(quantity)
        elif fact["fact_type"] == "stock_usage":
            movement_type = "usage"
            signed_quantity = -abs(quantity)
        movement = asdict(InventoryMovement(
            id=self.next_id("inv-move", self.inventory_movements + movements),
            item_id=item_id,
            date=fact["date"],
            movement_type=movement_type,
            quantity=round(signed_quantity, 3),
            unit_cost=unit_cost,
            source_fact_id=fact["id"],
            confirmed_by_owner=True,
            notes=fact.get("description", ""),
        ))
        movements.append(movement)
        item["current_quantity"] = round(float(item.get("current_quantity") or 0) + signed_quantity, 3)
        if unit_cost > 0:
            item["latest_unit_cost"] = unit_cost
        self.inventory_movements.extend(movements)
        return movements

    def money_view(self, date: str | None = None) -> dict[str, Any]:
        entries = [entry for entry in self.ledger_entries if not date or entry["date"] == date]
        buckets = {
            "owner_cmb_bank": 0.0,
            "owner_cash": 0.0,
            "keruyun_pending_settlement": 0.0,
            "former_owner_account": 0.0,
            "platform_unsettled": 0.0,
            "refund_deduction": 0.0,
            "purchase_cost": 0.0,
            "supplier_payable": 0.0,
            "non_operating": 0.0,
        }
        platform_accounts = {
            "meituan_unsettled": 0.0,
            "taobao_unsettled": 0.0,
            "jd_unsettled": 0.0,
            "douyin_unsettled": 0.0,
            "meituan_group_unsettled": 0.0,
        }
        total_sales = 0.0
        platform_costs = 0.0
        purchase_spend = 0.0
        for entry in entries:
            account = entry["account"]
            amount = float(entry["amount"])
            if entry["entry_type"] == "revenue":
                total_sales += amount
            if account in platform_accounts:
                platform_accounts[account] += amount
                buckets["platform_unsettled"] += amount
            elif account in buckets:
                buckets[account] += amount
            if entry["entry_type"] in {"platform_deduction", "platform_fee", "promotion_cost", "refund"}:
                platform_costs += abs(amount)
            if entry["entry_type"] == "purchase_cost":
                purchase_spend += abs(amount)
        return {
            "date": date,
            "total_sales": round(total_sales, 2),
            "fixture_sales": self.fixture_sales_card(date or today()),
            "former_owner": self.former_owner_summary(date or today()),
            "accounts": {key: round(value, 2) for key, value in buckets.items()},
            "platform_accounts": {key: round(value, 2) for key, value in platform_accounts.items()},
            "platform_costs": round(platform_costs, 2),
            "purchase_spend": round(purchase_spend, 2),
            "entries": entries,
            "rules": [
                "到账截图不直接等于营业收入",
                "前老板转账是应收前老板回款，不是新销售",
                "外卖/团购销售先进入平台未结算，再进入前老板代收账户",
            ],
        }

    def inventory_view(self, date: str | None = None) -> dict[str, Any]:
        date = date or today()
        movements = [m for m in self.inventory_movements if m["date"] == date]
        by_item: dict[str, dict[str, float]] = {}
        for movement in movements:
            row = by_item.setdefault(movement["item_id"], {"stock_in": 0.0, "consumption": 0.0, "loss": 0.0, "count_adjustment": 0.0})
            mtype = movement["movement_type"]
            qty = float(movement["quantity"])
            if mtype == "stock_in":
                row["stock_in"] += qty
            elif mtype == "loss":
                row["loss"] += abs(qty)
            elif mtype in {"usage", "estimated_consumption"}:
                row["consumption"] += abs(qty)
            elif mtype == "count_adjustment":
                row["count_adjustment"] += qty
        items = []
        bom_ready_for = {bom["ingredient_item_id"] for bom in self.product_boms if bom.get("confirmed_by_owner") and bom.get("quantity_per_unit") is not None}
        has_opening_count = any(f.get("fact_type") == "stock_count" and f.get("ledger_status") == "posted" for f in self.business_facts if f.get("date") == date)
        for item in self.inventory_items:
            row = by_item.get(item["id"], {})
            current = float(item.get("current_quantity") or 0)
            safe = float(item.get("safe_stock") or 0)
            recommend_qty = max(0, safe * 1.5 - current)
            theoretical_calculable = item["id"] in bom_ready_for
            actual_calculable = has_opening_count and bool(row.get("stock_in"))
            item_info = {
                **item,
                "evidence_source": item.get("evidence_source", "seed"),
                "confirmation_status": item.get("confirmation_status", "待确认"),
                "latest_unit_cost_source": item.get("latest_unit_cost_source", "7/6 进货单"),
                "owner_confirmed": item.get("owner_confirmed", False),
                "today_stock_in": round(row.get("stock_in", 0), 3),
                "today_estimated_consumption": round(row.get("consumption", 0), 3),
                "today_loss": round(row.get("loss", 0), 3),
                "today_count_adjustment": round(row.get("count_adjustment", 0), 3),
                "risk_level": "high" if current <= safe * 0.5 else "watch" if current <= safe else "ok",
                "purchase_recommendation": round(recommend_qty, 2),
                "theoretical_consumption_calculable": theoretical_calculable,
                "theoretical_consumption_reason": "" if theoretical_calculable else "缺少 BOM 用量，理论消耗不可算",
                "actual_consumption_calculable": actual_calculable,
                "actual_consumption_reason": "" if actual_calculable else "缺少期初/期末盘点，实际消耗不可算",
                "variance_calculable": theoretical_calculable and actual_calculable,
                "inventory_value_basis": f"按{item.get('latest_unit_cost_source', '最近采购价')}估算，非精确成本",
            }
            items.append(item_info)
        count_dates = [
            str(fact.get("date"))
            for fact in self.business_facts
            if fact.get("fact_type") == "stock_count" and fact.get("date")
        ]
        return {
            "date": date,
            "last_count_date": max(count_dates) if count_dates else None,
            "pending_inventory_facts": len([f for f in self.business_facts if f.get("review_status") == "need_review" and f.get("fact_type") in INVENTORY_FACT_TYPES]),
            "inventory_value_basis": (
                "库存账面金额按最近采购价估算；低置信度盘点或进货字段仍需老板确认。"
                if items else "尚无已登记库存资料，不能计算库存金额。"
            ),
            "bom_cost_status": "BOM 缺粉、酱料、木鱼花、海苔等克重，不允许给出确定单盒成本。",
            "items": items,
            "movements": movements,
            "alerts": self.inventory_alerts(items),
            "consumption_methods": {
                "theoretical": "销量 × BOM 理论用量",
                "actual": "期初库存 + 今日入库 - 期末库存",
            },
        }

    def today_card(self, date: str | None = None) -> dict[str, Any]:
        date = date or today()
        money = self.money_view(date)
        inventory = self.inventory_view(date)
        accounts = money["accounts"]
        estimated_inventory_cost = sum(
            abs(float(m["quantity"])) * float(m["unit_cost"])
            for m in inventory["movements"]
            if m["movement_type"] in {"usage", "estimated_consumption", "loss"}
        )
        estimated_profit = (
            money["total_sales"]
            - money["platform_costs"]
            - money["purchase_spend"]
            - estimated_inventory_cost
        )
        questions = self.gap_questions(date)
        tomorrow_actions = []
        for alert in inventory["alerts"][:3]:
            tomorrow_actions.append(f"补货或盘点：{alert['title']}")
        if accounts["former_owner_account"] > 0:
            tomorrow_actions.append("向前老板核对线上款是否已转")
        if not tomorrow_actions:
            tomorrow_actions.append("继续上传今日销售、到账和复盘库存证据")
        source_ids = {
            str(item.get("raw_material_id"))
            for item in self.business_facts
            if item.get("date") == date and item.get("raw_material_id")
        }
        sources = [
            str(item.get("title"))
            for item in self.raw_materials
            if item.get("id") in source_ids and item.get("title")
        ]
        return {
            "date": date,
            "sales": self.sales_breakdown(date),
            "fixture_sales": self.fixture_sales_card(date),
            "sources": sources,
            "money_where": money,
            "today_purchase_spend": money["purchase_spend"],
            "today_inventory_consumption_estimate": round(estimated_inventory_cost, 2),
            "estimated_profit": None,
            "profit_statement": "利润暂不能精确确认；成本、BOM 与盘点字段未确认时，只能显示经营净收入已确认/待确认。",
            "missing_fields": questions,
            "tomorrow_actions": tomorrow_actions,
        }

    def fixture_sales_card(self, date: str) -> dict[str, Any]:
        if date != REAL_FIXTURE_DATE:
            return {}
        return {
            "source": "7/4 客如云营业日报",
            "sales": {
                "order_amount": 2080.34,
                "net_operating_income": 1794.8,
                "order_count": 114,
                "sales_orders": 113,
                "refund_orders": 1,
                "dine_in_income": 1609.03,
                "third_party_income": 185.77,
            },
            "deductions": {
                "merchant_discount": 123.25,
                "delivery_cost": 45.7,
                "service_fee": 101.27,
                "subsidy_adjustment": -15.32,
            },
            "products": [
                {"name": "经典必吃", "quantity": 82, "amount": 1338.0, "source": "7/4 客如云营业日报"},
                {"name": "外部商品", "quantity": 13, "amount": 382.54, "source": "7/4 客如云营业日报"},
                {"name": "夹心大丸", "quantity": 7, "amount": 126.0, "source": "7/4 客如云营业日报"},
            ],
            "money": [
                {"label": "现金", "amount": 185.0, "status": "需老板确认", "source": "7/4 客如云营业概况"},
                {"label": "微信", "amount": 956.0, "status": "归入客如云/老板结算，需确认", "source": "7/4 客如云营业概况"},
                {"label": "支付宝", "amount": 166.0, "status": "归入客如云/老板结算，需确认", "source": "7/4 客如云营业概况"},
                {"label": "第三方收入", "amount": 185.77, "status": "需确认平台未结算还是前老板代收", "source": "7/4 客如云营业日报"},
                {"label": "抖音团购券", "amount": 226.76, "status": "需要确认结算状态", "source": "7/4 客如云营业概况"},
                {"label": "美团团购券", "amount": 75.27, "status": "需要确认结算状态", "source": "7/4 客如云营业概况"},
            ],
            "inventory": {
                "status": "已关联 7/4 盘点表，手写字段未确认；库存消耗暂不能正式入账。",
                "source": "7/4 盘点表 / 7/6 进货单",
            },
            "profit": {
                "confirmed": "经营净收入 1794.8 来自 7/4 客如云营业日报，仍需确认资金归属。",
                "pending": "利润暂不能精确确认；成本、BOM、盘点和平台结算状态未确认。",
            },
        }

    def former_owner_summary(self, date: str) -> dict[str, Any]:
        return {
            "receivable_from_former_owner": "待确认",
            "transferred_to_owner": "待确认",
            "pending_allocation": "微信聊天截图提到回款，待关联日期区间",
            "unsettled": "待确认",
            "rule": "前老板转账不是新收入，是应收回款。",
        }

    def sales_breakdown(self, date: str) -> dict[str, float]:
        result = {
            "keruyun_pos": 0.0,
            "cash": 0.0,
            "meituan_delivery": 0.0,
            "taobao_delivery": 0.0,
            "jd_delivery": 0.0,
            "douyin_group": 0.0,
            "meituan_group": 0.0,
        }
        mapping = {
            "pos_sale": "keruyun_pos",
            "cash_sale": "cash",
            "meituan_delivery_sale": "meituan_delivery",
            "taobao_delivery_sale": "taobao_delivery",
            "jd_delivery_sale": "jd_delivery",
            "douyin_group_sale": "douyin_group",
            "meituan_group_sale": "meituan_group",
        }
        for fact in self.business_facts:
            if fact.get("date") == date and fact.get("ledger_status") == "posted":
                key = mapping.get(fact.get("fact_type"))
                if key:
                    result[key] += float(fact.get("amount") or 0)
        result["total"] = round(sum(result.values()), 2)
        return {key: round(value, 2) for key, value in result.items()}

    def gap_questions(self, date: str | None = None) -> list[dict[str, Any]]:
        date = date or today()
        facts_today = [f for f in self.business_facts if f.get("date") == date and f.get("review_status") in {"need_review", "parsed"}]
        gaps = []
        for fact in facts_today:
            if fact.get("missing_fields"):
                gaps.append(gap("、".join(fact["missing_fields"]), "字段不完整，AI 不能直接入账", "正式钱账/库存账", "打开今日待确认逐条确认或修改", "P0"))
        if not any(f.get("fact_type") == "stock_count" and f.get("date") == date and f.get("ledger_status") == "posted" for f in self.business_facts):
            gaps.append(gap("复盘库存盘点", "缺少期末库存，实际消耗暂不能确认", "库存消耗和今日利润", "拍冰柜、粉、章鱼粒、酱料、盒子照片", "P1"))
        if not self.bom_ready("经典原味", "基础 6 粒"):
            gaps.append(gap("6 粒章鱼烧 BOM 克重", "缺原料规格和每盒用量，不能精确算单盒成本", "单品成本和外卖最低售价", "记录一包粉/章鱼粒能做多少盒，并称一次酱料、沙拉酱、木鱼花用量", "P1"))
        if not any(f.get("fact_type") in {"platform_fee", "promotion_cost"} and f.get("date") == date and f.get("ledger_status") == "posted" for f in self.business_facts):
            gaps.append(gap("平台费和活动补贴截图", "外卖/团购到手金额不能只看销售额", "线上渠道利润", "上传美团、淘宝闪购、京东、抖音或团购今日账单页", "P1"))
        return gaps[:6]

    def cost_question(self, question: str) -> dict[str, Any]:
        known = [
            "一盒基础 6 粒至少需要 6 个章鱼粒。",
        ]
        for bom in self.product_boms:
            if bom["variant"] == "基础 6 粒" and bom.get("confirmed_by_owner") and bom.get("quantity_per_unit") is not None:
                item = next((i for i in self.inventory_items if i["id"] == bom["ingredient_item_id"]), None)
                if item:
                    known.append(f"{item['name']}：{bom['quantity_per_unit']}{bom['unit']}，最近采购价 ¥{item['latest_unit_cost']}/{item['unit']}")
        missing = [
            "章鱼粒每包规格/粒数或克重",
            "章鱼预拌粉每包规格",
            "一包粉可做多少盒 6 粒",
            "每盒酱料克重",
            "每盒沙拉酱克重",
            "每盒木鱼花克重",
            "每盒海苔粉/切丝海苔用量",
            "油、电、水、损耗摊销",
            "堂食/外卖包装差异",
            "平台抽佣和活动补贴",
        ]
        return {
            "question": question,
            "answer": "目前不能精确确认 6 粒章鱼烧真实成本，只能列出已知和缺失字段。",
            "known_costs": known,
            "missing_fields": missing,
            "can_estimate_from": [
                "按一段时间销量和采购消耗反推理论单盒成本",
                "按盘点差异反推实际单盒成本",
            ],
            "follow_up": gap("6 粒章鱼烧 BOM", "缺少原料规格和每盒用量", "单盒成本、毛利和最低售价", "称一次 6 粒出品的酱料/粉/木鱼花/海苔用量，并记录一包章鱼粒能做多少盒", "P1"),
        }

    def daily_close_check(self, date: str | None = None) -> dict[str, Any]:
        date = date or REAL_FIXTURE_DATE
        facts_today = [f for f in self.business_facts if f.get("date") == date]
        confirmed_facts = [f for f in facts_today if f.get("review_status") in {"confirmed", "posted"}]
        pending_facts = [f for f in facts_today if f.get("review_status") in {"need_review", "parsed"}]
        posted_facts = [f for f in facts_today if f.get("ledger_status") == "posted"]

        duplicate_risks = [
            f for f in facts_today
            if f.get("duplicate_of") and f.get("evidence_role") not in {"supporting"}
        ] + [
            f for f in facts_today
            if f.get("evidence_role") == "discrepancy"
        ]

        low_confidence_inventory = [
            f for f in facts_today
            if f.get("fact_type") in INVENTORY_FACT_TYPES and f.get("confidence") == "low"
        ]
        low_conf_inv_items = [
            item for item in self.inventory_items
            if item.get("confirmation_status") in {"低置信度", "low", "待确认"}
        ]

        missing_cost_fields = []
        if not any(f.get("fact_type") == "stock_count" and f.get("ledger_status") == "posted" for f in facts_today):
            missing_cost_fields.append("期末盘点未确认")
        if not self.bom_ready("经典原味", "基础 6 粒"):
            missing_cost_fields.append("BOM 克重未确认")
        if not any(f.get("fact_type") in {"platform_fee", "promotion_cost", "service_fee", "merchant_discount"} and f.get("ledger_status") == "posted" for f in facts_today):
            missing_cost_fields.append("平台费/活动补贴未确认")

        blocking_reasons: list[str] = []
        next_actions: list[str] = []

        kyy_daily_posted = any(
            f.get("fact_type") == "net_operating_income"
            and f.get("ledger_status") == "posted"
            and f.get("evidence_role") != "supporting"
            for f in facts_today
        )
        if not kyy_daily_posted:
            blocking_reasons.append("客如云营业日报营业收入还未确认入账")
            revenue_candidate = next(
                (
                    f for f in facts_today
                    if f.get("fact_type") == "net_operating_income"
                    and f.get("evidence_role") != "supporting"
                ),
                None,
            )
            revenue_hint = (
                f"营业收入 {float(revenue_candidate.get('amount') or 0):g} 元"
                if revenue_candidate and revenue_candidate.get("amount") is not None
                else "营业收入"
            )
            next_actions.append(f"在录入页确认 {date} 客如云营业日报{revenue_hint}")

        cash_candidate = next(
            (
                f for f in facts_today
                if f.get("fact_type") == "payment_method_breakdown"
                and f.get("platform") == "cash"
            ),
            None,
        )
        cash_confirmed = any(
            f.get("fact_type") == "payment_method_breakdown"
            and f.get("platform") == "cash"
            and f.get("account_location") == "owner_cash"
            and f.get("review_status") in {"confirmed", "posted"}
            for f in facts_today
        )
        if not cash_confirmed:
            if cash_candidate and cash_candidate.get("amount") is not None:
                cash_amount = float(cash_candidate.get("amount") or 0)
                blocking_reasons.append(f"{date} 现金 {cash_amount:g} 元还未确认是否在店内")
                next_actions.append(f"在录入页确认 {date} 现金 {cash_amount:g} 元的实际位置")
            else:
                blocking_reasons.append(f"{date} 现金收款和店内实点尚未确认")
                next_actions.append(f"补录 {date} 现金收款，并确认打烊实点金额")

        third_party_settled = all(
            f.get("review_status") in {"confirmed", "posted"}
            for f in facts_today
            if f.get("fact_type") == "third_party_income"
            or (f.get("fact_type") == "payment_method_breakdown" and f.get("platform") in {"meituan", "taobao_flash", "jd_delivery", "douyin", "meituan_group"})
        )
        if not third_party_settled:
            blocking_reasons.append("第三方收入 185.77 元还未确认是平台未结算还是前老板代收")
            next_actions.append("在录入页为美团/淘宝/抖音等第三方收入标记结算状态")

        if duplicate_risks:
            blocking_reasons.append(f"存在 {len(duplicate_risks)} 条重复入账风险，请核对")
            next_actions.append("在录入页核对重复风险的事实，确认为辅助证据或驳回")

        if low_conf_inv_items:
            low_names = "、".join(item["name"] for item in low_conf_inv_items[:3])
            blocking_reasons.append(f"最近库存基线中 {low_names} 为低置信度，暂不能形成完整复盘")
            next_actions.append(f"在录入页或库存页补录 {date} 的实际库存，确认低置信度物料数量并覆盖旧基线")

        can_close = len(blocking_reasons) == 0
        close_status = "can_close" if can_close else ("partial" if len(blocking_reasons) <= 2 else "blocked")

        posted_amount = sum(
            float(f.get("amount") or 0)
            for f in posted_facts
            if f.get("fact_type") in {"net_operating_income", "dine_in_income", "third_party_income", "pos_sale", "cash_sale"}
            and f.get("evidence_role") != "supporting"
        )
        pending_amount = sum(
            float(f.get("amount") or 0)
            for f in pending_facts
            if f.get("fact_type") in {"net_operating_income", "dine_in_income", "third_party_income", "pos_sale", "cash_sale"}
        )

        evidence_summary = {
            "primary_evidence_count": len([f for f in facts_today if f.get("evidence_role") == "primary"]),
            "supporting_evidence_count": len([f for f in facts_today if f.get("evidence_role") == "supporting"]),
            "discrepancy_count": len([f for f in facts_today if f.get("evidence_role") == "discrepancy"]),
            "raw_materials_today": len({f.get("raw_material_id") for f in facts_today}),
        }

        return {
            "date": date,
            "can_close": can_close,
            "close_status": close_status,
            "confirmed_facts_count": len(confirmed_facts),
            "pending_facts_count": len(pending_facts),
            "posted_entries_count": len(posted_facts),
            "duplicate_risks_count": len(duplicate_risks),
            "low_confidence_inventory_count": len(low_conf_inv_items),
            "missing_cost_fields": missing_cost_fields,
            "blocking_reasons": blocking_reasons,
            "next_actions": next_actions,
            "confirmed_amount": round(posted_amount, 2),
            "pending_amount": round(pending_amount, 2),
            "evidence_summary": evidence_summary,
        }

    def bom_ready(self, product_name: str, variant: str) -> bool:
        boms = [bom for bom in self.product_boms if bom["product_name"] == product_name and bom["variant"] == variant]
        return bool(boms) and all(bom.get("confirmed_by_owner") and bom.get("quantity_per_unit") is not None for bom in boms)

    def fact_impact(self, fact: dict[str, Any]) -> str:
        fact_type = fact.get("fact_type")
        if fact_type in {"pos_sale", "net_operating_income", "dine_in_income", "third_party_income", "cash_sale", "meituan_delivery_sale", "taobao_delivery_sale", "jd_delivery_sale", "douyin_group_sale", "meituan_group_sale"}:
            return "销售收入 + 资金位置"
        if fact_type in {"platform_fee", "promotion_cost", "refund"}:
            return "平台成本 / 到手利润"
        if fact_type in {"former_owner_collected", "former_owner_transfer", "platform_settlement"}:
            return "钱在哪里 / 应收前老板"
        if fact_type in INVENTORY_FACT_TYPES:
            return "库存账 / 采购建议"
        if fact_type == "non_operating":
            return "非经营款，不计入销售"
        return "待人工判断"

    def profit_impact(self, fact: dict[str, Any]) -> bool:
        no_profit_types = {"former_owner_transfer", "former_owner_collected", "non_operating", "unknown", "platform_settlement", "payment_method_breakdown", "channel_sales_breakdown"}
        return fact.get("fact_type") not in no_profit_types

    def inventory_alerts(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        alerts = []
        for item in items:
            if item["risk_level"] == "high":
                alerts.append({"level": "P0", "title": f"{item['name']}可能断货", "body": f"当前 {item['current_quantity']}{item['unit']}，安全库存 {item['safe_stock']}{item['unit']}"})
            elif item["today_loss"] > 0:
                alerts.append({"level": "P1", "title": f"{item['name']}有报损", "body": f"今日报损 {item['today_loss']}{item['unit']}，需要核对原因"})
        return alerts

    def seed_real_store(self) -> None:
        d = REAL_FIXTURE_DATE
        self.inventory_items = seed_inventory_items()
        self.products, self.product_variants, self.channel_prices, self.product_boms = seed_products_and_bom()
        raw_defs = [
            ("raw-kyy-daily-20260704", "real_fixture_screenshot", "keruyun", "7/4 客如云营业日报", "订单金额 2080.34，营业收入 1794.8，订单数 114"),
            ("raw-kyy-overview-20260704", "real_fixture_screenshot", "keruyun", "7/4 客如云营业概况", "微信 956，现金 185，支付宝 166，团购券与外卖渠道待对账"),
            ("raw-stock-20260704", "real_fixture_photo", "manual", "7/4 大口章鱼烧物料盘点表", "手写盘点字段低置信度，库存消耗不能直接入账"),
            ("raw-purchase-20260706", "real_fixture_photo", "supplier", "7/6 大口章鱼烧供应链进货单", "鲜章鱼粒、章鱼粉、竹签、外卖无纺袋、纸巾、章鱼预拌粉等"),
            ("raw-wechat-long", "real_fixture_screenshot", "wechat", "微信聊天长截图", "前老板回款、平台结算、采购确认等聊天事实均需复核"),
        ]
        self.raw_materials = [
            asdict(RawMaterial(
                id=raw_id,
                shop_id=self.project_id,
                uploaded_at=now_iso(),
                source_type=source_type,
                source_platform=platform,
                title=title,
                ai_summary=summary,
            ))
            for raw_id, source_type, platform, title, summary in raw_defs
        ]

        posted_facts = [
            fact("fact-kyy-net-income", "raw-kyy-daily-20260704", "net_operating_income", d, 1794.8, "keruyun", "keruyun_pending_settlement", "my_shop",
                 "7/4 营业收入（主证据：营业日报）",
                 source_group="daily_report",
                 source_type="real_fixture_screenshot",
                 source_platform="keruyun",
                 affects_accounts=["keruyun_pending_settlement"],
                 metadata={"source": "7/4 客如云营业日报", "evidence_role_note": "营业日报是营业收入主证据"}),
        ]
        review_facts = [
            fact("fact-kyy-overview-net-income", "raw-kyy-overview-20260704", "net_operating_income", d, 1794.8, "keruyun", "keruyun_pending_settlement", "my_shop",
                 "7/4 营业收入（辅助证据：营业概况）",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 evidence_role="supporting",
                 primary_evidence_id="fact-kyy-net-income",
                 source_group="overview",
                 source_type="real_fixture_screenshot",
                 source_platform="keruyun",
                 metadata={"source": "7/4 客如云营业概况", "derived_from": "支付方式汇总", "evidence_role_note": "营业概况与日报金额一致，作为辅助证据增强置信度"}),
            fact("fact-kyy-order-amount", "raw-kyy-daily-20260704", "pos_sale", d, 2080.34, "keruyun", "keruyun_pending_settlement", "my_shop",
                 "订单金额 2080.34（主证据：营业日报）",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 source_group="daily_report",
                 source_type="real_fixture_screenshot",
                 source_platform="keruyun",
                 metadata={"source": "7/4 客如云营业日报", "orders": 114, "sales_orders": 113}),
            fact("fact-kyy-overview-order-amount", "raw-kyy-overview-20260704", "pos_sale", d, 2080.34, "keruyun", "keruyun_pending_settlement", "my_shop",
                 "订单金额 2080.34（辅助证据：营业概况）",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 evidence_role="supporting",
                 primary_evidence_id="fact-kyy-order-amount",
                 source_group="overview",
                 source_type="real_fixture_screenshot",
                 source_platform="keruyun",
                 metadata={"source": "7/4 客如云营业概况", "derived_from": "渠道汇总", "evidence_role_note": "渠道汇总与日报订单金额一致"}),
            fact("fact-kyy-dine-in", "raw-kyy-daily-20260704", "dine_in_income", d, 1609.03, "keruyun", "keruyun_pending_settlement", "my_shop",
                 "店内营业收入 1609.03",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 source_group="daily_report", source_type="real_fixture_screenshot", source_platform="keruyun",
                 affects_accounts=["keruyun_pending_settlement"]),
            fact("fact-kyy-third-party", "raw-kyy-daily-20260704", "third_party_income", d, 185.77, "keruyun", "platform_unsettled", "my_shop",
                 "第三方营业收入 185.77",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["确认平台未结算还是前老板代收"],
                 source_group="daily_report", source_type="real_fixture_screenshot", source_platform="keruyun",
                 affects_accounts=["platform_unsettled"]),
            fact("fact-kyy-discount", "raw-kyy-daily-20260704", "merchant_discount", d, 123.25, "keruyun", "refund_deduction", "my_shop",
                 "商户优惠 123.25",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 source_group="daily_report", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-kyy-delivery-cost", "raw-kyy-daily-20260704", "delivery_cost", d, 45.7, "keruyun", "refund_deduction", "my_shop",
                 "订单配送支出 45.70",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 source_group="daily_report", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-kyy-service-fee", "raw-kyy-daily-20260704", "service_fee", d, 101.27, "keruyun", "refund_deduction", "my_shop",
                 "服务费 101.27",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 source_group="daily_report", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-kyy-subsidy", "raw-kyy-daily-20260704", "subsidy_adjustment", d, -15.32, "keruyun", "refund_deduction", "my_shop",
                 "补贴 -15.32",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 source_group="daily_report", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-kyy-refund-order", "raw-kyy-daily-20260704", "refund", d, 1, "keruyun", "refund_deduction", "my_shop",
                 "退款订单 1 笔",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 source_group="daily_report", source_type="real_fixture_screenshot", source_platform="keruyun",
                 metadata={"unit": "order_count"}),
            fact("fact-pay-wechat", "raw-kyy-overview-20260704", "payment_method_breakdown", d, 956, "wechat", "keruyun_pending_settlement", "my_shop",
                 "微信 956.00",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["是否 T+1 到招行卡"],
                 source_group="overview", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-pay-douyin", "raw-kyy-overview-20260704", "payment_method_breakdown", d, 226.76, "douyin", "platform_unsettled", "my_shop",
                 "抖音团购券 226.76",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["结算状态"],
                 source_group="overview", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-pay-cash", "raw-kyy-overview-20260704", "payment_method_breakdown", d, 185, "cash", "owner_cash", "my_shop",
                 "现金 185.00",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["老板现金是否已收"],
                 source_group="overview", source_type="real_fixture_screenshot", source_platform="keruyun",
                 affects_accounts=["owner_cash"]),
            fact("fact-pay-alipay", "raw-kyy-overview-20260704", "payment_method_breakdown", d, 166, "alipay", "keruyun_pending_settlement", "my_shop",
                 "支付宝 166.00",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["是否 T+1 到招行卡"],
                 source_group="overview", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-pay-taobao", "raw-kyy-overview-20260704", "payment_method_breakdown", d, 104.37, "taobao_flash", "platform_unsettled", "my_shop",
                 "淘宝闪购餐饮 104.37",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["平台未结算/前老板代收/已回款"],
                 source_group="overview", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-pay-meituan", "raw-kyy-overview-20260704", "payment_method_breakdown", d, 81.4, "meituan", "platform_unsettled", "my_shop",
                 "美团外卖 81.40",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["平台未结算/前老板代收/已回款"],
                 source_group="overview", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-pay-meituan-coupon", "raw-kyy-overview-20260704", "payment_method_breakdown", d, 75.27, "meituan_group", "platform_unsettled", "my_shop",
                 "美团团购券 75.27",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["结算状态"],
                 source_group="overview", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-channel-android", "raw-kyy-overview-20260704", "channel_sales_breakdown", d, 1666.6, "android_pos", "keruyun_pending_settlement", "my_shop",
                 "Android 收银终端 1666.60",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 source_group="overview", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-channel-taobao", "raw-kyy-overview-20260704", "channel_sales_breakdown", d, 224.01, "taobao_flash", "platform_unsettled", "my_shop",
                 "淘宝闪购 224.01",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 source_group="overview", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-channel-meituan", "raw-kyy-overview-20260704", "channel_sales_breakdown", d, 188.73, "meituan", "platform_unsettled", "my_shop",
                 "美团外卖 188.73",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 source_group="overview", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-channel-qr", "raw-kyy-overview-20260704", "channel_sales_breakdown", d, 1, "mini_program", "keruyun_pending_settlement", "my_shop",
                 "二代码支付小程序 1.00",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 source_group="overview", source_type="real_fixture_screenshot", source_platform="keruyun"),
            fact("fact-stock-photo", "raw-stock-20260704", "inventory_count_photo", d, 0, "manual", "inventory", "my_shop",
                 "7/4 盘点表照片",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["手写字段待确认"],
                 source_type="real_fixture_photo", source_platform="manual",
                 metadata={"source": "7/4 盘点表"}),
            fact("fact-stock-count", "raw-stock-20260704", "stock_count", d, 0, "manual", "inventory", "my_shop",
                 "7/4 物料盘点",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["章鱼粒/粉/木鱼花数量需确认"],
                 confidence="low",
                 source_type="real_fixture_photo", source_platform="manual",
                 affects_inventory_items=["inv-octopus", "inv-powder", "inv-bonito"],
                 metadata={"item_id": "inv-octopus", "quantity": 2, "unit_cost": 60}),
            fact("fact-stock-usage", "raw-stock-20260704", "stock_usage", d, 0, "manual", "inventory", "my_shop",
                 "7/4 库存消耗",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["期初库存", "期末库存", "BOM 克重"],
                 source_type="real_fixture_photo", source_platform="manual"),
            fact("fact-stock-adjustment", "raw-stock-20260704", "stock_adjustment", d, 0, "manual", "inventory", "my_shop",
                 "7/4 库存调整",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["调整原因"],
                 source_type="real_fixture_photo", source_platform="manual"),
            fact("fact-purchase-invoice", "raw-purchase-20260706", "supplier_invoice", "2026-07-06", 0, "supplier", "inventory", "my_shop",
                 "7/6 供应链进货单",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["部分数量/单价需复核"],
                 source_type="real_fixture_photo", source_platform="supplier",
                 metadata={"items": ["鲜章鱼粒", "章鱼粉", "竹签", "外卖无纺袋", "纸巾", "章鱼预拌粉", "章鱼烧盒子", "香甜酱", "调料包", "全家福打包盒", "培根丁", "泡椒", "章鱼花", "木鱼花"]}),
            fact("fact-purchase", "raw-purchase-20260706", "purchase", "2026-07-06", 0, "supplier", "owner_cmb_bank", "my_shop",
                 "7/6 采购付款待确认",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["总金额", "付款账户"],
                 source_type="real_fixture_photo", source_platform="supplier",
                 affects_accounts=["owner_cmb_bank"]),
            fact("fact-stock-in", "raw-purchase-20260706", "stock_in", "2026-07-06", 0, "supplier", "inventory", "my_shop",
                 "7/6 到货入库待确认",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["实际到货数量"],
                 source_type="real_fixture_photo", source_platform="supplier",
                 affects_inventory_items=["inv-octopus", "inv-powder", "inv-box6", "inv-bonito"]),
            fact("fact-wechat-former-transfer", "raw-wechat-long", "former_owner_transfer", d, 0, "wechat", "owner_cmb_bank", "my_shop",
                 "微信聊天：前老板回款",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["金额", "对应日期区间"],
                 source_type="real_fixture_screenshot", source_platform="wechat",
                 affects_accounts=["owner_cmb_bank", "former_owner_account"]),
            fact("fact-wechat-former-collected", "raw-wechat-long", "former_owner_collected", d, 0, "wechat", "former_owner_account", "my_shop",
                 "微信聊天：前老板代收",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["平台", "金额", "是否已转回"],
                 source_type="real_fixture_screenshot", source_platform="wechat",
                 affects_accounts=["former_owner_account"]),
            fact("fact-wechat-platform", "raw-wechat-long", "platform_settlement", d, 0, "wechat", "platform_unsettled", "my_shop",
                 "微信聊天：平台结算",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["结算平台", "到账账户"],
                 source_type="real_fixture_screenshot", source_platform="wechat"),
            fact("fact-wechat-purchase", "raw-wechat-long", "purchase_confirmation", d, 0, "wechat", "owner_cmb_bank", "my_shop",
                 "微信聊天：采购确认",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["采购单据关联"],
                 source_type="real_fixture_screenshot", source_platform="wechat"),
            fact("fact-wechat-note", "raw-wechat-long", "manual_note", d, 0, "wechat", "unknown", "my_shop",
                 "微信聊天：人工备注",
                 review_status="need_review", ledger_status="not_posted", state="need_review",
                 missing_fields=["老板确认含义"],
                 source_type="real_fixture_screenshot", source_platform="wechat"),
        ]
        self.business_facts = posted_facts + review_facts
        self.ledger_entries = []
        self.inventory_movements = [
            asdict(InventoryMovement("inv-move-seed-usage", "inv-octopus", d, "estimated_consumption", -1.5, 60, "seed-sales-bom", True, "按今日销量暂估章鱼粒消耗")),
            asdict(InventoryMovement("inv-move-seed-bonito", "inv-bonito", d, "estimated_consumption", -0.35, 45, "seed-sales-bom", True, "木鱼花消耗偏高，待盘点")),
        ]
        for seed_fact in list(self.business_facts):
            if seed_fact["ledger_status"] == "posted":
                seed_fact["ledger_status"] = "not_posted"
                seed_fact["review_status"] = "confirmed"
                seed_fact["state"] = "confirmed"
                self.confirm_fact(seed_fact["id"])

        self.link_supporting_evidence("fact-kyy-net-income", "fact-kyy-overview-net-income")
        self.link_supporting_evidence("fact-kyy-order-amount", "fact-kyy-overview-order-amount")


def fact(
    fact_id: str,
    raw_id: str,
    fact_type: FactType,
    date: str,
    amount: float,
    platform: str,
    account_location: str,
    business_owner: str,
    title: str,
    review_status: str = "confirmed",
    ledger_status: str = "posted",
    state: str = "posted",
    missing_fields: list[str] | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    metadata: dict[str, Any] | None = None,
    evidence_role: str = "primary",
    primary_evidence_id: str = "",
    source_group: str = "",
    source_type: str = "",
    source_platform: str = "",
    affects_accounts: list[str] | None = None,
    affects_inventory_items: list[str] | None = None,
    confidence: str | None = None,
    evidence_image_url: str = "",
) -> dict[str, Any]:
    md = metadata or {}
    if confidence is not None:
        conf = confidence
    else:
        conf = "medium" if missing_fields else "high"
    posting_key = compute_posting_key_static(
        shop_id="xinyu-hengtai-dakou",
        business_date=date,
        metric_name=fact_type,
        fact_type=fact_type,
        source_platform=source_platform or platform,
        source_group=source_group or md.get("source_group", ""),
        account_location=account_location,
    )
    return asdict(BusinessFact(
        id=fact_id,
        raw_material_id=raw_id,
        fact_type=fact_type,
        date=date,
        amount=amount,
        platform=platform,
        account_location=account_location,
        business_owner=business_owner,
        confidence=conf,
        review_status=review_status,
        ledger_status=ledger_status,
        state=state,
        title=title,
        description=title,
        affects=[],
        missing_fields=missing_fields or [],
        period_start=period_start,
        period_end=period_end,
        metadata=md,
        posting_key=posting_key,
        evidence_role=evidence_role,
        primary_evidence_id=primary_evidence_id,
        supporting_evidence_ids=[],
        duplicate_of="",
        source_type=source_type,
        source_platform=source_platform or platform,
        source_date=date,
        evidence_image_url=evidence_image_url,
        evidence_file_ref="",
        extracted_fields={},
        posted_at="",
        posted_by="owner",
        affects_accounts=affects_accounts or [],
        affects_inventory_items=affects_inventory_items or [],
        source_group=source_group,
    ))


def compute_posting_key_static(
    shop_id: str,
    business_date: str,
    metric_name: str,
    fact_type: str,
    source_platform: str,
    source_group: str = "",
    account_location: str = "",
) -> str:
    parts = [shop_id, business_date, source_platform, source_group or fact_type, metric_name]
    if account_location:
        parts.append(account_location)
    return ":".join(p for p in parts if p)


def gap(missing: str, why: str, impact: str, action: str, priority: str) -> dict[str, str]:
    return {
        "missing": missing,
        "why": why,
        "impact": impact,
        "action": action,
        "priority": priority,
        "text": f"【缺口追问】\n缺什么：{missing}\n为什么缺：{why}\n影响哪个结论：{impact}\n怎么补最省事：{action}\n优先级：{priority}",
    }


def platform_account(platform: str) -> str:
    mapping = {
        "meituan": "meituan_unsettled",
        "taobao_flash": "taobao_unsettled",
        "jd_delivery": "jd_unsettled",
        "douyin": "douyin_unsettled",
        "meituan_group": "meituan_group_unsettled",
    }
    return mapping.get(platform, "platform_unsettled")


def item_id_by_name(items: list[dict[str, Any]], name: str) -> str | None:
    if not name:
        return None
    return next((item["id"] for item in items if item["name"] == name), None)


def seed_inventory_items() -> list[dict[str, Any]]:
    rows = [
        ("inv-octopus", "章鱼粒", "ingredient", "包", 2, 60, 4, "冷冻柜", "7/4 盘点表 / 7/6 进货单", "低置信度"),
        ("inv-powder", "章鱼预拌粉", "ingredient", "包", 6, 26.5, 3, "干货架", "7/4 盘点表 / 7/6 进货单", "低置信度"),
        ("inv-sauce", "原味照烧酱", "ingredient", "瓶", 3, 18, 2, "操作台", "7/6 进货单", "待确认"),
        ("inv-bonito", "木鱼花", "ingredient", "包", 0.8, 45, 1.5, "干货架", "7/4 盘点表 / 7/6 进货单", "低置信度"),
        ("inv-seaweed", "海苔粉", "ingredient", "包", 2, 22, 1, "干货架", "seed", "待确认"),
        ("inv-mayo", "沙拉酱", "ingredient", "瓶", 4, 16, 2, "操作台", "seed", "待确认"),
        ("inv-box6", "6 粒盒", "packaging", "个", 220, 0.36, 80, "包装区", "7/6 进货单", "待确认"),
        ("inv-packaging", "包装耗材", "consumable", "套", 180, 0.18, 60, "包装区", "7/6 进货单", "待确认"),
    ]
    items = []
    for id_, name, category, unit, qty, cost, safe, location, source, status in rows:
        item = asdict(InventoryItem(id_, name, category, unit, qty, cost, safe, None, location))
        item.update({
            "evidence_source": source,
            "confirmation_status": status,
            "latest_unit_cost_source": "7/6 进货单" if "7/6" in source else "seed 待确认",
            "owner_confirmed": status == "已确认",
        })
        items.append(item)
    priority = {"inv-octopus": 0, "inv-powder": 1, "inv-bonito": 2, "inv-box6": 3}
    return sorted(items, key=lambda item: priority.get(item["id"], 10))


def seed_products_and_bom():
    products = [asdict(Product(f"prod-{idx}", name, name)) for idx, name in enumerate([
        "经典原味", "海苔肉松", "藤椒蛤蜊", "芥末", "玉米奶酪", "咸蛋黄", "培根芝士"
    ], start=1)]
    variants = [
        asdict(ProductVariant("variant-6", "prod-1", "基础 6 粒", 6, "inv-box6")),
        asdict(ProductVariant("variant-8", "prod-1", "双拼 8 粒", 8, "inv-packaging")),
        asdict(ProductVariant("variant-9", "prod-1", "全家福 9 粒", 9, "inv-packaging")),
    ]
    prices = [
        asdict(ChannelPrice("price-6-dine", "variant-6", "堂食", 18, 18)),
        asdict(ChannelPrice("price-6-delivery", "variant-6", "外卖", 22, None, "到手价受平台抽佣、配送、活动影响")),
        asdict(ChannelPrice("price-6-group", "variant-6", "团购", 15, None, "核销后才形成实际收入")),
    ]
    boms = [
        asdict(ProductBOM("bom-6-octopus", "经典原味", "基础 6 粒", "inv-octopus", 6, "粒", 0, True)),
        asdict(ProductBOM("bom-6-powder", "经典原味", "基础 6 粒", "inv-powder", None, "克", 0, False, "缺一包粉可做多少盒")),
        asdict(ProductBOM("bom-6-sauce", "经典原味", "基础 6 粒", "inv-sauce", None, "克", 0, False, "缺每盒酱料克重")),
        asdict(ProductBOM("bom-6-mayo", "经典原味", "基础 6 粒", "inv-mayo", None, "克", 0, False, "缺每盒沙拉酱克重")),
        asdict(ProductBOM("bom-6-bonito", "经典原味", "基础 6 粒", "inv-bonito", None, "克", 0, False, "缺每盒木鱼花克重")),
        asdict(ProductBOM("bom-6-seaweed", "经典原味", "基础 6 粒", "inv-seaweed", None, "克", 0, False, "缺海苔粉用量")),
        asdict(ProductBOM("bom-6-box", "经典原味", "基础 6 粒", "inv-box6", 1, "个", 0, True)),
    ]
    return products, variants, prices, boms
