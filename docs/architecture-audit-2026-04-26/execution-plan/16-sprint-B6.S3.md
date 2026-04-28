# Sprint B6.S3 — Feature flags fail-safe + history + sha256 + Redis PUB/SUB

> **STATUT** : ⏳ À démarrer après B6.S2
> **DURÉE MAX** : 1 semaine
> **OWNER** : Dev1
> **BLOQUE** : B6.S4 (Celery utilise FF), B6.S6 (observability metrics filtre par FF)
> **DÉPEND DE** : B6.S2 (audit refondu)
> **OBJECTIF** : Refondre Feature Flags pour : (1) `fail_safe_value` colonne `BOOLEAN NOT NULL` per-flag avec politique fail-closed `mfa_enabled` (F1031), (2) drop `hashlib.md5` → `sha256` salté tenant_id (F1032), (3) audit changements via Outbox (F1033), (4) `FeatureFlagHistory` append-only, (5) table M:N `feature_flag_tenants` (drop ARRAY orphan), (6) cache LRU + Redis PUB/SUB invalidation cross-replica.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B6.S3.T1** | F1031 — `feature_flags.fail_safe_value BOOLEAN NOT NULL` + politique fail-closed mfa_enabled | P0 | 1 j | T2 |
| **B6.S3.T2** | F1032 — Drop `hashlib.md5` → `sha256` salté tenant_id | P0 | 0.5 j | aucun |
| **B6.S3.T3** | F1033 — Audit changements FF via Outbox + table `FeatureFlagHistory` | P0 | 1 j | aucun |
| **B6.S3.T4** | Drop `ARRAY orphan target_tenants` → table M:N `feature_flag_tenants` | P1 | 1 j | aucun |
| **B6.S3.T5** | Cache LRU local + Redis PUB/SUB invalidation cross-replica | P1 | 1 j | aucun |
| **B6.S3.T6** | CI invariant `tools/check_feature_flag_fail_safe.py` (chaque flag DB a fail_safe_value) | P1 | 0.5 j | aucun |

**Total effort** : 5 jours-homme.

---

# Story B6.S3.T1 — `fail_safe_value` BOOLEAN NOT NULL (F1031)

## Contexte

**Friction** : F1031
**Sévérité** : P0 — DB+Redis down → flag retourne `False` sans distinction (ou raise) → user MFA skip silencieux

### Description

Cible : chaque flag a un `fail_safe_value: bool NOT NULL` qui est retourné si DB ou Redis sont injoignables. Politique :
- `mfa_enabled` → `fail_safe_value = TRUE` (sécurité par défaut)
- `feature_x_beta` → `fail_safe_value = FALSE` (no surprise)

## Solution

```python
# alembic/versions/k1a2b3c4d605_feature_flag_fail_safe.py
def upgrade() -> None:
    op.add_column(
        "feature_flags",
        sa.Column("fail_safe_value", sa.Boolean, nullable=False, server_default="false"),
    )
    # Politique fail-closed pour flags sécurité
    op.execute(text("""
        UPDATE feature_flags SET fail_safe_value = true
        WHERE name IN ('mfa_enabled', 'rls_enforced', 'audit_chain_required')
    """))
```

```python
# app/services/feature_flag.py
class FeatureFlagService:
    async def is_enabled(self, name: str, tenant_id: int) -> bool:
        try:
            return await self._evaluate(name, tenant_id)
        except (DatabaseError, RedisError) as e:
            # Fail-safe : retourner valeur configurée
            flag = await self._fetch_flag_from_cache_or_db(name)
            logger.error("ff_fail_safe_triggered", name=name, error=str(e), fallback=flag.fail_safe_value)
            return flag.fail_safe_value if flag else False
```

### Test

```python
async def test_fail_safe_mfa_enabled_when_redis_down(monkeypatch, ff_service):
    monkeypatch.setattr(ff_service.redis, "get", AsyncMock(side_effect=RedisError("connection refused")))
    monkeypatch.setattr(ff_service.db, "scalar", AsyncMock(side_effect=DatabaseError("timeout")))
    
    enabled = await ff_service.is_enabled("mfa_enabled", tenant_id=1)
    assert enabled is True  # fail-safe value
```

