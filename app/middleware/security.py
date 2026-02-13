"""Middlewares de sécurité pour CaroCorp."""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, Optional
import secrets

from app.core.config import settings
from app.core.redis import redis_client
from app.core.security import decode_token
from app.core.rate_limiter import RateLimiter
from app.constants import AuthEndpoints, ErrorMessages, HealthEndpoints, HTTPMethods, Limits, PublicEndpoints, RateLimitScope, SecurityHeaders


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """Middleware CSRF pour protéger contre les attaques Cross-Site Request Forgery.

    Pour les requêtes modifiantes (POST, PUT, PATCH, DELETE), vérifie la présence
    d'un token CSRF valide dans les headers.
    """

    SAFE_METHODS = HTTPMethods.SAFE_METHODS

    async def dispatch(self, request: Request, call_next: Callable):
        """Vérifie le token CSRF pour les méthodes non-sûres."""

        # Skip CSRF pour les méthodes sûres
        if request.method in self.SAFE_METHODS:
            return await call_next(request)

        # Skip CSRF pour les endpoints publics (docs, health, auth)
        if request.url.path in {
            PublicEndpoints.HEALTH,
            PublicEndpoints.DOCS,
            PublicEndpoints.REDOC,
            PublicEndpoints.OPENAPI,
            AuthEndpoints.LOGIN,
            AuthEndpoints.REFRESH,
        }:
            return await call_next(request)

        # Skip CSRF pour requêtes sans authentification (JWT retournera 401)
        authorization = request.headers.get(SecurityHeaders.AUTHORIZATION)
        if not authorization:
            return await call_next(request)

        # Extraire user_id depuis le JWT Bearer token
        user_id = self._extract_user_id_from_jwt(authorization)
        if not user_id:
            # Token JWT invalide, laisser le endpoint gérer la 401
            return await call_next(request)

        # Vérifier le token CSRF
        csrf_token = request.headers.get(SecurityHeaders.X_CSRF_TOKEN)

        if not csrf_token:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": ErrorMessages.CSRF_TOKEN_MISSING},
            )

        # Valider le token avec Redis
        if not self._validate_csrf_token(user_id, csrf_token):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": ErrorMessages.CSRF_TOKEN_INVALID},
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
        if not authorization or not authorization.startswith(SecurityHeaders.BEARER_PREFIX):
            return None

        try:
            token = authorization.replace(SecurityHeaders.BEARER_PREFIX, "")
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
        if not token or len(token) < Limits.CSRF_TOKEN_MIN_LENGTH:
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
        response.headers[SecurityHeaders.X_CONTENT_TYPE_OPTIONS] = SecurityHeaders.NOSNIFF
        response.headers[SecurityHeaders.X_FRAME_OPTIONS] = SecurityHeaders.DENY
        response.headers[SecurityHeaders.X_XSS_PROTECTION] = SecurityHeaders.XSS_BLOCK
        response.headers[SecurityHeaders.STRICT_TRANSPORT_SECURITY] = SecurityHeaders.HSTS_ONE_YEAR
        response.headers[SecurityHeaders.REFERRER_POLICY] = SecurityHeaders.STRICT_ORIGIN_CROSS_ORIGIN

        # Content Security Policy
        if not settings.DEBUG:
            response.headers[SecurityHeaders.CONTENT_SECURITY_POLICY] = SecurityHeaders.CSP_DEFAULT

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware de rate limiting multi-niveaux basé sur Redis.

    Protège l'API contre les abus et attaques DDoS via rate limiting distribué.

    Stratégie multi-niveaux :
    1. Global IP : 1000 req/min (protection DDoS générale)
    2. Login endpoint : 5 req/min (anti brute force auth)
    3. User authentifié : 200 req/min (quota utilisateur)
    4. Mutations (POST/PUT/DELETE) : 100 req/min (protection write abuse)
    5. Reads (GET) : 300 req/min (protection read abuse)

    Headers 429 retournés (RFC 6585) :
    - X-RateLimit-Limit : Limite maximale
    - X-RateLimit-Remaining : Requêtes restantes
    - X-RateLimit-Reset : Timestamp Unix reset
    - Retry-After : Secondes à attendre

    Example réponse 429:
        HTTP/1.1 429 Too Many Requests
        X-RateLimit-Limit: 5
        X-RateLimit-Remaining: 0
        X-RateLimit-Reset: 1709123456
        Retry-After: 42

        {
          "detail": "Rate limit exceeded for scope 'login'. Retry after 42 seconds."
        }

    Notes:
        - Skip health checks (/health, /health/ready, /health/live)
        - Skip Swagger docs (/api/docs, /api/redoc, /openapi.json)
        - Fail-open si Redis down (disponibilité > sécurité)
        - Headers ajoutés même pour 200 OK (permet clients intelligents)
    """

    # Endpoints exemptés de rate limiting
    EXEMPT_PATHS = {
        HealthEndpoints.BASE,
        HealthEndpoints.READY,
        HealthEndpoints.LIVE,
        PublicEndpoints.DOCS,
        PublicEndpoints.REDOC,
        PublicEndpoints.OPENAPI,
    }

    def __init__(self, app):
        """Initialise le middleware avec RateLimiter Redis."""
        super().__init__(app)
        self.rate_limiter = RateLimiter(redis_client.client)

    def _get_client_ip(self, request: Request) -> str:
        """Extrait l'IP du client depuis la requête.

        Gère les proxies/load balancers via header X-Forwarded-For.

        Args:
            request: Requête FastAPI

        Returns:
            IP du client (string)

        Notes:
            - X-Forwarded-For format : "client, proxy1, proxy2"
            - On prend la première IP (client réel)
            - Fallback sur request.client.host si header absent
        """
        forwarded_for = request.headers.get(SecurityHeaders.X_FORWARDED_FOR)
        if forwarded_for:
            # Prendre la première IP (client réel)
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_user_id(self, request: Request) -> Optional[int]:
        """Extrait le user_id depuis le JWT token si présent.

        Args:
            request: Requête FastAPI

        Returns:
            User ID ou None si non authentifié

        Notes:
            - Parse header Authorization: Bearer <token>
            - Décode JWT pour extraire 'sub' claim
            - Retourne None si token absent/invalide
        """
        auth_header = request.headers.get(SecurityHeaders.AUTHORIZATION)
        if not auth_header or not auth_header.startswith(SecurityHeaders.BEARER_PREFIX):
            return None

        try:
            token = auth_header.split(" ")[1]
            payload = decode_token(token)
            return payload.get("sub")  # user_id
        except Exception:
            return None

    def _determine_scope(self, request: Request) -> str:
        """Détermine le scope de rate limit selon la requête.

        Priorités (ordre de vérification) :
        1. Login endpoint → "login" (5 req/min strict)
        2. User authentifié → "user_authenticated" (200 req/min)
        3. Mutations (POST/PUT/DELETE) → "mutations" (100 req/min)
        4. Reads (GET) → "reads" (300 req/min)

        Args:
            request: Requête FastAPI

        Returns:
            Nom du scope (string)

        Notes:
            - Global IP toujours vérifié en amont (pas retourné ici)
            - Login scope = endpoint exact match
            - User scope = JWT présent et valide
        """
        # Scope login (brute force protection)
        if request.url.path == AuthEndpoints.LOGIN:
            return RateLimitScope.LOGIN

        # Scope user authentifié (quota utilisateur)
        if self._get_user_id(request) is not None:
            return RateLimitScope.USER_AUTHENTICATED

        # Scope mutations (write-heavy abuse)
        if request.method in HTTPMethods.UNSAFE_METHODS:
            return RateLimitScope.MUTATIONS

        # Scope reads (read-heavy abuse)
        return RateLimitScope.READS

    async def dispatch(self, request: Request, call_next: Callable):
        """Vérifie les rate limits multi-niveaux avant d'autoriser la requête.

        Workflow:
        1. Skip endpoints exemptés (health, docs)
        2. Vérifier global IP (1000 req/min)
        3. Déterminer scope spécifique (login/user/mutations/reads)
        4. Vérifier scope spécifique
        5. Si limite dépassée → 429 avec headers
        6. Sinon → ajouter headers rate limit et continuer

        Args:
            request: Requête FastAPI
            call_next: Fonction suivante dans la chaîne middleware

        Returns:
            Response FastAPI (200 ou 429)

        Raises:
            Aucune exception (fail-open si Redis down)
        """
        # Skip endpoints exemptés
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        client_ip = self._get_client_ip(request)

        # ===== Niveau 1 : Global IP (toujours vérifié) =====
        global_key = self.rate_limiter.build_key(RateLimitScope.GLOBAL_IP, client_ip)
        global_limit, global_window = self.rate_limiter.get_scope_config(RateLimitScope.GLOBAL_IP)
        global_allowed, global_meta = self.rate_limiter.check_rate_limit(
            key=global_key,
            limit=global_limit,
            window_seconds=global_window
        )

        if not global_allowed:
            return self._rate_limit_response(
                scope=RateLimitScope.GLOBAL_IP,
                metadata=global_meta
            )

        # ===== Niveau 2 : Scope spécifique =====
        scope = self._determine_scope(request)

        # Identifier pour le scope
        if scope == RateLimitScope.LOGIN:
            # Pour login, rate limit par IP uniquement
            identifier = client_ip
        elif scope == RateLimitScope.USER_AUTHENTICATED:
            # Pour user, rate limit par user_id
            user_id = self._get_user_id(request)
            identifier = str(user_id) if user_id else client_ip
        else:
            # Pour mutations/reads, rate limit par IP
            identifier = client_ip

        scope_key = self.rate_limiter.build_key(scope, identifier)
        scope_limit, scope_window = self.rate_limiter.get_scope_config(scope)
        scope_allowed, scope_meta = self.rate_limiter.check_rate_limit(
            key=scope_key,
            limit=scope_limit,
            window_seconds=scope_window
        )

        if not scope_allowed:
            return self._rate_limit_response(
                scope=scope,
                metadata=scope_meta
            )

        # Rate limit OK → continuer et ajouter headers
        response = await call_next(request)

        # Ajouter headers rate limit (permet clients intelligents d'ajuster)
        response.headers[SecurityHeaders.X_RATELIMIT_LIMIT] = str(scope_meta["limit"])
        response.headers[SecurityHeaders.X_RATELIMIT_REMAINING] = str(scope_meta["remaining"])
        response.headers[SecurityHeaders.X_RATELIMIT_RESET] = str(scope_meta["reset"])

        return response

    def _rate_limit_response(self, scope: str, metadata: dict) -> JSONResponse:
        """Construit une réponse 429 Too Many Requests avec headers.

        Args:
            scope: Nom du scope ayant déclenché la limite
            metadata: Métadonnées du rate limiter (limit, remaining, reset, retry_after)

        Returns:
            JSONResponse 429 avec headers RFC 6585

        Example:
            >>> response = self._rate_limit_response("login", {
            ...     "limit": 5,
            ...     "remaining": 0,
            ...     "reset": 1709123456,
            ...     "retry_after": 42
            ... })
        """
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": f"Rate limit exceeded for scope '{scope}'. "
                         f"Retry after {metadata['retry_after']} seconds."
            },
            headers={
                SecurityHeaders.X_RATELIMIT_LIMIT: str(metadata["limit"]),
                SecurityHeaders.X_RATELIMIT_REMAINING: str(metadata["remaining"]),
                SecurityHeaders.X_RATELIMIT_RESET: str(metadata["reset"]),
                SecurityHeaders.RETRY_AFTER: str(metadata["retry_after"]),
            }
        )
