#!/usr/bin/env bash
# run_demo.sh — Pipeline tout-en-un pour la démo Marveline Mobile
#
# Usage :
#   ./scripts/demo/run_demo.sh
#
# Pré-requis :
#   - Docker en cours d'exécution (docker compose)
#   - ffmpeg installé sur la machine hôte (brew install ffmpeg / apt install ffmpeg)
#   - Node.js + npm/npx disponibles
#
# Produit : frontend/demo-output/demo-marveline-YYYYMMDD.mp4

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
DATE_STAMP=$(date +%Y%m%d)
OUTPUT_MP4="${FRONTEND_DIR}/demo-output/demo-marveline-${DATE_STAMP}.mp4"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║      Marveline Demo — Pipeline Complet       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── 1. Vérifier que Docker est en cours ───────────────────────────────────────
echo "▶ Étape 1/5 — Vérification Docker..."
cd "${PROJECT_ROOT}"

if ! docker compose ps | grep -q "api.*running\|api.*Up"; then
    echo "  → Démarrage des services Docker..."
    docker compose up -d
else
    echo "  → Services Docker déjà en cours."
fi

# ── 2. Attendre le healthcheck API (max 60s) ──────────────────────────────────
echo ""
echo "▶ Étape 2/5 — Attente healthcheck API..."
MAX_WAIT=60
WAITED=0
until docker compose exec -T api python -c "import sys; sys.exit(0)" 2>/dev/null; do
    if [ "${WAITED}" -ge "${MAX_WAIT}" ]; then
        echo "  ✗ API non disponible après ${MAX_WAIT}s. Vérifier : docker compose logs api"
        exit 1
    fi
    echo "  → Attente API... (${WAITED}s)"
    sleep 5
    WAITED=$((WAITED + 5))
done
echo "  → API disponible."

# Pause supplémentaire pour que les migrations soient terminées
sleep 3

# ── 3. Seed données démo (idempotent) ─────────────────────────────────────────
echo ""
echo "▶ Étape 3/5 — Seed données démo..."
docker compose exec -T api python scripts/demo/seed_marveline_demo.py

# ── 4. Installer webkit Playwright si nécessaire ──────────────────────────────
echo ""
echo "▶ Étape 4/5 — Playwright webkit..."
cd "${FRONTEND_DIR}"

if ! npx playwright --version &>/dev/null; then
    echo "  → Installation de Playwright..."
    npm install --save-dev @playwright/test
fi

echo "  → Installation du browser webkit (iPhone Safari)..."
npx playwright install webkit --with-deps 2>/dev/null || true
echo "  → webkit prêt."

# ── 5. Enregistrement Playwright ──────────────────────────────────────────────
echo ""
echo "▶ Étape 5a/5 — Enregistrement démo (vue iPhone 14 Pro)..."
mkdir -p "${FRONTEND_DIR}/demo-output"

npx playwright test \
    --config=playwright.demo.config.ts \
    --reporter=list \
    2>&1 | tee "${FRONTEND_DIR}/demo-output/playwright-run-${DATE_STAMP}.log"

# ── 6. Conversion WebM → MP4 ──────────────────────────────────────────────────
echo ""
echo "▶ Étape 5b/5 — Conversion WebM → MP4..."

WEBM_FILE=$(find "${FRONTEND_DIR}/demo-output" -name "*.webm" -newer "${FRONTEND_DIR}/demo-output/playwright-run-${DATE_STAMP}.log" 2>/dev/null | head -1)

if [ -z "${WEBM_FILE}" ]; then
    # Fallback : prendre le WebM le plus récent
    WEBM_FILE=$(find "${FRONTEND_DIR}/demo-output" -name "*.webm" | sort -t'-' -k1 -r | head -1)
fi

if [ -z "${WEBM_FILE}" ]; then
    echo "  ✗ Aucun fichier .webm trouvé dans demo-output/."
    echo "    Vérifier que le test s'est exécuté correctement."
    exit 1
fi

echo "  → Source : ${WEBM_FILE}"
echo "  → Destination : ${OUTPUT_MP4}"

if ! command -v ffmpeg &>/dev/null; then
    echo ""
    echo "  ⚠  ffmpeg non trouvé. Installez-le :"
    echo "     macOS : brew install ffmpeg"
    echo "     Ubuntu : sudo apt install ffmpeg"
    echo ""
    echo "  Le fichier .webm est disponible : ${WEBM_FILE}"
    exit 0
fi

ffmpeg -y \
    -i "${WEBM_FILE}" \
    -c:v libx264 \
    -preset slow \
    -crf 20 \
    -c:a aac \
    -b:a 128k \
    -movflags +faststart \
    "${OUTPUT_MP4}"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║              ✓ Démo générée !                ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Fichier MP4 : ${OUTPUT_MP4}"
echo "  Durée cible : 2 min 15 — 2 min 45"
echo ""
echo "  Ouvrir : xdg-open '${OUTPUT_MP4}' (Linux)"
echo "           open '${OUTPUT_MP4}' (macOS)"
echo ""
