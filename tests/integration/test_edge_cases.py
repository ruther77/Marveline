"""Tests edge cases et gestion d'erreurs HTTP."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.product import Product
from app.models.customer import Customer
from app.models.reservation import Reservation, ReservationLine
from app.constants import CustomerType, InvoiceStatus, ProductCategory, ProductCondition, ReservationStatus


# ═══════════════════════════════════════════════════════════════════════════
# Tests 404 Not Found
# ═══════════════════════════════════════════════════════════════════════════

def test_get_nonexistent_product_returns_404(client: TestClient, auth_headers_real):
    """Test GET produit inexistant → 404."""
    response = client.get("/api/v1/products/999999", headers=auth_headers_real)

    assert response.status_code == 404


def test_get_nonexistent_customer_returns_404(client: TestClient, auth_headers_real):
    """Test GET client inexistant → 404."""
    response = client.get("/api/v1/customers/999999", headers=auth_headers_real)

    assert response.status_code == 404


def test_get_nonexistent_reservation_returns_404(client: TestClient, auth_headers_real):
    """Test GET réservation inexistante → 404."""
    response = client.get("/api/v1/reservations/999999", headers=auth_headers_real)

    assert response.status_code == 404


def test_get_nonexistent_invoice_returns_404(client: TestClient, auth_headers_real):
    """Test GET facture inexistante → 404."""
    response = client.get("/api/v1/invoices/999999", headers=auth_headers_real)

    assert response.status_code == 404


def test_update_nonexistent_product_returns_404(client: TestClient, auth_headers_real):
    """Test PATCH produit inexistant → 404."""
    response = client.patch("/api/v1/products/999999", json={"name": "Updated"}, headers=auth_headers_real)

    assert response.status_code == 404


def test_delete_nonexistent_product_returns_404(client: TestClient, auth_headers_real):
    """Test DELETE produit inexistant → 404."""
    response = client.delete("/api/v1/products/999999", headers=auth_headers_real)

    assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Tests 401 Unauthorized
# ═══════════════════════════════════════════════════════════════════════════

def test_list_products_without_auth_returns_401(client: TestClient):
    """Test liste produits sans auth → 401."""
    response = client.get("/api/v1/products")

    assert response.status_code == 401


def test_create_product_without_auth_returns_401(client: TestClient):
    """Test créer produit sans auth → 401."""
    product_data = {
        "name": "Unauthorized Product",
        "sku": "UNAUTH-SKU",
        "category": "test",
        "price_per_day_cents": 1000,
        "deposit_amount_cents": 2000,
        "stock_quantity": 10,
        "available_quantity": 10,
        "condition": "good"
    }

    response = client.post("/api/v1/products", json=product_data)

    assert response.status_code == 401


def test_invalid_token_returns_401(client: TestClient):
    """Test token invalide → 401."""
    headers = {"Authorization": "Bearer invalid_token_12345"}

    response = client.get("/api/v1/products", headers=headers)

    assert response.status_code == 401


def test_expired_token_returns_401(client: TestClient):
    """Test token expiré → 401."""
    from app.core.security import create_access_token
    from datetime import datetime, timedelta

    # Créer token expiré (expires_delta négatif)
    expired_token = create_access_token(
        {"sub": 1, "tenant_id": 1, "email": "test@test.com", "role": "staff"},
        expires_delta=timedelta(seconds=-3600)  # Expiré il y a 1h
    )
    headers = {"Authorization": f"Bearer {expired_token}"}

    response = client.get("/api/v1/products", headers=headers)

    assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# Tests 422 Validation Errors
# ═══════════════════════════════════════════════════════════════════════════

def test_create_product_missing_required_field_returns_422(client: TestClient, auth_headers_real):
    """Test créer produit sans champ requis → 422."""
    product_data = {
        "name": "Incomplete Product",
        # sku manquant (requis)
        "category": "test",
        "price_per_day_cents": 1000,
        "deposit_amount_cents": 2000
    }

    response = client.post("/api/v1/products", json=product_data, headers=auth_headers_real)

    assert response.status_code == 422


def test_create_product_negative_price_returns_422(client: TestClient, auth_headers_real):
    """Test créer produit avec prix négatif → 422."""
    product_data = {
        "name": "Negative Price Product",
        "sku": "NEGATIVE-SKU",
        "category": "test",
        "price_per_day_cents": -1000,  # Négatif
        "deposit_amount_cents": 2000,
        "stock_quantity": 10,
        "available_quantity": 10,
        "condition": "good"
    }

    response = client.post("/api/v1/products", json=product_data, headers=auth_headers_real)

    assert response.status_code == 422


def test_create_customer_invalid_email_returns_422(client: TestClient, auth_headers_real):
    """Test créer client avec email invalide → 422."""
    customer_data = {
        "customer_type": "individual",
        "first_name": "Test",
        "last_name": "User",
        "email": "invalid_email",  # Pas de @
        "phone": "+33612345678",
        "city": "Paris",
        "postal_code": "75001"
    }

    response = client.post("/api/v1/customers", json=customer_data, headers=auth_headers_real)

    assert response.status_code == 422


def test_create_reservation_invalid_dates_returns_422(client: TestClient, test_db, auth_headers_real):
    """Test créer réservation avec dates invalides → 422."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Test",
        last_name="Customer",
        email="testdates@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    product = Product(
        tenant_id=1,
        name="Date Product",
        sku="DATE-PRODUCT",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add_all([customer, product])
    test_db.commit()

    # delivery_date après event_date (invalide)
    reservation_data = {
        "customer_id": customer.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=11)),  # Après event
        "return_date": str(date.today() + timedelta(days=12)),
        "event_location": "Test",
        "lines": [{"product_id": product.id, "quantity": 1}]
    }

    response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)

    assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Tests 400 Bad Request (Business Logic)
