"""Tests E2E pour endpoints /api/v1/audit (admin uniquement)."""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.models.audit_log import AuditLog
from app.services.audit import AuditService


class TestAuditEndpointsE2E:
    """Tests E2E endpoints audit logs."""

    def test_list_audit_logs_admin(
        self,
        client: TestClient,
        test_db,
        auth_headers_admin
    ):
        """GET /audit retourne liste logs (admin only)."""
        # Créer quelques audit logs
        audit_service = AuditService(test_db)
        audit_service.log_action(action="CREATE", tenant_id=1, user_id=1, entity_type="Customer", entity_id=100)
        audit_service.log_action(action="UPDATE", tenant_id=1, user_id=1, entity_type="Customer", entity_id=100)
        audit_service.log_action(action="DELETE", tenant_id=1, user_id=1, entity_type="Customer", entity_id=100)
        test_db.commit()

        response = client.get(
            "/api/v1/audit?skip=0&limit=10",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        data = response.json()

        assert "logs" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert data["skip"] == 0
        assert data["limit"] == 10
        assert len(data["logs"]) >= 3
        assert all("id" in log for log in data["logs"])
        assert all("action" in log for log in data["logs"])
        assert all("tenant_id" in log for log in data["logs"])

    def test_list_audit_logs_non_admin_403(
        self,
        client: TestClient,
        test_db,
        auth_headers_real  # User staff non admin
    ):
        """GET /audit par non-admin retourne 403."""
        response = client.get(
            "/api/v1/audit",
            headers=auth_headers_real
        )

        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "permissions" in detail.lower() or "audit:read" in detail

    def test_list_audit_logs_filter_by_action(
        self,
        client: TestClient,
        test_db,
        auth_headers_admin
    ):
        """GET /audit avec filtre action."""
        audit_service = AuditService(test_db)
        audit_service.log_action(action="CREATE", tenant_id=1)
        audit_service.log_action(action="CREATE", tenant_id=1)
        audit_service.log_action(action="UPDATE", tenant_id=1)
        audit_service.log_action(action="DELETE", tenant_id=1)
        test_db.commit()

        response = client.get(
            "/api/v1/audit?action=CREATE&limit=100",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        data = response.json()

        create_logs = [log for log in data["logs"] if log["action"] == "CREATE"]
        assert len(create_logs) >= 2
        assert all(log["action"] == "CREATE" for log in create_logs)

    def test_list_audit_logs_filter_by_user_id(
        self,
        client: TestClient,
        test_db,
        auth_headers_admin
    ):
        """GET /audit avec filtre user_id."""
        audit_service = AuditService(test_db)
        audit_service.log_action(action="CREATE", tenant_id=1, user_id=42)
        audit_service.log_action(action="UPDATE", tenant_id=1, user_id=42)
        audit_service.log_action(action="DELETE", tenant_id=1, user_id=99)
        test_db.commit()

        response = client.get(
            "/api/v1/audit?user_id=42&limit=100",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        data = response.json()

        user42_logs = [log for log in data["logs"] if log["user_id"] == 42]
        assert len(user42_logs) >= 2
        assert all(log["user_id"] == 42 for log in user42_logs)

    def test_list_audit_logs_filter_by_entity_type(
        self,
        client: TestClient,
        test_db,
        auth_headers_admin
    ):
        """GET /audit avec filtre entity_type."""
        audit_service = AuditService(test_db)
        audit_service.log_action(action="CREATE", tenant_id=1, entity_type="Customer", entity_id=1)
        audit_service.log_action(action="CREATE", tenant_id=1, entity_type="Customer", entity_id=2)
        audit_service.log_action(action="CREATE", tenant_id=1, entity_type="Product", entity_id=1)
        test_db.commit()

        response = client.get(
            "/api/v1/audit?entity_type=Customer&limit=100",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        data = response.json()

        customer_logs = [log for log in data["logs"] if log["entity_type"] == "Customer"]
        assert len(customer_logs) >= 2
        assert all(log["entity_type"] == "Customer" for log in customer_logs)

    def test_list_audit_logs_filter_by_date_range(
        self,
        client: TestClient,
        test_db,
        auth_headers_admin
    ):
        """GET /audit avec filtres date (start_date, end_date)."""
        audit_service = AuditService(test_db)
        audit_service.log_action(action="CREATE", tenant_id=1)
        test_db.commit()

        now = datetime.now(timezone.utc)
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=0)

        # Passer params comme dict pour encodage URL correct
        response = client.get(
            "/api/v1/audit",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "limit": 100
            },
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) >= 1

    def test_list_audit_logs_pagination(
        self,
        client: TestClient,
        test_db,
        auth_headers_admin
    ):
        """GET /audit pagination fonctionne."""
        audit_service = AuditService(test_db)
        for i in range(15):
            audit_service.log_action(action="CREATE", tenant_id=1, entity_id=i)
        test_db.commit()

        # Page 1
        response_p1 = client.get(
            "/api/v1/audit?skip=0&limit=10",
            headers=auth_headers_admin
        )
        assert response_p1.status_code == 200
        data_p1 = response_p1.json()
        assert len(data_p1["logs"]) == 10
        assert data_p1["skip"] == 0
        assert data_p1["limit"] == 10
        assert data_p1["total"] >= 15

        # Page 2
        response_p2 = client.get(
            "/api/v1/audit?skip=10&limit=10",
            headers=auth_headers_admin
        )
        assert response_p2.status_code == 200
        data_p2 = response_p2.json()
        assert len(data_p2["logs"]) >= 5
        assert data_p2["skip"] == 10

        # Vérifier pas de duplication entre pages
        ids_p1 = {log["id"] for log in data_p1["logs"]}
        ids_p2 = {log["id"] for log in data_p2["logs"]}
        assert len(ids_p1.intersection(ids_p2)) == 0

    def test_get_user_audit_trail(
        self,
        client: TestClient,
        test_db,
        auth_headers_admin
    ):
        """GET /audit/user/{user_id} retourne audit trail utilisateur."""
        audit_service = AuditService(test_db)
        audit_service.log_action(action="CREATE", tenant_id=1, user_id=42, entity_type="Customer", entity_id=1)
        audit_service.log_action(action="UPDATE", tenant_id=1, user_id=42, entity_type="Customer", entity_id=1)
        audit_service.log_action(action="DELETE", tenant_id=1, user_id=99, entity_type="Product", entity_id=1)
        test_db.commit()

        response = client.get(
            "/api/v1/audit/user/42?limit=100",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        data = response.json()

        assert "logs" in data
        assert "total" in data
        user42_logs = [log for log in data["logs"] if log["user_id"] == 42]
        assert len(user42_logs) >= 2
        assert all(log["user_id"] == 42 for log in user42_logs)
        assert all(log["tenant_id"] == 1 for log in user42_logs)

    def test_get_user_audit_trail_non_admin_403(
        self,
        client: TestClient,
        auth_headers_real
    ):
        """GET /audit/user/{user_id} par non-admin retourne 403."""
        response = client.get(
            "/api/v1/audit/user/42",
            headers=auth_headers_real
        )

        assert response.status_code == 403

    def test_get_entity_audit_trail(
        self,
        client: TestClient,
        test_db,
        auth_headers_admin
    ):
        """GET /audit/entity/{entity_type}/{entity_id} retourne historique entité."""
        audit_service = AuditService(test_db)
        audit_service.log_action(action="CREATE", tenant_id=1, entity_type="Reservation", entity_id=456)
        audit_service.log_action(action="UPDATE", tenant_id=1, entity_type="Reservation", entity_id=456)
        audit_service.log_action(action="UPDATE", tenant_id=1, entity_type="Reservation", entity_id=456)
        audit_service.log_action(action="DELETE", tenant_id=1, entity_type="Reservation", entity_id=456)
        test_db.commit()

        response = client.get(
            "/api/v1/audit/entity/Reservation/456?limit=100",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        data = response.json()

        assert "logs" in data
        assert "total" in data
        res456_logs = [log for log in data["logs"] if log["entity_id"] == 456 and log["entity_type"] == "Reservation"]
        assert len(res456_logs) >= 4
        assert all(log["entity_type"] == "Reservation" for log in res456_logs)
        assert all(log["entity_id"] == 456 for log in res456_logs)

    def test_get_entity_audit_trail_non_admin_403(
        self,
        client: TestClient,
        auth_headers_real
    ):
        """GET /audit/entity/{entity_type}/{entity_id} par non-admin retourne 403."""
        response = client.get(
            "/api/v1/audit/entity/Reservation/456",
            headers=auth_headers_real
        )

        assert response.status_code == 403

    def test_audit_multi_tenant_isolation(
        self,
        client: TestClient,
        test_db,
        auth_headers_admin,
        auth_headers_admin_tenant2
    ):
        """Endpoints audit isolent strictement par tenant_id."""
        audit_service = AuditService(test_db)
        # Logs tenant 1
        audit_service.log_action(action="CREATE", tenant_id=1, user_id=1, entity_type="Customer", entity_id=100)
        audit_service.log_action(action="UPDATE", tenant_id=1, user_id=1, entity_type="Customer", entity_id=100)

        # Logs tenant 2
        audit_service.log_action(action="CREATE", tenant_id=2, user_id=2, entity_type="Customer", entity_id=200)
        audit_service.log_action(action="UPDATE", tenant_id=2, user_id=2, entity_type="Customer", entity_id=200)

        test_db.commit()

        # Admin tenant 1 voit seulement logs tenant 1
        response_t1 = client.get(
            "/api/v1/audit?limit=100",
            headers=auth_headers_admin
        )
        assert response_t1.status_code == 200
        logs_t1 = response_t1.json()["logs"]
        tenant1_logs = [log for log in logs_t1 if log.get("entity_id") in [100, 200]]
        assert all(log["tenant_id"] == 1 for log in tenant1_logs)
        assert any(log["entity_id"] == 100 for log in tenant1_logs)
        assert not any(log["entity_id"] == 200 for log in tenant1_logs)

        # Admin tenant 2 voit seulement logs tenant 2
        response_t2 = client.get(
            "/api/v1/audit?limit=100",
            headers=auth_headers_admin_tenant2
        )
        assert response_t2.status_code == 200
        logs_t2 = response_t2.json()["logs"]
        tenant2_logs = [log for log in logs_t2 if log.get("entity_id") in [100, 200]]
        assert all(log["tenant_id"] == 2 for log in tenant2_logs)
        assert any(log["entity_id"] == 200 for log in tenant2_logs)
        assert not any(log["entity_id"] == 100 for log in tenant2_logs)

    def test_audit_logs_unauthenticated_401(self, client: TestClient):
        """GET /audit sans auth retourne 401."""
        response = client.get("/api/v1/audit")
        assert response.status_code == 401

    def test_audit_logs_order_desc_created_at(
        self,
        client: TestClient,
        test_db,
        auth_headers_admin
    ):
        """GET /audit retourne logs triés par created_at DESC (plus récent en premier)."""
        audit_service = AuditService(test_db)
        log1 = audit_service.log_action(action="CREATE", tenant_id=1, entity_id=1)
        test_db.commit()
        test_db.refresh(log1)

        import time
        time.sleep(0.1)  # Attendre pour différencier timestamps

        log2 = audit_service.log_action(action="UPDATE", tenant_id=1, entity_id=2)
        test_db.commit()
        test_db.refresh(log2)

        response = client.get(
            "/api/v1/audit?limit=100",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        logs = response.json()["logs"]

        # Trouver nos logs
        our_logs = [log for log in logs if log["id"] in [log1.id, log2.id]]
        assert len(our_logs) == 2

        # Vérifier ordre décroissant (log2 plus récent devant)
        if len(our_logs) == 2:
            first_log = next(log for log in our_logs if log["id"] == log2.id)
            second_log = next(log for log in our_logs if log["id"] == log1.id)
            first_index = logs.index(first_log)
            second_index = logs.index(second_log)
            assert first_index < second_index  # Plus récent en premier
