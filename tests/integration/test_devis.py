"""Tests d'intégration — Module Devis (CRUD + transitions + cross-tenant)."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.models.bundle import ProductBundle
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


@pytest.fixture
def bundle_dev(test_db):
    b = ProductBundle(
        tenant_id=1,
        name="Pack Test Devis",
        slug="pack-test-devis",
        bundle_price_cents=15000,
        cleaning_fee_cents=0,
        featured=False,
        display_order=0,
    )
    test_db.add(b)
    test_db.commit()
    test_db.refresh(b)
    return b


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
    def test_create_devis_201(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        payload = _devis_payload(customer_dev.id)
        resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == DevisStatus.DRAFT
        assert data["reference"].startswith("DEV-")
        assert data["total_cents"] == 60000  # 50000 HT + 20% TVA = 60000
        assert data["subtotal_cents"] == 50000
        assert data["tva_cents"] == 10000
        assert len(data["lines"]) == 1
        assert data["customer_name"] == "Alice Devis"

    def test_get_devis_200(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        payload = _devis_payload(customer_dev.id)
        create_resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_admin)
        devis_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json()["id"] == devis_id

    def test_list_devis_200(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        payload = _devis_payload(customer_dev.id)
        client.post("/api/v1/devis", json=payload, headers=auth_headers_admin)

        resp = client.get("/api/v1/devis", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_update_devis_draft_200(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        payload = _devis_payload(customer_dev.id)
        create_resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_admin)
        devis_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/devis/{devis_id}",
            json={"notes": "Note mise à jour"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Note mise à jour"

    def test_update_devis_replaces_lines_and_recalculates_totals(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, bundle_dev
    ):
        payload = _devis_payload(customer_dev.id)
        create_resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_admin)
        devis_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/devis/{devis_id}",
            json={
                "discount_pct": 1000,  # 10%
                "lines": [
                    {
                        "label": "Pack bundle",
                        "bundle_id": bundle_dev.id,
                        "quantity": 2,
                        "unit_price_cents": 10000,
                        "discount_pct": 0,
                    },
                    {
                        "label": "Ligne libre remisée",
                        "quantity": 1,
                        "unit_price_cents": 20000,
                        "discount_pct": 500,  # 5%
                    },
                ],
            },
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["lines"]) == 2
        assert data["lines"][0]["bundle_id"] == bundle_dev.id
        assert data["lines"][1]["bundle_id"] is None
        assert data["lines"][1]["product_id"] is None
        assert data["subtotal_cents"] == 35100
        assert data["tva_cents"] == 7020
        assert data["total_cents"] == 42120

    def test_create_devis_response_includes_bundle_id(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, bundle_dev
    ):
        payload = {
            **_devis_payload(customer_dev.id),
            "lines": [
                {
                    "label": "Pack bundle",
                    "bundle_id": bundle_dev.id,
                    "quantity": 1,
                    "unit_price_cents": 15000,
                    "discount_pct": 0,
                }
            ],
        }
        resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 201, resp.text
        assert resp.json()["lines"][0]["bundle_id"] == bundle_dev.id

    def test_update_devis_preserves_bundle_ref_when_payload_omits_it(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, bundle_dev
    ):
        create_payload = {
            **_devis_payload(customer_dev.id),
            "lines": [
                {
                    "label": "Pack bundle",
                    "bundle_id": bundle_dev.id,
                    "quantity": 1,
                    "unit_price_cents": 15000,
                    "discount_pct": 0,
                }
            ],
        }
        create_resp = client.post("/api/v1/devis", json=create_payload, headers=auth_headers_admin)
        assert create_resp.status_code == 201, create_resp.text
        devis_id = create_resp.json()["id"]

        # Simule le payload actuel de DevisEditPage: pas de bundle_id pour une ligne bundle.
        resp = client.patch(
            f"/api/v1/devis/{devis_id}",
            json={
                "lines": [
                    {
                        "label": "Pack bundle (modifié)",
                        "quantity": 1,
                        "unit_price_cents": 16000,
                        "discount_pct": 0,
                    }
                ]
            },
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200, resp.text
        line = resp.json()["lines"][0]
        assert line["bundle_id"] == bundle_dev.id
        assert line["product_id"] is None

    def test_get_devis_404(self, client: TestClient, auth_headers_admin: dict):
        resp = client.get("/api/v1/devis/999999", headers=auth_headers_admin)
        assert resp.status_code == 404

    def test_reference_format(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        """La référence doit être DEV-YYYY-NNNN."""
        payload = _devis_payload(customer_dev.id)
        resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_admin)
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

    def test_send_draft_to_sent(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == DevisStatus.SENT
        # Version snapshot v1 créé
        versions = client.get(f"/api/v1/devis/{devis_id}/versions", headers=auth_headers_admin)
        assert len(versions.json()) == 1

    def test_accept_sent_devis(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/accept", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json()["status"] == DevisStatus.ACCEPTED

    def test_start_negotiation_sent_devis(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json()["status"] == DevisStatus.NEGOTIATION

    def test_mark_version_pending_from_negotiation(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/version-pending", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json()["status"] == DevisStatus.VERSION_PENDING

    def test_resume_negotiation_from_version_pending(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/version-pending", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json()["status"] == DevisStatus.NEGOTIATION

    def test_refuse_sent_devis(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/refuse", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json()["status"] == DevisStatus.REFUSED

    def test_cancel_draft_devis(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{devis_id}/cancel", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json()["status"] == DevisStatus.CANCELLED

    def test_invalid_transition_refused_to_sent(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/refuse", headers=auth_headers_admin)
        # Tenter d'envoyer un devis refusé → 400
        resp = client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_negotiation_requires_negotiation_status(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        # En draft — pas en négociation → 400
        resp = client.post(
            f"/api/v1/devis/{devis_id}/negotiation",
            json={"message": "Je voudrais une remise"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400


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
    def test_pdf_returns_pdf(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        resp = client.get(f"/api/v1/devis/{devis_id}/pdf", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert len(resp.content) > 100

    def test_pdf_404(self, client: TestClient, auth_headers_admin: dict):
        resp = client.get("/api/v1/devis/999999/pdf", headers=auth_headers_admin)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Duplicate
# ---------------------------------------------------------------------------

class TestDevisDuplicate:
    def _create(self, client, headers, customer_id):
        return client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers).json()

    def test_duplicate_creates_draft(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        original = self._create(client, auth_headers_admin, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{original['id']}/duplicate", headers=auth_headers_admin)
        assert resp.status_code == 201
        dup = resp.json()
        assert dup["status"] == "draft"
        assert dup["id"] != original["id"]
        assert dup["reference"] != original["reference"]
        assert dup["customer_id"] == original["customer_id"]

    def test_duplicate_copies_lines(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        original = self._create(client, auth_headers_admin, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{original['id']}/duplicate", headers=auth_headers_admin)
        assert resp.status_code == 201
        dup = resp.json()
        assert len(dup.get("lines", [])) == len(original.get("lines", []))

    def test_duplicate_404(self, client: TestClient, auth_headers_admin: dict):
        resp = client.post("/api/v1/devis/999999/duplicate", headers=auth_headers_admin)
        assert resp.status_code == 404

    def test_duplicate_cross_tenant_404(
        self, client: TestClient, auth_headers_admin: dict, auth_headers_admin_tenant2: dict, customer_dev
    ):
        original = self._create(client, auth_headers_admin, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{original['id']}/duplicate", headers=auth_headers_admin_tenant2)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests isolation cross-tenant
# ---------------------------------------------------------------------------

class TestDevisCrossTenant:
    def test_cannot_access_other_tenant_devis(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_admin_tenant2: dict,
        customer_dev: Customer,
    ):
        """Un utilisateur tenant1 ne peut pas lire un devis tenant2."""
        payload = _devis_payload(customer_dev.id)
        # Créer devis dans tenant1
        resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 201
        devis_id = resp.json()["id"]

        # Tenter de lire depuis tenant2 → 404
        resp2 = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin_tenant2)
        assert resp2.status_code == 404

    def test_cannot_send_other_tenant_devis(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_admin_tenant2: dict,
        customer_dev: Customer,
    ):
        """Un utilisateur tenant2 ne peut pas transiter un devis tenant1."""
        payload = _devis_payload(customer_dev.id)
        resp = client.post("/api/v1/devis", json=payload, headers=auth_headers_admin)
        devis_id = resp.json()["id"]

        resp2 = client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin_tenant2)
        assert resp2.status_code == 404


# ---------------------------------------------------------------------------
# Signature électronique
# ---------------------------------------------------------------------------

class TestDevisSignature:
    def _create_and_send(self, client, headers, customer_id):
        devis = client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers).json()
        client.post(f"/api/v1/devis/{devis['id']}/send", headers=headers)
        return devis["id"]

    def test_signature_nominal(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        """Signer un devis 'sent' → signed_at non null, signature_url non vide."""
        devis_id = self._create_and_send(client, auth_headers_admin, customer_dev.id)
        resp = client.post(
            f"/api/v1/devis/{devis_id}/signature",
            json={"signature_data": "data:image/png;base64,iVBORw0KGgo="},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == devis_id
        assert data["signature_url"] is not None
        assert data["signed_at"] is not None

    def test_signature_draft_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        """Signer un devis 'draft' → 400."""
        devis = client.post("/api/v1/devis", json=_devis_payload(customer_dev.id), headers=auth_headers_admin).json()
        resp = client.post(
            f"/api/v1/devis/{devis['id']}/signature",
            json={"signature_data": "data:image/png;base64,iVBORw0KGgo="},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400

    def test_signature_cross_tenant_404(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_admin_tenant2: dict,
        customer_dev,
    ):
        """Un tenant2 ne peut pas signer un devis tenant1."""
        devis_id = self._create_and_send(client, auth_headers_admin, customer_dev.id)
        resp = client.post(
            f"/api/v1/devis/{devis_id}/signature",
            json={"signature_data": "data:image/png;base64,iVBORw0KGgo="},
            headers=auth_headers_admin_tenant2,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET listes : change-requests, modules, phases
# ---------------------------------------------------------------------------

class TestDevisGetLists:
    def _create_devis(self, client, headers, customer_id):
        resp = client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers)
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_list_change_requests_empty(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        resp = client.get(f"/api/v1/devis/{devis_id}/change-requests", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_change_requests_after_create(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        client.post(
            f"/api/v1/devis/{devis_id}/change-request",
            json={"description": "Ajouter une table ronde"},
            headers=auth_headers_admin,
        )
        resp = client.get(f"/api/v1/devis/{devis_id}/change-requests", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["description"] == "Ajouter une table ronde"
        assert data[0]["status"] == "pending"

    def test_list_modules_empty(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        resp = client.get(f"/api/v1/devis/{devis_id}/modules", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_modules_after_add(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        client.post(
            f"/api/v1/devis/{devis_id}/modules",
            json={"module_type": "socle", "label": "Module A", "content_json": {}},
            headers=auth_headers_admin,
        )
        resp = client.get(f"/api/v1/devis/{devis_id}/modules", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["label"] == "Module A"

    def test_list_phases_empty(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        resp = client.get(f"/api/v1/devis/{devis_id}/phases", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_phases_after_add(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        from datetime import date, timedelta
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        today = date.today()
        client.post(
            f"/api/v1/devis/{devis_id}/phases",
            json={
                "label": "Phase 1",
                "date_start": today.isoformat(),
                "date_end": (today + timedelta(days=7)).isoformat(),
                "sort_order": 1,
            },
            headers=auth_headers_admin,
        )
        resp = client.get(f"/api/v1/devis/{devis_id}/phases", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["label"] == "Phase 1"

    def test_list_change_requests_404_unknown_devis(self, client: TestClient, auth_headers_admin: dict):
        resp = client.get("/api/v1/devis/99999/change-requests", headers=auth_headers_admin)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests Coverage (P2-21)
# ---------------------------------------------------------------------------

class TestDevisCoverage:
    def test_coverage_empty_devis(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        """GET /devis/{id}/coverage retourne la structure complète pour un devis sans modules ni phases."""
        payload = _devis_payload(customer_dev.id)
        r = client.post("/api/v1/devis", json=payload, headers=auth_headers_admin)
        assert r.status_code == 201
        devis_id = r.json()["id"]

        resp = client.get(f"/api/v1/devis/{devis_id}/coverage", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["devis_id"] == devis_id
        assert data["reference"].startswith("DEV-")
        assert data["total_modules"] == 0
        assert data["active_modules"] == 0
        assert data["module_types"] == []
        assert data["total_phases"] == 0
        assert data["phase_completion_pct"] == 0
        assert data["total_lines"] == 1
        assert data["subtotal_cents"] == 50000

    def test_coverage_with_modules_and_phases(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        """GET /devis/{id}/coverage tient compte des modules actifs et de la progression des phases."""
        payload = _devis_payload(customer_dev.id)
        r = client.post("/api/v1/devis", json=payload, headers=auth_headers_admin)
        devis_id = r.json()["id"]

        # Ajouter un module
        client.post(
            f"/api/v1/devis/{devis_id}/modules",
            json={"module_type": "socle", "label": "Module socle", "content_json": {}},
            headers=auth_headers_admin,
        )

        # Ajouter une phase passée
        past = date.today() - timedelta(days=10)
        client.post(
            f"/api/v1/devis/{devis_id}/phases",
            json={
                "label": "Phase passée",
                "date_start": (past - timedelta(days=5)).isoformat(),
                "date_end": (past).isoformat(),
                "sort_order": 1,
            },
            headers=auth_headers_admin,
        )

        resp = client.get(f"/api/v1/devis/{devis_id}/coverage", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_modules"] == 1
        assert data["active_modules"] == 1
        assert "socle" in data["module_types"]
        assert data["total_phases"] == 1
        assert data["phases_past"] == 1
        assert data["phase_completion_pct"] == 100

    def test_coverage_not_found(self, client: TestClient, auth_headers_admin: dict):
        resp = client.get("/api/v1/devis/99999/coverage", headers=auth_headers_admin)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Helper — forçage de statut via DB (bypass guards HTTP)
# ---------------------------------------------------------------------------

def _force_status(test_db, devis_id: int, new_status: str) -> None:
    """Force le statut d'un devis directement en DB (contourne les gardes HTTP)."""
    from app.models.devis import Devis as DevisModel
    devis = test_db.get(DevisModel, devis_id)
    assert devis is not None, f"Devis {devis_id} introuvable"
    devis.status = new_status
    test_db.commit()


