#!/bin/bash
# Script de correction Round 2

set -e

echo "🔧 Correction Round 2 - Erreurs supplémentaires..."
echo ""

backup_file() {
    if [ -f "$1" ]; then
        cp "$1" "$1.bak2.$(date +%Y%m%d_%H%M%S)"
        echo "  📦 Backup : $1.bak2"
    fi
}

# 1. Activer middlewares de sécurité
echo "1️⃣  Activation middlewares de sécurité dans main.py..."
backup_file "app/main.py"
cat > app/main.py << 'EOF'
"""Point d'entrée principal de l'API CaroCorp."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.api.v1 import api_router
from app.middleware.security import (
    CSRFProtectionMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
)


def create_application() -> FastAPI:
    """Factory pour créer l'application FastAPI."""

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="API de gestion de location de vaisselle et accessoires pour événements",
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
    )

    # Security Headers Middleware (premier pour headers sur toutes réponses)
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trusted Host Middleware (protection contre Host Header Injection)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.carocorp.local"],
    )

    # CSRF Protection Middleware
    app.add_middleware(CSRFProtectionMiddleware)

    # Rate Limiting Middleware
    app.add_middleware(RateLimitMiddleware)

    # Routes API v1
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        """Endpoint de santé pour monitoring."""
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
EOF
echo "  ✅ 3 middlewares activés : SecurityHeaders, CSRF, RateLimit"
echo ""

# 2. Corriger .env avec variables manquantes
echo "2️⃣  Ajout variables manquantes dans .env..."
backup_file ".env"
cat > .env << 'EOF'
# Configuration CaroCorp - Development

# Application
ENV=dev
DEBUG=true
APP_NAME=CaroCorp
APP_VERSION=0.1.0

# Database
DATABASE_URL=postgresql+psycopg2://caro:dev_password@localhost:5433/CaroCorp
POSTGRES_DB=CaroCorp
POSTGRES_USER=caro
POSTGRES_PASSWORD=dev_postgres_password_CHANGER_EN_PROD
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10

# Security
JWT_SECRET=dev_jwt_secret_CHANGER_EN_PRODUCTION_min32chars
CSRF_SECRET=dev_csrf_secret_CHANGER_EN_PRODUCTION_min32chars
BCRYPT_ROUNDS=12

# Redis
REDIS_PASSWORD=dev_redis_password_CHANGER_EN_PROD
REDIS_URL=redis://:dev_redis_password_CHANGER_EN_PROD@localhost:6380/0
SESSION_EXPIRE_SECONDS=3600

# Celery
CELERY_BROKER_URL=redis://:dev_redis_password_CHANGER_EN_PROD@localhost:6380/1
CELERY_RESULT_BACKEND=redis://:dev_redis_password_CHANGER_EN_PROD@localhost:6380/2

# CORS
CORS_ORIGINS=["http://localhost:3002"]
CORS_ALLOW_CREDENTIALS=true
EOF
echo "  ✅ POSTGRES_PASSWORD et REDIS_PASSWORD ajoutés"
echo ""

# 3. Harmoniser .env.example
echo "3️⃣  Harmonisation .env.example..."
backup_file ".env.example"
cp .env .env.example
sed -i 's/dev_postgres_password_CHANGER_EN_PROD/CHANGER_MOT_DE_PASSE_POSTGRES/g' .env.example
sed -i 's/dev_redis_password_CHANGER_EN_PROD/CHANGER_MOT_DE_PASSE_REDIS/g' .env.example
sed -i 's/dev_jwt_secret_CHANGER_EN_PRODUCTION_min32chars/CHANGER_CLE_JWT_MIN_32_CARACTERES/g' .env.example
sed -i 's/dev_csrf_secret_CHANGER_EN_PRODUCTION_min32chars/CHANGER_CLE_CSRF_MIN_32_CARACTERES/g' .env.example
echo "  ✅ .env.example synchronisé avec .env"
echo ""

# 4. Supprimer import hashlib inutile
echo "4️⃣  Nettoyage import inutile dans security.py..."
backup_file "app/middleware/security.py"
sed -i '/^import hashlib$/d' app/middleware/security.py
echo "  ✅ Import hashlib supprimé"
echo ""

echo ""
echo "✅ ROUND 2 TERMINÉ !"
echo ""
echo "🔐 Sécurité maintenant active :"
echo "  ✅ CSRF Protection"
echo "  ✅ Security Headers (X-Frame-Options, CSP, HSTS)"
echo "  ✅ Rate Limiting"
echo ""
echo "📝 Prochaines étapes :"
echo "  1. Tester : docker-compose up -d"
echo "  2. Vérifier : curl http://localhost:8001/health"
echo "  3. Lire : ERREURS_ROUND2.md pour détails"
