"""Tests d'intégration pour les endpoints avoirs (credit notes) et actions factures."""
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
def customer_cn(test_db):
    c = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Alice",
        last_name="Dupont",
        email="alice.cn@example.com",
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
def product_cn(test_db):
    p = Product(
        tenant_id=1,
        name="Chaise Credit",
        sku="CHAIR-CN-001",
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
def reservation_cn(test_db, customer_cn, product_cn):
    r = Reservation(
        tenant_id=1,
        customer_id=customer_cn.id,
        reference="RES-CN-001",
        event_date=date.today() + timedelta(days=15),
        delivery_date=date.today() + timedelta(days=14),
        return_date=date.today() + timedelta(days=16),
        event_location="Salle Lumière",
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
        product_id=product_cn.id,
        quantity=10,
        unit_price_cents=500,
        subtotal_cents=5000,
    )
    test_db.add(line)
    test_db.commit()
    return r


@pytest.fixture
def sent_invoice(test_db, reservation_cn):
    inv = Invoice(
        tenant_id=1,
        reservation_id=reservation_cn.id,
        invoice_number="INV-2026-TCN01",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount_cents=10000,
        paid_amount_cents=0,
        status=InvoiceStatus.SENT,
    )
    test_db.add(inv)
    test_db.commit()
    test_db.refresh(inv)
    return inv


@pytest.fixture
def draft_invoice_cn(test_db, reservation_cn):
    inv = Invoice(
        tenant_id=1,
        reservation_id=reservation_cn.id,
        invoice_number="INV-2026-TCN02",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount_cents=8000,
        paid_amount_cents=0,
        status=InvoiceStatus.DRAFT,
    )
    test_db.add(inv)
    test_db.commit()
    test_db.refresh(inv)
    return inv


# ---------------------------------------------------------------------------
# Tests — POST /{id}/credit-note
# ---------------------------------------------------------------------------

class TestCreateCreditNote:
    def test_create_credit_note_ok(self, client: TestClient, auth_headers_real: dict, sent_invoice: Invoice):
        resp = client.post(
            f"/api/v1/invoices/{sent_invoice.id}/credit-note",
            json={"amount_cents": 3000, "reason": "Erreur de facturation initiale"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["amount_cents"] == 3000
        assert data["original_invoice_id"] == sent_invoice.id
        assert data["status"] == "draft"
        assert data["invoice_number"].startswith("AVOIR-")
        assert data["amount_euros"] == 30.0

    def test_create_credit_note_exceeds_invoice(self, client: TestClient, auth_headers_real: dict, sent_invoice: Invoice):
        resp = client.post(
            f"/api/v1/invoices/{sent_invoice.id}/credit-note",
            json={"amount_cents": 99999, "reason": "Montant trop élevé intentionnellement"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 400

    def test_create_credit_note_invoice_not_found(self, client: TestClient, auth_headers_real: dict):
        resp = client.post(
            "/api/v1/invoices/99999/credit-note",
            json={"amount_cents": 1000, "reason": "Avoir test introuvable"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 404

    def test_create_credit_note_cumulative_cap(
        self, client: TestClient, auth_headers_real: dict, sent_invoice: Invoice
    ):
        """Deux avoirs successifs : le second ne peut pas dépasser le solde restant."""
        # Premier avoir : 7000
        r1 = client.post(
            f"/api/v1/invoices/{sent_invoice.id}/credit-note",
            json={"amount_cents": 7000, "reason": "Premier avoir partiel"},
            headers=auth_headers_real,
        )
        assert r1.status_code == 201

        # Second avoir : 4000 → total 11000 > 10000 → 400
        r2 = client.post(
            f"/api/v1/invoices/{sent_invoice.id}/credit-note",
            json={"amount_cents": 4000, "reason": "Deuxième avoir excédentaire"},
            headers=auth_headers_real,
        )
        assert r2.status_code == 400


# ---------------------------------------------------------------------------
# Tests — GET /{id}/credit-notes
# ---------------------------------------------------------------------------

class TestListCreditNotes:
    def test_list_empty(self, client: TestClient, auth_headers_real: dict, sent_invoice: Invoice):
        resp = client.get(
            f"/api/v1/invoices/{sent_invoice.id}/credit-notes",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_creation(self, client: TestClient, auth_headers_real: dict, sent_invoice: Invoice):
        client.post(
            f"/api/v1/invoices/{sent_invoice.id}/credit-note",
            json={"amount_cents": 2000, "reason": "Avoir liste test suffisant"},
            headers=auth_headers_real,
        )
        resp = client.get(
            f"/api/v1/invoices/{sent_invoice.id}/credit-notes",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
# Tests — POST /{id}/mark-sent
# ---------------------------------------------------------------------------

class TestMarkSent:
    def test_mark_sent_from_draft(self, client: TestClient, auth_headers_real: dict, draft_invoice_cn: Invoice):
        resp = client.post(
            f"/api/v1/invoices/{draft_invoice_cn.id}/mark-sent",
            json={},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "sent"

    def test_mark_sent_invalid_status(self, client: TestClient, auth_headers_real: dict, sent_invoice: Invoice):
        """Déjà 'sent' → OK (idempotent selon le service)."""
        resp = client.post(
            f"/api/v1/invoices/{sent_invoice.id}/mark-sent",
            json={},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — POST /{id}/remind
# ---------------------------------------------------------------------------

class TestRemind:
    def test_remind_sent_invoice(self, client: TestClient, auth_headers_real: dict, sent_invoice: Invoice):
        resp = client.post(
            f"/api/v1/invoices/{sent_invoice.id}/remind",
            json={"notes": "Rappel paiement sous 7 jours"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200

    def test_remind_draft_invoice_rejected(self, client: TestClient, auth_headers_real: dict, draft_invoice_cn: Invoice):
        """Relancer une facture draft → 400."""
        resp = client.post(
            f"/api/v1/invoices/{draft_invoice_cn.id}/remind",
            json={},
            headers=auth_headers_real,
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests — POST /damage
# ---------------------------------------------------------------------------

class TestDamageInvoice:
    def test_create_damage_invoice_ok(
        self, client: TestClient, auth_headers_real: dict, reservation_cn: Reservation
    ):
        resp = client.post(
            "/api/v1/invoices/damage",
            json={
                "reservation_id": reservation_cn.id,
                "charges": [
                    {"charge_type": "DAMAGE", "description": "Nappe déchirée", "amount_cents": 2500},
                    {"charge_type": "DAMAGE", "description": "Verre cassé", "amount_cents": 800},
                ],
                "notes": "Dommages constatés au retour",
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "draft"
        assert data["invoice_number"].startswith("INV-")

    def test_create_damage_reservation_not_found(self, client: TestClient, auth_headers_real: dict):
        resp = client.post(
            "/api/v1/invoices/damage",
            json={
                "reservation_id": 99999,
                "charges": [
                    {"charge_type": "DAMAGE", "description": "Test", "amount_cents": 1000}
                ],
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 404
