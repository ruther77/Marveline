"""Tests d'isolation multi-tenant CRITIQUES pour sécurité.

Ces tests vérifient qu'un utilisateur d'un tenant ne peut JAMAIS accéder
aux données d'un autre tenant. C'est la règle de sécurité la plus importante.

Pattern attendu:
- User tenant1 crée ressource → status 201/200
- User tenant2 tente d'accéder ressource tenant1 → status 404 (pas 403 pour éviter info leakage)
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.customer import Customer
from app.models.product import Product
from app.models.reservation import Reservation, ReservationLine
from app.models.invoice import Invoice
from app.constants import CustomerType, ProductCategory, ProductCondition, ReservationStatus


@pytest.fixture
def tenant1_product(test_db):
    """Produit appartenant à tenant_id=1."""
    product = Product(
        tenant_id=1,
        name="Table tenant 1",
        sku="TABLE-T1-SECURITY",
        category=ProductCategory.NAPPE,
        price_per_day=2000,
        deposit_amount=5000,
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
def tenant1_customer(test_db):
    """Client appartenant à tenant_id=1."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Alice",
        last_name="Tenant1",
        email="alice@tenant1.com",
        phone="+33600000001",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture
def tenant1_reservation(test_db, tenant1_customer, tenant1_product):
    """Réservation appartenant à tenant_id=1."""
    reservation = Reservation(
        tenant_id=1,
        customer_id=tenant1_customer.id,
        reference="RES-T1-001",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test Location",
        status=ReservationStatus.CONFIRMED,
        total_amount=6000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()
    test_db.refresh(reservation)

    # Ajouter ligne
    line = ReservationLine(
        tenant_id=1,
        reservation_id=reservation.id,
        product_id=tenant1_product.id,
        quantity=1,
        unit_price=2000,
        subtotal=6000
    )
    test_db.add(line)
    test_db.commit()

    return reservation


@pytest.fixture
def tenant1_invoice(test_db, tenant1_reservation):
    """Facture appartenant à tenant_id=1."""
    invoice = Invoice(
        tenant_id=1,
        reservation_id=tenant1_reservation.id,
        invoice_number="INV-T1-001",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount=6000,
        paid_amount=0,
        status=ReservationStatus.DRAFT
    )
    test_db.add(invoice)
    test_db.commit()
    test_db.refresh(invoice)
    return invoice


# ═══════════════════════════════════════════════════════════════════════════
# Tests anti-cross-tenant PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════

def test_tenant2_cannot_get_tenant1_product(client: TestClient, tenant1_product, auth_headers_tenant2):
    """User tenant2 tente d'accéder produit tenant1 → 404 (pas 403)."""
    response = client.get(f"/api/v1/products/{tenant1_product.id}", headers=auth_headers_tenant2)

    # CRITICAL: Doit être 404 (pas 403) pour éviter info leakage
    # 403 signifierait "la ressource existe mais tu n'as pas accès" → info leak
    # 404 signifie "la ressource n'existe pas (pour toi)"
    assert response.status_code == 404


def test_tenant2_cannot_update_tenant1_product(client: TestClient, tenant1_product, test_db, test_admin_tenant2, auth_headers_admin_tenant2):
    """Admin tenant2 tente de modifier produit tenant1 → 404."""
    update_data = {"price_per_day_cents": 9999}
    response = client.patch(
        f"/api/v1/products/{tenant1_product.id}",
        json=update_data,
        headers=auth_headers_admin_tenant2
    )

    assert response.status_code == 404


def test_tenant2_cannot_delete_tenant1_product(client: TestClient, tenant1_product, auth_headers_admin_tenant2):
    """Admin tenant2 tente de supprimer produit tenant1 → 404."""
    # Même si role=admin, ne peut pas supprimer produit d'un autre tenant
    response = client.delete(f"/api/v1/products/{tenant1_product.id}", headers=auth_headers_admin_tenant2)

    assert response.status_code == 404


def test_tenant2_cannot_list_tenant1_products(client: TestClient, tenant1_product, auth_headers_tenant2):
    """User tenant2 liste produits → ne voit PAS produits tenant1."""
    response = client.get("/api/v1/products", headers=auth_headers_tenant2)

    assert response.status_code == 200
    data = response.json()

    # Vérifier que produit tenant1 n'est PAS dans la liste
    product_ids = [item["id"] for item in data["items"]]
    assert tenant1_product.id not in product_ids


# ═══════════════════════════════════════════════════════════════════════════
# Tests anti-cross-tenant CUSTOMERS
# ═══════════════════════════════════════════════════════════════════════════

def test_tenant2_cannot_get_tenant1_customer(client: TestClient, tenant1_customer, auth_headers_tenant2):
    """User tenant2 tente d'accéder client tenant1 → 404."""
    response = client.get(f"/api/v1/customers/{tenant1_customer.id}", headers=auth_headers_tenant2)

    assert response.status_code == 404


def test_tenant2_cannot_update_tenant1_customer(client: TestClient, tenant1_customer, auth_headers_tenant2):
    """User tenant2 tente de modifier client tenant1 → 404."""
    update_data = {"phone": "+33699999999"}
    response = client.patch(
        f"/api/v1/customers/{tenant1_customer.id}",
        json=update_data,
        headers=auth_headers_tenant2
    )

    assert response.status_code == 404


def test_tenant2_cannot_delete_tenant1_customer(client: TestClient, tenant1_customer, auth_headers_tenant2):
    """User tenant2 tente de supprimer client tenant1 → 404."""
    response = client.delete(f"/api/v1/customers/{tenant1_customer.id}", headers=auth_headers_tenant2)

    assert response.status_code == 404


def test_tenant2_cannot_list_tenant1_customers(client: TestClient, tenant1_customer, auth_headers_tenant2):
    """User tenant2 liste clients → ne voit PAS clients tenant1."""
    response = client.get("/api/v1/customers", headers=auth_headers_tenant2)

    assert response.status_code == 200
    data = response.json()

    customer_ids = [item["id"] for item in data["items"]]
    assert tenant1_customer.id not in customer_ids


# ═══════════════════════════════════════════════════════════════════════════
# Tests anti-cross-tenant RESERVATIONS
# ═══════════════════════════════════════════════════════════════════════════

def test_tenant2_cannot_get_tenant1_reservation(client: TestClient, tenant1_reservation, auth_headers_tenant2):
    """User tenant2 tente d'accéder réservation tenant1 → 404."""
    response = client.get(f"/api/v1/reservations/{tenant1_reservation.id}", headers=auth_headers_tenant2)

    assert response.status_code == 404


def test_tenant2_cannot_update_tenant1_reservation(client: TestClient, tenant1_reservation, auth_headers_tenant2):
    """User tenant2 tente de modifier réservation tenant1 → 404."""
    update_data = {"event_location": "Hacked Location"}
    response = client.patch(
        f"/api/v1/reservations/{tenant1_reservation.id}",
        json=update_data,
        headers=auth_headers_tenant2
    )

    assert response.status_code == 404


def test_tenant2_cannot_confirm_tenant1_reservation(client: TestClient, test_db, tenant1_reservation, auth_headers_tenant2):
    """User tenant2 tente de confirmer réservation tenant1 → 404."""
    # Mettre réservation en draft pour pouvoir confirmer
    tenant1_reservation.status=ReservationStatus.DRAFT
    test_db.commit()

    response = client.post(
        f"/api/v1/reservations/{tenant1_reservation.id}/confirm",
        headers=auth_headers_tenant2
    )

    assert response.status_code == 404

    # Restaurer status
    tenant1_reservation.status=ReservationStatus.CONFIRMED
    test_db.commit()


def test_tenant2_cannot_cancel_tenant1_reservation(client: TestClient, tenant1_reservation, auth_headers_tenant2):
    """User tenant2 tente d'annuler réservation tenant1 → 404."""
    response = client.post(
        f"/api/v1/reservations/{tenant1_reservation.id}/cancel",
        headers=auth_headers_tenant2
    )

    assert response.status_code == 404


def test_tenant2_cannot_list_tenant1_reservations(client: TestClient, tenant1_reservation, auth_headers_tenant2):
    """User tenant2 liste réservations → ne voit PAS réservations tenant1."""
    response = client.get("/api/v1/reservations", headers=auth_headers_tenant2)

    assert response.status_code == 200
    data = response.json()

    reservation_ids = [item["id"] for item in data["items"]]
    assert tenant1_reservation.id not in reservation_ids


# ═══════════════════════════════════════════════════════════════════════════
# Tests anti-cross-tenant INVOICES
# ═══════════════════════════════════════════════════════════════════════════

def test_tenant2_cannot_get_tenant1_invoice(client: TestClient, tenant1_invoice, auth_headers_tenant2):
    """User tenant2 tente d'accéder facture tenant1 → 404."""
    response = client.get(f"/api/v1/invoices/{tenant1_invoice.id}", headers=auth_headers_tenant2)

    assert response.status_code == 404


def test_tenant2_cannot_update_tenant1_invoice(client: TestClient, tenant1_invoice, auth_headers_tenant2):
    """User tenant2 tente de modifier facture tenant1 → 404."""
    update_data = {"status": "sent"}
    response = client.patch(
        f"/api/v1/invoices/{tenant1_invoice.id}",
        json=update_data,
        headers=auth_headers_tenant2
    )

    assert response.status_code == 404


def test_tenant2_cannot_add_payment_to_tenant1_invoice(client: TestClient, tenant1_invoice, auth_headers_tenant2):
    """User tenant2 tente d'ajouter paiement à facture tenant1 → 404."""
    payment_data = {
        "amount_cents": 1000,
        "payment_method": "card",
        "payment_date": str(date.today())
    }
    response = client.post(
        f"/api/v1/invoices/{tenant1_invoice.id}/add-payment",
        json=payment_data,
        headers=auth_headers_tenant2
    )

    assert response.status_code == 404


def test_tenant2_cannot_cancel_tenant1_invoice(client: TestClient, tenant1_invoice, auth_headers_tenant2):
    """User tenant2 tente d'annuler facture tenant1 → 404."""
    response = client.post(
        f"/api/v1/invoices/{tenant1_invoice.id}/cancel",
        headers=auth_headers_tenant2
    )

    assert response.status_code == 404


def test_tenant2_cannot_list_tenant1_invoices(client: TestClient, tenant1_invoice, auth_headers_tenant2):
    """User tenant2 liste factures → ne voit PAS factures tenant1."""
    response = client.get("/api/v1/invoices", headers=auth_headers_tenant2)

    assert response.status_code == 200
    data = response.json()

    invoice_ids = [item["id"] for item in data["items"]]
    assert tenant1_invoice.id not in invoice_ids


# ═══════════════════════════════════════════════════════════════════════════
# Tests cross-tenant via création (tentative d'usurpation tenant_id)
# ═══════════════════════════════════════════════════════════════════════════

def test_cannot_create_resource_for_another_tenant_via_payload(
    client: TestClient,
    test_db,
    auth_headers_tenant2
):
    """
    User tenant2 tente de créer produit avec tenant_id=1 dans payload → ignoré.
    Le tenant_id doit toujours venir du JWT, jamais du payload.
    """
    # Tenter de créer produit avec tenant_id=1 (usurpation)
    malicious_payload = {
        "tenant_id": 1,  # Tentative d'usurpation
        "name": "Produit malveillant",
        "sku": "MALICIOUS-SKU",
        "category": "autre",
        "price_per_day_cents": 1000,
        "deposit_amount_cents": 2000,
        "stock_quantity": 10,
        "available_quantity": 10,
        "condition": "bon"
    }

    # Créer admin tenant2 pour avoir permission de créer produits
    from app.models.user import User
    from app.core.security import get_password_hash, create_access_token

    admin_t2 = User(
        tenant_id=2,
        email="admin2@tenant2.com",
        hashed_password=get_password_hash("admin123"),
        full_name="Admin Tenant 2",
        role="admin",
        is_active=True
    )
    test_db.add(admin_t2)
    test_db.commit()

    admin_t2_token = create_access_token({
        "sub": admin_t2.id,
        "tenant_id": admin_t2.tenant_id,
        "email": admin_t2.email,
        "role": admin_t2.role
    })
    admin_t2_headers = {"Authorization": f"Bearer {admin_t2_token}"}

    response = client.post("/api/v1/products", json=malicious_payload, headers=admin_t2_headers)

    # Si création réussit, vérifier que tenant_id=2 (pas 1)
    if response.status_code == 201:
        created_product = response.json()
        assert created_product["tenant_id"] == 2  # Forcé par JWT, pas payload

        # Cleanup
        test_db.query(Product).filter(Product.id == created_product["id"]).delete()
        test_db.commit()


# Fixture test_admin_tenant2 déplacée vers tests/conftest.py pour réutilisation globale
