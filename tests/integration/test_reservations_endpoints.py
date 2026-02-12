"""Tests d'intégration pour les endpoints réservations."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.customer import Customer
from app.models.product import Product
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
        category=ProductCategory.NAPPE,
        price_per_day=2000,  # 20€/jour
        deposit_amount=5000,  # 50€ caution
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.NEUF,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


def test_list_reservations_success(client: TestClient, auth_headers_real):
    """Test liste réservations avec pagination."""
    response = client.get("/api/v1/reservations?skip=0&limit=20", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_create_reservation_success(client: TestClient, test_customer_res, test_product_res, auth_headers_real):
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


def test_create_reservation_customer_not_found(client: TestClient, test_product_res, auth_headers_real):
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
                "quantity": 1
            }
        ]
    }

    response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)

    assert response.status_code == 404
    assert "Product" in response.json()["detail"]


def test_get_reservation_success(client: TestClient, test_db, test_customer_res, test_product_res, auth_headers_real):
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
                "quantity": 3
            }
        ]
    }
    create_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
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


def test_update_reservation_draft_only(client: TestClient, test_db, test_customer_res, test_product_res, auth_headers_real):
    """Test mettre à jour réservation (status=draft uniquement)."""
    # Créer réservation
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": test_product_res.id, "quantity": 1}]
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


def test_confirm_reservation_success(client: TestClient, test_db, test_customer_res, test_product_res, auth_headers_real):
    """Test confirmer réservation → réserve stock."""
    # Créer réservation
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": test_product_res.id, "quantity": 5}]
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
    assert data["status"] == "confirmed"

    # Vérifier que stock a été réservé
    test_db.refresh(test_product_res)
    assert test_product_res.available_quantity == initial_available - 5


def test_confirm_reservation_insufficient_stock(client: TestClient, test_db, test_customer_res, test_product_res, auth_headers_real):
    """Test confirmer réservation avec stock insuffisant → 400."""
    # Réduire stock disponible
    test_product_res.available_quantity = 2
    test_db.commit()

    # Créer réservation avec quantité > stock
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": test_product_res.id, "quantity": 5}]  # Quantité > stock
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
    test_product_res.available_quantity = 10
    test_db.commit()


def test_cancel_reservation_success(client: TestClient, test_db, test_customer_res, test_product_res, auth_headers_real):
    """Test annuler réservation confirmée → libère stock."""
    # Créer et confirmer réservation
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": test_product_res.id, "quantity": 3}]
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


def test_filter_reservations_by_status(client: TestClient, test_db, test_customer_res, test_product_res, auth_headers_real):
    """Test filtrer réservations par statut."""
    # Créer réservation et confirmer
    reservation_data = {
        "customer_id": test_customer_res.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": test_product_res.id, "quantity": 1}]
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
