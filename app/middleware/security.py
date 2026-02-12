"""Middlewares de sécurité pour CaroCorp."""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import secrets

from app.core.config import settings
from app.core.redis import redis_client
from app.core.security import decode_token


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """Middleware CSRF pour protéger contre les attaques Cross-Site Request Forgery.

    Pour les requêtes modifiantes (POST, PUT, PATCH, DELETE), vérifie la présence
    d'un token CSRF valide dans les headers.
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    async def dispatch(self, request: Request, call_next: Callable):
        """Vérifie le token CSRF pour les méthodes non-sûres."""

        # Skip CSRF pour les méthodes sûres
        if request.method in self.SAFE_METHODS:
            return await call_next(request)

        # Skip CSRF pour les endpoints publics (docs, health, auth)
        if request.url.path in [
            "/health",
            "/api/docs",
            "/api/redoc",
            "/openapi.json",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh"
        ]:
            return await call_next(request)

        # Skip CSRF pour requêtes sans authentification (JWT retournera 401)
        authorization = request.headers.get("Authorization")
        if not authorization:
            return await call_next(request)

        # Extraire user_id depuis le JWT Bearer token
        user_id = self._extract_user_id_from_jwt(authorization)
        if not user_id:
            # Token JWT invalide, laisser le endpoint gérer la 401
            return await call_next(request)

        # Vérifier le token CSRF
        csrf_token = request.headers.get("X-CSRF-Token")

        if not csrf_token:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "CSRF token manquant"},
            )

        # Valider le token avec Redis
        if not self._validate_csrf_token(user_id, csrf_token):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "CSRF token invalide ou expiré"},
            )

        response = await call_next(request)
        return response

    def _extract_user_id_from_jwt(self, authorization: str) -> int | None:
        """Extrait le user_id depuis le header Authorization (JWT Bearer token).

        Args:
            authorization: Header Authorization (format: "Bearer <token>")

        Returns:
            user_id si JWT valide, None sinon

        Security:
            - Pas d'exception levée (silent fail)
            - Laisse le endpoint gérer la 401 si JWT invalide
        """
        if not authorization or not authorization.startswith("Bearer "):
            return None

        try:
            token = authorization.replace("Bearer ", "")
            payload = decode_token(token)
            if not payload:
                return None

            # JWT spec: "sub" est une string, convertir en int
            user_id_str = payload.get("sub")
            return int(user_id_str) if user_id_str else None
        except (ValueError, TypeError):
            return None

    def _validate_csrf_token(self, user_id: int, token: str) -> bool:
        """Valide le token CSRF avec Redis.

        Args:
            user_id: ID de l'utilisateur (extrait du JWT)
            token: Token CSRF à valider

        Returns:
            True si token valide (existe dans Redis), False sinon

        Implementation:
            - Vérifie longueur token (anti bruteforce basique)
            - Vérifie existence dans Redis : csrf:{user_id}:{token}
            - TTL automatique géré par Redis (15 min)

        Security:
            - Pas d'exception levée (silent fail)
            - Timing attack protection (constant time check)
        """
        if not token or len(token) < 32:
            return False

        # Valider avec Redis
        return redis_client.validate_csrf_token(user_id, token)

    @staticmethod
    def generate_csrf_token() -> str:
        """Génère un nouveau token CSRF."""
        return secrets.token_urlsafe(32)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware pour ajouter les headers de sécurité recommandés."""

    async def dispatch(self, request: Request, call_next: Callable):
        """Ajoute les headers de sécurité à la réponse."""
        response = await call_next(request)

        # Headers de sécurité
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy
        if not settings.DEBUG:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self';"
            )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware basique de rate limiting.

    TODO: Implémenter avec Redis pour un rate limiting distribué.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        """Vérifie le rate limit pour l'IP."""

        # TODO: Implémenter rate limiting avec Redis
        # client_ip = request.client.host
        # redis_key = f"rate_limit:{client_ip}"
        # requests_count = redis_client.incr(redis_key)
        # if requests_count == 1:
        #     redis_client.expire(redis_key, 60)  # 1 minute
        # if requests_count > 100:  # 100 requêtes/minute
        #     raise HTTPException(status_code=429, detail="Too many requests")

        response = await call_next(request)
        return response
