"""Utilitaires pour rate limiting et détermination de scope.

Centralise la logique de détermination de scope pour éviter duplication
entre RateLimitMiddleware et MetricsMiddleware.
"""

from typing import Optional
from fastapi import Request
from app.constants import AuthEndpoints, HTTPMethods, RateLimitScope
from app.core.deps import X_API_KEY_HEADER
from app.core.security import decode_token


def get_user_id_from_jwt(request: Request) -> Optional[int]:
    """Extrait user_id depuis JWT Bearer token (si présent et valide).

    Args:
        request: Requête FastAPI

    Returns:
        user_id si JWT valide, None sinon

    Notes:
        - Retourne None si Authorization header absent
        - Retourne None si token invalide/expiré
        - Pas d'exception levée (fail-safe)
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    try:
        token = auth_header.split(" ")[1]
        payload = decode_token(token)
        user_id_str = payload.get("sub")
        return int(user_id_str) if user_id_str else None
    except Exception:
        return None


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

    # Scope API key authentifiée (quota par API key)
    if request.headers.get(X_API_KEY_HEADER):
        return RateLimitScope.API_KEY_AUTHENTICATED

    # Scope user authentifié (quota utilisateur)
    if get_user_id_from_jwt(request) is not None:
        return RateLimitScope.USER_AUTHENTICATED

    # Scope mutations (write-heavy abuse)
    if request.method in HTTPMethods.UNSAFE_METHODS:
        return RateLimitScope.MUTATIONS

    # Scope reads (read-heavy abuse)
    return RateLimitScope.READS
