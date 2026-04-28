"""Middleware mode dégradé 4 niveaux — graceful degradation (§S-08.4).

Niveaux (ordre de sévérité croissant) :
    NOMINAL          : Tout fonctionne normalement
    READ_ONLY        : Mutations bloquées (DB surcharge / maintenance)
    AUTH_DOWN        : Redis-SEC down — JWT sans vérif blacklist (FAIL-OPEN)
    EMERGENCY_BYPASS : Override d'urgence — auth court-circuitée (à utiliser avec précaution)

Activation des flags :
    POST /admin/degraded/enable  {level: "READ_ONLY", ttl_seconds: 3600}
    POST /admin/degraded/disable {level: "READ_ONLY"}

Transitions automatiques :
    Redis-SEC down  → AUTH_DOWN automatique (détection dans get_degradation_level)
    TTL expiré      → retour NOMINAL automatique
"""
import logging
from typing import Callable

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.constants import RedisKeys

logger = logging.getLogger(__name__)

# Méthodes HTTP qui modifient l'état — bloquées en READ_ONLY
_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Prefixes exemptés du blocage READ_ONLY (auth toujours accessible)
_READ_ONLY_EXEMPT_PREFIXES = (
    "/auth/",
    "/api/v1/auth/",
    "/.well-known/",
    "/health",
    "/metrics",
    "/api/docs",
    "/api/redoc",
    "/openapi.json",
)

# Préfixes admin de contrôle de la dégradation (toujours accessibles)
_DEGRADED_CONTROL_PREFIX = "/api/v1/admin/degraded"

# Mapping app → clé Redis pour dégradation par app
_APP_PREFIX_MAP = {
    "/api/v1/epicerie/": "degraded:epicerie",
    "/api/v1/restaurant/": "degraded:restaurant",
}
# Marveline = toutes les routes non-épicerie/restaurant → clé "degraded:marveline"
_MARVELINE_DEGRADED_KEY = "degraded:marveline"


def _is_exempt_from_read_only(path: str, method: str) -> bool:
    """Retourne True si la requête doit passer même en READ_ONLY."""
    if method not in _MUTATION_METHODS:
        return True  # GET/HEAD/OPTIONS toujours autorisés
    for prefix in _READ_ONLY_EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return True
    if path.startswith(_DEGRADED_CONTROL_PREFIX):
        return True
    return False


class DegradedModeMiddleware(BaseHTTPMiddleware):
    """Middleware de contrôle du mode dégradé (§S-08.4).

    Vérifie le niveau de dégradation actuel à chaque requête et adapte
    la réponse selon les règles de chaque niveau.

    Performance : 1 appel Redis-SEC par requête (GET flag). FAIL-OPEN si down.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        from app.core.redis import redis_sec  # import local anti-circularité

        # Vérifier d'abord la dégradation par app (granulaire)
        app_level = await self._get_app_degradation(request.url.path, redis_sec)
        if app_level and app_level != "NOMINAL":
            if app_level == "READ_ONLY":
                return await self._handle_read_only(request, call_next)

        # Ensuite la dégradation globale (legacy)
        level = await redis_sec.get_degradation_level()

        if level == "NOMINAL":
            return await call_next(request)

        if level == "READ_ONLY":
            return await self._handle_read_only(request, call_next)

        if level == "AUTH_DOWN":
            # AUTH_DOWN : laisser passer, le FAIL-OPEN de token_service gère
            logger.warning(
                "AUTH_DOWN mode: request passed without blacklist check path=%s",
                request.url.path,
            )
            return await call_next(request)

        if level == "EMERGENCY_BYPASS":
            logger.critical(
                "EMERGENCY_BYPASS active: auth bypassed path=%s method=%s",
                request.url.path, request.method,
            )
            return await call_next(request)

        return await call_next(request)

    async def _handle_read_only(self, request: Request, call_next: Callable):
        """READ_ONLY : bloque les mutations sauf pour auth et endpoints exemptés."""
        if _is_exempt_from_read_only(request.url.path, request.method):
            return await call_next(request)

        logger.warning(
            "READ_ONLY mode: mutation blocked path=%s method=%s",
            request.url.path, request.method,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "SERVICE_READ_ONLY",
                "message": "Le service est en mode lecture seule. Les modifications sont temporairement indisponibles.",
                "retry_after": 60,
            },
            headers={"Retry-After": "60"},
        )

    # Prefixes exemptés de toute dégradation par app
    _NO_DEGRADE_PREFIXES = ("/health", "/api/docs", "/api/redoc", "/openapi.json", "/.well-known/", "/metrics")

    @staticmethod
    async def _get_app_degradation(path: str, redis_sec) -> str | None:
        """Vérifie la dégradation par app (granulaire, indépendant du global).

        Clés Redis :
            degraded:epicerie    → "READ_ONLY" | "NOMINAL" | None
            degraded:restaurant  → idem
            degraded:marveline   → idem

        Returns:
            Niveau de dégradation ou None si pas de flag.
        """
        for exempt in DegradedModeMiddleware._NO_DEGRADE_PREFIXES:
            if path.startswith(exempt):
                return None

        redis_key = None
        for prefix, key in _APP_PREFIX_MAP.items():
            if path.startswith(prefix):
                redis_key = key
                break
        if redis_key is None:
            redis_key = _MARVELINE_DEGRADED_KEY

        try:
            level = await redis_sec.client.get(redis_key)
            return level.decode() if level else None
        except Exception:
            return None
