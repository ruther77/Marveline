"""Middleware de contexte de requete pour CaroCorp API.

Fusionne 4 preoccupations en un seul middleware (performance) :
- Generation / propagation du X-Request-ID
- Extraction tenant_id + user_id depuis le JWT OU API key (fix M2: plus de hardcode, fix M3: parse unique)
- Detection dual-mode authentication (Bearer JWT vs X-API-Key header)
- Positionnement des ContextVars pour le structured logging

Usage :
    Le middleware est ajoute dans main.py via app.add_middleware(RequestContextMiddleware).
    Toutes les requetes passent par ce middleware.
"""

import logging
import uuid
from typing import Any, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.database import get_db_context
from app.core.deps import X_API_KEY_HEADER
from app.core.logging import set_request_context, clear_request_context
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


def _extract_api_key_info(request: Request) -> Dict[str, Any]:
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
        # Creer session DB temporaire pour validation
        with get_db_context() as db:
            api_key_service = ApiKeyService(db)
            api_key = api_key_service.validate_key(api_key_value)

            if not api_key or not api_key.is_active:
                return {}

            # Retourner infos pour request.state
            return {
                "tenant_id": api_key.tenant_id,
                "api_key_id": api_key.id,
                "scopes": api_key.scopes,
            }
    except Exception as e:
        # Log erreur mais ne bloque pas la requete (fail-safe)
        logger.warning(f"API key validation error: {e}")
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
        # 1. Request ID : recuperer ou generer
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        # 2. Dual-mode authentication : JWT d'abord, puis API key
        claims = _extract_jwt_claims(request)
        api_key_info = _extract_api_key_info(request) if not claims else {}

        # 3. Extraire tenant_id, user_id, api_key_id selon mode auth
        tenant_id: Optional[int] = None
        user_id: Optional[int] = None
        api_key_id: Optional[int] = None
        principal_type: Optional[str] = None

        if claims:
            # Mode JWT : extraire tenant_id et user_id depuis claims
            tenant_id = claims.get("tenant_id")
            user_id_raw = claims.get("sub")

            # sub est un string dans le JWT (spec), on le convertit en int
            if user_id_raw is not None:
                try:
                    user_id = int(user_id_raw)
                    principal_type = "user"
                except (ValueError, TypeError):
                    pass
        elif api_key_info:
            # Mode API key : extraire tenant_id et api_key_id depuis validation
            tenant_id = api_key_info.get("tenant_id")
            api_key_id = api_key_info.get("api_key_id")
            principal_type = "api_key"

        # 4. Stocker dans request.state
        request.state.request_id = request_id
        request.state.tenant_id = tenant_id
        request.state.user_id = user_id
        request.state.principal_type = principal_type
        request.state.api_key_id = api_key_id

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
