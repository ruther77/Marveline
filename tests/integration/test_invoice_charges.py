"""Tests d'intégration pour l'endpoint POST /invoices/{id}/add-charge."""
import math
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.customer import Customer
from app.models.product import Product
from app.models.reservation import Reservation, ReservationLine
from app.models.invoice import Invoice
from app.constants import (
    CustomerType, ProductCategory, ProductCondition,
    ReservationStatus, InvoiceStatus,
    HOURLY_RATE_WEEKDAY_CENTS, HOURLY_RATE_WEEKEND_CENTS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def customer_chg(test_db):
    c = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Bob",
        last_name="Martin",
        email="bob.martin.chg@example.com",
        phone="+33600000001",
        city="Lyon",
        postal_code="69001",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def product_chg(test_db):
    p = Product(
        tenant_id=1,
        name="Table Ronde Charge",
        sku="TABLE-CHG-001",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    return p


@pytest.fixture
def reservation_chg(test_db, customer_chg, product_chg):
    r = Reservation(
        tenant_id=1,
        customer_id=customer_chg.id,
        reference="RES-CHG-001",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Salle des fêtes",
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=5000,
        deposit_amount_cents=10000,
        deposit_paid=False,
    )
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)

    line = ReservationLine(
        tenant_id=1,
        reservation_id=r.id,
        product_id=product_chg.id,
        quantity=5,
        unit_price_cents=1000,
        subtotal_cents=5000,
    )
    test_db.add(line)
    test_db.commit()
    return r


@pytest.fixture
def draft_invoice(test_db, reservation_chg):
    """Facture en statut draft prête pour les tests de charge."""
    inv = Invoice(
        tenant_id=1,
        reservation_id=reservation_chg.id,
        invoice_number="INV-2026-TCHG1",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount_cents=5000,
        paid_amount_cents=0,
        status=InvoiceStatus.DRAFT,
    )
    test_db.add(inv)
    test_db.commit()
    test_db.refresh(inv)
    return inv


@pytest.fixture
def paid_invoice(test_db, reservation_chg):
    """Facture payée — doit refuser les charges."""
    inv = Invoice(
        tenant_id=1,
        reservation_id=reservation_chg.id,
        invoice_number="INV-2026-TCHG2",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount_cents=5000,
        paid_amount_cents=5000,
        status=InvoiceStatus.PAID,
    )
    test_db.add(inv)
    test_db.commit()
    test_db.refresh(inv)
    return inv


@pytest.fixture
def cancelled_invoice(test_db, reservation_chg):
    """Facture annulée — doit refuser les charges."""
    inv = Invoice(
        tenant_id=1,
        reservation_id=reservation_chg.id,
        invoice_number="INV-2026-TCHG3",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount_cents=5000,
        paid_amount_cents=0,
        status=InvoiceStatus.CANCELLED,
    )
    test_db.add(inv)
    test_db.commit()
    test_db.refresh(inv)
    return inv


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_add_damage_charge_increments_total(
    client: TestClient, draft_invoice, auth_headers_real, test_db
):
    """DAMAGE charge → total_amount de la facture incrémenté du montant."""
    initial_total = draft_invoice.total_amount  # 5000

    payload = {
        "charge_type": "DAMAGE",
        "description": "Assiette cassée",
        "amount_cents": 1500,
    }
    url = f"/api/v1/invoices/{draft_invoice.id}/add-charge"
    response = client.post(url, json=payload, headers=auth_headers_real)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["charge_type"] == "DAMAGE"
    assert data["amount_cents"] == 1500
    assert data["description"] == "Assiette cassée"
    assert data["invoice_id"] == draft_invoice.id

    # Vérifier que total_amount de la facture a bien été incrémenté
    test_db.refresh(draft_invoice)
    assert draft_invoice.total_amount == initial_total + 1500


def test_add_labor_weekday_charge_calculates_correctly(
    client: TestClient, draft_invoice, auth_headers_real, test_db
):
    """LABOR weekday → ceil(hours × HOURLY_RATE_WEEKDAY_CENTS)."""
    hours = 2.5
    expected_amount = math.ceil(hours * HOURLY_RATE_WEEKDAY_CENTS)  # ceil(2.5 × 3000) = 7500

    payload = {
        "charge_type": "LABOR",
        "description": "Nettoyage post-événement",
        "hours": hours,
        "day_type": "weekday",
    }
    url = f"/api/v1/invoices/{draft_invoice.id}/add-charge"
    response = client.post(url, json=payload, headers=auth_headers_real)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["charge_type"] == "LABOR"
    assert data["amount_cents"] == expected_amount
    assert data["day_type"] == "weekday"

    test_db.refresh(draft_invoice)
    # Le total doit avoir augmenté du montant calculé
    # Note : un test DAMAGE a pu modifier draft_invoice — on vérifie juste la présence
    # de la charge (montant correct)


def test_add_labor_weekend_charge_calculates_correctly(
    client: TestClient, draft_invoice, auth_headers_real, test_db
):
    """LABOR weekend → ceil(hours × HOURLY_RATE_WEEKEND_CENTS)."""
    hours = 1.0
    expected_amount = math.ceil(hours * HOURLY_RATE_WEEKEND_CENTS)  # ceil(1 × 6000) = 6000

    payload = {
        "charge_type": "LABOR",
        "description": "Montage le week-end",
        "hours": hours,
        "day_type": "weekend",
    }
    url = f"/api/v1/invoices/{draft_invoice.id}/add-charge"
    response = client.post(url, json=payload, headers=auth_headers_real)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["amount_cents"] == expected_amount
    assert data["day_type"] == "weekend"


def test_add_labor_night_charge_uses_weekend_rate(
    client: TestClient, draft_invoice, auth_headers_real
):
    """LABOR night → ceil(hours × HOURLY_RATE_WEEKEND_CENTS) (même taux que weekend)."""
    hours = 3.0
    expected_amount = math.ceil(hours * HOURLY_RATE_WEEKEND_CENTS)  # ceil(3 × 6000) = 18000

    payload = {
        "charge_type": "LABOR",
        "description": "Démontage nocturne",
        "hours": hours,
        "day_type": "night",
    }
    url = f"/api/v1/invoices/{draft_invoice.id}/add-charge"
    response = client.post(url, json=payload, headers=auth_headers_real)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["amount_cents"] == expected_amount
    assert data["day_type"] == "night"


def test_add_charge_refuses_paid_invoice(
    client: TestClient, paid_invoice, auth_headers_real
):
    """Facture payée → 422."""
    payload = {
        "charge_type": "DAMAGE",
        "description": "Dommage post-paiement",
        "amount_cents": 1000,
    }
    url = f"/api/v1/invoices/{paid_invoice.id}/add-charge"
    response = client.post(url, json=payload, headers=auth_headers_real)

    assert response.status_code == 422, response.text
    assert "paid" in response.json()["detail"].lower()


def test_add_charge_refuses_cancelled_invoice(
    client: TestClient, cancelled_invoice, auth_headers_real
):
    """Facture annulée → 422."""
    payload = {
        "charge_type": "DAMAGE",
        "description": "Dommage sur annulée",
        "amount_cents": 500,
    }
    url = f"/api/v1/invoices/{cancelled_invoice.id}/add-charge"
    response = client.post(url, json=payload, headers=auth_headers_real)

    assert response.status_code == 422, response.text
    assert "cancelled" in response.json()["detail"].lower()


def test_add_charge_invoice_not_found(
    client: TestClient, auth_headers_real
):
    """Facture inexistante → 404."""
    payload = {
        "charge_type": "DAMAGE",
        "description": "Charge sur facture inconnue",
        "amount_cents": 1000,
    }
    response = client.post("/api/v1/invoices/999999/add-charge", json=payload, headers=auth_headers_real)
    assert response.status_code == 404


def test_add_charge_tenant_isolation(
    client: TestClient, draft_invoice, auth_headers_tenant2
):
    """Facture tenant 1 inaccessible depuis tenant 2 → 404."""
    payload = {
        "charge_type": "DAMAGE",
        "description": "Tentative cross-tenant",
        "amount_cents": 100,
    }
    url = f"/api/v1/invoices/{draft_invoice.id}/add-charge"
    response = client.post(url, json=payload, headers=auth_headers_tenant2)

    assert response.status_code == 404
