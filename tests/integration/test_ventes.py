"""Tests d'intégration — Module Ventes."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.models.customer import Customer
from app.constants import CustomerType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def customer_vte(test_db):
    c = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Alice",
        last_name="Vente",
        email="alice.vente@example.com",
        phone="+33600000099",
        city="Paris",
        postal_code="75001",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def customer_vte_t2(test_db):
    c = Customer(
        tenant_id=2,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Bob",
        last_name="Tenant2",
        email="bob.vte.t2@example.com",
        phone="+33600000098",
        city="Lyon",
        postal_code="69001",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


def _vente_payload(customer_id: int) -> dict:
    return {
        "customer_id": customer_id,
        "deposit_pct": 30,
        "payment_due_date": (date.today() + timedelta(days=30)).isoformat(),
        "notes": "Vente test",
        "lines": [
            {"label": "Chaise dorée", "quantity": 10, "unit_price_cents": 500},
            {"label": "Table ronde", "quantity": 2, "unit_price_cents": 2000},
        ],
    }


# ---------------------------------------------------------------------------
# CRUD nominal
# ---------------------------------------------------------------------------

class TestVenteCRUD:
    def test_create_vente_201(self, client: TestClient, auth_headers_real, customer_vte):
        resp = client.post("/api/v1/ventes", json=_vente_payload(customer_vte.id), headers=auth_headers_real)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reference"].startswith("VTE-")
        assert data["status"] == "draft"
        assert len(data["lines"]) == 2
        # Vérifier calcul total HT + TVA 20%
        subtotal = 10 * 500 + 2 * 2000
        tva = int(subtotal * 0.20)
        assert data["subtotal_cents"] == subtotal
        assert data["tva_cents"] == tva
        assert data["total_cents"] == subtotal + tva

    def test_list_ventes(self, client: TestClient, auth_headers_real, customer_vte):
        client.post("/api/v1/ventes", json=_vente_payload(customer_vte.id), headers=auth_headers_real)
        resp = client.get("/api/v1/ventes", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_get_vente(self, client: TestClient, auth_headers_real, customer_vte):
        created = client.post("/api/v1/ventes", json=_vente_payload(customer_vte.id), headers=auth_headers_real).json()
        resp = client.get(f"/api/v1/ventes/{created['id']}", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_vente_404(self, client: TestClient, auth_headers_real):
        resp = client.get("/api/v1/ventes/999999", headers=auth_headers_real)
        assert resp.status_code == 404

    def test_update_vente(self, client: TestClient, auth_headers_real, customer_vte):
        created = client.post("/api/v1/ventes", json=_vente_payload(customer_vte.id), headers=auth_headers_real).json()
        resp = client.patch(
            f"/api/v1/ventes/{created['id']}",
            json={"notes": "Modifié"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Modifié"


# ---------------------------------------------------------------------------
# Paiements
# ---------------------------------------------------------------------------

class TestVentePayments:
    def _create(self, client, headers, customer_id):
        return client.post("/api/v1/ventes", json=_vente_payload(customer_id), headers=headers).json()

    def test_add_payment_201(self, client: TestClient, auth_headers_real, customer_vte):
        vente = self._create(client, auth_headers_real, customer_vte.id)
        resp = client.post(
            f"/api/v1/ventes/{vente['id']}/payments",
            json={
                "amount_cents": 2000,
                "payment_method": "card",
                "payment_date": date.today().isoformat(),
                "is_deposit": True,
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 201
        assert resp.json()["amount_cents"] == 2000
        assert resp.json()["is_deposit"] is True

    def test_add_payment_updates_paid_cents(self, client: TestClient, auth_headers_real, customer_vte):
        vente = self._create(client, auth_headers_real, customer_vte.id)
        client.post(
            f"/api/v1/ventes/{vente['id']}/payments",
            json={"amount_cents": 1000, "payment_method": "cash", "payment_date": date.today().isoformat()},
            headers=auth_headers_real,
        )
        detail = client.get(f"/api/v1/ventes/{vente['id']}", headers=auth_headers_real).json()
        assert detail["paid_cents"] == 1000

    def test_list_payments(self, client: TestClient, auth_headers_real, customer_vte):
        vente = self._create(client, auth_headers_real, customer_vte.id)
        client.post(
            f"/api/v1/ventes/{vente['id']}/payments",
            json={"amount_cents": 500, "payment_method": "transfer", "payment_date": date.today().isoformat()},
            headers=auth_headers_real,
        )
        resp = client.get(f"/api/v1/ventes/{vente['id']}/payments", headers=auth_headers_real)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_full_payment_sets_status_fully_paid(self, client: TestClient, auth_headers_real, customer_vte):
        """Payer le montant total déclenche la transition → fully_paid."""
        vente = self._create(client, auth_headers_real, customer_vte.id)
        total = vente["total_cents"]
        client.post(
            f"/api/v1/ventes/{vente['id']}/payments",
            json={"amount_cents": total, "payment_method": "card", "payment_date": date.today().isoformat()},
            headers=auth_headers_real,
        )
        detail = client.get(f"/api/v1/ventes/{vente['id']}", headers=auth_headers_real).json()
        assert detail["status"] == "fully_paid"


# ---------------------------------------------------------------------------
# Remboursement
# ---------------------------------------------------------------------------

class TestVenteRefund:
    def test_refund_201(self, client: TestClient, auth_headers_real, customer_vte):
        vente = client.post("/api/v1/ventes", json=_vente_payload(customer_vte.id), headers=auth_headers_real).json()
        resp = client.post(f"/api/v1/ventes/{vente['id']}/refund", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["status"] == "refunded"

    def test_double_refund_400(self, client: TestClient, auth_headers_real, customer_vte):
        vente = client.post("/api/v1/ventes", json=_vente_payload(customer_vte.id), headers=auth_headers_real).json()
        client.post(f"/api/v1/ventes/{vente['id']}/refund", headers=auth_headers_real)
        resp = client.post(f"/api/v1/ventes/{vente['id']}/refund", headers=auth_headers_real)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Overdue
# ---------------------------------------------------------------------------

class TestVenteOverdue:
    def test_list_overdue(self, client: TestClient, auth_headers_real):
        resp = client.get("/api/v1/ventes/overdue", headers=auth_headers_real)
        assert resp.status_code == 200
        assert "items" in resp.json()


# ---------------------------------------------------------------------------
# Anti cross-tenant
# ---------------------------------------------------------------------------

class TestVenteCrossTenant:
    def test_cross_tenant_404(self, client: TestClient, auth_headers_real, customer_vte_t2, auth_headers_tenant2):
        # Créer vente dans tenant2
        vente_t2 = client.post(
            "/api/v1/ventes",
            json=_vente_payload(customer_vte_t2.id),
            headers=auth_headers_tenant2,
        ).json()
        # Accéder depuis tenant1
        resp = client.get(f"/api/v1/ventes/{vente_t2['id']}", headers=auth_headers_real)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

class TestVenteCancel:
    def test_cancel_draft_ok(self, client: TestClient, auth_headers_real, customer_vte):
        vente = client.post("/api/v1/ventes", json=_vente_payload(customer_vte.id), headers=auth_headers_real).json()
        resp = client.post(f"/api/v1/ventes/{vente['id']}/cancel", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_pending_ok(self, client: TestClient, auth_headers_real, customer_vte):
        vente = client.post("/api/v1/ventes", json=_vente_payload(customer_vte.id), headers=auth_headers_real).json()
        client.post(
            f"/api/v1/ventes/{vente['id']}/payments",
            json={"amount_cents": 500, "payment_method": "cash", "payment_date": date.today().isoformat(), "is_deposit": False},
            headers=auth_headers_real,
        )
        resp = client.post(f"/api/v1/ventes/{vente['id']}/cancel", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_fully_paid_400(self, client: TestClient, auth_headers_real, customer_vte):
        """Une vente fully_paid ne peut pas être annulée."""
        vente = client.post("/api/v1/ventes", json=_vente_payload(customer_vte.id), headers=auth_headers_real).json()
        total = vente["total_cents"]
        client.post(
            f"/api/v1/ventes/{vente['id']}/payments",
            json={"amount_cents": total, "payment_method": "card", "payment_date": date.today().isoformat(), "is_deposit": False},
            headers=auth_headers_real,
        )
        resp = client.post(f"/api/v1/ventes/{vente['id']}/cancel", headers=auth_headers_real)
        assert resp.status_code == 400

    def test_cancel_404(self, client: TestClient, auth_headers_real):
        resp = client.post("/api/v1/ventes/999999/cancel", headers=auth_headers_real)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

import importlib.util as _ilu

weasyprint_available = pytest.mark.skipif(
    _ilu.find_spec("weasyprint") is None,
    reason="weasyprint non installé",
)


class TestVentePDF:
    @weasyprint_available
    def test_pdf_returns_pdf(self, client: TestClient, auth_headers_real, customer_vte):
        vente = client.post("/api/v1/ventes", json=_vente_payload(customer_vte.id), headers=auth_headers_real).json()
        resp = client.get(f"/api/v1/ventes/{vente['id']}/pdf", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert len(resp.content) > 100

    def test_pdf_404(self, client: TestClient, auth_headers_real):
        resp = client.get("/api/v1/ventes/999999/pdf", headers=auth_headers_real)
        assert resp.status_code == 404
