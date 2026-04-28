#!/usr/bin/env bash
# ============================================================================
# backup-db.sh — Backup PostgreSQL sur le Synology
#
# Usage :
#   ./deploy/backup-db.sh
#
# Ajouter en cron (DSM → Panneau de config → Planificateur de taches) :
#   Tous les jours a 03:00
#   /volume1/docker/marveline/deploy/backup-db.sh
# ============================================================================

set -euo pipefail

PROJECT_DIR="/volume1/docker/marveline"
BACKUP_DIR="${PROJECT_DIR}/backups"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M)
BACKUP_FILE="${BACKUP_DIR}/marveline_${DATE}.sql.gz"

mkdir -p "${BACKUP_DIR}"

# Dump via le container db
docker compose -f "${PROJECT_DIR}/docker-compose.synology.yml" \
    exec -T db pg_dump -U caro -d CaroCorp --no-owner --no-acl \
    | gzip > "${BACKUP_FILE}"

SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[$(date -I)] Backup OK: ${BACKUP_FILE} (${SIZE})"

# Rotation
find "${BACKUP_DIR}" -name "marveline_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
REMAINING=$(find "${BACKUP_DIR}" -name "marveline_*.sql.gz" | wc -l)
echo "[$(date -I)] Backups conserves: ${REMAINING}"
