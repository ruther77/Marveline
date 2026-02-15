# Phase 6 : WireGuard API - Gestion dynamique des peers

## Contexte

WireGuard est un VPN kernel-level performant. L'objectif est d'exposer une API REST pour
gerer dynamiquement les peers WireGuard (ajout, suppression, rotation de cles) sans toucher
manuellement aux fichiers de config ou au CLI `wg`.

**Cas d'usage Marveline :**
- Connecter les points de vente distants au reseau prive
- Securiser les connexions entre API, base de donnees, et services internes
- Permettre l'acces VPN aux techniciens/partenaires avec des cles temporaires
- Gestion centralisee du reseau depuis le dashboard admin

## Architecture : 2 options evaluees

### Option A : Service integre a Marveline (monolithe)

```
[Marveline API] ---> [WireGuard module] ---> [subprocess: wg / wg-quick]
                                         ---> [fichier: /etc/wireguard/wg0.conf]
```

**Avantages :** Simple, pas de service supplementaire.
**Inconvenients :**
- Le conteneur API doit avoir `NET_ADMIN` capability (securite)
- Couplage fort entre logique metier et infra reseau
- L'API Marveline tourne en user `appuser` (non-root) : impossible de toucher wg0
- Scalabilite impossible (2 replicas API = 2 configs wg differentes)

### Option B : Microservice dedie (RECOMMANDE)

```
[Marveline API] --REST/gRPC--> [WireGuard Service] ---> [netlink / wg CLI]
     |                              |
     |                              +---> [PostgreSQL: wg_peers table]
     |                              +---> [Redis: peer status cache]
     +-- meme reseau Docker --------+
```

**Avantages :**
- Separation des responsabilites (SRP)
- Le service WG tourne avec les privileges necessaires, isole
- L'API Marveline reste stateless et non-privilegiee
- Deploiement independant, scaling independant
- Peut etre reutilise par d'autres projets

**Inconvenients :**
- Un service de plus a maintenir
- Communication inter-service a gerer

**Verdict : Option B.** Le WireGuard Service est un service FastAPI separe, dans le meme
docker-compose, avec son propre Dockerfile et ses privileges reseaux.

## Architecture detaillee

### Vue d'ensemble

```
                    Internet
                       |
                  [Load Balancer]
                       |
              +--------+--------+
              |                 |
         [Marveline API]  [Frontend]
              |
              | (reseau interne Docker)
              |
         [WireGuard Service]  <--- NET_ADMIN capability
              |
         [wg0 interface]
              |
         [Peers VPN] <---> Points de vente, techniciens, etc.
```

### Modele de donnees

Le WireGuard Service a sa propre base (ou schema separe dans PostgreSQL).

