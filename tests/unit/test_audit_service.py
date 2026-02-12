"""Tests unitaires pour AuditService."""
import pytest
from app.services.audit import AuditService
from app.models.audit_log import AuditLog


class TestAuditService:
    """Tests pour service d'audit log."""

    def test_log_action_generic(self, test_db):
        """log_action() crée audit log générique."""
        audit_service = AuditService(test_db)

        log = audit_service.log_action(
            action="CUSTOM_ACTION",
            tenant_id=1,
            user_id=42,
            entity_type="Product",
            entity_id=123,
            changes={"custom": "data"},
            description="Custom action description",
            ip_address="192.168.1.100",
            user_agent="TestAgent",
            request_id="test-request-id-123"
        )

        test_db.commit()
        test_db.refresh(log)

        assert log.id is not None
        assert log.action == "CUSTOM_ACTION"
        assert log.tenant_id == 1
        assert log.user_id == 42
        assert log.entity_type == "Product"
        assert log.entity_id == 123
        assert log.changes == {"custom": "data"}
        assert log.description == "Custom action description"
        assert log.ip_address == "192.168.1.100"
        assert log.user_agent == "TestAgent"
        assert log.request_id == "test-request-id-123"

    def test_log_action_auto_generates_request_id(self, test_db):
        """log_action() génère UUID request_id si absent."""
        audit_service = AuditService(test_db)

        log = audit_service.log_action(
            action="CREATE",
            tenant_id=1,
            request_id=None  # Pas fourni
        )

        test_db.commit()
        test_db.refresh(log)

        assert log.request_id is not None
        assert len(log.request_id) == 36  # UUID format

    def test_log_create(self, test_db):
        """log_create() enregistre création entité."""
        audit_service = AuditService(test_db)

        entity_data = {
            "customer_type": "individual",
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "jean.dupont@example.com"
        }

        log = audit_service.log_create(
            entity_type="Customer",
            entity_id=123,
            entity_data=entity_data,
            tenant_id=1,
            user_id=42,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            request_id="req-create-123"
        )

        test_db.commit()
        test_db.refresh(log)

        assert log.action == "CREATE"
        assert log.entity_type == "Customer"
        assert log.entity_id == 123
        assert log.changes == {"after": entity_data}
        assert log.description == "Created Customer #123"
        assert log.user_id == 42
        assert log.tenant_id == 1

    def test_log_update_with_diff(self, test_db):
        """log_update() calcule diff automatique (before/after)."""
        audit_service = AuditService(test_db)

        before = {
            "status": "draft",
            "total_amount": 10000,
            "notes": "Old notes",
            "unchanged_field": "same"
        }

        after = {
            "status": "confirmed",
            "total_amount": 12000,
            "notes": "New notes",
            "unchanged_field": "same"
        }

        log = audit_service.log_update(
            entity_type="Reservation",
            entity_id=456,
            before=before,
            after=after,
            tenant_id=1,
            user_id=42,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            request_id="req-update-456"
        )

        test_db.commit()
        test_db.refresh(log)

        assert log.action == "UPDATE"
        assert log.entity_type == "Reservation"
        assert log.entity_id == 456

        # Vérifier que seuls les champs modifiés sont dans changes
        assert "status" in log.changes
        assert log.changes["status"] == {"before": "draft", "after": "confirmed"}
        assert "total_amount" in log.changes
        assert log.changes["total_amount"] == {"before": 10000, "after": 12000}
        assert "notes" in log.changes
        assert "unchanged_field" not in log.changes  # Pas de diff si identique

        assert log.description == "Updated Reservation #456: status, total_amount, notes"

    def test_log_update_no_changes(self, test_db):
        """log_update() avec aucun changement crée log vide."""
        audit_service = AuditService(test_db)

        before = {"field1": "value1", "field2": "value2"}
        after = {"field1": "value1", "field2": "value2"}

        log = audit_service.log_update(
            entity_type="Product",
            entity_id=789,
            before=before,
            after=after,
            tenant_id=1,
            user_id=42,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            request_id="req-noop-789"
        )

        test_db.commit()
        test_db.refresh(log)

        assert log.action == "UPDATE"
        assert log.changes == {}  # Aucun champ modifié
        assert log.description == "Updated Product #789: "

    def test_log_delete_soft(self, test_db):
        """log_delete() avec soft_delete=True."""
        audit_service = AuditService(test_db)

        entity_data = {
            "email": "deleted@example.com",
            "is_active": True
        }

        log = audit_service.log_delete(
            entity_type="Customer",
            entity_id=999,
            entity_data=entity_data,
            tenant_id=1,
            user_id=42,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            request_id="req-soft-delete-999",
            soft_delete=True
        )

        test_db.commit()
        test_db.refresh(log)

        assert log.action == "SOFT_DELETE"
        assert log.entity_type == "Customer"
        assert log.entity_id == 999
        assert log.changes == {"before": entity_data}
        assert log.description == "Soft deleted Customer #999"

    def test_log_delete_hard(self, test_db):
        """log_delete() avec soft_delete=False."""
        audit_service = AuditService(test_db)

        entity_data = {"email": "deleted@example.com"}

        log = audit_service.log_delete(
            entity_type="Customer",
            entity_id=888,
            entity_data=entity_data,
            tenant_id=1,
            user_id=42,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            request_id="req-hard-delete-888",
            soft_delete=False
        )

        test_db.commit()
        test_db.refresh(log)

        assert log.action == "HARD_DELETE"
        assert log.description == "Hard deleted Customer #888"

    def test_log_read_sensitive(self, test_db):
        """log_read_sensitive() pour conformité RGPD."""
        audit_service = AuditService(test_db)

        log = audit_service.log_read_sensitive(
            entity_type="Customer",
            entity_id=123,
            tenant_id=1,
            user_id=42,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            request_id="req-read-123"
        )

        test_db.commit()
        test_db.refresh(log)

        assert log.action == "READ_SENSITIVE"
        assert log.entity_type == "Customer"
        assert log.entity_id == 123
        assert log.description == "Accessed sensitive data Customer #123"
        assert log.changes is None  # Pas de modifications pour lecture

    def test_log_login_success(self, test_db):
        """log_login() avec success=True."""
        audit_service = AuditService(test_db)

        log = audit_service.log_login(
            user_id=42,
            tenant_id=1,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            request_id="req-login-success",
            success=True,
            email="user@example.com"
        )

        test_db.commit()
        test_db.refresh(log)

        assert log.action == "LOGIN_SUCCESS"
        assert log.user_id == 42
        assert log.tenant_id == 1
        assert log.description == "Login successful for user@example.com"

    def test_log_login_failed(self, test_db):
        """log_login() avec success=False."""
        audit_service = AuditService(test_db)

        log = audit_service.log_login(
            user_id=None,  # User non trouvé
            tenant_id=1,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            request_id="req-login-failed",
            success=False,
            email="attacker@example.com"
        )

        test_db.commit()
        test_db.refresh(log)

        assert log.action == "LOGIN_FAILED"
        assert log.user_id is None
        assert log.description == "Login failed for attacker@example.com"

    def test_log_logout(self, test_db):
        """log_logout() enregistre déconnexion."""
        audit_service = AuditService(test_db)

        log = audit_service.log_logout(
            user_id=42,
            tenant_id=1,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            request_id="req-logout"
        )

        test_db.commit()
        test_db.refresh(log)

        assert log.action == "LOGOUT"
        assert log.user_id == 42
        assert log.description == "User logged out"

    def test_audit_multi_tenant_isolation(self, test_db):
        """Audit logs isolés par tenant_id."""
        audit_service = AuditService(test_db)

        # Logs tenant 1
        log_t1_1 = audit_service.log_action(action="CREATE", tenant_id=1, user_id=10)
        log_t1_2 = audit_service.log_action(action="UPDATE", tenant_id=1, user_id=10)

        # Logs tenant 2
        log_t2_1 = audit_service.log_action(action="CREATE", tenant_id=2, user_id=20)
        log_t2_2 = audit_service.log_action(action="DELETE", tenant_id=2, user_id=20)

        test_db.commit()

        # Query tenant 1 uniquement
        logs_tenant1 = test_db.query(AuditLog).filter(AuditLog.tenant_id == 1).all()
        assert len([l for l in logs_tenant1 if l.user_id == 10]) >= 2

        # Query tenant 2 uniquement
        logs_tenant2 = test_db.query(AuditLog).filter(AuditLog.tenant_id == 2).all()
        assert len([l for l in logs_tenant2 if l.user_id == 20]) >= 2

        # Vérifier isolation stricte
        assert all(log.tenant_id == 1 for log in logs_tenant1 if log.user_id == 10)
        assert all(log.tenant_id == 2 for log in logs_tenant2 if log.user_id == 20)
