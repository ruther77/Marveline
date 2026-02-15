# Phase 5 : API Keys & Feature Flags

## Etat actuel

- Authentification uniquement JWT (user-based)
- Aucun mecanisme M2M (machine-to-machine)
- Aucun systeme de feature flags
- Rate limiting existe (Redis-based, multi-niveaux) — extensible pour quotas API keys
- Audit logging existe — extensible pour operations API keys

## Partie A : API Keys (Auth M2M)

### Cas d'usage

1. **Integrations tierces** : caisse enregistreuse, site web public, app mobile
2. **Automatisation** : scripts d'import/export, synchronisation stock
3. **Partenaires** : acces limite au catalogue pour sites referents
4. **CI/CD** : health checks, smoke tests automatises

### Architecture

#### Modele de donnees

```sql
CREATE TABLE api_keys (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id),
    name            VARCHAR(100) NOT NULL,          -- "Caisse magasin 1"
    key_prefix      VARCHAR(12) NOT NULL,           -- "mk_live_a1b2" (visible, pour identification)
    key_hash        VARCHAR(128) NOT NULL,           -- SHA-256 du full key (stockage securise)
    scopes          TEXT[] NOT NULL DEFAULT '{}',    -- {"products:read", "inventory:read"}
    rate_limit      INTEGER DEFAULT 1000,            -- req/heure (null = defaut tenant)
    expires_at      TIMESTAMP WITH TIME ZONE,        -- null = pas d'expiration
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_by      BIGINT NOT NULL REFERENCES users(id),
    last_used_at    TIMESTAMP WITH TIME ZONE,
    last_used_ip    VARCHAR(45),                     -- IPv4 ou IPv6
    usage_count     BIGINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_api_keys_tenant_prefix UNIQUE (tenant_id, key_prefix),
    CONSTRAINT uq_api_keys_key_hash UNIQUE (key_hash),
    CONSTRAINT ck_api_keys_scopes_not_empty CHECK (array_length(scopes, 1) > 0)
);

CREATE INDEX ix_api_keys_tenant_id ON api_keys(tenant_id);
CREATE INDEX ix_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX ix_api_keys_tenant_active ON api_keys(tenant_id, is_active) WHERE is_active = TRUE;
```

#### Format de cle

```
mk_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6

Decomposition :
  mk_      : prefixe Marveline Key (identification rapide)
  live_    : environnement (live / test)
  a1b2...  : 32 caracteres aleatoires (secrets.token_urlsafe(32))

Stockage :
  - key_prefix = "mk_live_a1b2" (12 premiers chars, visible dans UI)
  - key_hash = SHA-256(full_key)  (jamais le full key en base)
  - full_key montre UNE SEULE FOIS a la creation
```

#### Authentification dual-mode

Le systeme doit supporter JWT (users) ET API keys (machines) sur les memes endpoints.

```python
# app/core/deps.py

def get_current_principal(
    request: Request,
    db: Session = Depends(get_db)
) -> Principal:
    """Extrait le principal (User ou ApiKeyClient) depuis la requete.

    Ordre de resolution :
    1. Header Authorization: Bearer <jwt>     -> User
    2. Header X-API-Key: mk_live_xxx          -> ApiKeyClient
    3. Aucun -> 401
    """

class Principal(Protocol):
    """Interface commune User / ApiKeyClient."""
    tenant_id: int
    permissions: set[str]
    principal_type: str  # "user" ou "api_key"
    principal_id: str    # user_id ou api_key_id

class ApiKeyClient:
    """Principal represantant une API key authentifiee."""
    tenant_id: int
    permissions: set[str]  # = scopes de l'API key
    principal_type = "api_key"
    principal_id: str  # api_key.id
    api_key_name: str
```

**Pourquoi un `Principal` abstrait ?**
- `require_permission()` fonctionne identiquement pour User et ApiKey
- L'audit log capture qui a fait quoi (user OU api_key)
- Pas de duplication de logique d'autorisation
- Les endpoints ne changent PAS (transparent)

#### Validation API Key (flow)

```
Request avec X-API-Key: mk_live_xxx
  |
  v
1. Extraire le header X-API-Key
2. SHA-256(key) -> key_hash
3. SELECT * FROM api_keys WHERE key_hash = ? AND is_active = TRUE
4. Verifier expiration (expires_at > now() ou NULL)
5. Verifier tenant isolation
6. Charger scopes -> permissions
7. Rate limiting specifique (api_key.rate_limit)
8. UPDATE last_used_at, last_used_ip, usage_count += 1
9. Retourner ApiKeyClient
```