```sql
-- Table principale des peers
CREATE TABLE wg_peers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       BIGINT NOT NULL,                     -- isolation multi-tenant
    name            VARCHAR(100) NOT NULL,                -- "Magasin Lyon", "Tech Jean"
    description     TEXT,
    public_key      VARCHAR(44) NOT NULL UNIQUE,          -- base64, 32 bytes = 44 chars
    preshared_key   VARCHAR(128),                         -- chiffre (AES-256-GCM), optionnel
    allowed_ips     TEXT[] NOT NULL,                       -- {"10.0.1.2/32", "192.168.1.0/24"}
    endpoint        VARCHAR(255),                          -- "vpn.marveline.fr:51820" (serveur)
    assigned_ip     INET NOT NULL UNIQUE,                  -- IP attribuee dans le tunnel
    dns             TEXT[],                                 -- DNS pousses au client
    persistent_keepalive INTEGER DEFAULT 25,               -- secondes (0 = desactive)
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at      TIMESTAMP WITH TIME ZONE,              -- null = permanent
    last_handshake  TIMESTAMP WITH TIME ZONE,              -- derniere connexion reussie
    rx_bytes        BIGINT DEFAULT 0,
    tx_bytes        BIGINT DEFAULT 0,
    created_by      BIGINT NOT NULL,                       -- user_id Marveline
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_wg_peers_tenant_name UNIQUE (tenant_id, name),
    CONSTRAINT ck_wg_peers_allowed_ips CHECK (array_length(allowed_ips, 1) > 0)
);

CREATE INDEX ix_wg_peers_tenant ON wg_peers(tenant_id);
CREATE INDEX ix_wg_peers_public_key ON wg_peers(public_key);
CREATE INDEX ix_wg_peers_assigned_ip ON wg_peers(assigned_ip);

-- Pool d'IPs disponibles pour attribution
CREATE TABLE wg_ip_pool (
    id              SERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL,
    subnet          CIDR NOT NULL,                         -- "10.0.1.0/24"
    next_ip         INET NOT NULL,                         -- prochaine IP a attribuer
    gateway_ip      INET NOT NULL,                         -- IP du serveur WG dans ce subnet

    CONSTRAINT uq_wg_ip_pool_tenant_subnet UNIQUE (tenant_id, subnet)
);

-- Journal des operations (audit specifique WG)
CREATE TABLE wg_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL,
    peer_id         UUID REFERENCES wg_peers(id),
    action          VARCHAR(50) NOT NULL,                  -- "peer_created", "peer_revoked", "key_rotated"
    actor_id        BIGINT NOT NULL,                       -- user_id
    details         JSONB DEFAULT '{}',
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### API Endpoints (WireGuard Service)

Le service expose une API REST interne (non exposee publiquement).

```
# Gestion des peers
POST   /wg/v1/peers                    # Creer un peer (genere keypair, attribue IP)
GET    /wg/v1/peers                    # Lister les peers du tenant
GET    /wg/v1/peers/{id}              # Detail d'un peer + stats temps reel
PATCH  /wg/v1/peers/{id}              # Modifier (name, allowed_ips, keepalive)
DELETE /wg/v1/peers/{id}              # Revoquer (supprime de wg0 + soft delete)
POST   /wg/v1/peers/{id}/rotate       # Rotation de cles (nouveau keypair)
POST   /wg/v1/peers/{id}/enable       # Reactiver un peer desactive
POST   /wg/v1/peers/{id}/disable      # Desactiver temporairement

# Configuration client
GET    /wg/v1/peers/{id}/config        # Telecharger le fichier .conf client
GET    /wg/v1/peers/{id}/qrcode        # QR code pour config mobile

# Monitoring
GET    /wg/v1/status                   # Etat global du serveur WG
GET    /wg/v1/peers/{id}/stats         # Stats temps reel (handshake, rx/tx)

# IP Pool
GET    /wg/v1/ip-pools                 # Lister les pools du tenant
POST   /wg/v1/ip-pools                 # Creer un pool (admin)
```

### Gestion des cles

```python
# Generation keypair WireGuard (curve25519)
import subprocess

def generate_keypair() -> tuple[str, str]:
    """Genere une paire de cles WireGuard."""
    private_key = subprocess.run(
        ["wg", "genkey"], capture_output=True, text=True, check=True
    ).stdout.strip()

    public_key = subprocess.run(
        ["wg", "pubkey"], input=private_key,
        capture_output=True, text=True, check=True
    ).stdout.strip()

    return private_key, public_key

def generate_preshared_key() -> str:
    """Genere une cle pre-partagee pour double chiffrement."""
    return subprocess.run(
        ["wg", "genpsk"], capture_output=True, text=True, check=True
    ).stdout.strip()
