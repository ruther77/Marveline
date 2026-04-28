#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# E2E Production Audit via ngrok
#
# Démarre un tunnel ngrok, configure l'environnement, exécute les tests
# Playwright avec monitoring 5 axes, et collecte les rapports .txt.
#
# Prérequis :
#   - ngrok installé et authentifié (ngrok config add-authtoken ...)
#   - Services Docker up (docker compose up -d)
#   - Playwright installé (cd frontend && pnpm exec playwright install)
#
# Usage :
#   ./scripts/deploy/run-e2e-ngrok.sh [--local]    # --local = sans ngrok
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
FRONTEND_DIR="$PROJECT_DIR/frontend"
RESULTS_DIR="$FRONTEND_DIR/test-results/monitoring"
RUN_ID="$(date '+%Y%m%d_%H%M%S')"
LOG_FILE="$RESULTS_DIR/run_${RUN_ID}.log"
LOCAL_MODE=false

if [[ "${1:-}" == "--local" ]]; then
    LOCAL_MODE=true
fi

mkdir -p "$RESULTS_DIR"

# ── Functions ─────────────────────────────────────────────────────────────────

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
cleanup() {
    log "Nettoyage..."
    if [[ -n "${NGROK_PID:-}" ]]; then
        kill "$NGROK_PID" 2>/dev/null || true
        log "ngrok arrêté (PID $NGROK_PID)"
    fi
}
trap cleanup EXIT

# ── Step 1 : Vérifier les prérequis ──────────────────────────────────────────

log "═══════════════════════════════════════════════════"
log " E2E PRODUCTION AUDIT — Run $RUN_ID"
log "═══════════════════════════════════════════════════"

log "[1/6] Vérification des prérequis..."

# Docker services
if ! docker compose ps api --format json 2>/dev/null | grep -q '"running"'; then
    log "ERREUR: Le service API n'est pas démarré. Lancez: docker compose up -d"
    exit 1
fi
log "  API: running"

# Frontend dev server (port 3002)
if ! curl -sf http://localhost:3002/ > /dev/null 2>&1; then
    log "ATTENTION: Frontend dev server (port 3002) non détecté."
    log "  Lancez: cd frontend && pnpm --filter @carocorp/marveline dev"
    exit 1
fi
log "  Frontend: http://localhost:3002"

# Playwright
if ! (cd "$FRONTEND_DIR" && pnpm exec playwright --version > /dev/null 2>&1); then
    log "ERREUR: Playwright non installé. Lancez: cd frontend && pnpm exec playwright install"
    exit 1
fi
log "  Playwright: $(cd "$FRONTEND_DIR" && pnpm exec playwright --version 2>/dev/null)"

# ── Step 2 : Tunnel ngrok (sauf mode local) ──────────────────────────────────

NGROK_URL=""
if [[ "$LOCAL_MODE" == "true" ]]; then
    log "[2/6] Mode local — pas de tunnel ngrok"
    NGROK_URL="http://localhost:3002"
else
    log "[2/6] Démarrage du tunnel ngrok..."

    if ! command -v ngrok &> /dev/null; then
        log "ERREUR: ngrok non installé. Installez: https://ngrok.com/download"
        exit 1
    fi

    # Démarrer ngrok en background
    ngrok http 3002 --log=stdout --log-format=json > "/tmp/ngrok_${RUN_ID}.log" 2>&1 &
    NGROK_PID=$!
    log "  ngrok PID: $NGROK_PID"

    # Attendre que l'URL publique soit disponible
    TIMEOUT=15
    ELAPSED=0
    while [[ -z "$NGROK_URL" ]]; do
        sleep 1
        ELAPSED=$((ELAPSED + 1))
        NGROK_URL=$(curl -sf http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for t in data.get('tunnels', []):
        if 'https' in t.get('public_url', ''):
            print(t['public_url'])
            break
except: pass
" 2>/dev/null || true)

        if [[ "$ELAPSED" -ge "$TIMEOUT" ]]; then
            log "ERREUR: ngrok n'a pas démarré en ${TIMEOUT}s"
            exit 1
        fi
    done

    log "  URL publique: $NGROK_URL"
fi

# ── Step 3 : Configurer les variables d'environnement ─────────────────────────

log "[3/6] Configuration de l'environnement..."

export PLAYWRIGHT_BASE_URL="${NGROK_URL:-http://localhost:3002}"
export API_BASE_URL="${NGROK_URL:+${NGROK_URL}/api/v1}"
export API_BASE_URL="${API_BASE_URL:-http://localhost:8001/api/v1}"
export E2E_ADMIN_EMAIL="${E2E_ADMIN_EMAIL:-admin@carocorp.dev}"
export E2E_ADMIN_PASSWORD="${E2E_ADMIN_PASSWORD:-Admin123!}"

log "  PLAYWRIGHT_BASE_URL=$PLAYWRIGHT_BASE_URL"
log "  API_BASE_URL=$API_BASE_URL"
log "  E2E_ADMIN_EMAIL=$E2E_ADMIN_EMAIL"

# ── Step 4 : Exécuter les tests ──────────────────────────────────────────────

log "[4/6] Exécution des tests E2E avec monitoring..."

cd "$FRONTEND_DIR"

# Exécuter production-audit.spec.ts avec sortie détaillée
pnpm exec playwright test production-audit \
    --reporter=list \
    --timeout=120000 \
    --retries=0 \
    --workers=1 \
    2>&1 | tee -a "$LOG_FILE"

TEST_EXIT=$?

# ── Step 5 : Collecter les rapports ──────────────────────────────────────────

log "[5/6] Collecte des rapports..."

REPORT_COUNT=$(find "$RESULTS_DIR" -name "${RUN_ID:0:8}*.txt" -newer "$LOG_FILE" 2>/dev/null | wc -l)
log "  Rapports monitoring générés: $REPORT_COUNT"

# Lister les fichiers générés
find "$RESULTS_DIR" -name "*.txt" -newer "$LOG_FILE" -exec basename {} \; | while read -r f; do
    log "  → $f"
done

# ── Step 6 : Résumé ──────────────────────────────────────────────────────────

log "[6/6] Résumé..."
log ""
log "═══════════════════════════════════════════════════"
log " RÉSULTAT: $([ $TEST_EXIT -eq 0 ] && echo 'PASS' || echo 'FAIL')"
log " Rapports: $RESULTS_DIR/"
log " Log complet: $LOG_FILE"
if [[ -n "$NGROK_URL" && "$NGROK_URL" != "http://localhost:3002" ]]; then
    log " URL ngrok: $NGROK_URL"
fi
log "═══════════════════════════════════════════════════"

exit $TEST_EXIT
