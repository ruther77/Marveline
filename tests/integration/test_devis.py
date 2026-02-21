"""Tests d'intégration — Module Devis (CRUD + transitions + cross-tenant)."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.models.customer import Customer
from app.constants import CustomerType, DevisStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def customer_dev(test_db):
    c = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Alice",
        last_name="Devis",
        email="alice.devis@example.com",
        phone="+33600000050",
        city="Paris",
        postal_code="75001",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def customer_dev_t2(test_db):
    c = Customer(
        tenant_id=2,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Bob",
        last_name="Tenant2",
        email="bob.devis.t2@example.com",
        phone="+33600000051",
        city="Lyon",
        postal_code="69001",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


def _devis_payload(customer_id: int) -> dict:
    return {
        "customer_id": customer_id,
        "valid_until": (date.today() + timedelta(days=30)).isoformat(),
        "tva_rate": 2000,
        "lines": [
            {
                "label": "Location salle",
                "quantity": 1,
                "unit_price_cents": 50000,
                "discount_pct": 0,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Tests CRUD basiques
# ---------------------------------------------------------------------------

class TestDevisCRUD:
    def test_create_devis_201(self, client: TestClient, auth_headers_real: dict, customer_dev):
        payload = _devis_payload(customer_dev.id)
        resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_real)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == DevisStatus.DRAFT
        assert data["reference"].startswith("DEV-")
        assert data["total_cents"] == 60000  # 50000 HT + 20% TVA = 60000
        assert data["subtotal_cents"] == 50000
        assert data["tva_cents"] == 10000
        assert len(data["lines"]) == 1
        assert data["customer_name"] == "Alice Devis"

    def test_get_devis_200(self, client: TestClient, auth_headers_real: dict, customer_dev):
        payload = _devis_payload(customer_dev.id)
        create_resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_real)
        devis_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["id"] == devis_id

    def test_list_devis_200(self, client: TestClient, auth_headers_real: dict, customer_dev):
        payload = _devis_payload(customer_dev.id)
        client.post("/api/v1/devis", json=payload, headers=auth_headers_real)

        resp = client.get("/api/v1/devis", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_update_devis_draft_200(self, client: TestClient, auth_headers_real: dict, customer_dev):
        payload = _devis_payload(customer_dev.id)
        create_resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_real)
        devis_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/devis/{devis_id}",
            json={"notes": "Note mise à jour"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Note mise à jour"

    def test_get_devis_404(self, client: TestClient, auth_headers_real: dict):
        resp = client.get("/api/v1/devis/999999", headers=auth_headers_real)
        assert resp.status_code == 404

    def test_reference_format(self, client: TestClient, auth_headers_real: dict, customer_dev):
        """La référence doit être DEV-YYYY-NNNN."""
        payload = _devis_payload(customer_dev.id)
        resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_real)
        ref = resp.json()["reference"]
        year = date.today().year
        assert ref.startswith(f"DEV-{year}-")


# ---------------------------------------------------------------------------
# Tests transitions d'état
# ---------------------------------------------------------------------------

class TestDevisTransitions:
    def _create(self, client, headers, customer_id):
        payload = _devis_payload(customer_id)
        resp = client.post("/api/v1/devis", json=payload, headers=headers)
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_send_draft_to_sent(self, client: TestClient, auth_headers_real: dict, customer_dev):
        devis_id = self._create(client, auth_headers_real, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == DevisStatus.SENT
        # Version snapshot v1 créé
        versions = client.get(f"/api/v1/devis/{devis_id}/versions", headers=auth_headers_real)
        assert len(versions.json()) == 1

    def test_accept_sent_devis(self, client: TestClient, auth_headers_real: dict, customer_dev):
        devis_id = self._create(client, auth_headers_real, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_real)
        resp = client.post(f"/api/v1/devis/{devis_id}/accept", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["status"] == DevisStatus.ACCEPTED

    def test_refuse_sent_devis(self, client: TestClient, auth_headers_real: dict, customer_dev):
        devis_id = self._create(client, auth_headers_real, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_real)
        resp = client.post(f"/api/v1/devis/{devis_id}/refuse", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["status"] == DevisStatus.REFUSED

    def test_cancel_draft_devis(self, client: TestClient, auth_headers_real: dict, customer_dev):
        devis_id = self._create(client, auth_headers_real, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{devis_id}/cancel", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["status"] == DevisStatus.CANCELLED

    def test_invalid_transition_refused_to_sent(self, client: TestClient, auth_headers_real: dict, customer_dev):
        devis_id = self._create(client, auth_headers_real, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_real)
        client.post(f"/api/v1/devis/{devis_id}/refuse", headers=auth_headers_real)
        # Tenter d'envoyer un devis refusé → 400
        resp = client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_real)
        assert resp.status_code == 400

    def test_negotiation_requires_negotiation_status(self, client: TestClient, auth_headers_real: dict, customer_dev):
        devis_id = self._create(client, auth_headers_real, customer_dev.id)
        # En draft — pas en négociation → 400
        resp = client.post(
            f"/api/v1/devis/{devis_id}/negotiation",
            json={"message": "Je voudrais une remise"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests isolation cross-tenant
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

import importlib.util as _ilu

_weasyprint_available = pytest.mark.skipif(
    _ilu.find_spec("weasyprint") is None,
    reason="weasyprint non installé",
)


class TestDevisPDF:
    def _create(self, client, headers, customer_id):
        return client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers).json()["id"]

    @_weasyprint_available
    def test_pdf_returns_pdf(self, client: TestClient, auth_headers_real: dict, customer_dev):
        devis_id = self._create(client, auth_headers_real, customer_dev.id)
        resp = client.get(f"/api/v1/devis/{devis_id}/pdf", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert len(resp.content) > 100

    def test_pdf_404(self, client: TestClient, auth_headers_real: dict):
        resp = client.get("/api/v1/devis/999999/pdf", headers=auth_headers_real)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Duplicate
# ---------------------------------------------------------------------------

class TestDevisDuplicate:
    def _create(self, client, headers, customer_id):
        return client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers).json()

    def test_duplicate_creates_draft(self, client: TestClient, auth_headers_real: dict, customer_dev):
        original = self._create(client, auth_headers_real, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{original['id']}/duplicate", headers=auth_headers_real)
        assert resp.status_code == 201
        dup = resp.json()
        assert dup["status"] == "draft"
        assert dup["id"] != original["id"]
        assert dup["reference"] != original["reference"]
        assert dup["customer_id"] == original["customer_id"]

    def test_duplicate_copies_lines(self, client: TestClient, auth_headers_real: dict, customer_dev):
        original = self._create(client, auth_headers_real, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{original['id']}/duplicate", headers=auth_headers_real)
        assert resp.status_code == 201
        dup = resp.json()
        assert len(dup.get("lines", [])) == len(original.get("lines", []))

    def test_duplicate_404(self, client: TestClient, auth_headers_real: dict):
        resp = client.post("/api/v1/devis/999999/duplicate", headers=auth_headers_real)
        assert resp.status_code == 404

    def test_duplicate_cross_tenant_404(
        self, client: TestClient, auth_headers_real: dict, auth_headers_tenant2: dict, customer_dev
    ):
        original = self._create(client, auth_headers_real, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{original['id']}/duplicate", headers=auth_headers_tenant2)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests isolation cross-tenant
# ---------------------------------------------------------------------------

class TestDevisCrossTenant:
    def test_cannot_access_other_tenant_devis(
        self,
        client: TestClient,
        auth_headers_real: dict,
        auth_headers_tenant2: dict,
        customer_dev: Customer,
    ):
        """Un utilisateur tenant1 ne peut pas lire un devis tenant2."""
        payload = _devis_payload(customer_dev.id)
        # Créer devis dans tenant1
        resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_real)
        assert resp.status_code == 201
        devis_id = resp.json()["id"]

        # Tenter de lire depuis tenant2 → 404
        resp2 = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_tenant2)
        assert resp2.status_code == 404

    def test_cannot_send_other_tenant_devis(
        self,
        client: TestClient,
        auth_headers_real: dict,
        auth_headers_tenant2: dict,
        customer_dev: Customer,
    ):
        """Un utilisateur tenant2 ne peut pas transiter un devis tenant1."""
        payload = _devis_payload(customer_dev.id)
        resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_real)
        devis_id = resp.json()["id"]

        resp2 = client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_tenant2)
        assert resp2.status_code == 404