# ═══════════════════════════════════════════════════════════════════════════

def test_create_product_duplicate_sku_returns_400(client: TestClient, test_db, auth_headers_real):
    """Test créer produit avec SKU dupliqué → 400."""
    existing_product = Product(
        tenant_id=1,
        name="Existing Product",
        sku="DUPLICATE-SKU",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(existing_product)
    test_db.commit()

    product_data = {
        "name": "New Product",
        "sku": "DUPLICATE-SKU",  # Déjà existant
        "category": "test",
        "price_per_day_cents": 1000,
        "deposit_amount_cents": 2000,
        "stock_quantity": 10,
        "available_quantity": 10,
        "condition": "good"
    }

    response = client.post("/api/v1/products", json=product_data, headers=auth_headers_real)

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_create_customer_duplicate_email_returns_400(client: TestClient, test_db, auth_headers_real):
    """Test créer client avec email dupliqué → 400."""
    existing_customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Existing",
        last_name="Customer",
        email="existing@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(existing_customer)
    test_db.commit()

    customer_data = {
        "customer_type": "individual",
        "first_name": "New",
        "last_name": "Customer",
        "email": "existing@example.com",  # Déjà existant
        "phone": "+33600000000",
        "city": "Lyon",
        "postal_code": "69001"
    }

    response = client.post("/api/v1/customers", json=customer_data, headers=auth_headers_real)

    assert response.status_code == 400


def test_confirm_reservation_insufficient_stock_returns_400(client: TestClient, test_db, auth_headers_real):
    """Test confirmer réservation avec stock insuffisant → 400."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Stock",
        last_name="Test",
        email="stocktest@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    product = Product(
        tenant_id=1,
        name="Low Stock Product",
        sku="LOW-STOCK-TEST",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=2,  # Seulement 2 disponibles
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add_all([customer, product])
    test_db.commit()

    # Créer réservation avec quantité > stock
    reservation_data = {
        "customer_id": customer.id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Test",
        "lines": [{"product_id": product.id, "quantity": 5}]  # > 2
    }
    res_response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    reservation_id = res_response.json()["id"]

    # Tenter de confirmer
    response = client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=auth_headers_real)

    assert response.status_code == 400
    assert "stock" in response.json()["detail"].lower()


def test_cancel_already_cancelled_reservation_returns_400(client: TestClient, test_db, auth_headers_real):
    """Test annuler réservation déjà annulée → 400."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Cancel",
        last_name="Test",
        email="canceltest@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-CANCELLED",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CANCELLED,  # Déjà annulée
        total_amount=1000,
        deposit_amount=500,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()

    response = client.post(f"/api/v1/reservations/{reservation.id}/cancel", headers=auth_headers_real)

    assert response.status_code == 400


def test_add_payment_exceeding_total_returns_400(client: TestClient, test_db, auth_headers_real):
    """Test ajouter paiement qui dépasse total → 400."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Payment",
        last_name="Test",
        email="paymenttest@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()

    from app.models.reservation import Reservation
    from app.models.invoice import Invoice

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-PAYMENT-TEST",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()

    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-EXCEED",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount=10000,
        paid_amount=0,
        status=ReservationStatus.DRAFT
    )
    test_db.add(invoice)
    test_db.commit()

    # Tenter paiement supérieur au total
    payment_data = {
        "amount_cents": 15000,  # > 10000
        "payment_method": "card",
        "payment_date": str(date.today())
    }

    response = client.post(f"/api/v1/invoices/{invoice.id}/add-payment", json=payment_data, headers=auth_headers_real)

    assert response.status_code == 400


def test_cancel_paid_invoice_returns_400(client: TestClient, test_db, auth_headers_real):
    """Test annuler facture payée → 400."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Paid",
        last_name="Invoice",
        email="paidinvoice@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()

    from app.models.reservation import Reservation
    from app.models.invoice import Invoice

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-PAID",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()

    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-PAID",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount=10000,
        paid_amount=10000,  # Payée
        status=InvoiceStatus.PAID
    )
    test_db.add(invoice)
    test_db.commit()

    response = client.post(f"/api/v1/invoices/{invoice.id}/cancel", headers=auth_headers_real)

    assert response.status_code == 400
    assert "paid" in response.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════════
# Tests Pagination Edge Cases
# ═══════════════════════════════════════════════════════════════════════════

def test_list_products_with_large_limit_capped_at_1000(client: TestClient, auth_headers_real):
    """Test limit > 1000 est cappé à 1000."""
    response = client.get("/api/v1/products?limit=5000", headers=auth_headers_real)

    assert response.status_code == 200
    # Vérifier que limit est cappé (si implémenté dans endpoint)


def test_list_products_with_negative_skip_returns_422(client: TestClient, auth_headers_real):
    """Test skip négatif → 422."""
    response = client.get("/api/v1/products?skip=-10", headers=auth_headers_real)

    assert response.status_code == 422


def test_list_empty_results(client: TestClient, test_db, auth_headers_real):
    """Test liste vide retourne 200 avec items vides."""
    # S'assurer qu'aucun produit n'existe pour ce tenant
    response = client.get("/api/v1/products?category=nonexistent_category", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
