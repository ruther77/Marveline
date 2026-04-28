"""Tests d'intégration pour les endpoints audit logs (GET /audit, /audit/user, /audit/entity)."""
import pytest
from fastapi.testclient import TestClient

from app.models.audit_log import AuditLog


# ============================================================
# Helper: insérer des logs d'audit en DB
# ============================================================

def _insert_audit_logs(test_db, tenant_id: int, count: int, user_id: int, entity_type: str = "Customer") -> list[int]:
    """Insère `count` logs d'audit pour les fixtures de test."""
    ids = []
    for i in range(count):
        log = AuditLog(
            tenant_id=tenant_id,
            account_id=user_id,
            action="UPDATE" if i % 2 == 0 else "CREATE",
            entity_type=entity_type,
            entity_id=100 + i,
            description=f"Test audit log {i}",
        )
        test_db.add(log)
        test_db.flush()
        ids.append(log.id)
    test_db.commit()
    return ids


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# GET /audit — Liste tous les audit logs
# ============================================================

class TestListAuditLogs:
    """Tests pour GET /api/v1/audit."""

    def test_list_audit_logs_empty(self, client: TestClient, test_admin, auth_token_admin):
        """Admin peut lister les logs — résultat vide sans logs."""
        resp = client.get("/api/v1/audit", headers=_auth(auth_token_admin))

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert data["total"] >= 0

    def test_list_audit_logs_with_data(self, client: TestClient, test_db, test_admin, auth_token_admin):
        """Les logs insérés sont retournés."""
        _insert_audit_logs(test_db, tenant_id=1, count=3, user_id=test_admin.id)

        resp = client.get("/api/v1/audit", headers=_auth(auth_token_admin))

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        assert len(data["items"]) >= 3

    def test_list_audit_logs_paginated(self, client: TestClient, test_db, test_admin, auth_token_admin):
        """Pagination skip/limit fonctionne correctement."""
        _insert_audit_logs(test_db, tenant_id=1, count=5, user_id=test_admin.id)

        resp = client.get("/api/v1/audit?skip=0&limit=2", headers=_auth(auth_token_admin))

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["skip"] == 0
        assert data["limit"] == 2

    def test_list_audit_logs_filter_action(self, client: TestClient, test_db, test_admin, auth_token_admin):
        """Filtrage par action retourne uniquement les logs correspondants."""
        _insert_audit_logs(test_db, tenant_id=1, count=4, user_id=test_admin.id)

        resp = client.get("/api/v1/audit?action=CREATE", headers=_auth(auth_token_admin))

        assert resp.status_code == 200
        data = resp.json()
        for log in data["items"]:
            assert log["action"] == "CREATE"

    def test_list_audit_logs_filter_user_id(self, client: TestClient, test_db, test_admin, test_user, auth_token_admin):
        """Filtrage par user_id retourne uniquement les logs de cet utilisateur."""
        _insert_audit_logs(test_db, tenant_id=1, count=2, user_id=test_user.id)
        _insert_audit_logs(test_db, tenant_id=1, count=2, user_id=test_admin.id)

        resp = client.get(f"/api/v1/audit?user_id={test_user.id}", headers=_auth(auth_token_admin))

        assert resp.status_code == 200
        data = resp.json()
        for log in data["items"]:
            assert log["account_id"] == test_user.id

    def test_list_audit_logs_filter_entity_type(self, client: TestClient, test_db, test_admin, auth_token_admin):
        """Filtrage par entity_type fonctionne."""
        _insert_audit_logs(test_db, tenant_id=1, count=2, user_id=test_admin.id, entity_type="Invoice")
        _insert_audit_logs(test_db, tenant_id=1, count=2, user_id=test_admin.id, entity_type="Customer")

        resp = client.get("/api/v1/audit?entity_type=Invoice", headers=_auth(auth_token_admin))

        assert resp.status_code == 200
        data = resp.json()
        for log in data["items"]:
            assert log["entity_type"] == "Invoice"

    def test_list_audit_logs_requires_auth(self, client: TestClient):
        """Sans token → 401."""
        resp = client.get("/api/v1/audit")
        assert resp.status_code == 401

    def test_list_audit_logs_requires_audit_scope(self, client: TestClient, test_user, auth_token):
        """Staff sans scope audit:read → 403."""
        resp = client.get("/api/v1/audit", headers=_auth(auth_token))
        assert resp.status_code == 403

    def test_list_audit_logs_cross_tenant_isolation(
        self, client: TestClient, test_db, test_admin, test_admin_tenant2,
        auth_token_admin, auth_token_admin_tenant2
    ):
        """Admin tenant 1 ne voit pas les logs du tenant 2."""
        log_t2 = AuditLog(
            tenant_id=2,
            account_id=test_admin_tenant2.id,
            action="DELETE",
            entity_type="Product",
            entity_id=999,
            description="Tenant 2 only log",
        )
        test_db.add(log_t2)
        test_db.commit()

        resp = client.get("/api/v1/audit", headers=_auth(auth_token_admin))

        assert resp.status_code == 200
        data = resp.json()
        tenant_ids = {log.get("tenant_id") for log in data["items"]}
        assert 2 not in tenant_ids


