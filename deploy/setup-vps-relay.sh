#!/usr/bin/env bash
# ============================================================================
# setup-vps-relay.sh — Provision VPS OVH en mode relay-only
#
# Le VPS ne fait que :
#   1. Terminer TLS (Let's Encrypt)
#   2. Forward le trafic vers le Synology via WireGuard
#
# Usage :
#   ssh root@<VPS_IP> 'bash -s' < deploy/setup-vps-relay.sh
#
# Pre-requis :
#   - Ubuntu 22.04 ou 24.04 LTS
#   - DNS A record deja configure : app.sondomaine.fr → IP VPS
# ============================================================================

set -euo pipefail

echo "=== [1/7] Mise a jour systeme ==="
apt-get update -qq && apt-get upgrade -y -qq
apt-get install -y -qq curl gnupg lsb-release ca-certificates ufw fail2ban nginx certbot python3-certbot-nginx wireguard

echo "=== [2/7] Firewall UFW ==="
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp        # SSH
ufw allow 80/tcp        # HTTP (ACME + redirect)
ufw allow 443/tcp       # HTTPS
ufw allow 51820/udp     # WireGuard
ufw --force enable
echo "UFW actif."

echo "=== [3/7] Fail2ban ==="
systemctl enable --now fail2ban

echo "=== [4/7] WireGuard server ==="
# Generer cles serveur
mkdir -p /etc/wireguard
wg genkey | tee /etc/wireguard/server_private.key | wg pubkey > /etc/wireguard/server_public.key
chmod 600 /etc/wireguard/server_private.key

SERVER_PRIVKEY=$(cat /etc/wireguard/server_private.key)
SERVER_PUBKEY=$(cat /etc/wireguard/server_public.key)

# Detecter interface reseau principale
MAIN_IF=$(ip route show default | awk '{print $5}' | head -1)

cat > /etc/wireguard/wg0.conf << WGEOF
[Interface]
PrivateKey = ${SERVER_PRIVKEY}
Address = 10.0.0.1/24
ListenPort = 51820
PostUp = iptables -t nat -A POSTROUTING -o ${MAIN_IF} -j MASQUERADE
PostDown = iptables -t nat -D POSTROUTING -o ${MAIN_IF} -j MASQUERADE

# Peer : Synology DS220+ (a remplir avec add-peer.sh)
# [Peer]
# PublicKey = <SYNOLOGY_PUBLIC_KEY>
# AllowedIPs = 10.0.0.2/32
# PersistentKeepalive = 25
WGEOF

chmod 600 /etc/wireguard/wg0.conf

# IP forwarding
echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-wg-forward.conf
sysctl -p /etc/sysctl.d/99-wg-forward.conf

# Demarrer WireGuard
systemctl enable --now wg-quick@wg0

echo "=== [5/7] Nginx (config placeholder) ==="
# On met une config temporaire, le vrai fichier sera copie ensuite
cat > /etc/nginx/sites-available/marveline-relay << 'NGEOF'
# Placeholder — remplacer par nginx-vps-relay.conf une fois le certificat obtenu
server {
    listen 80 default_server;
    server_name _;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'VPS relay ready. Waiting for TLS setup.';
        add_header Content-Type text/plain;
    }
}
NGEOF

mkdir -p /var/www/certbot
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/marveline-relay /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo "=== [6/7] User deploy ==="
if ! id deploy &>/dev/null; then
    useradd -m -s /bin/bash deploy
    echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy
fi

echo "=== [7/7] Resume ==="
VPS_IP=$(curl -s4 ifconfig.me)
echo ""
echo "============================================"
echo "  VPS RELAY CONFIGURE"
echo "============================================"
echo "  IP publique VPS    : ${VPS_IP}"
echo "  WG server pubkey   : ${SERVER_PUBKEY}"
echo "  WG server IP       : 10.0.0.1/24"
echo "  WG port            : 51820/udp"
echo "  Nginx              : actif (placeholder)"
echo ""
echo "  PROCHAINES ETAPES :"
echo "  1. Ajouter le peer Synology :"
echo "     ./deploy/add-synology-peer.sh"
echo "  2. Obtenir le certificat TLS :"
echo "     certbot --nginx -d app.VOTREDOMAINE.fr"
echo "  3. Copier la config nginx finale :"
echo "     cp nginx-vps-relay.conf /etc/nginx/sites-available/marveline-relay"
echo "     sed -i 's/__APP_DOMAIN__/app.VOTREDOMAINE.fr/g' /etc/nginx/sites-available/marveline-relay"
echo "     nginx -t && systemctl reload nginx"
echo "============================================"