**Cache Redis** pour eviter le SELECT a chaque requete :
```
Key   : api_key:{key_hash_prefix}
Value : {tenant_id, scopes, rate_limit, expires_at}
TTL   : 5 minutes
Invalidation : sur update/delete de l'API key
```

#### Endpoints CRUD API Keys

```
POST   /api/v1/api-keys              # Creer une cle (admin only)
GET    /api/v1/api-keys              # Lister les cles du tenant
GET    /api/v1/api-keys/{id}         # Detail d'une cle
PATCH  /api/v1/api-keys/{id}         # Modifier (name, scopes, rate_limit, is_active)
DELETE /api/v1/api-keys/{id}         # Revoquer (soft delete)
POST   /api/v1/api-keys/{id}/rotate  # Rotation : nouvelle cle, ancienne revoquee
```

**Securite :**
- Seuls les `admin` peuvent gerer les API keys
- Le full key n'est retourne QU'AU CREATE et ROTATE (jamais apres)
- Rate limiting independant par API key
- Scopes = sous-ensemble des permissions du role admin (jamais plus)

#### Schemas

```python
class ApiKeyCreate(BaseSchema):
    name: str                           # max 100 chars
    scopes: list[Permission]            # au moins 1 scope
    rate_limit: int | None = None       # req/heure, null = defaut
    expires_at: datetime | None = None  # null = pas d'expiration

class ApiKeyResponse(BaseSchema):
    id: int
    name: str
    key_prefix: str                     # "mk_live_a1b2"
    scopes: list[str]
    rate_limit: int | None
    expires_at: datetime | None
    is_active: bool
    last_used_at: datetime | None
    usage_count: int
    created_at: datetime

class ApiKeyCreated(ApiKeyResponse):
    full_key: str                       # UNIQUEMENT au create/rotate

class ApiKeyUpdate(BaseSchema):
    name: str | None = None
    scopes: list[Permission] | None = None
    rate_limit: int | None = None
    is_active: bool | None = None
```

### Fichiers a creer / modifier

```
CREER :
  app/models/api_key.py                 # Modele SQLAlchemy
  app/schemas/api_key.py                # Schemas Pydantic
  app/repositories/api_key.py           # Repository
  app/services/api_key.py               # Service (CRUD + validation + hashing)
  app/api/v1/endpoints/api_keys.py      # Endpoints CRUD
  alembic/versions/xxx_create_api_keys_table.py  # Migration
  tests/unit/test_api_key_service.py
  tests/integration/test_api_keys_endpoints.py
  tests/security/test_api_key_isolation.py

MODIFIER :
  app/core/deps.py                      # Principal abstrait + get_current_principal
  app/models/__init__.py                # Export ApiKey
  app/schemas/__init__.py               # Export schemas
  app/services/__init__.py              # Export service
  app/api/v1/__init__.py                # Enregistrer router api_keys
  app/middleware/audit.py               # Supporter audit pour API key principal
  app/middleware/security.py            # Rate limiting par API key
  app/constants/security.py             # RedisKeys pour api_key cache
```

---

## Partie B : Feature Flags

### Cas d'usage

1. **Rollout progressif** : activer une feature pour certains tenants d'abord
2. **Kill switch** : desactiver une feature en production sans deploiement
3. **A/B testing** : activer des variantes par tenant
4. **Features payantes** : gating par plan/tier

### Architecture

#### Choix : Feature flags en base + cache Redis

**Pourquoi pas des variables d'environnement ?**
- Pas de rollout progressif possible
- Changement = redeploiement
- Pas de ciblage par tenant

**Pourquoi pas un service externe (LaunchDarkly, Unleash) ?**
- Surcout pour une app de cette taille
- Dependance externe supplementaire
- Les besoins sont simples (on/off par tenant)

#### Modele de donnees