# ============================================================
# GET /audit/user/{user_id} — Audit trail par utilisateur
# ============================================================

class TestUserAuditTrail:
    """Tests pour GET /api/v1/audit/user/{user_id}."""

    def test_get_user_audit_trail(self, client: TestClient, test_db, test_admin, test_user, auth_token_admin):
        """Retourne uniquement les logs de l'utilisateur cible."""
        _insert_audit_logs(test_db, tenant_id=1, count=3, user_id=test_user.id)
        _insert_audit_logs(test_db, tenant_id=1, count=2, user_id=test_admin.id)

        resp = client.get(f"/api/v1/audit/user/{test_user.id}", headers=_auth(auth_token_admin))

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        for log in data["items"]:
            assert log["account_id"] == test_user.id

    def test_user_audit_trail_cross_tenant_isolation(
        self, client: TestClient, test_db, test_admin, test_admin_tenant2,
        auth_token_admin, auth_token_admin_tenant2
    ):
        """Admin tenant 1 ne voit pas les logs tenant 2 même pour un user_id valide."""
        log_t2 = AuditLog(
            tenant_id=2,
            account_id=test_admin_tenant2.id,
            action="CREATE",
            entity_type="Customer",
            entity_id=1,
        )
        test_db.add(log_t2)
        test_db.commit()

        # Admin tenant 1 interroge le user_id de l'admin tenant 2
        resp = client.get(f"/api/v1/audit/user/{test_admin_tenant2.id}", headers=_auth(auth_token_admin))

        assert resp.status_code == 200
        data = resp.json()
        # Aucun résultat : user appartient à tenant 2, filtre tenant_id=1
        assert data["total"] == 0

    def test_user_audit_trail_requires_audit_scope(self, client: TestClient, test_user, auth_token):
        """Staff → 403."""
        resp = client.get(f"/api/v1/audit/user/{test_user.id}", headers=_auth(auth_token))
        assert resp.status_code == 403


# ============================================================
# GET /audit/entity/{entity_type}/{entity_id} — Audit trail par entité
# ============================================================

class TestEntityAuditTrail:
    """Tests pour GET /api/v1/audit/entity/{entity_type}/{entity_id}."""

    def test_get_entity_audit_trail(self, client: TestClient, test_db, test_admin, auth_token_admin):
        """Retourne uniquement les logs de l'entité cible."""
        target_entity_id = 555
        _insert_audit_logs(test_db, tenant_id=1, count=2, user_id=test_admin.id, entity_type="Reservation")
        log = AuditLog(
            tenant_id=1,
            account_id=test_admin.id,
            action="UPDATE",
            entity_type="Reservation",
            entity_id=target_entity_id,
            description="Target entity log",
        )
        test_db.add(log)
        test_db.commit()

        resp = client.get(f"/api/v1/audit/entity/Reservation/{target_entity_id}", headers=_auth(auth_token_admin))

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for log_item in data["items"]:
            assert log_item["entity_type"] == "Reservation"
            assert log_item["entity_id"] == target_entity_id

    def test_entity_audit_trail_cross_tenant_isolation(
        self, client: TestClient, test_db, test_admin, test_admin_tenant2,
        auth_token_admin
    ):
        """Admin tenant 1 ne voit pas les logs d'entités du tenant 2."""
        shared_entity_id = 777
        log_t2 = AuditLog(
            tenant_id=2,
            account_id=test_admin_tenant2.id,
            action="DELETE",
            entity_type="Product",
            entity_id=shared_entity_id,
        )
        test_db.add(log_t2)
        test_db.commit()

        resp = client.get(f"/api/v1/audit/entity/Product/{shared_entity_id}", headers=_auth(auth_token_admin))

        assert resp.status_code == 200
        data = resp.json()
        tenant_ids = {log.get("tenant_id") for log in data["items"]}
        assert 2 not in tenant_ids

    def test_entity_audit_trail_requires_audit_scope(self, client: TestClient, test_user, auth_token):
        """Staff → 403."""
        resp = client.get("/api/v1/audit/entity/Customer/1", headers=_auth(auth_token))
        assert resp.status_code == 403
