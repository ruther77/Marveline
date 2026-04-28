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

    RSA_KEY_MIN_BITS = 2048
    """Taille minimale de la cle RSA pour JWT RS256."""

    # ─────────────────────────────────────────────────────────────────────
    # Rate Limiting
    # ─────────────────────────────────────────────────────────────────────

    REQUESTS_PER_MINUTE = 100
    """Nombre max de requêtes par minute par IP."""

    RATE_LIMIT_WINDOW_SECONDS = 60
    """Fenêtre de temps pour le rate limiting (1 minute)."""

    # ─────────────────────────────────────────────────────────────────────
    # Tokens (CaroCorp §1.4, §2.1)
    # ─────────────────────────────────────────────────────────────────────

    ACCESS_TOKEN_EXPIRE_SECONDS = 900
    """Duree de validite d'un access token JWT (15 min)."""

    REFRESH_TOKEN_EXPIRE_SECONDS = 604800
    """Duree de validite d'un refresh token (7 jours)."""

    MAX_SESSIONS_PER_USER = 5
    """Nombre max de sessions simultanees par utilisateur (CaroCorp §6.8)."""

    # ─────────────────────────────────────────────────────────────────────
    # Password Reset
    # ─────────────────────────────────────────────────────────────────────

    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 30
    """Durée de validité d'un token de réinitialisation de mot de passe."""

    PASSWORD_RESET_MAX_PER_EMAIL = 3
    """Nombre max de demandes reset par email dans la fenêtre."""

    PASSWORD_RESET_WINDOW_MINUTES = 15
    """Fenêtre de rate limiting pour les demandes reset (en minutes)."""

    PASSWORD_CHANGE_MAX_ATTEMPTS = 3
    """Nombre max de tentatives échouées pour change_password (§4.5 S-09.3)."""

    PASSWORD_CHANGE_WINDOW_SECONDS = 900
    """Fenêtre brute force pour change_password : 15 min glissantes (§4.5)."""

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
