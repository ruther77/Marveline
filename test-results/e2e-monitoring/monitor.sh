#!/usr/bin/env bash
# ============================================================
# E2E Monitoring — 5 axes simultanés
# Usage: ./monitor.sh [session_name]
# ============================================================
set -euo pipefail

SESSION="${1:-$(date +%Y%m%d_%H%M%S)}"
DIR="$(cd "$(dirname "$0")" && pwd)/sessions/${SESSION}"
mkdir -p "$DIR"

API_BASE="http://localhost:8001"

# Fichiers de sortie
TRACE="$DIR/1_trace_execution.txt"
PERF="$DIR/2_temps_execution.txt"
PARASITES="$DIR/3_parasitages_appels.txt"
COHERENCE="$DIR/4_coherence_backend_frontend.txt"
LOGS="$DIR/5_logs_erreurs_activites.txt"
SUMMARY="$DIR/0_resume_session.txt"

# Initialisation des fichiers
for f in "$TRACE" "$PERF" "$PARASITES" "$COHERENCE" "$LOGS" "$SUMMARY"; do
  echo "═══════════════════════════════════════════════════════════" > "$f"
  echo "  SESSION: $SESSION — $(date '+%Y-%m-%d %H:%M:%S')" >> "$f"
  echo "═══════════════════════════════════════════════════════════" >> "$f"
  echo "" >> "$f"
done

echo "[AXE 1] TRACE D'EXECUTION" >> "$TRACE"
echo "[AXE 2] TEMPS D'EXECUTION (ms)" >> "$PERF"
echo "[AXE 3] PARASITAGES D'APPELS" >> "$PARASITES"
echo "[AXE 4] COHERENCE BACKEND / FRONTEND" >> "$COHERENCE"
echo "[AXE 5] LOGS ERREURS & ACTIVITES" >> "$LOGS"

# --- AXE 1 : Trace d'exécution (capture API health + services) ---
echo "" >> "$TRACE"
echo "[$(date '+%H:%M:%S')] === Démarrage monitoring ===" >> "$TRACE"
echo "[$(date '+%H:%M:%S')] Docker services:" >> "$TRACE"
docker compose -f "/home/ruuuzer/Documents/FUTUR PROJ/docker-compose.yml" ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null >> "$TRACE"
echo "" >> "$TRACE"

# --- AXE 2 : Temps d'exécution des endpoints critiques ---
echo "" >> "$PERF"
echo "Endpoint                          | Status | Temps (ms)" >> "$PERF"
echo "----------------------------------|--------|----------" >> "$PERF"

declare -a ENDPOINTS=(
  "/api/v1/health"
  "/api/v1/dashboard/stats"
  "/api/v1/reservations?page=1&per_page=10"
  "/api/v1/products?page=1&per_page=10"
  "/api/v1/customers?page=1&per_page=10"
  "/api/v1/invoices?page=1&per_page=10"
  "/api/v1/planning/today"
  "/api/v1/categories"
)

# Récupérer un token d'auth
TOKEN=$(curl -s -X POST "$API_BASE/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@carocorp.fr","password":"Admin123!@#"}' \
  2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
  echo "[WARN] Impossible d'obtenir un token auth — tests auth requis" >> "$LOGS"
  TOKEN="no-token"
fi

for ep in "${ENDPOINTS[@]}"; do
  START_MS=$(date +%s%N)
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    "$API_BASE$ep" 2>/dev/null || echo "000")
  END_MS=$(date +%s%N)
  DURATION=$(( (END_MS - START_MS) / 1000000 ))

  printf "%-35s | %s    | %s\n" "$ep" "$HTTP_CODE" "${DURATION}" >> "$PERF"

  # AXE 5 : log si erreur
  if [[ "$HTTP_CODE" != "200" && "$HTTP_CODE" != "201" ]]; then
    echo "[$(date '+%H:%M:%S')] ERREUR $HTTP_CODE sur $ep" >> "$LOGS"
  fi

  # AXE 2 : alerte perf si > 500ms
  if [ "$DURATION" -gt 500 ]; then
    echo "[$(date '+%H:%M:%S')] LENT ($DURATION ms) : $ep" >> "$PERF"
  fi
done

# --- AXE 3 : Parasitages — Vérifier les appels inattendus dans les logs API ---
echo "" >> "$PARASITES"
echo "[$(date '+%H:%M:%S')] Analyse des logs API (30 dernières secondes)..." >> "$PARASITES"
docker compose -f "/home/ruuuzer/Documents/FUTUR PROJ/docker-compose.yml" logs --since=30s api 2>/dev/null | \
  grep -E "(ERROR|WARNING|CRITICAL|duplicate|retry|timeout)" >> "$PARASITES" 2>/dev/null || \
  echo "[OK] Aucun parasitage détecté dans les logs API" >> "$PARASITES"

