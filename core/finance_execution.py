"""Permissioned finance execution plans.

Evidence and user input first become an explainable plan.  Only an explicit
confirmation may turn that plan into merchant-sales, bookkeeping and
reconciliation records.
"""

from __future__ import annotations

from core.finance_categories import find_finance_category

import hashlib
from collections import defaultdict
from datetime import date
from typing import Any

from models.finance_ledger import FinanceLedger, FinanceMigrationError


SCHEMA_VERSION = "finance_execution_plan_v1"
FORMER_OWNER_PLATFORMS = ["美团外卖", "淘宝闪购", "京东外卖", "抖音团购"]

EVENT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "categorized_transaction": {
        "direction": "outflow", "kind": "categorized_transaction", "scope": "store",
        "code": None, "name": "分类资金记录", "risk": "L3",
    },
    "platform_settlement": {
        "direction": "inflow", "kind": "platform_settlement", "scope": "store",
        "code": None, "name": "平台结算到账", "risk": "L3",
    },
    "former_owner_transfer": {
        "direction": "inflow", "kind": "former_owner_transfer", "scope": "store",
        "code": "1013", "name": "前老板转回代收款", "risk": "L3",
    },
    "inventory_purchase": {
        "direction": "outflow", "kind": "inventory_purchase", "scope": "store",
        "code": "1401", "name": "原材料库存", "risk": "L3",
    },
    "operating_expense": {
        "direction": "outflow", "kind": "operating_expense", "scope": "store",
        "code": "6005", "name": "店铺经营支出", "risk": "L3",
    },
    "personal_spending": {
        "direction": "outflow", "kind": "personal_spending", "scope": "personal",
        "code": None, "name": "个人消费", "risk": "L3",
    },
    "owner_investment": {
        "direction": "inflow", "kind": "owner_investment", "scope": "store",
        "code": "3001", "name": "老板投入", "risk": "L3",
    },
    "owner_draw": {
        "direction": "outflow", "kind": "owner_draw", "scope": "store",
        "code": "3002", "name": "老板取用", "risk": "L3",
    },
    "loan_in": {
        "direction": "inflow", "kind": "loan_in", "scope": "store",
        "code": "2003", "name": "借款到账", "risk": "L3",
    },
    "loan_repayment": {
        "direction": "outflow", "kind": "loan_repayment", "scope": "store",
        "code": "2003", "name": "偿还借款本金", "risk": "L3",
    },
    "merchant_net_sale": {
        "name": "实际到手营业额", "risk": "L3",
    },
}


