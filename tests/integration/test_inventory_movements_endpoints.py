"""Tests d'integration pour les endpoints Inventory Movements (CRUD + workflow + items)."""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient


# -- Helpers ------------------------------------------------------------------


def _create_movement(client: TestClient, headers: dict, **overrides) -> dict:
    """Helper pour creer un mouvement via l'endpoint."""
    payload = {
        "movement_type": overrides.get("movement_type", "departure"),
        "scheduled_date": overrides.get(
            "scheduled_date",
            (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        ),
        "items": overrides.get("items", [{"quantity_expected": 5}]),
    }
    if "event_id" in overrides:
        payload["event_id"] = overrides["event_id"]
    if "delivery_method" in overrides:
        payload["delivery_method"] = overrides["delivery_method"]
    if "delivery_address" in overrides:
        payload["delivery_address"] = overrides["delivery_address"]
    if "delivery_notes" in overrides:
        payload["delivery_notes"] = overrides["delivery_notes"]
    return client.post("/api/v1/inventory-movements", json=payload, headers=headers)


def _transition_to_in_transit(client: TestClient, headers: dict, movement_id: int):
    """Helper pour passer un mouvement en in_transit."""
    return client.patch(
        f"/api/v1/inventory-movements/{movement_id}",
        json={"status": "in_transit"},
        headers=headers,
    )


# -- POST /inventory-movements -----------------------------------------------


class TestCreateMovement:
    """Tests POST /api/v1/inventory-movements."""

    def test_create_success(self, client: TestClient, auth_headers_admin):
        """Creation d'un mouvement retourne 201 avec items."""
        response = _create_movement(
            client, auth_headers_admin,
            movement_type="departure",
            delivery_method="delivery",
            delivery_address="12 rue de la Paix, Paris",
            delivery_notes="Fragile",
            items=[
                {"quantity_expected": 10},
                {"quantity_expected": 5, "condition": "good"},
            ],
        )

        assert response.status_code == 201
        data = response.json()
        assert data["movement_type"] == "departure"
        assert data["status"] == "scheduled"
        assert data["delivery_method"] == "delivery"
        assert data["delivery_address"] == "12 rue de la Paix, Paris"
        assert data["delivery_notes"] == "Fragile"
        assert len(data["items"]) == 2
        assert data["items"][0]["quantity_expected"] == 10
        assert data["items"][1]["quantity_expected"] == 5
        assert data["items"][1]["condition"] == "good"
        assert data["id"] > 0

    def test_create_return_type(self, client: TestClient, auth_headers_admin):
        """Creation d'un mouvement retour."""
        response = _create_movement(
            client, auth_headers_admin,
            movement_type="return",
        )
        assert response.status_code == 201
        assert response.json()["movement_type"] == "return"

    def test_create_minimal(self, client: TestClient, auth_headers_admin):
        """Creation avec uniquement les champs obligatoires."""
        response = _create_movement(client, auth_headers_admin)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "scheduled"
        assert data["delivery_method"] is None
        assert data["delivery_address"] is None
        assert len(data["items"]) == 1

    def test_create_empty_items_422(self, client: TestClient, auth_headers_admin):
        """Items vides retourne 422."""
        response = _create_movement(
            client, auth_headers_admin,
            items=[],
        )
        assert response.status_code == 422

    def test_create_invalid_type_422(self, client: TestClient, auth_headers_admin):
        """Type invalide retourne 422."""
        payload = {
            "movement_type": "invalid_type",
            "scheduled_date": datetime.now(timezone.utc).isoformat(),
            "items": [{"quantity_expected": 1}],
        }
        response = client.post(
            "/api/v1/inventory-movements",
            json=payload,
            headers=auth_headers_admin,
        )
        assert response.status_code == 422

    def test_create_invalid_quantity_422(self, client: TestClient, auth_headers_admin):
        """quantity_expected <= 0 retourne 422."""
        response = _create_movement(
            client, auth_headers_admin,
            items=[{"quantity_expected": 0}],
        )
        assert response.status_code == 422

    def test_create_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission inventory:write -> 403."""
        response = _create_movement(client, auth_headers_real)
        assert response.status_code == 403

    def test_create_unauthenticated_401(self, client: TestClient):
        """Sans auth -> 401."""
        response = client.post(
            "/api/v1/inventory-movements",
            json={
                "movement_type": "departure",
                "scheduled_date": datetime.now(timezone.utc).isoformat(),
                "items": [{"quantity_expected": 1}],
            },
        )
        assert response.status_code == 401


# -- GET /inventory-movements -------------------------------------------------


class TestListMovements:
    """Tests GET /api/v1/inventory-movements."""

    def test_list_empty(self, client: TestClient, auth_headers_admin):
        """Liste vide quand aucun mouvement n'existe."""
        response = client.get("/api/v1/inventory-movements", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_with_movements(self, client: TestClient, auth_headers_admin):
        """Liste retourne les mouvements crees."""
        _create_movement(client, auth_headers_admin, movement_type="departure")
        _create_movement(client, auth_headers_admin, movement_type="return")

        response = client.get("/api/v1/inventory-movements", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        types = {item["movement_type"] for item in data["items"]}
        assert types == {"departure", "return"}

    def test_list_has_items_count(self, client: TestClient, auth_headers_admin):
        """La liste inclut items_count pour chaque mouvement."""
        _create_movement(
            client, auth_headers_admin,
            items=[{"quantity_expected": 3}, {"quantity_expected": 7}],
        )

        response = client.get("/api/v1/inventory-movements", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["items_count"] == 2

    def test_list_pagination(self, client: TestClient, auth_headers_admin):
        """Pagination skip/limit fonctionne."""
        for _ in range(5):
            _create_movement(client, auth_headers_admin)

        response = client.get(
            "/api/v1/inventory-movements?skip=2&limit=2",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2

    def test_list_filter_by_type(self, client: TestClient, auth_headers_admin):
        """Filtre par movement_type."""
        _create_movement(client, auth_headers_admin, movement_type="departure")
        _create_movement(client, auth_headers_admin, movement_type="return")

        response = client.get(
            "/api/v1/inventory-movements?movement_type=departure",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["movement_type"] == "departure"

    def test_list_filter_by_status(self, client: TestClient, auth_headers_admin):
        """Filtre par status."""
        create_resp = _create_movement(client, auth_headers_admin)
        mid = create_resp.json()["id"]
        _transition_to_in_transit(client, auth_headers_admin, mid)

        _create_movement(client, auth_headers_admin)

        response = client.get(
            "/api/v1/inventory-movements?status=in_transit",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "in_transit"

    def test_list_staff_can_read(self, client: TestClient, auth_headers_real, auth_headers_admin):
        """Un staff peut lire les mouvements (inventory:read)."""
        _create_movement(client, auth_headers_admin)

        response = client.get("/api/v1/inventory-movements", headers=auth_headers_real)
        assert response.status_code == 200


# -- GET /inventory-movements/{id} -------------------------------------------


class TestGetMovement:
    """Tests GET /api/v1/inventory-movements/{id}."""

    def test_get_success(self, client: TestClient, auth_headers_admin):
        """Recuperation d'un mouvement par ID avec items."""
        create_resp = _create_movement(
            client, auth_headers_admin,
            items=[{"quantity_expected": 10}, {"quantity_expected": 20}],
        )
        movement_id = create_resp.json()["id"]

        response = client.get(
            f"/api/v1/inventory-movements/{movement_id}",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == movement_id
        assert len(data["items"]) == 2
        assert data["damage_fee"] == 0
        assert data["damage_fee_euros"] == 0.0

    def test_get_not_found_404(self, client: TestClient, auth_headers_admin):
        """ID inexistant retourne 404."""
        response = client.get(
            "/api/v1/inventory-movements/99999",
            headers=auth_headers_admin,
        )
        assert response.status_code == 404

    def test_get_cross_tenant_404(
        self, client: TestClient, auth_headers_admin, auth_headers_admin_tenant2,
    ):
        """Un admin d'un autre tenant ne peut pas voir le mouvement -> 404."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        response = client.get(
            f"/api/v1/inventory-movements/{movement_id}",
            headers=auth_headers_admin_tenant2,
        )
        assert response.status_code == 404


# -- PATCH /inventory-movements/{id} -----------------------------------------


class TestUpdateMovement:
    """Tests PATCH /api/v1/inventory-movements/{id}."""

    def test_update_delivery_fields(self, client: TestClient, auth_headers_admin):
        """Mise a jour des champs de livraison."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/inventory-movements/{movement_id}",
            json={
                "delivery_method": "shipping",
                "delivery_address": "42 avenue des Champs",
                "delivery_notes": "Appeler avant livraison",
            },
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["delivery_method"] == "shipping"
        assert data["delivery_address"] == "42 avenue des Champs"
        assert data["delivery_notes"] == "Appeler avant livraison"

    def test_update_status_scheduled_to_in_transit(self, client: TestClient, auth_headers_admin):
        """Transition scheduled -> in_transit valide."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        response = _transition_to_in_transit(client, auth_headers_admin, movement_id)
        assert response.status_code == 200
        assert response.json()["status"] == "in_transit"

    def test_update_status_scheduled_to_cancelled(self, client: TestClient, auth_headers_admin):
        """Transition scheduled -> cancelled valide."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/inventory-movements/{movement_id}",
            json={"status": "cancelled"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    def test_update_status_invalid_transition_400(self, client: TestClient, auth_headers_admin):
        """Transition scheduled -> completed invalide -> 400."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/inventory-movements/{movement_id}",
            json={"status": "completed"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 400

    def test_update_damage_fee(self, client: TestClient, auth_headers_admin):
        """Mise a jour des frais de dommages."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/inventory-movements/{movement_id}",
            json={"damage_fee": 2500},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["damage_fee"] == 2500
        assert data["damage_fee_euros"] == 25.0

    def test_update_not_found_404(self, client: TestClient, auth_headers_admin):
        """Update d'un mouvement inexistant -> 404."""
        response = client.patch(
            "/api/v1/inventory-movements/99999",
            json={"delivery_notes": "Ghost"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 404

    def test_update_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff ne peut pas modifier un mouvement -> 403."""
        response = client.patch(
            "/api/v1/inventory-movements/1",
            json={"delivery_notes": "Nope"},
            headers=auth_headers_real,
        )
        assert response.status_code == 403


# -- DELETE /inventory-movements/{id} ----------------------------------------


class TestDeleteMovement:
    """Tests DELETE /api/v1/inventory-movements/{id}."""

    def test_delete_success(self, client: TestClient, auth_headers_admin):
        """Suppression soft-delete d'un mouvement scheduled -> 204."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/v1/inventory-movements/{movement_id}",
            headers=auth_headers_admin,
        )
        assert response.status_code == 204

        # Verifier que GET retourne 404 (soft deleted)
        get_resp = client.get(
            f"/api/v1/inventory-movements/{movement_id}",
            headers=auth_headers_admin,
        )
        assert get_resp.status_code == 404

    def test_delete_completed_400(self, client: TestClient, auth_headers_admin):
        """Suppression d'un mouvement completed -> 400."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        # scheduled -> in_transit -> completed
        _transition_to_in_transit(client, auth_headers_admin, movement_id)
        client.patch(
            f"/api/v1/inventory-movements/{movement_id}/complete",
            headers=auth_headers_admin,
        )

        response = client.delete(
            f"/api/v1/inventory-movements/{movement_id}",
            headers=auth_headers_admin,
        )
        assert response.status_code == 400

    def test_delete_not_found_404(self, client: TestClient, auth_headers_admin):
        """Suppression d'un mouvement inexistant -> 404."""
        response = client.delete(
            "/api/v1/inventory-movements/99999",
            headers=auth_headers_admin,
        )
        assert response.status_code == 404

    def test_delete_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff ne peut pas supprimer -> 403."""
        response = client.delete(
            "/api/v1/inventory-movements/1",
            headers=auth_headers_real,
        )
        assert response.status_code == 403


# -- PATCH /inventory-movements/{id}/complete --------------------------------


class TestCompleteMovement:
    """Tests PATCH /api/v1/inventory-movements/{id}/complete."""

    def test_complete_from_in_transit(self, client: TestClient, auth_headers_admin):
        """Complete un mouvement in_transit -> completed avec actual_date."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        _transition_to_in_transit(client, auth_headers_admin, movement_id)

        response = client.patch(
            f"/api/v1/inventory-movements/{movement_id}/complete",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["actual_date"] is not None

    def test_complete_from_late(self, client: TestClient, auth_headers_admin):
        """Complete un mouvement late -> completed."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        # scheduled -> in_transit -> late -> completed
        _transition_to_in_transit(client, auth_headers_admin, movement_id)
        client.patch(
            f"/api/v1/inventory-movements/{movement_id}",
            json={"status": "late"},
            headers=auth_headers_admin,
        )

        response = client.patch(
            f"/api/v1/inventory-movements/{movement_id}/complete",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    def test_complete_from_scheduled_invalid(self, client: TestClient, auth_headers_admin):
        """Complete directement depuis scheduled -> 400 (transition invalide)."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/inventory-movements/{movement_id}/complete",
            headers=auth_headers_admin,
        )
        assert response.status_code == 400

    def test_complete_already_completed_idempotent(self, client: TestClient, auth_headers_admin):
        """Complete un mouvement deja completed -> idempotent (200)."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        _transition_to_in_transit(client, auth_headers_admin, movement_id)
        client.patch(
            f"/api/v1/inventory-movements/{movement_id}/complete",
            headers=auth_headers_admin,
        )

        response = client.patch(
            f"/api/v1/inventory-movements/{movement_id}/complete",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    def test_complete_not_found_404(self, client: TestClient, auth_headers_admin):
        """Complete un mouvement inexistant -> 404."""
        response = client.patch(
            "/api/v1/inventory-movements/99999/complete",
            headers=auth_headers_admin,
        )
        assert response.status_code == 404


# -- GET /inventory-movements/late -------------------------------------------


class TestLateMovements:
    """Tests GET /api/v1/inventory-movements/late."""

    def test_list_late_empty(self, client: TestClient, auth_headers_admin):
        """Liste vide quand aucun mouvement en retard."""
        response = client.get(
            "/api/v1/inventory-movements/late",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_list_late_returns_only_late(self, client: TestClient, auth_headers_admin):
        """Ne retourne que les mouvements avec statut late."""
        # Creer un mouvement scheduled (pas late)
        _create_movement(client, auth_headers_admin)

        # Creer un mouvement late
        create_resp = _create_movement(client, auth_headers_admin)
        mid = create_resp.json()["id"]
        _transition_to_in_transit(client, auth_headers_admin, mid)
        client.patch(
            f"/api/v1/inventory-movements/{mid}",
            json={"status": "late"},
            headers=auth_headers_admin,
        )

        response = client.get(
            "/api/v1/inventory-movements/late",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "late"


# -- GET /inventory-movements/pending-inspections ----------------------------


class TestPendingInspections:
    """Tests GET /api/v1/inventory-movements/pending-inspections."""

    def test_list_pending_empty(self, client: TestClient, auth_headers_admin):
        """Liste vide quand aucune inspection en attente."""
        response = client.get(
            "/api/v1/inventory-movements/pending-inspections",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_list_pending_returns_matching(self, client: TestClient, auth_headers_admin):
        """Retourne les mouvements avec inspection_status=pending."""
        # Mouvement sans inspection
        _create_movement(client, auth_headers_admin)

        # Mouvement avec inspection pending
        create_resp = _create_movement(client, auth_headers_admin)
        mid = create_resp.json()["id"]
        client.patch(
            f"/api/v1/inventory-movements/{mid}",
            json={"inspection_status": "pending"},
            headers=auth_headers_admin,
        )

        response = client.get(
            "/api/v1/inventory-movements/pending-inspections",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1


# -- GET /inventory-movements/statistics -------------------------------------


class TestMovementStatistics:
    """Tests GET /api/v1/inventory-movements/statistics."""

    def test_statistics_empty(self, client: TestClient, auth_headers_admin):
        """Statistiques vides sans mouvements."""
        response = client.get(
            "/api/v1/inventory-movements/statistics",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_movements"] == 0
        assert data["scheduled"] == 0
        assert data["total_damage_fees"] == 0
        assert data["total_damage_fees_euros"] == 0.0

    def test_statistics_with_data(self, client: TestClient, auth_headers_admin):
        """Statistiques avec des mouvements crees."""
        # 2 mouvements scheduled
        _create_movement(client, auth_headers_admin)
        _create_movement(client, auth_headers_admin)

        # 1 mouvement in_transit
        create_resp = _create_movement(client, auth_headers_admin)
        mid = create_resp.json()["id"]
        _transition_to_in_transit(client, auth_headers_admin, mid)

        response = client.get(
            "/api/v1/inventory-movements/statistics",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_movements"] == 3
        assert data["scheduled"] == 2
        assert data["in_transit"] == 1


# -- POST /inventory-movements/{id}/items -----------------------------------


class TestAddItem:
    """Tests POST /api/v1/inventory-movements/{id}/items."""

    def test_add_item_success(self, client: TestClient, auth_headers_admin):
        """Ajout d'un item a un mouvement scheduled -> 201."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/inventory-movements/{movement_id}/items",
            json={"quantity_expected": 15, "condition": "perfect"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["quantity_expected"] == 15
        assert data["condition"] == "perfect"
        assert data["movement_id"] == movement_id

    def test_add_item_to_completed_400(self, client: TestClient, auth_headers_admin):
        """Ajout d'un item a un mouvement completed -> 400."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        # scheduled -> in_transit -> completed
        _transition_to_in_transit(client, auth_headers_admin, movement_id)
        client.patch(
            f"/api/v1/inventory-movements/{movement_id}/complete",
            headers=auth_headers_admin,
        )

        response = client.post(
            f"/api/v1/inventory-movements/{movement_id}/items",
            json={"quantity_expected": 5},
            headers=auth_headers_admin,
        )
        assert response.status_code == 400

    def test_add_item_to_cancelled_400(self, client: TestClient, auth_headers_admin):
        """Ajout d'un item a un mouvement cancelled -> 400."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        client.patch(
            f"/api/v1/inventory-movements/{movement_id}",
            json={"status": "cancelled"},
            headers=auth_headers_admin,
        )

        response = client.post(
            f"/api/v1/inventory-movements/{movement_id}/items",
            json={"quantity_expected": 5},
            headers=auth_headers_admin,
        )
        assert response.status_code == 400

    def test_add_item_not_found_404(self, client: TestClient, auth_headers_admin):
        """Ajout d'un item a un mouvement inexistant -> 404."""
        response = client.post(
            "/api/v1/inventory-movements/99999/items",
            json={"quantity_expected": 5},
            headers=auth_headers_admin,
        )
        assert response.status_code == 404

    def test_add_item_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff ne peut pas ajouter d'items -> 403."""
        response = client.post(
            "/api/v1/inventory-movements/1/items",
            json={"quantity_expected": 5},
            headers=auth_headers_real,
        )
        assert response.status_code == 403


# -- PATCH /inventory-movements/items/{id} -----------------------------------


class TestUpdateItem:
    """Tests PATCH /api/v1/inventory-movements/items/{id}."""

    def test_update_item_success(self, client: TestClient, auth_headers_admin):
        """Mise a jour quantity_actual et condition d'un item."""
        create_resp = _create_movement(
            client, auth_headers_admin,
            items=[{"quantity_expected": 10}],
        )
        item_id = create_resp.json()["items"][0]["id"]

        response = client.patch(
            f"/api/v1/inventory-movements/items/{item_id}",
            json={"quantity_actual": 8, "condition": "damaged", "condition_notes": "Casse"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["quantity_actual"] == 8
        assert data["condition"] == "damaged"
        assert data["condition_notes"] == "Casse"

    def test_update_item_not_found_404(self, client: TestClient, auth_headers_admin):
        """Update d'un item inexistant -> 404."""
        response = client.patch(
            "/api/v1/inventory-movements/items/99999",
            json={"quantity_actual": 5},
            headers=auth_headers_admin,
        )
        assert response.status_code == 404

    def test_update_item_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff ne peut pas modifier un item -> 403."""
        response = client.patch(
            "/api/v1/inventory-movements/items/1",
            json={"quantity_actual": 5},
            headers=auth_headers_real,
        )
        assert response.status_code == 403


# -- DELETE /inventory-movements/items/{id} ----------------------------------


class TestRemoveItem:
    """Tests DELETE /api/v1/inventory-movements/items/{id}."""

    def test_remove_item_success(self, client: TestClient, auth_headers_admin):
        """Suppression d'un item d'un mouvement scheduled -> 204."""
        create_resp = _create_movement(
            client, auth_headers_admin,
            items=[{"quantity_expected": 10}, {"quantity_expected": 5}],
        )
        item_id = create_resp.json()["items"][0]["id"]

        response = client.delete(
            f"/api/v1/inventory-movements/items/{item_id}",
            headers=auth_headers_admin,
        )
        assert response.status_code == 204

    def test_remove_item_from_completed_400(self, client: TestClient, auth_headers_admin):
        """Suppression d'un item d'un mouvement completed -> 400."""
        create_resp = _create_movement(
            client, auth_headers_admin,
            items=[{"quantity_expected": 10}],
        )
        movement_id = create_resp.json()["id"]
        item_id = create_resp.json()["items"][0]["id"]

        # scheduled -> in_transit -> completed
        _transition_to_in_transit(client, auth_headers_admin, movement_id)
        client.patch(
            f"/api/v1/inventory-movements/{movement_id}/complete",
            headers=auth_headers_admin,
        )

        response = client.delete(
            f"/api/v1/inventory-movements/items/{item_id}",
            headers=auth_headers_admin,
        )
        assert response.status_code == 400

    def test_remove_item_not_found_404(self, client: TestClient, auth_headers_admin):
        """Suppression d'un item inexistant -> 404."""
        response = client.delete(
            "/api/v1/inventory-movements/items/99999",
            headers=auth_headers_admin,
        )
        assert response.status_code == 404

    def test_remove_item_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff ne peut pas supprimer un item -> 403."""
        response = client.delete(
            "/api/v1/inventory-movements/items/1",
            headers=auth_headers_real,
        )
        assert response.status_code == 403


# -- Cross-tenant isolation --------------------------------------------------


class TestCrossTenantIsolation:
    """Tests d'isolation multi-tenant pour les mouvements."""

    def test_list_tenant_isolation(
        self, client: TestClient, auth_headers_admin, auth_headers_admin_tenant2,
    ):
        """Le tenant 2 ne voit pas les mouvements du tenant 1."""
        _create_movement(client, auth_headers_admin)

        response = client.get(
            "/api/v1/inventory-movements",
            headers=auth_headers_admin_tenant2,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_update_cross_tenant_404(
        self, client: TestClient, auth_headers_admin, auth_headers_admin_tenant2,
    ):
        """Un admin tenant 2 ne peut pas modifier un mouvement du tenant 1."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/inventory-movements/{movement_id}",
            json={"delivery_notes": "Hacked"},
            headers=auth_headers_admin_tenant2,
        )
        assert response.status_code == 404

    def test_delete_cross_tenant_404(
        self, client: TestClient, auth_headers_admin, auth_headers_admin_tenant2,
    ):
        """Un admin tenant 2 ne peut pas supprimer un mouvement du tenant 1."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/v1/inventory-movements/{movement_id}",
            headers=auth_headers_admin_tenant2,
        )
        assert response.status_code == 404

    def test_complete_cross_tenant_404(
        self, client: TestClient, auth_headers_admin, auth_headers_admin_tenant2,
    ):
        """Un admin tenant 2 ne peut pas completer un mouvement du tenant 1."""
        create_resp = _create_movement(client, auth_headers_admin)
        movement_id = create_resp.json()["id"]
        _transition_to_in_transit(client, auth_headers_admin, movement_id)

        response = client.patch(
            f"/api/v1/inventory-movements/{movement_id}/complete",
            headers=auth_headers_admin_tenant2,
        )
        assert response.status_code == 404
