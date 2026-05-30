#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计 Agent 当前到底读进了哪些资料。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from 掌柜Agent import 掌柜Agent  # noqa: E402


def main():
    agent = 掌柜Agent()
    print(json.dumps(agent.audit_sources(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
