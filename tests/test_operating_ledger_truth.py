import json

from fastapi.testclient import TestClient

import config
from models.operating_ledger import OperatingLedger, project_path, today
from server.main import app


def test_missing_operating_ledger_starts_empty_instead_of_seeding_sample_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)

    ledger = OperatingLedger.load("truth-empty")

    assert ledger.raw_materials == []
    assert ledger.business_facts == []
    assert ledger.ledger_entries == []
    assert not project_path("truth-empty").exists()


def test_schema_version_drift_preserves_existing_store_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    path = project_path("truth-version")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "project_id": "truth-version",
        "fixture_version": "older-version",
        "raw_materials": [{"id": "real-source", "title": "真实资料"}],
        "business_facts": [{"id": "real-fact", "date": "2026-07-17"}],
        "ledger_entries": [{"id": "real-entry", "date": "2026-07-17"}],
        "inventory_items": [],
        "inventory_movements": [],
        "products": [],
        "product_variants": [],
        "channel_prices": [],
        "product_boms": [],
    }, ensure_ascii=False), encoding="utf-8")

    ledger = OperatingLedger.load("truth-version")

    assert ledger.raw_materials == [{"id": "real-source", "title": "真实资料"}]
    assert ledger.business_facts == [{"id": "real-fact", "date": "2026-07-17"}]
    assert ledger.ledger_entries == [{"id": "real-entry", "date": "2026-07-17"}]


def test_today_operating_card_defaults_to_shanghai_today(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)

    response = TestClient(app).get("/api/projects/truth-today/today-operating-card")

    assert response.status_code == 200
    assert response.json()["date"] == today()
    assert response.json()["fixture_sales"] == {}
