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
    """Préfixes pour les clés Redis (v3 — CaroCorp §3.2).

    Redis-SEC (6380, noeviction, FAIL-CLOSED) :
        whitelist, blacklist, families, CSRF, brute force, MFA, sessions auth
    Redis-CACHE (6381, allkeys-lru, FAIL-OPEN) :
        API key cache, feature flags, RBAC scope cache

    Usage :
        key = RedisKeys.refresh_whitelist(uid=1, did="abc", sid="def")
        # → "whitelist:refresh:1:abc:def"
    """

    # ─────────────────────────────────────────────────────────────────────
    # Redis-SEC — Préfixes auth/sécurité (§3.2)
    # ─────────────────────────────────────────────────────────────────────

    REFRESH_WHITELIST = "whitelist:refresh:"
    ACCESS_BLACKLIST = "blacklist:jti:"
    TOKEN_FAMILY = "family:"
    JTI_META = "jti:meta:"
    USER_SESSIONS_INDEX = "user_sessions_index:"
    SESSION = "session:"
    CSRF_TOKEN = "csrf:"
    STEPUP = "stepup:"

    # Brute force (§3.2, §7.1)
    BRUTE_FORCE_USER = "brute:"
    BRUTE_FORCE_IP = "brute:ip:"
    BRUTE_FORCE_DEVICE = "brute:device:"
    BRUTE_FORCE_PWD_CHANGE = "brute:pwd_change:"
    BRUTE_FORCE_LOCK = "bf_lock:"
    BRUTE_FORCE_ALERT = "bf_alert:"

    # Credential stuffing global (§7.2 NIVEAU 3)
    CREDENTIAL_STUFFING = "credential_stuffing:failures:"
    CAPTCHA_REQUIRED = "captcha:required"
    LOGIN_BLOCKED = "login:blocked"

    # MFA (§3.2, §5)
    TOTP_USED = "totp:used:"
    MFA_SESSION = "mfa_session:"

    # Password reset
    PASSWORD_RESET_TOKEN = "pwd_reset:"
    PASSWORD_RESET_RATE = "pwd_reset_rate:"

    # Devices révoqués (§7.1 S-08.1)
    REVOKED_DEVICE         = "revoked_device:"
    REVOKED_DEVICE_ATTEMPT = "revoked_device_attempt:"

    # Mode dégradé (§S-08.4 — contrôle niveau dégradation)
    DEGRADED_READ_ONLY      = "degraded:read_only"
    DEGRADED_AUTH_DOWN      = "degraded:auth_down"
    DEGRADED_EMERGENCY_BYPASS = "degraded:emergency_bypass"

    # WebSocket ticket éphémère (usage unique, TTL 30s)
    WS_TICKET = "ws_ticket:"

    # Rate limiting
    RATE_LIMIT = "rate_limit:"

    # ─────────────────────────────────────────────────────────────────────
    # Redis-CACHE — Préfixes cache applicatif
    # ─────────────────────────────────────────────────────────────────────

    RESERVATION_COUNTER = "reservation_counter:"
    INVOICE_COUNTER = "invoice_counter:"
    API_KEY_CACHE = "api_key:"
    FEATURE_FLAG_CACHE = "ff:"
    RBAC_SCOPE_CACHE = "rbac:scopes:"

    # ─────────────────────────────────────────────────────────────────────
    # Helpers — Redis-SEC
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def refresh_whitelist(uid: int, did: str, sid: str) -> str:
        """whitelist:refresh:{uid}:{did}:{sid} — STRING, EXPIREAT absolu."""
        return f"{RedisKeys.REFRESH_WHITELIST}{uid}:{did}:{sid}"

    @staticmethod
    def access_blacklist(jti: str) -> str:
        """blacklist:jti:{jti} — STRING "1", TTL résiduel."""
        return f"{RedisKeys.ACCESS_BLACKLIST}{jti}"

    @staticmethod
    def token_family(family_id: str) -> str:
        """family:{fid} — SET de JTIs, EXPIREAT absolu."""
        return f"{RedisKeys.TOKEN_FAMILY}{family_id}"

    @staticmethod
    def jti_meta(jti_access: str) -> str:
        """jti:meta:{jti_access} — STRING(exp_timestamp), TTL 900s."""
        return f"{RedisKeys.JTI_META}{jti_access}"

    @staticmethod
    def user_sessions_index(user_id: int) -> str:
        """user_sessions_index:{uid} — SET de "did:sid"."""
        return f"{RedisKeys.USER_SESSIONS_INDEX}{user_id}"

    @staticmethod
    def session(uid: int, did: str, sid: str) -> str:
        """session:{uid}:{did}:{sid} — HASH."""
        return f"{RedisKeys.SESSION}{uid}:{did}:{sid}"

    @staticmethod
    def csrf_token(session_id: str) -> str:
        """csrf:{session_id} — STRING."""
        return f"{RedisKeys.CSRF_TOKEN}{session_id}"

    @staticmethod
    def stepup(uid: int, did: str) -> str:
        """stepup:{uid}:{did} — STRING, TTL 900s."""
        return f"{RedisKeys.STEPUP}{uid}:{did}"

    @staticmethod
    def brute_force_user(uid: int) -> str:
        """brute:{uid} — STRING, 15 min glissantes."""
        return f"{RedisKeys.BRUTE_FORCE_USER}{uid}"

    @staticmethod
    def brute_force_ip(ip_hash: str) -> str:
        """brute:ip:{ip_hash} — STRING, 1h."""
        return f"{RedisKeys.BRUTE_FORCE_IP}{ip_hash}"

    @staticmethod
    def brute_force_device(device_id: str) -> str:
        """brute:device:{device_id} — STRING, 1h."""
        return f"{RedisKeys.BRUTE_FORCE_DEVICE}{device_id}"

    @staticmethod
    def brute_force_pwd_change(uid: int) -> str:
        """brute:pwd_change:{uid} — STRING, 15 min glissantes (§4.5)."""
        return f"{RedisKeys.BRUTE_FORCE_PWD_CHANGE}{uid}"

    @staticmethod
    def totp_used(uid: int, step: int) -> str:
        """totp:used:{uid}:{step} — STRING, 90s anti-replay."""
        return f"{RedisKeys.TOTP_USED}{uid}:{step}"

    @staticmethod
    def mfa_session(token_uuid: str) -> str:
        """mfa_session:{token_uuid} — STRING, 300s."""
        return f"{RedisKeys.MFA_SESSION}{token_uuid}"

    @staticmethod
    def revoked_device(device_id: str) -> str:
        """revoked_device:{did} — STRING "1", TTL 24h. Device marqué révoqué (§7.1)."""
        return f"{RedisKeys.REVOKED_DEVICE}{device_id}"

    @staticmethod
    def revoked_device_attempt(device_id: str) -> str:
        """revoked_device_attempt:{did} — STRING counter, TTL 24h (§7.1 S-08.1)."""
        return f"{RedisKeys.REVOKED_DEVICE_ATTEMPT}{device_id}"

    @staticmethod
    def ws_ticket(ticket_id: str) -> str:
        """ws_ticket:{ticket_id} — STRING(JSON claims), TTL 30s, usage unique."""
        return f"{RedisKeys.WS_TICKET}{ticket_id}"

    # ─────────────────────────────────────────────────────────────────────
    # Helpers — Redis-CACHE
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def reservation_counter(year: int) -> str:
        """Clé Redis pour compteur réservations par année."""
        return f"{RedisKeys.RESERVATION_COUNTER}{year}"

    @staticmethod
    def invoice_counter(year: int) -> str:
        """Clé Redis pour compteur factures par année."""
        return f"{RedisKeys.INVOICE_COUNTER}{year}"

    @staticmethod
    def rbac_scope_cache(role_name: str) -> str:
        """rbac:scopes:{role_name} — cache scopes d'un rôle, 5 min."""
        return f"{RedisKeys.RBAC_SCOPE_CACHE}{role_name}"

    @staticmethod
    def rate_limit(ip: str) -> str:
        """Clé Redis pour rate limiting d'une IP."""
        return f"{RedisKeys.RATE_LIMIT}{ip}"


