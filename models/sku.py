#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SKU 目录与进货预测模型：食材、包装、耗材的库存管理和补货推算。"""

from __future__ import annotations

import copy
import time
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import PROJECT_DATA_DIR
from models.json_store import atomic_write_json, load_json

SKU_CATEGORIES = ["食材", "包装", "耗材", "清洁", "其他"]
SKU_UNITS = ["kg", "g", "个", "包", "箱", "卷", "双", "袋", "瓶", "桶", "张", "套"]
INVENTORY_LOCATIONS = ["store", "warehouse", "freezer", "unallocated"]
LOCATION_LABELS = {
    "store": "门店",
    "warehouse": "仓库",
    "freezer": "大冰箱",
    "unallocated": "待分配",
}


@dataclass
class SkuItem:
    """单个 SKU：食材、包装盒、耗材、清洁用品等。"""
    id: str = ""
    name: str = ""
    category: str = "食材"
    unit: str = "个"
    safety_stock: float = 0.0
    current_stock: float = 0.0
    unit_cost: float = 0.0
    supplier: str = ""
    batch_cycle_days: int = 14
    consumption_per_day: float = 0.0
    last_purchase_date: str = ""
    next_purchase_est: str = ""
    status: str = "正常"
    notes: str = ""
    hq_code: str = ""
    hq_name: str = ""
    hq_image: str = ""
    hq_category: str = ""
    standard_unit: str = ""
    spec: str = ""
    pack_quantity: float = 0.0
    stock_by_location: Dict[str, float] = field(default_factory=dict)
    count_units: List[Dict[str, Any]] = field(default_factory=list)
    tracking_mode: str = "periodic_count"
    daily_usage_group: str = ""
    daily_usage_sort: int = 0
    display_unit: str = ""
    store_target_days: float = 0.0
    supplier_lead_days: int = 3
    reorder_enabled: bool = True
    usage_integer_only: bool = True
    asset_class: str = "inventory"
    master_source: str = ""
    master_source_row: int = 0
    master_data_status: str = "needs_review"
    unit_cost_source: str = ""
    active: bool = True
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkuItem":
        defaults = {
            "id": "", "name": "", "category": "食材", "unit": "个",
            "safety_stock": 0.0, "current_stock": 0.0, "unit_cost": 0.0,
            "supplier": "", "batch_cycle_days": 14, "consumption_per_day": 0.0,
            "last_purchase_date": "", "next_purchase_est": "", "status": "正常",
            "notes": "", "hq_code": "", "hq_name": "", "hq_image": "", "hq_category": "",
            "standard_unit": "", "spec": "", "pack_quantity": 0.0,
            "stock_by_location": {}, "count_units": [],
            "tracking_mode": "periodic_count", "daily_usage_group": "", "daily_usage_sort": 0,
            "display_unit": "", "active": True,
            "store_target_days": 0.0, "supplier_lead_days": 3,
            "reorder_enabled": True, "usage_integer_only": True,
            "asset_class": "inventory", "master_source": "", "master_source_row": 0,
            "master_data_status": "needs_review", "unit_cost_source": "",
            "created_at": 0.0, "updated_at": 0.0,
        }
        return cls(**{key: data.get(key, default) for key, default in defaults.items()})


@dataclass
class PurchaseItem:
    """进货单中的单行项目。"""
    sku_id: str = ""
    name: str = ""
    quantity: float = 0.0
    unit_cost: float = 0.0
    subtotal: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PurchaseRecord:
    """一次进货记录。"""
    id: str = ""
    date: str = ""
    supplier: str = ""
    items: List[Dict[str, Any]] = field(default_factory=list)
    total_cost: float = 0.0
    payment_status: str = "未付"
    paid_amount: float = 0.0
    fulfillment_status: str = "ordered"
    external_order_id: str = ""
    location: str = "warehouse"
    received_at: str = ""
    notes: str = ""
    platform: str = ""
    freight: float = 0.0
    discount_amount: float = 0.0
    refund_amount: float = 0.0
    evidence_file: str = ""
    accounting_status: str = "inventory_asset"
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SkuAlias:
    """SKU 别名映射：供应商品名/外部分类名 → 门店 SKU。"""
    id: str = ""
    sku_id: str = ""
    alias: str = ""
    supplier: str = ""
    unit_conversion: float = 1.0
    alias_unit: str = ""
    source: str = "manual"
    usage_count: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkuAlias":
        defaults = {
            "id": "", "sku_id": "", "alias": "", "supplier": "",
            "unit_conversion": 1.0, "alias_unit": "", "source": "manual",
            "usage_count": 0, "created_at": 0.0, "updated_at": 0.0,
        }
        return cls(**{key: data.get(key, default) for key, default in defaults.items()})


