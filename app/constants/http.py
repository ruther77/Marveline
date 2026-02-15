"""Constantes HTTP et API.

Ce module centralise :
- Méthodes HTTP
- Endpoints publics
- Configurations API
"""


class HTTPMethods:
    """Méthodes HTTP standardisées.

    Usage :
        if request.method in HTTPMethods.SAFE_METHODS:
            # Skip CSRF validation
    """

    # ─────────────────────────────────────────────────────────────────────
    # Méthodes individuelles
    # ─────────────────────────────────────────────────────────────────────

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

    # ─────────────────────────────────────────────────────────────────────
    # Groupes de méthodes
    # ─────────────────────────────────────────────────────────────────────

    SAFE_METHODS = frozenset([GET, HEAD, OPTIONS])
    UNSAFE_METHODS = frozenset([POST, PUT, PATCH, DELETE])


class PublicEndpoints:
    """Endpoints publics (pas d'authentification / CSRF requis).

    Usage :
        if request.url.path in PublicEndpoints.all():
            # Skip CSRF validation
    """

    HEALTH = "/api/v1/health"
    DOCS = "/api/docs"
    REDOC = "/api/redoc"
    OPENAPI = "/openapi.json"

    @classmethod
    def all(cls) -> set[str]:
        """Retourne tous les endpoints publics sous forme de set."""
        return {cls.HEALTH, cls.DOCS, cls.REDOC, cls.OPENAPI}


class AuthEndpoints:
    """Endpoints d'authentification (chemins complets avec préfixe API).

    Utilisé dans :
        - middleware.security (CSRF skip, login scope detection)
        - middleware.audit (skip audit paths)
        - middleware.metrics (login scope detection)
        - core.deps (OAuth2 tokenUrl)
    """

    LOGIN = "/api/v1/auth/login"
    REFRESH = "/api/v1/auth/refresh"
    CSRF = "/api/v1/auth/csrf"
    LOGOUT = "/api/v1/auth/logout"
    MFA_VERIFY = "/api/v1/mfa/verify"


class HealthEndpoints:
    """Endpoints de health check (chemins complets avec préfixe API).

    Utilisé dans :
        - middleware.security (rate limit exemptions)
    """

    BASE = "/api/v1/health"
    READY = "/api/v1/health/ready"
    LIVE = "/api/v1/health/live"


__all__ = [
    "HTTPMethods",
    "PublicEndpoints",
    "AuthEndpoints",
    "HealthEndpoints",
]
