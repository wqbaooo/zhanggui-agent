#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Model routing inspection route."""

from __future__ import annotations

from fastapi import APIRouter

from server.model_routing import model_routing_state

router = APIRouter(prefix="/model-routing", tags=["model-routing"])


@router.get("")
async def get_model_routing():
    return model_routing_state()
