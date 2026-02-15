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
    REFRESH_WHITELIST = "refresh_wl:"
    ACCESS_BLACKLIST = "access_bl:"
    TOKEN_FAMILY = "token_family:"
    CSRF_TOKEN = "csrf:"
    SESSION = "session:"
    RATE_LIMIT = "rate_limit:"
    BRUTE_FORCE_EMAIL = "bf_email:"
    BRUTE_FORCE_IP = "bf_ip:"
    BRUTE_FORCE_LOCK = "bf_lock:"
    BRUTE_FORCE_ALERT = "bf_alert:"
    SESSION_USER_INDEX = "session_idx:"
    RESERVATION_COUNTER = "reservation_counter:"
    INVOICE_COUNTER = "invoice_counter:"
    API_KEY_CACHE = "api_key:"
    FEATURE_FLAG_CACHE = "ff:"

    # ─────────────────────────────────────────────────────────────────────
    # Helpers pour générer clés complètes
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def refresh_token(user_id: int) -> str:
        """Génère clé Redis pour refresh token d'un user."""
        return f"{RedisKeys.REFRESH_TOKEN}{user_id}"

    @staticmethod
    def refresh_whitelist(jti: str) -> str:
        """Génère clé Redis pour whitelist refresh token (JTI → user data)."""
        return f"{RedisKeys.REFRESH_WHITELIST}{jti}"

    @staticmethod
    def access_blacklist(jti: str) -> str:
        """Génère clé Redis pour blacklist access token (JTI → "1")."""
        return f"{RedisKeys.ACCESS_BLACKLIST}{jti}"

    @staticmethod
    def token_family(family_id: str) -> str:
        """Génère clé Redis pour famille de tokens (rotation tracking)."""
        return f"{RedisKeys.TOKEN_FAMILY}{family_id}"

    @staticmethod
    def csrf_token(session_id: str) -> str:
        """Génère clé Redis pour token CSRF d'une session."""
        return f"{RedisKeys.CSRF_TOKEN}{session_id}"

    @staticmethod
    def rate_limit(ip: str) -> str:
        """Génère clé Redis pour rate limiting d'une IP."""
        return f"{RedisKeys.RATE_LIMIT}{ip}"

    @staticmethod
    def session_user_index(user_id: int) -> str:
        """Génère clé Redis pour l'index des sessions d'un user."""
        return f"{RedisKeys.SESSION_USER_INDEX}{user_id}"

    @staticmethod
    def reservation_counter(year: int) -> str:
        """Génère clé Redis pour compteur réservations par année."""
        return f"{RedisKeys.RESERVATION_COUNTER}{year}"

    @staticmethod
    def invoice_counter(year: int) -> str:
        """Génère clé Redis pour compteur factures par année."""
        return f"{RedisKeys.INVOICE_COUNTER}{year}"


class BruteForceThresholds:
    """Seuils d'escalation brute force.

    Niveaux:
        0-2  tentatives : Normal (aucune restriction)
        3-4  tentatives : CAPTCHA requis (flag dans response)
        5-7  tentatives : Délai progressif (1s, 2s, 4s)
        8-9  tentatives : Lock temporaire (15 min)
        10+  tentatives : Lock + alerte admin (une seule fois)
    """

    CAPTCHA_THRESHOLD = 3
    DELAY_THRESHOLD = 5
    LOCK_THRESHOLD = 8
    ALERT_THRESHOLD = 10

    LOCK_DURATION_SECONDS = 900  # 15 minutes
    ATTEMPT_WINDOW_SECONDS = 900  # 15 minutes (TTL compteurs)

    BASE_DELAY_SECONDS = 1  # Délai progressif: 1s, 2s, 4s (2^(n-5))


class Argon2Params:
    """Paramètres Argon2id pour le hashing de mots de passe.

    Recommandation OWASP 2024+ : Argon2id avec ces paramètres minimum.
    Résistant GPU/ASIC (memory-hard).

    Note: TIME_COST, MEMORY_COST et PARALLELISM sont définis dans config.py
    (source unique de vérité depuis variables d'environnement).
    """

    HASH_LENGTH = 32       # Longueur du hash en bytes (256 bits)
    SALT_LENGTH = 16       # Longueur du salt en bytes (128 bits)

    # Préfixes pour auto-détection de l'algorithme
    BCRYPT_PREFIX = "$2b$"
    ARGON2ID_PREFIX = "$argon2id$"


class PasswordPolicy:
    """Constantes pour la politique de mots de passe.

    Règles :
        - Min 8 chars standard, 12 pour admin/manager
        - Majuscule + minuscule + chiffre + caractère spécial
        - Pas dans la liste des common passwords
        - Pas de username/email dans le password
    """

    MIN_LENGTH = 8
    ADMIN_MIN_LENGTH = 12
    MAX_LENGTH = 128

    # Rôles nécessitant un password plus long
    ELEVATED_ROLES = ("admin", "manager")


class SessionConfig:
    """Configuration pour le session management Redis.

    Sessions stockées dans Redis (pas en DB) car éphémères.
    Chaque login crée une session, chaque logout la supprime.
    Max 5 sessions par user (la plus ancienne est évincée).
    """

    MAX_SESSIONS_PER_USER = 5
    SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 jours (aligné avec refresh token TTL)


class MFAConfig:
    """Configuration MFA TOTP.

    Paramètres:
        - TOTP_DIGITS: 6 chiffres standard
        - TOTP_PERIOD: 30 secondes (RFC 6238)
        - TOTP_WINDOW: ±1 window (accepte code précédent/suivant)
        - RECOVERY_CODE_COUNT: 8 codes de récupération
        - MFA_SESSION_TTL: 5 minutes pour compléter le flow MFA
        - MAX_VERIFY_ATTEMPTS: 5 tentatives avant invalidation du setup
    """

    TOTP_DIGITS = 6
    TOTP_PERIOD = 30
    TOTP_WINDOW = 1
    RECOVERY_CODE_COUNT = 8
    RECOVERY_CODE_LENGTH = 8
    MFA_SESSION_TTL_SECONDS = 300  # 5 minutes
    MAX_VERIFY_ATTEMPTS = 5
    ISSUER_NAME = "Marveline"


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
    "Argon2Params",
    "BruteForceThresholds",
    "MFAConfig",
    "PasswordPolicy",
    "SessionConfig",
    "SecurityHeaders",
    "RedisKeys",
    "RateLimitScope",
]
