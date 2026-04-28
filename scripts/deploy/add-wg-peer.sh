#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# Ajouter un peer WireGuard (un local = un peer)
#
# Usage : ./add-wg-peer.sh <NOM_LOCAL> <IP_PEER>
#   Exemple : ./add-wg-peer.sh marveline 10.0.0.2
#             ./add-wg-peer.sh epicerie 10.0.0.3
#             ./add-wg-peer.sh restaurant 10.0.0.4
#
# Exécuter sur le VPS. Génère :
#   - La config client à copier sur le PC/routeur du local
#   - Ajoute le peer au serveur WireGuard
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <NOM_LOCAL> <IP_PEER>"
  echo "  Ex: $0 marveline 10.0.0.2"
  exit 1
fi

NAME="$1"
PEER_IP="$2"
SERVER_PUBLIC=$(cat /etc/wireguard/server_public.key)
VPS_IP=$(curl -s ifconfig.me)

# Générer les clés du peer
PEER_PRIVATE=$(wg genkey)
PEER_PUBLIC=$(echo "$PEER_PRIVATE" | wg pubkey)

echo ""
echo "═══ Peer '${NAME}' (${PEER_IP}) ═══"
echo ""

# Ajouter au serveur
cat >> /etc/wireguard/wg0.conf << PEEREOF

# ── Peer : ${NAME} ──
[Peer]
PublicKey = ${PEER_PUBLIC}
AllowedIPs = ${PEER_IP}/32
PEEREOF

# Recharger WireGuard
wg syncconf wg0 <(wg-quick strip wg0)

echo "✅ Peer ajouté au serveur WireGuard"
echo ""
echo "═══ Config client — à installer sur le PC/routeur du local '${NAME}' ═══"
echo ""
echo "Fichier : /etc/wireguard/wg0.conf (sur le PC du local)"
echo "────────────────────────────────────────────────────────"

cat << CLIENTEOF
[Interface]
PrivateKey = ${PEER_PRIVATE}
Address = ${PEER_IP}/24
DNS = 1.1.1.1

[Peer]
PublicKey = ${SERVER_PUBLIC}
Endpoint = ${VPS_IP}:51820
AllowedIPs = 10.0.0.0/24
PersistentKeepalive = 25
CLIENTEOF

echo "────────────────────────────────────────────────────────"
echo ""
echo "Sur le PC du local, installer WireGuard puis :"
echo "  sudo wg-quick up wg0"
echo ""
echo "Tester : ping 10.0.0.1 (depuis le local → VPS)"
