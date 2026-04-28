# Infra — Backup & Restore

## Stratégie

| Type | Fréquence | Rétention | Stockage |
|---|---|---|---|
| Full backup | Quotidien (2h) | 30 jours | S3 chiffré |
| WAL archives | Continu | 7 jours | S3 chiffré |
| Snapshot Redis | Toutes les 6h | 7 jours | S3 chiffré |

## RTO / RPO

- **RPO (Recovery Point Objective)** : < 1 heure (WAL archives continues)
- **RTO (Recovery Time Objective)** : < 4 heures

## Backup PostgreSQL

```bash
#!/bin/bash
# scripts/backup/backup_postgres.sh

set -euo pipefail

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="marveline_backup_${DATE}.dump"
S3_BUCKET="s3://marveline-backups/postgres"

# Dump compressé
pg_dump \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --username="${DB_USER}" \
    --dbname="${DB_NAME}" \
    --format=custom \
    --compress=9 \
    --file="/tmp/${BACKUP_FILE}"

# Chiffrement avec age
age --recipient "${AGE_PUBLIC_KEY}" \
    --output "/tmp/${BACKUP_FILE}.age" \
    "/tmp/${BACKUP_FILE}"

# Upload S3
aws s3 cp "/tmp/${BACKUP_FILE}.age" "${S3_BUCKET}/${BACKUP_FILE}.age"

# Vérification de l'upload
aws s3 ls "${S3_BUCKET}/${BACKUP_FILE}.age" || exit 1

# Cleanup local
rm "/tmp/${BACKUP_FILE}" "/tmp/${BACKUP_FILE}.age"

echo "Backup completed: ${BACKUP_FILE}.age"
```

## Restore PostgreSQL

```bash
#!/bin/bash
# scripts/backup/restore_postgres.sh
# USAGE : ./restore_postgres.sh <backup_filename>

set -euo pipefail

BACKUP_FILENAME="${1:?Backup filename required}"
S3_BUCKET="s3://marveline-backups/postgres"

echo "=== RESTORE RUNBOOK ==="
echo "1. Downloading: ${BACKUP_FILENAME}"
aws s3 cp "${S3_BUCKET}/${BACKUP_FILENAME}" "/tmp/${BACKUP_FILENAME}"

echo "2. Decrypting"
age --decrypt \
    --identity "${AGE_PRIVATE_KEY_FILE}" \
    --output "/tmp/restore.dump" \
    "/tmp/${BACKUP_FILENAME}"

echo "3. CONFIRMATION REQUIRED"
echo "   Target: ${DB_HOST}/${DB_NAME}"
read -p "   Type 'RESTORE' to proceed: " confirm
[ "${confirm}" = "RESTORE" ] || exit 1

echo "4. Stopping application (optional — put in maintenance mode)"
# curl -X POST https://api.marveline.com/admin/maintenance/enable

echo "5. Restoring database"
pg_restore \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --username="${DB_USER}" \
    --dbname="${DB_NAME}" \
    --clean \
    --if-exists \
    --no-privileges \
    "/tmp/restore.dump"

echo "6. Running post-restore checks"
psql "${DATABASE_URL}" -c "SELECT COUNT(*) FROM users;" || exit 1
psql "${DATABASE_URL}" -c "SELECT COUNT(*) FROM invoices;" || exit 1

echo "7. Re-enabling application"
# curl -X POST https://api.marveline.com/admin/maintenance/disable

echo "=== RESTORE COMPLETED ==="
rm "/tmp/${BACKUP_FILENAME}" "/tmp/restore.dump"
```

## Test de Restore (Mensuel)

```bash
#!/bin/bash
# scripts/backup/test_restore.sh
# À exécuter mensuellement pour valider le processus de restore

set -euo pipefail

# Récupérer le dernier backup
LATEST=$(aws s3 ls s3://marveline-backups/postgres/ | sort | tail -1 | awk '{print $4}')

# Restore dans un environnement temporaire (pas la production)
TEMP_DB="marveline_restore_test_$(date +%s)"
createdb "${TEMP_DB}"

./restore_postgres.sh "${LATEST}" "${TEMP_DB}"

# Vérifications
psql "${TEMP_DB}" -c "SELECT COUNT(*) FROM users WHERE is_active = TRUE;"
psql "${TEMP_DB}" -c "SELECT MAX(created_at) FROM reservations;"

# Cleanup
dropdb "${TEMP_DB}"
echo "Restore test passed: ${LATEST}"
```

## Celery Task (Backup Automatique)

```python
@celery_app.task
def scheduled_backup():
    """Tâche quotidienne à 2h du matin"""
    import subprocess
    result = subprocess.run(
        ["/app/scripts/backup/backup_postgres.sh"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.critical("Backup failed: %s", result.stderr)
        sentry_sdk.capture_message("CRITICAL: Database backup failed", level="critical")
    else:
        logger.info("Backup completed: %s", result.stdout)
```

## Règles

- Backup testé mensuellement (test-restore)
- Backup chiffré avant upload S3
- Alerte critique si backup échoue
- Jamais de restore direct en production sans double confirmation
- WAL archives pour recovery point-in-time
- Documenter l'heure du dernier backup réussi dans un fichier healthcheck
