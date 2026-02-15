"""Middleware de contexte de requete pour CaroCorp API.

Fusionne 3 preoccupations en un seul middleware (performance) :
- Generation / propagation du X-Request-ID
- Extraction tenant_id + user_id depuis le JWT (fix M2: plus de hardcode, fix M3: parse unique)
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

from app.core.logging import set_request_context, clear_request_context

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

        # 2. Claims JWT (silencieux si absent ou invalide)
        claims = _extract_jwt_claims(request)
        tenant_id: Optional[int] = claims.get("tenant_id")
        user_id_raw = claims.get("sub")

        # sub est un string dans le JWT (spec), on le convertit en int
        user_id: Optional[int] = None
        if user_id_raw is not None:
            try:
                user_id = int(user_id_raw)
            except (ValueError, TypeError):
                pass

        # 3. Stocker dans request.state
        request.state.request_id = request_id
        request.state.tenant_id = tenant_id
        request.state.user_id = user_id

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
