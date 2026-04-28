# Sprint B4.S1 — Hotfixes catalogue

> **STATUT** : ⏳ À démarrer après Bloc 2 + B3.S1
> **DURÉE MAX** : 1 semaine
> **OWNER** : Dev2
> **BLOQUE** : B4.S2 (StockItemFSM consomme release_n strict), B4.S4 (PricingEngine fusion)
> **DÉPEND DE** : B2.S3 (RBAC unifié + scopes)
> **OBJECTIF** : Corriger les frictions catalogue P0 immédiates avant les refontes structurelles : F486 (`require_scope` sur 5 endpoints catalogue), F530 (PricingEngine `÷100` vs `÷10000` divergence), préparation F641 release_n strict (signature pré-B4.S2), audit cohérence reference UNIQUE per-tenant catalogue (vérification post-B3.S1.T4).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B4.S1.T1** | TR-19/F486 — `require_scope(PRODUCTS_READ)` sur 5 endpoints catalogue | P0 | 1 j | aucun |
| **B4.S1.T2** | TR-21/F530 — Unification convention `÷100` PricingEngine + `/pricing/simulate` | P0 | 1 j | B4.S4 |
| **B4.S1.T3** | F641 prep — `release_n(reservation_id=...)` signature mandatory côté Python (CI ; fix complet B4.S2) | P0 | 0.5 j | B4.S2 |
| **B4.S1.T4** | F767/F826/F827 verify — audit cohérence reference UNIQUE per-tenant Catalogue (Bundle/Collection si existant) | P1 | 0.5 j | aucun |
| **B4.S1.T5** | F507 — `Bundle.is_active` filtre dans repository list | P1 | 0.5 j | aucun |
| **B4.S1.T6** | Audit + Outbox sur mutations Catalogue (Product/Bundle/Category) — pattern décorateur Bloc 6 | P1 | 1 j | B6.S2 |

**Total effort** : 4.5 jours-homme.

---

# Story B4.S1.T1 — `require_scope(PRODUCTS_READ)` sur 5 endpoints catalogue (TR-19/F486)

## Contexte

**Friction** : TR-19, F486 (cf. `architecture-cible.md §4.2.6`)
**Sévérité** : P0 — User avec scope `customers:read` accède au catalogue intégral (escalation horizontale)
**Code source** : `app/api/v1/endpoints/products.py`, `bundles.py`

### Description

Aujourd'hui : 5 endpoints `GET /products*` utilisent `Depends(get_current_user)` au lieu de `Depends(require_scope(Scope.PRODUCTS_READ))`. Conséquences :
- User avec scope `customers:read` uniquement → consultation catalogue interdite
- API key avec scope limité → idem (F407 amplifie)

Endpoints concernés (à auditer puis fixer) :
- `GET /products`
- `GET /products/{id}`
- `GET /products/search`
- `GET /products/{id}/variants`
- `GET /products/{id}/availability`

## Solution

```python
# app/api/v1/endpoints/products.py — avant
@router.get("/products")
async def list_products(user: User = Depends(get_current_user)):
    ...

# après
@router.get("/products")
async def list_products(user: User = Depends(require_scope(Scope.PRODUCTS_READ))):
    ...
```

Auditer aussi `POST/PATCH/DELETE` → doit être `PRODUCTS_WRITE`.

### Test

```python
async def test_get_products_requires_products_read(client_with_only_customers_read):
    response = await client_with_only_customers_read.get("/api/v1/products")
    assert response.status_code == 403
    assert "products:read" in response.json()["detail"]

async def test_get_products_ok_with_products_read(client_with_products_read):
    response = await client_with_products_read.get("/api/v1/products")
    assert response.status_code == 200
```

### Script CI

Rappel : `tools/check_endpoint_scopes.py` (déjà livré B6) parcourt l'AST et vérifie qu'aucun `@router.get/post/patch/delete` n'utilise `Depends(get_current_user)` direct (sauf whitelist `/health`, `/metrics`).

