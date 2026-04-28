"""Tests d'intégration pour le endpoint RFM clients."""
import pytest
from fastapi.testclient import TestClient


class TestCustomerRFM:
    def test_rfm_ok(self, client: TestClient, auth_headers_real: dict):
        """Analyse RFM retourne une liste structurée."""
        r = client.get("/api/v1/customers/rfm", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == len(data["items"])

    def test_rfm_item_structure(self, client: TestClient, auth_headers_real: dict):
        """Chaque item RFM a les champs attendus."""
        r = client.get("/api/v1/customers/rfm", headers=auth_headers_real)
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert "customer_id" in item
            assert "customer_name" in item
            assert "recency_days" in item
            assert "frequency" in item
            assert "monetary_cents" in item
            assert "segment" in item
            assert item["segment"] in ("Champions", "Loyal", "Potential", "At Risk", "Lost", "New")

    def test_rfm_unauthenticated(self, client: TestClient):
        r = client.get("/api/v1/customers/rfm")
        assert r.status_code == 401

    def test_rfm_tenant_isolation(
        self, client: TestClient, auth_headers_real: dict, auth_headers_tenant2: dict
    ):
        """Chaque tenant ne voit que ses propres clients."""
        r1 = client.get("/api/v1/customers/rfm", headers=auth_headers_real)
        r2 = client.get("/api/v1/customers/rfm", headers=auth_headers_tenant2)
        assert r1.status_code == 200
        assert r2.status_code == 200
        ids1 = {item["customer_id"] for item in r1.json()["items"]}
        ids2 = {item["customer_id"] for item in r2.json()["items"]}
        # Aucun client en commun entre les deux tenants
        assert ids1.isdisjoint(ids2)
