"""Tests intégration GET/PATCH /admin/settings."""
import pytest
from fastapi.testclient import TestClient


def test_get_settings_admin(client: TestClient, auth_headers_admin: dict):
    resp = client.get("/api/v1/admin/settings", headers=auth_headers_admin)
    assert resp.status_code == 200
    data = resp.json()
    assert "vat_rate" in data
    assert "hourly_rate_weekday" in data
    assert data["vat_rate"] == pytest.approx(0.20)


def test_get_settings_forbidden_staff(client: TestClient, auth_headers_real: dict):
    resp = client.get("/api/v1/admin/settings", headers=auth_headers_real)
    assert resp.status_code == 403


def test_patch_settings_admin(client: TestClient, auth_headers_admin: dict):
    resp = client.patch(
        "/api/v1/admin/settings",
        json={"company_name": "Ma Société", "vat_rate": 0.10},
        headers=auth_headers_admin,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_name"] == "Ma Société"
    assert data["vat_rate"] == pytest.approx(0.10)


def test_patch_settings_forbidden_staff(client: TestClient, auth_headers_real: dict):
    resp = client.patch(
        "/api/v1/admin/settings",
        json={"company_name": "Hack"},
        headers=auth_headers_real,
    )
    assert resp.status_code == 403


def test_patch_settings_cross_tenant_isolation(
    client: TestClient,
    auth_headers_admin: dict,
    auth_headers_admin_tenant2: dict,
):
    """Tenant 1 ne voit pas les settings de tenant 2."""
    client.patch(
        "/api/v1/admin/settings",
        json={"company_name": "Tenant1 Corp"},
        headers=auth_headers_admin,
    )
    resp2 = client.get("/api/v1/admin/settings", headers=auth_headers_admin_tenant2)
    assert resp2.status_code == 200
    assert resp2.json().get("company_name") != "Tenant1 Corp"
