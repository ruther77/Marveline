"""Middleware Prometheus metrics pour CaroCorp.

Collecte automatiquement métriques RED (Rate, Errors, Duration) sur toutes requêtes HTTP.

Workflow :
1. Request arrive → Incrémenter http_requests_in_progress
2. Démarrer timer → Mesurer durée requête
3. Appeler next middleware → Obtenir response
4. Décrémenter http_requests_in_progress
5. Enregistrer métriques :
   - http_requests_total (counter) : +1
   - http_request_duration_seconds (histogram) : observe(duration)
6. Si 429 rate limit → Incrémenter rate_limit_hits_total

Notes :
- Middleware installé AVANT tous les autres (pour mesurer durée totale incluant middlewares)
- Pas d'exception levée (try/finally garantit décrémentation gauge)
- Path normalisé : /api/v1/products/123 → /api/v1/products/{id} (éviter cardinalité infinie)
"""
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from typing import Callable
import time
import re

from app.core.metrics import (
    http_requests_total,
    http_request_duration_seconds,
    http_requests_in_progress,
    rate_limit_hits_total,
)
from app.core.rate_limit_utils import determine_rate_limit_scope
from app.constants import AuthEndpoints, HTTPMethods, PATH_NORMALIZATION_PATTERNS, RateLimitScope


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware Prometheus metrics collection.

    Collecte métriques RED sur toutes requêtes :
    - Rate : http_requests_total
    - Errors : http_requests_total{status=~"5.."}
    - Duration : http_request_duration_seconds

    Pattern :
    - Gauge incremented BEFORE request processing
    - Gauge decremented AFTER request processing (try/finally)
    - Counter/Histogram recorded AFTER response

    Notes :
        - Path normalisé pour éviter cardinalité infinie (ID → {id})
        - 429 rate limit → incrémenter rate_limit_hits_total
        - Pas d'exemption (même /health et /metrics sont comptés)
    """

    def _normalize_path(self, path: str) -> str:
        r"""Normalise path en remplaçant IDs par {id}.

        Évite cardinalité infinie de métriques Prometheus.

        Args:
            path: Path original (ex: /api/v1/products/123)

        Returns:
            Path normalisé (ex: /api/v1/products/{id})

        Example:
            >>> self._normalize_path("/api/v1/products/123")
            '/api/v1/products/{id}'
            >>> self._normalize_path("/api/v1/reservations/456/confirm")
            '/api/v1/reservations/{id}/confirm'

        Notes:
            - Seuls IDs numériques remplacés (\d+)
            - UUID/slugs préservés (pas de pattern match)
            - Paths inconnus -> 'other' (S1.T12 / F1126 : anti-DoS cardinalité)
        """
        for pattern, replacement in PATH_NORMALIZATION_PATTERNS:
            if pattern.match(path):
                return pattern.sub(replacement, path)

        # S1.T12 (F1126) : aucun pattern -> "other" pour bloquer la cardinalite
        # explosion via paths random (UUID arbitraires) qui causerait un OOM
        # Prometheus en quelques minutes (exploit DoS sur monitoring).
        return "other"


    def _get_identifier_type(self, request: Request, scope: str) -> str:
        """Détermine type identifier (ip ou user_id) selon scope.

        Args:
            request: Request FastAPI
            scope: Rate limit scope

        Returns:
            "ip" ou "user_id"

        Logic:
            - user_authenticated scope → "user_id"
            - Autres scopes → "ip"

        Notes:
            - Utilisé comme label Prometheus : rate_limit_hits_total{identifier_type="ip"}
            - Permet distinguer rate limit par IP vs par user
        """
        if scope == RateLimitScope.USER_AUTHENTICATED:
            return "user_id"
        return "ip"

    async def dispatch(self, request: Request, call_next: Callable):
        """Collecte métriques Prometheus sur requête HTTP.

        Workflow :
        1. Normaliser path (/api/v1/products/123 → /api/v1/products/{id})
        2. Incrémenter gauge http_requests_in_progress
        3. Démarrer timer
        4. Appeler next middleware → Obtenir response
        5. Décrémenter gauge (try/finally)
        6. Mesurer durée totale
        7. Enregistrer métriques :
           - http_requests_total{method, path, status} +1
           - http_request_duration_seconds{method, path}.observe(duration)
        8. Si 429 rate limit → rate_limit_hits_total{scope, identifier_type} +1

        Args:
            request: Request FastAPI
            call_next: Next middleware

        Returns:
            Response FastAPI (inchangée, métriques collectées en background)

        Notes:
            - Pas d'exception levée (try/finally garantit cleanup)
            - Métriques enregistrées même si middleware suivant lève exception
            - Path normalisé pour éviter cardinalité infinie
        """
        # Normaliser path (éviter cardinalité infinie)
        path = self._normalize_path(request.url.path)
        method = request.method

        # Incrémenter gauge requêtes en cours
        http_requests_in_progress.labels(method=method, path=path).inc()

        # Démarrer timer
        start_time = time.time()

        try:
            # Appeler next middleware
            response = await call_next(request)

            # Mesurer durée
            duration = time.time() - start_time

            # Enregistrer métriques
            status = response.status_code

            # Counter requêtes total
            http_requests_total.labels(
                method=method,
                path=path,
                status=status
            ).inc()

            # Histogram durée requête
            http_request_duration_seconds.labels(
                method=method,
                path=path
            ).observe(duration)

            # Si 429 rate limit → incrémenter rate_limit_hits_total
            if status == 429:
                # Déterminer scope depuis request (logique centralisée)
                scope = determine_rate_limit_scope(request)
                identifier_type = self._get_identifier_type(request, scope)
                rate_limit_hits_total.labels(
                    scope=scope.value if hasattr(scope, 'value') else scope,
                    identifier_type=identifier_type
                ).inc()

            return response

        finally:
            # Décrémenter gauge (toujours exécuté, même si exception)
            http_requests_in_progress.labels(method=method, path=path).dec()
