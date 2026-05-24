#!/usr/bin/env python3
"""Agent Harness — 垂直方法论遵循度评测。

评测维度:
1. 知识库引用率 — 回答是否引用了知识库内容
2. 方法论框架应用 — 是否使用了特定的方法论框架
3. 数据源标注 — 是否标注了事实来源和置信度
4. 实地追问 — 是否生成了实地确认清单
"""

import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import 开店Agent

TEST_CASES = [
    {
        "id": "site_transfer",
        "query": "我在新余恒太城五楼美食城，铺位是转租的，月租4500，旁边有正新鸡排，做章鱼烧。帮我分析。",
        "expect": {
            "kb_reference": True,
            "methodology": ["360度", "人·流·场", "转租", "租金营收比"],
            "source_annotation": True,
            "field_checklist": True,
        },
    },
    {
        "id": "finance_basic",
        "query": "我投资10万在县城开早餐店，帮我做财务测算",
        "expect": {
            "kb_reference": True,
            "methodology": ["盈亏平衡", "回本周期", "固定成本", "毛利率"],
            "source_annotation": True,
            "field_checklist": False,
        },
    },
    {
        "id": "franchise_risk",
        "query": "我想加盟大口章鱼烧，加盟费3.5万，品牌方说3个月回本月入2万，靠谱吗？",
        "expect": {
            "kb_reference": True,
            "methodology": ["闭店率", "隐性成本", "加盟商投诉", "快招"],
            "source_annotation": True,
            "field_checklist": True,
        },
    },
    {
        "id": "category_selection",
        "query": "我在三四线城市，预算5万，不知道选什么品类好，帮我分析",
        "expect": {
            "kb_reference": True,
            "methodology": ["品类", "市场容量", "竞争", "客单价"],
            "source_annotation": True,
            "field_checklist": False,
        },
    },
]

def evaluate_response(response: str, expected: dict) -> dict:
    results = {}

    # 1. 知识库引用率
    kb_keywords = ["知识库", "课程", "视频", "勇哥", "案例", "方法论", "360度", "人·流·场"]
    results["kb_referenced"] = any(kw in response for kw in kb_keywords)

    # 2. 方法论框架
    methods_found = [m for m in expected.get("methodology", []) if m in response]
    results["methodology_hits"] = len(methods_found)
    results["methodology_total"] = len(expected.get("methodology", []))
    results["methodology_pct"] = results["methodology_hits"] / max(results["methodology_total"], 1) * 100

    # 3. 数据源标注
    source_keywords = ["高德", "美团", "点评", "实地", "来源", "知识库", "POI"]
    results["source_annotated"] = any(kw in response for kw in source_keywords)

    # 4. 实地追问
    field_keywords = ["实地", "蹲点", "拍照", "确认", "核实", "走访"]
    results["field_checklist"] = any(kw in response for kw in field_keywords)

    return results


def main():
    print("=" * 60)
    print("开店Agent Harness — 垂直方法论遵循度评测")
    print("=" * 60)

    agent = 开店Agent()
    total_cases = len(TEST_CASES)
    passed = 0
    total_methodology = 0
    hit_methodology = 0

    for tc in TEST_CASES:
        print(f"\n[{tc['id']}] 查询: {tc['query'][:50]}...")
        try:
            response = agent.get_response(tc["query"])
            result = evaluate_response(response, tc["expect"])

            kb_ok = "✅" if result["kb_referenced"] else "❌"
            method_ok = f"{result['methodology_hits']}/{result['methodology_total']}"
            source_ok = "✅" if result["source_annotated"] else "❌"
            field_ok = "✅" if result.get("field_checklist") else "—"

            print(f"  知识库引用: {kb_ok} | 方法论: {method_ok} | 数据源: {source_ok} | 实地追问: {field_ok}")

            if result["kb_referenced"]:
                passed += 1
            hit_methodology += result["methodology_hits"]
            total_methodology += result["methodology_total"]
        except Exception as e:
            print(f"  ❌ 执行失败: {e}")

    kb_rate = passed / total_cases * 100 if total_cases else 0
    method_rate = hit_methodology / max(total_methodology, 1) * 100

    print(f"\n{'=' * 60}")
    print(f"知识库引用率: {passed}/{total_cases} ({kb_rate:.0f}%)")
    print(f"方法论命中率: {hit_methodology}/{total_methodology} ({method_rate:.0f}%)")
    print(f"{'=' * 60}")

    return 0 if kb_rate >= 75 else 1


if __name__ == "__main__":
    sys.exit(main())
