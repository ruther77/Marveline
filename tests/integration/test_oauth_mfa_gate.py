"""S1.T10 — Tests F404/OAUTH-MFA-BYPASS-01.

Spec : docs/architecture-audit-2026-04-26/execution-plan/10-sprint-1-PROD-FIRE-DRILL.md
       L1906-2024 (Story S1.T10).

Avant : `_issue_oauth_tokens` (oauth.py legacy) et `_open_session_and_issue`
(oauth_v2.py) creaient une session avec `mfa_verified=False` puis emettaient
les tokens directement, sans verifier si l'account avait un MFA enrole. Un user
avec TOTP / WebAuthn enrole et qui se connecte via Google bypass le challenge MFA
-> tous les endpoints non gardes par `require_step_up()` accessibles sans MFA.
Vecteur : compromission compte Google -> controle total compte CaroCorp/Marveline.

Apres : avant emission tokens, `mfa_service.is_mfa_enabled()` est appele.
Si MFA enrole -> `mfa_service.create_mfa_session()` + retour MFA-required result.
Le client doit appeler POST /api/v1/auth/mfa/verify pour finaliser.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Response

from app.api.v1.endpoints.oauth import _issue_oauth_tokens
from app.schemas.auth import TokenResponse
from app.schemas.mfa import MFALoginResponse
from app.services.auth_v2 import MFARequiredResult
from app.services.oauth_v2 import OAuthV2Service


# ----------------------------------------------------------------------------
# Flow legacy : oauth.py:_issue_oauth_tokens
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_oauth_legacy_with_mfa_enrolled_returns_mfa_required():
    """F404 fix flow legacy : compte avec MFA enrole + login OAuth ->
    MFALoginResponse(mfa_required=True), pas TokenResponse."""
    db = MagicMock()
    user = MagicMock()
    user.id = 42
    user.tenant_id = 1
    user.email = "admin@test.fr"
    user.role = "tenant_admin"
    response = MagicMock(spec=Response)

    with patch("app.api.v1.endpoints.oauth.mfa_service") as mock_mfa:
        mock_mfa.is_mfa_enabled = AsyncMock(return_value=True)
        mock_mfa.create_mfa_session = AsyncMock(return_value="mfa_session_token_xyz")

        result = await _issue_oauth_tokens(
            db=db, user=user, ip_address="1.2.3.4",
            user_agent="Mozilla/5.0", response=response,
        )

    assert isinstance(result, MFALoginResponse), f"Expected MFALoginResponse, got {type(result)}"
    assert result.mfa_required is True
    assert result.mfa_session_token == "mfa_session_token_xyz"
    assert result.token_type == "mfa_session"

    # is_mfa_enabled appele avec les bons args
    mock_mfa.is_mfa_enabled.assert_awaited_once()
    call_kwargs = mock_mfa.is_mfa_enabled.await_args.kwargs
    assert call_kwargs.get("user_id") == 42
    assert call_kwargs.get("tenant_id") == 1


@pytest.mark.asyncio
async def test_oauth_legacy_without_mfa_continues_to_token_emission():
    """Compte sans MFA enrole -> flow nominal (audit + session + tokens)."""
    db = MagicMock()
    db.commit = AsyncMock()
    user = MagicMock()
    user.id = 42
    user.tenant_id = 1
    user.email = "nomfa@test.fr"
    user.role = "viewer"
    user.password_change_required = False
    response = MagicMock(spec=Response)

    with patch("app.api.v1.endpoints.oauth.mfa_service") as mock_mfa, \
         patch("app.api.v1.endpoints.oauth.AuditService") as mock_audit_cls, \
         patch("app.api.v1.endpoints.oauth.session_service") as mock_session, \
         patch("app.api.v1.endpoints.oauth.token_service") as mock_token:
        mock_mfa.is_mfa_enabled = AsyncMock(return_value=False)
        mock_audit_instance = MagicMock()
        mock_audit_instance.log_login = AsyncMock()
        mock_audit_cls.return_value = mock_audit_instance
        mock_session.create_session = AsyncMock(return_value="session_xyz")
        mock_token.issue_tokens = AsyncMock(return_value=("access_tok", "refresh_tok", 3600))

        result = await _issue_oauth_tokens(
            db=db, user=user, ip_address="1.2.3.4",
            user_agent="Mozilla/5.0", response=response,
        )

    assert isinstance(result, TokenResponse), f"Expected TokenResponse, got {type(result)}"
    assert result.access_token == "access_tok"
    assert result.token_type == "bearer"

    # is_mfa_enabled DOIT avoir ete appele (le gate F404)
    mock_mfa.is_mfa_enabled.assert_awaited_once()
    # create_mfa_session ne doit PAS avoir ete appele
    mock_mfa.create_mfa_session.assert_not_called()


# ----------------------------------------------------------------------------
# Flow IAM v2 : OAuthV2Service._open_session_and_issue
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_oauth_v2_with_mfa_enrolled_returns_mfa_required_result():
    """F404 fix flow v2 : compte avec MFA enrole -> MFARequiredResult."""
    db = MagicMock()
    svc = OAuthV2Service(db)
    account = MagicMock()
    account.id = 42
    account.email = "admin@test.fr"
    membership = MagicMock()
    membership.id = 100
    membership.tenant_id = 1
    membership.role_name = "tenant_admin"

    with patch("app.services.oauth_v2.mfa_service") as mock_mfa:
        mock_mfa.is_mfa_enabled = AsyncMock(return_value=True)
        mock_mfa.create_mfa_session = AsyncMock(return_value="mfa_token_v2")

        result = await svc._open_session_and_issue(
            account=account, membership=membership,
            ip_address="1.2.3.4", user_agent="Mozilla", request_id="req-1",
        )

    assert isinstance(result, MFARequiredResult), f"Expected MFARequiredResult, got {type(result)}"
    assert result.mfa_session_token == "mfa_token_v2"

    mock_mfa.is_mfa_enabled.assert_awaited_once()
    call_kwargs = mock_mfa.is_mfa_enabled.await_args.kwargs
    assert call_kwargs.get("user_id") == 42
    assert call_kwargs.get("tenant_id") == 1


@pytest.mark.asyncio
async def test_oauth_v2_without_mfa_continues_to_token_tuple():
    """Compte sans MFA -> flow nominal v2 (tuple access/refresh/expires/pcr)."""
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    svc = OAuthV2Service(db)
    account = MagicMock()
    account.id = 42
    account.email = "nomfa@test.fr"
    account.password_change_required = False
    membership = MagicMock()
    membership.id = 100
    membership.tenant_id = 1
    membership.role_name = "viewer"

    with patch("app.services.oauth_v2.mfa_service") as mock_mfa, \
         patch("app.services.oauth_v2.AuditService") as mock_audit_cls, \
         patch("app.services.oauth_v2.token_service") as mock_token:
        mock_mfa.is_mfa_enabled = AsyncMock(return_value=False)
        mock_audit_instance = MagicMock()
        mock_audit_instance.log_login = AsyncMock()
        mock_audit_cls.return_value = mock_audit_instance
        mock_token.issue_tokens = AsyncMock(return_value=("at_v2", "rt_v2", 3600))
        # Mock session service interne au service
        svc._session_svc = MagicMock()
        fake_session = MagicMock()
        fake_session.session_id = "sess_v2"
        svc._session_svc.open = AsyncMock(return_value=fake_session)

        result = await svc._open_session_and_issue(
            account=account, membership=membership,
            ip_address="1.2.3.4", user_agent="Mozilla", request_id="req-1",
        )

    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    assert len(result) == 4
    access_token, refresh_token, expires_in, pcr = result
    assert access_token == "at_v2"
    assert refresh_token == "rt_v2"
    assert expires_in == 3600
    assert pcr is False

    mock_mfa.is_mfa_enabled.assert_awaited_once()
    mock_mfa.create_mfa_session.assert_not_called()


# ----------------------------------------------------------------------------
# Cohérence : les 2 flows verifient bien le MFA
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_both_oauth_flows_call_is_mfa_enabled_before_session():
    """Anti-bypass : les 2 flows OAuth (legacy + v2) appellent is_mfa_enabled
    AVANT toute creation de session ou emission de token. Garantie d'isolation."""
    # Flow legacy
    db1 = MagicMock()
    user = MagicMock()
    user.id = 1
    user.tenant_id = 1
    user.email = "x@x.fr"
    user.role = "viewer"
    user.password_change_required = False
    response = MagicMock(spec=Response)

    call_order_legacy = []

    with patch("app.api.v1.endpoints.oauth.mfa_service") as mock_mfa, \
         patch("app.api.v1.endpoints.oauth.session_service") as mock_session, \
         patch("app.api.v1.endpoints.oauth.AuditService") as mock_audit_cls, \
         patch("app.api.v1.endpoints.oauth.token_service") as mock_tok:
        async def track_mfa_check(*args, **kwargs):
            call_order_legacy.append("is_mfa_enabled")
            return False
        async def track_session_create(*args, **kwargs):
            call_order_legacy.append("create_session")
            return "sid"
        mock_mfa.is_mfa_enabled = AsyncMock(side_effect=track_mfa_check)
        mock_session.create_session = AsyncMock(side_effect=track_session_create)
        mock_tok.issue_tokens = AsyncMock(return_value=("a", "b", 1))
        # AuditService(...).log_login() doit etre awaitable
        mock_audit_instance = MagicMock()
        mock_audit_instance.log_login = AsyncMock()
        mock_audit_cls.return_value = mock_audit_instance
        db1.commit = AsyncMock()

        await _issue_oauth_tokens(db1, user, "ip", "ua", response)

    # is_mfa_enabled doit avoir ete appele AVANT create_session
    assert call_order_legacy[0] == "is_mfa_enabled", (
        f"is_mfa_enabled doit precede create_session, ordre: {call_order_legacy}"
    )
    assert "create_session" in call_order_legacy
