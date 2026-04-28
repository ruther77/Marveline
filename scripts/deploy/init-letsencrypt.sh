#!/bin/bash
# Initialisation Let's Encrypt pour marveline.fr et massacorp.fr
# Usage: ./scripts/deploy/init-letsencrypt.sh [--staging]
#
# Prérequis :
#   - DNS A records pointant vers le VPS pour les 4 domaines
#   - Ports 80 et 443 ouverts
#   - docker compose fonctionnel
#   - Variable LETSENCRYPT_EMAIL définie

set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
DOMAINS_MARVELINE=("marveline.fr" "www.marveline.fr")
DOMAINS_MASSACORP=("massacorp.fr" "www.massacorp.fr")
EMAIL="${LETSENCRYPT_EMAIL:?Variable LETSENCRYPT_EMAIL requise (ex: export LETSENCRYPT_EMAIL=contact@marveline.fr)}"
RSA_KEY_SIZE=4096
CERTBOT_DIR="./certbot"

# Mode staging pour les tests (rate limit Let's Encrypt)
STAGING_ARG=""
if [[ "${1:-}" == "--staging" ]]; then
    STAGING_ARG="--staging"
    echo "[INFO] Mode staging activé (certificats de test)"
fi

echo "============================================"
echo " Init Let's Encrypt — CaroCorp Production"
echo " Email: $EMAIL"
echo "============================================"

# 1. Créer les répertoires certbot
echo "[1/6] Création des répertoires certbot..."
mkdir -p "$CERTBOT_DIR/conf"
mkdir -p "$CERTBOT_DIR/www"

# 2. Télécharger les params SSL recommandés par certbot
echo "[2/6] Téléchargement des paramètres SSL..."
if [ ! -f "$CERTBOT_DIR/conf/options-ssl-nginx.conf" ]; then
    curl -sf https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf \
        -o "$CERTBOT_DIR/conf/options-ssl-nginx.conf"
fi
if [ ! -f "$CERTBOT_DIR/conf/ssl-dhparams.pem" ]; then
    curl -sf https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem \
        -o "$CERTBOT_DIR/conf/ssl-dhparams.pem"
fi

# 3. Créer des certificats auto-signés temporaires (pour que nginx démarre)
echo "[3/6] Création des certificats temporaires..."
for domain in marveline.fr massacorp.fr; do
    cert_path="$CERTBOT_DIR/conf/live/$domain"
    if [ ! -f "$cert_path/fullchain.pem" ]; then
        mkdir -p "$cert_path"
        openssl req -x509 -nodes -newkey rsa:$RSA_KEY_SIZE \
            -days 1 \
            -keyout "$cert_path/privkey.pem" \
            -out "$cert_path/fullchain.pem" \
            -subj "/CN=$domain" 2>/dev/null
        cp "$cert_path/fullchain.pem" "$cert_path/chain.pem"
        echo "  → Certificat temporaire créé pour $domain"
    else
        echo "  → Certificat déjà existant pour $domain (skip)"
    fi
done

# 4. Démarrer nginx avec les certificats temporaires
echo "[4/6] Démarrage de nginx..."
docker compose -f "$COMPOSE_FILE" up -d nginx

echo "  → Attente que nginx soit prêt..."
TIMEOUT=30
ELAPSED=0
while ! docker compose -f "$COMPOSE_FILE" ps --format json nginx 2>/dev/null | grep -q '"running"'; do
    sleep 1
    ELAPSED=$((ELAPSED + 1))
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "[ERREUR] Nginx n'a pas démarré en ${TIMEOUT}s. Logs :"
        docker compose -f "$COMPOSE_FILE" logs nginx --tail=20
        exit 1
    fi
done
echo "  → Nginx démarré (${ELAPSED}s)"

# 5. Obtenir les vrais certificats Let's Encrypt
echo "[5/6] Obtention des certificats Let's Encrypt..."

# marveline.fr
echo "  → marveline.fr..."
domain_args_marv=()
for d in "${DOMAINS_MARVELINE[@]}"; do
    domain_args_marv+=("-d" "$d")
done

docker compose -f "$COMPOSE_FILE" run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --keep-until-expiring \
    $STAGING_ARG \
    "${domain_args_marv[@]}"

# massacorp.fr
echo "  → massacorp.fr..."
domain_args_massa=()
for d in "${DOMAINS_MASSACORP[@]}"; do
    domain_args_massa+=("-d" "$d")
done

docker compose -f "$COMPOSE_FILE" run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --keep-until-expiring \
    $STAGING_ARG \
    "${domain_args_massa[@]}"

# 6. Recharger nginx avec les vrais certificats
echo "[6/6] Rechargement de nginx avec les certificats Let's Encrypt..."
docker compose -f "$COMPOSE_FILE" exec nginx nginx -s reload

echo ""
echo "============================================"
echo " TLS configuré avec succès !"
echo ""
echo " marveline.fr  → https://marveline.fr"
echo " massacorp.fr  → https://massacorp.fr"
echo ""
echo " Renouvellement automatique : certbot renew (toutes les 12h)"
echo " Post-renouvellement : exécuter scripts/deploy/certbot-renew.sh"
echo "============================================"
