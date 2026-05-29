#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ingest external restaurant/franchise cases into the structured case library.

The crawler is intentionally conservative: it stores source URL, confidence and
case-derived operating rules, not unsupported revenue claims.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from core.case_repository import DEFAULT_CASE_PATH, CaseRepository, RestaurantCase


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    )
}


def fetch_html(url: str, timeout: int = 15) -> str:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_article_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    candidates = soup.select("article, main, .article, .content, .post, .rich_media_content")
    blocks = candidates or [soup.body or soup]
    text = "\n".join(block.get_text("\n", strip=True) for block in blocks)
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 2]
    return title[:120], "\n".join(lines)


def search_urls(query: str, limit: int = 5) -> List[str]:
    try:
        from duckduckgo_search import DDGS
    except Exception:
        return []
    urls: List[str] = []
    with DDGS() as ddgs:
        for result in ddgs.text(query, max_results=limit):
            href = result.get("href") or result.get("url")
            if href:
                urls.append(href)
    return urls


def build_case_from_text(url: str, title: str, text: str) -> RestaurantCase:
    compact = _compact_text(text)
    case_type = _detect_case_type(compact)
    failure_reason = _extract_reasons(compact, FAILURE_TERMS)
    success_pattern = _extract_reasons(compact, SUCCESS_TERMS)
    warning_signal = _extract_reasons(compact, WARNING_TERMS)
    source_role = _detect_source_role(url, compact)
    category = _first_match(compact, ("章鱼烧", "奶茶", "咖啡", "小吃", "早餐", "快餐", "火锅", "烧烤"))
    location_type = _first_match(compact, ("商场", "美食城", "档口", "社区", "学校", "街边", "夜市"))
    mode = "加盟" if any(term in compact for term in ("加盟", "总部", "品牌方", "特许经营")) else ""
    city_tier = "低线城市" if any(term in compact for term in ("县城", "三四线", "下沉", "乡镇", "新余")) else ""

    rule = _derive_agent_rule(
        mode=mode,
        location_type=location_type,
        failure_reason=failure_reason,
        success_pattern=success_pattern,
        warning_signal=warning_signal,
        compact=compact,
    )

    return RestaurantCase(
        case_id=_case_id(url),
        title=title or _fallback_title(compact, url),
        source_role=source_role,
        case_type=case_type,
        city_tier=city_tier,
        location_type=location_type,
        category=category,
        mode=mode,
        failure_reason=failure_reason[:5],
        success_pattern=success_pattern[:5],
        warning_signal=warning_signal[:5],
        agent_rule=rule,
        source_url=url,
        confidence=_confidence(source_role, text),
        notes=compact[:260],
    )


def ingest_urls(urls: Iterable[str], out: Path = DEFAULT_CASE_PATH, dry_run: bool = False) -> List[RestaurantCase]:
    repo = CaseRepository(out)
    ingested: List[RestaurantCase] = []
    for url in urls:
        html = fetch_html(url)
        title, text = extract_article_text(html)
        case = build_case_from_text(url, title, text)
        ingested.append(case)
        if not dry_run:
            repo.upsert(case)
    return ingested


FAILURE_TERMS = (
    "亏损", "倒闭", "闭店", "退费", "纠纷", "诉讼", "租金", "人工", "成本高", "选址",
    "总部", "供货", "培训", "虚假宣传", "回本", "同品牌", "区域保护", "外卖扣点",
)
SUCCESS_TERMS = (
    "复购", "标准化", "单店模型", "供应链", "选址", "坪效", "会员", "多店", "培训", "出餐速度",
)
WARNING_TERMS = (
    "承诺收益", "低投资高回报", "快速回本", "不退", "强制采购", "区域保护", "装修费", "管理费",
    "人工成本", "租金压力", "活动补贴",
)


def _case_id(url: str) -> str:
    parsed = urlparse(url)
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", parsed.netloc).strip("_")[:32] or "case"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"external_{slug}_{digest}"


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _detect_case_type(text: str) -> str:
    if any(term in text for term in ("法院", "判决", "特许经营合同", "诉讼")):
        return "legal_dispute"
    if any(term in text for term in ("超级加盟商", "多店", "扩张")):
        return "operator_playbook"
    if any(term in text for term in ("投资人", "资本", "上市", "单店模型")):
        return "investor_analysis"
    return "operator_case"


def _detect_source_role(url: str, text: str) -> str:
    host = urlparse(url).netloc
    if any(term in text for term in ("法院", "判决", "裁判", "特许经营合同")):
        return "legal_or_regulatory"
    if any(term in text for term in ("超级加盟商", "多店加盟商")):
        return "super_franchisee"
    if any(domain in host for domain in ("cbndata", "huxiu", "36kr")) or "投资" in text:
        return "investor"
    if "加盟" in text:
        return "operator"
    return "influencer_content"


def _confidence(source_role: str, text: str) -> str:
    if source_role == "legal_or_regulatory":
        return "high"
    if source_role in {"super_franchisee", "investor"} and len(text) > 1200:
        return "medium"
    return "low"


def _extract_reasons(text: str, terms: Iterable[str]) -> List[str]:
    hits = []
    for term in terms:
        if term in text:
            hits.append(term)
    return hits


def _derive_agent_rule(
    mode: str,
    location_type: str,
    failure_reason: List[str],
    success_pattern: List[str],
    warning_signal: List[str],
    compact: str,
) -> str:
    if "人工" in "".join(failure_reason) or "人工成本" in "".join(warning_signal):
        return "先拆老板亲自守店和请人经营两套账；营业额不能替代净现金流。"
    if mode == "加盟" and any(term in compact for term in ("合同", "总部", "供货", "管理费", "区域保护")):
        return "加盟项目先验合同约束、供货价、区域保护和退出条款，再谈营销增长。"
    if location_type in {"商场", "美食城", "档口"}:
        return "商场档口优先验证高峰转化、出餐速度、同层竞品和租金抽成压力。"
    if "单店模型" in "".join(success_pattern) or "多店" in compact:
        return "把可复制单店模型放在扩张前面，确认店长、SOP、供应链和利润留存。"
    if "外卖扣点" in "".join(failure_reason) or "活动补贴" in "".join(warning_signal):
        return "外卖、团购、满减必须逐单核算实收、扣点、包装和补贴后的利润。"
    return "把外部案例转成自己的验收清单：客流、毛利、人工、租金、合同和止损线逐项验证。"


def _first_match(text: str, candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if candidate in text:
            return candidate
    return ""


def _fallback_title(text: str, url: str) -> str:
    if text:
        return text[:36]
    return urlparse(url).netloc or "外部案例"


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="餐饮开店外部案例采集")
    parser.add_argument("--url", action="append", default=[], help="直接采集的文章 URL，可重复")
    parser.add_argument("--query", action="append", default=[], help="搜索关键词，可重复")
    parser.add_argument("--limit", type=int, default=5, help="每个 query 最多抓取链接数")
    parser.add_argument("--out", type=Path, default=DEFAULT_CASE_PATH, help="输出 structured_cases.json")
    parser.add_argument("--dry-run", action="store_true", help="只打印结果，不写入")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    urls = list(args.url)
    for query in args.query:
        urls.extend(search_urls(query, limit=args.limit))
    seen = []
    for url in urls:
        if url not in seen:
            seen.append(url)
    cases = ingest_urls(seen, out=args.out, dry_run=args.dry_run)
    for case in cases:
        print(asdict(case))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
