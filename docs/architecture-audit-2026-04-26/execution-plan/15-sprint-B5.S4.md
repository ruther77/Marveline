# Sprint B5.S4 — Celery tenant-aware + advisory lock idempotence ETL + IdfCorpus per-call + AWAITING_VENDOR_MATCH

> **STATUT** : ⏳ À démarrer après B5.S3
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev3
> **BLOQUE** : B5.S5 (categorie_id FK), B5.S6 (TransferRequest workflow)
> **DÉPEND DE** : B5.S2 (tenant_id ETL NOT NULL), B5.S3 (FSM ETL)
> **OBJECTIF** : Rendre tous les Celery tasks ETL **tenant-aware** (TR-48) avec linter CI vérifiant arg `tenant_id` partout. Livrer advisory lock idempotence ETL (TR-49 — retry après commit partiel ne double-import plus). Refactorer `_global_idf` singleton → `IdfCorpus` per-call (TR-50). Implémenter queue `AWAITING_VENDOR_MATCH` pour vendor inconnu (TR-51, Q33=B).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B5.S4.T1** | TR-48 — Celery tasks ETL arg `tenant_id` mandatory + linter CI `check_celery_tenant_arg.py` | P0 | 1.5 j | T2 |
| **B5.S4.T2** | TR-49 — Advisory lock per-import idempotence (retry safe) | P0 | 1 j | aucun |
| **B5.S4.T3** | TR-50 — `IdfCorpus` per-call (drop `_global_idf` singleton) | P0 | 1.5 j | aucun |
| **B5.S4.T4** | TR-51 / Q33=B — Vendor matching strict + queue `AWAITING_VENDOR_MATCH` + endpoint resolve | P0 | 2 j | aucun |
| **B5.S4.T5** | F1110 — Linter CI vérifie aussi tenant_id sur tasks non-ETL (general purpose) | P1 | 0.5 j | aucun |
| **B5.S4.T6** | TR-52 / F907 — Smart `stock_alerte = moyenne_consommation_7j × 2` calcul ETL + backfill | P1 | 1 j | aucun |

**Total effort** : 7.5 jours-homme.

---

# Story B5.S4.T1 — Celery tenant-aware + linter CI (TR-48)

## Contexte

**Friction** : TR-48, F960 (cf. `architecture-cible.md §5.1`)
**Sévérité** : P0 — `run_etl_import` sans arg `tenant_id` → validation tenant via `EtlImport.target_tenant_id` non vérifié = forge possible
**Code source** : `app/workers/tasks/etl/run_etl_import.py`

### Description

Cible :
1. Tous les Celery tasks ETL acceptent `tenant_id: int` en argument explicite
2. Au début du task : `SET LOCAL app.current_tenant_id = :tenant_id` pour RLS
3. Linter CI `tools/check_celery_tenant_arg.py` parse l'AST et vérifie chaque `@shared_task` (sauf whitelist beat tasks).

## Solution

### Refacto tasks

```python
# app/workers/tasks/etl/run_etl_import.py
@shared_task(name="run_etl_import")
def run_etl_import_task(import_id: str, tenant_id: int):  # tenant_id mandatory
    async def _run():
        async with AsyncSessionLocal() as db:
            # Set RLS context
            await db.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": tenant_id})
            
            imp = await db.get(EtlImport, UUID(import_id))
            if imp.target_tenant_id != tenant_id:
                raise SecurityError(f"Tenant mismatch: import.target={imp.target_tenant_id}, arg={tenant_id}")
            # ... logique ETL
    asyncio.run(_run())
```

### Caller (endpoint)

```python
# app/api/v1/endpoints/etl.py
@router.post("/etl/imports/{import_id}/run")
async def run_etl_import(
    import_id: UUID,
    user: User = Depends(require_scope(Scope.ETL_WRITE)),
):
    task = run_etl_import_task.delay(str(import_id), user.tenant_id)
    return {"task_id": task.id}
```

### Linter CI

