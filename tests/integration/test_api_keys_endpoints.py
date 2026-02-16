"""Tests d'intégration pour les endpoints API Keys (CRUD + rotate)."""
import pytest
from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────


def _create_api_key(client: TestClient, headers: dict, **overrides) -> dict:
    """Helper pour créer une API key via l'endpoint."""
    payload = {
        "name": overrides.get("name", "Test Key"),
        "scopes": overrides.get("scopes", ["products:read"]),
        "rate_limit": overrides.get("rate_limit", 500),
    }
    if "expires_at" in overrides:
        payload["expires_at"] = overrides["expires_at"]
    response = client.post("/api/v1/api-keys", json=payload, headers=headers)
    return response


# ── POST /api-keys ───────────────────────────────────────────────────


class TestCreateApiKey:
    """Tests POST /api/v1/api-keys."""

    def test_create_success(self, client: TestClient, auth_headers_admin):
        """Création API key retourne 201 avec full_key visible."""
        response = _create_api_key(
            client, auth_headers_admin,
            name="Caisse Magasin 1",
            scopes=["products:read", "inventory:read"],
            rate_limit=1000,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Caisse Magasin 1"
        assert "full_key" in data
        assert data["full_key"].startswith("mk_live_")
        assert data["key_prefix"] == data["full_key"][:12]
        assert sorted(data["scopes"]) == ["inventory:read", "products:read"]
        assert data["rate_limit"] == 1000
        assert data["is_active"] is True
        assert data["usage_count"] == 0
        assert data["id"] > 0

    def test_create_invalid_scopes_422(self, client: TestClient, auth_headers_admin):
        """Scopes invalides retournent 422."""
        response = _create_api_key(
            client, auth_headers_admin,
            scopes=["fake:scope"],
        )
        assert response.status_code == 422

    def test_create_empty_scopes_422(self, client: TestClient, auth_headers_admin):
        """Scopes vides retournent 422."""
        response = client.post(
            "/api/v1/api-keys",
            json={"name": "Empty", "scopes": []},
            headers=auth_headers_admin,
        )
        assert response.status_code == 422

    def test_create_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission api_keys:write → 403."""
        response = _create_api_key(client, auth_headers_real)
        assert response.status_code == 403

    def test_create_unauthenticated_401(self, client: TestClient):
        """Sans auth → 401."""
        response = client.post(
            "/api/v1/api-keys",
            json={"name": "No Auth", "scopes": ["products:read"]},
        )
        assert response.status_code == 401

    def test_create_deduplicates_scopes(self, client: TestClient, auth_headers_admin):
        """Les scopes dupliqués sont dédupliqués."""
        response = _create_api_key(
            client, auth_headers_admin,
            scopes=["products:read", "products:read", "products:read"],
        )
        assert response.status_code == 201
        data = response.json()
        assert data["scopes"] == ["products:read"]


# ── GET /api-keys ────────────────────────────────────────────────────


class TestListApiKeys:
    """Tests GET /api/v1/api-keys."""

    def test_list_empty(self, client: TestClient, auth_headers_admin):
        """Liste vide quand aucune clé n'existe."""
        response = client.get("/api/v1/api-keys", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_with_keys(self, client: TestClient, auth_headers_admin):
        """Liste retourne les clés créées."""
        _create_api_key(client, auth_headers_admin, name="Key A")
        _create_api_key(client, auth_headers_admin, name="Key B")

        response = client.get("/api/v1/api-keys", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        names = {item["name"] for item in data["items"]}
        assert names == {"Key A", "Key B"}

    def test_list_excludes_revoked_by_default(self, client: TestClient, auth_headers_admin):
        """Les clés révoquées ne sont pas listées par défaut."""
        create_resp = _create_api_key(client, auth_headers_admin, name="To Revoke")
        key_id = create_resp.json()["id"]

        # Révoquer
        client.delete(f"/api/v1/api-keys/{key_id}", headers=auth_headers_admin)

        response = client.get("/api/v1/api-keys", headers=auth_headers_admin)
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_list_includes_revoked_when_requested(self, client: TestClient, auth_headers_admin):
        """include_inactive=true montre les clés révoquées."""
        create_resp = _create_api_key(client, auth_headers_admin, name="Revoked Key")
        key_id = create_resp.json()["id"]
        client.delete(f"/api/v1/api-keys/{key_id}", headers=auth_headers_admin)

        response = client.get(
            "/api/v1/api-keys?include_inactive=true",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["is_active"] is False

    def test_list_pagination(self, client: TestClient, auth_headers_admin):
        """Pagination skip/limit fonctionne."""
        for i in range(5):
            _create_api_key(client, auth_headers_admin, name=f"Key {i}")

        response = client.get(
            "/api/v1/api-keys?skip=2&limit=2",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2

    def test_list_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission api_keys:read → 403."""
        response = client.get("/api/v1/api-keys", headers=auth_headers_real)
        assert response.status_code == 403


# ── GET /api-keys/{id} ──────────────────────────────────────────────


class TestGetApiKey:
    """Tests GET /api/v1/api-keys/{id}."""

    def test_get_success(self, client: TestClient, auth_headers_admin):
        """Récupération d'une clé par ID."""
        create_resp = _create_api_key(
            client, auth_headers_admin,
            name="Detail Key",
            scopes=["products:read", "categories:read"],
        )
        key_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/api-keys/{key_id}", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == key_id
        assert data["name"] == "Detail Key"
        assert "full_key" not in data  # full_key seulement au create/rotate

    def test_get_not_found_404(self, client: TestClient, auth_headers_admin):
        """ID inexistant retourne 404."""
        response = client.get("/api/v1/api-keys/99999", headers=auth_headers_admin)
        assert response.status_code == 404

    def test_get_cross_tenant_404(
        self, client: TestClient, auth_headers_admin, auth_headers_admin_tenant2
    ):
        """Un admin d'un autre tenant ne peut pas voir la clé → 404."""
        create_resp = _create_api_key(client, auth_headers_admin, name="Tenant 1 Key")
        key_id = create_resp.json()["id"]

        response = client.get(
            f"/api/v1/api-keys/{key_id}",
            headers=auth_headers_admin_tenant2,
        )
        assert response.status_code == 404


# ── PATCH /api-keys/{id} ────────────────────────────────────────────


class TestUpdateApiKey:
    """Tests PATCH /api/v1/api-keys/{id}."""

    def test_update_name(self, client: TestClient, auth_headers_admin):
        """Mise à jour du nom."""
        create_resp = _create_api_key(client, auth_headers_admin, name="Old Name")
        key_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/api-keys/{key_id}",
            json={"name": "New Name"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    def test_update_scopes(self, client: TestClient, auth_headers_admin):
        """Mise à jour des scopes."""
        create_resp = _create_api_key(
            client, auth_headers_admin,
            scopes=["products:read"],
        )
        key_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/api-keys/{key_id}",
            json={"scopes": ["products:read", "categories:read"]},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert sorted(response.json()["scopes"]) == ["categories:read", "products:read"]

    def test_update_invalid_scopes_422(self, client: TestClient, auth_headers_admin):
        """Scopes invalides en update → 422."""
        create_resp = _create_api_key(client, auth_headers_admin)
        key_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/api-keys/{key_id}",
            json={"scopes": ["nonexistent:scope"]},
            headers=auth_headers_admin,
        )
        assert response.status_code == 422

    def test_update_not_found_404(self, client: TestClient, auth_headers_admin):
        """Update d'une clé inexistante → 404."""
        response = client.patch(
            "/api/v1/api-keys/99999",
            json={"name": "Ghost"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 404

    def test_update_deactivate(self, client: TestClient, auth_headers_admin):
        """Désactivation d'une clé via PATCH is_active=false."""
        create_resp = _create_api_key(client, auth_headers_admin)
        key_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/api-keys/{key_id}",
            json={"is_active": False},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False


# ── DELETE /api-keys/{id} ────────────────────────────────────────────


class TestRevokeApiKey:
    """Tests DELETE /api/v1/api-keys/{id}."""

    def test_revoke_success(self, client: TestClient, auth_headers_admin):
        """Révocation soft-delete une clé."""
        create_resp = _create_api_key(client, auth_headers_admin, name="To Revoke")
        key_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/v1/api-keys/{key_id}",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

        # Vérifier que GET retourne toujours l'objet (soft delete)
        get_resp = client.get(f"/api/v1/api-keys/{key_id}", headers=auth_headers_admin)
        assert get_resp.status_code == 200
        assert get_resp.json()["is_active"] is False

    def test_revoke_not_found_404(self, client: TestClient, auth_headers_admin):
        """Révocation d'une clé inexistante → 404."""
        response = client.delete("/api/v1/api-keys/99999", headers=auth_headers_admin)
        assert response.status_code == 404

    def test_revoke_cross_tenant_404(
        self, client: TestClient, auth_headers_admin, auth_headers_admin_tenant2
    ):
        """Un admin d'un autre tenant ne peut pas révoquer la clé → 404."""
        create_resp = _create_api_key(client, auth_headers_admin)
        key_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/v1/api-keys/{key_id}",
            headers=auth_headers_admin_tenant2,
        )
        assert response.status_code == 404


# ── POST /api-keys/{id}/rotate ───────────────────────────────────────


class TestRotateApiKey:
    """Tests POST /api/v1/api-keys/{id}/rotate."""

    def test_rotate_success(self, client: TestClient, auth_headers_admin):
        """Rotation génère une nouvelle clé et révoque l'ancienne."""
        create_resp = _create_api_key(
            client, auth_headers_admin,
            name="Rotate Me",
            scopes=["products:read", "categories:read"],
        )
        old_id = create_resp.json()["id"]
        old_full_key = create_resp.json()["full_key"]

        response = client.post(
            f"/api/v1/api-keys/{old_id}/rotate",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()

        # Nouvelle clé générée
        assert "full_key" in data
        assert data["full_key"].startswith("mk_live_")
        assert data["full_key"] != old_full_key
        assert data["id"] != old_id

        # Mêmes attributs hérités
        assert data["name"] == "Rotate Me"
        assert sorted(data["scopes"]) == ["categories:read", "products:read"]
        assert data["is_active"] is True

        # Ancienne clé révoquée
        old_resp = client.get(
            f"/api/v1/api-keys/{old_id}",
            headers=auth_headers_admin,
        )
        assert old_resp.status_code == 200
        assert old_resp.json()["is_active"] is False

    def test_rotate_not_found_404(self, client: TestClient, auth_headers_admin):
        """Rotation d'une clé inexistante → 404."""
        response = client.post(
            "/api/v1/api-keys/99999/rotate",
            headers=auth_headers_admin,
        )
        assert response.status_code == 404

    def test_rotate_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff ne peut pas faire de rotation → 403."""
        response = client.post(
            "/api/v1/api-keys/1/rotate",
            headers=auth_headers_real,
        )
        assert response.status_code == 403
