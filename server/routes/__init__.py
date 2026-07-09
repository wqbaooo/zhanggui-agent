#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路由模块"""

from server.routes import audit, capture, chat, documents, finance, labor, model_routing, operating_ledger, projects, reports, skus, sops, speech

__all__ = ["chat", "audit", "finance", "projects", "capture", "documents", "skus", "sops", "labor", "reports", "model_routing", "speech", "operating_ledger"]
