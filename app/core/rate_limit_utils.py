"""Utilitaires pour rate limiting et détermination de scope.

Centralise la logique de détermination de scope pour éviter duplication
entre RateLimitMiddleware et MetricsMiddleware.
"""

from typing import Optional
from fastapi import Request
from app.constants import AuthEndpoints, HTTPMethods, RateLimitScope
from app.core.security import decode_token

# Constante dupliquée depuis deps.py pour briser le circular import :
# rate_limit_utils → deps → services → schemas → core.__init__ → rate_limit_utils
X_API_KEY_HEADER = "X-API-Key"


def _decode_jwt_claims(request: Request) -> Optional[dict]:
    """Décode le JWT Bearer et retourne les claims (fail-safe).

    Returns:
        dict claims si JWT valide, None sinon.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        token = auth_header.split(" ")[1]
        return decode_token(token)
    except Exception:
        return None


def get_user_id_from_jwt(request: Request) -> Optional[int]:
    """Extrait user_id depuis JWT Bearer token (si présent et valide)."""
    claims = _decode_jwt_claims(request)
    if not claims:
        return None
    user_id_str = claims.get("sub")
    return int(user_id_str) if user_id_str else None


def get_tenant_id_from_jwt(request: Request) -> Optional[int]:
    """Extrait tenant_id depuis JWT Bearer token (si présent et valide)."""
    claims = _decode_jwt_claims(request)
    if not claims:
        return None
    tid = claims.get("tid")
    return int(tid) if tid is not None else None


def determine_rate_limit_scope(request: Request) -> str:
    """Détermine le scope de rate limit selon la requête.

    Logique centralisée utilisée par :
    - RateLimitMiddleware (application des limites)
    - MetricsMiddleware (tracking métriques par scope)

    Priorités (ordre de vérification) :
    1. Login endpoint → "login" (5 req/min strict)
    2. API key présente → "api_key_authenticated" (quota par key)
    3. User authentifié → "user_authenticated" (200 req/min)
    4. Mutations (POST/PUT/PATCH/DELETE) → "mutations" (100 req/min)
    5. Reads (GET) → "reads" (300 req/min)

    Args:
        request: Requête FastAPI

    Returns:
        Nom du scope (RateLimitScope enum value)

    Notes:
        - Global IP toujours vérifié en amont (pas retourné ici)
        - Login scope = endpoint exact match
        - User scope = JWT présent et valide
        - Mutations/reads = fallback si non authentifié

    Examples:
        >>> # POST /auth/login → "login"
        >>> determine_rate_limit_scope(login_request)
        "login"

        >>> # GET /products (avec JWT valide) → "user_authenticated"
        >>> determine_rate_limit_scope(authenticated_request)
        "user_authenticated"

        >>> # POST /customers (sans JWT) → "mutations"
        >>> determine_rate_limit_scope(unauthenticated_post)
        "mutations"

        >>> # GET /products (sans JWT) → "reads"
        >>> determine_rate_limit_scope(unauthenticated_get)
        "reads"
    """
    # Scope login (brute force protection)
    if request.url.path == AuthEndpoints.LOGIN:
        return RateLimitScope.LOGIN

    # Scope CSRF — limite stricte pour éviter flood de tokens Redis (H2-Bug1)
    if request.url.path == AuthEndpoints.CSRF:
        return RateLimitScope.LOGIN

    # Scope API key authentifiée (quota par API key)
    if request.headers.get(X_API_KEY_HEADER):
        return RateLimitScope.API_KEY_AUTHENTICATED

    # Scope user authentifié — app-specific par préfixe route
    if get_user_id_from_jwt(request) is not None:
        path = request.url.path
        is_mutation = request.method in HTTPMethods.UNSAFE_METHODS

        if "/epicerie/" in path:
            return RateLimitScope.EPICERIE_MUTATIONS if is_mutation else RateLimitScope.EPICERIE_AUTHENTICATED
        if "/restaurant/" in path:
            return RateLimitScope.RESTAURANT_MUTATIONS if is_mutation else RateLimitScope.RESTAURANT_AUTHENTICATED

        return RateLimitScope.USER_AUTHENTICATED

    # Scope mutations (write-heavy abuse, non authentifié)
    if request.method in HTTPMethods.UNSAFE_METHODS:
        return RateLimitScope.MUTATIONS

    # Scope reads (read-heavy abuse, non authentifié)
    return RateLimitScope.READS
