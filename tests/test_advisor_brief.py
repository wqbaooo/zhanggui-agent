from fastapi.testclient import TestClient
from types import SimpleNamespace

from models.finance_ledger import FinanceLedger
from server.main import app
from server.routes import analyze


PROJECT_ID = "xinyu-hengtai-dakou"


def _context(*reports):
    gaps = [gap for report in reports for gap in report.get("gaps", [])]
    conflicts = [item for report in reports for item in report.get("conflicts", [])]
    return {
        "route": {
            "domains": [report["domain"] for report in reports],
            "consulted_modules": [report["label"] for report in reports],
        },
        "status": "conflict" if conflicts else "needs_input" if gaps else "answered",
        "reports": list(reports),
    }


def _report(domain, label, *, facts=None, gaps=None, conflicts=None, actions=None):
    return {
        "domain": domain,
        "label": label,
        "known_facts": facts or [],
        "hard_rules": [],
        "conflicts": conflicts or [],
        "gaps": gaps or [],
        "professional_guidance": [],
        "proposed_actions": actions or [],
        "evidence": [],
    }


def test_advisor_brief_never_turns_missing_data_into_normal(monkeypatch):
    monkeypatch.setattr(
        analyze,
        "build_domain_context",
        lambda project_id, message: _context(
            _report(
                "channel",
                "外卖渠道",
                gaps=["缺少外卖渠道拆分数据"],
                actions=[{"label": "补平台账单", "target": "/capture"}],
            ),
            _report(
                "procurement_inventory",
                "总部物料、采购与门店库存",
                gaps=["本店尚未录入相关物料库存"],
                actions=[{"label": "补录或盘点库存", "target": "/inventory"}],
            ),
        ),
    )
    monkeypatch.setattr(analyze, "_latest_business_date", lambda project_id: None)

    response = TestClient(app).get(f"/api/projects/{PROJECT_ID}/analyze/advisor-brief")

    assert response.status_code == 200
    brief = response.json()
    assert brief["permission"] == "read_only"
    assert brief["data_status"] == "empty"
    assert brief["latest_fact_date"] is None
    assert "正常" not in brief["headline"]
    assert all(section["status"] == "unknown" for section in brief["sections"])
    assert {item["target"] for item in brief["priority_actions"]} == {
        "/capture",
        "/inventory",
    }


def test_advisor_brief_separates_known_facts_gaps_and_conflicts(monkeypatch):
    monkeypatch.setattr(
        analyze,
        "build_domain_context",
        lambda project_id, message: _context(
            _report(
                "finance",
                "利润与经营台账",
                facts=[{
                    "fact": "期间经营摘要",
                    "values": {
                        "entry_count": 10,
                        "total_revenue": 11879.78,
                        "total_orders": 778,
                        "net_profit": None,
                    },
                    "source": "SQLite 财务账本",
                }],
                gaps=["食材成本尚未闭合"],
                conflicts=[{
                    "type": "finance_incomplete",
                    "message": "营业收入已确认，但暂不能确认净利润。",
                }],
                actions=[{"label": "补齐成本", "target": "/profit"}],
            ),
        ),
    )
    monkeypatch.setattr(analyze, "_latest_business_date", lambda project_id: "2026-07-16")

    response = TestClient(app).get(f"/api/projects/{PROJECT_ID}/analyze/advisor-brief")

    assert response.status_code == 200
    brief = response.json()
    section = brief["sections"][0]
    assert brief["calendar_date"]
    assert brief["latest_fact_date"] == "2026-07-16"
    assert brief["data_status"] == "conflict"
    assert section["status"] == "conflict"
    assert section["facts"][0]["summary"].startswith("已确认 10 天")
    assert "净利润暂不能确认" in section["facts"][0]["summary"]
    assert section["gaps"] == ["食材成本尚未闭合"]
    assert section["conflicts"][0]["message"] == "营业收入已确认，但暂不能确认净利润。"


def test_advisor_brief_rejects_other_projects():
    response = TestClient(app).get("/api/projects/demo-store/analyze/advisor-brief")

    assert response.status_code == 403


def test_latest_fact_date_uses_last_data_date_not_query_period_end(monkeypatch):
    monkeypatch.setattr(
        analyze.ProjectMemory,
        "load",
        classmethod(lambda cls, project_id: SimpleNamespace(
            daily_operations=[{"date": "2026-07-12"}],
        )),
    )

    class FakeLedger:
        def finance_overview(self, project_id):
            return {
                "sales_days": 12,
                "period_end": "2026-07-19",
                "last_data_date": "2026-07-16",
            }

    monkeypatch.setattr(
        FinanceLedger,
        "for_project",
        classmethod(lambda cls, project_id: FakeLedger()),
    )

    assert analyze._latest_business_date(PROJECT_ID) == "2026-07-16"