## DoD

- [ ] Migration `fail_safe_value BOOLEAN NOT NULL`
- [ ] Politique fail-closed sur 3 flags sécurité
- [ ] Service catch DB/Redis errors → fallback fail_safe
- [ ] Test : Redis+DB down → flag mfa retourne True

---

# Story B6.S3.T2 — Drop `md5` → `sha256` salté (F1032)

## Contexte

**Friction** : F1032
**Sévérité** : P0 — `hashlib.md5(tenant_id.encode())` pour hash partial rollout = collision possible (md5 cassé)

### Description

Cible : `sha256(salt || tenant_id)` avec salt per-flag.

## Solution

```python
# app/services/feature_flag.py
import hashlib

def _compute_rollout_hash(flag_name: str, tenant_id: int, salt: str) -> int:
    """SHA-256 avec sel per-flag."""
    msg = f"{salt}:{flag_name}:{tenant_id}".encode()
    digest = hashlib.sha256(msg).digest()
    # Premier 4 bytes → int 0..2^32 → modulo 100 pour pourcentage
    return int.from_bytes(digest[:4], "big") % 100

# Avant
# rollout_hash = int(hashlib.md5(str(tenant_id).encode()).hexdigest(), 16) % 100

# Après
rollout_hash = _compute_rollout_hash(flag.name, tenant_id, salt=settings.FF_SALT)
if rollout_hash < flag.rollout_pct:
    return True
```

### Migration

```python
# Pas de migration DB ; le hash est calculé runtime
# Note : changement de hash function = re-calcul rollout différent pour chaque tenant
# Communication ops avant deploy.
```

## DoD

- [ ] `sha256` salté remplace md5
- [ ] Salt per-flag via settings ou colonne `feature_flags.salt`
- [ ] Test : same input → same hash deterministic
- [ ] Documentation : changement re-calcule rollout

---

# Story B6.S3.T3 — Audit FF changes via Outbox + `FeatureFlagHistory`

## Contexte

**Friction** : F1033
**Sévérité** : P0 — modifications FF non auditées (compliance)

### Description

Cible :
1. Table `feature_flag_history` append-only
2. Trigger DB AFTER UPDATE → insert history + Outbox event

## Solution

```python
def upgrade() -> None:
    op.create_table(
        "feature_flag_history",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("feature_flag_id", sa.Integer, ForeignKey("feature_flags.id")),
        sa.Column("changed_by", postgresql.UUID, ForeignKey("accounts.id")),
        sa.Column("old_enabled", sa.Boolean),
        sa.Column("new_enabled", sa.Boolean),
        sa.Column("old_rollout_pct", sa.Integer),
        sa.Column("new_rollout_pct", sa.Integer),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.execute(text("""
        CREATE OR REPLACE FUNCTION feature_flag_history_log() RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.enabled IS DISTINCT FROM OLD.enabled OR NEW.rollout_pct IS DISTINCT FROM OLD.rollout_pct THEN
                INSERT INTO feature_flag_history (feature_flag_id, old_enabled, new_enabled, old_rollout_pct, new_rollout_pct, changed_at)
                VALUES (OLD.id, OLD.enabled, NEW.enabled, OLD.rollout_pct, NEW.rollout_pct, NOW());
                INSERT INTO outbox_events (event_type, aggregate_id, payload, created_at)
                VALUES ('FeatureFlagChanged', OLD.id::text,
                    jsonb_build_object('flag', OLD.name, 'old', OLD.enabled, 'new', NEW.enabled),
                    NOW());
            END IF;
            RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """))
    op.execute(text("""
        CREATE TRIGGER trg_feature_flag_history
        AFTER UPDATE ON feature_flags
        FOR EACH ROW EXECUTE FUNCTION feature_flag_history_log()
    """))
```

## DoD

