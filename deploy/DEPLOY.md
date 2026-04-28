# Deploiement Marveline — Synology DS220+ via WireGuard

## Architecture

```
Internet
  |
DNS OVH : app.marveline.fr --> A --> __VPS_IP__
  |
VPS OVH (relay, ~3 EUR/mois)
  |  Nginx (TLS Let's Encrypt)
  |  WireGuard server (10.0.0.1)
  |  Ports : 22, 80, 443, 51820/udp
  |
  |--- WireGuard tunnel (chiffre) ---|
                                     |
Synology DS220+ (chez la cliente)
  |  WireGuard client (10.0.0.2)
  |  Docker Compose :
  |    Nginx local (:8080)
  |    Frontend Marveline
  |    API FastAPI
  |    PostgreSQL 16
  |    Redis SEC + CACHE
  |    Celery worker + beat
  |
  |  DSM admin reste sur :5001
```

## Pre-requis

### Cote cliente (Synology)
- [ ] DSM 7.0 ou superieur
- [ ] SSH active (Panneau de config > Terminal & SNMP)
- [ ] Container Manager installe (Centre de paquets)
- [ ] Nom de domaine OVH connu

### Cote nous
- [ ] Acces SSH au Synology
- [ ] Acces manager OVH (zone DNS)
- [ ] Carte pour commander le VPS (~3 EUR/mois)

---

## Etape 1 — Commander le VPS OVH

1. Aller sur ovhcloud.com > VPS
2. Choisir **VPS Starter** (~3.50 EUR/mois) :
   - 1 vCPU, 2 Go RAM (largement suffisant pour du relay)
   - Ubuntu 24.04 LTS
   - Datacenter : Paris (latence minimale)
3. Noter l'IP publique du VPS : `__VPS_IP__`

---

## Etape 2 — Configurer DNS OVH

1. Manager OVH > Domaines > marveline.fr > Zone DNS
2. Ajouter un enregistrement :
   ```
   Type : A
   Sous-domaine : app
   Cible : __VPS_IP__
   TTL : 3600
   ```
3. Attendre propagation (~5-30 min)
4. Verifier : `dig app.marveline.fr` doit retourner `__VPS_IP__`

---

## Etape 3 — Provisionner le VPS

```bash
# Depuis votre machine locale
ssh root@__VPS_IP__ 'bash -s' < deploy/setup-vps-relay.sh
```

Ce script installe : UFW, fail2ban, WireGuard server, Nginx (placeholder), certbot.

Sortie attendue :
```
  IP publique VPS    : __VPS_IP__
  WG server pubkey   : xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  WG server IP       : 10.0.0.1/24
```

**Noter la cle publique serveur.**

---

## Etape 4 — Ajouter le peer Synology sur le VPS

```bash
ssh root@__VPS_IP__ 'bash -s' < deploy/add-synology-peer.sh
```

Le script genere la config client a copier sur le Synology.
**Copier la config affichee entre les lignes "DEBUT" et "FIN".**

---

## Etape 5 — Configurer le Synology

### 5a. Preparer l'environnement

```bash
ssh admin@__SYNOLOGY_IP__
sudo bash -s < deploy/setup-synology.sh
```

Ce script :
- Verifie DSM 7, Docker, Docker Compose
- Cree `/volume1/docker/marveline/`
- Genere les cles JWT RSA 4096
- Genere `.env.prod` avec secrets uniques

### 5b. Installer WireGuard client

```bash
sudo mkdir -p /etc/wireguard
sudo nano /etc/wireguard/wg0.conf
# Coller la config client de l'etape 4
sudo chmod 600 /etc/wireguard/wg0.conf
sudo wg-quick up wg0
```

Verifier le tunnel :
```bash
ping 10.0.0.1   # Doit repondre (VPS)
```

### 5c. Rendre WG persistant au reboot

Creer une tache planifiee dans DSM :
- Panneau de config > Planificateur de taches > Creer > Script defini par l'utilisateur
- Evenement : Demarrage
- Commande : `wg-quick up wg0`

### 5d. Copier les sources

