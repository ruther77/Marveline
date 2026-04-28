"""Tests intégration — Paiements de factures (POST/GET /invoices/{id}/payments)."""
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
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def customer_pay(test_db):
    c = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Alice",
        last_name="Paiement",
        email="alice.pay@example.com",
        phone="+33600000010",
        city="Paris",
        postal_code="75001",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def product_pay(test_db):
    p = Product(
        tenant_id=1,
        name="Chaise Paiement",
        sku="CHAISE-PAY-001",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=500,
        deposit_amount_cents=1000,
        stock_quantity=20,
        available_quantity=20,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    return p


@pytest.fixture
def reservation_pay(test_db, customer_pay, product_pay):
    r = Reservation(
        tenant_id=1,
        customer_id=customer_pay.id,
        reference="RES-PAY-001",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Salle Paiement",
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=10000,
        deposit_amount_cents=5000,
        deposit_paid=False,
    )
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)

    line = ReservationLine(
        tenant_id=1,
        reservation_id=r.id,
        product_id=product_pay.id,
        quantity=10,
        unit_price_cents=500,
        subtotal_cents=5000,
    )
    test_db.add(line)
    test_db.commit()
    return r


@pytest.fixture
def invoice_pay(test_db, reservation_pay):
    """Facture draft, total=10000 cents."""
    inv = Invoice(
        tenant_id=1,
        reservation_id=reservation_pay.id,
        invoice_number="INV-PAY-0001",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount_cents=10000,
        paid_amount_cents=0,
        status=InvoiceStatus.DRAFT,
    )
    test_db.add(inv)
    test_db.commit()
    test_db.refresh(inv)
    return inv


