# Sprint B1.S2 — RLS PostgreSQL + tenant context

> **STATUT** : ⏳ À démarrer après B1.S1
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev1 (lead Bloc 1)
> **BLOQUE** : tout B2 (Identity), B3, B4, B5, B6 — RLS est la garantie tenant DB-level
> **DÉPEND DE** : B1.S1 (F01 paramétrage RLS, F02 ApiKey set_tenant_context)
> **OBJECTIF** : Activer Row-Level Security PostgreSQL sur toutes les tables tenant-scoped (~80 tables) — passage de "filtres applicatifs uniquement" à "garantie DB-level cross-tenant impossible".

## Vue d'ensemble

| Story | Description | Estimation | Bloque |
|---|---|---|---|
| **B1.S2.T1** | Helper `set_config('app.current_tenant_id')` + audit caller-sites | 0.5 j | T2 |
| **B1.S2.T2** | Migration RLS enable + policies sur ~80 tables (`c1d2e3f4a5b7`) | 1.5 j | T3 |
| **B1.S2.T3** | Migration outbox RLS custom NULL (`c1d2e3f4a5ba`) | 0.25 j | aucun |
| **B1.S2.T4** | Tests E2E cross-tenant isolation (User + ApiKey + Celery worker) | 1 j | déploiement |
| **B1.S2.T5** | Migration step-by-step pré-prod (FORCE RLS bascule) | 0.75 j | aucun |

**Total effort** : 4 jours-homme. Séquentiel (T1→T2→T3+T4→T5).

**CI invariants livrés** :
- `check_rls_enabled_on_tenant_tables.py` (54 §13) — refuse merge si nouvelle table avec `tenant_id` sans RLS

---

# Story B1.S2.T1 — Helper `set_tenant_context` consolidé

## Contexte

**Friction prévenue** : F01 (B1.S1) + F02 (B1.S1) — couvert. Cette story consolide le helper `set_tenant_context()` comme **seule API publique** pour activer le RLS.

**Code source** : `app/core/database.py` (`set_tenant_context`, `_request_tenant_var`)

### Description

Aujourd'hui, l'activation du contexte tenant est dispersée :
- `app/core/database.py:74-90` : event listener `receive_begin` (auto via ContextVar)
- `app/core/deps.py:349-350` : appel manuel après résolution user
- `app/core/deps.py:531-582` : appel manuel après résolution apikey (B1.S1.T2)
- Workers Celery : appel manuel via `tenant_aware_task` decorator

Cette dispersion rend l'audit difficile. On veut **une seule façon** de set le contexte, avec invariant CI qui détecte les sessions DB ouvertes sans contexte.

## Solution

```python
# app/core/database.py (consolidé)

_request_tenant_var: ContextVar[Optional[int]] = ContextVar(
    "request_tenant_id", default=None
)


@contextmanager
def tenant_context(tenant_id: int):
    """Context manager pour fixer le tenant_id sur la transaction courante.

    Usage :
        with tenant_context(tenant.id):
            # toutes les requêtes DB dans ce bloc voient les data du tenant
            customers = await customer_repo.list(...)

    Pour les handlers HTTP : utilisé automatiquement via deps.py après auth.
    Pour Celery : à wrapper explicitement (cf. B1.S5).
    """
    token = _request_tenant_var.set(tenant_id)
    try:
        yield
    finally:
        _request_tenant_var.reset(token)


def set_tenant_context(tenant_id: int) -> None:
    """Fixe le tenant_id pour la requête courante (ContextVar).

    F01 + F02 fix : appelé par deps.py après résolution User OU ApiKey.
    Le receive_begin event listener picke automatiquement la valeur
    via _request_tenant_var.get() et l'applique via set_config.

    F02 ne pas oublier : si une session DB est ouverte AVANT que
    set_tenant_context ne soit appelé, les premières requêtes
    bypassent RLS. Pattern correct : auth → set_tenant_context → DB call.
    """
    _request_tenant_var.set(tenant_id)


def get_current_tenant_id() -> Optional[int]:
    """Retourne le tenant_id du contexte courant ou None."""
    return _request_tenant_var.get(None)


# Event listener (corrigé par B1.S1.T1)
@event.listens_for(Engine, "begin")
def receive_begin(conn):
    """SET app.current_tenant_id avant chaque transaction SQL."""
    tid = _request_tenant_var.get(None)
    if tid is None:
        return
    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"),
        {"tid": str(tid)},
    )
```

