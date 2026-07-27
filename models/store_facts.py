"""Canonical, evidence-linked store fact book beyond the journal ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import PROJECT_DATA_DIR
from models.json_store import atomic_write_json, load_json


@dataclass
class StoreFactBook:
    project_id: str
    version: str = "2026-07-13.2"
    cash_counts: list[dict[str, Any]] = field(default_factory=list)
    settlements: list[dict[str, Any]] = field(default_factory=list)
    supplier_invoices: list[dict[str, Any]] = field(default_factory=list)
    capital_payments: list[dict[str, Any]] = field(default_factory=list)
    product_sales_periods: list[dict[str, Any]] = field(default_factory=list)
    inventory_policy: dict[str, Any] = field(default_factory=dict)
    operational_forms: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, project_id: str) -> "StoreFactBook":
        data = load_json(PROJECT_DATA_DIR / project_id / "store_facts.json", dict)
        if not data:
            return cls(project_id=project_id)
        return cls(**{name: data.get(name, default) for name, default in {
            "project_id": project_id, "version": "2026-07-13.2", "cash_counts": [],
            "settlements": [], "supplier_invoices": [], "capital_payments": [],
            "product_sales_periods": [], "inventory_policy": {}, "operational_forms": [],
            "evidence": [],
        }.items()})

    def save(self) -> None:
        atomic_write_json(PROJECT_DATA_DIR / self.project_id / "store_facts.json", self.__dict__)

    def finance_summary(self) -> dict[str, Any]:
        invoices = self.supplier_invoices
        latest_cash = max(self.cash_counts, key=lambda item: item["date"], default=None)
        direct_use = sum(
            int(line.get("subtotal_minor", 0))
            for invoice in invoices for line in invoice.get("items", [])
            if line.get("accounting_treatment") == "direct_use_food_cost"
        )
        inventory = sum(
            int(line.get("subtotal_minor", 0))
            for invoice in invoices for line in invoice.get("items", [])
            if line.get("accounting_treatment") == "inventory_purchase"
        )
        former_transfer = next(
            (item for item in self.settlements if item.get("type") == "former_owner_collection_transfer"), {}
        )
        hq = next((item for item in self.capital_payments if item.get("type") == "hq_inventory_purchase"), {})
        packaging = self.packaging_estimate()
        # 7/1-7/12 商品规格推导出的包装耗用；只使用总部采购中已确认的单位成本。
        # 三粒大丸子盒尚无可靠单价，因此不伪造成本。
        estimated_packaging_cost = round(
            packaging["standard_six_box"] * 36
            + packaging["four_piece_box"] * 29
            + packaging["family_nine_box"] * (58 + 15)
        )
        return {
            "latest_cash_count": (
                {"date": latest_cash["date"], "amount_minor": int(latest_cash["amount_minor"])}
                if latest_cash else None
            ),
            "cash_definition": latest_cash.get("definition") if latest_cash else None,
            "local_supplier_payable_minor": sum(int(item.get("total_minor", 0)) for item in invoices),
            "direct_use_food_cost_minor": direct_use,
            "inventory_purchase_minor": inventory,
            "supplier_invoice_count": len(invoices),
            "former_owner_transfer_minor": int(former_transfer.get("amount_minor", 0)),
            "former_owner_transfer_direction": former_transfer.get("direction"),
            "hq_purchase_minor": int(hq.get("amount_minor", 0)),
            "hq_payment_status": hq.get("payment_status"),
            "hq_payee": hq.get("payee"),
            "hq_payments": hq.get("payments", []),
            "hq_payment_note": hq.get("note"),
            "estimated_packaging_cost_minor": estimated_packaging_cost,
            "estimated_packaging_cost_basis": "商品规格推导盒数 × 已确认采购单位成本；未含三粒大丸子盒",
        }

    def product_sales_summary(self) -> dict[str, Any]:
        if not self.product_sales_periods:
            return {}
        period = self.product_sales_periods[-1]
        rows = period.get("ranked_products", [])
        return {
            **{key: period.get(key) for key in (
                "period", "total_quantity", "gross_sales_minor", "refund_quantity",
                "refund_minor", "recognized_revenue_minor", "source_basis",
            )},
            "visible_ranked_quantity": sum(int(row.get("quantity", 0)) for row in rows),
            "visible_ranked_amount_minor": sum(int(row.get("amount_minor", 0)) for row in rows),
            "ranked_products": rows,
            "gross_to_recognized_difference_minor": int(period.get("gross_sales_minor", 0)) - int(period.get("recognized_revenue_minor", 0)),
        }

    def packaging_estimate(self) -> dict[str, Any]:
        rows = self.product_sales_summary().get("ranked_products", [])
        result = {
            "standard_six_box": 0, "family_nine_box": 0, "four_piece_box": 0,
            "large_three_box": 0, "unmapped_quantity": 0,
            "rule": "official_name_or_cross_platform_official_consensus",
            "confidence": "management_estimate_not_inventory_posting",
        }
        for row in rows:
            quantity = int(row.get("quantity", 0))
            spec = row.get("official_spec")
            if spec == "6粒":
                result["standard_six_box"] += quantity
            elif spec == "9粒":
                result["family_nine_box"] += quantity
            elif spec == "8粒_两盒四粒":
                result["four_piece_box"] += quantity * 2
            elif spec == "3粒大丸子":
                result["large_three_box"] += quantity
            elif spec == "non_food_packaging_sale":
                continue
            else:
                result["unmapped_quantity"] += quantity
        return result
