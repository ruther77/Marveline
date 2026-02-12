"""Constantes de sécurité et d'authentification.

Ce module centralise :
- Headers HTTP de sécurité
- Préfixes de clés Redis
- Configurations de sécurité
"""


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
    STRICT_TRANSPORT_SECURITY = "Strict-Transport-Security"
    REFERRER_POLICY = "Referrer-Policy"
    CONTENT_SECURITY_POLICY = "Content-Security-Policy"

    # ─────────────────────────────────────────────────────────────────────
    # Header values
    # ─────────────────────────────────────────────────────────────────────

    NOSNIFF = "nosniff"
    DENY = "DENY"
    XSS_BLOCK = "1; mode=block"
    HSTS_ONE_YEAR = "max-age=31536000; includeSubDomains"
    STRICT_ORIGIN_CROSS_ORIGIN = "strict-origin-when-cross-origin"

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


__all__ = [
    "SecurityHeaders",
    "RedisKeys",
]
