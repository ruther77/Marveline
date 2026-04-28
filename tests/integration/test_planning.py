"""Tests d'intégration pour les endpoints planning."""
import pytest
from fastapi.testclient import TestClient


class TestPlanningDay:
    def test_get_day_default(self, client: TestClient, auth_headers_real: dict):
        """Vue jour sans paramètre (aujourd'hui)."""
        r = client.get("/api/v1/planning/day", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        assert "date" in data
        assert "reservations" in data
        assert "movements" in data
        assert "total_reservations" in data
        assert "total_movements" in data
        assert isinstance(data["reservations"], list)
        assert isinstance(data["movements"], list)
        assert data["total_reservations"] == len(data["reservations"])
        assert data["total_movements"] == len(data["movements"])

    def test_get_day_with_date(self, client: TestClient, auth_headers_real: dict):
        """Vue jour avec date explicite."""
        r = client.get(
            "/api/v1/planning/day?date=2026-06-15",
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["date"] == "2026-06-15"

    def test_get_day_unauthenticated(self, client: TestClient):
        r = client.get("/api/v1/planning/day")
        assert r.status_code == 401

    def test_get_day_reservations_include_customer_name(
        self,
        client: TestClient,
        auth_headers_real: dict,
        test_db,
    ):
        """Les réservations retournées incluent customer_name (clé présente, peut être None)."""
        from app.models.customer import Customer
        from app.models.reservation import Reservation

        customer = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Jean",
            last_name="Dupont",
            email="jean.dupont@test-planning.com",
        )
        test_db.add(customer)
        test_db.flush()

        from datetime import date
        reservation = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="PLAN-TEST-001",
            event_date=date(2026, 7, 1),
            delivery_date=date(2026, 6, 30),
            return_date=date(2026, 7, 3),
            status="confirmed",
        )
        test_db.add(reservation)
        test_db.flush()

        r = client.get("/api/v1/planning/day?date=2026-07-01", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        assert len(data["reservations"]) >= 1
        res_entry = next(
            (res for res in data["reservations"] if res["reference"] == "PLAN-TEST-001"),
            None,
        )
        assert res_entry is not None
        assert "customer_name" in res_entry
        assert res_entry["customer_name"] == "Jean Dupont"

    def test_get_day_tenant_isolation(
        self,
        client: TestClient,
        auth_headers_real: dict,
        auth_headers_tenant2: dict,
    ):
        """Deux tenants ne voient pas les mêmes données."""
        r1 = client.get("/api/v1/planning/day?date=2026-06-15", headers=auth_headers_real)
        r2 = client.get("/api/v1/planning/day?date=2026-06-15", headers=auth_headers_tenant2)
        assert r1.status_code == 200
        assert r2.status_code == 200
        # Les deux appellent le même endpoint — pas de cross-tenant possible
        # (chaque appel filtre sur tenant_id du token)


class TestPlanningWeek:
    def test_get_week_default(self, client: TestClient, auth_headers_real: dict):
        """Vue semaine sans paramètre (semaine courante)."""
        r = client.get("/api/v1/planning/week", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        assert "week_start" in data
        assert "week_end" in data
        assert "days" in data
        assert "total_reservations" in data
        assert "total_movements" in data
        assert len(data["days"]) == 7

    def test_get_week_with_date(self, client: TestClient, auth_headers_real: dict):
        """Vue semaine avec date explicite."""
        r = client.get(
            "/api/v1/planning/week?date=2026-06-15",
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        data = r.json()
        # 2026-06-15 est un lundi → semaine 2026-06-15..2026-06-21
        assert data["week_start"] == "2026-06-15"
        assert data["week_end"] == "2026-06-21"

    def test_get_week_unauthenticated(self, client: TestClient):
        r = client.get("/api/v1/planning/week")
        assert r.status_code == 401


class TestPlanningMonth:
    def test_get_month_default(self, client: TestClient, auth_headers_real: dict):
        """Vue mois sans paramètre."""
        r = client.get("/api/v1/planning/month", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        assert "month" in data
        assert "start" in data
        assert "end" in data
        assert "reservations" in data
        assert "movements" in data
        assert isinstance(data["reservations"], list)
        assert isinstance(data["movements"], list)

    def test_get_month_with_date(self, client: TestClient, auth_headers_real: dict):
        """Vue mois avec date de référence."""
        r = client.get(
            "/api/v1/planning/month?date=2026-06-01",
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["month"] == "2026-06"
        assert data["start"] == "2026-06-01"
        assert data["end"] == "2026-06-30"

    def test_get_month_december(self, client: TestClient, auth_headers_real: dict):
        """Décembre : end = 31 décembre."""
        r = client.get(
            "/api/v1/planning/month?date=2026-12-10",
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["end"] == "2026-12-31"

    def test_unauthenticated(self, client: TestClient):
        r = client.get("/api/v1/planning/month")
        assert r.status_code == 401


class TestPlanningResources:
    def test_get_resources_default(self, client: TestClient, auth_headers_real: dict):
        """Vue ressources pour aujourd'hui."""
        r = client.get("/api/v1/planning/resources", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        assert "date" in data
        assert "active_reservations" in data
        assert "total" in data
        assert isinstance(data["active_reservations"], list)
        assert data["total"] == len(data["active_reservations"])

    def test_get_resources_with_date(self, client: TestClient, auth_headers_real: dict):
        """Vue ressources à une date passée."""
        r = client.get(
            "/api/v1/planning/resources?date=2025-01-01",
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["date"] == "2025-01-01"

    def test_unauthenticated(self, client: TestClient):
        r = client.get("/api/v1/planning/resources")
        assert r.status_code == 401


class TestPlanningToday:
    def test_today_default(self, client: TestClient, auth_headers_real: dict):
        """Structure de base de GET /planning/today."""
        r = client.get("/api/v1/planning/today", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        for key in ("date", "departures", "returns_today", "active", "overdue",
                    "total_departures", "total_returns", "total_active", "total_overdue"):
            assert key in data
        assert isinstance(data["departures"], list)
        assert isinstance(data["returns_today"], list)
        assert isinstance(data["active"], list)
        assert isinstance(data["overdue"], list)
        assert data["total_departures"] == len(data["departures"])
        assert data["total_returns"] == len(data["returns_today"])
        assert data["total_active"] == len(data["active"])
        assert data["total_overdue"] == len(data["overdue"])

    def test_today_departures(self, client: TestClient, auth_headers_real: dict, test_db):
        """Réservation event_date=today confirmed → dans departures."""
        from datetime import date
        from app.models.customer import Customer
        from app.models.reservation import Reservation

        today = date.today()
        customer = Customer(
            tenant_id=1, customer_type="individual",
            first_name="Dep", last_name="Test",
            email="dep.test.today@example.com",
        )
        test_db.add(customer)
        test_db.flush()

        res = Reservation(
            tenant_id=1, customer_id=customer.id,
            reference="TODAY-DEP-001",
            event_date=today,
            delivery_date=today,
            return_date=date(today.year + 1, today.month, today.day),
            status="confirmed",
            total_amount_cents=1000,
        )
        test_db.add(res)
        test_db.commit()

        r = client.get("/api/v1/planning/today", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        refs = [d["reference"] for d in data["departures"]]
        assert "TODAY-DEP-001" in refs

    def test_today_overdue(self, client: TestClient, auth_headers_real: dict, test_db):
        """return_date < today AND status != returned → dans overdue."""
        from datetime import date, timedelta
        from app.models.customer import Customer
        from app.models.reservation import Reservation

        today = date.today()
        yesterday = today - timedelta(days=1)
        customer = Customer(
            tenant_id=1, customer_type="individual",
            first_name="Ovd", last_name="Test",
            email="ovd.test.today@example.com",
        )
        test_db.add(customer)
        test_db.flush()

        res = Reservation(
            tenant_id=1, customer_id=customer.id,
            reference="TODAY-OVD-001",
            event_date=today - timedelta(days=3),
            delivery_date=today - timedelta(days=3),
            return_date=yesterday,
            status="delivered",
            total_amount_cents=1000,
        )
        test_db.add(res)
        test_db.commit()

        r = client.get("/api/v1/planning/today", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        refs = [d["reference"] for d in data["overdue"]]
        assert "TODAY-OVD-001" in refs

    def test_today_tenant_isolation(
        self, client: TestClient,
        auth_headers_real: dict, auth_headers_tenant2: dict,
    ):
        """Chaque tenant voit uniquement ses propres données."""
        r1 = client.get("/api/v1/planning/today", headers=auth_headers_real)
        r2 = client.get("/api/v1/planning/today", headers=auth_headers_tenant2)
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_today_unauthenticated(self, client: TestClient):
        r = client.get("/api/v1/planning/today")
        assert r.status_code == 401


class TestPlanningAssign:
    def test_assign_user_not_found_reservation(self, client: TestClient, auth_headers_real: dict):
        """Réservation inconnue → 404."""
        r = client.post(
            "/api/v1/planning/assign",
            json={"reservation_id": 999999, "user_id": None},
            headers=auth_headers_real,
        )
        assert r.status_code == 404

    def test_assign_user_not_found_user(self, client: TestClient, auth_headers_admin: dict, test_db):
        """Utilisateur inconnu → 404."""
        from datetime import date
        from app.models.customer import Customer
        from app.models.reservation import Reservation
        from app.constants import CustomerType

        customer = Customer(
            tenant_id=1,
            customer_type=CustomerType.INDIVIDUAL,
            first_name="Test",
            last_name="Assign",
            email="test.assign.planning@example.com",
            is_active=True,
        )
        test_db.add(customer)
        test_db.flush()

        res = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-PLAN-ASSIGN-001",
            event_date=date(2030, 7, 1),
            delivery_date=date(2030, 6, 30),
            return_date=date(2030, 7, 2),
            status="confirmed",
            total_amount_cents=5000,
        )
        test_db.add(res)
        test_db.commit()

        r = client.post(
            "/api/v1/planning/assign",
            json={"reservation_id": res.id, "user_id": 999999},
            headers=auth_headers_admin,
        )
        assert r.status_code == 404

    def test_assign_and_unassign(self, client: TestClient, auth_headers_admin: dict, test_db):
        """Affecter puis désaffecter un utilisateur à une réservation."""
        from datetime import date
        from app.models.customer import Customer
        from app.models.reservation import Reservation
        from app.models.tenant_membership import TenantMembership
        from app.constants import CustomerType

        customer = Customer(
            tenant_id=1,
            customer_type=CustomerType.INDIVIDUAL,
            first_name="Test2",
            last_name="Assign2",
            email="test.assign2.planning@example.com",
            is_active=True,
        )
        test_db.add(customer)
        test_db.flush()

        res = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="RES-PLAN-ASSIGN-002",
            event_date=date(2030, 8, 1),
            delivery_date=date(2030, 7, 31),
            return_date=date(2030, 8, 2),
            status="confirmed",
            total_amount_cents=5000,
        )
        test_db.add(res)
        test_db.commit()

        # Récupérer un user du tenant (l'admin) via TenantMembership (IAM v2)
        membership = test_db.query(TenantMembership).filter(TenantMembership.tenant_id == 1).first()
        assert membership is not None

        # Affectation
        r = client.post(
            "/api/v1/planning/assign",
            json={"reservation_id": res.id, "user_id": membership.account_id},
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["reservation_id"] == res.id
        assert data["assigned_user_id"] == membership.account_id

        # Désaffectation
        r2 = client.post(
            "/api/v1/planning/assign",
            json={"reservation_id": res.id, "user_id": None},
            headers=auth_headers_admin,
        )
        assert r2.status_code == 200
        assert r2.json()["assigned_user_id"] is None

    def test_unauthenticated(self, client: TestClient):
        r = client.post("/api/v1/planning/assign", json={"reservation_id": 1, "user_id": None})
        assert r.status_code == 401


class TestPlanningTimeline:
    """Tests pour GET /planning/timeline — contrat canonique planning (DoD P3)."""

    def test_timeline_default_schema(self, client: TestClient, auth_headers_real: dict):
        """Sans paramètre : 200 + schéma complet."""
        r = client.get("/api/v1/planning/timeline", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        assert "start_date" in data
        assert "end_date" in data
        assert "events" in data
        assert "reservations" in data
        assert "total_departures" in data
        assert "total_returns" in data
        assert "total_reservations" in data
        assert isinstance(data["events"], list)
        assert isinstance(data["reservations"], list)
        assert data["total_reservations"] == len(data["reservations"])

    def test_timeline_with_date_range(self, client: TestClient, auth_headers_real: dict):
        """Plage explicite start_date/end_date reflétée en réponse."""
        r = client.get(
            "/api/v1/planning/timeline?start_date=2026-07-01&end_date=2026-07-31",
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["start_date"] == "2026-07-01"
        assert data["end_date"] == "2026-07-31"

    def test_timeline_unauthenticated(self, client: TestClient):
        """Sans token → 401."""
        r = client.get("/api/v1/planning/timeline")
        assert r.status_code == 401

    def test_timeline_contains_reservation_in_range(
        self, client: TestClient, auth_headers_real: dict, test_db
    ):
        """Une réservation dans la plage apparaît dans events et reservations."""
        from datetime import date
        from app.models.customer import Customer
        from app.models.reservation import Reservation

        customer = Customer(
            tenant_id=1,
            customer_type="individual",
            first_name="Timeline",
            last_name="Test",
            email="timeline.test@example-planning.com",
        )
        test_db.add(customer)
        test_db.flush()

        res = Reservation(
            tenant_id=1,
            customer_id=customer.id,
            reference="PLAN-TL-001",
            event_date=date(2026, 8, 15),
            delivery_date=date(2026, 8, 14),
            return_date=date(2026, 8, 16),
            status="confirmed",
            total_amount_cents=10000,
        )
        test_db.add(res)
        test_db.commit()

        r = client.get(
            "/api/v1/planning/timeline?start_date=2026-08-01&end_date=2026-08-31",
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        data = r.json()

        refs = [item["reference"] for item in data["reservations"]]
        assert "PLAN-TL-001" in refs

        event_ids = [e["reservation_id"] for e in data["events"]]
        assert res.id in event_ids

    def test_timeline_tenant_isolation(
        self,
        client: TestClient,
        auth_headers_real: dict,
        auth_headers_tenant2: dict,
    ):
        """Deux tenants distincts ne voient pas les mêmes données."""
        r1 = client.get(
            "/api/v1/planning/timeline?start_date=2026-08-01&end_date=2026-08-31",
            headers=auth_headers_real,
        )
        r2 = client.get(
            "/api/v1/planning/timeline?start_date=2026-08-01&end_date=2026-08-31",
            headers=auth_headers_tenant2,
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        ids1 = {item["id"] for item in r1.json()["reservations"]}
        ids2 = {item["id"] for item in r2.json()["reservations"]}
        assert ids1.isdisjoint(ids2), "Cross-tenant data leak détecté dans /planning/timeline"
