"""Tests d'intégration pour les endpoints factures."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.customer import Customer
from app.models.product import Product
from app.models.reservation import Reservation, ReservationLine
from app.constants import CustomerType, ProductCategory, ProductCondition, ReservationStatus


@pytest.fixture
def test_customer_inv(test_db):
    """Client de test pour factures."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Alice",
        last_name="Dubois",
        email="alice.dubois@example.com",
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
def test_product_inv(test_db):
    """Produit de test pour factures."""
    product = Product(
        tenant_id=1,
        name="Chaise Napoléon",
        sku="CHAISE-INV-001",
        category=ProductCategory.MOBILIER,
        price_per_day=500,  # 5€/jour
        deposit_amount=1000,  # 10€ caution
        stock_quantity=50,
        available_quantity=50,
        condition=ProductCondition.NEUF,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def test_reservation_inv(test_db, test_customer_inv, test_product_inv):
    """Réservation de test pour factures."""
    reservation = Reservation(
        tenant_id=1,
        customer_id=test_customer_inv.id,
        reference="RES-TEST-001",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test Event",
        status=ReservationStatus.CONFIRMED,
        total_amount=3000,  # 30€ (20 chaises × 5€ × 3 jours)
        deposit_amount=20000,  # 200€ (20 chaises × 10€)
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()
    test_db.refresh(reservation)

    # Ajouter ligne
    line = ReservationLine(
        tenant_id=1,
        reservation_id=reservation.id,
        product_id=test_product_inv.id,
        quantity=20,
        unit_price=500,
        subtotal=3000  # 20 × 5€ × 3 jours
    )
    test_db.add(line)
    test_db.commit()

    return reservation


def test_list_invoices_success(client: TestClient, auth_headers_real):
    """Test liste factures avec pagination."""
    response = client.get("/api/v1/invoices?skip=0&limit=20", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_create_invoice_from_reservation_success(client: TestClient, test_reservation_inv, auth_headers_real):
    """Test créer facture depuis réservation → 201."""
    invoice_data = {
        "reservation_id": test_reservation_inv.id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }

    response = client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "draft"
    assert "invoice_number" in data
    assert data["invoice_number"].startswith("INV-")
    assert data["total_amount_cents"] == 3000  # Copié depuis réservation
    assert data["paid_amount_cents"] == 0
    assert data["is_paid"] is False
    assert data["remaining_amount_cents"] == 3000


def test_create_invoice_reservation_not_found(client: TestClient, auth_headers_real):
    """Test créer facture avec réservation inexistante → 404."""
    invoice_data = {
        "reservation_id": 999999,  # Inexistant
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }

    response = client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)

    assert response.status_code == 404
    assert "Reservation not found" in response.json()["detail"]


def test_create_invoice_duplicate_for_reservation(client: TestClient, test_reservation_inv, auth_headers_real):
    """Test créer facture pour réservation ayant déjà une facture → 400."""
    # Créer première facture
    invoice_data = {
        "reservation_id": test_reservation_inv.id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }
    client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)

    # Tenter de créer seconde facture pour même réservation
    response = client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_get_invoice_success(client: TestClient, test_reservation_inv, auth_headers_real):
    """Test récupérer détails facture."""
    # Créer facture
    invoice_data = {
        "reservation_id": test_reservation_inv.id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }
    create_response = client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)
    invoice_id = create_response.json()["id"]

    # Récupérer facture
    response = client.get(f"/api/v1/invoices/{invoice_id}", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == invoice_id
    assert "reservation" in data
    assert data["reservation"]["id"] == test_reservation_inv.id


def test_update_invoice_success(client: TestClient, test_reservation_inv, auth_headers_real):
    """Test mettre à jour facture (PATCH partiel)."""
    # Créer facture
    invoice_data = {
        "reservation_id": test_reservation_inv.id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }
    create_response = client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)
    invoice_id = create_response.json()["id"]

    # Mettre à jour
    update_data = {
        "status": "sent",
        "due_date": str(date.today() + timedelta(days=30))
    }
    response = client.patch(
        f"/api/v1/invoices/{invoice_id}",
        json=update_data,
        headers=auth_headers_real
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sent"


def test_add_payment_partial(client: TestClient, test_reservation_inv, auth_headers_real):
    """Test ajouter paiement partiel à facture."""
    # Créer facture (total: 3000 centimes = 30€)
    invoice_data = {
        "reservation_id": test_reservation_inv.id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }
    create_response = client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)
    invoice_id = create_response.json()["id"]

    # Ajouter paiement partiel (1500 centimes = 15€)
    payment_data = {
        "amount_cents": 1500,
        "payment_method": "card",
        "payment_date": str(date.today())
    }
    response = client.post(
        f"/api/v1/invoices/{invoice_id}/add-payment",
        json=payment_data,
        headers=auth_headers_real
    )

    assert response.status_code == 200
    data = response.json()
    assert data["paid_amount_cents"] == 1500
    assert data["remaining_amount_cents"] == 1500  # 3000 - 1500
    assert data["is_paid"] is False  # Pas encore complet
    assert data["status"] == "draft"  # Pas changé automatiquement