## DoD

- [ ] 5 endpoints catalogue migrés vers `require_scope(PRODUCTS_READ)`
- [ ] Endpoints write migrés vers `PRODUCTS_WRITE`
- [ ] Test : sans scope → 403 ; avec scope → 200
- [ ] Script CI `check_endpoint_scopes.py` passe vert sur catalogue

---

# Story B4.S1.T2 — Unification convention `÷100` PricingEngine (TR-21/F530)

## Contexte

**Friction** : TR-21, F530 (cf. `architecture-cible.md §4.2.5`)
**Sévérité** : P0 — admin simule `-10%` (`/pricing/simulate` ÷10000) → devis applique `-100×` (PricingEngine ÷100)
**Code source** : `app/services/pricing_engine.py`, `app/api/v1/endpoints/pricing.py:simulate`

### Description

Aujourd'hui :
- `PricingEngine.discount_pct` stocké en Integer (10 = 10%) — division par 100
- `/pricing/simulate` retourne discount en Integer (1000 = 10.00%) — division par 10000

→ admin saisit "10" → simulate calcule comme `10/10000 = 0.1%` → preview correcte
→ devis applique `10/100 = 10%` → catastrophique

**Cible** : convention unique `Numeric(5,4)` (ex: `0.10` pour 10%) cohérente avec B3.S3.T1 et B3.S3.T2 PricingEngine. Migration backfill Integer → Decimal.

## Solution

### Migration

```python
# alembic/versions/h1a2b3c4d5f5_pricing_rules_discount_pct_decimal.py
def upgrade() -> None:
    op.add_column("pricing_rules", sa.Column("discount_pct_new", sa.Numeric(5, 4), nullable=True))
    # Backfill : Integer → Decimal selon convention historique
    # Ancien stockage : Integer / 100 → discount factor (10 = 10%)
    op.execute(text("""
        UPDATE pricing_rules SET discount_pct_new = discount_pct::numeric / 100
    """))
    op.alter_column("pricing_rules", "discount_pct_new", nullable=False)
    op.create_check_constraint(
        "ck_pricing_rules_discount_range",
        "pricing_rules",
        "discount_pct_new >= 0 AND discount_pct_new <= 1",
    )
    op.drop_column("pricing_rules", "discount_pct")
    op.alter_column("pricing_rules", "discount_pct_new", new_column_name="discount_pct")
```

### Service

```python
# app/services/pricing_engine.py — avant
discount_factor = Decimal(rule.discount_pct) / 100

# après
discount_factor = rule.discount_pct  # déjà Decimal(0.10)
```

### Endpoint /simulate

```python
# app/api/v1/endpoints/pricing.py — avant
return {"discount_pct": result.discount_pct * 10000}  # confusion ÷10000

# après
return {"discount_pct": float(result.discount_pct)}  # 0.10
```

### Test invariant

```python
async def test_pricing_simulate_equals_apply(client, tenant, customer, product):
    """Invariant : /pricing/simulate retourne EXACTEMENT le résultat appliqué par devis."""
    payload = {"customer_id": customer.id, "lines": [{"product_id": product.id, "qty": 1}]}
    sim_response = await client.post("/api/v1/pricing/simulate", json=payload)
    sim_total = sim_response.json()["total_ttc_cents"]

    devis_response = await client.post("/api/v1/devis", json={**payload, "event_date": "2026-09-01"})
    devis_total = devis_response.json()["total_ttc_cents"]

    assert sim_total == devis_total  # même cent
```

## DoD

- [ ] Migration Integer → Numeric(5,4) avec backfill `÷100`
- [ ] CHECK `[0, 1]` actif
- [ ] PricingEngine consomme `Decimal` direct (sans `/100`)
- [ ] `/pricing/simulate` retourne `Decimal` cohérent
- [ ] Test invariant : simulate == apply au cent près

