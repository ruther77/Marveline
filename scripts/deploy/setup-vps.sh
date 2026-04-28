#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# Setup VPS OVH — CaroCorp (Marveline + MassaCorp)
#
# Prérequis : Ubuntu 24.04 LTS, accès root SSH
# Usage : ssh root@<IP_VPS> 'bash -s' < scripts/deploy/setup-vps.sh
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

echo "═══ 1. Mise à jour système ═══"
apt-get update && apt-get upgrade -y
apt-get install -y \
  curl wget git ufw fail2ban \
  ca-certificates gnupg lsb-release

echo "═══ 2. Docker ═══"
# Docker officiel (pas snap)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Docker sans sudo pour l'utilisateur deploy
useradd -m -s /bin/bash -G docker deploy || true
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy

echo "═══ 3. Firewall (UFW) ═══"
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh          # 22
ufw allow 80/tcp       # HTTP
ufw allow 443/tcp      # HTTPS
ufw allow 51820/udp    # WireGuard
ufw --force enable

echo "═══ 4. Fail2ban ═══"
systemctl enable fail2ban
systemctl start fail2ban

echo "═══ 5. WireGuard ═══"
apt-get install -y wireguard

# Générer les clés serveur
wg genkey | tee /etc/wireguard/server_private.key | wg pubkey > /etc/wireguard/server_public.key
chmod 600 /etc/wireguard/server_private.key

SERVER_PRIVATE=$(cat /etc/wireguard/server_private.key)
SERVER_PUBLIC=$(cat /etc/wireguard/server_public.key)

cat > /etc/wireguard/wg0.conf << WGEOF
[Interface]
Address = 10.0.0.1/24
ListenPort = 51820
PrivateKey = ${SERVER_PRIVATE}

# PostUp/PostDown pour le NAT (accès internet depuis les peers)
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

# ── Peer 1 : Local Marveline ──
# [Peer]
# PublicKey = <CLÉ_PUBLIQUE_LOCAL_1>
# AllowedIPs = 10.0.0.2/32

# ── Peer 2 : Local Épicerie ──
# [Peer]
# PublicKey = <CLÉ_PUBLIQUE_LOCAL_2>
# AllowedIPs = 10.0.0.3/32

# ── Peer 3 : Local Restaurant ──
# [Peer]
# PublicKey = <CLÉ_PUBLIQUE_LOCAL_3>
# AllowedIPs = 10.0.0.4/32
WGEOF

# Activer le forwarding IP
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p

systemctl enable wg-quick@wg0
systemctl start wg-quick@wg0

echo "═══ 6. Certbot (Let's Encrypt) ═══"
apt-get install -y certbot
# Les certificats seront générés après le DNS (voir setup-tls.sh)

echo "═══ 7. Backup cron (pg_dump quotidien) ═══"
mkdir -p /opt/backups
cat > /etc/cron.d/carocorp-backup << 'CRONEOF'
# pg_dump quotidien à 3h du matin
0 3 * * * deploy docker compose -f /opt/carocorp/docker-compose.prod.yml exec -T db pg_dump -U caro CaroCorp | gzip > /opt/backups/carocorp_$(date +\%Y\%m\%d).sql.gz
# Rotation : garder 30 jours
0 4 * * * deploy find /opt/backups -name "carocorp_*.sql.gz" -mtime +30 -delete
CRONEOF

echo "═══ 8. Dossier projet ═══"
mkdir -p /opt/carocorp
chown deploy:deploy /opt/carocorp

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  VPS configuré !"
echo ""
echo "  WireGuard server public key : ${SERVER_PUBLIC}"
echo "  WireGuard IP serveur        : 10.0.0.1"
echo "  WireGuard port              : 51820"
echo ""
echo "  Prochaines étapes :"
echo "    1. Configurer DNS : marveline.fr + massacorp.fr → $(curl -s ifconfig.me)"
echo "    2. Copier le code : scp -r . deploy@$(curl -s ifconfig.me):/opt/carocorp/"
echo "    3. Créer .env prod : /opt/carocorp/.env"
echo "    4. Lancer : cd /opt/carocorp && docker compose -f docker-compose.prod.yml up -d"
echo "    5. Certbot : certbot certonly --standalone -d marveline.fr -d massacorp.fr"
echo "    6. Ajouter peers WireGuard (un par local)"
echo "═══════════════════════════════════════════════════════"
