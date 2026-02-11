#!/bin/bash
# Script pour lancer tous les tests CaroCorp

set -e

echo "🧪 Lancement des tests CaroCorp..."

# Couleurs pour output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Vérifier que les services sont up
echo "🔍 Vérification des services de test..."
if ! nc -z localhost 5433 2>/dev/null; then
    echo -e "${RED}❌ PostgreSQL test (port 5433) non accessible${NC}"
    exit 1
fi

if ! nc -z localhost 6380 2>/dev/null; then
    echo -e "${RED}❌ Redis test (port 6380) non accessible${NC}"
    exit 1
fi

# Tests unitaires
echo -e "\n${YELLOW}📦 Tests unitaires...${NC}"
poetry run pytest tests/unit/ -v --cov=app --cov-report=term-missing || {
    echo -e "${RED}❌ Tests unitaires échoués${NC}"
    exit 1
}

# Tests d'intégration
echo -e "\n${YELLOW}🔗 Tests d'intégration...${NC}"
poetry run pytest tests/integration/ -v || {
    echo -e "${RED}❌ Tests d'intégration échoués${NC}"
    exit 1
}

# Tests E2E
echo -e "\n${YELLOW}🌐 Tests E2E...${NC}"
poetry run pytest tests/e2e/ -v || {
    echo -e "${RED}❌ Tests E2E échoués${NC}"
    exit 1
}

# Tests de sécurité
echo -e "\n${YELLOW}🔒 Tests de sécurité...${NC}"
poetry run pytest tests/security/ -v || {
    echo -e "${RED}❌ Tests de sécurité échoués${NC}"
    exit 1
}

# Linting
echo -e "\n${YELLOW}🔍 Linting (Black, Flake8, MyPy)...${NC}"
poetry run black --check app/ tests/ || {
    echo -e "${YELLOW}⚠️  Formatage incorrect. Exécutez : poetry run black app/ tests/${NC}"
}

poetry run flake8 app/ tests/ || {
    echo -e "${YELLOW}⚠️  Problèmes de linting détectés${NC}"
}

# Sécurité
echo -e "\n${YELLOW}🛡️  Analyse de sécurité (Bandit)...${NC}"
poetry run bandit -r app/ -ll || {
    echo -e "${YELLOW}⚠️  Problèmes de sécurité potentiels détectés${NC}"
}

echo -e "\n${GREEN}✅ Tous les tests ont réussi !${NC}"
