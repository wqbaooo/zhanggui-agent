#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SKU 与进货路由：商品/物料管理和补货预测。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models.sku import PurchaseRecord, SkuCatalog, SkuItem
from server.schemas import (
    PurchaseCreate,
    SkuCreate,
    SkuUpdate,
)

router = APIRouter(prefix="/projects", tags=["skus"])


def _catalog(project_id: str) -> SkuCatalog:
    catalog = SkuCatalog.load(project_id)
    if catalog is None:
        catalog = SkuCatalog.create(project_id)
    return catalog


# ── 列表与创建 ──

@router.get("/{project_id}/skus")
async def list_skus(
    project_id: str,
    category: Optional[str] = Query(None, description="按品类筛选"),
):
    catalog = _catalog(project_id)
    if category:
        grouped = catalog.by_category()
        skus = grouped.get(category, [])
    else:
        skus = catalog.skus
    return {
        "skus": skus,
        "categories": list(catalog.by_category().keys()),
        "total": len(catalog.skus),
    }


@router.post("/{project_id}/skus")
async def create_sku(project_id: str, req: SkuCreate):
    catalog = _catalog(project_id)
    sku = SkuItem(
        name=req.name,
        category=req.category,
        unit=req.unit,
        safety_stock=req.safety_stock,
        current_stock=req.current_stock,
        unit_cost=req.unit_cost,
        supplier=req.supplier,
        batch_cycle_days=req.batch_cycle_days,
        consumption_per_day=req.consumption_per_day,
        notes=req.notes,
        status="正常",
    )
    saved = catalog.add_sku(sku)
    return {"success": True, "sku": saved.to_dict()}


# ── 固定路径子资源（必须在 /{sku_id} 之前注册，避免路由冲突）──

@router.get("/{project_id}/skus/forecast")
async def get_forecast(project_id: str):
    catalog = _catalog(project_id)
    forecast = catalog.forecast()
    return {"forecast": forecast, "total_skus": len(catalog.skus)}


@router.post("/{project_id}/skus/purchase")
async def create_purchase(project_id: str, req: PurchaseCreate):
    catalog = _catalog(project_id)
    purchase = PurchaseRecord(
        date=req.date,
        supplier=req.supplier,
        items=[item.model_dump() if hasattr(item, "model_dump") else item.dict() for item in req.items],
        payment_status=req.payment_status,
        notes=req.notes,
    )
    saved = catalog.record_purchase(purchase)
    return {
        "success": True,
        "purchase": saved.to_dict(),
        "forecast": catalog.forecast(),
    }


@router.get("/{project_id}/skus/purchases")
async def list_purchases(project_id: str, limit: int = Query(30, ge=1, le=200)):
    catalog = _catalog(project_id)
    purchases = catalog.get_purchases(limit=limit)
    return {"purchases": purchases, "total": len(catalog.purchases)}


# ── 单条 SKU CRUD（/{sku_id} 参数化路由）──

@router.get("/{project_id}/skus/{sku_id}")
async def get_sku(project_id: str, sku_id: str):
    catalog = _catalog(project_id)
    sku = catalog.get_sku(sku_id)
    if sku is None:
        raise HTTPException(status_code=404, detail="sku not found")
    return {"sku": sku}


@router.patch("/{project_id}/skus/{sku_id}")
async def update_sku(project_id: str, sku_id: str, req: SkuUpdate):
    catalog = _catalog(project_id)
    payload = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    updated = catalog.update_sku(sku_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="sku not found")
    return {"success": True, "sku": updated}


@router.delete("/{project_id}/skus/{sku_id}")
async def delete_sku(project_id: str, sku_id: str):
    catalog = _catalog(project_id)
    if not catalog.delete_sku(sku_id):
        raise HTTPException(status_code=404, detail="sku not found")
    return {"success": True}
