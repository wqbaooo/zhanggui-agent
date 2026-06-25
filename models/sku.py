#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SKU 目录与进货预测模型：食材、包装、耗材的库存管理和补货推算。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import PROJECT_DATA_DIR

SKU_CATEGORIES = ["食材", "包装", "耗材", "清洁", "其他"]
SKU_UNITS = ["kg", "g", "个", "包", "箱", "卷", "双", "袋", "瓶", "桶", "张", "套"]


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
            "notes": "", "created_at": 0.0, "updated_at": 0.0,
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
    notes: str = ""
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SkuCatalog:
    """SKU 目录：管理该项目的全部 SKU 和进货记录。"""
    project_id: str
    skus: List[Dict[str, Any]] = field(default_factory=list)
    purchases: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    @property
    def data_file(self) -> Path:
        return PROJECT_DATA_DIR / self.project_id / "skus.json"

    def save(self):
        self.updated_at = time.time()
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, project_id: str) -> Optional["SkuCatalog"]:
        path = PROJECT_DATA_DIR / project_id / "skus.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**data)
        except Exception:
            return None

    @classmethod
    def create(cls, project_id: str) -> "SkuCatalog":
        catalog = cls(project_id=project_id)
        catalog.save()
        return catalog

    def _next_id(self, prefix: str) -> str:
        now = int(time.time() * 1000)
        items = self.skus if prefix == "sku" else self.purchases
        return f"{prefix}-{now}-{len(items)}"

    def add_sku(self, sku: SkuItem) -> SkuItem:
        now = time.time()
        if not sku.id:
            sku.id = self._next_id("sku")
        sku.created_at = now
        sku.updated_at = now
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

        for item in purchase.items:
            sku_id = item.get("sku_id", "")
            qty = float(item.get("quantity", 0))
            cost = float(item.get("unit_cost", 0))
            item["subtotal"] = round(qty * cost, 2)

        purchase.total_cost = round(sum(
            float(i.get("subtotal", 0)) for i in purchase.items
        ), 2)

        self.purchases.append(purchase.to_dict())

        for item in purchase.items:
            for i, sku in enumerate(self.skus):
                if sku.get("id") == item.get("sku_id"):
                    old_qty = float(sku.get("current_stock", 0))
                    add_qty = float(item.get("quantity", 0))
                    self.skus[i]["current_stock"] = round(old_qty + add_qty, 4)
                    self.skus[i]["last_purchase_date"] = purchase.date
                    self.skus[i]["unit_cost"] = float(item.get("unit_cost", 0))
                    self.skus[i]["updated_at"] = now
                    safety = float(self.skus[i].get("safety_stock", 0))
                    self.skus[i]["status"] = self._stock_status(
                        self.skus[i]["current_stock"], safety,
                    )

        self.save()
        return purchase

    def get_purchases(self, limit: int = 30) -> List[Dict[str, Any]]:
        return sorted(
            self.purchases, key=lambda p: p.get("date", ""), reverse=True,
        )[:limit]

    def forecast(self) -> List[Dict[str, Any]]:
        """基于消耗速度 + 安全库存推算补货建议。"""
        from datetime import datetime, timedelta
        today = datetime.now().strftime("%Y-%m-%d")
        result = []
        for sku in self.skus:
            current = float(sku.get("current_stock", 0))
            safety = float(sku.get("safety_stock", 0))
            daily = float(sku.get("consumption_per_day", 0))
            batch = int(sku.get("batch_cycle_days", 14))

            if daily <= 0:
                days_remaining = None
                recommend_qty = None
                action = "not_enough_data"
            else:
                days_remaining = max(0, (current - safety) / daily)
                if current <= safety:
                    recommend_qty = round(daily * batch + safety - current, 2)
                    action = "urgent"
                elif days_remaining <= batch:
                    recommend_qty = round(daily * batch, 2)
                    action = "recommend"
                else:
                    recommend_qty = None
                    action = "ok"

            result.append({
                "sku_id": sku.get("id"),
                "name": sku.get("name"),
                "category": sku.get("category"),
                "unit": sku.get("unit"),
                "current_stock": current,
                "safety_stock": safety,
                "consumption_per_day": daily,
                "days_remaining": round(days_remaining, 1) if days_remaining is not None else None,
                "recommend_qty": recommend_qty,
                "action": action,
                "estimated_date": today,
            })
        return sorted(result, key=lambda x: (x["action"] != "urgent", x["action"] != "recommend"))

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