### Audit caller-sites

```bash
# tools/audit_set_tenant_context_callsites.sh
# CI script qui vérifie que tous les chemins d'auth appellent set_tenant_context

grep -rn "set_tenant_context\|tenant_context" app/core/deps.py app/services/celery/
```

## Fichiers à modifier

- `app/core/database.py` (consolidation API)
- `app/core/deps.py` : utiliser nouveau API uniformément
- `tests/unit/core/test_tenant_context.py` (NOUVEAU)

## Tests

```python
@pytest.mark.asyncio
async def test_tenant_context__cm_isolates_requests(db, tenant, other_tenant):
    """tenant_context() context manager isole les requêtes."""
    from app.core.database import tenant_context, get_current_tenant_id
    from app.models import Customer

    customer_a = Customer(tenant_id=tenant.id, nom="A")
    customer_b = Customer(tenant_id=other_tenant.id, nom="B")
    db.add_all([customer_a, customer_b])
    await db.flush()

    with tenant_context(tenant.id):
        assert get_current_tenant_id() == tenant.id
        # Requête sous contexte A
        result = await db.execute(select(Customer))
        ids = {c.id for c in result.scalars().all()}
        # Note : avant B1.S2.T2 (RLS active), les 2 sont visibles
        # Après T2 : seul customer_a visible

    assert get_current_tenant_id() is None  # Reset après bloc
```

## Definition of Done

- [ ] `tenant_context()` context manager + `set_tenant_context()` + `get_current_tenant_id()` consolidés
- [ ] `app/core/deps.py` utilise uniformément le nouveau API
- [ ] 1 test unit vert
- [ ] Documentation `docs/tenant-context.md` créée

## Risque

- Probabilité 1, impact 2 → score 2 LOW

---

# Story B1.S2.T2 — Migration RLS enable + policies (~80 tables)

## Contexte

**Migration** : `c1d2e3f4a5b7` (cf. `51-alembic-migrations.md` §RLS)
**Sévérité** : **P0 architectural** — sans RLS, isolation tenant repose uniquement sur filtres applicatifs (1 oubli = leak)

### Description

Phase 1 §Q2 (architecture-cible.md) impose RLS sur toutes les tables tenant-scoped. Liste TENANT_TABLES dans `51-alembic-migrations.md:97-189` — ~80 tables.

```python
# alembic/versions/c1d2e3f4a5b7_enable_rls_on_tenant_tables.py
"""Enable Row-Level Security on all tenant-scoped tables.

Revision ID: c1d2e3f4a5b7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-05 09:00:00.000000

Bloc 1 Q2=A : RLS PostgreSQL — garantie cross-tenant impossible au niveau DB.

Préalables :
- B1.S1.T1 (F01) : f-string SQL → set_config paramétré
- B1.S1.T2 (F02) : ApiKey appelle set_tenant_context
- B1.S2.T1 : helper `tenant_context()` consolidé
"""
from alembic import op

revision = "c1d2e3f4a5b7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "customers", "products", "product_variants", "product_bundles",
    # ... 80 tables (cf. 51-alembic-migrations.md:97-189)
    # NOTE : `outbox` EXCLU — policy custom dans c1d2e3f4a5ba (B1.S2.T3)
]


def upgrade() -> None:
    for table in TENANT_TABLES:
        # Active RLS
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        # Policy : filtre par tenant_id depuis le contexte
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
                USING (tenant_id = current_setting('app.current_tenant_id', true)::bigint);
        """)
        # Force RLS pour le rôle applicatif (BYPASSRLS reste pour superadmin DEVUP)
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
```

### Rôles PostgreSQL

```sql
-- Pré-requis : 2 rôles distincts pour BYPASSRLS sélectif
CREATE ROLE devup_app NOLOGIN;     -- Application (RLS strict)
CREATE ROLE devup_superadmin NOLOGIN BYPASSRLS;  -- Migrations + ops support

-- Connection app : SET ROLE devup_app après login
-- Connection ops : SET ROLE devup_superadmin (Lead/Ops uniquement, audit MFA)
```

## Fichiers à modifier

- `alembic/versions/c1d2e3f4a5b7_enable_rls_on_tenant_tables.py` (NOUVEAU)
- `app/core/database.py` : SET ROLE devup_app au connect (cf. B1.S2.T5)
- `tests/integration/test_rls_enabled.py` (NOUVEAU)

