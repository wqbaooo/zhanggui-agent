"""Cross-ledger posting coordinator for owner-confirmed operating facts."""

from __future__ import annotations

from typing import Any

from models.finance_ledger import FinanceLedger, money_to_minor


class PostingCoordinator:
    """Mirror one confirmed operating fact into canonical finance subledgers.

    The caller must only persist the operating fact's final ``posted`` state
    after this method succeeds. Finance writes are idempotent, so a retry after
    an interrupted operating-ledger save does not duplicate journal entries.
    """

    def __init__(self, project_id: str, finance: FinanceLedger | None = None):
        self.project_id = project_id
        self.finance = finance or FinanceLedger.for_project(project_id)

    def sync_confirmed_fact(
        self,
        *,
        fact: dict[str, Any],
        inventory_movements: list[dict[str, Any]],
        inventory_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        finance_entries: list[Any] = []
        finance_inventory: list[dict[str, Any]] = []
        fact_type = str(fact.get("fact_type") or "")
        amount = float(fact.get("amount") or 0)
        reference = str(fact.get("posting_key") or fact.get("id") or "")

        if fact_type == "net_operating_income" and amount > 0:
            extracted = fact.get("extracted_fields") or {}
            synced = self.finance.record_confirmed_daily_revenue(
                self.project_id,
                {
                    "date": fact["date"],
                    "actual_revenue": amount,
                    "orders": extracted.get("orders", 0),
                    "dine_in_revenue": extracted.get("dine_in_revenue"),
                    "delivery_revenue": extracted.get("delivery_revenue"),
                    "dine_in_orders": extracted.get("dine_in_orders", 0),
                    "delivery_orders": extracted.get("delivery_orders", 0),
                },
            )
            finance_entries.append({"type": "daily_revenue", "posted": bool(synced)})
        elif fact_type == "former_owner_transfer" and amount > 0:
            finance_entries.append(self.finance.record_former_owner_transfer(
                self.project_id,
                str(fact["date"]),
                money_to_minor(amount),
                reference,
            ))
        elif fact_type == "platform_settlement" and amount > 0:
            finance_entries.append(self.finance.record_platform_settlement(
                self.project_id,
                str(fact["date"]),
                money_to_minor(amount),
                reference,
            ))
        elif fact_type == "operating_expense" and amount > 0:
            account = str((fact.get("metadata") or {}).get("finance_account_code") or "")
            self.finance.ensure_store(self.project_id, self.project_id, str(fact["date"]))
            finance_entries.append(self.finance.record_expense(
                self.project_id,
                str(fact["date"]),
                account,
                money_to_minor(amount),
                reference,
                description=str(fact.get("title") or "确认经营费用"),
            ))

        items_by_id = {str(item.get("id")): item for item in inventory_items}
        for movement in inventory_movements:
            item = items_by_id.get(str(movement.get("item_id")), {})
            finance_inventory.append(self.finance.record_inventory_movement(
                self.project_id,
                movement_id=str(movement["id"]),
                item_id=str(movement["item_id"]),
                item_name=str(item.get("name") or movement["item_id"]),
                business_date=str(movement["date"]),
                movement_type=str(movement["movement_type"]),
                quantity=float(movement["quantity"]),
                unit_cost=float(movement.get("unit_cost") or 0),
            ))

        return {
            "finance_synced": bool(finance_entries or finance_inventory),
            "finance_entries": finance_entries,
            "finance_inventory": finance_inventory,
        }
