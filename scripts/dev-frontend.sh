#!/bin/bash
# Démarrer le frontend en mode développement avec hot reload
# Usage: ./scripts/dev-frontend.sh

set -e

echo "🔧 Mode développement frontend avec hot reload"
echo "================================================"
echo ""
echo "Les modifications de code seront appliquées automatiquement"
echo "Pas besoin de rebuild Docker à chaque changement"
echo ""
echo "Frontend accessible sur: http://localhost:3002"
echo "API proxy vers: http://api:8000"
echo ""

# Arrêter le frontend prod si en cours
docker compose stop frontend 2>/dev/null || true

# Démarrer le frontend dev avec override config
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build frontend

echo ""
echo "✅ Frontend dev arrêté"
echo ""
echo "Pour revenir au mode production (build statique):"
echo "  docker compose up -d frontend"