```python
# tools/check_celery_tenant_arg.py
"""Refuse les @shared_task qui n'ont pas `tenant_id: int` en argument
(sauf whitelist tasks de beat globaux : verify_audit_chain, refresh_rfm_view, etc.).
"""
import ast, sys
from pathlib import Path

WHITELIST = {
    "verify_audit_chain",
    "refresh_rfm_view",
    "refresh_stock_view",
    "purge_audit_logs_older_than_7y",
    # tasks dont le contexte est explicitement "tous tenants" — boucle interne sur tenants.id
}

violations = []
for py in Path("app/workers/tasks").rglob("*.py"):
    tree = ast.parse(py.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            decorators = [d for d in node.decorator_list if isinstance(d, ast.Call) and getattr(d.func, "attr", None) == "task"]
            if not decorators:
                continue
            task_name = next((kw.value.value for d in decorators for kw in d.keywords if kw.arg == "name"), node.name)
            if task_name in WHITELIST:
                continue
            args = [a.arg for a in node.args.args]
            if "tenant_id" not in args:
                violations.append(f"{py}:{node.lineno} — task '{task_name}' manque arg `tenant_id`")

if violations:
    print("❌ Tenant-aware violations :")
    print("\n".join(f"  - {v}" for v in violations))
    sys.exit(1)
print("✅ All Celery tasks are tenant-aware")
```

### Tests

```python
async def test_etl_import_task_with_wrong_tenant_id_refused(db, import_record):
    """Tâche appelée avec tenant_id = 99 mais import.target_tenant_id = 1 → SecurityError."""
    with pytest.raises(SecurityError, match="Tenant mismatch"):
        run_etl_import_task.apply(args=(str(import_record.id), 99)).get()

async def test_lint_celery_tenant_arg_passes():
    result = subprocess.run([sys.executable, "tools/check_celery_tenant_arg.py"], capture_output=True)
    assert result.returncode == 0
```

## DoD

- [ ] Tous tasks ETL acceptent `tenant_id: int`
- [ ] `SET LOCAL app.current_tenant_id` au début de chaque task
- [ ] SecurityError si `tenant_id` arg ≠ `import.target_tenant_id`
- [ ] Linter `tools/check_celery_tenant_arg.py` actif CI
- [ ] Whitelist tasks beat globaux documentée

---

# Story B5.S4.T2 — Advisory lock idempotence ETL (TR-49)

## Contexte

**Friction** : TR-49, F964, ETL-DUPE-01 résolu partiellement 2026-04-21
**Sévérité** : P0 — retry après commit partiel double-import
**Code source** : `app/workers/tasks/etl/run_etl_import.py`

### Description

Cible : avant tout traitement, prendre un advisory lock per `import_id` :
- `pg_advisory_xact_lock(hashtext('etl_import:' || import_id))`
- Si déjà détenu (autre worker en cours) → exit gracieux
- Si déjà finalisé (status final) → exit no-op

## Solution

```python
# app/workers/tasks/etl/run_etl_import.py
@shared_task(name="run_etl_import")
def run_etl_import_task(import_id: str, tenant_id: int):
    async def _run():
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": tenant_id})
            
            async with db.begin():
                # Advisory lock per import — release fin de TX
                await db.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext('etl_import:' || :iid))"),
                    {"iid": import_id},
                )
                
                imp = await db.execute(
                    select(EtlImport).where(EtlImport.id == UUID(import_id)).with_for_update()
                )
                imp = imp.scalar_one()
                if imp.statut in ("SUCCES", "PARTIEL", "ECHEC"):
                    logger.info("etl_import_already_finalized", import_id=import_id)
                    return  # idempotent

                # ... traitement ETL
                # Finalisation : statut SUCCES/PARTIEL/ECHEC + commit
    asyncio.run(_run())
```

### Test

