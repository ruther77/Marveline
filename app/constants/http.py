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

    HEALTH = "/health"
    DOCS = "/api/docs"
    REDOC = "/api/redoc"
    OPENAPI = "/openapi.json"

    @classmethod
    def all(cls) -> set[str]:
        """Retourne tous les endpoints publics sous forme de set."""
        return {cls.HEALTH, cls.DOCS, cls.REDOC, cls.OPENAPI}


__all__ = [
    "HTTPMethods",
    "PublicEndpoints",
]
