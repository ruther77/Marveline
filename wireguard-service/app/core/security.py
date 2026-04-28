"""Sécurité inter-service pour le microservice WireGuard.

Validation de l'API key interne avec comparaison timing-safe.
"""

import hmac
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def verify_internal_api_key(provided_key: str) -> bool:
    """Vérifie l'API key interne avec comparaison timing-safe.

    Args:
        provided_key: Clé fournie dans le header X-Internal-API-Key.

    Returns:
        True si la clé est valide.
    """
    settings = get_settings()
    expected_key = settings.INTERNAL_API_KEY

    if not provided_key or not expected_key:
        return False

    return hmac.compare_digest(
        provided_key.encode("utf-8"),
        expected_key.encode("utf-8"),
    )
