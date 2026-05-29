#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.case_intelligence import build_case_intelligence_guidance, find_similar_external_cases
from core.case_repository import CaseRepository, RestaurantCase
from scripts.ingest_external_cases import build_case_from_text, extract_article_text


def test_repository_upsert_and_search(tmp_path):
    path = tmp_path / "cases.json"
    repo = CaseRepository(path)
    repo.upsert(RestaurantCase(
        case_id="case_1",
        title="商场档口加盟人工过高案例",
        source_role="legal_or_regulatory",
        case_type="legal_dispute",
        city_tier="低线城市",
        location_type="美食城",
        category="小吃",
        mode="加盟",
        failure_reason=["人工", "租金"],
        warning_signal=["承诺收益"],
        agent_rule="先拆老板亲自守店和请人经营两套账。",
        confidence="high",
    ))

    found = repo.search("新余美食城加盟人工", filters={"mode": "加盟", "location_type": "美食城"})

    assert len(found) == 1
    assert found[0].case_id == "case_1"


def test_ingest_extracts_article_and_builds_case():
    html = """
    <html><head><title>加盟纠纷案例</title></head>
    <body><article>法院审理特许经营合同纠纷。加盟商称总部承诺收益，后因租金压力、人工成本和强制采购亏损闭店。</article></body></html>
    """

    title, text = extract_article_text(html)
    case = build_case_from_text("https://example.com/franchise-case", title, text)

    assert title == "加盟纠纷案例"
    assert case.case_type == "legal_dispute"
    assert case.source_role == "legal_or_regulatory"
    assert "加盟" in case.mode
    assert "合同" in case.agent_rule or "两套账" in case.agent_rule


def test_case_intelligence_loads_seed_cases():
    cases = find_similar_external_cases("新余恒太城美食城加盟大口章鱼烧，老板不在店请两个人人工太高")
    guidance = build_case_intelligence_guidance("新余恒太城美食城加盟大口章鱼烧，老板不在店请两个人人工太高")

    assert cases
    assert "外部案例规则" in guidance
    assert "不要直接堆案例给用户" in guidance
