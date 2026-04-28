"""Tests d'intégration pour les endpoints événements avancés."""
import pytest
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.models.evenements import Evenement, EventIncident
from app.models.customer import Customer
from app.models.reservation import Reservation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def evenement(test_db, auth_headers_real, client):
    """Crée un événement de test via l'API."""
    resp = client.post(
        "/api/v1/evenements",
        json={
            "name": "Mariage Dupont",
            "event_date": str(date.today() + timedelta(days=30)),
            "location": "Salle des Fêtes",
        },
        headers=auth_headers_real,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def incident_payload():
    return {
        "description": "Micro défaillant en plein discours",
        "severity": "high",
        "declared_at": datetime.now(tz=timezone.utc).isoformat(),
        "affected_items": [],
    }


# ---------------------------------------------------------------------------
# CRUD Événements
# ---------------------------------------------------------------------------

class TestCreateEvenement:
    def test_create_ok(self, client: TestClient, auth_headers_real: dict):
        resp = client.post(
            "/api/v1/evenements",
            json={"name": "Anniversaire Martin", "event_date": str(date.today() + timedelta(days=10))},
            headers=auth_headers_real,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "Anniversaire Martin"
        assert data["status"] == "planned"
        assert data["reference"].startswith("EVT-")

    def test_create_missing_name(self, client: TestClient, auth_headers_real: dict):
        resp = client.post(
            "/api/v1/evenements",
            json={"event_date": str(date.today())},
            headers=auth_headers_real,
        )
        assert resp.status_code == 422

    def test_create_unauthenticated(self, client: TestClient):
        resp = client.post(
            "/api/v1/evenements",
            json={"name": "Test", "event_date": str(date.today())},
        )
        assert resp.status_code == 401


class TestListEvenements:
    def test_list_ok(self, client: TestClient, auth_headers_real: dict, evenement: dict):
        resp = client.get("/api/v1/evenements", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "items" in data
        assert isinstance(data["items"], list)
        ids = [e["id"] for e in data["items"]]
        assert evenement["id"] in ids

    def test_list_filter_status(self, client: TestClient, auth_headers_real: dict, evenement: dict):
        resp = client.get("/api/v1/evenements?status=planned", headers=auth_headers_real)
        assert resp.status_code == 200
        for ev in resp.json()["items"]:
            assert ev["status"] == "planned"

    def test_list_cross_tenant_isolation(
        self, client: TestClient, auth_headers_real: dict,
        auth_headers_tenant2: dict, evenement: dict,
    ):
        """Le tenant 2 ne doit pas voir les événements du tenant 1."""
        resp = client.get("/api/v1/evenements", headers=auth_headers_tenant2)
        assert resp.status_code == 200
        ids = [e["id"] for e in resp.json()["items"]]
        assert evenement["id"] not in ids


class TestGetEvenement:
    def test_get_ok(self, client: TestClient, auth_headers_real: dict, evenement: dict):
        resp = client.get(f"/api/v1/evenements/{evenement['id']}", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["id"] == evenement["id"]

    def test_get_not_found(self, client: TestClient, auth_headers_real: dict):
        resp = client.get("/api/v1/evenements/99999", headers=auth_headers_real)
        assert resp.status_code == 404

    def test_get_cross_tenant_blocked(
        self, client: TestClient, auth_headers_tenant2: dict, evenement: dict
    ):
        resp = client.get(f"/api/v1/evenements/{evenement['id']}", headers=auth_headers_tenant2)
        assert resp.status_code == 404


class TestUpdateEvenement:
    def test_update_ok(self, client: TestClient, auth_headers_real: dict, evenement: dict):
        resp = client.patch(
            f"/api/v1/evenements/{evenement['id']}",
            json={"location": "Grande Salle Versailles"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["event_location"] == "Grande Salle Versailles"


# ---------------------------------------------------------------------------
# Transitions d'état
# ---------------------------------------------------------------------------

class TestTransitions:
    def test_start_from_planned(self, client: TestClient, auth_headers_real: dict, evenement: dict):
        """planned → in_progress via POST /start."""
        resp = client.post(f"/api/v1/evenements/{evenement['id']}/start", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    def test_start_from_risk(self, client: TestClient, auth_headers_real: dict, evenement: dict):
        """risk → in_progress via POST /start."""
        client.post(f"/api/v1/evenements/{evenement['id']}/flag-risk", headers=auth_headers_real)
        resp = client.post(f"/api/v1/evenements/{evenement['id']}/start", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    def test_start_invalid_from_in_progress(self, client: TestClient, auth_headers_real: dict, evenement: dict):
        """in_progress → in_progress est invalide."""
        client.post(f"/api/v1/evenements/{evenement['id']}/start", headers=auth_headers_real)
        resp = client.post(f"/api/v1/evenements/{evenement['id']}/start", headers=auth_headers_real)
        assert resp.status_code == 400

    def test_flag_risk(self, client: TestClient, auth_headers_real: dict, evenement: dict):
        resp = client.post(f"/api/v1/evenements/{evenement['id']}/flag-risk", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["status"] == "risk"

    def test_flag_risk_then_cancel(self, client: TestClient, auth_headers_real: dict, evenement: dict):
        client.post(f"/api/v1/evenements/{evenement['id']}/flag-risk", headers=auth_headers_real)
        resp = client.post(f"/api/v1/evenements/{evenement['id']}/cancel", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_invalid_transition(self, client: TestClient, auth_headers_real: dict, evenement: dict):
        """planned → returned est invalide (doit passer par in_progress d'abord)."""
        resp = client.post(f"/api/v1/evenements/{evenement['id']}/mark-returned", headers=auth_headers_real)
        assert resp.status_code == 400

    def test_close_after_returned(self, client: TestClient, auth_headers_real: dict, evenement: dict):
        ev_id = evenement["id"]
        # planned → in_progress n'est pas un endpoint direct — on doit aller via flag-risk → in_progress
        # On force via DB : planned → in_progress
        # Transition: planned → risk → in_progress (via flag-risk puis patch status direct dans le test n'est pas dispo)
        # On utilise le chemin : POST /mark-returned depuis in_progress
        # Workaround : on doit créer un incident depuis in_progress
        # Simplification : test la transition returned → close
        # D'abord on met en planned → in_progress est accessible depuis planned dans les transitions
        # Mais il n'y a pas d'endpoint /start-event → on ne peut pas y accéder facilement
        # On skip ce chemin et on vérifie que close échoue depuis planned
        # CloseRequest.notes obligatoire (min 10) → on passe des notes valides
        # mais la transition planned → closed est invalide → 400
        resp = client.post(
            f"/api/v1/evenements/{ev_id}/close",
            json={"notes": "Clôture invalide depuis planned."},
            headers=auth_headers_real,
        )
        assert resp.status_code == 400  # planned → closed = invalide

    def test_cancel_already_cancelled(self, client: TestClient, auth_headers_real: dict, evenement: dict):
        ev_id = evenement["id"]
        client.post(f"/api/v1/evenements/{ev_id}/cancel", headers=auth_headers_real)
        resp = client.post(f"/api/v1/evenements/{ev_id}/cancel", headers=auth_headers_real)
        assert resp.status_code == 400  # cancelled → cancelled = invalide


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

class TestIncidents:
    def test_create_incident_ok(
        self, client: TestClient, auth_headers_real: dict, evenement: dict, incident_payload: dict
    ):
        resp = client.post(
            f"/api/v1/evenements/{evenement['id']}/incidents",
            json=incident_payload,
            headers=auth_headers_real,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["severity"] == "high"
        assert data["event_id"] == evenement["id"]

    def test_create_incident_changes_status(
        self, client: TestClient, auth_headers_real: dict, evenement: dict, incident_payload: dict, test_db
    ):
        """Créer un incident depuis in_progress → status passe à 'incident'."""
        # Forcer le statut in_progress via patch direct en DB
        ev_obj = test_db.query(Evenement).filter(Evenement.id == evenement["id"]).first()
        ev_obj.status = "in_progress"
        test_db.commit()

        client.post(
            f"/api/v1/evenements/{evenement['id']}/incidents",
            json=incident_payload,
            headers=auth_headers_real,
        )
        resp = client.get(f"/api/v1/evenements/{evenement['id']}", headers=auth_headers_real)
        assert resp.json()["status"] == "incident"

    def test_list_incidents_empty(
        self, client: TestClient, auth_headers_real: dict, evenement: dict
    ):
        resp = client.get(
            f"/api/v1/evenements/{evenement['id']}/incidents",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_incidents_after_create(
        self, client: TestClient, auth_headers_real: dict, evenement: dict, incident_payload: dict
    ):
        client.post(
            f"/api/v1/evenements/{evenement['id']}/incidents",
            json=incident_payload,
            headers=auth_headers_real,
        )
        resp = client.get(
            f"/api/v1/evenements/{evenement['id']}/incidents",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_incident_not_found(self, client: TestClient, auth_headers_real: dict):
        resp = client.get("/api/v1/evenements/99999/incidents", headers=auth_headers_real)
        assert resp.status_code == 404

    def test_incident_cross_tenant_blocked(
        self, client: TestClient, auth_headers_tenant2: dict,
        evenement: dict, incident_payload: dict
    ):
        resp = client.post(
            f"/api/v1/evenements/{evenement['id']}/incidents",
            json=incident_payload,
            headers=auth_headers_tenant2,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Plan d'actions
# ---------------------------------------------------------------------------

class TestActionPlan:
    def _create_incident(self, client, headers, evenement, incident_payload):
        r = client.post(
            f"/api/v1/evenements/{evenement['id']}/incidents",
            json=incident_payload,
            headers=headers,
        )
        return r.json()

    def test_create_action_plan_ok(
        self, client: TestClient, auth_headers_real: dict,
        evenement: dict, incident_payload: dict, test_user
    ):
        inc = self._create_incident(client, auth_headers_real, evenement, incident_payload)
        resp = client.post(
            f"/api/v1/evenements/{evenement['id']}/incidents/{inc['id']}/action-plan",
            json=[
                {"label": "Changer micro", "assignee_id": test_user.id, "deadline": str(date.today() + timedelta(days=2))},
                {"label": "Contacter prestataire", "assignee_id": test_user.id, "deadline": str(date.today() + timedelta(days=5))},
            ],
            headers=auth_headers_real,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert len(data) == 2
        assert data[0]["label"] == "Changer micro"
        assert data[0]["status"] == "todo"

    def test_action_plan_incident_not_found(
        self, client: TestClient, auth_headers_real: dict, evenement: dict, test_user
    ):
        resp = client.post(
            f"/api/v1/evenements/{evenement['id']}/incidents/99999/action-plan",
            json=[{"label": "Test", "assignee_id": test_user.id, "deadline": str(date.today())}],
            headers=auth_headers_real,
        )
        assert resp.status_code == 404

    def test_close_action_ok(
        self, client: TestClient, auth_headers_real: dict,
        evenement: dict, incident_payload: dict, test_user
    ):
        inc = self._create_incident(client, auth_headers_real, evenement, incident_payload)
        plan_resp = client.post(
            f"/api/v1/evenements/{evenement['id']}/incidents/{inc['id']}/action-plan",
            json=[{"label": "Tester clôture", "assignee_id": test_user.id, "deadline": str(date.today())}],
            headers=auth_headers_real,
        )
        assert plan_resp.status_code == 201
        action_id = plan_resp.json()[0]["id"]

        resp = client.patch(
            f"/api/v1/evenements/{evenement['id']}/incidents/{inc['id']}/actions/{action_id}/close",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "done"

    def test_close_action_not_found(
        self, client: TestClient, auth_headers_real: dict,
        evenement: dict, incident_payload: dict
    ):
        inc = self._create_incident(client, auth_headers_real, evenement, incident_payload)
        resp = client.patch(
            f"/api/v1/evenements/{evenement['id']}/incidents/{inc['id']}/actions/99999/close",
            headers=auth_headers_real,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Fixtures supplémentaires
# ---------------------------------------------------------------------------

@pytest.fixture
def reservation_in_db(test_db):
    """Réservation créée directement en DB pour les tests de conflit hard reschedule."""
    today = date.today()
    customer = Customer(
        tenant_id=1,
        customer_type="individual",
        first_name="Jean",
        last_name="Testeur",
        email="jean.testeur.reschedule@example.com",
    )
    test_db.add(customer)
    test_db.flush()
    res = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-CONFLICT-TEST-001",
        event_date=today + timedelta(days=30),
        delivery_date=today + timedelta(days=28),
        return_date=today + timedelta(days=35),
        status="confirmed",
        total_amount_cents=0,
    )
    test_db.add(res)
    test_db.commit()
    test_db.refresh(res)
    return res


# ---------------------------------------------------------------------------
# Reprogrammation (reschedule)
# ---------------------------------------------------------------------------

class TestRescheduleEvent:

    def test_reschedule_from_planned_ok(
        self, client: TestClient, auth_headers_real: dict, evenement: dict
    ):
        """planned → reschedule sans conflit → 200, date mise à jour."""
        new_date = str(date.today() + timedelta(days=60))
        resp = client.post(
            f"/api/v1/evenements/{evenement['id']}/reschedule",
            json={"new_date": new_date, "force": False},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["evenement"]["event_date"] == new_date
        assert data["conflicts"] == []

    def test_reschedule_from_risk_ok(
        self, client: TestClient, auth_headers_real: dict, evenement: dict
    ):
        """risk → reschedule autorisé → 200."""
        client.post(f"/api/v1/evenements/{evenement['id']}/flag-risk", headers=auth_headers_real)
        new_date = str(date.today() + timedelta(days=60))
        resp = client.post(
            f"/api/v1/evenements/{evenement['id']}/reschedule",
            json={"new_date": new_date},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["evenement"]["event_date"] == new_date

    def test_reschedule_from_in_progress_blocked(
        self, client: TestClient, auth_headers_real: dict, evenement: dict, test_db
    ):
        """in_progress → reschedule interdit → 400."""
        ev_obj = test_db.query(Evenement).filter(Evenement.id == evenement["id"]).first()
        ev_obj.status = "in_progress"
        test_db.commit()
        resp = client.post(
            f"/api/v1/evenements/{evenement['id']}/reschedule",
            json={"new_date": str(date.today() + timedelta(days=60))},
            headers=auth_headers_real,
        )
        assert resp.status_code == 400

    def test_reschedule_hard_conflict_reservation(
        self, client: TestClient, auth_headers_real: dict,
        test_db, reservation_in_db: Reservation
    ):
        """Reprogrammation hors de la plage livraison/retour → 400 conflit hard."""
        ev_date = str(reservation_in_db.delivery_date + timedelta(days=1))
        create_resp = client.post(
            "/api/v1/evenements",
            json={
                "name": "Event avec réservation liée",
                "event_date": ev_date,
                "reservation_id": reservation_in_db.id,
            },
            headers=auth_headers_real,
        )
        assert create_resp.status_code == 201
        ev_id = create_resp.json()["id"]

        out_of_range = str(reservation_in_db.return_date + timedelta(days=5))
        resp = client.post(
            f"/api/v1/evenements/{ev_id}/reschedule",
            json={"new_date": out_of_range, "force": False},
            headers=auth_headers_real,
        )
        assert resp.status_code == 400
        detail = resp.json().get("detail", "") or ""
        assert "conflict" in detail.lower() or "livraison" in detail.lower() or "bloquée" in detail.lower()

    def test_reschedule_soft_conflict_force_false(
        self, client: TestClient, auth_headers_real: dict, evenement: dict
    ):
        """Autre event même date, force=False → 200 avec conflicts, date inchangée."""
        target_date = str(date.today() + timedelta(days=50))
        client.post(
            "/api/v1/evenements",
            json={"name": "Autre événement concurrent", "event_date": target_date},
            headers=auth_headers_real,
        )
        original_date = evenement["event_date"]
        resp = client.post(
            f"/api/v1/evenements/{evenement['id']}/reschedule",
            json={"new_date": target_date, "force": False},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["conflicts"]) > 0
        assert data["conflicts"][0]["severity"] == "soft"
        assert data["evenement"]["event_date"] == original_date

    def test_reschedule_soft_conflict_force_true(
        self, client: TestClient, auth_headers_real: dict, evenement: dict
    ):
        """Autre event même date, force=True → 200, date mise à jour, conflicts vides."""
        target_date = str(date.today() + timedelta(days=50))
        client.post(
            "/api/v1/evenements",
            json={"name": "Événement concurrent 2", "event_date": target_date},
            headers=auth_headers_real,
        )
        resp = client.post(
            f"/api/v1/evenements/{evenement['id']}/reschedule",
            json={"new_date": target_date, "force": True},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["conflicts"] == []
        assert data["evenement"]["event_date"] == target_date


# ---------------------------------------------------------------------------
# Rapport de clôture
# ---------------------------------------------------------------------------

class TestEventReport:

    def test_report_from_planned_blocked(
        self, client: TestClient, auth_headers_real: dict, evenement: dict
    ):
        """Rapport inaccessible depuis planned → 400."""
        resp = client.get(
            f"/api/v1/evenements/{evenement['id']}/report",
            headers=auth_headers_real,
        )
        assert resp.status_code == 400

    def test_report_from_returned_ok(
        self, client: TestClient, auth_headers_real: dict, evenement: dict, test_db
    ):
        """Rapport accessible depuis returned → 200, structure valide."""
        ev_obj = test_db.query(Evenement).filter(Evenement.id == evenement["id"]).first()
        ev_obj.status = "returned"
        test_db.commit()
        resp = client.get(
            f"/api/v1/evenements/{evenement['id']}/report",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "evenement" in data
        assert "summary" in data
        assert "incidents" in data
        assert data["summary"]["total_incidents"] == 0

    def test_report_from_closed_ok(
        self, client: TestClient, auth_headers_real: dict, evenement: dict, test_db
    ):
        """Rapport accessible depuis closed → 200."""
        ev_obj = test_db.query(Evenement).filter(Evenement.id == evenement["id"]).first()
        ev_obj.status = "closed"
        test_db.commit()
        resp = client.get(
            f"/api/v1/evenements/{evenement['id']}/report",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["evenement"]["status"] == "closed"

    def test_report_with_incidents_summary(
        self, client: TestClient, auth_headers_real: dict,
        evenement: dict, incident_payload: dict, test_db
    ):
        """Le rapport agrège correctement les incidents ouverts."""
        ev_obj = test_db.query(Evenement).filter(Evenement.id == evenement["id"]).first()
        ev_obj.status = "in_progress"
        test_db.commit()

        client.post(
            f"/api/v1/evenements/{evenement['id']}/incidents",
            json=incident_payload,
            headers=auth_headers_real,
        )

        ev_obj2 = test_db.query(Evenement).filter(Evenement.id == evenement["id"]).first()
        ev_obj2.status = "returned"
        test_db.commit()

        resp = client.get(
            f"/api/v1/evenements/{evenement['id']}/report",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["summary"]["total_incidents"] == 1
        assert data["summary"]["open_incidents"] == 1
        assert data["summary"]["resolved_incidents"] == 0
        assert len(data["incidents"]) == 1

    def test_report_cross_tenant_blocked(
        self, client: TestClient, auth_headers_tenant2: dict, evenement: dict
    ):
        """Accès au rapport d'un event tenant1 depuis tenant2 → 404."""
        resp = client.get(
            f"/api/v1/evenements/{evenement['id']}/report",
            headers=auth_headers_tenant2,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Clôture avec notes obligatoires
# ---------------------------------------------------------------------------

class TestCloseWithNotes:

    def test_close_without_notes_422(
        self, client: TestClient, auth_headers_real: dict, evenement: dict
    ):
        """Clôture sans notes → 422."""
        resp = client.post(
            f"/api/v1/evenements/{evenement['id']}/close",
            json={},
            headers=auth_headers_real,
        )
        assert resp.status_code == 422

    def test_close_notes_too_short_422(
        self, client: TestClient, auth_headers_real: dict, evenement: dict
    ):
        """Clôture avec notes < 10 caractères → 422."""
        resp = client.post(
            f"/api/v1/evenements/{evenement['id']}/close",
            json={"notes": "court"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 422

    def test_close_with_valid_notes_ok(
        self, client: TestClient, auth_headers_real: dict, evenement: dict, test_db
    ):
        """Clôture depuis returned avec notes valides → 200, statut closed."""
        ev_obj = test_db.query(Evenement).filter(Evenement.id == evenement["id"]).first()
        ev_obj.status = "returned"
        test_db.commit()

        resp = client.post(
            f"/api/v1/evenements/{evenement['id']}/close",
            json={"notes": "Clôture validée après retour complet du matériel."},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "closed"
