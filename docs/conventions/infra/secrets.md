# Infra — Gestion des Secrets

## Principe : Zéro Secret Hardcodé

- Jamais de secret dans le code source (même en dev)
- Jamais de secret dans les logs ou traces
- Jamais de secret dans les messages d'erreur
- `.env` jamais commité (dans `.gitignore`)
- `.env.example` commité avec des valeurs fictives

## Vault / Doppler

```python
# Option 1 : HashiCorp Vault
import hvac

vault_client = hvac.Client(url=settings.VAULT_URL, token=settings.VAULT_TOKEN)

def get_secret(path: str) -> dict:
    return vault_client.secrets.kv.v2.read_secret_version(path=path)["data"]["data"]

# Récupérer les secrets au démarrage
secrets = get_secret("marveline/production")
DATABASE_PASSWORD = secrets["database_password"]
```

```bash
# Option 2 : Doppler CLI
# Injecter les secrets dans l'environnement
doppler run -- uvicorn app.main:app

# En CI/CD
- name: Deploy with secrets
  env:
    DOPPLER_TOKEN: ${{ secrets.DOPPLER_TOKEN }}
  run: doppler run -- ./scripts/deploy.sh
```

## Rotation des Secrets

```python
# Stratégie de rotation sans interruption de service
class SecretRotationStrategy:
    """
    Rotation en 2 phases :
    1. Ajouter le nouveau secret (les deux fonctionnent)
    2. Désactiver l'ancien secret
    """

    def rotate_db_password(self, old_password: str, new_password: str) -> None:
        # Phase 1 : créer le nouvel utilisateur DB
        self._create_db_user(new_password)

        # Phase 2 : redémarrer les workers avec le nouveau password
        self._restart_workers_with_new_password(new_password)

        # Phase 3 : après vérification, désactiver l'ancien
        self._revoke_old_db_user(old_password)
```

## DB SSL/TLS

```python
# Connexion PostgreSQL avec SSL obligatoire en production
DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    f"?sslmode=require"
    f"&sslcert=/path/to/client.crt"
    f"&sslkey=/path/to/client.key"
    f"&sslrootcert=/path/to/ca.crt"
)

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "sslmode": "require",
        "sslcert": settings.DB_SSL_CERT,
        "sslkey": settings.DB_SSL_KEY,
        "sslrootcert": settings.DB_SSL_CA,
    },
)
```

## Encryption Keys

```python
# app/core/config.py
from pydantic_settings import BaseSettings
from cryptography.fernet import Fernet

class Settings(BaseSettings):
    # Chiffrement des champs sensibles
    FIELD_ENCRYPTION_KEY: bytes  # Générer avec Fernet.generate_key()

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # MFA
    MFA_SECRET_KEY: str  # Pour TOTP

    # CSRF
    CSRF_SECRET_KEY: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

## .env.example

```bash
# .env.example — Valeurs fictives pour documentation
DATABASE_URL=postgresql://user:CHANGE_ME@localhost:5432/marveline
REDIS_URL=redis://localhost:6379
JWT_SECRET_KEY=CHANGE_ME_USE_openssl_rand_-hex_32
FIELD_ENCRYPTION_KEY=CHANGE_ME_USE_Fernet.generate_key()
SENTRY_DSN=https://CHANGE_ME@sentry.io/PROJECT_ID
VAULT_URL=https://vault.internal:8200
```

## Checklist Sécurité Secrets

- ☐ `.env` dans `.gitignore`
- ☐ `.env.example` committé avec valeurs fictives
- ☐ Pas de secret dans les logs (Sentry `before_send`)
- ☐ Rotation automatique planifiée (Celery beat)
- ☐ DB SSL en production
- ☐ JWT secret ≥ 256 bits (`openssl rand -hex 32`)
- ☐ Scan secrets en CI (truffleHog ou git-secrets)