@dataclass
class InventoryEvent:
    """可追溯的库存变化事件。quantity 始终使用 SKU 核算单位。"""

    id: str = ""
    date: str = ""
    event_type: str = ""
    sku_id: str = ""
    quantity: float = 0.0
    from_location: str = ""
    to_location: str = ""
    source: str = "manual"
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InventoryCount:
    """一次门店或仓库实盘。"""

    id: str = ""
    date: str = ""
    location: str = "store"
    count_type: str = "weekly"
    lines: List[Dict[str, Any]] = field(default_factory=list)
    source: str = "manual"
    notes: str = ""
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CountUnit:
    """盘点/计数单位与核算单位的换算关系。

    例如门店盘点「外卖无纺布袋」时习惯写「11 捆」，
    1 捆 = 50 个（核算单位），则 conversion=50。
    """

    unit: str = ""
    conversion: float = 1.0
    base_unit: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InventoryVariance:
    """SKU 在某一期间的理论消耗 vs 实际消耗差异。

    理论消耗 = 商品销量 × BOM（暂缺 BOM 时标记为不可核验）。
    实际消耗 = 期初库存 + 采购 - 损耗 - 期末盘点。
    """

    sku_id: str = ""
    sku_name: str = ""
    base_unit: str = ""
    period_start: str = ""
    period_end: str = ""
    opening_stock: float = 0.0
    purchases: float = 0.0
    usage_logged: float = 0.0
    waste_logged: float = 0.0
    closing_stock: float = 0.0
    actual_consumption: Optional[float] = None
    theoretical_consumption: Optional[float] = None
    variance_quantity: Optional[float] = None
    variance_rate: Optional[float] = None
    verification_status: str = "no_bom"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UsageLog:
    """员工纸质台账识别后的每日开包/领用记录。"""

    id: str = ""
    date: str = ""
    location: str = "store"
    items: List[Dict[str, Any]] = field(default_factory=list)
    source: str = "paper_ledger"
    notes: str = ""
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProductionBatch:
    """把原料转换为面浆等在制品的生产批次。"""

    id: str = ""
    date: str = ""
    name: str = ""
    location: str = "store"
    inputs: List[Dict[str, Any]] = field(default_factory=list)
    output_quantity: float = 0.0
    output_unit: str = "批"
    remaining_quantity: float = 0.0
    used_quantity: float = 0.0
    waste_quantity: float = 0.0
    pan_cycle_minutes: float = 0.0
    actual_pan_cycles: float = 0.0
    status: str = "open"
    source: str = "manual"
    notes: str = ""
    created_at: float = 0.0
    closed_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SkuCatalog:
    """SKU 目录：管理该项目的全部 SKU、别名映射和进货记录。"""
    project_id: str
    skus: List[Dict[str, Any]] = field(default_factory=list)
    aliases: List[Dict[str, Any]] = field(default_factory=list)
    purchases: List[Dict[str, Any]] = field(default_factory=list)
    inventory_events: List[Dict[str, Any]] = field(default_factory=list)
    inventory_counts: List[Dict[str, Any]] = field(default_factory=list)
    usage_logs: List[Dict[str, Any]] = field(default_factory=list)
    production_batches: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[Dict[str, Any]] = field(default_factory=list)
    integrity_repairs: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    @property
    def data_file(self) -> Path:
        return PROJECT_DATA_DIR / self.project_id / "skus.json"

    def save(self):
        self.updated_at = time.time()
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.data_file, asdict(self))

    @classmethod
    def load(cls, project_id: str) -> Optional["SkuCatalog"]:
        path = PROJECT_DATA_DIR / project_id / "skus.json"
        if not path.exists():
            return None
        data = load_json(path)
        if data is None:
            return None
        # Inventory archives evolve independently from the application binary.
        # Ignore forward-compatible top-level metadata instead of making the
        # whole store catalogue unreadable after a schema extension.
        supported = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in supported})

    @classmethod
    def create(cls, project_id: str) -> "SkuCatalog":
        catalog = cls(project_id=project_id)
        catalog.save()
        return catalog

    def _next_id(self, prefix: str) -> str:
        now = int(time.time() * 1000)
        if prefix == "sku":
            items = self.skus
        elif prefix == "alias":
            items = self.aliases
        elif prefix == "event":
            items = self.inventory_events
        elif prefix == "count":
            items = self.inventory_counts
        elif prefix == "usage":
            items = self.usage_logs
        elif prefix == "production":
            items = self.production_batches
        else:
            items = self.purchases
        return f"{prefix}-{now}-{len(items)}"

    # ── 别名管理 ──

    def add_alias(self, alias: SkuAlias) -> SkuAlias:
        now = time.time()
        if not alias.id:
            alias.id = self._next_id("alias")
        alias.created_at = now
        alias.updated_at = now
        self.aliases.append(alias.to_dict())
        self.save()
        return alias

    def get_alias(self, alias_id: str) -> Optional[Dict[str, Any]]:
        for a in self.aliases:
            if a.get("id") == alias_id:
                return a
        return None

    def update_alias(self, alias_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for i, a in enumerate(self.aliases):
            if a.get("id") == alias_id:
                patch["updated_at"] = time.time()
                self.aliases[i].update({k: v for k, v in patch.items() if v is not None})
                self.save()
                return self.aliases[i]
        return None

    def delete_alias(self, alias_id: str) -> bool:
        before = len(self.aliases)
        self.aliases = [a for a in self.aliases if a.get("id") != alias_id]
        if len(self.aliases) < before:
            self.save()
            return True
        return False

    def list_aliases(self, sku_id: Optional[str] = None, supplier: Optional[str] = None) -> List[Dict[str, Any]]:
        result = self.aliases
        if sku_id:
            result = [a for a in result if a.get("sku_id") == sku_id]
        if supplier:
            result = [a for a in result if a.get("supplier") == supplier]
        return sorted(result, key=lambda a: a.get("usage_count", 0), reverse=True)

    def match_alias(self, name: str, supplier: str = "") -> Optional[Dict[str, Any]]:
        """按供应商品名匹配别名，优先精确匹配，其次模糊匹配，同供应商优先。"""
        name_norm = name.strip()
        if not name_norm:
            return None

        exact_match = None
        fuzzy_match = None
        supplier_exact = None
        supplier_fuzzy = None

        for a in self.aliases:
            alias_name = a.get("alias", "").strip()
            if not alias_name:
                continue
            same_supplier = supplier and a.get("supplier") == supplier
            if alias_name == name_norm:
                if same_supplier:
                    supplier_exact = a
                elif not exact_match:
                    exact_match = a
            elif name_norm in alias_name or alias_name in name_norm:
                if same_supplier and not supplier_fuzzy:
                    supplier_fuzzy = a
                elif not fuzzy_match:
                    fuzzy_match = a

        best = supplier_exact or exact_match or supplier_fuzzy or fuzzy_match
        if best:
            self._increment_alias_usage(best.get("id", ""))
        return best

    def _increment_alias_usage(self, alias_id: str):
        for i, a in enumerate(self.aliases):
            if a.get("id") == alias_id:
                self.aliases[i]["usage_count"] = int(a.get("usage_count", 0)) + 1
                self.save()
                break

    def add_sku(self, sku: SkuItem) -> SkuItem:
        now = time.time()
        if not sku.id:
            sku.id = self._next_id("sku")
        sku.created_at = now
        sku.updated_at = now
        if not sku.stock_by_location and sku.current_stock:
            sku.stock_by_location = {"unallocated": round(float(sku.current_stock), 4)}
        sku.status = self._stock_status(sku.current_stock, sku.safety_stock)
        self.skus.append(sku.to_dict())
        self.save()
        return sku

    def get_sku(self, sku_id: str) -> Optional[Dict[str, Any]]:
        for sku in self.skus:
            if sku.get("id") == sku_id:
                return sku
        return None

    def update_sku(self, sku_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for i, sku in enumerate(self.skus):
            if sku.get("id") == sku_id:
                patch["updated_at"] = time.time()
                self.skus[i].update({k: v for k, v in patch.items() if v is not None})
                if "stock_by_location" in patch:
                    self._sync_total(self.skus[i])
                elif "current_stock" in patch and not self.skus[i].get("stock_by_location"):
                    self.skus[i]["stock_by_location"] = {
                        "unallocated": round(float(self.skus[i].get("current_stock", 0)), 4),
                    }
                current = float(self.skus[i].get("current_stock", 0))
                safety = float(self.skus[i].get("safety_stock", 0))
                self.skus[i]["status"] = self._stock_status(current, safety)
                self.save()
                return self.skus[i]
        return None

    def delete_sku(self, sku_id: str) -> bool:
        before = len(self.skus)
        self.skus = [s for s in self.skus if s.get("id") != sku_id]
        if len(self.skus) < before:
            self.save()
            return True
        return False

    def record_purchase(self, purchase: PurchaseRecord) -> PurchaseRecord:
        now = time.time()
        if not purchase.id:
            purchase.id = self._next_id("purchase")
        purchase.created_at = now
        purchase.fulfillment_status = purchase.fulfillment_status or "ordered"

        for item in purchase.items:
            sku_id = item.get("sku_id", "")
            qty = float(item.get("quantity", 0))
            cost = float(item.get("unit_cost", 0))
            item["subtotal"] = round(qty * cost, 2)

        purchase.total_cost = round(sum(
            float(i.get("subtotal", 0)) for i in purchase.items
        ), 2)

        self.purchases.append(purchase.to_dict())
        self.save()
        return purchase

    def record_receipt(
        self,
        purchase_id: str,
        date: str,
        items: List[Dict[str, Any]],
        source: str = "owner_confirmed",
        notes: str = "",
    ) -> Dict[str, Any]:
        purchase = next((item for item in self.purchases if item.get("id") == purchase_id), None)
        if purchase is None:
            raise ValueError("purchase not found")
        if purchase.get("fulfillment_status") == "received":
            raise ValueError("该进货单已经完成入库，不能重复收货")

        ordered_by_sku = {
            item.get("sku_id", ""): item
            for item in purchase.get("items", [])
        }
        prepared: List[Tuple[Dict[str, Any], Dict[str, Any], float, Dict[str, float], float, float]] = []
        for line in items:
            sku_id = line.get("sku_id", "")
            sku = self.get_sku(sku_id)
            ordered = ordered_by_sku.get(sku_id)
            if sku is None or ordered is None:
                raise ValueError(f"进货单中不存在该物料: {sku_id}")
            received = round(float(line.get("received_quantity", 0) or 0), 4)
            allocations = {
                location: round(float(quantity or 0), 4)
                for location, quantity in (line.get("allocations") or {}).items()
                if location in {"store", "warehouse", "freezer"}
            }
            if received < 0:
                raise ValueError("实收数量不能小于 0")
            if abs(sum(allocations.values()) - received) > 0.0001:
                raise ValueError(f"{sku.get('name')} 的位置分配合计必须等于实收数量")
            prepared.append((
                sku,
                ordered,
                received,
                allocations,
                round(float(sku.get("current_stock", 0) or 0), 4),
                round(float(sku.get("unit_cost", 0) or 0), 6),
            ))

        received_skus = {sku.get("id") for sku, _, _, _, _, _ in prepared}
        if received_skus != set(ordered_by_sku):
            raise ValueError("必须逐项确认进货单中的所有物料；缺货项请填写实收 0")

        for sku, ordered, received, allocations, previous_quantity, previous_unit_cost in prepared:
            for location, quantity in allocations.items():
                if quantity <= 0:
                    continue
                self._change_stock(sku, location, quantity)
                self._append_event(InventoryEvent(
                    date=date,
                    event_type="receipt",
                    sku_id=sku.get("id", ""),
                    quantity=quantity,
                    to_location=location,
                    source=source,
                    notes=notes or f"{purchase.get('supplier', '')} 清点入库",
                    metadata={"purchase_id": purchase_id},
                ))
            ordered["received_quantity"] = received
            ordered["receipt_variance"] = round(
                received - float(ordered.get("quantity", 0) or 0),
                4,
            )
            ordered["allocations"] = allocations
            sku["last_purchase_date"] = date
            receipt_unit_cost = float(ordered.get("unit_cost", 0) or 0)
            if receipt_unit_cost > 0 and received > 0:
                # 小店可能多次进货、更换平台供应商，单位库存成本不能被“最后一次价格”直接覆盖。
                # 按入库前库存与本次实收做移动加权平均，供后续库存金额和毛利核算使用。
                denominator = previous_quantity + received
                if denominator > 0:
                    sku["unit_cost"] = round(
                        (previous_quantity * previous_unit_cost + received * receipt_unit_cost) / denominator,
                        6,
                    )
                    sku["unit_cost_source"] = "移动加权平均（库存账）"

        purchase["fulfillment_status"] = "received"
        purchase["received_at"] = date
        purchase["notes"] = "；".join(filter(None, [purchase.get("notes", ""), notes]))
        self.save()
        return purchase

    def get_purchases(self, limit: int = 30) -> List[Dict[str, Any]]:
        return sorted(
            self.purchases, key=lambda p: p.get("date", ""), reverse=True,
        )[:limit]

    def record_production(self, batch: ProductionBatch) -> ProductionBatch:
        batch.location = self._validate_location(batch.location, allow_unallocated=False)
        if batch.location == "freezer":
            raise ValueError("生产批次不能在大冰箱位置创建")
        if batch.output_quantity <= 0:
            raise ValueError("生产批次产出数量必须大于 0")
        if not batch.id:
            batch.id = self._next_id("production")
        batch.created_at = time.time()
        batch.remaining_quantity = round(batch.output_quantity, 4)

        prepared: List[Tuple[Dict[str, Any], Dict[str, Any], float]] = []
        for item in batch.inputs:
            sku = self.get_sku(item.get("sku_id", ""))
            quantity = round(float(item.get("quantity", 0) or 0), 4)
            if sku is None:
                raise ValueError(f"sku not found: {item.get('sku_id', '')}")
            if quantity <= 0:
                raise ValueError("生产领料数量必须大于 0")
            available = self._stock_map(sku).get(batch.location, 0)
            if quantity > available + 0.0001:
                raise ValueError(f"{sku.get('name')} 在{LOCATION_LABELS[batch.location]}库存不足")
            prepared.append((sku, item, quantity))

        for sku, item, quantity in prepared:
            self._change_stock(sku, batch.location, -quantity)
            item["name"] = item.get("name") or sku.get("name", "")
            item["unit"] = item.get("unit") or sku.get("unit", "")
            self._append_event(InventoryEvent(
                date=batch.date,
                event_type="production_issue",
                sku_id=sku.get("id", ""),
                quantity=quantity,
                from_location=batch.location,
                source=batch.source,
                notes=batch.notes or f"用于{batch.name}",
                metadata={"production_batch_id": batch.id},
            ))

        self.production_batches.append(batch.to_dict())
        self.save()
        return batch

    def close_production(
        self,
        batch_id: str,
        used_quantity: float,
        waste_quantity: float = 0.0,
        actual_pan_cycles: float = 0.0,
        notes: str = "",
    ) -> Dict[str, Any]:
        batch = next((item for item in self.production_batches if item.get("id") == batch_id), None)
        if batch is None:
            raise ValueError("production batch not found")
        if batch.get("status") == "closed":
            raise ValueError("该生产批次已经关闭")
        total = round(float(used_quantity or 0) + float(waste_quantity or 0), 4)
        output = round(float(batch.get("output_quantity", 0) or 0), 4)
        if abs(total - output) > 0.0001:
            raise ValueError("已使用和报损数量合计必须等于批次产出")
        batch["used_quantity"] = round(float(used_quantity or 0), 4)
        batch["waste_quantity"] = round(float(waste_quantity or 0), 4)
        batch["remaining_quantity"] = 0.0
        batch["actual_pan_cycles"] = round(float(actual_pan_cycles or 0), 2)
        batch["status"] = "closed"
        batch["closed_at"] = time.time()
        batch["notes"] = "；".join(filter(None, [batch.get("notes", ""), notes]))
        self.save()
        return batch

    def get_production_batches(self, limit: int = 60) -> List[Dict[str, Any]]:
        return sorted(
            self.production_batches,
            key=lambda item: (item.get("date", ""), item.get("created_at", 0)),
            reverse=True,
        )[:limit]

    # ── 库存流水、调拨、开包与盘点 ──

    @staticmethod
    def _validate_location(location: str, allow_unallocated: bool = True) -> str:
        allowed = INVENTORY_LOCATIONS if allow_unallocated else INVENTORY_LOCATIONS[:3]
        if location not in allowed:
            raise ValueError(f"unsupported inventory location: {location}")
        return location

    @staticmethod
    def _parse_count_units(sku: Dict[str, Any]) -> List[CountUnit]:
        """把 SKU 中的 count_units / pack_quantity / standard_unit 统一成换算规则。"""
        units: List[CountUnit] = []
        base_unit = sku.get("unit", "")
        for item in sku.get("count_units", []) or []:
            if not isinstance(item, dict):
                continue
            units.append(CountUnit(
                unit=item.get("unit", ""),
                conversion=float(item.get("conversion", 1) or 1),
                base_unit=item.get("base_unit", base_unit),
            ))
        # pack_quantity + standard_unit 作为向后兼容的换算规则
        pack_qty = float(sku.get("pack_quantity", 0) or 0)
        standard_unit = sku.get("standard_unit", "")
        if pack_qty > 0 and standard_unit and standard_unit != base_unit:
            if not any(u.unit == standard_unit for u in units):
                units.append(CountUnit(unit=standard_unit, conversion=pack_qty, base_unit=base_unit))
        return units

    @staticmethod
    def _base_unit(sku: Dict[str, Any]) -> str:
        return sku.get("unit", "")

    @staticmethod
    def normalize_quantity(
        sku: Dict[str, Any],
        qty: float,
        input_unit: Optional[str] = None,
    ) -> Tuple[float, str]:
        """把按 input_unit 输入的数量换算成 SKU 核算单位（unit）。

        返回 (换算后数量, 核算单位)。无法识别单位时原样返回。
        """
        base_unit = SkuCatalog._base_unit(sku)
        unit = (input_unit or "").strip()
        if not unit:
            unit = (sku.get("display_unit") or "").strip()
        if not unit or unit == base_unit:
            return float(qty), base_unit

        for cu in SkuCatalog._parse_count_units(sku):
            if cu.unit == unit and cu.base_unit == base_unit and cu.conversion > 0:
                return float(qty) * cu.conversion, base_unit
        return float(qty), base_unit

    @staticmethod
    def _stock_map(sku: Dict[str, Any]) -> Dict[str, float]:
        raw = sku.get("stock_by_location") or {}
        if raw:
            return {
                key: round(float(value or 0), 4)
                for key, value in raw.items()
                if key in INVENTORY_LOCATIONS
            }
        current = round(float(sku.get("current_stock", 0) or 0), 4)
        return {"unallocated": current} if current else {}

    @staticmethod
    def _sync_total(sku: Dict[str, Any]) -> None:
        stock_map = {
            key: max(0.0, round(float(value or 0), 4))
            for key, value in (sku.get("stock_by_location") or {}).items()
            if key in INVENTORY_LOCATIONS
        }
        sku["stock_by_location"] = stock_map
        sku["current_stock"] = round(sum(stock_map.values()), 4)
        safety = float(sku.get("safety_stock", 0) or 0)
        sku["status"] = SkuCatalog._stock_status(sku["current_stock"], safety)

    def _change_stock(self, sku: Dict[str, Any], location: str, delta: float) -> None:
        location = self._validate_location(location)
        stock_map = self._stock_map(sku)
        new_value = round(float(stock_map.get(location, 0)) + float(delta), 4)
        if new_value < -0.0001:
            raise ValueError(f"{sku.get('name', sku.get('id'))} 在 {location} 库存不足")
        stock_map[location] = max(0.0, new_value)
        sku["stock_by_location"] = stock_map
        sku["updated_at"] = time.time()
        self._sync_total(sku)

    def _append_event(self, event: InventoryEvent) -> Dict[str, Any]:
        if not event.id:
            event.id = self._next_id("event")
        event.created_at = time.time()
        payload = event.to_dict()
        self.inventory_events.append(payload)
        return payload

    def record_transfer(
        self,
        date: str,
        from_location: str,
        to_location: str,
        items: List[Dict[str, Any]],
        source: str = "manual",
        notes: str = "",
    ) -> List[Dict[str, Any]]:
        from_location = self._validate_location(from_location)
        to_location = self._validate_location(to_location, allow_unallocated=False)
        if from_location == to_location:
            raise ValueError("调出和调入位置不能相同")

        prepared: List[Tuple[Dict[str, Any], float]] = []
        for item in items:
            sku = self.get_sku(item.get("sku_id", ""))
            qty = round(float(item.get("quantity", 0) or 0), 4)
            if sku is None:
                raise ValueError(f"sku not found: {item.get('sku_id', '')}")
            if qty <= 0:
                raise ValueError("调拨数量必须大于 0")
            available = self._stock_map(sku).get(from_location, 0)
            if qty > available + 0.0001:
                raise ValueError(f"{sku.get('name')} 在{LOCATION_LABELS[from_location]}库存不足")
            prepared.append((sku, qty))

        events = []
        for sku, qty in prepared:
            self._change_stock(sku, from_location, -qty)
            self._change_stock(sku, to_location, qty)
            events.append(self._append_event(InventoryEvent(
                date=date,
                event_type="transfer",
                sku_id=sku.get("id", ""),
                quantity=qty,
                from_location=from_location,
                to_location=to_location,
                source=source,
                notes=notes,
            )))
        self.save()
        return events

    def record_usage(
        self,
        log: UsageLog,
    ) -> UsageLog:
        operational = log.location == "operational"
        if not operational:
            log.location = self._validate_location(log.location, allow_unallocated=False)
        duplicate = next((
            item for item in self.usage_logs
            if item.get("date") == log.date and item.get("source") == log.source
        ), None)
        if duplicate is not None:
            raise ValueError("该日期的每日物料使用记录已存在；如需改错请使用覆盖保存")
        if not log.id:
            log.id = self._next_id("usage")
        log.created_at = time.time()

        prepared: List[Tuple[Dict[str, Any], Dict[str, Any], float]] = []
        for item in log.items:
            sku = self.get_sku(item.get("sku_id", ""))
            qty = round(float(item.get("quantity", 0) or 0), 4)
            if sku is None:
                raise ValueError(f"sku not found: {item.get('sku_id', '')}")
            if qty < 0:
                raise ValueError("领用数量不能小于 0")
            if sku.get("usage_integer_only", True) and abs(qty - round(qty)) > 0.0001:
                raise ValueError(f"{sku.get('name')} 按开封/领用次数登记，只能填写整数")
            prepared.append((sku, item, qty))

        for sku, item, qty in prepared:
            item["name"] = item.get("name") or sku.get("name", "")
            item["unit"] = item.get("unit") or sku.get("display_unit") or sku.get("unit", "")
            if qty <= 0:
                continue
            deductions: List[Dict[str, Any]] = []
            remaining = qty
            locations = ["store", "freezer", "warehouse", "unallocated"] if operational else [log.location]
            for location in locations:
                available = float(self._stock_map(sku).get(location, 0) or 0)
                deducted = min(available, remaining)
                if deducted <= 0:
                    continue
                self._change_stock(sku, location, -deducted)
                deductions.append({"location": location, "quantity": round(deducted, 4)})
                remaining = round(remaining - deducted, 4)
                if remaining <= 0:
                    break
            deducted_total = round(qty - remaining, 4)
            self._append_event(InventoryEvent(
                date=log.date,
                event_type="usage",
                sku_id=sku.get("id", ""),
                quantity=qty,
                from_location="operational" if operational else log.location,
                source=log.source,
                notes=log.notes,
                metadata={
                    "usage_log_id": log.id,
                    "deducted_quantity": deducted_total,
                    "deductions": deductions,
                    "shortfall": round(max(0.0, remaining), 4),
                    "unit_cost_snapshot": round(float(sku.get("unit_cost", 0) or 0), 6),
                    "usage_cost_snapshot": round(qty * float(sku.get("unit_cost", 0) or 0), 2),
                    "cost_source": sku.get("unit_cost_source") or sku.get("latest_unit_cost_source") or "sku_unit_cost",
                },
            ))

        self.usage_logs.append(log.to_dict())
        self.save()
        return log

    def replace_daily_usage(self, log: UsageLog) -> UsageLog:
        """覆盖某天纸质日用表，并把上一版扣减完整冲回后重新入账。"""
        snapshot = {
            "skus": copy.deepcopy(self.skus),
            "inventory_events": copy.deepcopy(self.inventory_events),
            "usage_logs": copy.deepcopy(self.usage_logs),
        }
        old_logs = [
            item for item in self.usage_logs
            if item.get("date") == log.date and item.get("source") == log.source
        ]
        old_ids = {item.get("id") for item in old_logs}
        try:
            for event in self.inventory_events:
                metadata = event.get("metadata") or {}
                if event.get("event_type") != "usage" or metadata.get("usage_log_id") not in old_ids:
                    continue
                sku = self.get_sku(event.get("sku_id", ""))
                if sku is None:
                    continue
                deductions = metadata.get("deductions") or []
                if not deductions and float(metadata.get("deducted_quantity", 0) or 0) > 0:
                    deductions = [{
                        "location": event.get("from_location") or "store",
                        "quantity": float(metadata.get("deducted_quantity", 0) or 0),
                    }]
                for deduction in deductions:
                    location = deduction.get("location", "")
                    if location in INVENTORY_LOCATIONS:
                        self._change_stock(sku, location, float(deduction.get("quantity", 0) or 0))
            self.inventory_events = [
                event for event in self.inventory_events
                if not (
                    event.get("event_type") == "usage"
                    and (event.get("metadata") or {}).get("usage_log_id") in old_ids
                )
            ]
            self.usage_logs = [item for item in self.usage_logs if item.get("id") not in old_ids]
            return self.record_usage(log)
        except Exception:
            self.skus = snapshot["skus"]
            self.inventory_events = snapshot["inventory_events"]
            self.usage_logs = snapshot["usage_logs"]
            raise

    def daily_usage_summary(self, date: str) -> Dict[str, Any]:
        sku_map = {sku.get("id"): sku for sku in self.skus}
        rows: List[Dict[str, Any]] = []
        usage_cost = 0.0
        shortfall_count = 0
        for event in self.inventory_events:
            if event.get("event_type") != "usage" or event.get("date") != date:
                continue
            sku = sku_map.get(event.get("sku_id"), {})
            quantity = float(event.get("quantity", 0) or 0)
            metadata = event.get("metadata") or {}
            unit_cost = float(metadata.get("unit_cost_snapshot", sku.get("unit_cost", 0)) or 0)
            shortfall = float(metadata.get("shortfall", 0) or 0)
            if shortfall > 0:
                shortfall_count += 1
            cost = round(float(metadata.get("usage_cost_snapshot", quantity * unit_cost) or 0), 2)
            usage_cost += cost
            rows.append({
                "sku_id": event.get("sku_id", ""),
                "name": sku.get("name", ""),
                "category": sku.get("category", ""),
                "quantity": quantity,
                "unit": sku.get("display_unit") or sku.get("unit", ""),
                "unit_cost": unit_cost,
                "usage_cost": cost,
                "shortfall": shortfall,
            })
        return {
            "date": date,
            "rows": rows,
            "recorded_sku_count": len(rows),
            "usage_cost": round(usage_cost, 2),
            "shortfall_sku_count": shortfall_count,
            "cost_basis": "按使用发生时的移动加权单位成本快照估算；属于库存耗用成本，不等于已确认商品毛利。",
        }

    def period_usage_cost_summary(self, start: str, end: str) -> Dict[str, Any]:
        """Aggregate cost snapshots for finance without posting accounting entries."""
        sku_map = {sku.get("id"): sku for sku in self.skus}
        categories: Dict[str, float] = {}
        evidence_event_ids: List[str] = []
        for event in self.inventory_events:
            event_date = str(event.get("date") or "")
            if event.get("event_type") != "usage" or not (start <= event_date <= end):
                continue
            sku = sku_map.get(event.get("sku_id"), {})
            metadata = event.get("metadata") or {}
            quantity = float(event.get("quantity", 0) or 0)
            unit_cost = float(metadata.get("unit_cost_snapshot", sku.get("unit_cost", 0)) or 0)
            usage_cost = round(float(metadata.get("usage_cost_snapshot", quantity * unit_cost) or 0), 2)
            category = str(sku.get("category") or "未分类")
            categories[category] = round(categories.get(category, 0) + usage_cost, 2)
            if event.get("id"):
                evidence_event_ids.append(str(event["id"]))
        food = round(categories.get("常温食材", 0) + categories.get("冷链食材", 0), 2)
        packaging = round(categories.get("包装耗材", 0), 2)
        other_consumables = round(sum(
            value for category, value in categories.items()
            if category not in {"常温食材", "冷链食材", "包装耗材"}
        ), 2)
        return {
            "period_start": start,
            "period_end": end,
            "food_cost": food,
            "packaging_cost": packaging,
            "other_consumables_cost": other_consumables,
            "total_usage_cost": round(food + packaging + other_consumables, 2),
            "categories": categories,
            "evidence_event_ids": evidence_event_ids,
            "status": "estimated_from_daily_usage" if evidence_event_ids else "not_enough_data",
            "accounting_boundary": "仅作暂估成本桥接；不自动过账，不覆盖已过账实际成本",
        }

    def record_waste(
        self,
        *,
        date: str,
        location: str,
        items: List[Dict[str, Any]],
        reason: str,
        source: str = "owner_confirmed",
        notes: str = "",
    ) -> List[Dict[str, Any]]:
        """登记撒漏、变质、过期等报损，并从指定位置扣减库存。"""
        location = self._validate_location(location, allow_unallocated=False)
        if not reason.strip():
            raise ValueError("报损原因不能为空")
        prepared: List[Tuple[Dict[str, Any], float]] = []
        for item in items:
            sku = self.get_sku(item.get("sku_id", ""))
            quantity = round(float(item.get("quantity", 0) or 0), 4)
            if sku is None:
                raise ValueError(f"sku not found: {item.get('sku_id', '')}")
            if quantity <= 0:
                raise ValueError("报损数量必须大于 0")
            if quantity > self._stock_map(sku).get(location, 0) + 0.0001:
                raise ValueError(f"{sku.get('name')} 在{LOCATION_LABELS[location]}库存不足")
            prepared.append((sku, quantity))

        events: List[Dict[str, Any]] = []
        for sku, quantity in prepared:
            self._change_stock(sku, location, -quantity)
            events.append(self._append_event(InventoryEvent(
                date=date,
                event_type="waste",
                sku_id=sku.get("id", ""),
                quantity=quantity,
                from_location=location,
                source=source,
                notes=notes,
                metadata={"reason": reason},
            )))
        self.save()
        return events

    def record_count(self, count: InventoryCount) -> InventoryCount:
        count.location = self._validate_location(count.location, allow_unallocated=False)
        if not count.id:
            count.id = self._next_id("count")
        count.created_at = time.time()

        normalized_lines: List[Dict[str, Any]] = []
        for raw in count.lines:
            sku = self.get_sku(raw.get("sku_id", ""))
            if sku is None:
                raise ValueError(f"sku not found: {raw.get('sku_id', '')}")
            raw_qty = round(float(raw.get("counted_quantity", 0) or 0), 4)
            if raw_qty < 0:
                raise ValueError("实盘数量不能小于 0")

            input_unit = raw.get("counted_unit", "") or sku.get("display_unit") or ""
            counted, base_unit = self.normalize_quantity(sku, raw_qty, input_unit)
            counted = round(counted, 4)

            stock_map = self._stock_map(sku)
            expected = round(float(stock_map.get(count.location, 0)), 4)
            # 员工纸质盘点表记录的是门店实盘结余，不是“从待分配库存划拨一部分”。
            # 首次以纸质表建账时，旧待分配数应作为账面预期值参与差异计算，
            # 然后全部归零，由实盘数建立门店真实库存。
            if count.source == "paper_inventory_sheet" and stock_map.get("unallocated", 0) > 0:
                expected = round(
                    float(stock_map.get(count.location, 0)) + float(stock_map.get("unallocated", 0)),
                    4,
                )
                stock_map["unallocated"] = 0.0
                stock_map[count.location] = counted
                sku["stock_by_location"] = stock_map
            # 旧数据第一次分地点盘点时，从“待分配”库存中迁移，避免凭空增加总库存。
            elif count.location not in stock_map and stock_map.get("unallocated", 0) > 0:
                allocated = min(counted, stock_map.get("unallocated", 0))
                stock_map["unallocated"] = round(stock_map.get("unallocated", 0) - allocated, 4)
                stock_map[count.location] = allocated
                sku["stock_by_location"] = stock_map
                expected = allocated

            variance = round(counted - expected, 4)
            sku["stock_by_location"] = self._stock_map(sku)
            sku["stock_by_location"][count.location] = counted
            self._sync_total(sku)
            self._append_event(InventoryEvent(
                date=count.date,
                event_type="count_adjustment",
                sku_id=sku.get("id", ""),
                quantity=abs(variance),
                to_location=count.location if variance > 0 else "",
                from_location=count.location if variance < 0 else "",
                source=count.source,
                notes=count.notes,
                metadata={
                    "count_id": count.id,
                    "expected_quantity": expected,
                    "counted_quantity": counted,
                    "signed_variance": variance,
                    "input_quantity": raw_qty,
                    "input_unit": input_unit,
                    "base_unit": base_unit,
                    "components": raw.get("components", []),
                },
            ))
            denominator = max(abs(expected), abs(counted), 1.0)
            normalized_lines.append({
                "sku_id": sku.get("id", ""),
                "name": sku.get("name", ""),
                "unit": base_unit,
                "display_unit": sku.get("display_unit") or base_unit,
                "input_quantity": raw_qty,
                "input_unit": input_unit,
                "expected_quantity": expected,
                "counted_quantity": counted,
                "variance_quantity": variance,
                "variance_rate": round(variance / denominator, 4),
                "components": raw.get("components", []),
                "notes": raw.get("notes", ""),
            })

        count.lines = normalized_lines
        self.inventory_counts.append(count.to_dict())
        self.save()
        return count

    def get_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        result = sorted(
            self.inventory_events,
            key=lambda item: (item.get("date", ""), item.get("created_at", 0)),
            reverse=True,
        )[:limit]
        names = {sku.get("id"): sku.get("name", "") for sku in self.skus}
        return [{**item, "sku_name": names.get(item.get("sku_id"), "")} for item in result]

    def get_counts(self, limit: int = 30) -> List[Dict[str, Any]]:
        return sorted(
            self.inventory_counts,
            key=lambda item: (item.get("date", ""), item.get("created_at", 0)),
            reverse=True,
        )[:limit]

    def get_usage_logs(self, limit: int = 60) -> List[Dict[str, Any]]:
        return sorted(
            self.usage_logs,
            key=lambda item: (item.get("date", ""), item.get("created_at", 0)),
            reverse=True,
        )[:limit]

    def _observed_consumption(self, sku_id: str, days: int = 28) -> float:
        """仅使用已确认开包/领用记录计算耗用，不再用进货间隔冒充耗用。"""
        cutoff = datetime.now() - timedelta(days=max(1, days))
        total = 0.0
        dates: List[datetime] = []
        for event in self.inventory_events:
            if event.get("sku_id") != sku_id or event.get("event_type") != "usage":
                continue
            try:
                event_date = datetime.strptime(event.get("date", ""), "%Y-%m-%d")
            except ValueError:
                continue
            if event_date < cutoff:
                continue
            total += float(event.get("quantity", 0) or 0)
            dates.append(event_date)
        if not dates:
            return 0.0
        observed_days = max(1, (max(dates) - min(dates)).days + 1)
        return round(total / observed_days, 4)

    def inventory_summary(self) -> Dict[str, Any]:
        location_totals = {location: 0.0 for location in INVENTORY_LOCATIONS}
        allocated_skus = 0
        unallocated_skus = 0
        inventory_value = 0.0
        active_catalog = [sku for sku in self.skus if sku.get("active", True)]
        active_skus = [sku for sku in active_catalog if sku.get("asset_class") != "equipment"]
        for sku in active_skus:
            stock_map = self._stock_map(sku)
            for location in INVENTORY_LOCATIONS:
                location_totals[location] += float(stock_map.get(location, 0) or 0)
            if stock_map.get("unallocated", 0) > 0:
                unallocated_skus += 1
            if any(stock_map.get(location, 0) > 0 for location in ("store", "warehouse", "freezer")):
                allocated_skus += 1
            inventory_value += float(sku.get("current_stock", 0) or 0) * float(sku.get("unit_cost", 0) or 0)

        recent_count = self.get_counts(limit=1)
        recent_usage = self.get_usage_logs(limit=1)
        today = datetime.now().strftime("%Y-%m-%d")
        today_usage = self.daily_usage_summary(today)
        today_waste_cost = 0.0
        sku_map = {sku.get("id"): sku for sku in self.skus}
        for event in self.inventory_events:
            if event.get("event_type") == "waste" and event.get("date") == today:
                sku = sku_map.get(event.get("sku_id"), {})
                today_waste_cost += float(event.get("quantity", 0) or 0) * float(sku.get("unit_cost", 0) or 0)
        active_sku_ids = {sku.get("id") for sku in active_skus}
        counted_sku_ids = {
            line.get("sku_id")
            for count in self.inventory_counts
            for line in count.get("lines", [])
            if line.get("sku_id") in active_sku_ids
        }
        actions: List[Dict[str, Any]] = []
        if unallocated_skus:
            actions.append({
                "id": "baseline-location-count",
                "level": "important",
                "title": f"{unallocated_skus} 个 SKU 仍需分清门店和仓库",
                "reason": "接店盘存只有总量，系统不会猜测库存位置。",
                "action": "先完成门店周盘，再完成仓库盘点",
                "confidence": "high",
            })
        if not recent_count:
            actions.append({
                "id": "first-count",
                "level": "important",
                "title": "还没有正式盘点基线",
                "reason": "没有实盘就无法计算真实耗用和盘点差异。",
                "action": "创建第一次门店盘点",
                "confidence": "high",
            })
        if not recent_usage:
            actions.append({
                "id": "first-usage-log",
                "level": "info",
                "title": "今日物料使用尚未录入",
                "reason": "预拌粉、调料包和章鱼粒等核心物料还没有连续耗用记录。",
                "action": "录入今天的每日物料使用表",
                "confidence": "high",
            })

        for sku in active_skus:
            daily = self._observed_consumption(sku.get("id", ""))
            target_days = float(sku.get("store_target_days", 0) or 0)
            stock_map = self._stock_map(sku)
            if daily <= 0 or target_days <= 0:
                continue
            target = daily * target_days
            store_stock = float(stock_map.get("store", 0) or 0)
            warehouse_stock = float(stock_map.get("warehouse", 0) or 0)
            gap = max(0.0, target - store_stock)
            if gap <= 0 or warehouse_stock <= 0:
                continue
            transfer_qty = min(warehouse_stock, float(int(gap) if gap.is_integer() else int(gap) + 1))
            actions.append({
                "id": f"transfer-{sku.get('id')}",
                "level": "warning",
                "title": f"建议从仓库带 {transfer_qty:g}{sku.get('display_unit') or sku.get('unit')} {sku.get('name')}",
                "reason": f"门店现有 {store_stock:g}，近期开包速度约 {daily:g}/天，目标覆盖 {target_days:g} 天。",
                "action": "确认后登记仓库到门店调拨",
                "confidence": "medium",
                "sku_id": sku.get("id"),
                "suggested_quantity": transfer_qty,
            })

        return {
            "locations": {
                location: {
                    "label": LOCATION_LABELS[location],
                    "quantity_total": round(total, 2),
                }
                for location, total in location_totals.items()
            },
            "sku_count": len(active_skus),
            "catalog_sku_count": len(active_catalog),
            "equipment_count": len([sku for sku in active_catalog if sku.get("asset_class") == "equipment"]),
            "daily_usage_sku_count": len([sku for sku in active_skus if sku.get("tracking_mode") == "daily_usage"]),
            "master_verified_sku_count": len([sku for sku in active_catalog if sku.get("master_data_status") == "complete"]),
            "master_gap_sku_count": len([sku for sku in active_catalog if sku.get("master_data_status") in {"needs_review", "legacy_not_in_product_archive"}]),
            "counted_sku_count": len(counted_sku_ids),
            "allocated_skus": allocated_skus,
            "unallocated_skus": unallocated_skus,
            "inventory_value": round(inventory_value, 2),
            "today_usage_cost": today_usage["usage_cost"],
            "today_usage_sku_count": today_usage["recorded_sku_count"],
            "today_waste_cost": round(today_waste_cost, 2),
            "cost_basis": today_usage["cost_basis"],
            "last_count": recent_count[0] if recent_count else None,
            "last_usage_log": recent_usage[0] if recent_usage else None,
            "work_in_process": {
                "open_batches": len([
                    batch for batch in self.production_batches
                    if batch.get("status") == "open"
                ]),
                "items": [
                    batch for batch in self.get_production_batches()
                    if batch.get("status") == "open"
                ],
            },
            "actions": actions,
            "data_status": "calibrating" if unallocated_skus or len(counted_sku_ids) < len(active_skus) else "ready",
        }

    def variance_analysis(self, limit: int = 12) -> Dict[str, Any]:
        counts = self.get_counts(limit=limit)
        rows: List[Dict[str, Any]] = []
        total_abs_value = 0.0
        counted_value = 0.0
        sku_map = {sku.get("id"): sku for sku in self.skus}
        for count in counts:
            for line in count.get("lines", []):
                sku = sku_map.get(line.get("sku_id"), {})
                cost = float(sku.get("unit_cost", 0) or 0)
                variance_value = round(float(line.get("variance_quantity", 0) or 0) * cost, 2)
                total_abs_value += abs(variance_value)
                counted_value += abs(float(line.get("counted_quantity", 0) or 0) * cost)
                rows.append({
                    "count_id": count.get("id"),
                    "date": count.get("date"),
                    "location": count.get("location"),
                    "location_label": LOCATION_LABELS.get(count.get("location"), count.get("location")),
                    **line,
                    "variance_value": variance_value,
                })
        accuracy = None
        if counted_value > 0:
            accuracy = round(max(0.0, 1 - total_abs_value / counted_value), 4)
        return {
            "rows": rows,
            "count_sessions": len(counts),
            "value_accuracy": accuracy,
            "absolute_variance_value": round(total_abs_value, 2),
            "method": "盘点差异按实盘前账面数量与实盘数量比较；当前仅展示事实，不使用固定行业损耗率。",
        }

    def consumption_variance_analysis(
        self,
        period_start: str,
        period_end: str,
        bom: Optional[Dict[str, float]] = None,
        sales_by_sku: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """SKU 期间实际消耗 vs 理论消耗差异。

        实际消耗 = 期初库存 + 期间入库 - 期末库存。
        日常使用与报损已改变账面库存，只作为耗用结构证据，不再二次扣减。
        理论消耗 = 商品销量 × BOM（BOM 或销量缺失时标记为暂不可核验）。
        """
        bom = bom or {}
        sales_by_sku = sales_by_sku or {}

        def in_period(date_str: str) -> bool:
            return period_start <= date_str <= period_end

        sku_map = {sku.get("id"): sku for sku in self.skus}
        result_rows: List[Dict[str, Any]] = []

        def last_count_by_location(sku_id: str, before_date: str, inclusive: bool) -> Dict[str, float]:
            """取某 SKU 在指定日期前（含/不含）各位置最近一次盘点数量。"""
            result: Dict[str, float] = {}
            counts = sorted(self.inventory_counts, key=lambda c: c.get("date", ""), reverse=False)
            for count in counts:
                date = count.get("date", "")
                if inclusive:
                    if date > before_date:
                        continue
                else:
                    if date >= before_date:
                        continue
                for line in count.get("lines", []):
                    if line.get("sku_id") == sku_id:
                        result[count.get("location", "store")] = float(line.get("counted_quantity", 0) or 0)
            return result

        for sku_id, sku in sku_map.items():
            base_unit = sku.get("unit", "")
            sku_name = sku.get("name", "")
            cost = float(sku.get("unit_cost", 0) or 0)

            # 期初：取 period_start 当天及之前各位置最近一次盘点；未盘点位置视为 0
            opening_by_loc = last_count_by_location(sku_id, period_start, inclusive=True)
            opening = sum(opening_by_loc.values())

            # 期末：取 period_end 当天及之前各位置最近一次盘点；未盘点位置视为 0
            closing_by_loc = last_count_by_location(sku_id, period_end, inclusive=True)
            closing = sum(closing_by_loc.values())

            # 采购 / 领用 / 损耗（按事件统计）
            purchases_qty = 0.0
            usage_qty = 0.0
            waste_qty = 0.0
            for event in self.inventory_events:
                if event.get("sku_id") != sku_id:
                    continue
                date_str = event.get("date", "")
                if not in_period(date_str):
                    continue
                etype = event.get("event_type", "")
                qty = float(event.get("quantity", 0) or 0)
                if etype == "receipt":
                    purchases_qty += qty
                elif etype == "usage":
                    usage_qty += qty
                elif etype == "waste":
                    waste_qty += qty
                elif etype == "count_adjustment":
                    # 盘点差异已体现在 opening/closing 中，不再重复计入
                    pass

            has_count_pair = bool(opening_by_loc) and bool(closing_by_loc)
            # 实际耗用由两个实盘端点闭合：期初 + 期间入库 - 期末。
            # 每日开包/领用和报损是解释实际耗用组成的经营信号，库存数量已在
            # 记录事件时扣减；若在这里再次扣除，会把同一耗用重复计算。
            actual_consumption = (
                round(opening + purchases_qty - closing, 4)
                if has_count_pair
                else None
            )

            # 理论消耗
            theoretical = None
            verification_status = "no_bom"
            notes = "缺少 BOM，无法核验实际消耗是否合理。"
            sku_bom = bom.get(sku_id)
            sold_qty = sales_by_sku.get(sku_id)
            if not has_count_pair:
                verification_status = "missing_opening_count" if closing_by_loc else "missing_count"
                notes = (
                    "只有期末实盘，缺少期间期初盘点，不能计算实际消耗。"
                    if closing_by_loc
                    else "期间缺少可用的期初和期末盘点，不能计算实际消耗。"
                )
                if sku_bom is not None and sold_qty is not None:
                    theoretical = round(float(sold_qty) * float(sku_bom), 4)
            elif sku_bom is not None and sold_qty is not None:
                theoretical = round(float(sold_qty) * float(sku_bom), 4)
                if actual_consumption == 0 and theoretical == 0:
                    verification_status = "ok"
                    notes = "期间无消耗。"
                elif theoretical <= 0:
                    verification_status = "no_sales"
                    notes = "BOM 存在但期间销量为 0，无法核验。"
                else:
                    variance_qty = round(actual_consumption - theoretical, 4)
                    variance_rate = round(variance_qty / theoretical, 4)
                    if abs(variance_rate) <= 0.05:
                        verification_status = "ok"
                        notes = "实际消耗与理论消耗差异在 ±5% 以内。"
                    elif variance_qty > 0:
                        verification_status = "over_consumption"
                        notes = f"实际消耗比理论值多 {variance_qty:g}{base_unit}，可能存在浪费、份量偏差或漏盘。"
                    else:
                        verification_status = "under_consumption"
                        notes = f"实际消耗比理论值少 {abs(variance_qty):g}{base_unit}，可能 BOM 不准、漏记采购或盘点有误。"
            elif sku_bom is not None:
                notes = "有 BOM 但缺少该 SKU 销量，无法核验。"
                verification_status = "no_sales"
            elif sold_qty is not None:
                notes = "有销量但缺少 BOM，无法核验。"
                verification_status = "no_bom"

            row = InventoryVariance(
                sku_id=sku_id,
                sku_name=sku_name,
                base_unit=base_unit,
                period_start=period_start,
                period_end=period_end,
                opening_stock=opening,
                purchases=purchases_qty,
                usage_logged=usage_qty,
                waste_logged=waste_qty,
                closing_stock=closing,
                actual_consumption=actual_consumption,
                theoretical_consumption=theoretical,
                variance_quantity=round(actual_consumption - (theoretical or 0), 4) if actual_consumption is not None and theoretical is not None else None,
                variance_rate=round((actual_consumption - (theoretical or 0)) / theoretical, 4) if actual_consumption is not None and theoretical else None,
                verification_status=verification_status,
                notes=notes,
            ).to_dict()
            row["variance_value"] = round((row.get("variance_quantity") or 0) * cost, 2)
            result_rows.append(row)

        # 汇总
        total_actual = sum(float(r["actual_consumption"] or 0) for r in result_rows)
        rows_with_bom = [r for r in result_rows if r["theoretical_consumption"] is not None]
        total_theoretical = sum(r["theoretical_consumption"] for r in rows_with_bom)
        total_variance_value = sum(abs(r.get("variance_value", 0)) for r in rows_with_bom)
        verification_coverage = round(len(rows_with_bom) / max(len(result_rows), 1), 4)

        return {
            "period_start": period_start,
            "period_end": period_end,
            "rows": result_rows,
            "total_actual_consumption": round(total_actual, 4),
            "total_theoretical_consumption": round(total_theoretical, 4) if rows_with_bom else None,
            "total_variance_value": round(total_variance_value, 2),
            "verification_coverage": verification_coverage,
            "method": "实际耗用 = 期初实盘 + 期间入库 - 期末实盘；每日领用与报损用于解释耗用组成，不重复扣减；理论耗用 = 销量 × BOM。",
        }

    def forecast(self, revenue_growth_factor: float = 1.0) -> List[Dict[str, Any]]:
        """推算补货建议：断货日期 + 动态采购量 + 建议金额 + 风险等级。

        revenue_growth_factor: 月营收增长率因子（>1 表示增长，<1 表示下降），
        用于根据营业趋势调整补货预测。例如 1.3 表示月营收增长 30%，消耗率同步上调。
        """
        from datetime import datetime, timedelta
        today_date = datetime.now()
        today = today_date.strftime("%Y-%m-%d")
        result = []
        for sku in self.skus:
            if (
                not sku.get("active", True)
                or sku.get("asset_class") == "equipment"
                or not sku.get("reorder_enabled", True)
            ):
                continue
            sku_id = sku.get("id", "")
            stock_by_location = self._stock_map(sku)
            current = float(sku.get("current_stock", 0))
            store_stock = float(stock_by_location.get("store", 0))
            warehouse_stock = float(stock_by_location.get("warehouse", 0))
            unallocated_stock = float(stock_by_location.get("unallocated", 0))
            safety = float(sku.get("safety_stock", 0))
            user_daily = float(sku.get("consumption_per_day", 0))
            unit_cost = float(sku.get("unit_cost", 0))
            batch = int(sku.get("batch_cycle_days", 14))
            lead_days = int(sku.get("supplier_lead_days", 0) or 0)
            target_days = float(sku.get("store_target_days", 0) or 0)

            observed_daily = self._observed_consumption(sku_id)
            daily = (observed_daily if observed_daily > 0 else user_daily) * revenue_growth_factor

            if daily <= 0:
                result.append({
                    "sku_id": sku_id,
                    "name": sku.get("name"),
                    "category": sku.get("category"),
                    "unit": sku.get("unit"),
                    "current_stock": current,
                    "store_stock": store_stock,
                    "warehouse_stock": warehouse_stock,
                    "unallocated_stock": unallocated_stock,
                    "safety_stock": safety,
                    "consumption_per_day": user_daily,
                    "observed_daily_consumption": observed_daily,
                    "days_remaining": None,
                    "stockout_date": None,
                    "recommend_qty": None,
                    "recommend_amount": None,
                    "risk_level": "unknown",
                    "action": "not_enough_data",
                    "missing_inputs": ["连续每日使用记录"],
                    "estimated_date": today,
                })
                continue

            days_remaining = current / daily
            days_remaining_val = round(days_remaining, 1)

            # 断货日期
            stockout_date = None
            if days_remaining > 0:
                stockout = today_date + timedelta(days=days_remaining)
                stockout_date = stockout.strftime("%Y-%m-%d")
            elif current <= safety:
                stockout_date = today  # 已低于安全线，视为即时风险

            # 风险等级
            if current <= 0:
                risk_level = "high"
            elif current <= safety * 0.5:
                risk_level = "high"
            elif current <= safety:
                risk_level = "medium"
            elif days_remaining <= max(lead_days, 1):
                risk_level = "medium"
            else:
                risk_level = "low"

            # 建议采购量 & 金额
            coverage_days = target_days if target_days > 0 else batch
            fill_to = daily * (coverage_days + lead_days) + safety
            gap = max(0.0, fill_to - current)

            if current <= safety:
                recommend_qty = round(gap, 2)
                action = "urgent"
            elif days_remaining <= lead_days + coverage_days:
                recommend_qty = round(gap, 2)
                action = "recommend"
            else:
                recommend_qty = None
                action = "ok"

            recommend_amount = round(recommend_qty * unit_cost, 2) if recommend_qty is not None else None

            result.append({
                "sku_id": sku_id,
                "name": sku.get("name"),
                "category": sku.get("category"),
                "unit": sku.get("unit"),
                "current_stock": current,
                "store_stock": store_stock,
                "warehouse_stock": warehouse_stock,
                "unallocated_stock": unallocated_stock,
                "safety_stock": safety,
                "consumption_per_day": user_daily,
                "observed_daily_consumption": observed_daily,
                "days_remaining": days_remaining_val,
                "stockout_date": stockout_date,
                "recommend_qty": recommend_qty,
                "recommend_amount": recommend_amount,
                "risk_level": risk_level,
                "action": action,
                "supplier_lead_days": lead_days,
                "target_coverage_days": coverage_days,
                "missing_inputs": [],
                "estimated_date": today,
            })
        risk_order = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
        return sorted(result, key=lambda x: (
            risk_order.get(x["risk_level"], 9),
            0 if x["action"] == "urgent" else 1 if x["action"] == "recommend" else 2,
        ))

    def by_category(self) -> Dict[str, List[Dict[str, Any]]]:
        result: Dict[str, List[Dict[str, Any]]] = {}
        for sku in self.skus:
            cat = sku.get("category", "其他")
            result.setdefault(cat, []).append(sku)
        return result

    @staticmethod
    def _stock_status(current: float, safety: float) -> str:
        if current <= 0:
            return "断货"
        if current <= safety * 0.5:
            return "严重不足"
        if current <= safety:
            return "偏低"
        return "正常"

    def menu_analysis(self) -> List[Dict[str, Any]]:
        """菜单工程分析：每 SKU 成本、消耗、利润率估算。"""
        result = []
        for sku in self.skus:
            sku_id = sku.get("id", "")
            name = sku.get("name", "")
            category = sku.get("category", "")
            unit_cost = float(sku.get("unit_cost", 0))
            current_stock = float(sku.get("current_stock", 0))
            safety_stock = float(sku.get("safety_stock", 0))
            daily_consumption = self._observed_consumption(sku_id)
            if daily_consumption <= 0:
                daily_consumption = float(sku.get("consumption_per_day", 0))

            monthly_consumption = round(daily_consumption * 30, 2)
            monthly_cost = round(monthly_consumption * unit_cost, 2)
            stock_days = round(current_stock / max(daily_consumption, 0.001), 1)

            result.append({
                "sku_id": sku_id,
                "name": name,
                "category": category,
                "unit_cost": unit_cost,
                "current_stock": current_stock,
                "safety_stock": safety_stock,
                "daily_consumption": round(daily_consumption, 2),
                "monthly_consumption": monthly_consumption,
                "monthly_cost": monthly_cost,
                "stock_days": stock_days,
                "status": self._stock_status(current_stock, safety_stock),
            })

        result.sort(key=lambda x: x["monthly_cost"], reverse=True)
        return result
