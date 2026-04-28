"""Middleware de contexte de requete pour CaroCorp API.

Fusionne 5 preoccupations en un seul middleware (performance) :
- Generation / propagation du X-Request-ID
- Extraction tenant_id + user_id depuis le JWT OU API key (fix M2: plus de hardcode, fix M3: parse unique)
- Detection dual-mode authentication (Bearer JWT vs X-API-Key header)
- Resolution de l'objet Tenant complet -> request.state.tenant (S1.T11 — F368 WebAuthn multi-tenant)
- Positionnement des ContextVars pour le structured logging

Usage :
    Le middleware est ajoute dans main.py via app.add_middleware(RequestContextMiddleware).
    Toutes les requetes passent par ce middleware.
"""

import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.database import get_async_db_context
from app.core.deps import X_API_KEY_HEADER
from app.core.logging import set_request_context, clear_request_context
from app.models.tenant import Tenant
from app.services.api_key import ApiKeyService

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


def _extract_jwt_claims(request: Request) -> Dict[str, Any]:
    """Extrait les claims JWT depuis le header Authorization.

    Parse le JWT une seule fois par requete (fix M3).
    Ne bloque jamais — retourne un dict vide si pas de token ou token invalide.

    Returns:
        Dict avec les claims ou {} si pas de JWT valide.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return {}

    token = auth_header[7:]  # len("Bearer ") == 7
    if not token:
        return {}

    try:
        from app.core.security import decode_token
        claims = decode_token(token)
        return claims if claims else {}
    except Exception:
        return {}


async def _load_tenant(tenant_id: Optional[int]) -> Optional[Tenant]:
    """Charge l'objet Tenant complet depuis tenant_id (S1.T11 — F368).

    Utilise par WebAuthnService et autres services per-tenant (rp_id, frontend_url, brand).
    Ne bloque jamais — retourne None si tenant_id absent ou DB error.
    Renvoie une instance detachee de la session (utilisable hors request scope).
    """
    if tenant_id is None:
        return None
    try:
        async with get_async_db_context() as db:
            result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if tenant is not None:
                # Detacher de la session pour usage hors scope (request.state)
                db.expunge(tenant)
            return tenant
    except Exception as exc:
        logger.warning("Failed to load tenant id=%s in request context: %s", tenant_id, exc)
        return None


async def _extract_api_key_info(request: Request) -> Dict[str, Any]:
    """Extrait les infos API key depuis le header X-API-Key.

    Valide la cle via ApiKeyService (cache Redis + DB fallback).
    Ne bloque jamais — retourne un dict vide si pas de cle ou cle invalide.

    Returns:
        Dict avec {tenant_id, api_key_id, scopes} si valide, {} sinon.
    """
    api_key_value = request.headers.get(X_API_KEY_HEADER, "")
    if not api_key_value:
        return {}

    try:
        async with get_async_db_context() as db:
            api_key_service = ApiKeyService(db)
            api_key = await api_key_service.validate_key(api_key_value)

            if not api_key or not api_key.is_active:
                return {}

            return {
                "tenant_id": api_key.tenant_id,
                "api_key_id": api_key.id,
                "scopes": api_key.scopes,
            }
    except Exception as e:
        logger.warning("API key validation error: %s", e)
        return {}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware unifie pour le contexte de requete.

    Pour chaque requete :
    1. Genere ou propage X-Request-ID (UUID v4)
    2. Parse le JWT (si present) pour extraire tenant_id et user_id
    3. Positionne request.state.{request_id, tenant_id, user_id}
    4. Positionne les ContextVars pour le structured logging
    5. Ajoute X-Request-ID dans la response
    6. Nettoie les ContextVars en finally
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Reset N+1 query counter per request
        from app.core.slow_query import reset_query_counter
        reset_query_counter()

        # 1. Request ID : recuperer ou generer
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        # 2. Dual-mode authentication : JWT d'abord, puis API key
        claims = _extract_jwt_claims(request)
        api_key_info = await _extract_api_key_info(request) if not claims else {}

        # 3. Extraire tenant_id, user_id, api_key_id selon mode auth
        tenant_id: Optional[int] = None
        user_id: Optional[int] = None
        api_key_id: Optional[int] = None
        principal_type: Optional[str] = None

        jwt_scopes: list = []

        if claims:
            # Mode JWT : extraire tenant_id et user_id depuis claims (v3 : "tid" et "sub")
            tid_raw = claims.get("tid") or claims.get("tenant_id")  # compat v2
            tenant_id = int(tid_raw) if tid_raw is not None else None
            user_id_raw = claims.get("sub")

            # sub est un string dans le JWT (spec), on le convertit en int
            if user_id_raw is not None:
                try:
                    user_id = int(user_id_raw)
                    principal_type = "user"
                except (ValueError, TypeError):
                    pass

            # Extraire scopes JWT (claim "scopes" — liste de strings)
            jwt_scopes = claims.get("scopes") or []
        elif api_key_info:
            # Mode API key : extraire tenant_id, api_key_id et scopes depuis validation
            tenant_id = api_key_info.get("tenant_id")
            api_key_id = api_key_info.get("api_key_id")
            principal_type = "api_key"
            jwt_scopes = list(api_key_info.get("scopes") or [])

        # 4. Resoudre l'objet Tenant complet (S1.T11 — F368)
        # Utilise par WebAuthnService (rp_id, frontend_url) et services per-tenant.
        # Si tenant_id None ou tenant introuvable -> request.state.tenant = None (consumers font fallback).
        tenant = await _load_tenant(tenant_id)

        # 5. Stocker dans request.state
        request.state.request_id = request_id
        request.state.tenant_id = tenant_id
        request.state.tenant = tenant
        request.state.user_id = user_id
        request.state.principal_type = principal_type
        request.state.api_key_id = api_key_id
        request.state.jwt_scopes = jwt_scopes

        # 4. Positionner les ContextVars (logging structure)
        set_request_context(
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        try:
            response = await call_next(request)
            # 5. Ajouter X-Request-ID dans la response
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            # 6. Nettoyer les ContextVars
            clear_request_context()
