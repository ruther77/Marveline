"""Tests intégration — Relances planifiées (B8-C)."""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from datetime import timedelta
from app.models.reservation import Reservation, ReservationLine
from app.models.invoice import Invoice
from app.models.customer import Customer
from app.models.product import Product
from app.constants import ProductCategory, ReservationStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def future_dt(days: int = 1) -> str:
    return (datetime.now(tz=timezone.utc) + timedelta(days=days)).isoformat()


def past_dt() -> str:
    return (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------

@pytest.fixture
def customer_rel(test_db):
    c = Customer(
        tenant_id=1, first_name="Rel", last_name="Client",
        email="rel@test.com", customer_type="individual"
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def product_rel(test_db):
    p = Product(
        tenant_id=1, name="Produit Relance", sku="REL-001",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=500, stock_quantity=5, available_quantity=5
    )
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    return p


@pytest.fixture
def reservation_rel(test_db, customer_rel, product_rel):
    from datetime import date
    r = Reservation(
        tenant_id=1,
        customer_id=customer_rel.id,
        reference="RES-REL-001",
        event_date=date(2026, 6, 2),
        delivery_date=date(2026, 6, 1),
        return_date=date(2026, 6, 3),
        event_location="Salle test",
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=1500,
        deposit_amount_cents=0,
    )
    test_db.add(r)
    test_db.flush()
    line = ReservationLine(
        tenant_id=1,
        reservation_id=r.id, product_id=product_rel.id,
        quantity=1, unit_price_cents=500, subtotal_cents=500
    )
    test_db.add(line)
    test_db.commit()
    test_db.refresh(r)
    return r


@pytest.fixture
def draft_invoice_rel(test_db, reservation_rel):
    inv = Invoice(
        tenant_id=1,
        reservation_id=reservation_rel.id,
        invoice_number="INV-REL-001",
        issue_date=datetime.now(tz=timezone.utc).date(),
        due_date=datetime.now(tz=timezone.utc).date(),
        total_amount_cents=1000,
        paid_amount_cents=0,
        status="draft",
    )
    test_db.add(inv)
    test_db.commit()
    test_db.refresh(inv)
    return inv


@pytest.fixture
def customer_t2(test_db):
    c = Customer(
        tenant_id=2, first_name="T2", last_name="Client",
        email="t2rel@test.com", customer_type="individual"
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


# ---------------------------------------------------------------------------
# GET /relances
# ---------------------------------------------------------------------------

class TestListRelances:
    def test_list_empty(self, client: TestClient, auth_headers_real: dict):
        resp = client.get("/api/v1/relances", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_list_with_invoice_filter(
        self, client: TestClient, auth_headers_real: dict, auth_headers_admin: dict, draft_invoice_rel: Invoice
    ):
        client.post(
            "/api/v1/relances/schedule",
            json={"invoice_id": draft_invoice_rel.id, "scheduled_at": future_dt()},
            headers=auth_headers_admin,
        )
        resp = client.get(
            f"/api/v1/relances?invoice_id={draft_invoice_rel.id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert any(r["invoice_id"] == draft_invoice_rel.id for r in data["items"])

    def test_list_filter_unknown_invoice_returns_empty(
        self, client: TestClient, auth_headers_real: dict
    ):
        resp = client.get("/api/v1/relances?invoice_id=99999", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0

    def test_list_with_customer_filter(
        self,
        client: TestClient,
        auth_headers_real: dict,
        auth_headers_admin: dict,
        draft_invoice_rel: Invoice,
        customer_rel: Customer,
    ):
        """Filtre par customer_id via join Relance→Invoice→Reservation→Customer."""
        client.post(
            "/api/v1/relances/schedule",
            json={"invoice_id": draft_invoice_rel.id, "scheduled_at": future_dt()},
            headers=auth_headers_admin,
        )
        resp = client.get(
            f"/api/v1/relances?customer_id={customer_rel.id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 1
        assert all(r["invoice_id"] == draft_invoice_rel.id for r in data["items"])

    def test_list_customer_filter_returns_empty_for_unknown(
        self, client: TestClient, auth_headers_real: dict
    ):
        resp = client.get("/api/v1/relances?customer_id=99999", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# POST /relances/schedule
# ---------------------------------------------------------------------------

class TestScheduleRelance:
    def test_schedule_nominal(
        self, client: TestClient, auth_headers_admin: dict, draft_invoice_rel: Invoice
    ):
        resp = client.post(
            "/api/v1/relances/schedule",
            json={"invoice_id": draft_invoice_rel.id, "scheduled_at": future_dt(2), "channel": "email"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "scheduled"
        assert data["channel"] == "email"
        assert data["invoice_id"] == draft_invoice_rel.id
        assert data["sent_at"] is None
        assert data["cancelled_at"] is None

    def test_schedule_sms_channel(
        self, client: TestClient, auth_headers_admin: dict, draft_invoice_rel: Invoice
    ):
        resp = client.post(
            "/api/v1/relances/schedule",
            json={"invoice_id": draft_invoice_rel.id, "scheduled_at": future_dt(3), "channel": "sms"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201
        assert resp.json()["channel"] == "sms"

    def test_schedule_push_channel(
        self, client: TestClient, auth_headers_admin: dict, draft_invoice_rel: Invoice
    ):
        resp = client.post(
            "/api/v1/relances/schedule",
            json={"invoice_id": draft_invoice_rel.id, "scheduled_at": future_dt(4), "channel": "push"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201
        assert resp.json()["channel"] == "push"

    def test_schedule_past_date_rejected(
        self, client: TestClient, auth_headers_admin: dict, draft_invoice_rel: Invoice
    ):
        resp = client.post(
            "/api/v1/relances/schedule",
            json={"invoice_id": draft_invoice_rel.id, "scheduled_at": past_dt()},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]  # rejet d'une date passée confirmé

    def test_schedule_invoice_not_found(
        self, client: TestClient, auth_headers_admin: dict
    ):
        resp = client.post(
            "/api/v1/relances/schedule",
            json={"invoice_id": 99999, "scheduled_at": future_dt()},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 404

    def test_schedule_invalid_channel(
        self, client: TestClient, auth_headers_admin: dict, draft_invoice_rel: Invoice
    ):
        resp = client.post(
            "/api/v1/relances/schedule",
            json={"invoice_id": draft_invoice_rel.id, "scheduled_at": future_dt(), "channel": "fax"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 422

    def test_schedule_multiple_relances_same_invoice(
        self, client: TestClient, auth_headers_admin: dict, draft_invoice_rel: Invoice
    ):
        """Plusieurs relances peuvent être planifiées sur la même facture."""
        for days in [1, 2, 3]:
            resp = client.post(
                "/api/v1/relances/schedule",
                json={"invoice_id": draft_invoice_rel.id, "scheduled_at": future_dt(days)},
                headers=auth_headers_admin,
            )
            assert resp.status_code == 201


# ---------------------------------------------------------------------------
# POST /relances/cancel/{relance_id}
# ---------------------------------------------------------------------------

class TestCancelRelance:
    def _schedule(self, client, headers, invoice_id, days=1):
        resp = client.post(
            "/api/v1/relances/schedule",
            json={"invoice_id": invoice_id, "scheduled_at": future_dt(days)},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_cancel_nominal(
        self, client: TestClient, auth_headers_admin: dict, draft_invoice_rel: Invoice
    ):
        rid = self._schedule(client, auth_headers_admin, draft_invoice_rel.id)
        resp = client.post(f"/api/v1/relances/cancel/{rid}", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["cancelled_at"] is not None

    def test_cancel_already_cancelled_400(
        self, client: TestClient, auth_headers_admin: dict, draft_invoice_rel: Invoice
    ):
        rid = self._schedule(client, auth_headers_admin, draft_invoice_rel.id)
        client.post(f"/api/v1/relances/cancel/{rid}", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/relances/cancel/{rid}", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_cancel_not_found(self, client: TestClient, auth_headers_admin: dict):
        resp = client.post("/api/v1/relances/cancel/99999", headers=auth_headers_admin)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /relances/mark-sent/{relance_id}
# ---------------------------------------------------------------------------

class TestMarkSentRelance:
    def _schedule(self, client, headers, invoice_id, days=1):
        resp = client.post(
            "/api/v1/relances/schedule",
            json={"invoice_id": invoice_id, "scheduled_at": future_dt(days)},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_mark_sent_nominal(
        self, client: TestClient, auth_headers_admin: dict, draft_invoice_rel: Invoice
    ):
        rid = self._schedule(client, auth_headers_admin, draft_invoice_rel.id)
        resp = client.post(f"/api/v1/relances/mark-sent/{rid}", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sent"
        assert data["sent_at"] is not None

    def test_mark_sent_already_sent_400(
        self, client: TestClient, auth_headers_admin: dict, draft_invoice_rel: Invoice
    ):
        rid = self._schedule(client, auth_headers_admin, draft_invoice_rel.id)
        client.post(f"/api/v1/relances/mark-sent/{rid}", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/relances/mark-sent/{rid}", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_mark_sent_cancelled_rejected(
        self, client: TestClient, auth_headers_admin: dict, draft_invoice_rel: Invoice
    ):
        rid = self._schedule(client, auth_headers_admin, draft_invoice_rel.id)
        client.post(f"/api/v1/relances/cancel/{rid}", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/relances/mark-sent/{rid}", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_mark_sent_not_found(self, client: TestClient, auth_headers_admin: dict):
        resp = client.post("/api/v1/relances/mark-sent/99999", headers=auth_headers_admin)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Anti cross-tenant
# ---------------------------------------------------------------------------

class TestRelancesTenantIsolation:
    def test_cannot_schedule_on_other_tenant_invoice(
        self,
        client: TestClient,
        auth_headers_admin_tenant2: dict,
        draft_invoice_rel: Invoice,
    ):
        """Tenant 2 ne peut pas planifier sur la facture du tenant 1."""
        resp = client.post(
            "/api/v1/relances/schedule",
            json={"invoice_id": draft_invoice_rel.id, "scheduled_at": future_dt()},
            headers=auth_headers_admin_tenant2,
        )
        assert resp.status_code == 404

    def test_cannot_cancel_other_tenant_relance(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_admin_tenant2: dict,
        draft_invoice_rel: Invoice,
    ):
        """Tenant 2 ne peut pas annuler la relance du tenant 1."""
        resp = client.post(
            "/api/v1/relances/schedule",
            json={"invoice_id": draft_invoice_rel.id, "scheduled_at": future_dt()},
            headers=auth_headers_admin,
        )
        rid = resp.json()["id"]

        resp_t2 = client.post(
            f"/api/v1/relances/cancel/{rid}", headers=auth_headers_admin_tenant2
        )
        assert resp_t2.status_code == 404

    def test_list_only_own_tenant_relances(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_tenant2: dict,
        draft_invoice_rel: Invoice,
    ):
        """Tenant 2 ne voit pas les relances du tenant 1."""
        client.post(
            "/api/v1/relances/schedule",
            json={"invoice_id": draft_invoice_rel.id, "scheduled_at": future_dt()},
            headers=auth_headers_admin,
        )
        resp_t2 = client.get("/api/v1/relances", headers=auth_headers_tenant2)
        assert resp_t2.status_code == 200
        # Tenant 2 ne voit aucune relance du tenant 1
        ids = [r["id"] for r in resp_t2.json()["items"]]
        resp_t1 = client.get("/api/v1/relances", headers=auth_headers_admin)
        t1_ids = [r["id"] for r in resp_t1.json()["items"]]
        assert not any(i in t1_ids for i in ids)
