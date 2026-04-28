"""Tests unitaires — contrôle backend password_change_required.

Verifie que :
- Un utilisateur avec password_change_required=True est bloque sur les endpoints metier (403)
- Les endpoints exemptes (change-password, logout, csrf) restent accessibles
- Un utilisateur avec password_change_required=False passe normalement
- La reponse 403 contient le code "PASSWORD_CHANGE_REQUIRED"
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from app.constants.http import AuthEndpoints, PASSWORD_CHANGE_ALLOWED


# -- Helpers ------------------------------------------------------------------

def _make_user(*, password_change_required: bool, is_active: bool = True) -> MagicMock:
    user = MagicMock()
    user.id = 1
    user.tenant_id = 1
    user.is_active = is_active
    user.password_change_required = password_change_required
    return user


def _make_request(path: str) -> MagicMock:
    req = MagicMock()
    req.url.path = path
    return req


def _make_payload(uid: int = 1, tid: int = 1) -> dict:
    return {
        "sub": str(uid),
        "tid": str(tid),
        "type": "access",
        "jti": "test-jti-abc",
        "did": "device-123",
    }


# -- PASSWORD_CHANGE_ALLOWED ------------------------------------

class TestPasswordChangeAllowedConstant:
    def test_change_password_in_allowed(self):
        assert "/api/v1/auth/change-password" in PASSWORD_CHANGE_ALLOWED

    def test_logout_in_allowed(self):
        assert "/api/v1/auth/logout" in PASSWORD_CHANGE_ALLOWED

    def test_csrf_in_allowed(self):
        assert "/api/v1/auth/csrf" in PASSWORD_CHANGE_ALLOWED

    def test_business_endpoints_not_in_allowed(self):
        for path in ["/api/v1/products", "/api/v1/reservations", "/api/v1/invoices"]:
            assert path not in PASSWORD_CHANGE_ALLOWED


# -- get_current_user (async) -------------------------------------------------

class TestGetCurrentUserPasswordChangeRequired:
    """get_current_user est async depuis la conversion BUG-DEPS-SYNC-01."""

    async def _call(self, user: MagicMock, path: str):
        from app.core.deps import get_current_user
        from unittest.mock import AsyncMock
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = user
        db.execute.return_value = result_mock
        request = _make_request(path)
        with (
            patch("app.core.deps.decode_access_token", return_value=_make_payload()),
            patch("app.core.deps.token_service.is_access_blacklisted", return_value=False),
            patch("app.core.deps._handle_revoked_device", return_value=None),
        ):
            return await get_current_user(request=request, db=db, token="fake.jwt.token")

    @pytest.mark.asyncio
    async def test_blocked_on_business_endpoint(self):
        """password_change_required=True → 403 PASSWORD_CHANGE_REQUIRED sur endpoint metier."""
        user = _make_user(password_change_required=True)
        with pytest.raises(HTTPException) as exc:
            await self._call(user, "/api/v1/products")
        assert exc.value.status_code == 403
        assert exc.value.detail == "PASSWORD_CHANGE_REQUIRED"

    @pytest.mark.asyncio
    async def test_allowed_on_change_password(self):
        """password_change_required=True → passe sur /auth/change-password."""
        user = _make_user(password_change_required=True)
        result = await self._call(user, "/api/v1/auth/change-password")
        assert result is user

    @pytest.mark.asyncio
    async def test_allowed_on_logout(self):
        """password_change_required=True → passe sur /auth/logout."""
        user = _make_user(password_change_required=True)
        result = await self._call(user, "/api/v1/auth/logout")
        assert result is user

    @pytest.mark.asyncio
    async def test_allowed_on_csrf(self):
        """password_change_required=True → passe sur /auth/csrf."""
        user = _make_user(password_change_required=True)
        result = await self._call(user, "/api/v1/auth/csrf")
        assert result is user

    @pytest.mark.asyncio
    async def test_normal_user_passes_business_endpoint(self):
        """password_change_required=False → acces normal."""
        user = _make_user(password_change_required=False)
        result = await self._call(user, "/api/v1/products")
        assert result is user

    @pytest.mark.asyncio
    async def test_detail_distinguishable_from_account_inactive(self):
        """Le code 403 est distinct de ACCOUNT_INACTIVE pour que le frontend puisse router."""
        user_pcr = _make_user(password_change_required=True)
        user_inactive = _make_user(password_change_required=False, is_active=False)

        with pytest.raises(HTTPException) as exc_pcr:
            await self._call(user_pcr, "/api/v1/products")

        with pytest.raises(HTTPException) as exc_inactive:
            await self._call(user_inactive, "/api/v1/products")

        assert exc_pcr.value.detail != exc_inactive.value.detail
        assert exc_pcr.value.detail == "PASSWORD_CHANGE_REQUIRED"

    @pytest.mark.asyncio
    async def test_blocked_on_variants_endpoint(self):
        """Endpoint variantes produit bloque avec password_change_required."""
        user = _make_user(password_change_required=True)
        with pytest.raises(HTTPException) as exc:
            await self._call(user, "/api/v1/products/1/variants")
        assert exc.value.status_code == 403
        assert exc.value.detail == "PASSWORD_CHANGE_REQUIRED"

    @pytest.mark.asyncio
    async def test_blocked_on_reservations(self):
        """Endpoint reservations bloque avec password_change_required."""
        user = _make_user(password_change_required=True)
        with pytest.raises(HTTPException) as exc:
            await self._call(user, "/api/v1/reservations")
        assert exc.value.status_code == 403