echo "" >> "$PARASITES"
echo "[$(date '+%H:%M:%S')] Requêtes en double (même endpoint < 1s)..." >> "$PARASITES"
docker compose -f "/home/ruuuzer/Documents/FUTUR PROJ/docker-compose.yml" logs --since=60s api 2>/dev/null | \
  grep -oP 'GET /api/v1/\S+|POST /api/v1/\S+|PUT /api/v1/\S+|DELETE /api/v1/\S+' | \
  sort | uniq -c | sort -rn | head -20 >> "$PARASITES" 2>/dev/null || true

# --- AXE 4 : Cohérence backend — compter les réservations via API ---
echo "" >> "$COHERENCE"
echo "[$(date '+%H:%M:%S')] Vérification cohérence données..." >> "$COHERENCE"

if [ "$TOKEN" != "no-token" ]; then
  # Compter réservations
  RES_COUNT=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "$API_BASE/api/v1/reservations?page=1&per_page=1" 2>/dev/null | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',d.get('count','?')))" 2>/dev/null || echo "?")
  echo "  Réservations (API) : $RES_COUNT" >> "$COHERENCE"

  # Compter produits
  PROD_COUNT=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "$API_BASE/api/v1/products?page=1&per_page=1" 2>/dev/null | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',d.get('count','?')))" 2>/dev/null || echo "?")
  echo "  Produits (API)     : $PROD_COUNT" >> "$COHERENCE"

  # Compter clients
  CUST_COUNT=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "$API_BASE/api/v1/customers?page=1&per_page=1" 2>/dev/null | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',d.get('count','?')))" 2>/dev/null || echo "?")
  echo "  Clients (API)      : $CUST_COUNT" >> "$COHERENCE"

  # Compter factures
  INV_COUNT=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "$API_BASE/api/v1/invoices?page=1&per_page=1" 2>/dev/null | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',d.get('count','?')))" 2>/dev/null || echo "?")
  echo "  Factures (API)     : $INV_COUNT" >> "$COHERENCE"
fi

# --- AXE 5 : Logs erreurs et activités — Redis, Celery, DB ---
echo "" >> "$LOGS"
echo "[$(date '+%H:%M:%S')] === Logs services (60s) ===" >> "$LOGS"

echo "" >> "$LOGS"
echo "--- Redis SEC ---" >> "$LOGS"
docker compose -f "/home/ruuuzer/Documents/FUTUR PROJ/docker-compose.yml" logs --since=60s redis_sec 2>/dev/null | tail -5 >> "$LOGS" 2>/dev/null || true

echo "" >> "$LOGS"
echo "--- Redis CACHE ---" >> "$LOGS"
docker compose -f "/home/ruuuzer/Documents/FUTUR PROJ/docker-compose.yml" logs --since=60s redis_cache 2>/dev/null | tail -5 >> "$LOGS" 2>/dev/null || true

echo "" >> "$LOGS"
echo "--- Celery Worker ---" >> "$LOGS"
docker compose -f "/home/ruuuzer/Documents/FUTUR PROJ/docker-compose.yml" logs --since=60s celery_worker 2>/dev/null | tail -10 >> "$LOGS" 2>/dev/null || true

echo "" >> "$LOGS"
echo "--- Celery Beat ---" >> "$LOGS"
docker compose -f "/home/ruuuzer/Documents/FUTUR PROJ/docker-compose.yml" logs --since=60s celery_beat 2>/dev/null | tail -5 >> "$LOGS" 2>/dev/null || true

echo "" >> "$LOGS"
echo "--- DB (PostgreSQL) ---" >> "$LOGS"
docker compose -f "/home/ruuuzer/Documents/FUTUR PROJ/docker-compose.yml" logs --since=60s db 2>/dev/null | \
  grep -iE "(error|fatal|warn|slow)" >> "$LOGS" 2>/dev/null || \
  echo "[OK] Aucune erreur DB" >> "$LOGS"

# --- Résumé ---
echo "Session    : $SESSION" >> "$SUMMARY"
echo "Date       : $(date '+%Y-%m-%d %H:%M:%S')" >> "$SUMMARY"
echo "Token auth : $([ "$TOKEN" != "no-token" ] && echo 'OK' || echo 'ECHEC')" >> "$SUMMARY"
echo "" >> "$SUMMARY"
echo "Fichiers générés :" >> "$SUMMARY"
echo "  1_trace_execution.txt       — Trace d'exécution complète" >> "$SUMMARY"
echo "  2_temps_execution.txt       — Temps de réponse par endpoint" >> "$SUMMARY"
echo "  3_parasitages_appels.txt    — Appels parasites/doublons" >> "$SUMMARY"
echo "  4_coherence_backend_frontend.txt — Compteurs données" >> "$SUMMARY"
echo "  5_logs_erreurs_activites.txt — Logs erreurs tous services" >> "$SUMMARY"

echo ""
echo "=== Monitoring terminé ==="
echo "Résultats dans : $DIR"
ls -la "$DIR"
