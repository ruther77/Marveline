"""Tests d'intégration pour les endpoints Feature Flags (CRUD + evaluate)."""
import pytest
from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────


def _create_flag(client: TestClient, headers: dict, **overrides) -> dict:
    """Helper pour créer un feature flag via l'endpoint."""
    payload = {
        "name": overrides.get("name", "test_flag"),
        "description": overrides.get("description", "A test flag"),
        "is_enabled": overrides.get("is_enabled", True),
        "rollout_pct": overrides.get("rollout_pct", 100),
    }
    if "target_tenants" in overrides:
        payload["target_tenants"] = overrides["target_tenants"]
    if "metadata_json" in overrides:
        payload["metadata_json"] = overrides["metadata_json"]
    return client.post("/api/v1/features", json=payload, headers=headers)


# ── POST /features ───────────────────────────────────────────────────


class TestCreateFeatureFlag:
    """Tests POST /api/v1/features."""

    def test_create_success(self, client: TestClient, auth_headers_admin):
        """Création d'un flag retourne 201."""
        response = _create_flag(
            client, auth_headers_admin,
            name="stripe_payments",
            description="Active Stripe Checkout",
            is_enabled=True,
            rollout_pct=100,
            target_tenants=[1, 2],
            metadata_json={"tier": "premium"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "stripe_payments"
        assert data["description"] == "Active Stripe Checkout"
        assert data["is_enabled"] is True
        assert data["rollout_pct"] == 100
        assert data["target_tenants"] == [1, 2]
        assert data["metadata_json"] == {"tier": "premium"}
        assert data["id"] > 0

    def test_create_minimal(self, client: TestClient, auth_headers_admin):
        """Création avec uniquement les champs obligatoires."""
        response = _create_flag(
            client, auth_headers_admin,
            name="minimal_flag",
            is_enabled=False,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "minimal_flag"
        assert data["is_enabled"] is False
        assert data["rollout_pct"] == 100
        assert data["target_tenants"] is None

    def test_create_duplicate_name_409(self, client: TestClient, auth_headers_admin):
        """Nom dupliqué retourne 409."""
        _create_flag(client, auth_headers_admin, name="unique_flag")
        response = _create_flag(client, auth_headers_admin, name="unique_flag")
        assert response.status_code == 409

    def test_create_invalid_name_format_422(self, client: TestClient, auth_headers_admin):
        """Nom avec format invalide (pas snake_case) → 422."""
        response = _create_flag(client, auth_headers_admin, name="Invalid-Name")
        assert response.status_code == 422

    def test_create_rollout_out_of_range_422(self, client: TestClient, auth_headers_admin):
        """rollout_pct > 100 → 422."""
        response = _create_flag(
            client, auth_headers_admin,
            name="bad_rollout",
            rollout_pct=150,
        )
        assert response.status_code == 422

    def test_create_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission features:write → 403."""
        response = _create_flag(client, auth_headers_real, name="no_perm")
        assert response.status_code == 403

    def test_create_unauthenticated_401(self, client: TestClient):
        """Sans auth → 401."""
        response = client.post(
            "/api/v1/features",
            json={"name": "no_auth", "is_enabled": True},
        )
        assert response.status_code == 401


# ── GET /features ────────────────────────────────────────────────────


class TestListFeatureFlags:
    """Tests GET /api/v1/features."""

    def test_list_empty(self, client: TestClient, auth_headers_admin):
        """Liste vide quand aucun flag n'existe."""
        response = client.get("/api/v1/features", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_with_flags(self, client: TestClient, auth_headers_admin):
        """Liste retourne les flags créés."""
        _create_flag(client, auth_headers_admin, name="flag_a")
        _create_flag(client, auth_headers_admin, name="flag_b")

        response = client.get("/api/v1/features", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        names = {item["name"] for item in data["items"]}
        assert names == {"flag_a", "flag_b"}

    def test_list_pagination(self, client: TestClient, auth_headers_admin):
        """Pagination skip/limit fonctionne."""
        for i in range(5):
            _create_flag(client, auth_headers_admin, name=f"flag_{i}")

        response = client.get(
            "/api/v1/features?skip=2&limit=2",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2

    def test_list_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission features:read → 403."""
        response = client.get("/api/v1/features", headers=auth_headers_real)
        assert response.status_code == 403


# ── GET /features/{id} ──────────────────────────────────────────────


class TestGetFeatureFlag:
    """Tests GET /api/v1/features/{id}."""

    def test_get_success(self, client: TestClient, auth_headers_admin):
        """Récupération d'un flag par ID."""
        create_resp = _create_flag(
            client, auth_headers_admin,
            name="detail_flag",
            description="Detailed flag",
        )
        flag_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/features/{flag_id}", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == flag_id
        assert data["name"] == "detail_flag"
        assert data["description"] == "Detailed flag"

    def test_get_not_found_404(self, client: TestClient, auth_headers_admin):
        """ID inexistant retourne 404."""
        response = client.get("/api/v1/features/99999", headers=auth_headers_admin)
        assert response.status_code == 404


# ── PATCH /features/{id} ────────────────────────────────────────────


class TestUpdateFeatureFlag:
    """Tests PATCH /api/v1/features/{id}."""

    def test_update_description(self, client: TestClient, auth_headers_admin):
        """Mise à jour de la description."""
        create_resp = _create_flag(client, auth_headers_admin, name="update_desc")
        flag_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/features/{flag_id}",
            json={"description": "New description"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json()["description"] == "New description"

    def test_update_toggle_enabled(self, client: TestClient, auth_headers_admin):
        """Toggle is_enabled."""
        create_resp = _create_flag(
            client, auth_headers_admin,
            name="toggle_flag",
            is_enabled=True,
        )
        flag_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/features/{flag_id}",
            json={"is_enabled": False},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json()["is_enabled"] is False

    def test_update_rollout_pct(self, client: TestClient, auth_headers_admin):
        """Mise à jour du rollout_pct."""
        create_resp = _create_flag(
            client, auth_headers_admin,
            name="rollout_flag",
            rollout_pct=100,
        )
        flag_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/features/{flag_id}",
            json={"rollout_pct": 50},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json()["rollout_pct"] == 50

    def test_update_target_tenants(self, client: TestClient, auth_headers_admin):
        """Mise à jour de target_tenants."""
        create_resp = _create_flag(
            client, auth_headers_admin,
            name="target_flag",
            target_tenants=[1],
        )
        flag_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/features/{flag_id}",
            json={"target_tenants": [1, 2, 3]},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json()["target_tenants"] == [1, 2, 3]

    def test_update_not_found_404(self, client: TestClient, auth_headers_admin):
        """Update d'un flag inexistant → 404."""
        response = client.patch(
            "/api/v1/features/99999",
            json={"is_enabled": False},
            headers=auth_headers_admin,
        )
        assert response.status_code == 404


# ── DELETE /features/{id} ────────────────────────────────────────────


class TestDeleteFeatureFlag:
    """Tests DELETE /api/v1/features/{id}."""

    def test_delete_success(self, client: TestClient, auth_headers_admin):
        """Suppression hard-delete un flag → 204."""
        create_resp = _create_flag(client, auth_headers_admin, name="to_delete")
        flag_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/v1/features/{flag_id}",
            headers=auth_headers_admin,
        )
        assert response.status_code == 204

        # Vérifier que GET retourne 404
        get_resp = client.get(f"/api/v1/features/{flag_id}", headers=auth_headers_admin)
        assert get_resp.status_code == 404

    def test_delete_not_found_404(self, client: TestClient, auth_headers_admin):
        """Suppression d'un flag inexistant → 404."""
        response = client.delete("/api/v1/features/99999", headers=auth_headers_admin)
        assert response.status_code == 404

    def test_delete_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff ne peut pas supprimer un flag → 403."""
        response = client.delete("/api/v1/features/1", headers=auth_headers_real)
        assert response.status_code == 403


# ── GET /features/check/{flag_name} ─────────────────────────────────


class TestCheckFeatureFlag:
    """Tests GET /api/v1/features/check/{flag_name}?tenant_id=X."""

    def test_check_enabled_whitelist(self, client: TestClient, auth_headers_admin):
        """Flag activé avec tenant dans la whitelist → enabled=true, reason=whitelist."""
        _create_flag(
            client, auth_headers_admin,
            name="whitelist_flag",
            is_enabled=True,
            target_tenants=[1, 2],
        )

        response = client.get(
            "/api/v1/features/check/whitelist_flag?tenant_id=1",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["reason"] == "whitelist"

    def test_check_not_in_whitelist(self, client: TestClient, auth_headers_admin):
        """Tenant pas dans la whitelist → enabled=false, reason=not_in_whitelist."""
        _create_flag(
            client, auth_headers_admin,
            name="restricted_flag",
            is_enabled=True,
            target_tenants=[2, 3],
        )

        response = client.get(
            "/api/v1/features/check/restricted_flag?tenant_id=1",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["reason"] == "not_in_whitelist"

    def test_check_kill_switch(self, client: TestClient, auth_headers_admin):
        """Flag désactivé (is_enabled=false) → enabled=false, reason=kill_switch."""
        _create_flag(
            client, auth_headers_admin,
            name="killed_flag",
            is_enabled=False,
            target_tenants=[1],
        )

        response = client.get(
            "/api/v1/features/check/killed_flag?tenant_id=1",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["reason"] == "kill_switch"

    def test_check_rollout_100pct(self, client: TestClient, auth_headers_admin):
        """Rollout 100% sans whitelist → enabled=true, reason=rollout."""
        _create_flag(
            client, auth_headers_admin,
            name="full_rollout",
            is_enabled=True,
            rollout_pct=100,
            # pas de target_tenants → None → mode rollout
        )

        response = client.get(
            "/api/v1/features/check/full_rollout?tenant_id=1",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["reason"] == "rollout"

    def test_check_rollout_0pct(self, client: TestClient, auth_headers_admin):
        """Rollout 0% → enabled=false, reason=rollout."""
        _create_flag(
            client, auth_headers_admin,
            name="zero_rollout",
            is_enabled=True,
            rollout_pct=0,
        )

        response = client.get(
            "/api/v1/features/check/zero_rollout?tenant_id=1",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["reason"] == "rollout"

    def test_check_not_found(self, client: TestClient, auth_headers_admin):
        """Flag inexistant → enabled=false, reason=not_found."""
        response = client.get(
            "/api/v1/features/check/nonexistent_flag?tenant_id=1",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["reason"] == "not_found"

    def test_check_missing_tenant_id_422(self, client: TestClient, auth_headers_admin):
        """Paramètre tenant_id manquant → 422."""
        response = client.get(
            "/api/v1/features/check/some_flag",
            headers=auth_headers_admin,
        )
        assert response.status_code == 422
