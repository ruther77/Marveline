#!/bin/bash
# Script d'initialisation du projet CaroCorp

set -e

echo "🚀 Initialisation du projet CaroCorp..."

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Erreur : pyproject.toml non trouvé. Exécutez ce script depuis la racine du projet."
    exit 1
fi

# Vérifier que .env existe
if [ ! -f ".env" ]; then
    echo "⚠️  Fichier .env non trouvé. Copie de .env.example..."
    cp .env.example .env
    echo "⚙️  IMPORTANT : Éditez .env et changez JWT_SECRET et CSRF_SECRET !"
fi

# Installer Poetry si nécessaire
if ! command -v poetry &> /dev/null; then
    echo "📦 Installation de Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

# Installer les dépendances
echo "📦 Installation des dépendances..."
poetry install

# Vérifier que PostgreSQL et Redis sont disponibles
echo "🔍 Vérification des services..."
if ! nc -z localhost 5433 2>/dev/null; then
    echo "⚠️  PostgreSQL (port 5433) n'est pas accessible. Lancez : docker-compose up -d db"
fi

if ! nc -z localhost 6380 2>/dev/null; then
    echo "⚠️  Redis (port 6380) n'est pas accessible. Lancez : docker-compose up -d redis"
fi

# Créer la base de données si elle n'existe pas
echo "🗄️  Vérification de la base de données..."
poetry run python -c "from app.models.base import Base; from app.core.database import engine; Base.metadata.create_all(bind=engine)" 2>/dev/null || true

echo ""
echo "✅ Initialisation terminée !"
echo ""
echo "📝 Prochaines étapes :"
echo "  1. Éditez .env et changez les secrets (JWT_SECRET, CSRF_SECRET)"
echo "  2. Lancez les services : docker-compose up -d"
echo "  3. Lancez l'API : poetry run uvicorn app.main:app --reload --port 8001"
echo "  4. Tests : poetry run pytest -v"
echo ""
echo "📚 Documentation :"
echo "  - README.md : Guide de démarrage"
echo "  - ARCHITECTURE.md : Architecture détaillée"
echo "  - API docs : http://localhost:8001/api/docs"
echo ""
