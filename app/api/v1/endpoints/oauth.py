"""Endpoints OAuth 2.0 (Google, GitHub, Facebook) — Authorization Code flow.

Security:
    - state single-use (GETDEL atomique, TTL 300s, Redis-SEC FAIL-CLOSED)
    - PKCE S256 pour Google
    - client_secret jamais loggué ni transmis côté client
    - Pas de création de compte — liaison uniquement sur compte admin existant
"""
import base64
import hashlib
import logging
import secrets
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.errors import ErrorMessages
from app.core.config import settings
from app.core.deps import UserCompat
from app.core.exceptions import NotFound
from app.core.database import get_async_db
from app.core.redis import redis_sec
from app.models.account import Account
from app.models.account_oauth_identity import AccountOAuthIdentity
from app.models.tenant_membership import TenantMembership
from app.schemas.auth import TokenResponse
from app.services.audit import AuditService
from app.services.session import generate_device_id, session_service
from app.services.token import token_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["OAuth"])

_REFRESH_COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 jours

# ─── Configuration statique des providers ─────────────────────────────────────

_PROVIDERS: dict[str, dict] = {
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


def _client_id(provider: str) -> str:
    return {
        "google": settings.OAUTH_GOOGLE_CLIENT_ID,
        "github": settings.OAUTH_GITHUB_CLIENT_ID,
        "facebook": settings.OAUTH_FACEBOOK_CLIENT_ID,
    }.get(provider, "")


def _client_secret(provider: str) -> str:
    return {
        "google": settings.OAUTH_GOOGLE_CLIENT_SECRET,
        "github": settings.OAUTH_GITHUB_CLIENT_SECRET,
        "facebook": settings.OAUTH_FACEBOOK_CLIENT_SECRET,
    }.get(provider, "")


def _redirect_uri(provider: str) -> str:
    return {
        "google": settings.OAUTH_GOOGLE_REDIRECT_URI,
        "github": settings.OAUTH_GITHUB_REDIRECT_URI,
        "facebook": settings.OAUTH_FACEBOOK_REDIRECT_URI,
    }.get(provider, "")


def _active_providers() -> list[str]:
    """Providers avec CLIENT_ID configuré."""
    return [p for p in _PROVIDERS if _client_id(p)]


def _require_provider(provider: str) -> dict:
    """Valide le provider ; 404 si inconnu ou non configuré."""
    if provider not in _PROVIDERS:
        raise NotFound("Unknown OAuth provider")
    if not _client_id(provider):
        raise NotFound("OAuth provider not configured")
    return _PROVIDERS[provider]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _pkce_challenge(verifier: str) -> str:
    """PKCE S256 : base64url(SHA256(verifier))."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


async def _exchange_code(
    provider: str,
    code: str,
    cfg: dict,
    code_verifier: Optional[str],
) -> str:
    """Échange le code contre l'access_token du provider (httpx, timeout 10s).

    Returns: access_token provider (str).
    Raises: HTTPException 502 si l'échange échoue.
    """
    payload = {
        "code": code,
        "client_id": _client_id(provider),
        "client_secret": _client_secret(provider),
        "redirect_uri": _redirect_uri(provider),
        "grant_type": "authorization_code",
    }
    if code_verifier:
        payload["code_verifier"] = code_verifier
    headers = {"Accept": "application/json"} if provider == "github" else {}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(cfg["token_url"], data=payload, headers=headers)

    if resp.status_code != 200:
        logger.error("OAuth token exchange failed for %s (HTTP %s)", provider, resp.status_code)
        raise HTTPException(status_code=502, detail="OAuth token exchange failed")

    data = resp.json()
    token = data.get("access_token")
    if not token:
        logger.error("No access_token in OAuth response for %s", provider)
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
    """Email primaire vérifié via GET /user/emails (GitHub — email parfois null)."""
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


async def _lookup_or_link_user(
    db: AsyncSession,
    provider: str,
    oauth_id: str,
    email: str,
) -> UserCompat:
    """Cherche un compte par (provider, provider_subject) ou le lie via email (IAM v2).

    1. Lookup AccountOAuthIdentity (provider, oauth_id) → Account déjà lié.
    2. Lookup Account par email → liaison automatique (crée AccountOAuthIdentity).
    3. Introuvable, inactif ou membership ambigu → 400.
    Raises: HTTPException 400.
    """
    account: Optional[Account] = None

    identity = (await db.execute(
        select(AccountOAuthIdentity).where(
            AccountOAuthIdentity.provider == provider,
            AccountOAuthIdentity.provider_subject == oauth_id,
        )
    )).scalar_one_or_none()

    if identity:
        account = (await db.execute(
            select(Account).where(
                Account.id == identity.account_id,
                Account.is_active.is_(True),
            )
        )).scalar_one_or_none()

    if not account:
        # Auto-link par email — FOR UPDATE évite double-write race condition
        accounts = (await db.execute(
            select(Account).where(
                Account.email == email.lower().strip(),
                Account.is_active.is_(True),
            ).with_for_update()
        )).scalars().all()

        if not accounts:
            raise HTTPException(status_code=400, detail=ErrorMessages.OAUTH_EMAIL_NOT_FOUND)
        if len(accounts) > 1:
            raise HTTPException(
                status_code=400,
                detail="Email ambigu (plusieurs comptes). Contactez votre administrateur.",
            )
        account = accounts[0]
        db.add(AccountOAuthIdentity(
            account_id=account.id,
            provider=provider,
            provider_subject=oauth_id,
            email_at_provider=email,
        ))
        await db.flush()

    # Membership unique actif pour ce compte (OAuth sans contexte tenant)
    memberships = (await db.execute(
        select(TenantMembership).where(
            TenantMembership.account_id == account.id,
            TenantMembership.status == "active",
            TenantMembership.revoked_at.is_(None),
        )
    )).scalars().all()

    if not memberships:
        raise HTTPException(status_code=400, detail=ErrorMessages.OAUTH_EMAIL_NOT_FOUND)
    if len(memberships) > 1:
        raise HTTPException(
            status_code=400,
            detail="Compte appartient à plusieurs tenants. Contactez votre administrateur.",
        )
    return UserCompat(account, memberships[0])


async def _issue_oauth_tokens(
    db: AsyncSession,
    user: UserCompat,
    ip_address: str,
    user_agent: str,
    response: Response,
) -> TokenResponse:
    """Crée session + émet JWT + pose cookie refresh_token (même pattern que login classique)."""
    device_id = generate_device_id(user_agent, ip_address)
    audit_service = AuditService(db)

    await audit_service.log_login(
        user_id=user.id,
        tenant_id=user.tenant_id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=None,
        success=True,
        email=user.email,
    )
    session_id = await session_service.create_session(
        db=db,
        user_id=user.id,
        tenant_id=user.tenant_id,
        device_id=device_id,
        ip_address=ip_address,
        user_agent=user_agent,
        mfa_verified=False,
    )
    await db.commit()

    access_token, refresh_token, expires_in = await token_service.issue_tokens(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        device_id=device_id,
        session_id=session_id,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=_REFRESH_COOKIE_MAX_AGE,
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        password_change_required=user.password_change_required,
    )


# ─── Schéma body ──────────────────────────────────────────────────────────────

class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/providers", status_code=status.HTTP_200_OK)
async def list_providers():
    """Liste les providers OAuth actifs (CLIENT_ID configuré).

    Aucune auth requise — appelé depuis la page de login avant toute session.
    """
    icons = {"google": "google", "github": "github", "facebook": "facebook"}
    colors = {
        "google": "bg-white text-gray-700",
        "github": "bg-[#24292E] text-white",
        "facebook": "bg-[#1877F2] text-white",
    }
    return {
        "providers": [
            {
                "provider": p,
                "name": _PROVIDERS[p]["name"],
                "icon": icons.get(p, p),
                "color": colors.get(p, ""),
                "enabled": True,
            }
            for p in _active_providers()
        ]
    }


@router.get("/{provider}/authorize", status_code=status.HTTP_200_OK)
async def authorize(provider: str):
    """Génère state + auth_url vers le provider.

    Security:
        - state 32 bytes aléatoires, stocké Redis-SEC TTL=300s (FAIL-CLOSED)
        - PKCE S256 pour Google (code_verifier stocké dans state, jamais transmis)
    """
    cfg = _require_provider(provider)
    state = secrets.token_urlsafe(32)
    state_data: dict = {"provider": provider}

    query_params: dict[str, str] = {
        "client_id": _client_id(provider),
        "redirect_uri": _redirect_uri(provider),
        "scope": " ".join(cfg["scopes"]),
        "state": state,
        "response_type": "code",
    }

    if cfg.get("pkce"):
        verifier = secrets.token_urlsafe(64)
        state_data["code_verifier"] = verifier
        query_params["code_challenge"] = _pkce_challenge(verifier)
        query_params["code_challenge_method"] = "S256"

    try:
        await redis_sec.store_oauth_state(state, state_data, ttl=300)
    except Exception:
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")

    return {"auth_url": f"{cfg['auth_url']}?{urlencode(query_params)}"}


@router.post("/{provider}/callback", status_code=status.HTTP_200_OK)
async def callback(
    provider: str,
    body: OAuthCallbackRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
):
    """Traite le callback OAuth après retour du provider.

    Security:
        - state validé et consommé atomiquement (single-use, FAIL-CLOSED)
        - provider dans le state vérifié (anti-tamper)
        - code_verifier jamais exposé côté client
    """
    cfg = _require_provider(provider)
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent", "unknown")

    try:
        state_data = await redis_sec.consume_oauth_state(body.state)
    except Exception:
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")

    if not state_data or state_data.get("provider") != provider:
        raise HTTPException(status_code=400, detail=ErrorMessages.OAUTH_STATE_INVALID)

    provider_token = await _exchange_code(
        provider, body.code, cfg, state_data.get("code_verifier")
    )
    userinfo = await _get_userinfo(provider, provider_token, cfg)

    if not userinfo.get("email"):
        raise HTTPException(status_code=400, detail="Email non fourni par le provider OAuth")

    user = await _lookup_or_link_user(db, provider, userinfo["id"], userinfo["email"])
    return await _issue_oauth_tokens(db, user, ip_address, user_agent, response)
