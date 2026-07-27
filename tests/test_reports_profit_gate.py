from fastapi.testclient import TestClient

from models.reports import ReportArchive
from server.main import app


def test_report_generation_is_blocked_when_profit_is_not_ready():
    client = TestClient(app)
    response = client.post(
        "/api/projects/xinyu-hengtai-dakou/reports/generate?report_type=weekly"
    )

    assert response.status_code == 409
    assert "成本" in response.json()["detail"]


def test_legacy_report_is_explicitly_unverified():
    archive = ReportArchive(
        project_id="test-store",
        reports=[
            {
                "id": "rpt-legacy",
                "status": "generated",
                "generated_at": "2026-07-06 02:19",
                "narrative": "旧口径曾计算利润",
                "net_profit": -3031.32,
                "findings": [{"type": "loss", "title": "当期亏损"}],
            }
        ],
    )

    [report] = archive.list_reports()

    assert report["status"] == "legacy_unverified"
    assert "不可作为正式利润结论" in report["narrative"]
    assert report["net_profit"] is None
    assert report["findings"] == []
