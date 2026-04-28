"""Configuration de l'application CaroCorp."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from functools import lru_cache
import logging
import socket

logger = logging.getLogger(__name__)


def _get_lan_ips() -> list[str]:
    """Détecte les IPs LAN de la machine (IPv4 non-loopback)."""
    ips: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    # Fallback : connecter un socket UDP vers un IP externe pour trouver l'IP LAN
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
            s.close()
        except OSError:
            pass
    return list(set(ips))


class Settings(BaseSettings):
    """Configuration principale de l'application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignorer les champs extra du .env
    )

    # Application
    APP_NAME: str = "CaroCorp"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database (obligatoire via .env)
    DATABASE_URL: str = ""
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    @property
    def DATABASE_ASYNC_URL(self) -> str:
        """URL async dérivée de DATABASE_URL (psycopg2 → asyncpg)."""
        return self.DATABASE_URL.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)

    # JWT Authentication (RS256 — CaroCorp §1.1-1.4)
    JWT_ALGORITHM: str = "RS256"
    # Deux paires de clés distinctes (CaroCorp §1.1 — séparation access/refresh)
    JWT_ACCESS_PRIVATE_KEY_PATH: str = "keys/jwt_access_private.pem"
    JWT_ACCESS_PUBLIC_KEY_PATH: str = "keys/jwt_access_public.pem"
    JWT_REFRESH_PRIVATE_KEY_PATH: str = "keys/jwt_refresh_private.pem"
    JWT_REFRESH_PUBLIC_KEY_PATH: str = "keys/jwt_refresh_public.pem"
    JWT_ISSUER: str = "marveline.com"
    JWT_AUDIENCE: str = "marveline-api"
    # ISO-APP-01 : audience JWT par app_code du tenant. Permet l'enforcement
    # app↔tenant (token Marveline non utilisable sur endpoints Épicerie/Restaurant).
    JWT_AUDIENCES: dict[str, str] = {
        "marveline": "marveline-api",
        "epicerie": "epicerie-api",
        "restaurant": "restaurant-api",
    }
    JWT_ACCESS_TOKEN_EXPIRE_SECONDS: int = 900  # 15 min (CaroCorp §1.4)
    JWT_REFRESH_TOKEN_EXPIRE_SECONDS: int = 604800  # 7 jours
    JWT_CLOCK_SKEW_SECONDS: int = 15  # P3-03 : ±15s (etait 30s, RFC recommande 10-15s)
    JWT_RSA_KEY_SIZE: int = 2048  # 4096 recommandé post-2030 (NIST SP 800-56B)
    # KMS (prod only — dev utilise les fichiers PEM locaux, CaroCorp §1.1)
    KMS_KEY_ACCESS: str = ""   # alias/auth-access-jwt
    KMS_KEY_REFRESH: str = ""  # alias/auth-refresh-jwt

    # Password hashing (CaroCorp §13.5) — obligatoire via .env (min 32 chars)
    PASSWORD_PEPPER: str = ""

    # Redis dual (CaroCorp §3.1-3.2)
    REDIS_SEC_URL: str = "redis://:dev_local@localhost:6380/0"
    REDIS_CACHE_URL: str = "redis://:dev_local@localhost:6381/0"

    # Celery (sur redis-cache — pas de donnee auth)
    CELERY_BROKER_URL: str = "redis://:dev_local@localhost:6381/1"
    CELERY_RESULT_BACKEND: str = "redis://:dev_local@localhost:6381/2"

    # CORS — prod : marveline.fr + massacorp.fr ; dev : localhost:3000 (reverse proxy)
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3002"]
    # Prod override via .env :
    # CORS_ORIGINS=["https://marveline.fr","https://massacorp.fr"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # Trusted hosts (TrustedHostMiddleware) — configurable via .env
    # Défaut dev : localhost + Docker. Prod : ajouter le domaine réel.
    # Mobile LAN : ajouter l'IP locale (ex: "192.168.1.10")
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "api", "testserver"]

    # Security
    BCRYPT_ROUNDS: int = 12

    # Argon2id (OWASP 2024+ recommended)
    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_COST: int = 65536   # 64 MiB en KiB
    ARGON2_PARALLELISM: int = 4

    # MFA / Encryption
    ENCRYPTION_KEY: str = ""  # 32 bytes pour AES-256 — obligatoire via .env
    MFA_ISSUER_NAME: str = "Marveline"
    # KEK master pour envelope encryption TOTP (spec §05-MFA-TOTP §5.4)
    # Prod : utiliser une valeur ≥ 32 chars aléatoire ou ARN AWS KMS
    TOTP_DEV_MASTER_KEY: str = ""  # KEK TOTP — obligatoire via .env

    # HMAC signing des audit logs (spec §01 §1.8)
    # Prod : valeur aléatoire ≥ 32 chars (ou ARN AWS Secrets Manager versionné)
    AUDIT_HMAC_KEY: str = ""  # HMAC audit — obligatoire via .env

    # hCaptcha (CaroCorp §7.2 NIVEAU 4 — validation CAPTCHA côté serveur)
    HCAPTCHA_ENABLED: bool = False
    HCAPTCHA_SECRET_KEY: str = ""
    HCAPTCHA_VERIFY_URL: str = "https://hcaptcha.com/siteverify"

    # OAuth providers (Google, GitHub, Facebook)
    OAUTH_GOOGLE_CLIENT_ID: str = ""
    OAUTH_GOOGLE_CLIENT_SECRET: str = ""
    OAUTH_GOOGLE_REDIRECT_URI: str = "http://localhost:3000/auth/callback/google"

    OAUTH_GITHUB_CLIENT_ID: str = ""
    OAUTH_GITHUB_CLIENT_SECRET: str = ""
    OAUTH_GITHUB_REDIRECT_URI: str = "http://localhost:3000/auth/callback/github"

    OAUTH_FACEBOOK_CLIENT_ID: str = ""
    OAUTH_FACEBOOK_CLIENT_SECRET: str = ""
    OAUTH_FACEBOOK_REDIRECT_URI: str = "http://localhost:3000/auth/callback/facebook"

    # ── Loyalty / Wallet ─────────────────────────────────────────────────────
    LOYALTY_BARCODE_SECRET: str = "dev_loyalty_barcode_secret_change_me_32chars"

    # Apple Wallet (PKPass)
    APPLE_PASS_TYPE_ID: str = ""  # ex: pass.fr.lincontournable.fidelite
    APPLE_TEAM_ID: str = ""
    APPLE_PASS_CERT_PATH: str = ""  # chemin vers le .pem du certificat Pass Type
    APPLE_PASS_KEY_PATH: str = ""   # chemin vers la cle privee .pem
    APPLE_WWDR_CERT_PATH: str = ""  # chemin vers le certificat WWDR Apple
    APNS_KEY_PATH: str = ""         # cle .p8 APNs
    APNS_KEY_ID: str = ""
    APNS_USE_SANDBOX: bool = True

    # Google Wallet
    GOOGLE_WALLET_ISSUER_ID: str = ""
    GOOGLE_WALLET_SERVICE_ACCOUNT_JSON: str = ""  # chemin vers le service account JSON
    GOOGLE_WALLET_CLASS_SUFFIX: str = "loyalty"

    # WireGuard Service (proxy inter-service)
    WG_SERVICE_URL: str = "http://wireguard-service:8002"
    WG_INTERNAL_API_KEY: str = ""  # WireGuard inter-service — obligatoire via .env

    # Boxtal (carrier quotes — ex EnvoiMoinsCher)
    BOXTAL_LOGIN: str = ""
    BOXTAL_PASSWORD: str = ""
    BOXTAL_ENV: str = "test"  # "test" ou "prod"
    BOXTAL_WEBHOOK_SECRET: str = ""  # cle HMAC-SHA256 pour valider x-bxt-signature

    # Frontend (for email links)
    FRONTEND_URL: str = "http://localhost:3000"

    # Email (MailHog in dev, real SMTP in prod)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM: str = "noreply@marveline.com"

    # Sentry (APM + erreurs)
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"

    # Uploads
    UPLOAD_DIR: str = "/uploads"

    # M-07 : IP whitelist partenaires de confiance (exemption rate limiting)
    TRUSTED_PARTNER_IPS: list[str] = []  # ex: ["203.0.113.0/24"]

    # DB SSL (P3-15)
    DB_SSL_MODE: str = ""  # vide en dev, "require" en prod

    # Proxy de confiance (nginx/traefik) — activer pour utiliser X-Forwarded-For
    # DÉSACTIVÉ par défaut : sans proxy de confiance configuré, X-Forwarded-For
    # est contrôlable par le client → bypass rate limit possible.
    TRUSTED_PROXY_HEADERS: bool = False

    # Logging & compression
    LOG_LEVEL: str = "INFO"
    GZIP_MIN_SIZE: int = 500

    @property
    def COOKIE_SECURE(self) -> bool:
        """Secure flag pour les cookies httpOnly (refresh_token, etc.).

        False en DEBUG car le réseau local est HTTP — Safari iOS refuse
        les cookies Secure sur des connexions non-HTTPS.
        """
        return not self.DEBUG

    @model_validator(mode='after')
    def expand_dev_network(self) -> 'Settings':
        """En mode DEBUG, ajoute automatiquement les IPs LAN aux CORS et hosts.

        Résout le problème d'accès mobile (iOS/Android) sur le réseau local :
        sans cela, il faut ajouter manuellement chaque IP au .env.
        """
        if not self.DEBUG:
            return self
        # P3-08 : restreint a localhost uniquement (plus de scan LAN)
        dev_ports = [3000, 3002, 5173, 80]
        existing_origins = set(self.CORS_ORIGINS)
        existing_hosts = set(self.ALLOWED_HOSTS)
        added_origins: list[str] = []
        added_hosts: list[str] = []
        for host in ("localhost", "127.0.0.1"):
            if host not in existing_hosts:
                added_hosts.append(host)
            for port in dev_ports:
                origin = f"http://{host}:{port}"
                if origin not in existing_origins:
                    added_origins.append(origin)
        # Ngrok tunnel : auto-detect URL via ngrok local API (docker profile "tunnel")
        self._add_ngrok_origin(existing_origins, added_origins)
        if added_origins:
            self.CORS_ORIGINS = [*self.CORS_ORIGINS, *added_origins]
        if added_hosts:
            self.ALLOWED_HOSTS = [*self.ALLOWED_HOSTS, *added_hosts]
        if added_origins or added_hosts:
            logger.info(
                "DEV auto-network: +%d CORS origins, +%d allowed hosts",
                len(added_origins), len(added_hosts),
            )
        return self

    @staticmethod
    def _add_ngrok_origin(
        existing: set[str], added: list[str]
    ) -> None:
        """Détecte l'URL ngrok via son API locale (port 4040) et l'ajoute au CORS.

        Appelé uniquement en DEBUG. Timeout très court (0.3s) pour ne pas
        ralentir le startup si ngrok n'est pas lancé.
        """
        import urllib.request
        import json
        try:
            req = urllib.request.Request(
                "http://localhost:4040/api/tunnels",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=0.3) as resp:
                data = json.loads(resp.read())
            for tunnel in data.get("tunnels", []):
                url = tunnel.get("public_url", "")
                if url.startswith("https://") and url not in existing:
                    added.append(url)
                    logger.info("DEV ngrok tunnel detected: %s", url)
        except Exception:
            pass  # ngrok not running — silent

    @model_validator(mode='after')
    def validate_production_secrets(self) -> 'Settings':
        """Verifie que tous les secrets critiques sont renseignes et securises.

        Validation inconditionnelle (meme DEBUG=True) :
        - Secrets obligatoires : non vides, min 32 chars, pas de prefixe dev_
        - DATABASE_URL : non vide
        - Secrets optionnels : vide OK (service non active), dev_ = violation
        """
        violations: list[str] = []

        # DATABASE_URL obligatoire
        if not self.DATABASE_URL:
            violations.append("DATABASE_URL (requis — definir dans .env)")

        # Secrets obligatoires : non vides + min 32 chars + pas de prefixe dev_
        mandatory_secrets = [
            "PASSWORD_PEPPER",
            "ENCRYPTION_KEY",
            "TOTP_DEV_MASTER_KEY",
            "AUDIT_HMAC_KEY",
            "WG_INTERNAL_API_KEY",
        ]
        for field_name in mandatory_secrets:
            val = getattr(self, field_name)
            if not val:
                violations.append(f"{field_name} (vide — definir dans .env)")
            elif val.startswith("dev_"):
                violations.append(f"{field_name} (prefixe dev_ interdit)")
            elif len(val) < 32:
                violations.append(f"{field_name} (trop court: {len(val)} < 32 chars)")

        # Secrets optionnels : vide = service non active (OK), dev_ = violation
        optional_secrets = [
            "HCAPTCHA_SECRET_KEY",
            "OAUTH_GOOGLE_CLIENT_SECRET",
            "OAUTH_GITHUB_CLIENT_SECRET",
            "OAUTH_FACEBOOK_CLIENT_SECRET",
        ]
        for field_name in optional_secrets:
            val = getattr(self, field_name)
            if val and val.startswith("dev_"):
                violations.append(f"{field_name} (prefixe dev_ interdit)")

        # Production : COOKIE_SECURE obligatoire
        if not self.DEBUG and not self.COOKIE_SECURE:
            violations.append("COOKIE_SECURE doit etre True en production")

        if violations:
            raise ValueError(
                f"SECURITE CRITIQUE — {len(violations)} violation(s) :\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\nDefinir ces variables dans .env avec des valeurs securisees."
            )

        return self


@lru_cache()
def get_settings() -> Settings:
    """Singleton pour la configuration."""
    return Settings()


settings = get_settings()
