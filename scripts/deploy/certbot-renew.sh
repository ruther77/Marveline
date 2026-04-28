#!/bin/bash
# Script de renouvellement certbot + rechargement nginx
# À exécuter via cron : 0 */12 * * * /path/to/certbot-renew.sh >> /var/log/certbot-renew.log 2>&1
#
# Ce script remplace la boucle interne du conteneur certbot
# car le conteneur certbot ne peut pas signaler nginx pour recharger les certs.

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

echo "$LOG_PREFIX Début du renouvellement certbot..."

# Tenter le renouvellement
docker compose -f "$COMPOSE_FILE" run --rm certbot renew --quiet

# Recharger nginx pour prendre en compte les éventuels nouveaux certs
docker compose -f "$COMPOSE_FILE" exec -T nginx nginx -s reload

echo "$LOG_PREFIX Renouvellement terminé, nginx rechargé."
