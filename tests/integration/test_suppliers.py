"""Tests d'intégration pour les endpoints fournisseurs."""
import pytest
from fastapi.testclient import TestClient


class TestSuppliersCRUD:
    """Tests CRUD complets sur /suppliers."""

    def test_list_empty(self, client: TestClient, auth_headers_admin: dict):
        """Liste vide initialement."""
        r = client.get("/api/v1/suppliers", headers=auth_headers_admin)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_ok(self, client: TestClient, auth_headers_admin: dict):
        """Création d'un fournisseur → 201."""
        r = client.post(
            "/api/v1/suppliers",
            json={"name": "Vaisselier Pro", "email": "contact@vaisselier.fr", "phone": "0600000000"},
            headers=auth_headers_admin,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Vaisselier Pro"
        assert data["email"] == "contact@vaisselier.fr"
        assert data["is_active"] is True
        assert "id" in data

    def test_create_duplicate_name_409(self, client: TestClient, auth_headers_admin: dict):
        """Nom dupliqué → 409."""
        payload = {"name": "FournisseurDup"}
        client.post("/api/v1/suppliers", json=payload, headers=auth_headers_admin)
        r = client.post("/api/v1/suppliers", json=payload, headers=auth_headers_admin)
        assert r.status_code == 409

    def test_get_by_id(self, client: TestClient, auth_headers_admin: dict):
        """Récupération par ID."""
        created = client.post(
            "/api/v1/suppliers",
            json={"name": "GetById Supplier"},
            headers=auth_headers_admin,
        ).json()
        r = client.get(f"/api/v1/suppliers/{created['id']}", headers=auth_headers_admin)
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    def test_get_not_found(self, client: TestClient, auth_headers_admin: dict):
        r = client.get("/api/v1/suppliers/99999", headers=auth_headers_admin)
        assert r.status_code == 404

    def test_update_ok(self, client: TestClient, auth_headers_admin: dict):
        """PATCH partiel."""
        created = client.post(
            "/api/v1/suppliers",
            json={"name": "Supplier Update Test"},
            headers=auth_headers_admin,
        ).json()
        r = client.patch(
            f"/api/v1/suppliers/{created['id']}",
            json={"contact_name": "Jean Dupont", "phone": "0700000001"},
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["contact_name"] == "Jean Dupont"
        assert data["phone"] == "0700000001"
        assert data["name"] == "Supplier Update Test"

    def test_delete_ok(self, client: TestClient, auth_headers_admin: dict):
        """Soft delete → 204, puis 404 sur re-lecture."""
        created = client.post(
            "/api/v1/suppliers",
            json={"name": "ToDelete Supplier"},
            headers=auth_headers_admin,
        ).json()
        r = client.delete(f"/api/v1/suppliers/{created['id']}", headers=auth_headers_admin)
        assert r.status_code == 204
        r2 = client.get(f"/api/v1/suppliers/{created['id']}", headers=auth_headers_admin)
        assert r2.status_code == 404

    def test_delete_not_found(self, client: TestClient, auth_headers_admin: dict):
        r = client.delete("/api/v1/suppliers/99999", headers=auth_headers_admin)
        assert r.status_code == 404

    def test_unauthenticated(self, client: TestClient):
        r = client.get("/api/v1/suppliers")
        assert r.status_code == 401


class TestSuppliersTenantIsolation:
    """Isolation multi-tenant."""

    def test_cross_tenant_get_blocked(
        self, client: TestClient, auth_headers_admin: dict, auth_headers_tenant2: dict
    ):
        created = client.post(
            "/api/v1/suppliers",
            json={"name": "Tenant1 Only Supplier"},
            headers=auth_headers_admin,
        ).json()
        r = client.get(f"/api/v1/suppliers/{created['id']}", headers=auth_headers_tenant2)
        assert r.status_code == 404

    def test_cross_tenant_list_isolation(
        self, client: TestClient, auth_headers_admin: dict, auth_headers_tenant2: dict
    ):
        created = client.post(
            "/api/v1/suppliers",
            json={"name": "Tenant1 Only Supplier List"},
            headers=auth_headers_admin,
        ).json()
        r = client.get("/api/v1/suppliers", headers=auth_headers_tenant2)
        ids = [s["id"] for s in r.json()]
        assert created["id"] not in ids
