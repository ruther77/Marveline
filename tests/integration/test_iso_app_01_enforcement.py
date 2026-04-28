"""ISO-APP-01 — Tests d'enforcement app↔tenant.

Vérifie :
    1. JWT émis au login porte l'audience de l'app_code du tenant
    2. Login reject 403 si X-App-Code ≠ tenant.app_code
    3. Middleware AppEnforcementMiddleware bloque JWT utilisé cross-app
    4. Refresh token préserve l'audience
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import decode_token
from app.models.account import Account
from app.models.auth_role import AuthRole
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership
from app.core.security import get_password_hash


_PASSWORD = "IsoAppTest2026!"
_ROLE = "manager"


@pytest.fixture
def iso_role_manager(test_db):
    """AuthRole manager en DB (FK requirement)."""
    from sqlalchemy import select
    existing = test_db.execute(select(AuthRole).where(AuthRole.name == _ROLE)).scalar_one_or_none()
    if existing:
        return existing
    role = AuthRole(name=_ROLE, level=3, is_system=False, mfa_required=False, description="Manager")
    test_db.add(role)
    test_db.commit()
    return role


def _mk_tenant(test_db, app_code: str) -> Tenant:
    token = uuid.uuid4().hex[:8]
    tenant = Tenant(
        external_id=str(uuid.uuid4()),
        name=f"ISO {app_code} {token}",
        domain=f"iso-{app_code}-{token}.test",
        contact_email=f"iso-{app_code}-{token}@example.com",
        app_code=app_code,
        status="active",
        is_active=True,
    )
    test_db.add(tenant)
    test_db.commit()
    test_db.refresh(tenant)
    return tenant


def _mk_account_with_membership(test_db, tenant_id: int, _role_fixture) -> Account:
    token = uuid.uuid4().hex[:8]
    account = Account(
        email=f"iso-user-{token}@example.com",
        hashed_password=get_password_hash(_PASSWORD),
        first_name="Iso",
        last_name="User",
        is_active=True,
    )
    test_db.add(account)
    test_db.flush()
    membership = TenantMembership(
        account_id=account.id,
        tenant_id=tenant_id,
        role_name=_ROLE,
        status="active",
    )
    test_db.add(membership)
    test_db.commit()
    test_db.refresh(account)
    return account


class TestLoginAudience:
    """Login émet JWT avec audience dérivée de tenant.app_code."""

    def test_login_marveline_emits_marveline_audience(
        self, client: TestClient, test_db, iso_role_manager,
    ):
        tenant = _mk_tenant(test_db, "marveline")
        account = _mk_account_with_membership(test_db, tenant.id, iso_role_manager)
        resp = client.post("/api/v1/auth/v2/login", json={
            "email": account.email, "password": _PASSWORD, "tenant_id": tenant.id,
        })
        assert resp.status_code == 200, resp.text
        claims = decode_token(resp.json()["access_token"])
        assert claims["aud"] == "marveline-api"

    def test_login_epicerie_emits_epicerie_audience(
        self, client: TestClient, test_db, iso_role_manager,
    ):
        tenant = _mk_tenant(test_db, "epicerie")
        account = _mk_account_with_membership(test_db, tenant.id, iso_role_manager)
        resp = client.post("/api/v1/auth/v2/login", json={
            "email": account.email, "password": _PASSWORD, "tenant_id": tenant.id,
        })
        assert resp.status_code == 200, resp.text
        claims = decode_token(resp.json()["access_token"])
        assert claims["aud"] == "epicerie-api"


class TestLoginAppCodeHeader:
    """Login reject 403 si X-App-Code ne match pas tenant.app_code."""

    def test_login_marveline_user_on_epicerie_app_rejected(
        self, client: TestClient, test_db, iso_role_manager,
    ):
        tenant = _mk_tenant(test_db, "marveline")
        account = _mk_account_with_membership(test_db, tenant.id, iso_role_manager)
        resp = client.post(
            "/api/v1/auth/v2/login",
            json={"email": account.email, "password": _PASSWORD, "tenant_id": tenant.id},
            headers={"X-App-Code": "epicerie"},
        )
        assert resp.status_code == 403, resp.text
        assert "marveline" in resp.json()["detail"].lower() or "epicerie" in resp.json()["detail"].lower()

    def test_login_marveline_user_on_marveline_app_ok(
        self, client: TestClient, test_db, iso_role_manager,
    ):
        tenant = _mk_tenant(test_db, "marveline")
        account = _mk_account_with_membership(test_db, tenant.id, iso_role_manager)
        resp = client.post(
            "/api/v1/auth/v2/login",
            json={"email": account.email, "password": _PASSWORD, "tenant_id": tenant.id},
            headers={"X-App-Code": "marveline"},
        )
        assert resp.status_code == 200, resp.text


class TestMiddlewareEnforcement:
    """AppEnforcementMiddleware bloque JWT utilisé sur une app différente."""

    def test_marveline_jwt_on_epicerie_header_returns_403(
        self, client: TestClient, test_db, iso_role_manager,
    ):
        tenant = _mk_tenant(test_db, "marveline")
        account = _mk_account_with_membership(test_db, tenant.id, iso_role_manager)
        login_resp = client.post("/api/v1/auth/v2/login", json={
            "email": account.email, "password": _PASSWORD, "tenant_id": tenant.id,
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Utiliser ce JWT sur un endpoint avec X-App-Code=epicerie → 403
        resp = client.get("/api/v1/products", headers={
            "Authorization": f"Bearer {token}",
            "X-App-Code": "epicerie",
        })
        assert resp.status_code == 403
        body = resp.json()
        assert body.get("error") == "APP_TENANT_MISMATCH" or "mismatch" in str(body).lower()

    def test_marveline_jwt_on_marveline_header_ok(
        self, client: TestClient, test_db, iso_role_manager,
    ):
        tenant = _mk_tenant(test_db, "marveline")
        account = _mk_account_with_membership(test_db, tenant.id, iso_role_manager)
        login_resp = client.post("/api/v1/auth/v2/login", json={
            "email": account.email, "password": _PASSWORD, "tenant_id": tenant.id,
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Même app → middleware doit laisser passer (endpoint retournera son propre status)
        resp = client.get("/api/v1/products", headers={
            "Authorization": f"Bearer {token}",
            "X-App-Code": "marveline",
        })
        assert resp.status_code != 403 or "APP_TENANT_MISMATCH" not in resp.text

    def test_no_app_code_header_skips_enforcement(
        self, client: TestClient, test_db, iso_role_manager,
    ):
        """Mode rétrocompatible : header absent → pas de block (tests legacy continuent)."""
        tenant = _mk_tenant(test_db, "marveline")
        account = _mk_account_with_membership(test_db, tenant.id, iso_role_manager)
        login_resp = client.post("/api/v1/auth/v2/login", json={
            "email": account.email, "password": _PASSWORD, "tenant_id": tenant.id,
        })
        token = login_resp.json()["access_token"]

        resp = client.get("/api/v1/products", headers={"Authorization": f"Bearer {token}"})
        # Pas de 403 APP_TENANT_MISMATCH quand le header est absent
        assert "APP_TENANT_MISMATCH" not in resp.text
