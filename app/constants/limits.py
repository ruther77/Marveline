"""Limites et seuils de l'application.

Ce module centralise tous les magic numbers et configurations :
- Pagination
- Sécurité (tokens, mots de passe)
- Rate limiting
- Sessions
- Business logic
"""


class Limits:
    """Limites et seuils de l'application.

    Centralise tous les magic numbers pour faciliter le tuning.
    """

    # ─────────────────────────────────────────────────────────────────────
    # Pagination
    # ─────────────────────────────────────────────────────────────────────

    MAX_PAGE_SIZE = 1000
    """Nombre maximum d'items par page (évite surcharge serveur)."""

    DEFAULT_PAGE_SIZE = 100
    """Nombre d'items par défaut si non spécifié."""

    # ─────────────────────────────────────────────────────────────────────
    # Sécurité
    # ─────────────────────────────────────────────────────────────────────

    CSRF_TOKEN_MIN_LENGTH = 32
    """Longueur minimale d'un token CSRF (256 bits)."""

    PASSWORD_MIN_LENGTH = 8
    """Longueur minimale d'un mot de passe."""

    JWT_SECRET_MIN_LENGTH = 32
    """Longueur minimale du secret JWT (256 bits)."""

    # ─────────────────────────────────────────────────────────────────────
    # Rate Limiting
    # ─────────────────────────────────────────────────────────────────────

    REQUESTS_PER_MINUTE = 100
    """Nombre max de requêtes par minute par IP."""

    RATE_LIMIT_WINDOW_SECONDS = 60
    """Fenêtre de temps pour le rate limiting (1 minute)."""

    # ─────────────────────────────────────────────────────────────────────
    # Sessions & Tokens
    # ─────────────────────────────────────────────────────────────────────

    SESSION_TIMEOUT_SECONDS = 3600
    """Timeout de session (1 heure)."""

    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    """Durée de validité d'un access token JWT."""

    REFRESH_TOKEN_EXPIRE_DAYS = 7
    """Durée de validité d'un refresh token."""

    # ─────────────────────────────────────────────────────────────────────
    # Business Logic
    # ─────────────────────────────────────────────────────────────────────

    RESERVATION_REFERENCE_PADDING = 4
    """Nombre de zéros pour padding des références (RES-2026-0001)."""

    INVOICE_NUMBER_PADDING = 5
    """Nombre de zéros pour padding des numéros de facture (INV-2026-00001)."""


__all__ = [
    "Limits",
]
