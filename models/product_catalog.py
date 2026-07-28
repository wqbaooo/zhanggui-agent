#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""销售商品、规格与 BOM 版本档案。

这个档案从空数据开始，只保存店主明确录入的事实。
它不读取历史演示 BOM，也不根据商品名推测用量。
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import PROJECT_DATA_DIR
from models.json_store import atomic_write_json, load_json


@dataclass
class ProductCatalog:
    project_id: str
    products: List[Dict[str, Any]] = field(default_factory=list)
    variants: List[Dict[str, Any]] = field(default_factory=list)
    bom_versions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0

    @property
    def data_file(self) -> Path:
        return PROJECT_DATA_DIR / self.project_id / "products.json"

    @classmethod
    def load(cls, project_id: str) -> Optional["ProductCatalog"]:
        payload = load_json(PROJECT_DATA_DIR / project_id / "products.json")
        if payload is None:
            return None
        return cls(
            project_id=project_id,
            products=list(payload.get("products", [])),
            variants=list(payload.get("variants", [])),
            bom_versions=list(payload.get("bom_versions", [])),
            created_at=float(payload.get("created_at", 0.0)),
            updated_at=float(payload.get("updated_at", 0.0)),
        )

    @classmethod
    def create(cls, project_id: str) -> "ProductCatalog":
        now = time.time()
        catalog = cls(project_id=project_id, created_at=now, updated_at=now)
        catalog.save()
        return catalog

    def save(self) -> None:
        self.updated_at = time.time()
        atomic_write_json(self.data_file, asdict(self))

    def _next_id(self, prefix: str, items: List[Dict[str, Any]]) -> str:
        return f"{prefix}-{int(time.time() * 1000)}-{len(items)}"

    def to_dict(self) -> Dict[str, Any]:
        active_boms: Dict[str, Dict[str, Any]] = {}
        for bom in self.bom_versions:
            variant_id = str(bom.get("variant_id", ""))
            current = active_boms.get(variant_id)
            if current is None or int(bom.get("version", 0)) > int(current.get("version", 0)):
                active_boms[variant_id] = bom
        return {
            "project_id": self.project_id,
            "products": self.products,
            "variants": self.variants,
            "bom_versions": self.bom_versions,
            "active_boms": active_boms,
            "counts": {
                "products": len(self.products),
                "variants": len(self.variants),
                "bom_versions": len(self.bom_versions),
            },
            "updated_at": self.updated_at,
        }

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        return next((item for item in self.products if item.get("id") == product_id), None)

    def get_variant(self, variant_id: str) -> Optional[Dict[str, Any]]:
        return next((item for item in self.variants if item.get("id") == variant_id), None)

    def add_product(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = time.time()
        product = {
            "id": self._next_id("product", self.products),
            "name": payload["name"].strip(),
            "category": payload.get("category", "").strip(),
            "aliases": payload.get("aliases", []),
            "notes": payload.get("notes", "").strip(),
            "active": bool(payload.get("active", True)),
            "created_at": now,
            "updated_at": now,
        }
        self.products.append(product)
        self.save()
        return product

    def update_product(self, product_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        product = self.get_product(product_id)
        if product is None:
            return None
        allowed = {"name", "category", "aliases", "notes", "active"}
        product.update({key: value for key, value in patch.items() if key in allowed and value is not None})
        product["updated_at"] = time.time()
        self.save()
        return product

    def add_variant(self, product_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.get_product(product_id) is None:
            return None
        now = time.time()
        variant = {
            "id": self._next_id("variant", self.variants),
            "product_id": product_id,
            "name": payload["name"].strip(),
            "spec": payload.get("spec", "").strip(),
            "sale_unit": payload.get("sale_unit", "份").strip() or "份",
            "channel_prices": payload.get("channel_prices", []),
            "active": bool(payload.get("active", True)),
            "created_at": now,
            "updated_at": now,
        }
        self.variants.append(variant)
        self.save()
        return variant

    def set_bom(
        self,
        product_id: str,
        variant_id: str,
        payload: Dict[str, Any],
        material_names: Dict[str, str],
    ) -> Optional[Dict[str, Any]]:
        variant = self.get_variant(variant_id)
        if variant is None or variant.get("product_id") != product_id:
            return None
        versions = [
            int(item.get("version", 0))
            for item in self.bom_versions
            if item.get("variant_id") == variant_id
        ]
        lines = [
            {
                "sku_id": line["sku_id"],
                "sku_name": material_names[line["sku_id"]],
                "quantity": float(line["quantity"]),
                "unit": line["unit"].strip(),
            }
            for line in payload["lines"]
        ]
        bom = {
            "id": self._next_id("bom", self.bom_versions),
            "product_id": product_id,
            "variant_id": variant_id,
            "version": max(versions, default=0) + 1,
            "effective_date": payload["effective_date"],
            "source": payload["source"].strip(),
            "notes": payload.get("notes", "").strip(),
            "lines": lines,
            "created_at": time.time(),
        }
        self.bom_versions.append(bom)
        self.save()
        return bom
