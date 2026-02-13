"""Constantes de sécurité et d'authentification.

Ce module centralise :
- Headers HTTP de sécurité
- Préfixes de clés Redis
- Scopes de rate limiting
- Configurations de sécurité
"""

from enum import Enum


class SecurityHeaders:
    """Headers HTTP de sécurité (SecurityHeadersMiddleware).

    Usage :
        response.headers[SecurityHeaders.X_CONTENT_TYPE_OPTIONS] = SecurityHeaders.NOSNIFF
    """

    # ─────────────────────────────────────────────────────────────────────
    # Header names
    # ─────────────────────────────────────────────────────────────────────

    X_CONTENT_TYPE_OPTIONS = "X-Content-Type-Options"
    X_FRAME_OPTIONS = "X-Frame-Options"
    X_XSS_PROTECTION = "X-XSS-Protection"
    X_CSRF_TOKEN = "X-CSRF-Token"
    X_FORWARDED_FOR = "X-Forwarded-For"
    X_RATELIMIT_LIMIT = "X-RateLimit-Limit"
    X_RATELIMIT_REMAINING = "X-RateLimit-Remaining"
    X_RATELIMIT_RESET = "X-RateLimit-Reset"
    STRICT_TRANSPORT_SECURITY = "Strict-Transport-Security"
    REFERRER_POLICY = "Referrer-Policy"
    CONTENT_SECURITY_POLICY = "Content-Security-Policy"
    AUTHORIZATION = "Authorization"
    WWW_AUTHENTICATE = "WWW-Authenticate"
    RETRY_AFTER = "Retry-After"

    # ─────────────────────────────────────────────────────────────────────
    # Header values & prefixes
    # ─────────────────────────────────────────────────────────────────────

    NOSNIFF = "nosniff"
    DENY = "DENY"
    XSS_BLOCK = "1; mode=block"
    HSTS_ONE_YEAR = "max-age=31536000; includeSubDomains"
    STRICT_ORIGIN_CROSS_ORIGIN = "strict-origin-when-cross-origin"
    BEARER_PREFIX = "Bearer "
    BEARER_SCHEME = "Bearer"

    # ─────────────────────────────────────────────────────────────────────
    # Content Security Policy (production only)
    # ─────────────────────────────────────────────────────────────────────

    CSP_DEFAULT = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self';"
    )


class RedisKeys:
    """Préfixes pour les clés Redis.

    Usage :
        key = RedisKeys.refresh_token(user_id=123)
        # → "refresh_token:123"
    """

    # ─────────────────────────────────────────────────────────────────────
    # Préfixes bruts
    # ─────────────────────────────────────────────────────────────────────

    REFRESH_TOKEN = "refresh_token:"
    CSRF_TOKEN = "csrf:"
    SESSION = "session:"
    RATE_LIMIT = "rate_limit:"
    RESERVATION_COUNTER = "reservation_counter:"
    INVOICE_COUNTER = "invoice_counter:"

    # ─────────────────────────────────────────────────────────────────────
    # Helpers pour générer clés complètes
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def refresh_token(user_id: int) -> str:
        """Génère clé Redis pour refresh token d'un user."""
        return f"{RedisKeys.REFRESH_TOKEN}{user_id}"

    @staticmethod
    def csrf_token(session_id: str) -> str:
        """Génère clé Redis pour token CSRF d'une session."""
        return f"{RedisKeys.CSRF_TOKEN}{session_id}"

    @staticmethod
    def rate_limit(ip: str) -> str:
        """Génère clé Redis pour rate limiting d'une IP."""
        return f"{RedisKeys.RATE_LIMIT}{ip}"

    @staticmethod
    def reservation_counter(year: int) -> str:
        """Génère clé Redis pour compteur réservations par année."""
        return f"{RedisKeys.RESERVATION_COUNTER}{year}"

    @staticmethod
    def invoice_counter(year: int) -> str:
        """Génère clé Redis pour compteur factures par année."""
        return f"{RedisKeys.INVOICE_COUNTER}{year}"


class RateLimitScope(str, Enum):
    """Scopes de rate limiting multi-niveaux.

    Utilisé dans :
        - core.rate_limiter (configuration scopes)
        - middleware.security (détermination scope, vérification)
        - middleware.metrics (compteurs par scope)

    Niveaux (ordre de vérification) :
        1. GLOBAL_IP : 1000 req/min (protection DDoS)
        2. LOGIN : 5 req/min (anti brute force)
        3. USER_AUTHENTICATED : 200 req/min (quota utilisateur)
        4. MUTATIONS : 100 req/min (write abuse)
        5. READS : 300 req/min (read abuse)
    """

    GLOBAL_IP = "global_ip"
    LOGIN = "login"
    USER_AUTHENTICATED = "user_authenticated"
    MUTATIONS = "mutations"
    READS = "reads"


__all__ = [
    "SecurityHeaders",
    "RedisKeys",
    "RateLimitScope",
]