def _devis_bundle_payload(customer_id: int, bundle_id: int) -> dict:
    """Devis avec une ligne bundle (nécessaire pour convert_to_reservation)."""
    return {
        "customer_id": customer_id,
        "valid_until": (date.today() + timedelta(days=30)).isoformat(),
        "tva_rate": 2000,
        "lines": [
            {
                "label": "Pack bundle",
                "bundle_id": bundle_id,
                "quantity": 1,
                "unit_price_cents": 15000,
                "discount_pct": 0,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Tests allowed_actions par statut
# ---------------------------------------------------------------------------

class TestDevisAllowedActions:
    """Vérifie que allowed_actions reflète exactement STATUS_ALLOWED_ACTIONS pour chaque statut."""

    def _create(self, client, headers, customer_id):
        resp = client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers)
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_draft_allowed_actions(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        data = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin).json()
        assert set(data["allowed_actions"]) == {"send", "cancel"}

    def test_sent_allowed_actions(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        data = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin).json()
        assert set(data["allowed_actions"]) == {"start_negotiation", "accept", "refuse", "expire"}

    def test_negotiation_allowed_actions(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=auth_headers_admin)
        data = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin).json()
        assert set(data["allowed_actions"]) == {"accept", "refuse", "new_version", "expire"}

    def test_version_pending_allowed_actions(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/version-pending", headers=auth_headers_admin)
        data = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin).json()
        assert set(data["allowed_actions"]) == {"send", "back_to_negotiation", "accept", "refuse", "cancel"}

    def test_accepted_allowed_actions(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/accept", headers=auth_headers_admin)
        data = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin).json()
        assert set(data["allowed_actions"]) == {"convert", "cancel"}

    def test_refused_allowed_actions(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/refuse", headers=auth_headers_admin)
        data = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin).json()
        assert set(data["allowed_actions"]) == {"duplicate"}

    def test_expired_allowed_actions(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, test_db
    ):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        _force_status(test_db, devis_id, DevisStatus.EXPIRED)
        data = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin).json()
        assert set(data["allowed_actions"]) == {"renew"}

    def test_converted_allowed_actions(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, test_db
    ):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        _force_status(test_db, devis_id, DevisStatus.CONVERTED)
        data = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin).json()
        assert data["allowed_actions"] == []

    def test_cancelled_allowed_actions(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/cancel", headers=auth_headers_admin)
        data = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin).json()
        assert data["allowed_actions"] == []

    def test_allowed_actions_list_matches_detail(
        self, client: TestClient, auth_headers_admin: dict, customer_dev
    ):
        """allowed_actions dans la liste doit être identique au détail."""
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        detail = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin).json()
        listing = client.get("/api/v1/devis", headers=auth_headers_admin).json()
        item = next(i for i in listing["items"] if i["id"] == devis_id)
        assert set(item["allowed_actions"]) == set(detail["allowed_actions"])


