from fastapi.testclient import TestClient

import config
import models.product_catalog as product_model
import models.sku as sku_model
from server.main import app


def product_client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(product_model, "PROJECT_DATA_DIR", tmp_path)
    monkeypatch.setattr(sku_model, "PROJECT_DATA_DIR", tmp_path)
    return TestClient(app)


def create_material(client, project_id):
    response = client.post(f"/api/projects/{project_id}/skus", json={
        "name": "测试物料",
        "category": "常温食材",
        "unit": "包",
        "display_unit": "包",
    })
    assert response.status_code == 200
    return response.json()["sku"]


def test_product_and_variant_can_be_created_without_invented_bom(tmp_path, monkeypatch):
    client = product_client(tmp_path, monkeypatch)
    project_id = "product-entry"

    product = client.post(f"/api/projects/{project_id}/products", json={
        "name": "测试产品",
        "category": "章鱼烧",
        "aliases": [{"channel": "客如云", "name": "测试产品(标准)"}],
    })
    assert product.status_code == 200
    saved = product.json()["product"]
    assert "bom" not in saved

    variant = client.post(f"/api/projects/{project_id}/products/{saved['id']}/variants", json={
        "name": "标准规格",
        "spec": "店主录入规格",
        "sale_unit": "份",
    })
    assert variant.status_code == 200

    catalog = client.get(f"/api/projects/{project_id}/products").json()
    assert catalog["products"][0]["name"] == "测试产品"
    assert catalog["variants"][0]["name"] == "标准规格"
    assert catalog["bom_versions"] == []


def test_bom_is_versioned_and_rejects_unknown_material(tmp_path, monkeypatch):
    client = product_client(tmp_path, monkeypatch)
    project_id = "product-bom-version"
    material = create_material(client, project_id)
    product = client.post(f"/api/projects/{project_id}/products", json={"name": "测试产品"}).json()["product"]
    variant = client.post(
        f"/api/projects/{project_id}/products/{product['id']}/variants",
        json={"name": "六粒装", "sale_unit": "份"},
    ).json()["variant"]

    unknown = client.put(
        f"/api/projects/{project_id}/products/{product['id']}/variants/{variant['id']}/bom",
        json={"effective_date": "2026-08-01", "source": "店主录入", "lines": [{"sku_id": "missing", "quantity": 1, "unit": "包"}]},
    )
    assert unknown.status_code == 400

    first = client.put(
        f"/api/projects/{project_id}/products/{product['id']}/variants/{variant['id']}/bom",
        json={"effective_date": "2026-08-01", "source": "店主录入", "lines": [{"sku_id": material['id'], "quantity": 1, "unit": "包"}]},
    )
    assert first.status_code == 200
    assert first.json()["bom"]["version"] == 1

    second = client.put(
        f"/api/projects/{project_id}/products/{product['id']}/variants/{variant['id']}/bom",
        json={"effective_date": "2026-08-02", "source": "店主修正", "lines": [{"sku_id": material['id'], "quantity": 2, "unit": "包"}]},
    )
    assert second.status_code == 200
    assert second.json()["bom"]["version"] == 2

    catalog = client.get(f"/api/projects/{project_id}/products").json()
    assert [item["version"] for item in catalog["bom_versions"]] == [1, 2]
    assert catalog["active_boms"][variant["id"]]["lines"][0]["quantity"] == 2


def test_bom_requires_at_least_one_owner_supplied_line(tmp_path, monkeypatch):
    client = product_client(tmp_path, monkeypatch)
    project_id = "product-empty-bom"
    product = client.post(f"/api/projects/{project_id}/products", json={"name": "测试产品"}).json()["product"]
    variant = client.post(
        f"/api/projects/{project_id}/products/{product['id']}/variants",
        json={"name": "标准规格"},
    ).json()["variant"]

    response = client.put(
        f"/api/projects/{project_id}/products/{product['id']}/variants/{variant['id']}/bom",
        json={"effective_date": "2026-08-01", "source": "店主录入", "lines": []},
    )
    assert response.status_code == 422