```

**Securite des cles privees :**
- La cle privee du PEER est generee cote serveur, incluse dans le .conf client,
  puis SUPPRIMEE de la memoire serveur (jamais stockee en base)
- La cle privee du SERVEUR est dans un secret Docker / variable d'env
- La preshared key est chiffree en base (AES-256-GCM via `app/core/crypto.py`)

### Application dynamique (sans restart)

WireGuard supporte la modification a chaud via `wg set` :

```python
class WireGuardManager:
    """Gere l'interface wg0 via le CLI wg."""

    def __init__(self, interface: str = "wg0"):
        self.interface = interface

    def add_peer(self, public_key: str, allowed_ips: list[str],
                 preshared_key: str | None = None) -> None:
        """Ajoute un peer a l'interface WG (sans restart)."""
        cmd = ["wg", "set", self.interface, "peer", public_key,
               "allowed-ips", ",".join(allowed_ips)]
        if preshared_key:
            # preshared-key via stdin (pas en argument, securite)
            cmd.extend(["preshared-key", "/dev/stdin"])
            subprocess.run(cmd, input=preshared_key, text=True, check=True)
        else:
            subprocess.run(cmd, check=True)

    def remove_peer(self, public_key: str) -> None:
        """Retire un peer de l'interface WG (sans restart)."""
        subprocess.run(
            ["wg", "set", self.interface, "peer", public_key, "remove"],
            check=True
        )

    def get_peer_stats(self, public_key: str) -> dict:
        """Recupere les stats temps reel d'un peer."""
        output = subprocess.run(
            ["wg", "show", self.interface, "dump"],
            capture_output=True, text=True, check=True
        ).stdout
        # Parse le dump pour trouver le peer
        for line in output.strip().split("\n")[1:]:  # skip header
            fields = line.split("\t")
            if fields[0] == public_key:
                return {
                    "endpoint": fields[2],
                    "allowed_ips": fields[3].split(","),
                    "last_handshake": int(fields[4]),
                    "rx_bytes": int(fields[5]),
                    "tx_bytes": int(fields[6]),
                }
        return {}

    def sync_config(self, peers: list[dict]) -> None:
        """Synchronise la config complete (reconciliation).
        Utilise wg syncconf pour appliquer l'etat desire."""
        config = self._generate_config(peers)
        # wg syncconf applique le delta sans couper les connexions
        subprocess.run(
            ["wg", "syncconf", self.interface, "/dev/stdin"],
            input=config, text=True, check=True
        )
```

### Communication Marveline <-> WireGuard Service

```
Option 1 : REST interne (RECOMMANDE pour la simplicite)
  - Marveline API appelle WG Service via HTTP sur le reseau Docker
  - Auth : API key interne (shared secret) ou mTLS
  - URL : http://wireguard-service:8002/wg/v1/...

Option 2 : Message queue (Celery/Redis)
  - Marveline publie des taches, WG Service les consomme
  - Avantage : asynchrone, retry automatique
  - Inconvenient : plus complexe, latence

Recommandation : REST pour les operations CRUD (synchrones, reponse immediate),
                 Celery pour les operations batch (sync config, expiration crons)
```

### Docker setup

```yaml
# Ajout dans docker-compose.yml
wireguard-service:
  build:
    context: ./wireguard-service
    dockerfile: Dockerfile
  container_name: marveline_wireguard
  cap_add:
    - NET_ADMIN
    - SYS_MODULE
  sysctls:
    - net.ipv4.ip_forward=1
    - net.ipv4.conf.all.src_valid_mark=1
  ports:
    - "51820:51820/udp"    # Port WireGuard
    - "8002:8000"          # API interne (pas expose en prod)
  volumes:
    - /lib/modules:/lib/modules:ro   # Pour le module kernel wg
  environment:
    - DATABASE_URL=postgresql://...
    - REDIS_URL=redis://...
    - WG_PRIVATE_KEY=${WG_PRIVATE_KEY}
    - WG_LISTEN_PORT=51820
    - WG_ADDRESS=10.0.0.1/24
    - MARVELINE_API_KEY=${WG_INTERNAL_API_KEY}
  networks:
    - carocorp_net
  depends_on:
    db:
      condition: service_healthy
    redis:
      condition: service_healthy
