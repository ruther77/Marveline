"""Tests d'intégration — IAM v2 endpoints (POST /auth/v2/login, refresh, logout, GET /me).

Fixtures locales : Tenant + Account + TenantMembership (distinct du User legacy).
Anti-cross-tenant : test_login_wrong_tenant vérifie l'isolation par membership.
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.models.account import Account
from app.models.auth_role import AuthRole
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership

_TENANT_DOMAIN_PREFIX = "auth-v2-test"
_ACCOUNT_EMAIL = "iam2@carocorp-test.com"
_ACCOUNT_PASSWORD = "SecureIAM2Pass!"
_ROLE = "staff"


@pytest.fixture
def test_tenant_v2(test_db):
    """Tenant actif pour tests IAM v2."""
    tenant = Tenant(
        external_id=str(uuid.uuid4()),
        name="Tenant IAM v2 Test",
        domain=f"{_TENANT_DOMAIN_PREFIX}-{uuid.uuid4().hex[:8]}.test",
        contact_email="contact@iamv2test.example.com",
        app_code="marveline",
        status="active",
        plan="standard",
        is_active=True,
    )
    test_db.add(tenant)
    test_db.commit()
    test_db.refresh(tenant)
    return tenant


@pytest.fixture
def test_account_v2(test_db):
    """Account global pour tests IAM v2 (email unique par exécution)."""
    account = Account(
        email=f"iam2-{uuid.uuid4().hex[:6]}@carocorp-test.com",
        hashed_password=get_password_hash(_ACCOUNT_PASSWORD),
        first_name="IAM",
        last_name="V2User",
        is_active=True,
        password_change_required=False,
    )
    test_db.add(account)
    test_db.commit()
    test_db.refresh(account)
    return account


@pytest.fixture
def test_role_staff(test_db):
    """Insère le rôle 'staff' dans auth_roles (table statique truncatée par clean_db)."""
    existing = test_db.get(AuthRole, "staff")
    if not existing:
        role = AuthRole(
            name="staff",
            level=4,
            is_system=False,
            mfa_required=False,
            description="Staff opérationnel",
        )
        test_db.add(role)
        test_db.commit()
    return test_db.get(AuthRole, "staff")


@pytest.fixture
def test_membership_v2(test_db, test_account_v2, test_tenant_v2, test_role_staff):
    """TenantMembership actif liant account + tenant."""
    membership = TenantMembership(
        account_id=test_account_v2.id,
        tenant_id=test_tenant_v2.id,
        role_name=_ROLE,
        status="active",
    )
    test_db.add(membership)
    test_db.commit()
    test_db.refresh(membership)
    return membership


@pytest.fixture
def v2_auth_headers(test_account_v2, test_membership_v2):
    """Headers Authorization avec token JWT IAM v2 (sans mise en Redis — pour /me)."""
    claims = {
        "sub": str(test_account_v2.id),
        "tid": str(test_membership_v2.tenant_id),
        "mid": str(test_membership_v2.id),
        "did": "test-device-v2",
        "sid": str(uuid.uuid4()),
        "role": _ROLE,
    }
    token = create_access_token(claims)
    return {"Authorization": f"Bearer {token}"}


def _login_v2(client, email, password, tenant_id, **extra):
    """Helper POST /auth/v2/login."""
    return client.post(
        "/api/v1/auth/v2/login",
        json={"email": email, "password": password, "tenant_id": tenant_id, **extra},
    )


class TestLoginV2:
    """POST /auth/v2/login — authentification IAM v2."""

    def test_login_success(self, client: TestClient, test_membership_v2, test_account_v2, test_tenant_v2):
        """Login valide → 200 + access_token + cookie refresh."""
        resp = _login_v2(client, test_account_v2.email, _ACCOUNT_PASSWORD, test_tenant_v2.id)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert "refresh_token" in resp.cookies  # cookie httpOnly

    def test_login_wrong_password(self, client: TestClient, test_membership_v2, test_account_v2, test_tenant_v2):
        """Mauvais password → 401."""
        resp = _login_v2(client, test_account_v2.email, "wrong-password!", test_tenant_v2.id)
        assert resp.status_code == 401

    def test_login_unknown_email(self, client: TestClient, test_tenant_v2):
        """Email inconnu → 401 (pas 404 — anti-énumération)."""
        resp = _login_v2(client, "nobody@no-domain.example", "anypass!", test_tenant_v2.id)
        assert resp.status_code == 401

    def test_login_inactive_account(self, client: TestClient, test_db, test_account_v2, test_membership_v2, test_tenant_v2):
        """Compte inactif → 403."""
        test_account_v2.is_active = False
        test_db.commit()
        try:
            resp = _login_v2(client, test_account_v2.email, _ACCOUNT_PASSWORD, test_tenant_v2.id)
            assert resp.status_code == 403
        finally:
            test_account_v2.is_active = True
            test_db.commit()

    def test_login_no_membership_in_tenant(self, client: TestClient, test_db, test_account_v2, test_tenant_v2):
        """Account valide mais pas de membership pour ce tenant → 401/403."""
        # Créer un second tenant sans membership pour cet account
        other_tenant = Tenant(
            external_id=str(uuid.uuid4()),
            name="Other Tenant v2",
            domain=f"other-{uuid.uuid4().hex[:8]}.test",
            contact_email="x@other.example",
            app_code="marveline",
            status="active",
            is_active=True,
        )
        test_db.add(other_tenant)
        test_db.commit()
        test_db.refresh(other_tenant)

        resp = _login_v2(client, test_account_v2.email, _ACCOUNT_PASSWORD, other_tenant.id)
        # Membership inexistant → MembershipService.require_active lève 401 ou 403
        assert resp.status_code in (401, 403)

    def test_login_missing_fields(self, client: TestClient):
        """Body incomplet → 422 Pydantic validation."""
        resp = client.post("/api/v1/auth/v2/login", json={"email": "x@x.com"})
        assert resp.status_code == 422

    def test_login_v2_json_not_form(self, client: TestClient, test_membership_v2, test_account_v2, test_tenant_v2):
        """Login v2 accepte JSON, pas form-encoded."""
        resp = client.post(
            "/api/v1/auth/v2/login",
            data={
                "username": test_account_v2.email,
                "password": _ACCOUNT_PASSWORD,
            },
        )
        # form-encoded → 422 (LoginV2Request attend JSON)
        assert resp.status_code == 422


class TestRefreshV2:
    """POST /auth/v2/refresh — rotation token IAM v2."""

    def test_refresh_missing_cookie(self, client: TestClient):
        """Sans cookie → 401."""
        resp = client.post("/api/v1/auth/v2/refresh")
        assert resp.status_code == 401

    def test_refresh_after_login(self, client: TestClient, test_membership_v2, test_account_v2, test_tenant_v2):
        """Login → refresh → nouveau access_token."""
        login_resp = _login_v2(client, test_account_v2.email, _ACCOUNT_PASSWORD, test_tenant_v2.id)
        assert login_resp.status_code == 200

        client.cookies.update(login_resp.cookies)
        refresh_resp = client.post("/api/v1/auth/v2/refresh")
        assert refresh_resp.status_code == 200
        data = refresh_resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        # Nouveau cookie refresh émis
        assert "refresh_token" in refresh_resp.cookies


class TestLogoutV2:
    """POST /auth/v2/logout — révocation tokens IAM v2."""

    def test_logout_clears_cookie(self, client: TestClient, test_membership_v2, test_account_v2, test_tenant_v2):
        """Login → logout → cookie refresh effacé."""
        login_resp = _login_v2(client, test_account_v2.email, _ACCOUNT_PASSWORD, test_tenant_v2.id)
        assert login_resp.status_code == 200

        access_token = login_resp.json()["access_token"]
        client.cookies.update(login_resp.cookies)
        logout_resp = client.post(
            "/api/v1/auth/v2/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert logout_resp.status_code == 200
        assert logout_resp.json()["tokens_revoked"] is True
        # Set-Cookie avec Max-Age=0 supprime le cookie
        assert "refresh_token" not in logout_resp.cookies or logout_resp.cookies.get("refresh_token") == ""

    def test_logout_without_token(self, client: TestClient):
        """Sans Authorization header → 401 (dep CurrentAccount)."""
        resp = client.post("/api/v1/auth/v2/logout")
        assert resp.status_code == 401


class TestMeV2:
    """GET /auth/v2/me — informations compte IAM v2."""

    def test_me_returns_account_info(self, client: TestClient, v2_auth_headers, test_account_v2, test_membership_v2):
        """Token valide → AccountInfo complet."""
        resp = client.get("/api/v1/auth/v2/me", headers=v2_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["account_id"] == test_account_v2.id
        assert data["email"] == test_account_v2.email
        assert data["first_name"] == test_account_v2.first_name
        assert data["last_name"] == test_account_v2.last_name
        assert data["tenant_id"] == test_membership_v2.tenant_id
        assert data["membership_id"] == test_membership_v2.id
        assert data["role_name"] == _ROLE
        assert isinstance(data["scopes"], list)

    def test_me_no_token(self, client: TestClient):
        """Sans token → 401."""
        resp = client.get("/api/v1/auth/v2/me")
        assert resp.status_code == 401


class TestCrossTenantV2:
    """Isolation multi-tenant — un account ne peut pas accéder à un autre tenant."""

    def test_login_cross_tenant_blocked(self, client: TestClient, test_db, test_account_v2, test_tenant_v2, test_membership_v2):
        """Account du tenant A ne peut pas se connecter au tenant B."""
        tenant_b = Tenant(
            external_id=str(uuid.uuid4()),
            name="Tenant B",
            domain=f"tenant-b-{uuid.uuid4().hex[:8]}.test",
            contact_email="b@tenantb.example",
            app_code="marveline",
            status="active",
            is_active=True,
        )
        test_db.add(tenant_b)
        test_db.commit()
        test_db.refresh(tenant_b)

        # Account n'a de membership que dans test_tenant_v2, pas dans tenant_b
        resp = _login_v2(client, test_account_v2.email, _ACCOUNT_PASSWORD, tenant_b.id)
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 for cross-tenant login, got {resp.status_code}"
        )


class TestSwitchMembershipV2:
    """POST /auth/v2/switch-membership — changement de tenant actif (access token uniquement)."""

    def test_switch_success(
        self,
        client: TestClient,
        test_db,
        test_account_v2,
        test_tenant_v2,
        test_membership_v2,
        test_role_staff,
    ):
        """Login tenant A → switch tenant B → 200 + nouvel access_token."""
        tenant_b = Tenant(
            external_id=str(uuid.uuid4()),
            name="Tenant B Switch",
            domain=f"switch-b-{uuid.uuid4().hex[:8]}.test",
            contact_email="b@switch.example",
            app_code="marveline",
            status="active",
            is_active=True,
        )
        test_db.add(tenant_b)
        test_db.commit()
        test_db.refresh(tenant_b)

        membership_b = TenantMembership(
            account_id=test_account_v2.id,
            tenant_id=tenant_b.id,
            role_name=_ROLE,
            status="active",
        )
        test_db.add(membership_b)
        test_db.commit()

        login_resp = _login_v2(client, test_account_v2.email, _ACCOUNT_PASSWORD, test_tenant_v2.id)
        assert login_resp.status_code == 200
        client.cookies.update(login_resp.cookies)

        resp = client.post("/api/v1/auth/v2/switch-membership", json={"tenant_id": tenant_b.id})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_switch_missing_cookie(self, client: TestClient, test_tenant_v2):
        """Sans cookie refresh → 401."""
        resp = client.post("/api/v1/auth/v2/switch-membership", json={"tenant_id": test_tenant_v2.id})
        assert resp.status_code == 401

    def test_switch_no_membership_in_target(
        self,
        client: TestClient,
        test_db,
        test_account_v2,
        test_tenant_v2,
        test_membership_v2,
    ):
        """Switch vers un tenant sans membership → 401/403 (isolation cross-tenant)."""
        tenant_c = Tenant(
            external_id=str(uuid.uuid4()),
            name="Tenant C No-Membership",
            domain=f"nomember-{uuid.uuid4().hex[:8]}.test",
            contact_email="c@nomember.example",
            app_code="marveline",
            status="active",
            is_active=True,
        )
        test_db.add(tenant_c)
        test_db.commit()
        test_db.refresh(tenant_c)

        login_resp = _login_v2(client, test_account_v2.email, _ACCOUNT_PASSWORD, test_tenant_v2.id)
        assert login_resp.status_code == 200
        client.cookies.update(login_resp.cookies)

        resp = client.post("/api/v1/auth/v2/switch-membership", json={"tenant_id": tenant_c.id})
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 for cross-tenant switch, got {resp.status_code}"
        )

    def test_switch_invalid_body(
        self,
        client: TestClient,
        test_membership_v2,
        test_account_v2,
        test_tenant_v2,
    ):
        """Body sans tenant_id → 422 Pydantic."""
        login_resp = _login_v2(client, test_account_v2.email, _ACCOUNT_PASSWORD, test_tenant_v2.id)
        assert login_resp.status_code == 200
        client.cookies.update(login_resp.cookies)

        resp = client.post("/api/v1/auth/v2/switch-membership", json={})
        assert resp.status_code == 422

    def test_switch_cookie_not_rotated(
        self,
        client: TestClient,
        test_db,
        test_account_v2,
        test_tenant_v2,
        test_membership_v2,
        test_role_staff,
    ):
        """Switch ne rotate pas le cookie refresh (contrairement à /refresh)."""
        tenant_b = Tenant(
            external_id=str(uuid.uuid4()),
            name="Tenant B No-Rotate",
            domain=f"norot-{uuid.uuid4().hex[:8]}.test",
            contact_email="b@norot.example",
            app_code="marveline",
            status="active",
            is_active=True,
        )
        test_db.add(tenant_b)
        test_db.commit()
        test_db.refresh(tenant_b)

        membership_b = TenantMembership(
            account_id=test_account_v2.id,
            tenant_id=tenant_b.id,
            role_name=_ROLE,
            status="active",
        )
        test_db.add(membership_b)
        test_db.commit()

        login_resp = _login_v2(client, test_account_v2.email, _ACCOUNT_PASSWORD, test_tenant_v2.id)
        assert login_resp.status_code == 200
        client.cookies.update(login_resp.cookies)

        resp = client.post("/api/v1/auth/v2/switch-membership", json={"tenant_id": tenant_b.id})
        assert resp.status_code == 200
        # Aucun nouveau cookie refresh émis par switch-membership
        assert "refresh_token" not in resp.cookies


# ═══════════════════════════════════════════════════════════════════════
# Password management — forgot / reset / change (IAM v2)
# ═══════════════════════════════════════════════════════════════════════


class TestForgotPasswordV2:
    """POST /auth/v2/forgot-password — demande de reinitialisation."""

    def test_forgot_password_known_email(
        self, client: TestClient, test_membership_v2, test_account_v2,
    ):
        """Email connu → 200 (toujours, anti-enumeration)."""
        resp = client.post(
            "/api/v1/auth/v2/forgot-password",
            json={"email": test_account_v2.email},
        )
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_forgot_password_unknown_email(self, client: TestClient):
        """Email inconnu → 200 (anti-enumeration, meme reponse)."""
        resp = client.post(
            "/api/v1/auth/v2/forgot-password",
            json={"email": "nobody-ever@no-such-domain.example"},
        )
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_forgot_password_invalid_email(self, client: TestClient):
        """Email invalide → 422 Pydantic."""
        resp = client.post(
            "/api/v1/auth/v2/forgot-password",
            json={"email": "not-an-email"},
        )
        assert resp.status_code == 422

    def test_forgot_password_missing_body(self, client: TestClient):
        """Body vide → 422."""
        resp = client.post("/api/v1/auth/v2/forgot-password", json={})
        assert resp.status_code == 422


class TestResetPasswordV2:
    """POST /auth/v2/reset-password — reinitialisation avec token."""

    def test_reset_invalid_token(self, client: TestClient):
        """Token invalide (pas hex) → 400."""
        resp = client.post(
            "/api/v1/auth/v2/reset-password",
            json={"token": "not-a-valid-hex-token-at-all-xxxxx", "new_password": "NewSecure123!"},
        )
        assert resp.status_code == 400

    def test_reset_expired_token(self, client: TestClient):
        """Token hex valide mais inexistant en base → 400."""
        import secrets
        fake_token = secrets.token_hex(32)
        resp = client.post(
            "/api/v1/auth/v2/reset-password",
            json={"token": fake_token, "new_password": "NewSecure123!"},
        )
        assert resp.status_code == 400

    def test_reset_weak_password(self, client: TestClient):
        """Mot de passe trop court → 422 Pydantic."""
        resp = client.post(
            "/api/v1/auth/v2/reset-password",
            json={"token": "a" * 64, "new_password": "abc"},
        )
        assert resp.status_code == 422

    def test_reset_missing_fields(self, client: TestClient):
        """Body incomplet → 422."""
        resp = client.post("/api/v1/auth/v2/reset-password", json={"token": "abc"})
        assert resp.status_code == 422


class TestChangePasswordV2:
    """POST /auth/v2/change-password — changement authentifie."""

    def test_change_password_success(
        self, client: TestClient, test_membership_v2, test_account_v2, test_tenant_v2,
    ):
        """Login → change-password → 200."""
        login_resp = _login_v2(client, test_account_v2.email, _ACCOUNT_PASSWORD, test_tenant_v2.id)
        assert login_resp.status_code == 200
        access_token = login_resp.json()["access_token"]

        resp = client.post(
            "/api/v1/auth/v2/change-password",
            json={
                "current_password": _ACCOUNT_PASSWORD,
                "new_password": "BrandNewPass456!",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Password changed successfully"

        # Restaurer le mot de passe pour les autres tests
        from app.core.security import get_password_hash as _hash
        test_account_v2.hashed_password = _hash(_ACCOUNT_PASSWORD)
        # Note: commit handled by test_db fixture teardown

    def test_change_password_wrong_current(
        self, client: TestClient, test_membership_v2, test_account_v2, test_tenant_v2,
    ):
        """Mauvais mot de passe actuel → 401."""
        login_resp = _login_v2(client, test_account_v2.email, _ACCOUNT_PASSWORD, test_tenant_v2.id)
        assert login_resp.status_code == 200
        access_token = login_resp.json()["access_token"]

        resp = client.post(
            "/api/v1/auth/v2/change-password",
            json={
                "current_password": "wrong-current-pass!",
                "new_password": "BrandNewPass456!",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 401

    def test_change_password_same_as_current(
        self, client: TestClient, test_membership_v2, test_account_v2, test_tenant_v2,
    ):
        """Nouveau = ancien → 400."""
        login_resp = _login_v2(client, test_account_v2.email, _ACCOUNT_PASSWORD, test_tenant_v2.id)
        assert login_resp.status_code == 200
        access_token = login_resp.json()["access_token"]

        resp = client.post(
            "/api/v1/auth/v2/change-password",
            json={
                "current_password": _ACCOUNT_PASSWORD,
                "new_password": _ACCOUNT_PASSWORD,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 400

    def test_change_password_no_auth(self, client: TestClient):
        """Sans token → 401."""
        resp = client.post(
            "/api/v1/auth/v2/change-password",
            json={
                "current_password": "anything",
                "new_password": "BrandNewPass456!",
            },
        )
        assert resp.status_code == 401
