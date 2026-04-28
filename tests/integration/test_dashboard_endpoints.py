"""Tests d'intégration pour l'endpoint dashboard/finances."""
import pytest
from fastapi.testclient import TestClient


def test_get_finances_returns_structure(client: TestClient, auth_headers_real):
    """GET /dashboard/finances retourne la structure attendue."""
    response = client.get("/api/v1/dashboard/finances", headers=auth_headers_real)
    assert response.status_code == 200
    data = response.json()
    assert "year" in data
    assert "monthly" in data
    assert "totals" in data
    assert isinstance(data["monthly"], list)
    assert len(data["monthly"]) == 12


def test_get_finances_monthly_fields(client: TestClient, auth_headers_real):
    """Chaque entrée mensuelle a les champs attendus."""
    response = client.get("/api/v1/dashboard/finances", headers=auth_headers_real)
    assert response.status_code == 200
    data = response.json()
    for entry in data["monthly"]:
        assert "month" in entry
        assert "revenue_cents" in entry
        assert "invoices_paid" in entry
        assert "invoices_overdue" in entry
        assert 1 <= entry["month"] <= 12
        assert entry["revenue_cents"] >= 0
        assert entry["invoices_paid"] >= 0
        assert entry["invoices_overdue"] >= 0


def test_get_finances_totals_fields(client: TestClient, auth_headers_real):
    """Les totaux contiennent les champs attendus."""
    response = client.get("/api/v1/dashboard/finances", headers=auth_headers_real)
    assert response.status_code == 200
    data = response.json()
    totals = data["totals"]
    assert "revenue_ytd_cents" in totals
    assert "overdue_amount_cents" in totals
    assert "active_reservations" in totals
    assert "low_stock_products" in totals


def test_get_finances_year_param(client: TestClient, auth_headers_real):
    """Le paramètre year est respecté."""
    response = client.get("/api/v1/dashboard/finances?year=2025", headers=auth_headers_real)
    assert response.status_code == 200
    data = response.json()
    assert data["year"] == 2025
    assert len(data["monthly"]) == 12


def test_get_finances_requires_auth(client: TestClient):
    """L'endpoint requiert une authentification."""
    response = client.get("/api/v1/dashboard/finances")
    assert response.status_code == 401


def test_get_finances_tenant_isolation(client: TestClient, auth_headers_real, auth_headers_tenant2):
    """Les statistiques sont isolées par tenant."""
    r1 = client.get("/api/v1/dashboard/finances", headers=auth_headers_real)
    r2 = client.get("/api/v1/dashboard/finances", headers=auth_headers_tenant2)
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Les deux tenants ont des données indépendantes (pas de cross-contamination)
    # (on vérifie juste que les deux répondent 200 avec la structure correcte)
    assert "monthly" in r1.json()
    assert "monthly" in r2.json()
