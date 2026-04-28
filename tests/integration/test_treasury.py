"""Tests integration — Tresorerie unifiee (GET /treasury/entries, /treasury/summary)."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.models.customer import Customer
from app.models.deposit import Deposit
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.reservation import Reservation, ReservationLine
from app.models.product import Product
from app.constants import (
    CustomerType, ProductCategory, ProductCondition,
    ReservationStatus,
)


@pytest.fixture
def treasury_customer(test_db):
    c = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Tresor",
        last_name="Ier",
        email="tresor@example.com",
        phone="+33600099001",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def treasury_reservation(test_db, treasury_customer):
    r = Reservation(
        tenant_id=1,
        customer_id=treasury_customer.id,
        reference="RES-TREAS-001",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=10000,
        deposit_amount_cents=3000,
        deposit_paid=True,
    )
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)
    return r


@pytest.fixture
def treasury_deposit(test_db, treasury_reservation):
    d = Deposit(
        tenant_id=1,
        reservation_id=treasury_reservation.id,
        amount_cents=3000,
        status="held",
        collection_date=date.today(),
    )
    test_db.add(d)
    test_db.commit()
    test_db.refresh(d)
    return d


@pytest.fixture
def treasury_invoice(test_db, treasury_reservation):
    inv = Invoice(
        tenant_id=1,
        reservation_id=treasury_reservation.id,
        invoice_number="INV-TREAS-001",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=7),
        total_amount_cents=10000,
        total_ttc_cents=12000,
        paid_amount_cents=0,
        status="draft",
        invoice_type="advance",
    )
    test_db.add(inv)
    test_db.commit()
    test_db.refresh(inv)
    return inv


@pytest.fixture
def treasury_payment(test_db, treasury_invoice):
    p = Payment(
        tenant_id=1,
        invoice_id=treasury_invoice.id,
        amount_cents=4000,
        payment_method="card",
        payment_date=date.today(),
    )
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    return p


class TestTreasuryEntries:
    """GET /treasury/entries — liste unifiee."""

    def test_entries_returns_both_types(
        self, client, auth_headers_admin,
        treasury_deposit, treasury_payment,
    ):
        """Les entries contiennent deposits et payments."""
        r = client.get("/api/v1/treasury/entries", headers=auth_headers_admin)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        types = {item["entry_type"] for item in data["items"]}
        assert types == {"deposit", "payment"}

    def test_entries_filter_by_type(
        self, client, auth_headers_admin,
        treasury_deposit, treasury_payment,
    ):
        """Filtre par entry_type fonctionne."""
        r = client.get(
            "/api/v1/treasury/entries?entry_type=deposit",
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["entry_type"] == "deposit"

    def test_entries_filter_by_method(
        self, client, auth_headers_admin,
        treasury_deposit, treasury_payment,
    ):
        """Filtre par methode de paiement (payments uniquement)."""
        r = client.get(
            "/api/v1/treasury/entries?method=card",
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["method"] == "card"

    def test_entries_empty_when_no_data(self, client, auth_headers_admin):
        """Sans donnees, retourne liste vide."""
        r = client.get("/api/v1/treasury/entries", headers=auth_headers_admin)
        assert r.status_code == 200
        assert r.json()["total"] == 0


class TestTreasurySummary:
    """GET /treasury/summary — KPI agreges."""

    def test_summary_aggregates(
        self, client, auth_headers_admin,
        treasury_deposit, treasury_payment,
    ):
        """Summary contient totaux deposits + payments."""
        r = client.get("/api/v1/treasury/summary", headers=auth_headers_admin)
        assert r.status_code == 200
        data = r.json()
        assert data["deposits_held_cents"] == 3000
        assert data["payments_total_cents"] == 4000
        assert data["total_collected_cents"] == 7000
        assert data["deposits_count"] == 1
        assert data["payments_count"] == 1
        assert data["by_method"]["card"] == 4000

    def test_summary_empty(self, client, auth_headers_admin):
        """Summary sans donnees retourne zeros."""
        r = client.get("/api/v1/treasury/summary", headers=auth_headers_admin)
        assert r.status_code == 200
        data = r.json()
        assert data["total_collected_cents"] == 0
        assert data["deposits_count"] == 0
        assert data["payments_count"] == 0


class TestTreasuryCrossTenant:
    """Isolation tenant."""

    def test_tenant2_cannot_see_tenant1_data(
        self, client, auth_headers_admin, auth_headers_tenant2,
        treasury_deposit, treasury_payment,
    ):
        """Tenant 2 ne voit pas les donnees du tenant 1."""
        r = client.get("/api/v1/treasury/entries", headers=auth_headers_tenant2)
        assert r.status_code == 200
        assert r.json()["total"] == 0

        r = client.get("/api/v1/treasury/summary", headers=auth_headers_tenant2)
        assert r.status_code == 200
        assert r.json()["total_collected_cents"] == 0