- [ ] Table `feature_flag_history`
- [ ] Trigger AFTER UPDATE log + Outbox
- [ ] Test : update flag → row history créée
- [ ] Test : Outbox event publié

---

# Story B6.S3.T4 — Drop ARRAY → M:N `feature_flag_tenants`

## Contexte

**Sévérité** : P1 — `feature_flags.target_tenants INT[]` orphan ARRAY (pas FK, pas indexable)

### Description

Cible : table M:N `feature_flag_tenants(feature_flag_id, tenant_id)`.

## Solution

```python
def upgrade() -> None:
    op.create_table(
        "feature_flag_tenants",
        sa.Column("feature_flag_id", sa.Integer, ForeignKey("feature_flags.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tenant_id", sa.Integer, ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("rollout_pct", sa.Integer, nullable=False, server_default="100"),  # override per tenant
    )
    # Backfill
    op.execute(text("""
        INSERT INTO feature_flag_tenants (feature_flag_id, tenant_id, rollout_pct)
        SELECT id, unnest(target_tenants), 100
        FROM feature_flags WHERE target_tenants IS NOT NULL
    """))
    op.drop_column("feature_flags", "target_tenants")
```

## DoD

- [ ] Table M:N créée
- [ ] Backfill ARRAY → rows
- [ ] Drop ARRAY column
- [ ] Test : assignation per-tenant indexée + override rollout

---

# Story B6.S3.T5 — Cache LRU + Redis PUB/SUB invalidation

## Contexte

Performance + cohérence cross-replica.

### Description

Cible :
1. Cache LRU local (functools.lru_cache ou cachetools) — 1000 entries, TTL 60s
2. Redis PUB/SUB channel `feature_flags:invalidate` — broadcast invalidation
3. Tous les replicas listen et clear leur LRU sur message

## Solution

```python
# app/services/feature_flag.py
from cachetools import TTLCache
from cachetools.keys import hashkey

class FeatureFlagService:
    def __init__(self, db, redis):
        self.db = db
        self.redis = redis
        self.cache = TTLCache(maxsize=1000, ttl=60)
        self._listener_task = asyncio.create_task(self._listen_invalidations())

    async def _listen_invalidations(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("feature_flags:invalidate")
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                self.cache.clear()
                logger.info("ff_cache_invalidated_via_pubsub")

    async def is_enabled(self, name, tenant_id):
        key = hashkey(name, tenant_id)
        if key in self.cache:
            return self.cache[key]
        value = await self._evaluate(name, tenant_id)
        self.cache[key] = value
        return value

    async def update_flag(self, flag_id, **changes):
        # ... update DB
        await self.redis.publish("feature_flags:invalidate", "1")
```

## DoD

- [ ] LRU cache TTL 60s
- [ ] PUB/SUB invalidation cross-replica
- [ ] Test 2 replicas : update sur replica 1 → replica 2 cache cleared

---

# Story B6.S3.T6 — CI invariant fail_safe_value

## Solution

```python
# tools/check_feature_flag_fail_safe.py
"""Verify chaque flag DB a fail_safe_value défini."""
async def main():
    flags = await db.scalars(select(FeatureFlag))
    missing = [f.name for f in flags.all() if f.fail_safe_value is None]
    if missing:
        sys.exit(f"❌ Flags sans fail_safe_value: {missing}")
```

## DoD

- [ ] Script CI actif
- [ ] Whitelist flags vraiment fail-False (ex: feature_x_beta)
- [ ] Test : flag sans fail_safe_value → CI fail

---

## Critères de succès Sprint B6.S3

- [ ] **F1031 résolu** : fail_safe_value enforce + politique fail-closed
- [ ] **F1032 résolu** : sha256 salté
- [ ] **F1033 résolu** : audit + history via Outbox
- [ ] M:N `feature_flag_tenants` drop ARRAY orphan
- [ ] Cache LRU + Redis PUB/SUB
- [ ] CI invariant fail_safe

---

**Fin du document — 16-sprint-B6.S3.md**