class FinanceExecutionService:
    def __init__(self, ledger: FinanceLedger):
        self.ledger = ledger

    @staticmethod
    def _plan_id(store_id: str, event_type: str, source_reference: str) -> str:
        digest = hashlib.sha256(
            f"{store_id}|{event_type}|{source_reference}".encode("utf-8")
        ).hexdigest()[:20]
        return f"finance-plan:{store_id}:{digest}"

    @staticmethod
    def _prefix_allocations(
        rows: list[dict[str, Any]], platforms: list[str], target_minor: int
    ) -> tuple[list[dict[str, Any]], int]:
        """Find a chronological prefix for every platform whose total is exact.

        Settlement batches normally clear the oldest still-unpaid sales on each
        platform.  Prefix matching prevents a numerically convenient but
        historically impossible arbitrary subset.
        """
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row["channel"])].append(row)
        choices: dict[str, list[tuple[int, list[dict[str, Any]]]]] = {}
        for platform in platforms:
            ordered = sorted(
                grouped.get(platform, []),
                key=lambda item: (item["business_date"], item["id"]),
            )
            options: list[tuple[int, list[dict[str, Any]]]] = [(0, [])]
            running = 0
            selected: list[dict[str, Any]] = []
            for row in ordered:
                running += int(row["remaining_minor"])
                selected = [*selected, row]
                if running <= target_minor:
                    options.append((running, selected))
            choices[platform] = options

        states: dict[int, list[list[dict[str, Any]]]] = {0: [[]]}
        for platform in platforms:
            next_states: dict[int, list[list[dict[str, Any]]]] = defaultdict(list)
            for subtotal, combinations in states.items():
                for option_total, option_rows in choices[platform]:
                    total = subtotal + option_total
                    if total > target_minor:
                        continue
                    for combination in combinations:
                        bucket = next_states[total]
                        if len(bucket) < 2:
                            bucket.append([*combination, *option_rows])
            states = dict(next_states)

        exact = states.get(target_minor, [])
        if len(exact) != 1:
            return [], len(exact)
        return [
            {
                "target_type": "merchant_net_sale",
                "target_id": row["id"],
                "business_date": row["business_date"],
                "platform": row["channel"],
                "amount_minor": int(row["remaining_minor"]),
            }
            for row in exact[0]
        ], 1

    def preview(self, store_id: str, raw_input: dict[str, Any]) -> dict[str, Any]:
        data = dict(raw_input)
        event_type = str(data.get("event_type") or data.get("fact_type") or "")
        definition = EVENT_DEFINITIONS.get(event_type)
        source_reference = str(data.get("source_reference") or "").strip()
        if not source_reference:
            stable = repr(sorted((key, value) for key, value in data.items() if key != "file"))
            source_reference = f"finance-input:{hashlib.sha256(stable.encode()).hexdigest()[:20]}"
            data["source_reference"] = source_reference
        plan_id = self._plan_id(store_id, event_type, source_reference)
        missing_fields: list[str] = []
        if not definition:
            missing_fields.append("event_type")
        transaction_date = str(data.get("transaction_date") or data.get("business_date") or "")
        try:
            date.fromisoformat(transaction_date)
        except ValueError:
            missing_fields.append("transaction_date")
        amount_minor = int(data.get("amount_minor") or 0)
        if amount_minor <= 0:
            missing_fields.append("amount_minor")
        if event_type == "merchant_net_sale":
            if not data.get("channel"):
                missing_fields.append("channel")
            if not data.get("settlement_state"):
                missing_fields.append("settlement_state")
        elif definition and not data.get("account_key"):
            missing_fields.append("account_key")
        category = find_finance_category(data.get("business_category_key"))
        if category and category["transaction_kind"] == "account_transfer" and not data.get("counter_account_key"):
            missing_fields.append("counter_account_key")

        checks: list[dict[str, Any]] = []
        if missing_fields:
            status = "needs_input"
            actions: list[dict[str, Any]] = []
            accounting_effect = {"revenue_impact_minor": 0, "journal_preview": []}
            reconciliation = {
                "strategy": "not_ready", "allocations": [],
                "matched_minor": 0, "difference_minor": amount_minor,
                "confidence": "none",
            }
        else:
            checks.append({
                "code": "REQUIRED_FIELDS",
                "status": "passed",
                "message": "金额、日期、类型与账户字段完整",
            })
            accounts = {
                item["account_key"]: item
                for item in self.ledger.list_fund_accounts(store_id)
                if item.get("status") == "active"
            }
            account_key = str(data.get("account_key") or "")
            if event_type != "merchant_net_sale" and account_key not in accounts:
                checks.append({
                    "code": "ACCOUNT_NOT_REGISTERED",
                    "status": "failed",
                    "message": "收付款账户未登记或已无法识别",
                })
            else:
                checks.append({
                    "code": "ACCOUNT_REGISTERED",
                    "status": "passed",
                    "message": "收付款账户已登记，可保留资金去向",
                })

            duplicate = next(
                (
                    item for item in self.ledger.list_bookkeeping_records(store_id, limit=2000)
                    if item.get("source_reference") == source_reference
                    and item.get("transaction_kind") == event_type
                ),
                None,
            )
            if duplicate:
                checks.append({
                    "code": "DUPLICATE_SOURCE",
                    "status": "failed",
                    "message": f"该来源已经生成记账记录 {duplicate['id']}",
                })
            else:
                checks.append({
                    "code": "DUPLICATE_SOURCE",
                    "status": "passed",
                    "message": "未发现相同来源的已入账记录",
                })

            if event_type == "platform_settlement":
                semantic_text = " ".join(
                    str(data.get(key) or "")
                    for key in ("counterparty", "notes", "source_basis", "channel")
                )
                expense_markers = (
                    "花了", "缴费", "支付", "扣款", "消费", "购买",
                    "电网", "电力", "水费", "电费", "房租", "工资", "还款",
                )
                platform_markers = (
                    "美团", "淘宝", "闪购", "京东", "抖音", "客如云",
                    "POS", "平台", "商家钱包", "结算", "提现",
                )
                has_expense_semantics = any(marker in semantic_text for marker in expense_markers)
                has_platform_evidence = any(marker in semantic_text for marker in platform_markers)
                checks.append({
                    "code": "BUSINESS_SEMANTIC_CONTRADICTION",
                    "status": "failed" if has_expense_semantics else "passed",
                    "message": (
                        "文字表明这是支付或缴费，与‘平台结算到账’的资金方向冲突"
                        if has_expense_semantics
                        else "未发现与到账方向冲突的支出语义"
                    ),
                })
                checks.append({
                    "code": "PLATFORM_EVIDENCE_PRESENT",
                    "status": "passed" if has_platform_evidence else "failed",
                    "message": (
                        "已找到平台、商家钱包或结算提现证据"
                        if has_platform_evidence
                        else "没有平台或结算证据，不能仅因为出现银行字样就记为到账"
                    ),
                })

            allocations: list[dict[str, Any]] = []
            allocation_count = 0
            if event_type == "former_owner_transfer":
                receivable = self.ledger.account_balances(
                    store_id, "0001-01-01", transaction_date
                ).get("1013", 0)
                checks.append({
                    "code": (
                        "RECEIVABLE_SUFFICIENT"
                        if amount_minor <= receivable
                        else "RECEIVABLE_INSUFFICIENT"
                    ),
                    "status": "passed" if amount_minor <= receivable else "failed",
                    "message": (
                        f"前老板应收可核销 {receivable / 100:.2f} 元"
                        if amount_minor <= receivable
                        else f"到账 {amount_minor / 100:.2f} 元超过前老板应收 {receivable / 100:.2f} 元"
                    ),
                })
                platforms = [
                    str(value) for value in (data.get("platforms") or FORMER_OWNER_PLATFORMS)
                ]
                period_start = str(data.get("business_period_start") or "0001-01-01")
                period_end = str(data.get("business_period_end") or transaction_date)
                candidates = self.ledger.outstanding_merchant_sales(
                    store_id,
                    platforms=platforms,
                    start=period_start,
                    end=period_end,
                )
                allocations, allocation_count = self._prefix_allocations(
                    candidates, platforms, amount_minor
                )
                configured_bindings = self.ledger.list_platform_collection_bindings(
                    store_id
                )
                binding_errors: list[str] = []
                if configured_bindings:
                    for allocation in allocations:
                        active = [
                            item
                            for item in self.ledger.list_platform_collection_bindings(
                                store_id, allocation["business_date"]
                            )
                            if item["platform"] == allocation["platform"]
                        ]
                        if (
                            len(active) != 1
                            or active[0]["collector_owner_kind"] != "former_owner"
                        ):
                            binding_errors.append(
                                f"{allocation['platform']} {allocation['business_date']}"
                            )
                    checks.append({
                        "code": "COLLECTION_BINDING_VERSION",
                        "status": "passed" if not binding_errors else "failed",
                        "message": (
                            "每笔销售均匹配到当日有效的前老板代收版本"
                            if not binding_errors
                            else f"以下销售不属于当日有效的前老板代收路径：{', '.join(binding_errors)}"
                        ),
                    })
                checks.append({
                    "code": "RECONCILIATION_EXACT",
                    "status": "passed" if allocation_count == 1 else "failed",
                    "message": (
                        "四个平台待收销售按各平台最早未收日期可唯一加总到本次到账"
                        if allocation_count == 1
                        else "现有销售事实无法唯一解释本次合并到账，请补齐平台账单或人工选择范围"
                    ),
                })
                journal_preview = [
                    {"account_code": "1002", "debit_minor": amount_minor, "credit_minor": 0},
                    {"account_code": "1013", "debit_minor": 0, "credit_minor": amount_minor},
                ]
                revenue_impact = 0
            elif event_type == "merchant_net_sale":
                journal_preview = []
                revenue_impact = amount_minor
                allocation_count = 1
            else:
                journal_preview = []
                revenue_impact = 0
                allocation_count = 1

            failed = any(check["status"] == "failed" for check in checks)
            status = "blocked" if failed else "awaiting_confirmation"
            actions = [] if failed else [
                {
                    "action": (
                        "record_merchant_net_sale"
                        if event_type == "merchant_net_sale"
                        else "create_and_post_bookkeeping_record"
                    ),
                    "permission_level": "L3",
                    "status": "pending_confirmation",
                },
                *(
                    [{
                        "action": "reconcile_merchant_sales",
                        "permission_level": "L3",
                        "status": "pending_confirmation",
                        "target_count": len(allocations),
                    }]
                    if allocations else []
                ),
                {
                    "action": "refresh_finance_associations",
                    "permission_level": "L2",
                    "status": "after_posting",
                },
            ]
            accounting_effect = {
                "revenue_impact_minor": revenue_impact,
                "journal_preview": journal_preview,
                "explanation": (
                    "这是已确认销售对应的资金回收，只改变银行与前老板应收，不重复增加营业收入。"
                    if event_type == "former_owner_transfer"
                    else "这是老板个人消费，只保留个人资金去向，不计入店铺收入、成本或利润。"
                    if event_type == "personal_spending"
                    else "这是进货形成的库存，付款时不直接计入当期成本，实际耗用时再进入利润核算。"
                    if event_type == "inventory_purchase"
                    else "这笔经营支出会进入店铺成本，并减少对应账户的资金。"
                    if event_type == "operating_expense"
                    else "销售事实会进入营业额；到账、借款、投入和转账本身不重复形成销售。"
                ),
            }
            matched = sum(item["amount_minor"] for item in allocations)
            reconciliation = {
                "strategy": "oldest_unreceived_prefix_per_platform",
                "platforms": data.get("platforms") or FORMER_OWNER_PLATFORMS,
                "allocations": allocations,
                "matched_minor": matched,
                "difference_minor": amount_minor - matched,
                "confidence": "high" if allocation_count == 1 else "none",
            }

        plan = {
            "schema_version": SCHEMA_VERSION,
            "plan_id": plan_id,
            "project_id": store_id,
            "event_type": event_type,
            "title": definition["name"] if definition else "待识别财务事实",
            "status": status,
            "risk_level": definition["risk"] if definition else "L2",
            "normalized_fact": {
                "transaction_date": transaction_date,
                "amount_minor": amount_minor,
                "account_key": data.get("account_key"),
                "counterparty": data.get("counterparty"),
                "source_reference": source_reference,
                "evidence_reference": data.get("evidence_reference"),
            },
            "missing_fields": sorted(set(missing_fields)),
            "checks": checks,
            "actions": actions,
            "accounting_effect": accounting_effect,
            "reconciliation": reconciliation,
            "confirmation": {
                "required": status == "awaiting_confirmation",
                "prompt": f"确认执行方案 {plan_id}" if status == "awaiting_confirmation" else None,
            },
            "next_steps": (
                [{
                    "action": "reclassify_receivable_before_transfer",
                    "permission_level": "L3",
                    "message": (
                        "平台销售范围已唯一匹配，但总账中的前老板应收不足。"
                        "应先把有证据属于前老板代收的“平台待结算/待核对收款”重分类到1013，"
                        "复核无误后再执行本转款方案；禁止直接把1013冲成负数。"
                    ),
                }]
                if any(
                    check["code"] == "RECEIVABLE_INSUFFICIENT"
                    for check in checks
                )
                and reconciliation.get("difference_minor") == 0
                else []
            ),
        }
        return self.ledger.save_execution_plan(
            store_id,
            plan_id=plan_id,
            event_type=event_type or "unknown",
            status=status,
            risk_level=plan["risk_level"],
            source_reference=source_reference,
            input_data=data,
            plan_data=plan,
        )

    def execute(
        self,
        store_id: str,
        plan_id: str,
        *,
        confirmed_by: str,
    ) -> dict[str, Any]:
        persisted = self.ledger.get_execution_plan(store_id, plan_id)
        if persisted["status"] == "completed":
            return persisted
        if persisted["status"] != "awaiting_confirmation":
            raise FinanceMigrationError("该方案尚未通过校验，不能执行")
        source_reference = persisted["normalized_fact"]["source_reference"]
        with self.ledger.connect() as connection:
            row = connection.execute(
                "SELECT input_json FROM finance_execution_plans WHERE store_id=? AND id=?",
                (store_id, plan_id),
            ).fetchone()
        import json

        data = json.loads(row["input_json"])
        refreshed = self.preview(store_id, data)
        if refreshed["status"] == "completed":
            return refreshed
        if refreshed["status"] != "awaiting_confirmation":
            raise FinanceMigrationError("执行前复核发现账况已变化，请查看更新后的方案")
        self.ledger.update_execution_plan(
            store_id, plan_id, status="executing", confirmed_by=confirmed_by
        )
        try:
            event_type = str(data["event_type"])
            amount_minor = int(data["amount_minor"])
            transaction_date = str(
                data.get("transaction_date") or data.get("business_date")
            )
            if event_type == "merchant_net_sale":
                accounts = {
                    item["account_key"]: item
                    for item in self.ledger.list_fund_accounts(store_id)
                }
                current = accounts.get(str(data.get("current_account_key") or ""))
                record_id = self.ledger.record_merchant_net_sale(
                    store_id,
                    business_date=transaction_date,
                    channel=str(data["channel"]),
                    amount_minor=amount_minor,
                    source_basis=str(data.get("source_basis") or "确认录入"),
                    evidence_status="confirmed" if data.get("evidence_reference") else "manual",
                    settlement_state=str(data["settlement_state"]),
                    current_fund_account_id=current["id"] if current else None,
                    evidence_reference=data.get("evidence_reference"),
                    notes=data.get("notes"),
                )
            else:
                definition = EVENT_DEFINITIONS[event_type]
                category = find_finance_category(data.get("business_category_key"))
                voucher_id = None
                if data.get("evidence_reference"):
                    with self.ledger.connect() as connection:
                        voucher = connection.execute(
                            "SELECT id FROM evidence_vouchers WHERE store_id=? AND id=?",
                            (store_id, data["evidence_reference"]),
                        ).fetchone()
                    voucher_id = str(voucher["id"]) if voucher else None
                record_id = self.ledger.create_bookkeeping_record(
                    store_id,
                    transaction_date=transaction_date,
                    direction=str(category["direction"] if category else definition["direction"]),
                    amount_minor=amount_minor,
                    transaction_kind=str(category["transaction_kind"] if category else definition["kind"]),
                    business_scope=str(category["business_scope"] if category else definition["scope"]),
                    category_code=(category["account_code"] if category else None) or data.get("category_code") or definition.get("code"),
                    category_name=str(category["name"] if category else data.get("category_name") or definition["name"]),
                    business_category_key=str(category["key"]) if category else None,
                    business_category_group=str(category["group_name"]) if category else None,
                    account_key=str(data["account_key"]),
                    counter_account_key=data.get("counter_account_key"),
                    counterparty=data.get("counterparty"),
                    summary=data.get("notes"),
                    source_type="finance_execution_plan",
                    source_reference=source_reference,
                    voucher_id=voucher_id,
                    confidence="confirmed",
                    classification_reason="用户确认了可解释的财务执行方案",
                    raw_data={
                        "finance_execution_plan_id": plan_id,
                        "business_period_start": data.get("business_period_start"),
                        "business_period_end": data.get("business_period_end"),
                        "platforms": data.get("platforms"),
                        "evidence_reference": data.get("evidence_reference"),
                    },
                    status="draft",
                )
                self.ledger.confirm_bookkeeping_record(store_id, record_id)
                for allocation in refreshed["reconciliation"]["allocations"]:
                    self.ledger.match_reconciliation(
                        store_id,
                        record_id,
                        target_type=allocation["target_type"],
                        target_id=allocation["target_id"],
                        matched_amount_minor=int(allocation["amount_minor"]),
                        match_method="finance_execution_plan_v1",
                        notes=f"由方案 {plan_id} 经老板确认",
                    )
            refreshed["status"] = "completed"
            refreshed["record_id"] = record_id
            refreshed["actions"] = [
                {**action, "status": "completed"} for action in refreshed["actions"]
            ]
            if data.get("evidence_reference"):
                with self.ledger.connect() as connection:
                    connection.execute(
                        """UPDATE evidence_vouchers SET status='confirmed'
                           WHERE store_id=? AND id=?""",
                        (store_id, data["evidence_reference"]),
                    )
            return self.ledger.update_execution_plan(
                store_id,
                plan_id,
                status="completed",
                plan_data=refreshed,
                record_id=record_id if event_type != "merchant_net_sale" else None,
                confirmed_by=confirmed_by,
            )
        except Exception as exc:
            self.ledger.update_execution_plan(
                store_id,
                plan_id,
                status="failed",
                confirmed_by=confirmed_by,
                error_message=str(exc),
            )
            raise
