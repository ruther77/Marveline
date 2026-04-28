"""Tests d'intégration pour les endpoints réservations."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.customer import Customer
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.reservation import Reservation
from app.constants import CustomerType, ProductCategory, ProductCondition


@pytest.fixture
def test_customer_res(test_db):
    """Client de test pour réservations."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Sophie",
        last_name="Bernard",
        email="sophie.bernard@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture
def test_product_res(test_db):
    """Produit de test pour réservations."""
    product = Product(
        tenant_id=1,
        name="Table ronde 150cm",
        sku="TABLE-RES-001",
        category=ProductCategory.NAPPES,
        price_per_day_cents=2000,  # 20€/jour
        deposit_amount_cents=5000,  # 50€ caution
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.NEUF,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def test_variant_res(test_db, test_product_res):
    """Variante Standard du produit de test."""
    variant = ProductVariant(
        tenant_id=1,
        product_id=test_product_res.id,
        label="Standard",
        sku=f"STD-{test_product_res.id}",
        price_per_day_cents=test_product_res.price_per_day_cents,
        deposit_amount_cents=test_product_res.deposit_amount_cents,
        stock_quantity=test_product_res.stock_quantity,
        available_quantity=test_product_res.available_quantity,
        is_active=True,
    )
    test_db.add(variant)
    test_db.commit()
    test_db.refresh(variant)
    return variant


def test_list_reservations_success(client: TestClient, auth_headers_real):
    """Test liste réservations avec pagination."""
    response = client.get("/api/v1/reservations?skip=0&limit=20", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_create_reservation_success(client: TestClient, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test créer réservation avec lignes → 201."""
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Château de Versailles",
        "lines": [
            {
                "product_id": test_product_res.id,
                "variant_id": test_variant_res.id,
                "quantity": 5
            }
        ]
    }

    response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "draft"
    assert "reference" in data
    assert data["reference"].startswith("RES-")
    assert data["customer"]["id"] == test_customer_res.id
    assert len(data["lines"]) == 1
    assert data["lines"][0]["quantity"] == 5
    assert data["rental_days"] == 3  # Computed field


def test_create_reservation_customer_not_found(client: TestClient, test_product_res, test_variant_res, auth_headers_real):
    """Test créer réservation avec customer inexistant → 404."""
    reservation_data = {
        "customer_id": 999999,  # Inexistant
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [
            {
                "product_id": test_product_res.id,
                "variant_id": test_variant_res.id,
                "quantity": 1
            }
        ]
    }

    response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)

    assert response.status_code == 404
    assert "Customer not found" in response.json()["detail"]


def test_create_reservation_product_not_found(client: TestClient, test_customer_res, auth_headers_real):
    """Test créer réservation avec produit inexistant → 404."""
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [
            {
                "product_id": 999999,  # Inexistant
                "variant_id": 999999,
                "quantity": 1
            }
        ]
    }

    response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)

    assert response.status_code == 404
    assert "Product" in response.json()["detail"]


def test_get_reservation_success(client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test récupérer détails réservation avec relations."""
    # Créer réservation via endpoint
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test Event",
        "lines": [
            {
                "product_id": test_product_res.id,
                "variant_id": test_variant_res.id,
                "quantity": 3
            }
        ]
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    assert create_response.status_code == 201
    reservation_id = create_response.json()["id"]

    # Récupérer réservation
    response = client.get(f"/api/v1/reservations/{reservation_id}", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == reservation_id
    assert "customer" in data
    assert "lines" in data
    assert len(data["lines"]) == 1
    assert data["lines"][0]["product"]["name"] == "Table ronde 150cm"


def test_update_reservation_draft_only(client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test mettre à jour réservation (status=draft uniquement)."""
    # Créer réservation
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 1}]
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    reservation_id = create_response.json()["id"]

    # Mettre à jour
    update_data = {
        "event_location": "Nouvel emplacement"
    }
    response = client.patch(
        f"/api/v1/reservations/{reservation_id}",
        json=update_data,
        headers=auth_headers_real
    )

    assert response.status_code == 200
    data = response.json()
    assert data["event_location"] == "Nouvel emplacement"


def test_confirm_reservation_success(client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test confirmer réservation → réserve stock."""
    # Créer réservation
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 5}]
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    reservation_id = create_response.json()["id"]

    # Stock avant confirmation
    initial_available = test_product_res.available_quantity

    # Confirmer réservation
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/confirm",
        headers=auth_headers_real
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pre_check"

    # Vérifier que stock a été réservé
    test_db.refresh(test_product_res)
    assert test_product_res.available_quantity == initial_available - 5


def test_confirm_reservation_insufficient_stock(client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test confirmer réservation avec stock insuffisant → 400."""
    # Réduire stock disponible (variante = source de vérité)
    test_variant_res.available_quantity = 2
    test_product_res.available_quantity = 2
    test_db.commit()

    # Créer réservation avec quantité > stock
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 5}]  # Quantité > stock
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    reservation_id = create_response.json()["id"]

    # Tenter de confirmer
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/confirm",
        headers=auth_headers_real
    )

    assert response.status_code == 400
    assert "stock" in response.json()["detail"].lower()

    # Restaurer stock
    test_variant_res.available_quantity = 10
    test_product_res.available_quantity = 10
    test_db.commit()


def test_cancel_reservation_success(client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test annuler réservation confirmée → libère stock."""
    # Créer et confirmer réservation
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 3}]
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    reservation_id = create_response.json()["id"]

    # Confirmer
    client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=auth_headers_real)

    # Stock après confirmation
    test_db.refresh(test_product_res)
    stock_after_confirm = test_product_res.available_quantity

    # Annuler réservation
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/cancel",
        headers=auth_headers_real
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"

    # Vérifier que stock a été libéré
    test_db.refresh(test_product_res)
    assert test_product_res.available_quantity == stock_after_confirm + 3


def test_cancel_reservation_completed_forbidden(client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test annulation interdite sur réservation terminale `completed`."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    _force_status(test_db, reservation_id, "completed")

    response = client.post(
        f"/api/v1/reservations/{reservation_id}/cancel",
        headers=auth_headers_real,
    )

    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "cannot cancel reservation" in detail
    assert "completed" in detail


def test_cancel_reservation_returned_dispute_forbidden(client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test annulation interdite sur réservation terminale `returned_dispute`."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    _force_status(test_db, reservation_id, "returned_dispute")

    response = client.post(
        f"/api/v1/reservations/{reservation_id}/cancel",
        headers=auth_headers_real,
    )

    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "cannot cancel reservation" in detail
    assert "returned_dispute" in detail


def test_deliver_reservation_success(client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test marquer une réservation confirmée comme livrée."""
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 2}]
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    reservation_id = create_response.json()["id"]

    # Confirmer d'abord
    client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=auth_headers_real)

    # Marquer livrée
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/deliver",
        headers=auth_headers_real
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "delivered"

    # Stock reste réservé (pas libéré)
    test_db.refresh(test_product_res)
    # available_quantity ne change pas lors de la livraison


def test_deliver_reservation_not_confirmed(client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test marquer livrée une réservation non confirmée → 400."""
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 1}]
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    reservation_id = create_response.json()["id"]

    # Tenter deliver sans confirm (status = draft)
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/deliver",
        headers=auth_headers_real
    )

    assert response.status_code == 400
    assert "confirmed" in response.json()["detail"].lower()


def test_filter_reservations_by_status(client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test filtrer réservations par statut."""
    # Créer réservation et confirmer
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 1}]
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    reservation_id = create_response.json()["id"]
    client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=auth_headers_real)

    # Filtrer par status=confirmed
    response = client.get("/api/v1/reservations?status_filter=confirmed", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["status"] == "confirmed"


@pytest.fixture
def test_product_res2(test_db):
    """2ème produit de test pour lignes réservation."""
    product = Product(
        tenant_id=1,
        name="Chaise pliante",
        sku="CHAISE-RES-002",
        category=ProductCategory.NAPPES,
        price_per_day_cents=500,
        deposit_amount_cents=1000,
        stock_quantity=20,
        available_quantity=20,
        condition=ProductCondition.NEUF,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def test_variant_res2(test_db, test_product_res2):
    """Variante Standard du 2ème produit de test."""
    variant = ProductVariant(
        tenant_id=1,
        product_id=test_product_res2.id,
        label="Standard",
        sku=f"STD-{test_product_res2.id}",
        price_per_day_cents=test_product_res2.price_per_day_cents,
        deposit_amount_cents=test_product_res2.deposit_amount_cents,
        stock_quantity=test_product_res2.stock_quantity,
        available_quantity=test_product_res2.available_quantity,
        is_active=True,
    )
    test_db.add(variant)
    test_db.commit()
    test_db.refresh(variant)
    return variant


def test_add_reservation_line_success(client, test_db, test_customer_res, test_product_res, test_variant_res, test_product_res2, test_variant_res2, auth_headers_real):
    """Test ajout d'une ligne à une réservation draft."""
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test lignes",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 1}]
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    assert create_response.status_code == 201
    reservation_id = create_response.json()["id"]

    # Ajouter une 2ème ligne avec un produit différent
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/lines",
        json={"product_id": test_product_res2.id, "variant_id": test_variant_res2.id, "quantity": 2},
        headers=auth_headers_real
    )
    assert response.status_code == 201
    data = response.json()
    assert data["product_id"] == test_product_res2.id
    assert data["quantity"] == 2

    # Vérifier 2 lignes maintenant
    detail = client.get(f"/api/v1/reservations/{reservation_id}", headers=auth_headers_real)
    assert len(detail.json()["lines"]) == 2


def test_list_reservation_lines_success(client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test lecture des lignes via GET /reservations/{id}/lines."""
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test lecture lignes",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 2}],
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    assert create_response.status_code == 201
    reservation_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/reservations/{reservation_id}/lines",
        headers=auth_headers_real,
    )
    assert response.status_code == 200
    lines = response.json()
    assert len(lines) == 1
    assert lines[0]["reservation_id"] == reservation_id
    assert lines[0]["quantity"] == 2


def test_list_reservation_lines_not_found(client, auth_headers_real):
    """GET /reservations/{id}/lines sur réservation inconnue -> 404."""
    response = client.get(
        "/api/v1/reservations/99999/lines",
        headers=auth_headers_real,
    )
    assert response.status_code == 404


def test_remove_reservation_line_success(client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test suppression d'une ligne d'une réservation draft."""
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test suppression ligne",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 1}]
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    assert create_response.status_code == 201
    reservation_id = create_response.json()["id"]
    line_id = create_response.json()["lines"][0]["id"]

    # Supprimer la ligne
    response = client.delete(
        f"/api/v1/reservations/{reservation_id}/lines/{line_id}",
        headers=auth_headers_real
    )
    assert response.status_code == 204

    # Vérifier liste vide
    detail = client.get(f"/api/v1/reservations/{reservation_id}", headers=auth_headers_real)
    assert detail.json()["lines"] == []


def test_add_line_not_draft(client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test ajout ligne sur réservation non-draft → 400."""
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 1}]
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    reservation_id = create_response.json()["id"]
    client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=auth_headers_real)

    response = client.post(
        f"/api/v1/reservations/{reservation_id}/lines",
        json={"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 1},
        headers=auth_headers_real
    )
    assert response.status_code == 400


# ── Tests nouveaux endpoints workflow clôture ─────────────────────────────────


def _create_reservation(client, customer_id, product_id, headers, variant_id=None):
    """Helper : crée une réservation draft et retourne son ID."""
    line = {"product_id": product_id, "quantity": 1}
    if variant_id:
        line["variant_id"] = variant_id
    data = {
        "customer_id": customer_id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Salle des fêtes",
        "lines": [line],
    }
    resp = client.post("/api/v1/reservations", json=data, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _force_status(test_db, reservation_id, new_status):
    """Helper : force directement le statut en DB (transitions non couvertes par l'API)."""
    reservation = test_db.get(Reservation, reservation_id)
    reservation.status = new_status
    test_db.commit()
    test_db.refresh(reservation)


def test_complete_reservation_success(client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test clôture définitive : RETURNED → COMPLETED."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    # Passer en returned via mutation directe (pas d'endpoint /return dédié)
    _force_status(test_db, reservation_id, "returned")

    response = client.post(
        f"/api/v1/reservations/{reservation_id}/complete",
        headers=auth_headers_real,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["id"] == reservation_id


def test_complete_reservation_wrong_status(client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test clôture sur réservation non-returned → 400."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    # draft ne peut pas être clôturé
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/complete",
        headers=auth_headers_real,
    )

    assert response.status_code == 400
    assert "returned" in response.json()["detail"].lower()


def test_complete_reservation_not_found(client, test_db, auth_headers_real):
    """Test clôture sur réservation inexistante → 404."""
    response = client.post("/api/v1/reservations/99999/complete", headers=auth_headers_real)
    assert response.status_code == 404


def test_close_dispute_success(client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test résolution litige : RETURNED_DISPUTE → RETURNED."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    _force_status(test_db, reservation_id, "returned_dispute")

    response = client.post(
        f"/api/v1/reservations/{reservation_id}/close-dispute",
        json={"resolution_notes": "Litige résolu : dommages mineurs acceptés par les deux parties."},
        headers=auth_headers_real,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "returned"
    assert data["id"] == reservation_id


def test_close_dispute_wrong_status(client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test résolution litige sur statut incorrect → 400."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    # La réservation est en draft, pas returned_dispute
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/close-dispute",
        json={"resolution_notes": "Notes"},
        headers=auth_headers_real,
    )

    assert response.status_code == 400
    assert "returned_dispute" in response.json()["detail"].lower()


def test_close_dispute_missing_notes(client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test résolution litige sans resolution_notes → 422."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    _force_status(test_db, reservation_id, "returned_dispute")

    response = client.post(
        f"/api/v1/reservations/{reservation_id}/close-dispute",
        json={},
        headers=auth_headers_real,
    )

    assert response.status_code == 422


def test_remind_deposit_success(client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test rappel acompte sur réservation confirmée → 204."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    # Confirmer via API (transition draft → confirmed)
    confirm_resp = client.post(
        f"/api/v1/reservations/{reservation_id}/confirm",
        headers=auth_headers_real,
    )
    assert confirm_resp.status_code == 200

    response = client.post(
        f"/api/v1/reservations/{reservation_id}/remind-deposit",
        headers=auth_headers_real,
    )

    # 204 No Content — l'envoi email est best-effort async (Celery)
    assert response.status_code == 204


def test_remind_deposit_not_confirmed(client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Test rappel acompte sur réservation draft → 400."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/remind-deposit",
        headers=auth_headers_real,
    )

    assert response.status_code == 400


def test_remind_deposit_not_found(client, test_db, auth_headers_real):
    """Test rappel acompte sur réservation inexistante → 404."""
    response = client.post("/api/v1/reservations/99999/remind-deposit", headers=auth_headers_real)
    assert response.status_code == 404


def test_get_deposit_success(client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """GET /reservations/{id}/deposits/{deposit_id} retourne une caution existante."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    create_dep = client.post(
        f"/api/v1/reservations/{reservation_id}/deposits",
        json={"amount_cents": 5000, "notes": "Caution CB"},
        headers=auth_headers_real,
    )
    assert create_dep.status_code == 201
    deposit_id = create_dep.json()["id"]

    response = client.get(
        f"/api/v1/reservations/{reservation_id}/deposits/{deposit_id}",
        headers=auth_headers_real,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == deposit_id
    assert data["reservation_id"] == reservation_id
    assert data["amount_cents"] == 5000


def test_get_deposit_wrong_reservation_404(client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real):
    """Une caution d'une autre réservation n'est pas accessible (404)."""
    reservation_a = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    reservation_b = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    create_dep = client.post(
        f"/api/v1/reservations/{reservation_a}/deposits",
        json={"amount_cents": 4000},
        headers=auth_headers_real,
    )
    assert create_dep.status_code == 201
    deposit_id = create_dep.json()["id"]

    response = client.get(
        f"/api/v1/reservations/{reservation_b}/deposits/{deposit_id}",
        headers=auth_headers_real,
    )
    assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Lot D — Variant-first : propagation variant_id dans confirm / add_line
# ═══════════════════════════════════════════════════════════════════════════════


def test_confirm_reserves_variant_stock(
    client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real
):
    """Confirmer une réservation décrémente ProductVariant.available_quantity."""
    initial_variant_qty = test_variant_res.available_quantity

    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=12)),
        "delivery_date": str(date.today() + timedelta(days=11)),
        "return_date": str(date.today() + timedelta(days=14)),
        "event_location": "Lot D variant stock",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 3}],
    }
    create_resp = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    assert create_resp.status_code == 201
    reservation_id = create_resp.json()["id"]

    confirm_resp = client.post(
        f"/api/v1/reservations/{reservation_id}/confirm", headers=auth_headers_real
    )
    assert confirm_resp.status_code == 200

    test_db.refresh(test_variant_res)
    assert test_variant_res.available_quantity == initial_variant_qty - 3


def test_cancel_releases_variant_stock(
    client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real
):
    """Annuler une réservation confirmée restaure ProductVariant.available_quantity."""
    initial_variant_qty = test_variant_res.available_quantity

    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=12)),
        "delivery_date": str(date.today() + timedelta(days=11)),
        "return_date": str(date.today() + timedelta(days=14)),
        "event_location": "Lot D variant cancel",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 2}],
    }
    create_resp = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    assert create_resp.status_code == 201
    reservation_id = create_resp.json()["id"]

    client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=auth_headers_real)
    test_db.refresh(test_variant_res)
    after_confirm_qty = test_variant_res.available_quantity

    cancel_resp = client.post(
        f"/api/v1/reservations/{reservation_id}/cancel", headers=auth_headers_real
    )
    assert cancel_resp.status_code == 200

    test_db.refresh(test_variant_res)
    assert test_variant_res.available_quantity == after_confirm_qty + 2


def test_add_line_response_includes_variant(
    client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res,
    test_product_res2, test_variant_res2, auth_headers_real
):
    """add_line avec variant_id retourne le champ variant dans la réponse (non-MissingGreenlet)."""
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=12)),
        "delivery_date": str(date.today() + timedelta(days=11)),
        "return_date": str(date.today() + timedelta(days=14)),
        "event_location": "Lot D add_line variant",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 1}],
    }
    create_resp = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    assert create_resp.status_code == 201
    reservation_id = create_resp.json()["id"]

    add_resp = client.post(
        f"/api/v1/reservations/{reservation_id}/lines",
        json={"product_id": test_product_res2.id, "variant_id": test_variant_res2.id, "quantity": 2},
        headers=auth_headers_real,
    )
    assert add_resp.status_code == 201
    data = add_resp.json()
    assert data["product_id"] == test_product_res2.id
    assert data["variant_id"] == test_variant_res2.id
    # variant nested doit être présent (fix MissingGreenlet — db.refresh include "variant")
    assert data.get("variant") is not None
    assert data["variant"]["id"] == test_variant_res2.id


def test_departure_movement_has_variant_id(
    client: TestClient, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real
):
    """Après confirmation, le mouvement DEPARTURE auto-créé a variant_id propagé."""
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=12)),
        "delivery_date": str(date.today() + timedelta(days=11)),
        "return_date": str(date.today() + timedelta(days=14)),
        "event_location": "Lot D departure variant_id",
        "lines": [{"product_id": test_product_res.id, "variant_id": test_variant_res.id, "quantity": 2}],
    }
    create_resp = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    assert create_resp.status_code == 201
    reservation_id = create_resp.json()["id"]

    confirm_resp = client.post(
        f"/api/v1/reservations/{reservation_id}/confirm", headers=auth_headers_real
    )
    assert confirm_resp.status_code == 200

    # Récupérer les mouvements liés (liste MovementListItem — sans items)
    movements_resp = client.get(
        f"/api/v1/inventory-movements?reservation_id={reservation_id}",
        headers=auth_headers_real,
    )
    assert movements_resp.status_code == 200
    movements = movements_resp.json()["items"]
    departures = [m for m in movements if m["movement_type"] == "departure"]
    assert len(departures) == 1, "Un mouvement DEPARTURE doit être auto-créé"

    # GET /{id} retourne MovementResponse (avec items complets)
    departure_id = departures[0]["id"]
    detail_resp = client.get(
        f"/api/v1/inventory-movements/{departure_id}",
        headers=auth_headers_real,
    )
    assert detail_resp.status_code == 200
    departure_detail = detail_resp.json()

    # Vérifier que les items du mouvement portent variant_id
    assert len(departure_detail["items"]) >= 1
    for item in departure_detail["items"]:
        assert item.get("variant_id") == test_variant_res.id


# ── Tests archivage (Lot 4) ───────────────────────────────────────────────────

def test_archive_completed_reservation(
    client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real
):
    """Archive une réservation completed → is_archived=True, status inchangé."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    _force_status(test_db, reservation_id, "completed")

    response = client.post(
        f"/api/v1/reservations/{reservation_id}/archive",
        headers=auth_headers_real,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == reservation_id
    assert data["status"] == "completed"
    assert data["is_archived"] is True


def test_archive_cancelled_reservation(
    client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real
):
    """Archive une réservation cancelled → is_archived=True."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    _force_status(test_db, reservation_id, "cancelled")

    response = client.post(
        f"/api/v1/reservations/{reservation_id}/archive",
        headers=auth_headers_real,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"
    assert data["is_archived"] is True


def test_archive_draft_forbidden(
    client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real
):
    """Archive une réservation draft → 409 (statut non archivable)."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    # draft ne peut pas être archivé
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/archive",
        headers=auth_headers_real,
    )

    assert response.status_code == 409
    assert "draft" in response.json()["detail"].lower() or "archive" in response.json()["detail"].lower()


def test_archive_already_archived(
    client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real
):
    """Tenter d'archiver une réservation déjà archivée → 409."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    _force_status(test_db, reservation_id, "completed")

    # Première archive → OK
    resp1 = client.post(
        f"/api/v1/reservations/{reservation_id}/archive",
        headers=auth_headers_real,
    )
    assert resp1.status_code == 200

    # Deuxième archive → 409
    resp2 = client.post(
        f"/api/v1/reservations/{reservation_id}/archive",
        headers=auth_headers_real,
    )
    assert resp2.status_code == 409
    assert "already archived" in resp2.json()["detail"].lower()


def test_archive_not_found(client, auth_headers_real):
    """Archive d'une réservation inexistante → 404."""
    response = client.post("/api/v1/reservations/99999/archive", headers=auth_headers_real)
    assert response.status_code == 404


def test_archive_hidden_from_default_list(
    client, test_db, test_customer_res, test_product_res, test_variant_res, auth_headers_real
):
    """Une réservation archivée n'apparaît plus dans la liste par défaut."""
    reservation_id = _create_reservation(
        client, test_customer_res.id, test_product_res.id, auth_headers_real,
        variant_id=test_variant_res.id,
    )
    _force_status(test_db, reservation_id, "completed")

    # Avant archivage : la réservation est dans la liste
    list_before = client.get("/api/v1/reservations", headers=auth_headers_real)
    assert list_before.status_code == 200
    ids_before = [r["id"] for r in list_before.json()["items"]]
    assert reservation_id in ids_before

    # Archiver
    archive_resp = client.post(
        f"/api/v1/reservations/{reservation_id}/archive",
        headers=auth_headers_real,
    )
    assert archive_resp.status_code == 200

    # Après archivage : la réservation disparaît de la liste par défaut
    list_after = client.get("/api/v1/reservations", headers=auth_headers_real)
    assert list_after.status_code == 200
    ids_after = [r["id"] for r in list_after.json()["items"]]
    assert reservation_id not in ids_after
