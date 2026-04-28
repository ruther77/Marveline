"""Service OAuth v2 — Authorization Code flow pour IAM v2 (accounts + memberships).

Différences vs oauth.py (v1 legacy) :
    - Liaison via AccountOAuthIdentity (table dédiée) au lieu de User.oauth_provider/oauth_id
    - tenant_id encodé dans le state Redis → require_active membership
    - Session via AccountSessionService (pas session_service legacy)
    - Aucun import User / session_service

Security :
    - state single-use (consume_oauth_state atomique, FAIL-CLOSED)
    - PKCE S256 pour Google
    - Auto-link par email uniquement si compte actif unique
"""
import base64
import hashlib
import logging
import secrets
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ErrorMessages
from app.core.config import settings
from app.core.exceptions import NotFound
from app.core.redis import redis_sec
from typing import Union
from app.repositories.account import AsyncAccountRepository
from app.repositories.account_oauth_identity import AsyncAccountOAuthIdentityRepository
from app.services.account_session import AccountSessionService
from app.services.audit import AuditService
from app.services.auth_v2 import MFARequiredResult
from app.services.membership import MembershipService
from app.services.mfa import mfa_service
from app.services.session import generate_device_id
from app.services.token import token_service

logger = logging.getLogger(__name__)

# ─── Configuration statique des providers ─────────────────────────────────────

_PROVIDERS_V2: dict[str, dict] = {
    "google": {
        "name": "Google",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scopes": ["openid", "email", "profile"],
        "pkce": True,
    },
    "github": {
        "name": "GitHub",
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "emails_url": "https://api.github.com/user/emails",
        "scopes": ["user:email"],
        "pkce": False,
    },
    "facebook": {
        "name": "Facebook",
        "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
        "userinfo_url": "https://graph.facebook.com/me?fields=id,email,name,picture",
        "scopes": ["email"],
        "pkce": False,
    },
}


def _client_id_v2(provider: str) -> str:
    return {
        "google": settings.OAUTH_GOOGLE_CLIENT_ID,
        "github": settings.OAUTH_GITHUB_CLIENT_ID,
        "facebook": settings.OAUTH_FACEBOOK_CLIENT_ID,
    }.get(provider, "")


def _client_secret_v2(provider: str) -> str:
    return {
        "google": settings.OAUTH_GOOGLE_CLIENT_SECRET,
        "github": settings.OAUTH_GITHUB_CLIENT_SECRET,
        "facebook": settings.OAUTH_FACEBOOK_CLIENT_SECRET,
    }.get(provider, "")


def _redirect_uri_v2(provider: str) -> str:
    return {
        "google": settings.OAUTH_GOOGLE_REDIRECT_URI,
        "github": settings.OAUTH_GITHUB_REDIRECT_URI,
        "facebook": settings.OAUTH_FACEBOOK_REDIRECT_URI,
    }.get(provider, "")


def _require_provider_v2(provider: str) -> dict:
    """Valide le provider ; 404 si inconnu ou non configuré."""
    if provider not in _PROVIDERS_V2:
        raise NotFound("Unknown OAuth provider")
    if not _client_id_v2(provider):
        raise NotFound("OAuth provider not configured")
    return _PROVIDERS_V2[provider]


def _pkce_challenge_v2(verifier: str) -> str:
    """PKCE S256 : base64url(SHA256(verifier))."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


# ─── Helpers httpx (module-level → facilement mockables en tests) ──────────────

async def _exchange_code(
    provider: str,
    code: str,
    cfg: dict,
    code_verifier: Optional[str],
) -> str:
    """Échange le code OAuth contre l'access_token du provider.

    Returns: access_token provider (str).
    Raises: HTTPException 502 si l'échange échoue.
    """
    payload = {
        "code": code,
        "client_id": _client_id_v2(provider),
        "client_secret": _client_secret_v2(provider),
        "redirect_uri": _redirect_uri_v2(provider),
        "grant_type": "authorization_code",
    }
    if code_verifier:
        payload["code_verifier"] = code_verifier
    headers = {"Accept": "application/json"} if provider == "github" else {}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(cfg["token_url"], data=payload, headers=headers)

    if resp.status_code != 200:
        logger.error("OAuth v2 token exchange failed for %s (HTTP %s)", provider, resp.status_code)
        raise HTTPException(status_code=502, detail="OAuth token exchange failed")

    data = resp.json()
    token = data.get("access_token")
    if not token:
        logger.error("No access_token in OAuth v2 response for %s", provider)
        raise HTTPException(status_code=502, detail="OAuth token exchange failed")
    return token


async def _get_userinfo(provider: str, access_token: str, cfg: dict) -> dict:
    """Récupère id (str), email (str|None), name (str) depuis le provider.

    Raises: HTTPException 502 si l'appel échoue.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(cfg["userinfo_url"], headers=headers)

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch OAuth user info")

    data = resp.json()
    user_id = str(data.get("id") or data.get("sub") or "")
    email: Optional[str] = data.get("email")
    name: str = data.get("name") or ""

    if provider == "github" and not email:
        email = await _get_github_email(access_token, cfg)

    return {"id": user_id, "email": email, "name": name}