## Tests

```python
@pytest.mark.asyncio
async def test_rls__all_tenant_tables_enabled(db):
    """Vérifie que RLS est ENABLED + FORCED sur toutes les TENANT_TABLES."""
    from sqlalchemy import text
    from alembic.versions.c1d2e3f4a5b7_enable_rls_on_tenant_tables import TENANT_TABLES

    for table in TENANT_TABLES:
        result = await db.execute(text("""
            SELECT relrowsecurity, relforcerowsecurity
            FROM pg_class WHERE relname = :table
        """), {"table": table})
        row = result.fetchone()
        assert row is not None, f"Table {table} introuvable"
        rowsecurity, force_rowsecurity = row
        assert rowsecurity is True, f"RLS non activé sur {table}"
        assert force_rowsecurity is True, f"RLS non FORCED sur {table} (admin bypass)"


@pytest.mark.asyncio
async def test_rls__cross_tenant_query_returns_empty(db, tenant, other_tenant):
    """Une requête sous contexte tenant A ne retourne PAS les data tenant B."""
    from app.models import Customer
    from app.core.database import tenant_context

    customer_b = Customer(tenant_id=other_tenant.id, nom="B", email="b@b.fr")
    db.add(customer_b)
    await db.flush()

    with tenant_context(tenant.id):
        result = await db.execute(select(Customer))
        ids = {c.id for c in result.scalars().all()}
        assert customer_b.id not in ids, "RLS ne filtre pas correctement"


@pytest.mark.asyncio
async def test_rls__no_context_set__returns_empty(db, tenant):
    """Si set_tenant_context oublié, requête retourne 0 rows (fail-closed)."""
    from app.models import Customer
    customer = Customer(tenant_id=tenant.id, nom="A", email="a@a.fr")
    db.add(customer)
    await db.flush()

    # Pas de tenant_context → current_setting retourne ''
    # cast '' to bigint → erreur OU 0 selon config
    # Avec policy USING (tenant_id = current_setting(...)::bigint), comparison NULL → false
    # → 0 rows
    result = await db.execute(select(Customer))
    assert len(result.scalars().all()) == 0
```

## Definition of Done

- [ ] Migration `c1d2e3f4a5b7` upgrade/downgrade testée sur staging avec snapshot prod
- [ ] 3 tests intégration verts (RLS enabled, cross-tenant blocked, no-context fail-closed)
- [ ] Test perf : régression latence P95 < 5% (RLS overhead réel mesuré)
- [ ] Rôles `devup_app` + `devup_superadmin` créés en staging + prod
- [ ] CI invariant `check_rls_enabled_on_tenant_tables.py` (54 §13) vert

## Risque

- Probabilité 3, impact 5 → score 15 HIGH (cf. R13 disponibilité perf RLS)
- **Plan rollback** : downgrade migration c1d2e3f4a5b7 (RLS désactivé, retour comportement actuel)
- **Mitigation** : déploiement progressif staging 7j avant prod, monitoring latence DB

---

# Story B1.S2.T3 — Migration outbox RLS custom NULL

## Contexte

**Migration** : `c1d2e3f4a5ba` (cf. `51-alembic-migrations.md`)
**Sévérité** : P0 — sans cette policy custom, dispatcher Outbox aveugle (events globaux `tenant_id NULL` filtrés)

### Description

`outbox.tenant_id` est `NULLABLE` (cf. `50-sql-schema.md §1.2 ligne 103-104`) car les events globaux DEVUP-level (`TenantProvisioned`, `BeatHeartbeat`, migrations cross-tenant) n'ont pas de tenant. La policy générique `tenant_id = current_setting(...)::bigint` filtre silencieusement les NULL → dispatcher voit 0 events globaux.

**Cf. P0-5 vague 1** — déjà identifié et corrigé dans `51-alembic-migrations.md` (B1.S2.T3 = livre la migration).

## Solution

