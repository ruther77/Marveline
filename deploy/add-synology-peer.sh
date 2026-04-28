#!/usr/bin/env bash
# ============================================================================
# add-synology-peer.sh — Ajouter le Synology DS220+ comme peer WireGuard
#
# A executer sur le VPS apres setup-vps-relay.sh
#
# Usage :
#   ssh root@<VPS_IP> 'bash -s' < deploy/add-synology-peer.sh
# ============================================================================

set -euo pipefail

PEER_NAME="synology"
PEER_IP="10.0.0.2"

echo "=== Generation cles peer Synology ==="
PEER_PRIVKEY=$(wg genkey)
PEER_PUBKEY=$(echo "$PEER_PRIVKEY" | wg pubkey)
SERVER_PUBKEY=$(cat /etc/wireguard/server_public.key)
VPS_IP=$(curl -s4 ifconfig.me)

echo "=== Ajout peer a la config WG serveur ==="
cat >> /etc/wireguard/wg0.conf << PEEREOF

# Peer : Synology DS220+ (${PEER_NAME})
[Peer]
PublicKey = ${PEER_PUBKEY}
AllowedIPs = ${PEER_IP}/32
PersistentKeepalive = 25
PEEREOF

# Recharger WG sans couper les connexions existantes
wg syncconf wg0 <(wg-quick strip wg0)

echo ""
echo "============================================"
echo "  PEER SYNOLOGY AJOUTE"
echo "============================================"
echo ""
echo "  Copier cette config sur le Synology"
echo "  (fichier /etc/wireguard/wg0.conf) :"
echo ""
echo "------- DEBUT CONFIG CLIENT -------"
cat << CLIENTEOF
[Interface]
PrivateKey = ${PEER_PRIVKEY}
Address = ${PEER_IP}/24
DNS = 1.1.1.1

[Peer]
PublicKey = ${SERVER_PUBKEY}
Endpoint = ${VPS_IP}:51820
AllowedIPs = 10.0.0.0/24
PersistentKeepalive = 25
CLIENTEOF
echo "------- FIN CONFIG CLIENT -------"
echo ""
echo "  Sur le Synology (SSH) :"
echo "    1. sudo mkdir -p /etc/wireguard"
echo "    2. sudo nano /etc/wireguard/wg0.conf  (coller la config ci-dessus)"
echo "    3. sudo chmod 600 /etc/wireguard/wg0.conf"
echo "    4. sudo wg-quick up wg0"
echo "    5. ping 10.0.0.1  (doit repondre)"
echo ""
echo "============================================"
