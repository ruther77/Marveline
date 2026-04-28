"""Middleware CORS strict — defense-in-depth (§7.4 S-10.3).

Complète CORSMiddleware FastAPI (headers standards) en bloquant explicitement
les origines non autorisées avec 403 + log WARNING.

Position dans la chaîne d'exécution :
    TrustedHostMiddleware → StrictCORSMiddleware → CORSMiddleware → ...
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)


_NGROK_SUFFIX = ".ngrok-free.dev"
_TRYCF_SUFFIX = ".trycloudflare.com"


def _build_allowed_origins() -> frozenset[str]:
    """Construit la whitelist CORS à partir de la config."""
    return frozenset(settings.CORS_ORIGINS)


def _is_ngrok_origin(origin: str) -> bool:
    """Vérifie qu'une origine est un sous-domaine tunnel légitime (ngrok, trycloudflare).

    Uniquement en DEBUG — en prod, la whitelist est stricte.
    """
    if not settings.DEBUG:
        return False
    try:
        from urllib.parse import urlparse
        parsed = urlparse(origin)
        if parsed.scheme != "https" or parsed.hostname is None:
            return False
        return (
            parsed.hostname.endswith(_NGROK_SUFFIX)
            or parsed.hostname.endswith(_TRYCF_SUFFIX)
        )
    except Exception:
        return False


class StrictCORSMiddleware(BaseHTTPMiddleware):
    """Middleware CORS defense-in-depth (§7.4 S-10.3).

    Bloque les origines non autorisées avant qu'elles atteignent CORSMiddleware.

    Comportement :
        - Origin absente (mobile Bearer, curl, etc.)  → laissé passer
        - Origin dans la whitelist CORS_ORIGINS       → laissé passer + Vary: Origin
        - Origin ngrok-free.dev en DEBUG              → laissé passer + Vary: Origin
        - Origin hors whitelist                       → 403 + log WARNING

    Règles absolues (§7.4) :
        - Jamais de wildcard (*) — la whitelist est fermée
        - Jamais de reflection dynamique (Origin copié aveuglément)
        - Subdomain wildcard (*.carocorp.io) interdit
        - Exception DEV uniquement : *.ngrok-free.dev accepté si DEBUG=true
    """

    def __init__(self, app):
        super().__init__(app)
        self._allowed_origins: frozenset[str] = _build_allowed_origins()

    async def dispatch(self, request: Request, call_next) -> JSONResponse:
        origin = request.headers.get("origin")

        if origin is None:
            # Requête sans origine (mobile/API Bearer, curl, tests) — laissée passer
            return await call_next(request)

        if origin not in self._allowed_origins and not _is_ngrok_origin(origin):
            logger.warning(
                "CORS violation blocked: origin=%r path=%s method=%s",
                origin,
                request.url.path,
                request.method,
            )
            return JSONResponse(
                content={"detail": "Origin not allowed"},
                status_code=403,
            )

        response = await call_next(request)
        # Indique aux caches intermédiaires que la réponse varie selon l'origine
        response.headers["Vary"] = "Origin"
        return response
