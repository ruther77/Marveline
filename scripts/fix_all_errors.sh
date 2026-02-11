#!/bin/bash
# Script de correction automatique des erreurs détectées

set -e

echo "🔧 Correction automatique des erreurs CaroCorp..."
echo ""

# Fonction pour backup
backup_file() {
    if [ -f "$1" ]; then
        cp "$1" "$1.bak.$(date +%Y%m%d_%H%M%S)"
        echo "  📦 Backup créé : $1.bak"
    fi
}

# 1. Corriger docker-compose.yml - Chemin Celery
echo "1️⃣  Correction chemin Celery dans docker-compose.yml..."
backup_file "docker-compose.yml"
sed -i 's|celery -A app\.core\.celery:celery_app|celery -A app.tasks.celery_app:celery_app|g' docker-compose.yml
echo "  ✅ Chemin Celery corrigé"
echo ""

# 2. Corriger pyproject.toml - Ajouter dépendances
echo "2️⃣  Ajout dépendances manquantes dans pyproject.toml..."
backup_file "pyproject.toml"
cat > pyproject.toml << 'EOF'
[tool.poetry]
name = "carocorp"
version = "0.1.0"
description = "CaroCorp - Gestion location vaisselle événements"
authors = ["Équipe CaroCorp"]

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.115.0"
uvicorn = {extras = ["standard"], version = "^0.32.0"}
sqlalchemy = "^2.0.0"
alembic = "^1.13.0"
psycopg2-binary = "^2.9.9"
pydantic-settings = "^2.6.0"
redis = "^5.0.0"
celery = "^5.4.0"
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
passlib = {extras = ["bcrypt"], version = "^1.7.4"}

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.0"
pytest-cov = "^6.0.0"
pytest-asyncio = "^0.24.0"
httpx = "^0.27.0"
black = "^24.10.0"
flake8 = "^7.1.0"
mypy = "^1.13.0"
bandit = "^1.7.10"
safety = "^3.2.0"
ruff = "^0.7.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
EOF
echo "  ✅ Dépendances ajoutées : black, flake8, bandit, safety, httpx, pytest-asyncio"
echo ""

# 3. Corriger config.py - Secrets avec fallback dev
echo "3️⃣  Ajout fallback dev pour secrets dans config.py..."
backup_file "app/core/config.py"
cat > app/core/config.py << 'EOF'
"""Configuration de l'application CaroCorp."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuration principale de l'application."""

    # Application
    APP_NAME: str = "CaroCorp"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://caro:password@localhost:5433/CaroCorp"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # JWT Authentication
    JWT_SECRET: str = "dev_jwt_secret_CHANGER_EN_PROD_min32chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Redis
    REDIS_URL: str = "redis://:password@localhost:6380/0"
    SESSION_EXPIRE_SECONDS: int = 3600

    # Celery
    CELERY_BROKER_URL: str = "redis://:password@localhost:6380/1"
    CELERY_RESULT_BACKEND: str = "redis://:password@localhost:6380/2"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3002"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # Security
    CSRF_SECRET: str = "dev_csrf_secret_CHANGER_EN_PROD_min32chars"
    BCRYPT_ROUNDS: int = 12

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Singleton pour la configuration."""
    return Settings()


settings = get_settings()
EOF
echo "  ✅ Secrets avec fallback dev ajoutés (CHANGER EN PRODUCTION)"
echo ""

# 4. Créer frontend/Dockerfile
echo "4️⃣  Création frontend/Dockerfile..."
cat > frontend/Dockerfile << 'EOF'
FROM node:20-alpine AS builder
WORKDIR /app

# Installation dépendances
COPY package*.json ./
RUN npm ci

# Build application
COPY . .
RUN npm run build

# Production
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
EOF

cat > frontend/nginx.conf << 'EOF'
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://carocorp_api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

cat > frontend/package.json << 'EOF'
{
  "name": "carocorp-frontend",
  "version": "0.1.0",
  "scripts": {
    "dev": "echo 'TODO: Setup Vite/React'",
    "build": "mkdir -p dist && echo '<h1>CaroCorp - Frontend TODO</h1>' > dist/index.html"
  }
}
EOF
echo "  ✅ Frontend Dockerfile créé (placeholder)"
echo ""

# 5. Corriger .gitignore
echo "5️⃣  Complétion .gitignore..."
cat >> .gitignore << 'EOF'

# Coverage
htmlcov/
.coverage
.coverage.*

# Pytest
.pytest_cache/

# Python
*.egg-info/
dist/
build/

# Backups
*.bak.*
EOF
echo "  ✅ .gitignore complété"
echo ""

# 6. Corriger pytest.ini
echo "6️⃣  Ajout --cov-fail-under dans pytest.ini..."
backup_file "pytest.ini"
cat > pytest.ini << 'EOF'
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --strict-markers
    --tb=short
    --cov=app
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    security: Security tests
    slow: Slow running tests
EOF
echo "  ✅ Coverage threshold 80% ajouté"
echo ""

echo ""
echo "✅ TOUTES LES CORRECTIONS APPLIQUÉES !"
echo ""
echo "📝 Prochaines étapes :"
echo "  1. Vérifier les backups (*.bak.*) si besoin de rollback"
echo "  2. Exécuter : poetry lock --no-update"
echo "  3. Exécuter : poetry install"
echo "  4. Tester : docker-compose config"
echo "  5. Lire : ERREURS_DETECTEES.md pour les détails"
echo ""
echo "⚠️  IMPORTANT : Changez JWT_SECRET et CSRF_SECRET en production !"
