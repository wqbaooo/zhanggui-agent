#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路由模块"""

from server.routes import audit, capture, chat, documents, finance, labor, model_routing, projects, reports, skus, sops

__all__ = ["chat", "audit", "finance", "projects", "capture", "documents", "skus", "sops", "labor", "reports", "model_routing"]