```python
# alembic/versions/c1d2e3f4a5ba_outbox_rls_null_tenant.py (déjà spécifiée 51 §c1d2e3f4a5ba)
"""Outbox RLS policy with NULL tenant exception.

Revision ID: c1d2e3f4a5ba
Revises: c1d2e3f4a5b9
"""
def upgrade() -> None:
    op.execute("ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY tenant_isolation_outbox_events ON outbox_events
            USING (
                tenant_id IS NULL
                OR tenant_id = current_setting('app.current_tenant_id', true)::bigint
            )
            WITH CHECK (
                tenant_id IS NULL
                OR tenant_id = current_setting('app.current_tenant_id', true)::bigint
            );
    """)
    op.execute("ALTER TABLE outbox_events FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("ALTER TABLE outbox_events NO FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_outbox_events ON outbox_events;")
    op.execute("ALTER TABLE outbox_events DISABLE ROW LEVEL SECURITY;")
```

## Tests

```python
@pytest.mark.asyncio
async def test_outbox__null_tenant_event_visible_to_dispatcher(db):
    """Events globaux (tenant_id NULL) doivent être lisibles par le dispatcher."""
    from app.models import OutboxEvent
    from app.core.database import tenant_context

    global_event = OutboxEvent(
        tenant_id=None,
        event_type="BeatHeartbeat",
        aggregate_type="System",
        payload={"timestamp": "2026-04-27T10:00:00Z"},
        status="pending",
    )
    db.add(global_event)
    await db.flush()

    # Dispatcher tourne SANS tenant_context (rôle BYPASSRLS partial)
    # OU avec contexte spécifique : doit voir le NULL event quand même
    result = await db.execute(select(OutboxEvent).where(OutboxEvent.tenant_id.is_(None)))
    events = result.scalars().all()
    assert global_event.id in {e.id for e in events}


@pytest.mark.asyncio
async def test_outbox__tenant_event_filtered_by_context(db, tenant, other_tenant):
    """Events tenant-scoped suivent la policy normale."""
    from app.models import OutboxEvent
    from app.core.database import tenant_context

    event_a = OutboxEvent(tenant_id=tenant.id, event_type="ResaCreated", ...)
    event_b = OutboxEvent(tenant_id=other_tenant.id, event_type="ResaCreated", ...)
    db.add_all([event_a, event_b])
    await db.flush()

    with tenant_context(tenant.id):
        result = await db.execute(select(OutboxEvent).where(OutboxEvent.tenant_id.is_not(None)))
        ids = {e.id for e in result.scalars().all()}
        assert event_a.id in ids
        assert event_b.id not in ids
```

## Definition of Done

- [ ] Migration `c1d2e3f4a5ba` testée upgrade/downgrade
- [ ] 2 tests intégration verts (NULL visible, tenant filtered)
- [ ] Worker dispatcher Celery testé : voit bien les events NULL en staging

## Risque

- Probabilité 1, impact 4 → score 4 LOW (policy custom isolée)

---

# Story B1.S2.T4 — Tests E2E cross-tenant isolation

## Contexte

**Sévérité** : P0 — validation finale RLS bout-en-bout (User + ApiKey + Celery worker)

### Description

3 chemins d'accès DB doivent être validés avec RLS active :
1. **User HTTP** : login → JWT → set_tenant_context → query
2. **ApiKey HTTP** : X-API-Key → set_tenant_context → query (B1.S1.T2 préalable)
3. **Celery worker** : task triggered → tenant_context wrapper → query

## Solution