```python
async def test_etl_import_retry_idempotent(db, import_record):
    # 1ère exécution : SUCCES
    run_etl_import_task.apply(args=(str(import_record.id), tenant.id)).get()
    nb_lignes_apres_run1 = (await db.get(EtlImport, import_record.id)).nb_lignes_valides
    
    # 2e exécution (simulate retry) : no-op
    run_etl_import_task.apply(args=(str(import_record.id), tenant.id)).get()
    nb_lignes_apres_run2 = (await db.get(EtlImport, import_record.id)).nb_lignes_valides
    
    assert nb_lignes_apres_run1 == nb_lignes_apres_run2  # pas de double-import
```

## DoD

- [ ] Advisory lock per `import_id`
- [ ] Exit no-op si statut final
- [ ] Test retry idempotence
- [ ] Cohérent avec ETL-DUPE-01 fix 2026-04-21

---

# Story B5.S4.T3 — `IdfCorpus` per-call (TR-50)

## Contexte

**Friction** : TR-50, F967
**Sévérité** : P0 — `_global_idf` singleton mutable → 2 imports parallèles → IDF écrasé mid-batch → scores Soft TF-IDF incohérents
**Code source** : `app/services/etl/parsers/_shared/idf.py`

### Description

Cible : drop le singleton, instancier `IdfCorpus` par appel ETL.

## Solution

```python
# app/services/etl/parsers/_shared/idf.py (refacto)
from dataclasses import dataclass

@dataclass
class IdfCorpus:
    """IDF computed for a specific corpus (per ETL import call)."""
    document_count: int
    term_doc_freq: dict[str, int]

    def idf(self, term: str) -> float:
        df = self.term_doc_freq.get(term, 0)
        return math.log((self.document_count + 1) / (df + 1)) + 1

    @classmethod
    def from_corpus(cls, documents: list[str]) -> "IdfCorpus":
        term_doc_freq: dict[str, int] = defaultdict(int)
        for doc in documents:
            terms_in_doc = set(_tokenize(doc))
            for t in terms_in_doc:
                term_doc_freq[t] += 1
        return cls(document_count=len(documents), term_doc_freq=dict(term_doc_freq))


# app/services/etl/parsers/_shared/soft_tfidf.py (refacto)
class SoftTfidfMatcher:
    def __init__(self, idf_corpus: IdfCorpus):  # injection au lieu de global
        self.idf = idf_corpus

    def match(self, query: str, candidates: list[str]) -> tuple[str, float]:
        # ... utilise self.idf
```

```python
# app/workers/tasks/etl/run_etl_import.py
async def run_import(import_id, tenant_id):
    # Build IDF corpus from ce tenant's catalogue
    catalogue = await db.scalars(
        select(CatalogueProduit.libelle).where(CatalogueProduit.tenant_id == tenant_id)
    )
    idf_corpus = IdfCorpus.from_corpus([c for c in catalogue.all()])
    
    matcher = SoftTfidfMatcher(idf_corpus)  # local instance per call
    # ... traitement
```

### Test

```python
async def test_idf_corpus_isolated_between_imports(db, tenant_a, tenant_b):
    # Tenant A : catalogue avec "POMMES GLUNEX"
    # Tenant B : catalogue sans "POMMES"
    corpus_a = IdfCorpus.from_corpus(["POMMES GLUNEX 6 1KG"])
    corpus_b = IdfCorpus.from_corpus(["TOMATES BIO 500G"])
    
    # IDF(POMMES) doit différer
    assert corpus_a.idf("pommes") != corpus_b.idf("pommes")

async def test_no_global_idf_state(db):
    # Run 2 imports parallèles, vérifier qu'aucun ne capture le corpus de l'autre
    # (test concurrence)
    pass
```

## DoD

- [ ] `IdfCorpus` dataclass per-call
- [ ] Drop `_global_idf` singleton
- [ ] `SoftTfidfMatcher` accepte injection
- [ ] Test isolation cross-tenants
- [ ] Test concurrence : 2 imports parallèles sans cross-pollution

---

# Story B5.S4.T4 — Vendor matching strict + AWAITING_VENDOR_MATCH (Q33=B)

## Contexte