class BruteForceThresholds:
    """Seuils d'escalation brute force (politique sans lockout dur).

    Niveaux:
        0-2  tentatives : Normal (aucune restriction)
        3-4  tentatives : CAPTCHA requis
        5+   tentatives : CAPTCHA + délai exponentiel (max MAX_DELAY_SECONDS)
    """

    CAPTCHA_THRESHOLD = 3
    DELAY_THRESHOLD = 5

    ATTEMPT_WINDOW_SECONDS = 900  # 15 minutes (TTL compteurs)

    BASE_DELAY_SECONDS = 1        # Délai progressif : 1s, 2s, 4s… (2^(n-5))
    MAX_DELAY_SECONDS = 30        # Borne supérieure du délai exponentiel


class CredentialStuffingThresholds:
    """Seuils de détection credential stuffing global (CaroCorp §7.2 NIVEAU 3).

    Compteur par minute : credential_stuffing:failures:{YYYYMMDDHHMM}
    Opération Redis : INCR + EXPIRE MINUTE_WINDOW_SECONDS

    Niveaux d'escalation :
        > WARNING_THRESHOLD  : log WARNING
        > CAPTCHA_THRESHOLD  : activer flag captcha:required (TTL CAPTCHA_TTL_SECONDS)
        > BLOCK_THRESHOLD    : bloquer tout login (TTL BLOCK_TTL_SECONDS)
    """

    MINUTE_WINDOW_SECONDS = 600   # 10 min de rétention de la clé minute
    WARNING_THRESHOLD = 50        # > 50 failures/min → WARNING log
    CAPTCHA_THRESHOLD = 200       # > 200 → captcha:required flag (30 min)
    BLOCK_THRESHOLD = 500         # > 500 → login:blocked flag (5 min)
    CAPTCHA_TTL_SECONDS = 1800    # 30 minutes
    BLOCK_TTL_SECONDS = 300       # 5 minutes


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
    STEPUP_TTL = 300  # P2-08 : 5 minutes (etait 15 min — trop long pour ops sensibles)


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
        4. API_KEY_AUTHENTICATED : variable req/min (quota par API key)
        5. MUTATIONS : 100 req/min (write abuse)
        6. READS : 300 req/min (read abuse)
    """

    GLOBAL_IP = "global_ip"
    LOGIN = "login"
    USER_AUTHENTICATED = "user_authenticated"
    API_KEY_AUTHENTICATED = "api_key_authenticated"
    MUTATIONS = "mutations"
    READS = "reads"

    # App-specific (quotas adaptés au profil d'usage)
    EPICERIE_AUTHENTICATED = "epicerie_authenticated"
    EPICERIE_MUTATIONS = "epicerie_mutations"
    RESTAURANT_AUTHENTICATED = "restaurant_authenticated"
    RESTAURANT_MUTATIONS = "restaurant_mutations"


__all__ = [
    "Argon2Params",
    "BruteForceThresholds",
    "CredentialStuffingThresholds",
    "MFAConfig",
    "PasswordPolicy",
    "SessionConfig",
    "SecurityHeaders",
    "RedisKeys",
    "RateLimitScope",
]
