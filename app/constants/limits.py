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
    # Tokens
    # ─────────────────────────────────────────────────────────────────────

    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    """Durée de validité d'un access token JWT."""

    REFRESH_TOKEN_EXPIRE_DAYS = 7
    """Durée de validité d'un refresh token."""

    # ─────────────────────────────────────────────────────────────────────
    # Password Reset
    # ─────────────────────────────────────────────────────────────────────

    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 30
    """Durée de validité d'un token de réinitialisation de mot de passe."""

    PASSWORD_RESET_MAX_PER_EMAIL = 3
    """Nombre max de demandes reset par email dans la fenêtre."""

    PASSWORD_RESET_WINDOW_MINUTES = 15
    """Fenêtre de rate limiting pour les demandes reset (en minutes)."""

    # ─────────────────────────────────────────────────────────────────────
    # Business Logic
    # ─────────────────────────────────────────────────────────────────────

    RESERVATION_REFERENCE_PADDING = 4
    """Nombre de zéros pour padding des références (RES-2026-0001)."""

    INVOICE_NUMBER_PADDING = 4
    """Nombre de zéros pour padding des numéros de facture (INV-2026-0001)."""


__all__ = [
    "Limits",
]
