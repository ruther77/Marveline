#!/usr/bin/env bash
# ============================================================================
# setup-synology.sh — Configurer le Synology DS220+ pour Marveline
#
# Pre-requis DSM :
#   - DSM 7.0+ installe
#   - SSH active (Panneau de config → Terminal & SNMP → Activer SSH)
#   - Container Manager installe (Centre de paquets)
#
# Usage :
#   ssh admin@<SYNOLOGY_IP> 'sudo bash -s' < deploy/setup-synology.sh
#
# Ce script :
#   1. Verifie les pre-requis (DSM 7, Docker, WireGuard)
#   2. Installe WireGuard si necessaire
#   3. Configure WireGuard client
#   4. Prepare le dossier projet
#   5. Genere les cles JWT RSA
#   6. Genere les secrets prod
# ============================================================================

set -euo pipefail

PROJECT_DIR="/volume1/docker/marveline"

echo "=== [1/6] Verification pre-requis ==="

# DSM version
DSM_VERSION=$(cat /etc.defaults/VERSION 2>/dev/null | grep -oP 'majorversion="\K[0-9]+' || echo "?")
echo "  DSM major version: ${DSM_VERSION}"
if [ "$DSM_VERSION" -lt 7 ] 2>/dev/null; then
    echo "  ERREUR: DSM 7+ requis. Version actuelle: ${DSM_VERSION}"
    exit 1
fi

# Docker
if command -v docker &>/dev/null; then
    DOCKER_VERSION=$(docker --version 2>/dev/null || echo "?")
    echo "  Docker: ${DOCKER_VERSION}"
else
    echo "  ERREUR: Docker non trouve. Installer 'Container Manager' dans le Centre de paquets DSM."
    exit 1
fi

# Docker Compose
if docker compose version &>/dev/null; then
    echo "  Docker Compose: $(docker compose version --short)"
else
    echo "  ERREUR: Docker Compose non disponible."
    exit 1
fi

echo "  Pre-requis OK."

echo ""
echo "=== [2/6] WireGuard ==="

# Sur Synology DSM 7, le module WireGuard est integre au kernel
if ! command -v wg &>/dev/null; then
    echo "  WireGuard CLI non trouve."
    echo "  Sur DSM 7.2+ : installer le paquet WireGuard depuis le Centre de paquets"
    echo "  ou via SynoCommunity (https://synocommunity.com)."
    echo ""
    echo "  Alternative : installer manuellement le module kernel :"
    echo "    https://github.com/runfalk/synology-wireguard"
    echo ""
    echo "  Continuer sans WireGuard ? (le tunnel devra etre configure manuellement)"
    # On continue quand meme pour preparer le reste
fi

echo ""
echo "=== [3/6] Dossier projet ==="
mkdir -p "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}/keys"
mkdir -p "${PROJECT_DIR}/uploads"
mkdir -p "${PROJECT_DIR}/backups"
echo "  Cree: ${PROJECT_DIR}"

echo ""
echo "=== [4/6] Generation cles JWT RSA 4096 ==="
if [ ! -f "${PROJECT_DIR}/keys/jwt_access_private.pem" ]; then
    openssl genrsa -out "${PROJECT_DIR}/keys/jwt_access_private.pem" 4096 2>/dev/null
    openssl rsa -in "${PROJECT_DIR}/keys/jwt_access_private.pem" -pubout -out "${PROJECT_DIR}/keys/jwt_access_public.pem" 2>/dev/null
    echo "  Access token keys: OK"
else
    echo "  Access token keys: deja presentes (skip)"
fi

if [ ! -f "${PROJECT_DIR}/keys/jwt_refresh_private.pem" ]; then
    openssl genrsa -out "${PROJECT_DIR}/keys/jwt_refresh_private.pem" 4096 2>/dev/null
    openssl rsa -in "${PROJECT_DIR}/keys/jwt_refresh_private.pem" -pubout -out "${PROJECT_DIR}/keys/jwt_refresh_public.pem" 2>/dev/null
    echo "  Refresh token keys: OK"
else
    echo "  Refresh token keys: deja presentes (skip)"
fi

chmod 600 "${PROJECT_DIR}/keys/"*.pem

echo ""
echo "=== [5/6] Generation secrets prod ==="

gen_secret() {
    openssl rand -hex "$1"
}

ENV_FILE="${PROJECT_DIR}/.env.prod"
if [ ! -f "${ENV_FILE}" ]; then
    cat > "${ENV_FILE}" << ENVEOF
# ============================================================================
# .env.prod — Secrets production Marveline
# Genere le $(date -I)
# NE PAS COMMITTER CE FICHIER
# ============================================================================

# ── Domaine (a remplacer) ──────────────────────────────────────────────────
APP_DOMAIN=app.VOTREDOMAINE.fr

# ── Base de donnees ────────────────────────────────────────────────────────
DB_PASSWORD=$(gen_secret 32)

# ── Redis ──────────────────────────────────────────────────────────────────
REDIS_SEC_PASSWORD=$(gen_secret 24)
REDIS_CACHE_PASSWORD=$(gen_secret 24)

# ── Securite ───────────────────────────────────────────────────────────────
PASSWORD_PEPPER=$(gen_secret 32)
ENCRYPTION_KEY=$(gen_secret 32)
TOTP_DEV_MASTER_KEY=$(gen_secret 32)
AUDIT_HMAC_KEY=$(gen_secret 32)

# ── JWT RS256 ──────────────────────────────────────────────────────────────
JWT_ALGORITHM=RS256
JWT_ACCESS_PRIVATE_KEY_PATH=keys/jwt_access_private.pem
JWT_ACCESS_PUBLIC_KEY_PATH=keys/jwt_access_public.pem
JWT_REFRESH_PRIVATE_KEY_PATH=keys/jwt_refresh_private.pem
JWT_REFRESH_PUBLIC_KEY_PATH=keys/jwt_refresh_public.pem
JWT_ACCESS_TOKEN_EXPIRE_SECONDS=900
JWT_REFRESH_TOKEN_EXPIRE_SECONDS=604800

# ── SMTP (a configurer) ───────────────────────────────────────────────────
SMTP_HOST=smtp.VOTREFOURNISSEUR.fr
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
ENVEOF

    chmod 600 "${ENV_FILE}"
    echo "  .env.prod genere avec secrets uniques"
else
    echo "  .env.prod existe deja (skip)"
fi

echo ""
echo "=== [6/6] Resume ==="
echo ""
echo "============================================"
echo "  SYNOLOGY PREPARE"
echo "============================================"
echo "  Dossier    : ${PROJECT_DIR}"
echo "  Cles JWT   : ${PROJECT_DIR}/keys/ (4 fichiers PEM)"
echo "  Secrets    : ${PROJECT_DIR}/.env.prod"
echo ""
echo "  PROCHAINES ETAPES :"
echo "  1. Editer .env.prod : remplacer APP_DOMAIN et SMTP"
echo "  2. Configurer WireGuard client :"
echo "     sudo nano /etc/wireguard/wg0.conf"
echo "     sudo wg-quick up wg0"
echo "     ping 10.0.0.1"
echo "  3. Copier les sources du projet dans ${PROJECT_DIR}"
echo "  4. Builder et demarrer :"
echo "     cd ${PROJECT_DIR}"
echo "     docker compose -f docker-compose.synology.yml --env-file .env.prod up -d --build"
echo "============================================"
