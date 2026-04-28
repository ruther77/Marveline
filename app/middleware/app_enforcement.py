"""ISO-APP-01 — Middleware d'enforcement app↔tenant.

Vérifie que le JWT utilisé sur une requête API correspond à l'app déclarée
par le reverse proxy via le header `X-App-Code`.

Flow :
    1. Requête arrive avec JWT (tid=X) + header X-App-Code=marveline
    2. Middleware décode JWT, récupère `tid`
    3. Lookup Tenant(id=tid).app_code
    4. Si app_code ≠ X-App-Code → 403 FORBIDDEN

Mode rétrocompatible :
    - Si header X-App-Code absent → pas de block (log warning)
    - Une fois le reverse proxy déployé partout, activer mode strict.

Exemptions :
    - Health, docs, metrics, auth endpoints (pas de JWT requis)
    - Requêtes sans Authorization header (login initial, ressources publiques)
"""
import logging
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import get_async_db_context
from app.core.exceptions import TokenExpired, TokenInvalid
from app.core.security import decode_token
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

# Header injecté par le reverse proxy selon le Host / location
APP_CODE_HEADER = "X-App-Code"

# Paths exemptés : pas de JWT, donc rien à vérifier
EXEMPT_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/metrics",
    "/.well-known/",
    "/api/v1/auth/",
    "/api/v1/health",
)


class AppEnforcementMiddleware(BaseHTTPMiddleware):
    """Middleware ISO-APP-01 : bloque l'utilisation d'un JWT tid sur une app non correspondante."""

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path

        # Skip paths exemptés
        if any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return await call_next(request)

        # Skip si pas de Authorization Bearer (requête non-authentifiée)
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)

        app_code_header = request.headers.get(APP_CODE_HEADER)
        if not app_code_header:
            # Mode rétrocompatible : aucun reverse proxy ne fournit le header → log + skip
            logger.debug(
                "ISO-APP-01: %s header missing for %s, skipping enforcement (soft mode)",
                APP_CODE_HEADER, path,
            )
            return await call_next(request)

        # Décoder le JWT sans lever d'exception (laisser get_current_user faire le vrai check)
        token = auth_header.removeprefix("Bearer ").strip()
        try:
            claims = decode_token(token)
        except (TokenExpired, TokenInvalid):
            return await call_next(request)

        tid = claims.get("tid")
        if not tid:
            return await call_next(request)

        # Résoudre app_code du tenant
        try:
            tenant_id = int(tid)
        except (TypeError, ValueError):
            return await call_next(request)

        async with get_async_db_context() as db:
            tenant_app_code = await db.scalar(
                select(Tenant.app_code).where(Tenant.id == tenant_id)
            )

        if tenant_app_code is None:
            logger.warning("ISO-APP-01: tenant tid=%s not found", tid)
            return await call_next(request)

        if tenant_app_code != app_code_header:
            logger.warning(
                "ISO-APP-01 mismatch: JWT tid=%s (app_code=%s) used on app=%s path=%s",
                tid, tenant_app_code, app_code_header, path,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "error": "APP_TENANT_MISMATCH",
                    "message": (
                        f"Cannot access app '{app_code_header}' with credentials "
                        f"for app '{tenant_app_code}'"
                    ),
                    "detail": "Your account is not authorized on this app.",
                },
            )

        return await call_next(request)