```python
# tests/e2e/test_rls_cross_tenant_isolation.py

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_user_cannot_query_other_tenant(authenticated_client, db, tenant, other_tenant):
    """User A se connecte → ne voit que data tenant A."""
    customer_a = Customer(tenant_id=tenant.id, nom="A")
    customer_b = Customer(tenant_id=other_tenant.id, nom="B")
    db.add_all([customer_a, customer_b])
    await db.flush()

    response = await authenticated_client.get("/api/v1/customers")
    assert response.status_code == 200
    customers = response.json()["items"]
    ids = {c["id"] for c in customers}
    assert str(customer_a.id) in ids
    assert str(customer_b.id) not in ids


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_apikey_cannot_query_other_tenant(client, db, tenant, other_tenant):
    """ApiKey tenant A → ne voit que data tenant A (RLS via set_tenant_context F02 fix)."""
    from app.models import ApiKey
    raw_key = "test-key-tenant-a"
    api_key = ApiKey(
        tenant_id=tenant.id,
        key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
        is_active=True,
    )
    db.add(api_key)
    customer_b = Customer(tenant_id=other_tenant.id, nom="B")
    db.add(customer_b)
    await db.flush()

    response = await client.get("/api/v1/customers", headers={"X-API-Key": raw_key})
    assert response.status_code == 200
    ids = {c["id"] for c in response.json()["items"]}
    assert str(customer_b.id) not in ids


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_celery_task_respects_tenant_context(db, tenant, other_tenant):
    """Task Celery avec tenant_context isolation."""
    from app.tasks.example import process_tenant_data
    customer_a = Customer(tenant_id=tenant.id, nom="A")
    customer_b = Customer(tenant_id=other_tenant.id, nom="B")
    db.add_all([customer_a, customer_b])
    await db.flush()

    # Tâche tenant A
    result = await process_tenant_data.delay(tenant_id=tenant.id).get()
    assert customer_a.id in result["customer_ids"]
    assert customer_b.id not in result["customer_ids"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_repo_method_without_set_tenant_context__returns_empty(db, tenant):
    """Si un dev oublie set_tenant_context, RLS retourne 0 rows (fail-closed safe)."""
    customer = Customer(tenant_id=tenant.id, nom="A")
    db.add(customer)
    await db.flush()

    # Direct query sans context — fail-closed
    result = await db.execute(select(Customer))
    customers = result.scalars().all()
    assert len(customers) == 0  # RLS bloque par défaut
```

## Definition of Done

- [ ] 4 tests E2E verts en staging
- [ ] Validation manuelle : créer ApiKey Marveline, hit endpoint avec X-API-Key sur env Splendid → 401 OU liste vide

---

# Story B1.S2.T5 — Migration step-by-step pré-prod

## Contexte

Déploiement RLS = changement structurel risqué. Pattern 4 étapes (cf. `51-alembic-migrations.md §pattern backward-compatible`) :

### Plan de déploiement

**Étape 1 (J-7 staging)** : Déployer migration `c1d2e3f4a5b7` + `c1d2e3f4a5ba` sur staging avec snapshot prod
- Run smoke tests E2E
- Mesurer latence P95 sur 100 endpoints critiques (baseline vs RLS)
- Si régression > 10% → optimiser policies (indexes sur `tenant_id` partout)

**Étape 2 (J-3 staging)** : Activer pour 1 tenant test (`marveline-staging`) en prod-like config
- Monitor 72h : 0 erreur 500 attendue
- Vérifier dashboards Grafana cardinalité tenant_id labels

**Étape 3 (J-0 prod)** : Migration appliquée sur prod en maintenance window 30min (1h00 UTC)
- Pre-flight check : `SELECT count(*) FROM tenants WHERE app_code IS NULL` = 0
- Apply migrations
- Post-flight : `SELECT count(*) FROM customers WHERE tenant_id IS NULL` = 0
- Smoke tests post-deploy

**Étape 4 (J+7 prod)** : Validation continue
- Audit Loki : 0 erreur "RLS policy violation"
- Métriques `db_query_duration_seconds` régression < 5%

### Plan rollback

Si régression critique en post-deploy :
1. Downgrade migration `c1d2e3f4a5ba` (outbox RLS custom)
2. Downgrade migration `c1d2e3f4a5b7` (RLS general)
3. Retour comportement avant — aucune perte data
4. Post-mortem 72h → re-tenter avec mitigations

## Definition of Done

- [ ] Plan déploiement validé Lead + Ops
- [ ] Maintenance window planifiée (annonce clients J-7)
- [ ] Smoke tests automatisés (`pytest -m smoke_rls`) prêts
- [ ] Plan rollback documenté + script `tools/rollback_rls.sh`

---

## Critères de succès Sprint B1.S2

- [ ] **80 tables** ont RLS enabled + FORCE
- [ ] **outbox** a sa policy custom NULL-tolerant
- [ ] **3 chemins** d'accès DB validés (User, ApiKey, Celery)
- [ ] **0 régression latence** P95 > 10%
- [ ] **CI invariant `check_rls_enabled_on_tenant_tables.py`** vert
- [ ] **MEMORY.md à jour** : Q2=A appliqué

## Dépendances downstream débloquées

- **B1.S3** (KMS) : peut commencer (KMS context inclut tenant_id, validé par RLS)
- **B2.\*** (Identity) : sécurité tenant DB-level garantie
- **B3-B7** : tous les blocs métier dépendent de RLS pour leurs invariants cross-tenant

---

**Fin du document — 11-sprint-B1.S2.md**