```sql
CREATE TABLE feature_flags (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,    -- "mfa_enabled", "stripe_payments"
    description     TEXT,
    is_enabled      BOOLEAN NOT NULL DEFAULT FALSE,  -- master switch global
    target_tenants  BIGINT[] DEFAULT NULL,            -- null = tous, [] = aucun, [1,2] = specifiques
    rollout_pct     INTEGER DEFAULT 100,              -- 0-100, pourcentage de rollout
    metadata        JSONB DEFAULT '{}',               -- donnees arbitraires (plan, tier, etc.)
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX ix_feature_flags_name ON feature_flags(name);
```

#### Logique d'evaluation

```python
def is_feature_enabled(flag_name: str, tenant_id: int) -> bool:
    """Evalue si une feature est active pour un tenant donne.

    Regles d'evaluation (dans l'ordre) :
    1. Si is_enabled = False -> False (master kill switch)
    2. Si target_tenants is not None :
       a. Si target_tenants = [] -> False (aucun tenant)
       b. Si tenant_id in target_tenants -> True (whitelist)
       c. Sinon -> False
    3. Si target_tenants is None (tous les tenants) :
       a. Si rollout_pct = 100 -> True
       b. Si rollout_pct = 0 -> False
       c. Sinon -> hash(flag_name + tenant_id) % 100 < rollout_pct
          (deterministe : meme resultat pour meme tenant)
    """
```

**Cache Redis :**
```
Key   : ff:{flag_name}
Value : {is_enabled, target_tenants, rollout_pct}
TTL   : 60 secondes (refresh automatique)
Invalidation : sur update du flag
```

#### Endpoints

```
GET    /api/v1/features              # Lister tous les flags (admin)
GET    /api/v1/features/{name}       # Detail d'un flag (admin)
POST   /api/v1/features              # Creer un flag (admin)
PATCH  /api/v1/features/{name}       # Modifier un flag (admin)
DELETE /api/v1/features/{name}       # Supprimer un flag (admin)
GET    /api/v1/features/evaluate     # Evaluer tous les flags pour le tenant courant (auth)
```

#### Usage dans le code

```python
# Dans un endpoint :
@router.post("/reservations")
def create_reservation(
    ...,
    features: FeatureFlagService = Depends(get_feature_service)
):
    if features.is_enabled("online_booking", current_user.tenant_id):
        # logique booking online
    else:
        raise HTTPException(403, "Fonctionnalite non disponible")

# Dans le frontend (via /features/evaluate) :
# GET /api/v1/features/evaluate -> {"mfa_enabled": true, "online_booking": false, ...}
```

### Fichiers a creer

```
CREER :
  app/models/feature_flag.py
  app/schemas/feature_flag.py
  app/repositories/feature_flag.py
  app/services/feature_flag.py
  app/api/v1/endpoints/features.py
  alembic/versions/xxx_create_feature_flags_table.py
  tests/unit/test_feature_flag_service.py
  tests/integration/test_feature_flags_endpoints.py

MODIFIER :
  app/models/__init__.py
  app/schemas/__init__.py
  app/services/__init__.py
  app/api/v1/__init__.py
```

---

## Dependances inter-phases

```
Phase 4 (RBAC permissions) --> Phase 5A (API Keys)
  Les scopes des API keys = sous-ensemble des Permission enum de Phase 4.
  require_permission() doit fonctionner avec Principal (User ou ApiKeyClient).

Phase 5A (API Keys) est independant de Phase 5B (Feature Flags).
  Peuvent etre implementees en parallele.
```

### Ordre d'implementation recommande

1. Phase 4 : RBAC permissions (prerequis)
2. Phase 5A : API Keys (depend de Phase 4)
3. Phase 5B : Feature Flags (independant, peut aller en parallele avec 5A)

## Estimation

| Composant | Fichiers | Complexite |
|-----------|----------|-----------|
| API Keys (model -> endpoints) | ~12 nouveaux, ~8 modifies | Haute |
| Feature Flags | ~7 nouveaux, ~4 modifies | Moyenne |
| **Total Phase 5** | **~19 nouveaux, ~12 modifies** | **Haute** |

## Risques

| Risque | Mitigation |
|--------|-----------|
| Fuite de cle API | Hash SHA-256 en base, full key visible qu'une fois |
| Escalade de privileges via scopes | Scopes valides contre Permission enum, jamais > role admin |
| Cache stale sur feature flags | TTL court (60s) + invalidation explicite |
| Performance lookup API key | Cache Redis 5min + index sur key_hash |
| Timing attack sur hash lookup | Comparaison constant-time (hmac.compare_digest) |
