#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""销售商品与 BOM 录入路由。"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models.product_catalog import ProductCatalog
from models.sku import SkuCatalog

router = APIRouter(prefix="/projects", tags=["products"])


class ProductAliasInput(BaseModel):
    channel: str = Field(min_length=1)
    name: str = Field(min_length=1)


class ProductCreate(BaseModel):
    name: str = Field(min_length=1)
    category: str = ""
    aliases: List[ProductAliasInput] = Field(default_factory=list)
    notes: str = ""
    active: bool = True


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = None
    aliases: Optional[List[ProductAliasInput]] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


class ChannelPriceInput(BaseModel):
    channel: str = Field(min_length=1)
    price: float = Field(ge=0)


class ProductVariantCreate(BaseModel):
    name: str = Field(min_length=1)
    spec: str = ""
    sale_unit: str = "份"
    channel_prices: List[ChannelPriceInput] = Field(default_factory=list)
    active: bool = True


class BomLineInput(BaseModel):
    sku_id: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1)


class BomCreate(BaseModel):
    effective_date: str = Field(min_length=10, max_length=10)
    source: str = Field(min_length=1)
    notes: str = ""
    lines: List[BomLineInput] = Field(min_length=1)


def _catalog(project_id: str) -> ProductCatalog:
    return ProductCatalog.load(project_id) or ProductCatalog.create(project_id)


@router.get("/{project_id}/products")
async def list_products(project_id: str):
    return _catalog(project_id).to_dict()


@router.get("/{project_id}/products/entry-context")
async def product_entry_context(project_id: str):
    sku_catalog = SkuCatalog.load(project_id) or SkuCatalog.create(project_id)
    materials = [
        sku for sku in sku_catalog.skus
        if sku.get("active", True) and sku.get("asset_class", "inventory") != "equipment"
    ]
    return {
        **_catalog(project_id).to_dict(),
        "materials": materials,
    }


@router.post("/{project_id}/products")
async def create_product(project_id: str, req: ProductCreate):
    product = _catalog(project_id).add_product(req.model_dump())
    return {"success": True, "product": product}


@router.patch("/{project_id}/products/{product_id}")
async def update_product(project_id: str, product_id: str, req: ProductUpdate):
    product = _catalog(project_id).update_product(product_id, req.model_dump(exclude_unset=True))
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return {"success": True, "product": product}


@router.post("/{project_id}/products/{product_id}/variants")
async def create_variant(project_id: str, product_id: str, req: ProductVariantCreate):
    variant = _catalog(project_id).add_variant(product_id, req.model_dump())
    if variant is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return {"success": True, "variant": variant}


@router.put("/{project_id}/products/{product_id}/variants/{variant_id}/bom")
async def save_bom(project_id: str, product_id: str, variant_id: str, req: BomCreate):
    sku_catalog = SkuCatalog.load(project_id) or SkuCatalog.create(project_id)
    materials = {
        sku.get("id", ""): sku.get("name", "")
        for sku in sku_catalog.skus
        if sku.get("active", True) and sku.get("asset_class", "inventory") != "equipment"
    }
    unknown = sorted({line.sku_id for line in req.lines if line.sku_id not in materials})
    if unknown:
        raise HTTPException(status_code=400, detail=f"物料不存在或不可用: {', '.join(unknown)}")
    bom = _catalog(project_id).set_bom(
        product_id,
        variant_id,
        req.model_dump(),
        materials,
    )
    if bom is None:
        raise HTTPException(status_code=404, detail="商品规格不存在")
    return {"success": True, "bom": bom}