**Friction** : TR-51, F980 (cf. `architecture-cible.md Q33=B`)
**Sévérité** : P0 — auto-création silent `FinanceVendor` sur typo vendor_code → référentiel pollué

### Description

Décision Q33=B : vendor_code inconnu → `EtlImport.statut = 'AWAITING_VENDOR_MATCH'` + email admin tenant. Endpoint `POST /etl/imports/{id}/resolve-vendor` avec choix link existant ou create explicit.

## Solution

```python
# app/services/etl/vendor_resolver.py (refacto)
class VendorResolver:
    async def resolve(self, vendor_code: str, tenant_id: int) -> FinanceVendor:
        vendor = await self.db.scalar(
            select(FinanceVendor).where(
                FinanceVendor.code == vendor_code,
                FinanceVendor.tenant_id == tenant_id,
            )
        )
        if vendor is None:
            # ❌ AVANT : auto-create silent
            # ✅ APRÈS : raise pour escalade vers AWAITING
            raise VendorNotFound(vendor_code=vendor_code, tenant_id=tenant_id)
        return vendor


# app/workers/tasks/etl/run_etl_import.py
async def run_import(...):
    try:
        vendor = await vendor_resolver.resolve(parsed.vendor_code, tenant_id)
    except VendorNotFound:
        imp.statut = "AWAITING_VENDOR_MATCH"
        imp.awaiting_vendor_code = parsed.vendor_code
        # Email admin tenant
        await email_gateway.send(
            to=admin_email,
            subject=f"Import ETL en attente: vendor inconnu '{parsed.vendor_code}'",
            body_html=render("vendor_match_required.html.j2", {"import_id": imp.id, "vendor_code": parsed.vendor_code}),
            tenant_id=tenant_id,
        )
        return
```

### Endpoint resolve

```python
# app/api/v1/endpoints/etl.py
@router.post("/etl/imports/{import_id}/resolve-vendor")
async def resolve_vendor(
    import_id: UUID,
    payload: ResolveVendorPayload,  # {action: 'link' | 'create', vendor_id?: int, new_vendor_data?: dict}
    user: User = Depends(require_scope(Scope.ETL_WRITE)),
):
    imp = await db.get(EtlImport, import_id)
    if imp.statut != "AWAITING_VENDOR_MATCH":
        raise HTTPException(409, "Import not awaiting vendor match")
    
    if payload.action == "link":
        vendor = await db.get(FinanceVendor, payload.vendor_id)
    elif payload.action == "create":
        vendor = FinanceVendor(tenant_id=user.tenant_id, **payload.new_vendor_data)
        db.add(vendor)
        await db.flush()
    
    imp.resolved_vendor_id = vendor.id
    imp.statut = "VALIDATING"
    await db.commit()
    
    # Re-trigger ETL
    run_etl_import_task.delay(str(import_id), user.tenant_id)
    return {"status": "queued"}
```

### Tests

```python
async def test_unknown_vendor_marks_awaiting(db, tenant, etl_import_with_unknown_vendor):
    run_etl_import_task.apply(args=(str(etl_import_with_unknown_vendor.id), tenant.id)).get()
    await db.refresh(etl_import_with_unknown_vendor)
    assert etl_import_with_unknown_vendor.statut == "AWAITING_VENDOR_MATCH"

async def test_resolve_vendor_link_existing(client, etl_awaiting, existing_vendor):
    response = await client.post(
        f"/api/v1/etl/imports/{etl_awaiting.id}/resolve-vendor",
        json={"action": "link", "vendor_id": existing_vendor.id},
    )
    assert response.status_code == 200
    await db.refresh(etl_awaiting)
    assert etl_awaiting.statut == "VALIDATING"
```

## DoD

- [ ] Drop auto-create vendor silent
- [ ] `EtlImport.statut = AWAITING_VENDOR_MATCH` si inconnu
- [ ] Email admin envoyé via EmailGateway (B3.S5)
- [ ] Endpoint `/resolve-vendor` link/create
- [ ] FSM matrix `etl_import` inclut transition `AWAITING_VENDOR_MATCH → VALIDATING` (B5.S3.T1)
- [ ] Test : vendor inconnu → AWAITING ; resolve → VALIDATING

