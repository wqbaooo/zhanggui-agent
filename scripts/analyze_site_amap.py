#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用高德地图分析候选铺位周边 POI。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from amap_tool import AmapTool  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="高德地图候选铺位分析")
    parser.add_argument("address", help="候选铺位地址")
    parser.add_argument("--city", default=None, help="城市，例如杭州")
    parser.add_argument("--category", default="早餐", help="品类，例如 早餐/小吃/粉面/饮品/快餐")
    parser.add_argument("--radius", type=int, default=1000, help="搜索半径，单位米")
    parser.add_argument("--output", default=None, help="输出 JSON 文件")
    args = parser.parse_args()

    result = AmapTool().analyze_site(args.address, args.category, args.city, args.radius)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
