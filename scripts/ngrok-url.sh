#!/usr/bin/env bash
# Affiche l'URL publique du tunnel ngrok.
# Usage : ./scripts/ngrok-url.sh
#         make ngrok-url

set -euo pipefail

# Domaine statique configuré → URL immédiate sans appel API
DOMAIN="${NGROK_DOMAIN:-}"
if [ -n "$DOMAIN" ]; then
  echo "https://$DOMAIN"
  exit 0
fi

URL=$(curl -sf http://localhost:4040/api/tunnels \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
tunnels = data.get('tunnels', [])
https_urls = [t['public_url'] for t in tunnels if t.get('public_url','').startswith('https')]
print(https_urls[0] if https_urls else (tunnels[0]['public_url'] if tunnels else ''))
" 2>/dev/null || true)

if [ -z "$URL" ]; then
  echo "ngrok n'est pas actif. Lancer : docker compose --profile tunnel up ngrok -d" >&2
  exit 1
fi

echo "$URL"