@pytest.fixture
def invoice_paid(test_db, reservation_pay):
    """Facture déjà entièrement payée."""
    inv = Invoice(
        tenant_id=1,
        reservation_id=reservation_pay.id,
        invoice_number="INV-PAY-0002",
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
def customer_pay_t2(test_db):
    c = Customer(
        tenant_id=2,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Bob",
        last_name="Tenant2",
        email="bob.t2.pay@example.com",
        phone="+33600000011",
        city="Lyon",
        postal_code="69001",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def reservation_pay_t2(test_db, customer_pay_t2):
    r = Reservation(
        tenant_id=2,
        customer_id=customer_pay_t2.id,
        reference="RES-PAY-T2-001",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=5000,
        deposit_amount_cents=0,
        deposit_paid=False,
    )
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)
    return r


@pytest.fixture
def invoice_pay_t2(test_db, reservation_pay_t2):
    """Facture appartenant au tenant_id=2."""
    inv = Invoice(
        tenant_id=2,
        reservation_id=reservation_pay_t2.id,
        invoice_number="INV-PAY-T2-001",
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


# ---------------------------------------------------------------------------
# Tests CRUD
# ---------------------------------------------------------------------------

class TestPaymentsCRUD:
    """Tests CRUD sur /invoices/{id}/payments."""

    def test_add_payment_returns_201(
        self, client: TestClient, auth_headers_admin: dict, invoice_pay
    ):
        """Ajout d'un paiement → 201 avec données correctes."""
        r = client.post(
            f"/api/v1/invoices/{invoice_pay.id}/payments",
            json={
                "amount_cents": 3000,
                "payment_method": "cash",
                "payment_date": str(date.today()),
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["amount_cents"] == 3000
        assert data["payment_method"] == "cash"
        assert data["invoice_id"] == invoice_pay.id
        assert "id" in data

    def test_add_payment_updates_invoice_paid_amount(
        self, client: TestClient, auth_headers_admin: dict, invoice_pay
    ):
        """Ajout paiement → invoice.paid_amount_cents mis à jour."""
        client.post(
            f"/api/v1/invoices/{invoice_pay.id}/payments",
            json={
                "amount_cents": 4000,
                "payment_method": "transfer",
                "payment_date": str(date.today()),
            },
            headers=auth_headers_admin,
        )
        # Vérifier via GET invoice
        r = client.get(f"/api/v1/invoices/{invoice_pay.id}", headers=auth_headers_admin)
        assert r.status_code == 200
        data = r.json()
        assert data["paid_amount_cents"] == 4000

    def test_full_payment_sets_invoice_status_paid(
        self, client: TestClient, auth_headers_admin: dict, invoice_pay
    ):
        """Paiement total → invoice.status = 'paid'."""
        client.post(
            f"/api/v1/invoices/{invoice_pay.id}/payments",
            json={
                "amount_cents": 10000,
                "payment_method": "card",
                "payment_date": str(date.today()),
            },
            headers=auth_headers_admin,
        )
        r = client.get(f"/api/v1/invoices/{invoice_pay.id}", headers=auth_headers_admin)
        assert r.status_code == 200
        assert r.json()["status"] == "paid"

    def test_partial_payments_sum_correctly(
        self, client: TestClient, auth_headers_admin: dict, invoice_pay
    ):
        """Somme de plusieurs paiements correctement cumulée."""
        client.post(
            f"/api/v1/invoices/{invoice_pay.id}/payments",
            json={"amount_cents": 3000, "payment_method": "cash", "payment_date": str(date.today())},
            headers=auth_headers_admin,
        )
        client.post(
            f"/api/v1/invoices/{invoice_pay.id}/payments",
            json={"amount_cents": 4000, "payment_method": "transfer", "payment_date": str(date.today())},
            headers=auth_headers_admin,
        )
        r = client.get(f"/api/v1/invoices/{invoice_pay.id}", headers=auth_headers_admin)
        assert r.status_code == 200
        assert r.json()["paid_amount_cents"] == 7000

    def test_list_payments_empty(
        self, client: TestClient, auth_headers_real: dict, invoice_pay
    ):
        """GET /payments sur facture vierge → liste vide."""
        r = client.get(
            f"/api/v1/invoices/{invoice_pay.id}/payments",
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_list_payments_returns_all(
        self, client: TestClient, auth_headers_admin: dict, auth_headers_real: dict, invoice_pay
    ):
        """GET /payments retourne les paiements créés."""
        client.post(
            f"/api/v1/invoices/{invoice_pay.id}/payments",
            json={"amount_cents": 2000, "payment_method": "check", "payment_date": str(date.today())},
            headers=auth_headers_admin,
        )
        client.post(
            f"/api/v1/invoices/{invoice_pay.id}/payments",
            json={"amount_cents": 3000, "payment_method": "cash", "payment_date": str(date.today())},
            headers=auth_headers_admin,
        )
        r = client.get(
            f"/api/v1/invoices/{invoice_pay.id}/payments",
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 2

    def test_payment_exceeds_remaining_returns_400(
        self, client: TestClient, auth_headers_admin: dict, invoice_pay
    ):
        """Paiement > solde restant → 400."""
        r = client.post(
            f"/api/v1/invoices/{invoice_pay.id}/payments",
            json={
                "amount_cents": 99999,
                "payment_method": "cash",
                "payment_date": str(date.today()),
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 400

    def test_payment_on_paid_invoice_returns_400(
        self, client: TestClient, auth_headers_admin: dict, invoice_paid
    ):
        """Paiement sur facture déjà payée → 400."""
        r = client.post(
            f"/api/v1/invoices/{invoice_paid.id}/payments",
            json={
                "amount_cents": 1000,
                "payment_method": "cash",
                "payment_date": str(date.today()),
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 400

    def test_payment_on_cancelled_invoice_returns_400(
        self, client: TestClient, auth_headers_admin: dict, invoice_pay
    ):
        """Paiement sur facture annulée → 400."""
        cancel_resp = client.post(
            f"/api/v1/invoices/{invoice_pay.id}/cancel",
            headers=auth_headers_admin,
        )
        assert cancel_resp.status_code == 200

        r = client.post(
            f"/api/v1/invoices/{invoice_pay.id}/payments",
            json={
                "amount_cents": 1000,
                "payment_method": "cash",
                "payment_date": str(date.today()),
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 400
        assert "cancelled" in r.json()["detail"]

    def test_payment_on_nonexistent_invoice_returns_404(
        self, client: TestClient, auth_headers_admin: dict
    ):
        """Facture inexistante → 404."""
        r = client.post(
            "/api/v1/invoices/999999/payments",
            json={
                "amount_cents": 1000,
                "payment_method": "cash",
                "payment_date": str(date.today()),
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 404

    def test_payment_with_notes(
        self, client: TestClient, auth_headers_admin: dict, invoice_pay
    ):
        """Ajout paiement avec notes → notes conservées."""
        r = client.post(
            f"/api/v1/invoices/{invoice_pay.id}/payments",
            json={
                "amount_cents": 1000,
                "payment_method": "cash",
                "payment_date": str(date.today()),
                "notes": "Paiement reçu en espèces le 18/02",
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 201
        assert r.json()["notes"] == "Paiement reçu en espèces le 18/02"


# ---------------------------------------------------------------------------
# Tests isolation tenant
# ---------------------------------------------------------------------------

class TestPaymentsTenantIsolation:
    """Tests anti-cross-tenant pour les paiements."""

    def test_cannot_add_payment_to_other_tenant_invoice(
        self, client: TestClient, auth_headers_admin: dict, invoice_pay_t2
    ):
        """Tenant 1 ne peut pas payer une facture du tenant 2 → 404."""
        r = client.post(
            f"/api/v1/invoices/{invoice_pay_t2.id}/payments",
            json={
                "amount_cents": 1000,
                "payment_method": "cash",
                "payment_date": str(date.today()),
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 404

    def test_cannot_list_payments_of_other_tenant_invoice(
        self, client: TestClient, auth_headers_real: dict, invoice_pay_t2
    ):
        """Tenant 1 ne peut pas lister les paiements d'une facture du tenant 2 → 404."""
        r = client.get(
            f"/api/v1/invoices/{invoice_pay_t2.id}/payments",
            headers=auth_headers_real,
        )
        assert r.status_code == 404
