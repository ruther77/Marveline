"""Tests intégration — DamageType CRUD + isolation tenant."""
import pytest
from fastapi.testclient import TestClient


class TestDamageTypesCRUD:
    """Tests CRUD complets sur /damage-types."""

    def test_list_damage_types_empty(self, client: TestClient, auth_headers_real: dict):
        """Liste vide initialement."""
        r = client.get("/api/v1/damage-types", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_create_damage_type(
        self, client: TestClient, auth_headers_admin: dict
    ):
        """Création d'un type de dommage → 201."""
        r = client.post(
            "/api/v1/damage-types",
            json={"name": "Assiette cassee", "default_fee_cents": 500},
            headers=auth_headers_admin,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Assiette cassee"
        assert data["default_fee_cents"] == 500
        assert data["is_active"] is True
        assert "id" in data

    def test_create_duplicate_name_returns_409(
        self, client: TestClient, auth_headers_admin: dict
    ):
        """Nom dupliqué → 409."""
        payload = {"name": "Verre brise", "default_fee_cents": 200}
        client.post("/api/v1/damage-types", json=payload, headers=auth_headers_admin)
        r = client.post("/api/v1/damage-types", json=payload, headers=auth_headers_admin)
        assert r.status_code == 409

    def test_get_damage_type_by_id(
        self, client: TestClient, auth_headers_admin: dict, auth_headers_real: dict
    ):
        """Récupération par ID."""
        created = client.post(
            "/api/v1/damage-types",
            json={"name": "Nappe dechiree", "default_fee_cents": 300},
            headers=auth_headers_admin,
        ).json()
        r = client.get(f"/api/v1/damage-types/{created['id']}", headers=auth_headers_real)
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    def test_get_nonexistent_returns_404(
        self, client: TestClient, auth_headers_real: dict
    ):
        """ID inexistant → 404."""
        r = client.get("/api/v1/damage-types/999999", headers=auth_headers_real)
        assert r.status_code == 404

    def test_update_damage_type(
        self, client: TestClient, auth_headers_admin: dict
    ):
        """PATCH partiel mise à jour."""
        created = client.post(
            "/api/v1/damage-types",
            json={"name": "Chaise abimee", "default_fee_cents": 800},
            headers=auth_headers_admin,
        ).json()
        r = client.patch(
            f"/api/v1/damage-types/{created['id']}",
            json={"default_fee_cents": 1000},
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        assert r.json()["default_fee_cents"] == 1000
        assert r.json()["name"] == "Chaise abimee"

    def test_delete_damage_type(
        self, client: TestClient, auth_headers_admin: dict, auth_headers_real: dict
    ):
        """Soft delete → 204, puis 404 sur GET."""
        created = client.post(
            "/api/v1/damage-types",
            json={"name": "Table rayee", "default_fee_cents": 1500},
            headers=auth_headers_admin,
        ).json()
        r = client.delete(
            f"/api/v1/damage-types/{created['id']}", headers=auth_headers_admin
        )
        assert r.status_code == 204
        r2 = client.get(
            f"/api/v1/damage-types/{created['id']}", headers=auth_headers_real
        )
        assert r2.status_code == 404

    def test_default_fee_zero_is_valid(
        self, client: TestClient, auth_headers_admin: dict
    ):
        """default_fee_cents=0 est valide."""
        r = client.post(
            "/api/v1/damage-types",
            json={"name": "Dommage sans tarif", "default_fee_cents": 0},
            headers=auth_headers_admin,
        )
        assert r.status_code == 201

    def test_negative_fee_rejected(
        self, client: TestClient, auth_headers_admin: dict
    ):
        """Tarif négatif → 422."""
        r = client.post(
            "/api/v1/damage-types",
            json={"name": "Invalide", "default_fee_cents": -100},
            headers=auth_headers_admin,
        )
        assert r.status_code == 422


class TestDamageTypesTenantIsolation:
    """Tests isolation multi-tenant."""

    def test_tenant2_cannot_read_tenant1_damage_type(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_tenant2: dict,
    ):
        """Tenant2 obtient 404 sur un type créé par tenant1."""
        created = client.post(
            "/api/v1/damage-types",
            json={"name": "Verre brise tenant1", "default_fee_cents": 200},
            headers=auth_headers_admin,
        ).json()
        r = client.get(
            f"/api/v1/damage-types/{created['id']}", headers=auth_headers_tenant2
        )
        assert r.status_code == 404

    def test_tenant2_list_is_isolated(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_tenant2: dict,
    ):
        """La liste tenant2 ne contient pas les types de tenant1."""
        client.post(
            "/api/v1/damage-types",
            json={"name": "Nappe dechiree t1", "default_fee_cents": 300},
            headers=auth_headers_admin,
        )
        r = client.get("/api/v1/damage-types", headers=auth_headers_tenant2)
        assert r.status_code == 200
        names = [item["name"] for item in r.json()]
        assert "Nappe dechiree t1" not in names
