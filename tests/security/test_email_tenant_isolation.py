"""Tests sécurité : isolation email par tenant + audit tenant + case sensitivity.

Couvre les fixes:
- M17: UniqueConstraint("tenant_id", "email") au lieu de unique global
- M18: SYSTEM_TENANT_ID=0 pour audit login failed sans tenant connu
- M22: .lower().strip() + == au lieu de ilike
- M23: user.tenant_id == payload["tenant_id"] dans get_current_user
"""
import pytest
from sqlalchemy import text
from app.models.user import User
from app.core.security import get_password_hash, create_access_token
from app.constants import SYSTEM_TENANT_ID


class TestEmailTenantIsolation:
    """M17: Même email autorisé dans 2 tenants différents, interdit dans même tenant."""

    def test_same_email_different_tenants_allowed(self, test_db):
        """Deux tenants peuvent avoir le même email."""
        user1 = User(
            tenant_id=1,
            email="shared@example.com",
            hashed_password=get_password_hash("testpass123"),
            full_name="User Tenant 1",
            role="staff",
            is_active=True,
        )
        user2 = User(
            tenant_id=2,
            email="shared@example.com",
            hashed_password=get_password_hash("testpass123"),
            full_name="User Tenant 2",
            role="staff",
            is_active=True,
        )
        test_db.add(user1)
        test_db.commit()
        test_db.add(user2)
        test_db.commit()  # Should NOT raise IntegrityError

        # Verify both exist
        count = test_db.query(User).filter(User.email == "shared@example.com").count()
        assert count == 2

    def test_same_email_same_tenant_rejected(self, test_db):
        """Même tenant ne peut pas avoir 2 users avec le même email."""
        from sqlalchemy.exc import IntegrityError

        user1 = User(
            tenant_id=1,
            email="duplicate@example.com",
            hashed_password=get_password_hash("testpass123"),
            full_name="User 1",
            role="staff",
            is_active=True,
        )
        test_db.add(user1)
        test_db.commit()

        user2 = User(
            tenant_id=1,
            email="duplicate@example.com",
            hashed_password=get_password_hash("testpass456"),
            full_name="User 2",
            role="staff",
            is_active=True,
        )
        test_db.add(user2)
        with pytest.raises(IntegrityError):
            test_db.commit()
        test_db.rollback()


class TestAuditTenantId:
    """M18: Login failed sans tenant connu utilise SYSTEM_TENANT_ID=0."""

    def test_system_tenant_id_is_zero(self):
        """SYSTEM_TENANT_ID doit être 0."""
        assert SYSTEM_TENANT_ID == 0

    def test_login_failed_unknown_user_audit_uses_system_tenant(self, client, test_db):
        """Login failed pour user inconnu doit auditer avec SYSTEM_TENANT_ID."""
        from app.models.audit_log import AuditLog

        response = client.post(
            "/api/v1/auth/login",
            data={"username": "nobody@example.com", "password": "wrongpass123"},
        )
        assert response.status_code == 401

        # Vérifier que l'audit log utilise SYSTEM_TENANT_ID
        audit = (
            test_db.query(AuditLog)
            .filter(AuditLog.action == "LOGIN_FAILED")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert audit is not None
        assert audit.tenant_id == SYSTEM_TENANT_ID


class TestEmailCaseSensitivity:
    """M22: Email normalisé en lowercase, pas d'ilike."""

    def test_login_case_insensitive(self, client, test_user):
        """Login avec email en majuscules doit fonctionner."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "TEST@CAROCORP.COM", "password": "testpass123"},
        )
        assert response.status_code == 200

    def test_login_with_spaces(self, client, test_user):
        """Login avec espaces autour de l'email doit fonctionner."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "  test@carocorp.com  ", "password": "testpass123"},
        )
        assert response.status_code == 200


class TestTenantIdJwtValidation:
    """M23: get_current_user vérifie tenant_id du JWT vs DB."""

    def test_tampered_tenant_id_in_jwt_rejected(self, client, test_user):
        """JWT avec tenant_id falsifié doit être rejeté."""
        from tests.conftest import csrf_token_for_user

        # Créer un token avec tenant_id=999 (falsifié)
        tampered_token = create_access_token({
            "sub": test_user.id,
            "tenant_id": 999,
            "email": test_user.email,
            "role": test_user.role,
        })
        csrf = csrf_token_for_user(test_user.id)

        response = client.get(
            "/api/v1/products",
            headers={
                "Authorization": f"Bearer {tampered_token}",
                "X-CSRF-Token": csrf,
            },
        )
        assert response.status_code == 401

    def test_valid_tenant_id_in_jwt_accepted(self, client, test_user):
        """JWT avec tenant_id correct doit être accepté."""
        from tests.conftest import csrf_token_for_user

        valid_token = create_access_token({
            "sub": test_user.id,
            "tenant_id": test_user.tenant_id,
            "email": test_user.email,
            "role": test_user.role,
        })
        csrf = csrf_token_for_user(test_user.id)

        response = client.get(
            "/api/v1/products",
            headers={
                "Authorization": f"Bearer {valid_token}",
                "X-CSRF-Token": csrf,
            },
        )
        assert response.status_code == 200
