"""Middlewares de sécurité pour CaroCorp."""
import ipaddress
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, Optional
import secrets

from app.core.config import settings
from app.core.redis import redis_client
from app.core.security import decode_token
from app.core.rate_limiter import RateLimiter
from app.core.rate_limit_utils import determine_rate_limit_scope, get_user_id_from_jwt, get_tenant_id_from_jwt
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
        # Note B2: LOGOUT et MFA_VERIFY sont exemptés de CSRF car ils requièrent un Bearer
        # token dans Authorization. Les Bearer tokens ne sont pas envoyés automatiquement
        # par le navigateur (contrairement aux cookies), ce qui constitue déjà une protection
        # CSRF. Un attaquant ne peut pas forcer un logout sans posséder l'access token.
        if request.url.path in {
            PublicEndpoints.HEALTH,
            PublicEndpoints.DOCS,
            PublicEndpoints.REDOC,
            PublicEndpoints.OPENAPI,
            AuthEndpoints.LOGIN,
            AuthEndpoints.REFRESH,
            AuthEndpoints.LOGOUT,
            AuthEndpoints.MFA_VERIFY,
            AuthEndpoints.CHANGE_PASSWORD,  # INC-04: exempté — CSRF bootstrappage initial (§04 §4.3)
            # IAM v2 — même rationale Note B2 : Bearer token = protection CSRF implicite
            AuthEndpoints.V2_LOGIN,
            AuthEndpoints.V2_REFRESH,
            AuthEndpoints.V2_LOGOUT,
            # PIN auth — register-device et set-pin requièrent Bearer, pin-login est non-auth
            AuthEndpoints.V2_REGISTER_DEVICE,
            AuthEndpoints.V2_SET_PIN,
            AuthEndpoints.V2_PIN_LOGIN,
        }:
            return await call_next(request)

        # IAM v2 OAuth callbacks — pas de Bearer token initial, state Redis = protection CSRF
        if request.url.path.startswith("/api/v1/auth/v2/oauth/"):
            return await call_next(request)

        # P2-11 : bypass E2E via variable dediee (pas DEBUG seul — risque prod)
        import os
        if (
            os.environ.get("E2E_BYPASS_ENABLED", "").lower() == "true"
            and request.headers.get("X-E2E-Bypass") == "true"
        ):
            return await call_next(request)

        # Skip CSRF pour requêtes sans authentification (JWT retournera 401)
        authorization = request.headers.get(SecurityHeaders.AUTHORIZATION)
        if not authorization:
            return await call_next(request)

        # Extraire session_id depuis le claim "sid" du JWT (spec §04 §4.3)
        session_id = self._extract_session_id_from_jwt(authorization)
        if not session_id:
            # JWT invalide ou sans claim sid → laisser le endpoint gérer
            return await call_next(request)

        # Vérifier le token CSRF
        csrf_token = request.headers.get(SecurityHeaders.X_CSRF_TOKEN)

        if not csrf_token:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": ErrorMessages.CSRF_TOKEN_MISSING},
            )

        # Valider le token avec Redis
        if not await self._validate_csrf_token(session_id, csrf_token):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": ErrorMessages.CSRF_TOKEN_INVALID},
            )

        response = await call_next(request)
        return response

    def _extract_session_id_from_jwt(self, authorization: str) -> Optional[str]:
        """Extrait le session_id (claim 'sid') depuis le header Authorization (§04 §4.3).

        Args:
            authorization: Header Authorization (format: "Bearer <token>")

        Returns:
            session_id si JWT valide ET claim sid présent, None sinon
        """
        if not authorization or not authorization.startswith(SecurityHeaders.BEARER_PREFIX):
            return None
        try:
            token = authorization.replace(SecurityHeaders.BEARER_PREFIX, "", 1)
            payload = decode_token(token)
            return payload.get("sid") or None
        except Exception:
            return None

    async def _validate_csrf_token(self, session_id: str, token: str) -> bool:
        """Valide le token CSRF d'une session avec Redis (§04 §4.3).

        Args:
            session_id: ID de session extrait du claim "sid" du JWT
            token: Token CSRF à valider

        Returns:
            True si token valide (compare_digest sur valeur Redis), False sinon

        Security:
            - Pas d'exception levée (silent fail)
            - Timing-safe via hmac.compare_digest dans RedisSecClient.validate_csrf_token
        """
        # P2-18 : pas de early return sur longueur — timing constant via compare_digest
        if not token:
            token = ""
        return await redis_client.validate_csrf_token(session_id, token)

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
        # PDFs ETL servis dans iframe same-origin (vue split)
        if request.url.path.startswith("/uploads/etl/"):
            response.headers[SecurityHeaders.X_FRAME_OPTIONS] = "SAMEORIGIN"
        else:
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
        - FAIL-CLOSED si Redis down (securite > disponibilite — P0-01)
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
        "/metrics",  # P1-08 : Prometheus scraping exempt
    }

    def __init__(self, app):
        """Initialise le middleware avec RateLimiter Redis."""
        super().__init__(app)
        self.rate_limiter: Optional[RateLimiter] = None

    def _get_rate_limiter(self) -> RateLimiter:
        """Retourne un RateLimiter lié au client Redis courant.

        En tests, redis_client._client peut être réinitialisé entre deux event loops.
        On recâble le limiter à la volée pour éviter les erreurs "Event loop is closed".
        """
        current_client = redis_client.client
        if self.rate_limiter is None or self.rate_limiter.redis is not current_client:
            self.rate_limiter = RateLimiter(current_client)
        return self.rate_limiter

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
        # N'utiliser X-Forwarded-For que si un proxy de confiance est configuré.
        # Sans ce flag, le header est contrôlable par le client → bypass rate limit.
        if settings.TRUSTED_PROXY_HEADERS:
            forwarded_for = request.headers.get(SecurityHeaders.X_FORWARDED_FOR)
            if forwarded_for:
                raw_ip = forwarded_for.split(",")[0].strip()
                try:
                    # P2-02 : normaliser pour éviter le bypass via représentations équivalentes
                    # (ex: "::ffff:1.2.3.4" vs "1.2.3.4", padding IPv6 "::0001" vs "::1")
                    return ipaddress.ip_address(raw_ip).compressed
                except ValueError:
                    pass  # IP malformée — fallback sur request.client.host
        return request.client.host if request.client else "unknown"


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

        rate_limiter = self._get_rate_limiter()
        client_ip = self._get_client_ip(request)

        # M-07 : IP whitelist partenaires — exemption rate limiting
        if settings.TRUSTED_PARTNER_IPS:
            try:
                addr = ipaddress.ip_address(client_ip)
                for cidr in settings.TRUSTED_PARTNER_IPS:
                    if addr in ipaddress.ip_network(cidr, strict=False):
                        return await call_next(request)
            except ValueError:
                pass

        # ===== Niveau 1 : Global IP (toujours vérifié) =====
        global_key = rate_limiter.build_key(RateLimitScope.GLOBAL_IP, client_ip)
        global_limit, global_window = rate_limiter.get_scope_config(RateLimitScope.GLOBAL_IP)
        global_allowed, global_meta = await rate_limiter.check_rate_limit(
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
        scope = determine_rate_limit_scope(request)

        # Identifier pour le scope
        if scope == RateLimitScope.LOGIN:
            # P2-09 : rate limit login par email (tolerant multi-device derriere NAT)
            # Fallback sur IP si email non extractible (body non JSON, etc.)
            email_id = None
            if hasattr(request.state, "parsed_body"):
                email_id = getattr(request.state, "parsed_body", {}).get("email")
            identifier = f"email:{email_id}" if email_id else client_ip
        elif scope == RateLimitScope.API_KEY_AUTHENTICATED:
            # Pour API key, rate limit par api_key_id
            api_key_id = getattr(request.state, "api_key_id", None)
            identifier = f"apikey_{api_key_id}" if api_key_id else client_ip
        elif scope in (
            RateLimitScope.USER_AUTHENTICATED,
            RateLimitScope.EPICERIE_AUTHENTICATED,
            RateLimitScope.EPICERIE_MUTATIONS,
            RateLimitScope.RESTAURANT_AUTHENTICATED,
            RateLimitScope.RESTAURANT_MUTATIONS,
        ):
            # Pour user authentifié (toutes apps), rate limit par tenant_id:user_id
            user_id = get_user_id_from_jwt(request)
            tenant_id = get_tenant_id_from_jwt(request)
            if user_id and tenant_id:
                identifier = f"t{tenant_id}:u{user_id}"
            elif user_id:
                identifier = f"u{user_id}"
            else:
                identifier = client_ip
        else:
            # Pour mutations/reads non authentifiées, rate limit par IP
            identifier = client_ip

        scope_key = rate_limiter.build_key(scope, identifier)
        scope_limit, scope_window = rate_limiter.get_scope_config(scope)
        scope_allowed, scope_meta = await rate_limiter.check_rate_limit(
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
