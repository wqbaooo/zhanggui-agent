"""HTTP handlers that can only read the product's existing fact APIs."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _base_url() -> str:
    return os.getenv("ZHANGGUI_API_BASE", "http://127.0.0.1:8000").rstrip("/")


def _project_id() -> str:
    return os.getenv("ZHANGGUI_PROJECT_ID", "xinyu-hengtai-dakou")


def _date(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not _DATE_RE.fullmatch(text):
        raise ValueError(f"{field} 必须是 YYYY-MM-DD")
    return text


def _get(path: str, params: dict | None = None) -> str:
    url = f"{_base_url()}{path}"
    if params:
        clean = {key: value for key, value in params.items() if value not in (None, "")}
        if clean:
            url = f"{url}?{urllib.parse.urlencode(clean)}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return json.dumps(
            {"source": url, "read_only": True, "data": payload},
            ensure_ascii=False,
            default=str,
        )
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return json.dumps({"error": f"门店事实接口不可用: {exc}"}, ensure_ascii=False)


def finance_overview(args: dict, **kwargs) -> str:
    try:
        params = {}
        if args.get("start"):
            params["start"] = _date(args["start"], "start")
        if args.get("end"):
            params["end"] = _date(args["end"], "end")
        return _get(f"/api/projects/{_project_id()}/finance/overview", params)
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def finance_date_coverage(args: dict, **kwargs) -> str:
    try:
        start = _date(args.get("start"), "start")
        end = _date(args.get("end"), "end")
        return _get(
            f"/api/projects/{_project_id()}/finance/daily-revenue-checklist",
            {"start": start, "end": end},
        )
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def daily_finance(args: dict, **kwargs) -> str:
    try:
        date = _date(args.get("date"), "date")
        return _get(f"/api/projects/{_project_id()}/finance/daily-snapshot", {"date": date})
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def cash_forecast(args: dict, **kwargs) -> str:
    try:
        as_of = _date(args["as_of"], "as_of") if args.get("as_of") else None
        return _get(f"/api/projects/{_project_id()}/finance/cash-forecast", {"as_of": as_of})
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def inventory_summary(args: dict, **kwargs) -> str:
    return _get(f"/api/projects/{_project_id()}/skus/inventory-summary")


def operations_summary(args: dict, **kwargs) -> str:
    try:
        days = max(1, min(366, int(args.get("days") or 30)))
    except (TypeError, ValueError):
        return json.dumps({"error": "days 必须是 1 到 366 的整数"}, ensure_ascii=False)
    return _get(f"/api/projects/{_project_id()}/operations/summary", {"days": days})
