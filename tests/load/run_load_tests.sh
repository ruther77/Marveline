#!/bin/bash
# Script helper pour exécuter les tests de charge k6
# Usage: ./tests/load/run_load_tests.sh [test_name]

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-http://localhost:8001}"
RESULTS_DIR="tests/load/results"

echo -e "${BLUE}🚀 CaroCorp Load Testing Suite${NC}\n"

# Créer dossier résultats
mkdir -p "$RESULTS_DIR"

# Vérifier que k6 est installé
if ! command -v k6 &> /dev/null; then
    echo -e "${RED}❌ k6 n'est pas installé${NC}"
    echo ""
    echo "Installation Ubuntu/Debian:"
    echo "  sudo gpg -k"
    echo "  sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69"
    echo "  echo 'deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main' | sudo tee /etc/apt/sources.list.d/k6.list"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install k6"
    echo ""
    echo "Installation macOS:"
    echo "  brew install k6"
    echo ""
    exit 1
fi

# Vérifier que l'API est accessible
echo -e "${YELLOW}🔍 Vérification API à $API_URL...${NC}"
if curl -sf "$API_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API accessible${NC}\n"
else
    echo -e "${RED}❌ API non accessible à $API_URL${NC}"
    echo "Démarrez l'API avec: cd /path/to/CaroCorp && uvicorn app.main:app --reload"
    exit 1
fi

# Fonction pour exécuter un test
run_test() {
    local test_file=$1
    local test_name=$2
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local output_file="$RESULTS_DIR/${test_name}_${timestamp}.json"

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}📊 Test: $test_name${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

    # Exécuter k6
    if k6 run \
        --out json="$output_file" \
        -e API_URL="$API_URL" \
        "tests/load/$test_file"; then
        echo -e "\n${GREEN}✅ Test $test_name RÉUSSI${NC}"
        echo -e "${GREEN}📄 Résultats: $output_file${NC}\n"
        return 0
    else
        echo -e "\n${RED}❌ Test $test_name ÉCHOUÉ${NC}\n"
        return 1
    fi
}

# Menu de sélection
if [ -z "$1" ]; then
    echo "Sélectionnez un test:"
    echo "  1) GET Products (Cache Performance)"
    echo "  2) PATCH Products (Cache Invalidation)"
    echo "  3) Mixed Workload (90% GET / 10% PATCH)"
    echo "  4) Multi-Tenant Isolation"
    echo "  5) Tous les tests (suite complète)"
    echo "  6) Quick Smoke Test (30s)"
    echo ""
    read -p "Choix [1-6]: " choice
else
    choice=$1
fi

# Exécuter test(s)
case $choice in
    1)
        run_test "get_products_cache.js" "cache_performance"
        ;;
    2)
        run_test "patch_products_invalidation.js" "cache_invalidation"
        ;;
    3)
        run_test "mixed_workload.js" "mixed_workload"
        ;;
    4)
        run_test "multi_tenant_isolation.js" "multi_tenant"
        ;;
    5)
        echo -e "${YELLOW}🔥 Exécution suite complète...${NC}\n"
        run_test "get_products_cache.js" "cache_performance"
        run_test "patch_products_invalidation.js" "cache_invalidation"
        run_test "mixed_workload.js" "mixed_workload"
        run_test "multi_tenant_isolation.js" "multi_tenant"
        echo -e "${GREEN}✅ Suite complète terminée${NC}"
        ;;
    6)
        echo -e "${YELLOW}⚡ Quick Smoke Test (30s)${NC}\n"
        k6 run --duration 30s --vus 10 tests/load/get_products_cache.js
        ;;
    *)
        echo -e "${RED}Choix invalide${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 Tests terminés${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