def test_add_payment_full(client: TestClient, test_reservation_inv, auth_headers_real):
    """Test ajouter paiement complet → status=paid."""
    # Créer facture (total: 3000 centimes = 30€)
    invoice_data = {
        "reservation_id": test_reservation_inv.id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }
    create_response = client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)
    invoice_id = create_response.json()["id"]

    # Ajouter paiement complet
    payment_data = {
        "amount_cents": 3000,
        "payment_method": "card",
        "payment_date": str(date.today())
    }
    response = client.post(
        f"/api/v1/invoices/{invoice_id}/add-payment",
        json=payment_data,
        headers=auth_headers_real
    )

    assert response.status_code == 200
    data = response.json()
    assert data["paid_amount_cents"] == 3000
    assert data["remaining_amount_cents"] == 0
    assert data["is_paid"] is True
    assert data["status"] == "paid"  # Auto-changé


def test_add_payment_exceeds_total(client: TestClient, test_reservation_inv, auth_headers_real):
    """Test ajouter paiement qui dépasse le total → 400."""
    # Créer facture (total: 3000 centimes = 30€)
    invoice_data = {
        "reservation_id": test_reservation_inv.id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }
    create_response = client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)
    invoice_id = create_response.json()["id"]

    # Tenter paiement supérieur au total
    payment_data = {
        "amount_cents": 5000,  # > 3000
        "payment_method": "card",
        "payment_date": str(date.today())
    }
    response = client.post(
        f"/api/v1/invoices/{invoice_id}/add-payment",
        json=payment_data,
        headers=auth_headers_real
    )

    assert response.status_code == 400
    assert "exceed" in response.json()["detail"]


def test_add_payment_to_cancelled_invoice(client: TestClient, test_db, test_reservation_inv, auth_headers_real):
    """Test ajouter paiement à facture annulée → 400."""
    # Créer facture
    invoice_data = {
        "reservation_id": test_reservation_inv.id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }
    create_response = client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)
    invoice_id = create_response.json()["id"]

    # Annuler facture
    client.post(f"/api/v1/invoices/{invoice_id}/cancel", headers=auth_headers_real)

    # Tenter d'ajouter paiement
    payment_data = {
        "amount_cents": 1000,
        "payment_method": "card",
        "payment_date": str(date.today())
    }
    response = client.post(
        f"/api/v1/invoices/{invoice_id}/add-payment",
        json=payment_data,
        headers=auth_headers_real
    )

    assert response.status_code == 400
    assert "cancelled" in response.json()["detail"]


def test_cancel_invoice_success(client: TestClient, test_reservation_inv, auth_headers_real):
    """Test annuler facture non payée."""
    # Créer facture
    invoice_data = {
        "reservation_id": test_reservation_inv.id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }
    create_response = client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)
    invoice_id = create_response.json()["id"]

    # Annuler
    response = client.post(
        f"/api/v1/invoices/{invoice_id}/cancel",
        headers=auth_headers_real
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"


def test_cancel_paid_invoice_forbidden(client: TestClient, test_reservation_inv, auth_headers_real):
    """Test annuler facture payée → 400."""
    # Créer facture et payer
    invoice_data = {
        "reservation_id": test_reservation_inv.id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }
    create_response = client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)
    invoice_id = create_response.json()["id"]

    # Payer intégralement
    payment_data = {
        "amount_cents": 3000,
        "payment_method": "card",
        "payment_date": str(date.today())
    }
    client.post(f"/api/v1/invoices/{invoice_id}/add-payment", json=payment_data, headers=auth_headers_real)

    # Tenter d'annuler
    response = client.post(
        f"/api/v1/invoices/{invoice_id}/cancel",
        headers=auth_headers_real
    )

    assert response.status_code == 400
    assert "paid" in response.json()["detail"]


def test_list_overdue_invoices(client: TestClient, test_db, test_reservation_inv, auth_headers_real):
    """Test lister factures en retard."""
    # Créer facture avec due_date dans le passé
    invoice_data = {
        "reservation_id": test_reservation_inv.id,
        "issue_date": str(date.today() - timedelta(days=30)),
        "due_date": str(date.today() - timedelta(days=15))  # Passé
    }
    create_response = client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)
    invoice_id = create_response.json()["id"]

    # Vérifier overdue
    response = client.get("/api/v1/invoices/overdue", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    # Vérifier que facture créée est dans la liste
    invoice_ids = [item["id"] for item in data]
    assert invoice_id in invoice_ids
    # Vérifier que status est 'overdue'
    for item in data:
        if item["id"] == invoice_id:
            assert item["status"] == "overdue"


def test_filter_invoices_by_status(client: TestClient, test_reservation_inv, auth_headers_real):
    """Test filtrer factures par statut."""
    # Créer facture draft
    invoice_data = {
        "reservation_id": test_reservation_inv.id,
        "issue_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=14))
    }
    client.post("/api/v1/invoices", json=invoice_data, headers=auth_headers_real)

    # Filtrer par status=draft
    response = client.get("/api/v1/invoices?status_filter=draft", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["status"] == "draft"