---

# Story B4.S1.T3 — `release_n(reservation_id=...)` signature mandatory (F641 prep)

## Contexte

**Friction** : F641 (TR-23 — résolu complètement en B4.S2.T2)
**Sévérité** : P0 — bug critique non régression : libération aveugle stock items autres résa

### Description

Cette story est le **prep tactique** :
1. Modifier la signature Python pour rendre `reservation_id` mandatory positional (pas keyword default `None`)
2. Ajouter ValueError runtime
3. Ne PAS encore retirer la possibilité côté DB (cf. B4.S2 pour FSM enforcement complet)

Permet à B3 de continuer en parallèle sans dépendance hard sur B4.S2.

## Solution

```python
# app/services/stock.py
class StockService:
    async def release_n(
        self,
        items: list[UUID],
        reservation_id: UUID,  # mandatory positional, pas Optional[UUID] = None
        actor_id: UUID,
        tenant_id: int,
    ) -> int:
        if reservation_id is None:
            raise ValueError(
                "release_n: reservation_id is mandatory (cf. STOCK-RELEASE-BLIND-01 fix 2026-04-25)"
            )
        # ... reste hérite de B4.S2.T2
```

### Test

```python
async def test_release_n_refuses_none_at_b4s1(stock_service):
    with pytest.raises(ValueError, match="reservation_id is mandatory"):
        await stock_service.release_n(items=[uuid4()], reservation_id=None, actor_id=user.id, tenant_id=1)
```

## DoD

- [ ] Signature `release_n(items, reservation_id, actor_id, tenant_id)` sans default
- [ ] ValueError si appel avec None malgré tout
- [ ] Test refus None
- [ ] Note : enforcement complet (filtre SQL strict + FSM trigger) en B4.S2.T2

---

# Story B4.S1.T4 — Audit cohérence reference UNIQUE per-tenant Bundle/Collection

## Contexte

**Pré-requis** : B3.S1.T4 a livré UNIQUE per-tenant sur reservation/devis/invoice/vente. B3.S7.T2 a livré pour supplier_orders. B3.S7.T8 pour evenements. **Cette story** vérifie que Bundle et ProductCollection sont également couverts si applicable.

### Description

Audit :
1. `Bundle.reference` UNIQUE per-tenant ?
2. `ProductCollection.reference` UNIQUE per-tenant ?
3. Si non → migration corrective

## Solution

```python
# alembic/versions/h1a2b3c4d5f6_bundle_collection_reference_unique.py
def upgrade() -> None:
    # Bundle (si reference existe)
    with contextlib.suppress(Exception):
        op.drop_constraint("uq_bundles_reference", "bundles", type_="unique")
    op.create_unique_constraint(
        "uq_bundles_tenant_reference", "bundles", ["tenant_id", "reference"]
    )
    # ProductCollection — drop intégral en B7.S2 si concept brand_code abandonné
    # → Skip si B7.S2 déjà livré
```

### Test

```python
async def test_bundle_reference_unique_per_tenant(db, tenant_a, tenant_b):
    b_a = Bundle(tenant_id=tenant_a.id, reference="MARIAGE-2026-001", name="Mariage 100p")
    b_b = Bundle(tenant_id=tenant_b.id, reference="MARIAGE-2026-001", name="Splendid Mariage")
    db.add_all([b_a, b_b]); await db.commit()  # OK cross-tenant
```

## DoD

- [ ] Audit grep sur les modèles `Bundle.reference`, `ProductCollection.reference`
- [ ] Migration corrective si UNIQUE global présent
- [ ] Test cross-tenant OK

---

# Story B4.S1.T5 — `Bundle.is_active` filtre repository (F507)

## Contexte

**Friction** : F507 (vague 3)
**Sévérité** : P1 — bundle inactivé reste listé sur `GET /bundles` → confusion UI gestionnaire

### Description