# ---------------------------------------------------------------------------
# Tests matrice de transitions invalides
# ---------------------------------------------------------------------------

class TestDevisInvalidTransitions:
    """Vérifie que toutes les transitions non autorisées retournent 400."""

    def _create(self, client, headers, customer_id):
        resp = client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers)
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_send_from_cancelled_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/cancel", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_send_from_accepted_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/accept", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_accept_from_draft_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{devis_id}/accept", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_accept_from_cancelled_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/cancel", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/accept", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_refuse_from_draft_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{devis_id}/refuse", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_refuse_from_accepted_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/accept", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/refuse", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_cancel_from_converted_400(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, test_db
    ):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        _force_status(test_db, devis_id, DevisStatus.CONVERTED)
        resp = client.post(f"/api/v1/devis/{devis_id}/cancel", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_cancel_from_refused_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/refuse", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/cancel", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_cancel_from_sent_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        # SENT → [NEGOTIATION, ACCEPTED, REFUSED, EXPIRED] : pas CANCELLED
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/cancel", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_version_pending_from_draft_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{devis_id}/version-pending", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_version_pending_from_sent_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/version-pending", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_negotiation_start_from_draft_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_negotiation_start_from_accepted_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/accept", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_renew_from_draft_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{devis_id}/renew", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_renew_from_sent_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/renew", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_convert_from_draft_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        today = date.today()
        payload = {
            "delivery_date": (today + timedelta(days=10)).isoformat(),
            "return_date": (today + timedelta(days=12)).isoformat(),
        }
        resp = client.post(f"/api/v1/devis/{devis_id}/convert", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_convert_from_sent_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        today = date.today()
        payload = {
            "delivery_date": (today + timedelta(days=10)).isoformat(),
            "return_date": (today + timedelta(days=12)).isoformat(),
        }
        resp = client.post(f"/api/v1/devis/{devis_id}/convert", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests refuse avec raison
# ---------------------------------------------------------------------------

class TestDevisRefuseWithReason:
    def _create_and_send(self, client, headers, customer_id):
        devis_id = client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers).json()["id"]
        client.post(f"/api/v1/devis/{devis_id}/send", headers=headers)
        return devis_id

    def test_refuse_with_reason_persists(
        self, client: TestClient, auth_headers_admin: dict, customer_dev
    ):
        devis_id = self._create_and_send(client, auth_headers_admin, customer_dev.id)
        resp = client.post(
            f"/api/v1/devis/{devis_id}/refuse",
            json={"reason": "Budget insuffisant"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == DevisStatus.REFUSED
        assert data["refusal_reason"] == "Budget insuffisant"

    def test_refuse_without_reason_ok(
        self, client: TestClient, auth_headers_admin: dict, customer_dev
    ):
        devis_id = self._create_and_send(client, auth_headers_admin, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{devis_id}/refuse", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json()["refusal_reason"] is None

    def test_refusal_reason_persists_after_get(
        self, client: TestClient, auth_headers_admin: dict, customer_dev
    ):
        devis_id = self._create_and_send(client, auth_headers_admin, customer_dev.id)
        client.post(
            f"/api/v1/devis/{devis_id}/refuse",
            json={"reason": "Prix trop élevé"},
            headers=auth_headers_admin,
        )
        get_resp = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin)
        assert get_resp.status_code == 200
        assert get_resp.json()["refusal_reason"] == "Prix trop élevé"


# ---------------------------------------------------------------------------
# Tests conclude_negotiation
# ---------------------------------------------------------------------------

class TestDevisConcludeNegotiation:
    def _create_in_negotiation(self, client, headers, customer_id):
        devis_id = client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers).json()["id"]
        client.post(f"/api/v1/devis/{devis_id}/send", headers=headers)
        client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=headers)
        return devis_id

    def test_conclude_accepted(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_in_negotiation(client, auth_headers_admin, customer_dev.id)
        resp = client.post(
            f"/api/v1/devis/{devis_id}/negotiation/conclude",
            json={"outcome": "accepted"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == DevisStatus.ACCEPTED

    def test_conclude_refused_with_reason(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_in_negotiation(client, auth_headers_admin, customer_dev.id)
        resp = client.post(
            f"/api/v1/devis/{devis_id}/negotiation/conclude",
            json={"outcome": "refused", "reason": "Pas de budget"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == DevisStatus.REFUSED
        assert data["refusal_reason"] == "Pas de budget"

    def test_conclude_from_draft_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        """conclude depuis draft (pas en négociation) → 400."""
        devis_id = client.post("/api/v1/devis", json=_devis_payload(customer_dev.id), headers=auth_headers_admin).json()["id"]
        resp = client.post(
            f"/api/v1/devis/{devis_id}/negotiation/conclude",
            json={"outcome": "accepted"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400

    def test_conclude_invalid_outcome_422(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        """outcome hors pattern ^(accepted|refused)$ → 422."""
        devis_id = self._create_in_negotiation(client, auth_headers_admin, customer_dev.id)
        resp = client.post(
            f"/api/v1/devis/{devis_id}/negotiation/conclude",
            json={"outcome": "maybe"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests contraintes update / cancel
# ---------------------------------------------------------------------------

class TestDevisUpdateConstraints:
    def _create(self, client, headers, customer_id):
        resp = client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers)
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_update_sent_devis_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        resp = client.patch(
            f"/api/v1/devis/{devis_id}",
            json={"notes": "Essai de modification"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400

    def test_update_accepted_devis_400(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/accept", headers=auth_headers_admin)
        resp = client.patch(
            f"/api/v1/devis/{devis_id}",
            json={"notes": "Modification interdite"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400

    def test_cancel_accepted_devis_200(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        """ACCEPTED → CANCELLED est une transition valide."""
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/accept", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/cancel", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json()["status"] == DevisStatus.CANCELLED

    def test_cancel_version_pending_200(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        """VERSION_PENDING → CANCELLED est une transition valide."""
        devis_id = self._create(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/version-pending", headers=auth_headers_admin)
        resp = client.post(f"/api/v1/devis/{devis_id}/cancel", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json()["status"] == DevisStatus.CANCELLED

    def test_update_nonexistent_devis_404(self, client: TestClient, auth_headers_admin: dict):
        resp = client.patch("/api/v1/devis/999999", json={"notes": "x"}, headers=auth_headers_admin)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests renouvellement
# ---------------------------------------------------------------------------

class TestDevisRenew:
    def test_renew_from_expired_creates_new_draft(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, test_db
    ):
        devis_id = client.post("/api/v1/devis", json=_devis_payload(customer_dev.id), headers=auth_headers_admin).json()["id"]
        _force_status(test_db, devis_id, DevisStatus.EXPIRED)

        resp = client.post(f"/api/v1/devis/{devis_id}/renew", headers=auth_headers_admin)
        assert resp.status_code == 200, resp.text
        new_devis = resp.json()
        assert new_devis["status"] == DevisStatus.DRAFT
        assert new_devis["id"] != devis_id
        assert new_devis["reference"] != f"DEV-source-{devis_id}"

    def test_renew_source_stays_expired(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, test_db
    ):
        devis_id = client.post("/api/v1/devis", json=_devis_payload(customer_dev.id), headers=auth_headers_admin).json()["id"]
        _force_status(test_db, devis_id, DevisStatus.EXPIRED)
        client.post(f"/api/v1/devis/{devis_id}/renew", headers=auth_headers_admin)

        orig = client.get(f"/api/v1/devis/{devis_id}", headers=auth_headers_admin).json()
        assert orig["status"] == DevisStatus.EXPIRED

    def test_renew_copies_customer(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, test_db
    ):
        """La copie renew doit conserver le même customer_id."""
        payload = _devis_payload(customer_dev.id)
        devis_id = client.post("/api/v1/devis", json=payload, headers=auth_headers_admin).json()["id"]
        _force_status(test_db, devis_id, DevisStatus.EXPIRED)
        new_devis = client.post(f"/api/v1/devis/{devis_id}/renew", headers=auth_headers_admin).json()
        assert new_devis["customer_id"] == customer_dev.id


# ---------------------------------------------------------------------------
# Tests conversion en réservation
# ---------------------------------------------------------------------------

class TestDevisConvert:
    def _create_bundle_devis_and_accept(self, client, headers, customer_id, bundle_id, extra: dict = None):
        payload = _devis_bundle_payload(customer_id, bundle_id)
        if extra:
            payload.update(extra)
        devis_id = client.post("/api/v1/devis", json=payload, headers=headers).json()["id"]
        client.post(f"/api/v1/devis/{devis_id}/send", headers=headers)
        client.post(f"/api/v1/devis/{devis_id}/accept", headers=headers)
        return devis_id

    def test_convert_with_payload_dates_200(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, bundle_dev
    ):
        devis_id = self._create_bundle_devis_and_accept(
            client, auth_headers_admin, customer_dev.id, bundle_dev.id
        )
        today = date.today()
        convert_payload = {
            "delivery_date": (today + timedelta(days=10)).isoformat(),
            "return_date": (today + timedelta(days=12)).isoformat(),
        }
        resp = client.post(
            f"/api/v1/devis/{devis_id}/convert", json=convert_payload, headers=auth_headers_admin
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == DevisStatus.CONVERTED
        assert data["converted_reservation_id"] is not None

    def test_convert_uses_devis_dates_when_no_payload_dates(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, bundle_dev
    ):
        """Quand le devis a delivery_date + return_date et que le payload est vide,
        la conversion doit utiliser les dates du devis."""
        today = date.today()
        extra = {
            "delivery_date": (today + timedelta(days=5)).isoformat(),
            "return_date": (today + timedelta(days=7)).isoformat(),
        }
        devis_id = self._create_bundle_devis_and_accept(
            client, auth_headers_admin, customer_dev.id, bundle_dev.id, extra=extra
        )
        resp = client.post(
            f"/api/v1/devis/{devis_id}/convert", json={}, headers=auth_headers_admin
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == DevisStatus.CONVERTED
        assert data["converted_reservation_id"] is not None

    def test_convert_without_any_dates_400(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, bundle_dev
    ):
        """Pas de dates dans le payload ni dans le devis → 400."""
        devis_id = self._create_bundle_devis_and_accept(
            client, auth_headers_admin, customer_dev.id, bundle_dev.id
        )
        resp = client.post(
            f"/api/v1/devis/{devis_id}/convert", json={}, headers=auth_headers_admin
        )
        assert resp.status_code == 400

    def test_convert_freetext_lines_only_400(
        self, client: TestClient, auth_headers_admin: dict, customer_dev
    ):
        """Devis avec uniquement des lignes texte (sans product_id ni bundle_id) → 400."""
        devis_id = client.post(
            "/api/v1/devis", json=_devis_payload(customer_dev.id), headers=auth_headers_admin
        ).json()["id"]
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/accept", headers=auth_headers_admin)
        today = date.today()
        resp = client.post(
            f"/api/v1/devis/{devis_id}/convert",
            json={
                "delivery_date": (today + timedelta(days=10)).isoformat(),
                "return_date": (today + timedelta(days=12)).isoformat(),
            },
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400

    def test_convert_sets_converted_reservation_id(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, bundle_dev
    ):
        """converted_reservation_id doit être non-null après conversion réussie."""
        today = date.today()
        extra = {
            "delivery_date": (today + timedelta(days=5)).isoformat(),
            "return_date": (today + timedelta(days=7)).isoformat(),
        }
        devis_id = self._create_bundle_devis_and_accept(
            client, auth_headers_admin, customer_dev.id, bundle_dev.id, extra=extra
        )
        resp = client.post(
            f"/api/v1/devis/{devis_id}/convert", json={}, headers=auth_headers_admin
        )
        reservation_id = resp.json()["converted_reservation_id"]
        assert isinstance(reservation_id, int)
        assert reservation_id > 0

    def test_convert_propagates_caution_amount(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, bundle_dev
    ):
        """La caution du devis (caution_amount_cents) doit être propagée à la réservation."""
        today = date.today()
        extra = {
            "delivery_date": (today + timedelta(days=5)).isoformat(),
            "return_date": (today + timedelta(days=7)).isoformat(),
            "caution_amount_cents": 5000,
        }
        devis_id = self._create_bundle_devis_and_accept(
            client, auth_headers_admin, customer_dev.id, bundle_dev.id, extra=extra
        )
        resp = client.post(
            f"/api/v1/devis/{devis_id}/convert", json={}, headers=auth_headers_admin
        )
        assert resp.status_code == 200, resp.text
        reservation_id = resp.json()["reservation_id"]

        res_resp = client.get(f"/api/v1/reservations/{reservation_id}", headers=auth_headers_admin)
        assert res_resp.status_code == 200, res_resp.text
        assert res_resp.json()["deposit_amount_cents"] == 5000

    def test_convert_creates_deposit_when_caution_required(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, bundle_dev
    ):
        """Conversion avec caution_required=True doit creer un Deposit(status=held)."""
        today = date.today()
        extra = {
            "delivery_date": (today + timedelta(days=5)).isoformat(),
            "return_date": (today + timedelta(days=7)).isoformat(),
            "caution_required": True,
            "caution_amount_cents": 15000,
        }
        devis_id = self._create_bundle_devis_and_accept(
            client, auth_headers_admin, customer_dev.id, bundle_dev.id, extra=extra
        )
        resp = client.post(
            f"/api/v1/devis/{devis_id}/convert", json={}, headers=auth_headers_admin
        )
        assert resp.status_code == 200, resp.text
        reservation_id = resp.json()["reservation_id"]

        # Verifier que le deposit existe via endpoint reservation
        dep_resp = client.get(
            f"/api/v1/reservations/{reservation_id}/deposits",
            headers=auth_headers_admin,
        )
        assert dep_resp.status_code == 200, dep_resp.text
        deposits = dep_resp.json()
        assert len(deposits) == 1
        assert deposits[0]["amount_cents"] == 15000
        assert deposits[0]["status"] == "held"
        assert deposits[0]["collection_date"] is None

        # deposit_paid reste False (pas encore verse)
        res_resp = client.get(
            f"/api/v1/reservations/{reservation_id}", headers=auth_headers_admin
        )
        assert res_resp.status_code == 200
        assert res_resp.json()["deposit_paid"] is False

    def test_convert_no_deposit_when_caution_not_required(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, bundle_dev
    ):
        """Conversion sans caution_required ne doit PAS creer de Deposit."""
        today = date.today()
        extra = {
            "delivery_date": (today + timedelta(days=5)).isoformat(),
            "return_date": (today + timedelta(days=7)).isoformat(),
            "caution_required": False,
        }
        devis_id = self._create_bundle_devis_and_accept(
            client, auth_headers_admin, customer_dev.id, bundle_dev.id, extra=extra
        )
        resp = client.post(
            f"/api/v1/devis/{devis_id}/convert", json={}, headers=auth_headers_admin
        )
        assert resp.status_code == 200, resp.text
        reservation_id = resp.json()["reservation_id"]

        dep_resp = client.get(
            f"/api/v1/reservations/{reservation_id}/deposits",
            headers=auth_headers_admin,
        )
        assert dep_resp.status_code == 200
        deposits = dep_resp.json()
        assert len(deposits) == 0

    def test_convert_sets_devis_id(
        self, client: TestClient, auth_headers_admin: dict, customer_dev, bundle_dev
    ):
        """La réservation créée doit avoir devis_id égal à l'id du devis source."""
        today = date.today()
        extra = {
            "delivery_date": (today + timedelta(days=5)).isoformat(),
            "return_date": (today + timedelta(days=7)).isoformat(),
        }
        devis_id = self._create_bundle_devis_and_accept(
            client, auth_headers_admin, customer_dev.id, bundle_dev.id, extra=extra
        )
        resp = client.post(
            f"/api/v1/devis/{devis_id}/convert", json={}, headers=auth_headers_admin
        )
        assert resp.status_code == 200, resp.text
        reservation_id = resp.json()["reservation_id"]

        res_resp = client.get(f"/api/v1/reservations/{reservation_id}", headers=auth_headers_admin)
        assert res_resp.status_code == 200, res_resp.text
        assert res_resp.json()["devis_id"] == devis_id


# ---------------------------------------------------------------------------
# Tests cycle de vie modules
# ---------------------------------------------------------------------------

class TestDevisModuleLifecycle:
    def _create_devis(self, client, headers, customer_id):
        return client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers).json()["id"]

    def test_add_module_201(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        resp = client.post(
            f"/api/v1/devis/{devis_id}/modules",
            json={"module_type": "socle", "label": "Module principal", "content_json": {"key": "val"}},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["label"] == "Module principal"
        assert data["module_type"] == "socle"
        assert data["devis_id"] == devis_id

    def test_update_module_200(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        module = client.post(
            f"/api/v1/devis/{devis_id}/modules",
            json={"module_type": "socle", "label": "Avant modif", "content_json": {}},
            headers=auth_headers_admin,
        ).json()
        resp = client.patch(
            f"/api/v1/devis/{devis_id}/modules/{module['id']}",
            json={"label": "Après modif"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["label"] == "Après modif"

    def test_delete_module_204(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        module = client.post(
            f"/api/v1/devis/{devis_id}/modules",
            json={"module_type": "socle", "label": "À supprimer", "content_json": {}},
            headers=auth_headers_admin,
        ).json()
        resp = client.delete(
            f"/api/v1/devis/{devis_id}/modules/{module['id']}",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 204
        # Vérifier que la liste est vide
        listing = client.get(f"/api/v1/devis/{devis_id}/modules", headers=auth_headers_admin).json()
        assert all(m["id"] != module["id"] for m in listing)

    def test_module_unknown_devis_404(self, client: TestClient, auth_headers_admin: dict):
        resp = client.post(
            "/api/v1/devis/99999/modules",
            json={"module_type": "socle", "label": "X", "content_json": {}},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests cycle de vie phases
# ---------------------------------------------------------------------------

class TestDevisPhaseLifecycle:
    def _create_devis(self, client, headers, customer_id):
        return client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers).json()["id"]

    def _phase_payload(self, label: str = "Phase test") -> dict:
        today = date.today()
        return {
            "label": label,
            "date_start": today.isoformat(),
            "date_end": (today + timedelta(days=7)).isoformat(),
            "sort_order": 1,
        }

    def test_add_phase_201(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        resp = client.post(
            f"/api/v1/devis/{devis_id}/phases",
            json=self._phase_payload("Livraison"),
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["label"] == "Livraison"
        assert data["devis_id"] == devis_id

    def test_update_phase_200(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        phase = client.post(
            f"/api/v1/devis/{devis_id}/phases",
            json=self._phase_payload("Avant"),
            headers=auth_headers_admin,
        ).json()
        resp = client.patch(
            f"/api/v1/devis/{devis_id}/phases/{phase['id']}",
            json={"label": "Après"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["label"] == "Après"

    def test_delete_phase_204(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        phase = client.post(
            f"/api/v1/devis/{devis_id}/phases",
            json=self._phase_payload("À supprimer"),
            headers=auth_headers_admin,
        ).json()
        resp = client.delete(
            f"/api/v1/devis/{devis_id}/phases/{phase['id']}",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 204
        listing = client.get(f"/api/v1/devis/{devis_id}/phases", headers=auth_headers_admin).json()
        assert all(p["id"] != phase["id"] for p in listing)

    def test_phase_unknown_devis_404(self, client: TestClient, auth_headers_admin: dict):
        today = date.today()
        resp = client.post(
            "/api/v1/devis/99999/phases",
            json={
                "label": "X",
                "date_start": today.isoformat(),
                "date_end": (today + timedelta(days=1)).isoformat(),
                "sort_order": 0,
            },
            headers=auth_headers_admin,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests CRUD coverage-items
# ---------------------------------------------------------------------------

class TestDevisCoverageItemCRUD:
    def _create_devis(self, client, headers, customer_id):
        return client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers).json()["id"]

    def test_list_coverage_items_empty(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        resp = client.get(f"/api/v1/devis/{devis_id}/coverage-items", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_add_coverage_item_201(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        resp = client.post(
            f"/api/v1/devis/{devis_id}/coverage-items",
            json={"title": "Décor floral", "description": "Inclus", "status": "en_cours"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["title"] == "Décor floral"
        assert data["status"] == "en_cours"
        assert data["devis_id"] == devis_id

    def test_update_coverage_item_200(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        item = client.post(
            f"/api/v1/devis/{devis_id}/coverage-items",
            json={"title": "Sonorisation", "status": "a_cadrer"},
            headers=auth_headers_admin,
        ).json()
        resp = client.patch(
            f"/api/v1/devis/{devis_id}/coverage-items/{item['id']}",
            json={"status": "livre"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "livre"

    def test_delete_coverage_item_204(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        item = client.post(
            f"/api/v1/devis/{devis_id}/coverage-items",
            json={"title": "À supprimer", "status": "a_cadrer"},
            headers=auth_headers_admin,
        ).json()
        resp = client.delete(
            f"/api/v1/devis/{devis_id}/coverage-items/{item['id']}",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 204
        listing = client.get(f"/api/v1/devis/{devis_id}/coverage-items", headers=auth_headers_admin).json()
        assert all(i["id"] != item["id"] for i in listing)

    def test_coverage_item_invalid_status_422(self, client: TestClient, auth_headers_admin: dict, customer_dev):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        resp = client.post(
            f"/api/v1/devis/{devis_id}/coverage-items",
            json={"title": "Test", "status": "invalide"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests cycle de vie change-requests
# ---------------------------------------------------------------------------

class TestDevisChangeRequestLifecycle:
    def _create_devis(self, client, headers, customer_id):
        return client.post("/api/v1/devis", json=_devis_payload(customer_id), headers=headers).json()["id"]

    def test_add_change_request_creates_pending(
        self, client: TestClient, auth_headers_admin: dict, customer_dev
    ):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        resp = client.post(
            f"/api/v1/devis/{devis_id}/change-request",
            json={"description": "Ajouter un pupitre supplémentaire"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["description"] == "Ajouter un pupitre supplémentaire"
        assert data["status"] == "pending"
        assert data["devis_id"] == devis_id

    def test_update_change_request_status_accepted(
        self, client: TestClient, auth_headers_admin: dict, customer_dev
    ):
        """BUG-DEVIS-CR-01 : update_change_request endpoint swaps cr_id / tenant_id positionally.
        Ce test détectera la régression si le bug est présent."""
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        cr = client.post(
            f"/api/v1/devis/{devis_id}/change-request",
            json={"description": "Modifier la couleur"},
            headers=auth_headers_admin,
        ).json()
        resp = client.patch(
            f"/api/v1/devis/{devis_id}/change-request/{cr['id']}",
            json={"status": "accepted"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "accepted"

    def test_update_change_request_status_refused(
        self, client: TestClient, auth_headers_admin: dict, customer_dev
    ):
        devis_id = self._create_devis(client, auth_headers_admin, customer_dev.id)
        cr = client.post(
            f"/api/v1/devis/{devis_id}/change-request",
            json={"description": "Retirer une table"},
            headers=auth_headers_admin,
        ).json()
        resp = client.patch(
            f"/api/v1/devis/{devis_id}/change-request/{cr['id']}",
            json={"status": "refused"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "refused"

    def test_change_request_unknown_devis_404(self, client: TestClient, auth_headers_admin: dict):
        resp = client.post(
            "/api/v1/devis/99999/change-request",
            json={"description": "X"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests isolation cross-tenant exhaustifs
# ---------------------------------------------------------------------------

class TestDevisCrossTenantFull:
    def _create_t1(self, client, headers_t1, customer_id):
        return client.post(
            "/api/v1/devis", json=_devis_payload(customer_id), headers=headers_t1
        ).json()["id"]

    def test_update_cross_tenant_404(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_admin_tenant2: dict,
        customer_dev,
    ):
        devis_id = self._create_t1(client, auth_headers_admin, customer_dev.id)
        resp = client.patch(
            f"/api/v1/devis/{devis_id}",
            json={"notes": "Tentative"},
            headers=auth_headers_admin_tenant2,
        )
        assert resp.status_code == 404

    def test_cancel_cross_tenant_404(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_admin_tenant2: dict,
        customer_dev,
    ):
        devis_id = self._create_t1(client, auth_headers_admin, customer_dev.id)
        resp = client.post(f"/api/v1/devis/{devis_id}/cancel", headers=auth_headers_admin_tenant2)
        assert resp.status_code == 404

    def test_add_module_cross_tenant_404(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_admin_tenant2: dict,
        customer_dev,
    ):
        devis_id = self._create_t1(client, auth_headers_admin, customer_dev.id)
        resp = client.post(
            f"/api/v1/devis/{devis_id}/modules",
            json={"module_type": "socle", "label": "Intrusion", "content_json": {}},
            headers=auth_headers_admin_tenant2,
        )
        assert resp.status_code == 404

    def test_convert_cross_tenant_404(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_admin_tenant2: dict,
        customer_dev,
        bundle_dev,
    ):
        devis_id = self._create_t1(client, auth_headers_admin, customer_dev.id)
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/accept", headers=auth_headers_admin)
        today = date.today()
        resp = client.post(
            f"/api/v1/devis/{devis_id}/convert",
            json={
                "delivery_date": (today + timedelta(days=10)).isoformat(),
                "return_date": (today + timedelta(days=12)).isoformat(),
            },
            headers=auth_headers_admin_tenant2,
        )
        assert resp.status_code == 404

    def test_list_only_own_tenant(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_admin_tenant2: dict,
        customer_dev,
    ):
        """La liste /devis ne retourne que les devis du tenant connecté."""
        devis_id = self._create_t1(client, auth_headers_admin, customer_dev.id)
        listing_t2 = client.get("/api/v1/devis", headers=auth_headers_admin_tenant2).json()
        ids_t2 = [i["id"] for i in listing_t2["items"]]
        assert devis_id not in ids_t2


# ---------------------------------------------------------------------------
# Tests flux version_pending → resend → nouvelle version
# ---------------------------------------------------------------------------

class TestDevisVersionPendingFlow:
    def test_version_pending_to_sent_creates_version(
        self, client: TestClient, auth_headers_admin: dict, customer_dev
    ):
        """VERSION_PENDING → /send → SENT doit créer un snapshot de version."""
        devis_id = client.post(
            "/api/v1/devis", json=_devis_payload(customer_dev.id), headers=auth_headers_admin
        ).json()["id"]
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/version-pending", headers=auth_headers_admin)

        resp = client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == DevisStatus.SENT

        versions = client.get(f"/api/v1/devis/{devis_id}/versions", headers=auth_headers_admin).json()
        assert len(versions) >= 2  # v1 (premier send) + v2 (resend depuis version_pending)

    def test_version_pending_to_negotiation(
        self, client: TestClient, auth_headers_admin: dict, customer_dev
    ):
        """VERSION_PENDING → back_to_negotiation → NEGOTIATION."""
        devis_id = client.post(
            "/api/v1/devis", json=_devis_payload(customer_dev.id), headers=auth_headers_admin
        ).json()["id"]
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/version-pending", headers=auth_headers_admin)

        resp = client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=auth_headers_admin)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == DevisStatus.NEGOTIATION

    def test_version_pending_accept_direct(
        self, client: TestClient, auth_headers_admin: dict, customer_dev
    ):
        """VERSION_PENDING → accept → ACCEPTED (transition directe)."""
        devis_id = client.post(
            "/api/v1/devis", json=_devis_payload(customer_dev.id), headers=auth_headers_admin
        ).json()["id"]
        client.post(f"/api/v1/devis/{devis_id}/send", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/negotiation/start", headers=auth_headers_admin)
        client.post(f"/api/v1/devis/{devis_id}/version-pending", headers=auth_headers_admin)

        resp = client.post(f"/api/v1/devis/{devis_id}/accept", headers=auth_headers_admin)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == DevisStatus.ACCEPTED
