"""Tests d'intégration — Réservations avancées (B2) : pre-check, risks, extensions, signature, full."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.models.customer import Customer
from app.models.product import Product
from app.models.reservation import Reservation, ReservationPreCheckItem
from app.constants import CustomerType, ProductCategory, ProductCondition, ReservationStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def customer_adv(test_db):
    c = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Lucas",
        last_name="Avancé",
        email="lucas.avance@example.com",
        phone="+33600000060",
        city="Lyon",
        postal_code="69001",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def customer_adv_t2(test_db):
    c = Customer(
        tenant_id=2,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Marc",
        last_name="Tenant2",
        email="marc.adv.t2@example.com",
        phone="+33600000061",
        city="Marseille",
        postal_code="13001",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def reservation_adv(test_db, customer_adv):
    """Réservation CONFIRMED pour les tests avancés."""
    r = Reservation(
        tenant_id=1,
        customer_id=customer_adv.id,
        reference="RES-ADV-001",
        event_date=date.today() + timedelta(days=30),
        delivery_date=date.today() + timedelta(days=29),
        return_date=date.today() + timedelta(days=32),
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=100000,
        deposit_amount_cents=20000,
        deposit_paid=False,
    )
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)
    return r


@pytest.fixture
def reservation_adv_t2(test_db, customer_adv_t2):
    """Réservation tenant2."""
    r = Reservation(
        tenant_id=2,
        customer_id=customer_adv_t2.id,
        reference="RES-ADV-T2-001",
        event_date=date.today() + timedelta(days=30),
        delivery_date=date.today() + timedelta(days=29),
        return_date=date.today() + timedelta(days=32),
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=100000,
        deposit_amount_cents=20000,
        deposit_paid=False,
    )
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)
    return r


# ---------------------------------------------------------------------------
# Tests Pre-check
# ---------------------------------------------------------------------------

class TestPreCheck:
    def _add_items(self, test_db, reservation, items: list[dict]):
        """Ajoute des items pre-check en DB directement."""
        for i, item in enumerate(items):
            pc = ReservationPreCheckItem(
                tenant_id=reservation.tenant_id,
                reservation_id=reservation.id,
                label=item["label"],
                type=item.get("type", "custom"),
                checked=item.get("checked", False),
                sort_order=i,
            )
            test_db.add(pc)
        test_db.commit()

    def test_list_pre_check_empty(self, client: TestClient, auth_headers_real, reservation_adv):
        resp = client.get(
            f"/api/v1/reservations/{reservation_adv.id}/pre-check",
            headers=auth_headers_real
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_patch_pre_check_item(self, client: TestClient, auth_headers_real, reservation_adv, test_db):
        self._add_items(test_db, reservation_adv, [{"label": "Contrat signé", "type": "document"}])
        items_resp = client.get(
            f"/api/v1/reservations/{reservation_adv.id}/pre-check",
            headers=auth_headers_real
        )
        item_id = items_resp.json()[0]["id"]

        resp = client.patch(
            f"/api/v1/reservations/{reservation_adv.id}/pre-check/{item_id}",
            json={"checked": True},
            headers=auth_headers_real
        )
        assert resp.status_code == 200
        assert resp.json()["checked"] is True
        assert resp.json()["checked_at"] is not None

    def test_complete_pre_check_all_checked(self, client: TestClient, auth_headers_real, reservation_adv, test_db):
        """Valide le pre-check quand tous les items sont cochés."""
        self._add_items(test_db, reservation_adv, [
            {"label": "Contrat signé", "type": "document", "checked": True},
            {"label": "Paiement OK", "type": "payment", "checked": True},
        ])
        resp = client.post(
            f"/api/v1/reservations/{reservation_adv.id}/pre-check/complete",
            headers=auth_headers_real
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == ReservationStatus.PRE_CHECK

    def test_complete_pre_check_not_all_checked_400(self, client: TestClient, auth_headers_real, reservation_adv, test_db):
        """Échoue si des items sont non cochés."""
        self._add_items(test_db, reservation_adv, [
            {"label": "Contrat signé", "type": "document", "checked": True},
            {"label": "Paiement manquant", "type": "payment", "checked": False},
        ])
        resp = client.post(
            f"/api/v1/reservations/{reservation_adv.id}/pre-check/complete",
            headers=auth_headers_real
        )
        assert resp.status_code == 400

    def test_complete_pre_check_wrong_status_400(
        self, client: TestClient, auth_headers_real, reservation_adv, test_db
    ):
        reservation_adv.status = ReservationStatus.DELIVERED
        test_db.add(reservation_adv)
        test_db.commit()

        resp = client.post(
            f"/api/v1/reservations/{reservation_adv.id}/pre-check/complete",
            headers=auth_headers_real
        )
        assert resp.status_code == 400
        assert "pre-check completion impossible" in resp.json()["detail"].lower()

    def test_pre_check_cross_tenant_404(self, client: TestClient, auth_headers_real, reservation_adv_t2):
        resp = client.get(
            f"/api/v1/reservations/{reservation_adv_t2.id}/pre-check",
            headers=auth_headers_real
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests Risks
# ---------------------------------------------------------------------------

class TestReservationRisks:
    def test_list_risks_empty(self, client: TestClient, auth_headers_real, reservation_adv):
        resp = client.get(
            f"/api/v1/reservations/{reservation_adv.id}/risks",
            headers=auth_headers_real
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_add_risk_201(self, client: TestClient, auth_headers_real, reservation_adv):
        resp = client.post(
            f"/api/v1/reservations/{reservation_adv.id}/risks",
            json={
                "type": "missing_deposit",
                "severity": "medium",
                "description": "Dépôt non reçu",
                "blocking": False,
            },
            headers=auth_headers_real
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "missing_deposit"
        assert data["severity"] == "medium"

    def test_add_blocking_risk_changes_status(self, client: TestClient, auth_headers_real, reservation_adv):
        """Un risque bloquant passe la réservation en confirmed_risk."""
        resp = client.post(
            f"/api/v1/reservations/{reservation_adv.id}/risks",
            json={
                "type": "legal_issue",
                "severity": "high",
                "description": "Litige en cours",
                "blocking": True,
            },
            headers=auth_headers_real
        )
        assert resp.status_code == 201
        # Vérifier le statut de la réservation
        res_resp = client.get(
            f"/api/v1/reservations/{reservation_adv.id}",
            headers=auth_headers_real
        )
        assert res_resp.json()["status"] == ReservationStatus.CONFIRMED_RISK

    def test_delete_risk_204(self, client: TestClient, auth_headers_real, reservation_adv):
        add_resp = client.post(
            f"/api/v1/reservations/{reservation_adv.id}/risks",
            json={"type": "overdue_payment", "severity": "low", "description": "Test", "blocking": False},
            headers=auth_headers_real
        )
        risk_id = add_resp.json()["id"]
        del_resp = client.delete(
            f"/api/v1/reservations/{reservation_adv.id}/risks/{risk_id}",
            headers=auth_headers_real
        )
        assert del_resp.status_code == 204

    def test_patch_risk_200(self, client: TestClient, auth_headers_real, reservation_adv):
        """PATCH met à jour severity et description d'un risque."""
        add_resp = client.post(
            f"/api/v1/reservations/{reservation_adv.id}/risks",
            json={"type": "insurance_gap", "severity": "low", "description": "Couverture insuffisante", "blocking": False},
            headers=auth_headers_real
        )
        assert add_resp.status_code == 201
        risk_id = add_resp.json()["id"]
        patch_resp = client.patch(
            f"/api/v1/reservations/{reservation_adv.id}/risks/{risk_id}",
            json={"severity": "high", "description": "Couverture inexistante"},
            headers=auth_headers_real,
        )
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["severity"] == "high"
        assert data["description"] == "Couverture inexistante"
        assert data["type"] == "insurance_gap"  # non modifié

    def test_patch_risk_not_found(self, client: TestClient, auth_headers_real, reservation_adv):
        resp = client.patch(
            f"/api/v1/reservations/{reservation_adv.id}/risks/99999",
            json={"severity": "medium"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 404

    def test_patch_risk_cross_tenant_blocked(self, client: TestClient, auth_headers_real, reservation_adv_t2):
        resp = client.patch(
            f"/api/v1/reservations/{reservation_adv_t2.id}/risks/1",
            json={"severity": "low"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 404

    def test_risks_cross_tenant_404(self, client: TestClient, auth_headers_real, reservation_adv_t2):
        resp = client.get(
            f"/api/v1/reservations/{reservation_adv_t2.id}/risks",
            headers=auth_headers_real
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests Extension
# ---------------------------------------------------------------------------

class TestReservationExtension:
    def test_extend_reservation_201(self, client: TestClient, auth_headers_real, reservation_adv, test_db):
        reservation_adv.status = ReservationStatus.DELIVERED
        test_db.add(reservation_adv)
        test_db.commit()

        new_return = (date.today() + timedelta(days=35)).isoformat()
        resp = client.post(
            f"/api/v1/reservations/{reservation_adv.id}/extend",
            json={
                "new_return_date": new_return,
                "reason": "Client demande 3 jours supplémentaires",
                "extra_charge_cents": 15000,
            },
            headers=auth_headers_real
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["new_return_date"] == new_return
        assert data["extra_charge_cents"] == 15000

    def test_extend_before_current_return_400(self, client: TestClient, auth_headers_real, reservation_adv, test_db):
        """Impossible d'étendre à une date antérieure."""
        reservation_adv.status = ReservationStatus.DELIVERED
        test_db.add(reservation_adv)
        test_db.commit()

        past_return = (date.today() + timedelta(days=10)).isoformat()
        resp = client.post(
            f"/api/v1/reservations/{reservation_adv.id}/extend",
            json={
                "new_return_date": past_return,
                "reason": "Test",
                "extra_charge_cents": 0,
            },
            headers=auth_headers_real
        )
        assert resp.status_code == 400

    def test_extend_wrong_status_400(self, client: TestClient, auth_headers_real, reservation_adv):
        resp = client.post(
            f"/api/v1/reservations/{reservation_adv.id}/extend",
            json={
                "new_return_date": (date.today() + timedelta(days=40)).isoformat(),
                "reason": "Test status",
                "extra_charge_cents": 0,
            },
            headers=auth_headers_real
        )
        assert resp.status_code == 400
        assert "statuts autorisés" in resp.json()["detail"].lower()

    def test_extend_cross_tenant_404(self, client: TestClient, auth_headers_real, reservation_adv_t2):
        resp = client.post(
            f"/api/v1/reservations/{reservation_adv_t2.id}/extend",
            json={
                "new_return_date": (date.today() + timedelta(days=40)).isoformat(),
                "reason": "Test cross-tenant",
                "extra_charge_cents": 0,
            },
            headers=auth_headers_real
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests Signature
# ---------------------------------------------------------------------------

class TestReservationSignature:
    def test_upload_signature(self, client: TestClient, auth_headers_real, reservation_adv):
        resp = client.post(
            f"/api/v1/reservations/{reservation_adv.id}/signature",
            json={"signature_data": "data:image/png;base64,iVBORw0KGgo="},
            headers=auth_headers_real
        )
        assert resp.status_code == 200

    def test_signature_cross_tenant_404(self, client: TestClient, auth_headers_real, reservation_adv_t2):
        resp = client.post(
            f"/api/v1/reservations/{reservation_adv_t2.id}/signature",
            json={"signature_data": "data:image/png;base64,abc="},
            headers=auth_headers_real
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests Full
# ---------------------------------------------------------------------------

class TestReservationFull:
    def test_get_full(self, client: TestClient, auth_headers_real, reservation_adv):
        resp = client.get(
            f"/api/v1/reservations/{reservation_adv.id}/full",
            headers=auth_headers_real
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == reservation_adv.id
        assert "risks" in data
        assert "pre_check_items" in data
        assert "extensions" in data

    def test_get_full_cross_tenant_404(self, client: TestClient, auth_headers_real, reservation_adv_t2):
        resp = client.get(
            f"/api/v1/reservations/{reservation_adv_t2.id}/full",
            headers=auth_headers_real
        )
        assert resp.status_code == 404


class TestReservationAssignUser:
    def test_assign_user(self, client: TestClient, auth_headers_real, reservation_adv):
        """Affecter l'utilisateur courant à la réservation."""
        # Récupère l'id de l'utilisateur tenant 1
        me = client.get("/api/v1/auth/me", headers=auth_headers_real)
        user_id = me.json()["id"]

        resp = client.patch(
            f"/api/v1/reservations/{reservation_adv.id}/assign",
            json={"user_id": user_id},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["assigned_user_id"] == user_id

    def test_unassign_user(self, client: TestClient, auth_headers_real, reservation_adv):
        """Désaffecter (user_id=null)."""
        resp = client.patch(
            f"/api/v1/reservations/{reservation_adv.id}/assign",
            json={"user_id": None},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["assigned_user_id"] is None

    def test_assign_user_cross_tenant_rejected(
        self, client: TestClient, auth_headers_real, reservation_adv, auth_headers_tenant2
    ):
        """Un utilisateur d'un autre tenant est refusé."""
        me_t2 = client.get("/api/v1/auth/me", headers=auth_headers_tenant2)
        user_id_t2 = me_t2.json()["id"]

        resp = client.patch(
            f"/api/v1/reservations/{reservation_adv.id}/assign",
            json={"user_id": user_id_t2},
            headers=auth_headers_real,
        )
        assert resp.status_code == 404

    def test_assign_unauthenticated(self, client: TestClient, reservation_adv):
        resp = client.patch(
            f"/api/v1/reservations/{reservation_adv.id}/assign",
            json={"user_id": 1},
        )
        assert resp.status_code == 401