```bash
# Depuis votre machine locale
rsync -avz --exclude='.git' --exclude='node_modules' --exclude='.venv' \
  . admin@__SYNOLOGY_IP__:/volume1/docker/marveline/
```

### 5e. Editer la config

```bash
ssh admin@__SYNOLOGY_IP__
nano /volume1/docker/marveline/.env.prod
# Remplacer :
#   APP_DOMAIN=app.marveline.fr
#   SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD
```

### 5f. Builder et demarrer

```bash
cd /volume1/docker/marveline
sudo docker compose -f deploy/docker-compose.synology.yml --env-file .env.prod up -d --build
```

Premiere execution : le build peut prendre ~10-15 min (Celeron 2 coeurs).

Verifier :
```bash
sudo docker compose -f deploy/docker-compose.synology.yml ps
# Tous les services doivent etre "healthy"

curl http://localhost:8080/api/v1/health
# {"status":"ok"}
```

---

## Etape 6 — TLS sur le VPS

### 6a. Obtenir le certificat

```bash
ssh root@__VPS_IP__
certbot certonly --webroot -w /var/www/certbot -d app.marveline.fr --non-interactive --agree-tos -m __EMAIL__
```

### 6b. Installer la config nginx finale

```bash
# Copier la config
cp /chemin/vers/nginx-vps-relay.conf /etc/nginx/sites-available/marveline-relay

# Remplacer le placeholder domaine
sed -i 's/__APP_DOMAIN__/app.marveline.fr/g' /etc/nginx/sites-available/marveline-relay

# Tester et recharger
nginx -t && systemctl reload nginx
```

### 6c. Renouvellement automatique

```bash
crontab -e
# Ajouter :
0 */12 * * * certbot renew --quiet && nginx -s reload
```

---

## Etape 7 — Verification finale

Depuis n'importe ou sur internet :

```bash
# HTTPS fonctionne
curl -I https://app.marveline.fr
# HTTP/2 200

# API repond
curl https://app.marveline.fr/api/v1/health
# {"status":"ok"}

# Frontend se charge
curl -s https://app.marveline.fr/ | head -5
# <!DOCTYPE html>...
```

---

## Etape 8 — Seed base de donnees

```bash
ssh admin@__SYNOLOGY_IP__
cd /volume1/docker/marveline

# Creer le tenant + admin
sudo docker compose -f deploy/docker-compose.synology.yml \
  exec api python -c "
from app.core.database import get_sync_engine
from sqlalchemy import text
engine = get_sync_engine()
with engine.begin() as conn:
    # Verifier que les migrations sont OK
    result = conn.execute(text('SELECT count(*) FROM alembic_version'))
    print(f'Migrations: {result.scalar()}')
"

# Lancer les migrations
sudo docker compose -f deploy/docker-compose.synology.yml \
  exec api alembic upgrade head

# Creer le premier admin (script a adapter)
sudo docker compose -f deploy/docker-compose.synology.yml \
  exec api python scripts/create_test_user.py
```

---

## Maintenance

### Backup quotidien

Ajouter dans le Planificateur de taches DSM :
- Frequence : Tous les jours a 03:00
- Script : `/volume1/docker/marveline/deploy/backup-db.sh`

### Mise a jour

```bash
cd /volume1/docker/marveline
git pull  # ou rsync
sudo docker compose -f deploy/docker-compose.synology.yml --env-file .env.prod up -d --build
```

### Logs

```bash
sudo docker compose -f deploy/docker-compose.synology.yml logs -f api
sudo docker compose -f deploy/docker-compose.synology.yml logs -f nginx
```

### Restart

```bash
sudo docker compose -f deploy/docker-compose.synology.yml restart api
```

---

## Couts mensuels

| Poste | Cout |
|-------|------|
| VPS OVH Starter | ~3.50 EUR |
| Nom de domaine (deja possede) | 0 EUR |
| Synology (deja possede) | 0 EUR (electricite ~5 EUR) |
| Let's Encrypt | 0 EUR |
| **Total** | **~8.50 EUR/mois** |