---

# Story B5.S4.T5 — Linter tenant_id sur tasks non-ETL

## Contexte

Élargir T1 à tous les Celery tasks (non juste ETL).

### Description

Réviser whitelist + ajouter scan complet `app/workers/tasks/`.

## Solution

Idem T1 mais portée élargie. Whitelist documentée : tasks beat globaux qui itèrent sur tenants en interne.

## DoD

- [ ] Linter scan tous les `app/workers/tasks/`
- [ ] Whitelist explicite (verify_audit_chain, refresh_rfm_view, refresh_stock_view, purge_audit_logs_older_than_7y, expire_devis, expire_points, dunning_orchestrator, loyalty_revenue_window_recompute)
- [ ] Tasks non whitelistés sans `tenant_id` → CI fail

---

# Story B5.S4.T6 — Smart `stock_alerte` (TR-52 / F907)

## Contexte

**Friction** : TR-52, F907
**Sévérité** : P1 — `stock_alerte=0` default = aucune alerte ne déclenche jamais

### Description

Cible :
1. Compute `stock_alerte = round(moyenne_consommation_7j × 2)` au calcul ETL
2. Backfill historique sur produits existants
3. Recompute hebdo via Celery task

## Solution

```python
# app/services/epicerie/stock_alert_resolver.py (NEW)
class StockAlertResolver:
    async def compute_and_set(self, produit_id: UUID, tenant_id: int):
        # Moyenne consommation 7j
        sum_consumed = await self.db.scalar(
            select(func.coalesce(func.sum(EpicerieStockMovement.qty), 0))
            .where(
                EpicerieStockMovement.produit_id == produit_id,
                EpicerieStockMovement.type == "VENTE",
                EpicerieStockMovement.created_at >= datetime.now(UTC) - timedelta(days=7),
            )
        )
        avg_per_day = sum_consumed / 7
        new_alert = max(1, int(avg_per_day * 2))
        await self.db.execute(
            update(EpicerieProduit).where(EpicerieProduit.id == produit_id).values(stock_alerte=new_alert)
        )
```

### Celery task hebdo

```python
@shared_task(name="recompute_stock_alerts")
def recompute_stock_alerts_task(tenant_id: int):
    async def _run():
        async with AsyncSessionLocal() as db:
            produits = await db.scalars(
                select(EpicerieProduit.id).where(EpicerieProduit.tenant_id == tenant_id)
            )
            for pid in produits.all():
                await resolver.compute_and_set(pid, tenant_id)
    asyncio.run(_run())
```

### Beat schedule

```python
celery_app.conf.beat_schedule["recompute-stock-alerts-weekly"] = {
    "task": "recompute_stock_alerts",
    "schedule": crontab(day_of_week=1, hour=4, minute=0),  # lundi 04:00
    # tenant_id loop iterates dans le task
}
```

## DoD

- [ ] Service `StockAlertResolver` compute moyenne 7j × 2
- [ ] Celery task hebdo
- [ ] Backfill historique : run task pour chaque tenant existant
- [ ] Test : produit avec 35 ventes/7j → stock_alerte = 10

---

## Critères de succès Sprint B5.S4

- [ ] **TR-48 résolu** : tous Celery tasks ETL `tenant_id` mandatory + linter CI
- [ ] **TR-49 résolu** : advisory lock idempotence retry
- [ ] **TR-50 résolu** : `IdfCorpus` per-call, drop singleton
- [ ] **TR-51 / Q33=B résolu** : AWAITING_VENDOR_MATCH queue + endpoint resolve
- [ ] **TR-52 / F907 résolu** : smart stock_alerte
- [ ] Test E2E : ETL retry → idempotent ; vendor inconnu → AWAITING + email

---

**Fin du document — 15-sprint-B5.S4.md**
