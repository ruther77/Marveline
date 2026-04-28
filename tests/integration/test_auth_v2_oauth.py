"""Tests d'intégration — IAM v2 OAuth endpoints.

Coverage :
    GET  /auth/v2/oauth/{provider}/authorize
    POST /auth/v2/oauth/{provider}/callback

Fixtures locales : même stack que test_auth_v2 (Tenant + Account + TenantMembership).
Les appels httpx vers les providers externes sont mockés.
Le state Redis est mocké pour contrôler les cas valid/invalid.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.account import Account
from app.models.account_oauth_identity import AccountOAuthIdentity
from app.models.auth_role import AuthRole
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership

_ROLE = "staff"
_PROVIDER = "google"
_PROVIDER_SUBJECT = "google-oauth-sub-123"
_PROVIDER_EMAIL = "oauth-user@gmail.com"

_VALID_USERINFO = {
    "id": _PROVIDER_SUBJECT,
    "email": _PROVIDER_EMAIL,
    "name": "OAuth User",
}


# ─── Fixtures locales ──────────────────────────────────────────────────────────


@pytest.fixture
def oauth_tenant(test_db):
    """Tenant actif pour tests OAuth v2."""
    tenant = Tenant(
        external_id=str(uuid.uuid4()),
        name="Tenant OAuth v2 Test",
        domain=f"oauth-v2-{uuid.uuid4().hex[:8]}.test",
        contact_email="contact@oauth-v2-test.example.com",
        app_code="marveline",
        status="active",
        is_active=True,
    )
    test_db.add(tenant)
    test_db.commit()
    test_db.refresh(tenant)
    return tenant


@pytest.fixture
def oauth_role_staff(test_db):
    """Rôle 'staff' dans auth_roles (table statique truncatée par clean_db)."""
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
def oauth_account(test_db):
    """Account global avec email = _PROVIDER_EMAIL (pour auto-link)."""
    account = Account(
        email=_PROVIDER_EMAIL,
        hashed_password=get_password_hash("DummyPass123!"),
        first_name="OAuth",
        last_name="User",
        is_active=True,
        password_change_required=False,
    )
    test_db.add(account)
    test_db.commit()
    test_db.refresh(account)
    return account


@pytest.fixture
def oauth_membership(test_db, oauth_account, oauth_tenant, oauth_role_staff):
    """TenantMembership actif liant oauth_account + oauth_tenant."""
    membership = TenantMembership(
        account_id=oauth_account.id,
        tenant_id=oauth_tenant.id,
        role_name=_ROLE,
        status="active",
    )
    test_db.add(membership)
    test_db.commit()
    test_db.refresh(membership)
    return membership


@pytest.fixture
def linked_identity(test_db, oauth_account):
    """AccountOAuthIdentity déjà liée à oauth_account."""
    identity = AccountOAuthIdentity(
        account_id=oauth_account.id,
        provider=_PROVIDER,
        provider_subject=_PROVIDER_SUBJECT,
        email_at_provider=_PROVIDER_EMAIL,
    )
    test_db.add(identity)
    test_db.commit()
    test_db.refresh(identity)
    return identity


# ─── Helpers de mock ──────────────────────────────────────────────────────────

def _mock_state(tenant_id: int, provider: str = _PROVIDER, code_verifier: str = None) -> dict:
    state_data = {"provider": provider, "tenant_id": tenant_id}
    if code_verifier:
        state_data["code_verifier"] = code_verifier
    return state_data


# ─── Tests : GET /auth/v2/oauth/{provider}/authorize ──────────────────────────


class TestAuthorizeV2:
    """GET /auth/v2/oauth/{provider}/authorize."""

    def test_authorize_returns_auth_url(self, client: TestClient, oauth_tenant):
        """Provider configuré + tenant_id → 200 + auth_url."""
        with (
            patch("app.services.oauth_v2._client_id_v2", return_value="fake-client-id"),
            patch("app.services.oauth_v2.redis_sec") as mock_redis,
        ):
            mock_redis.store_oauth_state = AsyncMock()
            resp = client.get(
                f"/api/v1/auth/v2/oauth/{_PROVIDER}/authorize",
                params={"tenant_id": oauth_tenant.id},
            )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "auth_url" in data
        assert "accounts.google.com" in data["auth_url"]

    def test_authorize_unknown_provider(self, client: TestClient, oauth_tenant):
        """Provider inconnu → 404."""
        resp = client.get(
            "/api/v1/auth/v2/oauth/twitter/authorize",
            params={"tenant_id": oauth_tenant.id},
        )
        assert resp.status_code == 404

    def test_authorize_unconfigured_provider(self, client: TestClient, oauth_tenant):
        """Provider sans CLIENT_ID configuré → 404."""
        # CLIENT_ID vide par défaut dans les settings de test
        resp = client.get(
            f"/api/v1/auth/v2/oauth/{_PROVIDER}/authorize",
            params={"tenant_id": oauth_tenant.id},
        )
        assert resp.status_code == 404

    def test_authorize_missing_tenant_id(self, client: TestClient):
        """tenant_id manquant → 422 (Query obligatoire)."""
        with patch("app.services.oauth_v2._client_id_v2", return_value="fake-client-id"):
            resp = client.get(f"/api/v1/auth/v2/oauth/{_PROVIDER}/authorize")
        assert resp.status_code == 422


# ─── Tests : POST /auth/v2/oauth/{provider}/callback ──────────────────────────


class TestCallbackV2:
    """POST /auth/v2/oauth/{provider}/callback."""

    def test_callback_success_existing_identity(
        self, client: TestClient, oauth_membership, linked_identity, oauth_account, oauth_tenant
    ):
        """Identité déjà liée → 200 + access_token + cookie refresh."""
        state_data = _mock_state(oauth_tenant.id)

        with (
            patch("app.services.oauth_v2._client_id_v2", return_value="fake-client-id"),
            patch("app.services.oauth_v2._exchange_code", new_callable=AsyncMock, return_value="prov-token"),
            patch("app.services.oauth_v2._get_userinfo", new_callable=AsyncMock, return_value=_VALID_USERINFO),
            patch("app.services.oauth_v2.redis_sec") as mock_redis,
        ):
            mock_redis.consume_oauth_state = AsyncMock(return_value=state_data)
            resp = client.post(
                f"/api/v1/auth/v2/oauth/{_PROVIDER}/callback",
                json={"code": "auth-code-123", "state": "valid-state"},
            )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "refresh_token" in resp.cookies

    def test_callback_success_auto_link(
        self, client: TestClient, oauth_membership, oauth_account, oauth_tenant
    ):
        """Email connu mais identité non liée → auto-link + 200 + tokens."""
        state_data = _mock_state(oauth_tenant.id)

        with (
            patch("app.services.oauth_v2._client_id_v2", return_value="fake-client-id"),
            patch("app.services.oauth_v2._exchange_code", new_callable=AsyncMock, return_value="prov-token"),
            patch("app.services.oauth_v2._get_userinfo", new_callable=AsyncMock, return_value=_VALID_USERINFO),
            patch("app.services.oauth_v2.redis_sec") as mock_redis,
        ):
            mock_redis.consume_oauth_state = AsyncMock(return_value=state_data)
            resp = client.post(
                f"/api/v1/auth/v2/oauth/{_PROVIDER}/callback",
                json={"code": "auth-code-456", "state": "valid-state"},
            )

        assert resp.status_code == 200, resp.text
        assert "access_token" in resp.json()

    def test_callback_invalid_state(self, client: TestClient):
        """State Redis invalide / expiré → 400."""
        with (
            patch("app.services.oauth_v2._client_id_v2", return_value="fake-client-id"),
            patch("app.services.oauth_v2.redis_sec") as mock_redis,
        ):
            mock_redis.consume_oauth_state = AsyncMock(return_value=None)
            resp = client.post(
                f"/api/v1/auth/v2/oauth/{_PROVIDER}/callback",
                json={"code": "code", "state": "expired-state"},
            )

        assert resp.status_code == 400

    def test_callback_wrong_provider_in_state(self, client: TestClient):
        """Provider dans l'URL ≠ provider dans le state → 400 (anti-tamper)."""
        state_data = _mock_state(tenant_id=1, provider="github")

        with (
            patch("app.services.oauth_v2._client_id_v2", return_value="fake-client-id"),
            patch("app.services.oauth_v2.redis_sec") as mock_redis,
        ):
            mock_redis.consume_oauth_state = AsyncMock(return_value=state_data)
            resp = client.post(
                f"/api/v1/auth/v2/oauth/{_PROVIDER}/callback",
                json={"code": "code", "state": "tampered"},
            )

        assert resp.status_code == 400

    def test_callback_no_email_from_provider(self, client: TestClient, oauth_tenant):
        """Provider ne retourne pas d'email → 400."""
        state_data = _mock_state(oauth_tenant.id)
        userinfo_no_email = {"id": _PROVIDER_SUBJECT, "email": None, "name": "No Email"}

        with (
            patch("app.services.oauth_v2._client_id_v2", return_value="fake-client-id"),
            patch("app.services.oauth_v2._exchange_code", new_callable=AsyncMock, return_value="prov-token"),
            patch("app.services.oauth_v2._get_userinfo", new_callable=AsyncMock, return_value=userinfo_no_email),
            patch("app.services.oauth_v2.redis_sec") as mock_redis,
        ):
            mock_redis.consume_oauth_state = AsyncMock(return_value=state_data)
            resp = client.post(
                f"/api/v1/auth/v2/oauth/{_PROVIDER}/callback",
                json={"code": "code", "state": "valid"},
            )

        assert resp.status_code == 400

    def test_callback_email_not_found(self, client: TestClient, oauth_tenant):
        """Email provider inconnu dans accounts → 400."""
        state_data = _mock_state(oauth_tenant.id)
        unknown_email_info = {"id": "unknown-sub", "email": "no-account@nowhere.example", "name": "Ghost"}

        with (
            patch("app.services.oauth_v2._client_id_v2", return_value="fake-client-id"),
            patch("app.services.oauth_v2._exchange_code", new_callable=AsyncMock, return_value="prov-token"),
            patch("app.services.oauth_v2._get_userinfo", new_callable=AsyncMock, return_value=unknown_email_info),
            patch("app.services.oauth_v2.redis_sec") as mock_redis,
        ):
            mock_redis.consume_oauth_state = AsyncMock(return_value=state_data)
            resp = client.post(
                f"/api/v1/auth/v2/oauth/{_PROVIDER}/callback",
                json={"code": "code", "state": "valid"},
            )

        assert resp.status_code == 400

    def test_callback_no_membership_in_tenant(
        self, client: TestClient, test_db, oauth_account, oauth_tenant
    ):
        """Account valide mais pas de membership dans le tenant du state → 403."""
        # Pas de fixture oauth_membership → membership absent
        state_data = _mock_state(oauth_tenant.id)

        with (
            patch("app.services.oauth_v2._client_id_v2", return_value="fake-client-id"),
            patch("app.services.oauth_v2._exchange_code", new_callable=AsyncMock, return_value="prov-token"),
            patch("app.services.oauth_v2._get_userinfo", new_callable=AsyncMock, return_value=_VALID_USERINFO),
            patch("app.services.oauth_v2.redis_sec") as mock_redis,
        ):
            mock_redis.consume_oauth_state = AsyncMock(return_value=state_data)
            resp = client.post(
                f"/api/v1/auth/v2/oauth/{_PROVIDER}/callback",
                json={"code": "code", "state": "valid"},
            )

        assert resp.status_code == 403

    def test_callback_cross_tenant_blocked(
        self, client: TestClient, test_db, oauth_membership, oauth_account, oauth_tenant
    ):
        """Account a un membership dans tenant A mais state pointe vers tenant B → 403."""
        tenant_b = Tenant(
            external_id=str(uuid.uuid4()),
            name="Tenant B OAuth",
            domain=f"tenant-b-oauth-{uuid.uuid4().hex[:8]}.test",
            contact_email="b@tenantb.example",
            app_code="marveline",
            status="active",
            is_active=True,
        )
        test_db.add(tenant_b)
        test_db.commit()
        test_db.refresh(tenant_b)

        # State pointe vers tenant_b — pas de membership ici pour oauth_account
        state_data = _mock_state(tenant_b.id)

        with (
            patch("app.services.oauth_v2._client_id_v2", return_value="fake-client-id"),
            patch("app.services.oauth_v2._exchange_code", new_callable=AsyncMock, return_value="prov-token"),
            patch("app.services.oauth_v2._get_userinfo", new_callable=AsyncMock, return_value=_VALID_USERINFO),
            patch("app.services.oauth_v2.redis_sec") as mock_redis,
        ):
            mock_redis.consume_oauth_state = AsyncMock(return_value=state_data)
            resp = client.post(
                f"/api/v1/auth/v2/oauth/{_PROVIDER}/callback",
                json={"code": "code", "state": "valid"},
            )

        assert resp.status_code == 403, (
            f"Cross-tenant OAuth doit être bloqué, got {resp.status_code}"
        )

    def test_callback_inactive_account(
        self, client: TestClient, test_db, oauth_membership, linked_identity, oauth_account, oauth_tenant
    ):
        """Compte inactif → 403 même avec identité valide."""
        oauth_account.is_active = False
        test_db.commit()

        state_data = _mock_state(oauth_tenant.id)
        try:
            with (
                patch("app.services.oauth_v2._client_id_v2", return_value="fake-client-id"),
                patch("app.services.oauth_v2._exchange_code", new_callable=AsyncMock, return_value="prov-token"),
                patch("app.services.oauth_v2._get_userinfo", new_callable=AsyncMock, return_value=_VALID_USERINFO),
                patch("app.services.oauth_v2.redis_sec") as mock_redis,
            ):
                mock_redis.consume_oauth_state = AsyncMock(return_value=state_data)
                resp = client.post(
                    f"/api/v1/auth/v2/oauth/{_PROVIDER}/callback",
                    json={"code": "code", "state": "valid"},
                )

            assert resp.status_code == 403
        finally:
            oauth_account.is_active = True
            test_db.commit()

    def test_callback_redis_down(self, client: TestClient, oauth_tenant):
        """Redis indisponible au consume_oauth_state → 503."""
        with (
            patch("app.services.oauth_v2._client_id_v2", return_value="fake-client-id"),
            patch("app.services.oauth_v2.redis_sec") as mock_redis,
        ):
            mock_redis.consume_oauth_state = AsyncMock(side_effect=ConnectionError("Redis down"))
            resp = client.post(
                f"/api/v1/auth/v2/oauth/{_PROVIDER}/callback",
                json={"code": "code", "state": "any"},
            )

        assert resp.status_code == 503

    def test_callback_missing_body_fields(self, client: TestClient):
        """Body incomplet → 422."""
        resp = client.post(
            f"/api/v1/auth/v2/oauth/{_PROVIDER}/callback",
            json={"code": "only-code"},
        )
        assert resp.status_code == 422