Cible : filtre par défaut `is_active=True` dans `BundleRepository.list_active()` ; endpoint admin séparé `/bundles/all` pour voir inactifs.

## Solution

```python
# app/repositories/bundle.py
class BundleRepository:
    async def list_active(self, tenant_id: int) -> list[Bundle]:
        return (await self.db.scalars(
            select(Bundle).where(
                Bundle.tenant_id == tenant_id,
                Bundle.is_active.is_(True),
            )
        )).all()

    async def list_all_admin(self, tenant_id: int) -> list[Bundle]:
        """Admin : voir aussi inactifs."""
        return (await self.db.scalars(
            select(Bundle).where(Bundle.tenant_id == tenant_id)
        )).all()
```

```python
# app/api/v1/endpoints/bundles.py
@router.get("/bundles")
async def list_bundles(user: User = Depends(require_scope(Scope.PRODUCTS_READ))):
    return await repo.list_active(user.tenant_id)

@router.get("/bundles/all", dependencies=[Depends(require_scope(Scope.PRODUCTS_WRITE))])
async def list_all_bundles_admin(user: User = Depends(require_scope(Scope.PRODUCTS_WRITE))):
    return await repo.list_all_admin(user.tenant_id)
```

## DoD

- [ ] `BundleRepository.list_active` filtre `is_active=True`
- [ ] Endpoint admin séparé `/bundles/all`
- [ ] Test : bundle inactivé absent de `/bundles`, présent de `/bundles/all`

---

# Story B4.S1.T6 — Audit + Outbox sur mutations Catalogue

## Contexte

Préparation B6.S2 (audit refondu). Pattern décorateur `@audit_action(entity='Product')` à appliquer aux mutations Catalogue.

### Description

Cible : `ProductService.create/update/delete`, `BundleService.create/update/delete`, `CategoryService.create/update/delete` décorés avec `@audit_action`.

## Solution

```python
# app/services/product.py
from app.services.audit.decorator import audit_action

class ProductService:
    @audit_action(entity_type="Product", action_template="product.{op}")
    async def create(self, **data) -> Product:
        ...

    @audit_action(entity_type="Product", action_template="product.{op}")
    async def update(self, product_id, **changes) -> Product:
        ...

    @audit_action(entity_type="Product", action_template="product.{op}")
    async def delete(self, product_id, actor_id, tenant_id) -> None:
        ...
```

### Test

```python
async def test_product_update_audited(db, product_service):
    product = await product_service.create(name="Chaise", tenant_id=1, actor_id=user.id)
    await product_service.update(product.id, name="Chaise Louis XV", actor_id=user.id, tenant_id=1)

    log = await db.scalar(
        select(AuditLog).where(
            AuditLog.entity_type == "Product",
            AuditLog.entity_id == str(product.id),
            AuditLog.action == "product.update",
        )
    )
    assert log is not None
    assert log.changes == {"name": {"old": "Chaise", "new": "Chaise Louis XV"}}
```

## DoD

- [ ] Décorateur `@audit_action` appliqué aux 9 méthodes services Catalogue
- [ ] Test : mutation Product → AuditLog créé avec diff
- [ ] Outbox event publié dans même TX (B6.S2.T1)

---

## Critères de succès Sprint B4.S1

- [ ] **TR-19/F486 résolu** : 5 endpoints catalogue avec `require_scope(PRODUCTS_READ)`
- [ ] **TR-21/F530 résolu** : convention unique Numeric(5,4) ; simulate == apply au cent
- [ ] **F641 prep** : `release_n(reservation_id=...)` mandatory positional + ValueError
- [ ] **Audit ref UNIQUE** : Bundle / ProductCollection cohérent per-tenant
- [ ] **F507 résolu** : `Bundle.is_active` filtre par défaut
- [ ] Décorateur audit appliqué aux mutations Catalogue
- [ ] Aucune régression : tests E2E catalogue passent

---

**Fin du document — 14-sprint-B4.S1.md**