```

### Structure du microservice

```
wireguard-service/
├── Dockerfile
├── pyproject.toml
├── app/
│   ├── main.py                     # FastAPI app
│   ├── core/
│   │   ├── config.py               # Settings WG
│   │   ├── security.py             # Auth API key interne
│   │   └── wireguard.py            # WireGuardManager (CLI wrapper)
│   ├── models/
│   │   ├── peer.py                 # WgPeer model
│   │   └── ip_pool.py             # WgIpPool model
│   ├── schemas/
│   │   ├── peer.py
│   │   └── ip_pool.py
│   ├── services/
│   │   ├── peer_service.py         # Logique metier peers
│   │   ├── ip_allocator.py         # Attribution d'IPs
│   │   └── config_generator.py     # Generation fichiers .conf
│   ├── repositories/
│   │   ├── peer_repository.py
│   │   └── ip_pool_repository.py
│   └── api/
│       └── v1/
│           ├── peers.py
│           ├── status.py
│           └── ip_pools.py
├── alembic/                        # Migrations propres au service
├── tests/
└── scripts/
    └── init_wg.sh                  # Initialisation interface wg0
```

### Securite

| Concern | Solution |
|---------|----------|
| Privileges eleves | Seul le conteneur WG a NET_ADMIN, API Marveline reste non-privilegiee |
| Auth inter-service | API key interne partagee (env var), validee a chaque requete |
| Cle privee serveur | Variable d'env Docker secret, jamais en base |
| Cle privee peer | Generee, incluse dans .conf, jamais persistee cote serveur |
| Preshared key | Chiffree en base (AES-256-GCM) |
| Exposition API WG | Port 8002 NON expose en production (reseau Docker interne only) |
| Expiration peers | Cron job qui desactive les peers expires (Celery beat ou APScheduler) |
| Audit | Table wg_audit_log dediee + integration audit Marveline |
| IP spoofing | AllowedIPs strict sur chaque peer (WireGuard enforce cote kernel) |

### Cron jobs

```python
# Toutes les 5 minutes :
- Synchroniser stats peers (rx/tx, last_handshake) depuis wg show
- Desactiver peers expires (expires_at < now())
- Alerter sur peers sans handshake depuis > 24h (monitoring)

# Toutes les heures :
- Reconciliation config (wg syncconf vs base de donnees)
- Nettoyage peers soft-deleted depuis > 30 jours
```

### Integration frontend (Marveline dashboard)

```
Pages a creer dans le frontend Marveline :
  /admin/vpn              # Liste des peers VPN + stats
  /admin/vpn/new          # Formulaire creation peer
  /admin/vpn/{id}         # Detail peer + config download + QR code
  /admin/vpn/ip-pools     # Gestion des pools IP
```

L'API Marveline agit comme proxy : les endpoints frontend appellent Marveline API,
qui forwarde au WireGuard Service en ajoutant le tenant_id.

```
Frontend -> Marveline API /api/v1/vpn/peers -> WG Service /wg/v1/peers
```

## Dependances

```
Phase 4 (RBAC) --> Phase 5 (API Keys) --> Phase 6 (WireGuard)
  - Phase 6 utilise les permissions Phase 4 : "vpn:read", "vpn:write", "vpn:admin"
  - Phase 6 utilise l'API key interne Phase 5 pour auth inter-service
```

## Estimation

| Composant | Fichiers | Complexite |
|-----------|----------|-----------|
| WireGuard Service (nouveau) | ~20 fichiers | Haute |
| Integration Marveline (proxy) | ~5 fichiers | Moyenne |
| Frontend pages VPN | ~4 fichiers | Moyenne |
| Docker/infra setup | ~3 fichiers | Moyenne |
| **Total Phase 6** | **~32 fichiers** | **Haute** |

## Risques specifiques

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| Module kernel WG absent | Service KO | Dockerfile installe wireguard-tools, verif au startup |
| Desync config vs base | Peers fantomes | Reconciliation periodique (wg syncconf) |
| Fuite cle privee serveur | Compromission totale VPN | Secret Docker, rotation periodique, audit acces |
| Exhaustion IP pool | Plus de nouveaux peers | Monitoring usage pool, alertes a 80% |
| Latence inter-service | UX degradee | Timeout strict (5s), circuit breaker, retry |