async def _get_github_email(access_token: str, cfg: dict) -> Optional[str]:
    """Email primaire vérifié via GET /user/emails (GitHub)."""
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(cfg["emails_url"], headers=headers)
        if resp.status_code != 200:
            return None
        for entry in resp.json():
            if entry.get("primary") and entry.get("verified"):
                return entry.get("email")
    except httpx.HTTPError:
        pass
    return None


# ─── Service ──────────────────────────────────────────────────────────────────

class OAuthV2Service:
    """Service OAuth IAM v2 — authorize + callback flow complet.

    Responsabilités :
        - Générer state Redis + auth_url vers le provider
        - Échanger le code + résoudre l'identité OAuth en Account
        - Ouvrir session AccountSession + émettre tokens JWT v3
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._identity_repo = AsyncAccountOAuthIdentityRepository(db)
        self._account_repo = AsyncAccountRepository(db)
        self._membership_svc = MembershipService(db)
        self._session_svc = AccountSessionService(db)

    async def authorize(self, provider: str, tenant_id: int) -> dict:
        """Génère state Redis + auth_url vers le provider.

        Le tenant_id est stocké dans le state pour retrouver le membership au callback.

        Returns:
            { auth_url: str }
        Raises:
            404 si provider inconnu / non configuré.
            503 si Redis indisponible.
        """
        cfg = _require_provider_v2(provider)
        state = secrets.token_urlsafe(32)
        state_data: dict = {"provider": provider, "tenant_id": tenant_id}

        query_params: dict[str, str] = {
            "client_id": _client_id_v2(provider),
            "redirect_uri": _redirect_uri_v2(provider),
            "scope": " ".join(cfg["scopes"]),
            "state": state,
            "response_type": "code",
        }

        if cfg.get("pkce"):
            verifier = secrets.token_urlsafe(64)
            state_data["code_verifier"] = verifier
            query_params["code_challenge"] = _pkce_challenge_v2(verifier)
            query_params["code_challenge_method"] = "S256"

        try:
            await redis_sec.store_oauth_state(state, state_data, ttl=300)
        except Exception:
            raise HTTPException(status_code=503, detail="Service temporairement indisponible")

        return {"auth_url": f"{cfg['auth_url']}?{urlencode(query_params)}"}

    async def callback(
        self,
        provider: str,
        code: str,
        state: str,
        ip_address: str,
        user_agent: Optional[str],
        request_id: Optional[str],
    ) -> Union[tuple[str, str, int, bool], MFARequiredResult]:
        """Flow complet OAuth callback — retourne (access_token, refresh_token, expires_in, pcr).

        Séquence :
            1. Consume state (atomique, single-use)
            2. Valide provider + tenant_id dans le state
            3. Exchange code → provider_token
            4. Get userinfo → (provider_subject, email)
            5. Lookup ou lie le compte par identité OAuth / email
            6. Require active membership dans tenant_id
            7. Open AccountSession + audit log + issue tokens

        Raises:
            400 : state invalide, email manquant, compte introuvable.
            403 : compte inactif, membership inexistant / révoqué.
            502 : provider OAuth down.
            503 : Redis indisponible.
        """
        cfg = _require_provider_v2(provider)

        try:
            state_data = await redis_sec.consume_oauth_state(state)
        except Exception:
            raise HTTPException(status_code=503, detail="Service temporairement indisponible")

        if not state_data or state_data.get("provider") != provider:
            raise HTTPException(status_code=400, detail=ErrorMessages.OAUTH_STATE_INVALID)

        tenant_id: Optional[int] = state_data.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail=ErrorMessages.OAUTH_STATE_INVALID)

        provider_token = await _exchange_code(
            provider, code, cfg, state_data.get("code_verifier")
        )
        userinfo = await _get_userinfo(provider, provider_token, cfg)

        if not userinfo.get("email"):
            raise HTTPException(status_code=400, detail="Email non fourni par le provider OAuth")

        account = await self._resolve_account(
            provider, userinfo["id"], userinfo["email"],
            email_verified=userinfo.get("email_verified", False),
        )

        if not account.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorMessages.ACCOUNT_INACTIVE,
            )

        membership = await self._membership_svc.require_active(account.id, tenant_id)

        return await self._open_session_and_issue(
            account=account,
            membership=membership,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )

    # ── Helpers privés ──────────────────────────────────────────────────────

    async def _resolve_account(self, provider: str, provider_subject: str, email: str,
                               *, email_verified: bool = False):
        """Cherche ou lie un compte par identite OAuth puis par email.

        1. Lookup (provider, provider_subject) → identite deja liee → account.
        2. Lookup account actif par email → auto-link + insert identity.
        3. Introuvable → 400.
        """
        identity = await self._identity_repo.get_by_provider_subject(provider, provider_subject)
        if identity:
            account = await self._account_repo.get_by_id(identity.account_id)
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.OAUTH_EMAIL_NOT_FOUND,
                )
            return account

        # P2-23 : auto-linking uniquement si email verifie par le provider
        if not email_verified:
            logger.warning("OAuth auto-link rejete: email %s non verifie par %s", email, provider)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email non verifie par le provider OAuth — auto-link refuse",
            )

        account = await self._account_repo.get_active_by_email(email)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.OAUTH_EMAIL_NOT_FOUND,
            )

        await self._identity_repo.create(
            account_id=account.id,
            provider=provider,
            provider_subject=provider_subject,
            email_at_provider=email,
        )
        return account

    async def _open_session_and_issue(
        self,
        account,
        membership,
        ip_address: str,
        user_agent: Optional[str],
        request_id: Optional[str],
    ) -> Union[tuple[str, str, int, bool], MFARequiredResult]:
        """Ouvre session IAM v2, audit log, émet tokens JWT v3.

        S1.T10 (F404 / OAUTH-MFA-BYPASS-01) — Si l'account a un MFA enrole,
        retourne MFARequiredResult au lieu d'ouvrir la session : le client
        doit finaliser via POST /api/v1/auth/mfa/verify. Sans ce gate, la
        compromission d'un compte Google permettait acces total au compte
        CaroCorp meme avec MFA enrolee.
        """
        # F404 fix : MFA gate avant emission tokens (sinon bypass complet OAuth).
        has_mfa = await mfa_service.is_mfa_enabled(
            self.db, user_id=account.id, tenant_id=membership.tenant_id
        )
        if has_mfa:
            mfa_token = await mfa_service.create_mfa_session(
                user_id=account.id,
                tenant_id=membership.tenant_id,
                email=account.email,
                role=membership.role_name,
                ip_address=ip_address or "",
            )
            return MFARequiredResult(mfa_session_token=mfa_token)

        device_id = generate_device_id(user_agent or "unknown", ip_address)
        audit_service = AuditService(self.db)

        session = await self._session_svc.open(
            account_id=account.id,
            membership_id=membership.id,
            tenant_id=membership.tenant_id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.db.flush()

        await audit_service.log_login(
            user_id=account.id,
            tenant_id=membership.tenant_id,
            ip_address=ip_address,
            user_agent=user_agent or "unknown",
            request_id=request_id or "",
            success=True,
            email=account.email,
        )
        await self.db.commit()

        access_token, refresh_token, expires_in = await token_service.issue_tokens(
            user_id=account.id,
            tenant_id=membership.tenant_id,
            role=membership.role_name,
            device_id=device_id,
            session_id=session.session_id,
            membership_id=membership.id,
        )

        return access_token, refresh_token, expires_in, account.password_change_required
