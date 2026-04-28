# Sprint B4.S6 — CSV bulk + Bundle.check_availability + cohérence finale

> **STATUT** : ⏳ À démarrer après B4.S5
> **DURÉE MAX** : 1 semaine
> **OWNER** : Dev2
> **BLOQUE** : aucun (sprint final Bloc 4)
> **DÉPEND DE** : B4.S5 (PII chiffré pour respect import CSV), B4.S2 (StockItemFSM)
> **OBJECTIF** : Livrer l'import CSV en bulk transactionnel (TR-31, F446) — 10000 lignes en 1 TX au lieu de 10000 TX. Compléter `Bundle.check_availability(qty)` + `bundle_unit_price_cents` (TR-34, F500/F510). Fix `email_exists/sku_exists` filtre soft-deleted (TR-32, F447/F501). Cleanup final cohérence Bloc 4.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B4.S6.T1** | TR-31/F446 — CSV import bulk transactionnel + COPY FROM PostgreSQL | P0 | 2 j | aucun |
| **B4.S6.T2** | TR-34/F500/F510 — `Bundle.check_availability(qty)` + `BundleItem.bundle_unit_price_cents` | P0 | 1.5 j | aucun |
| **B4.S6.T3** | TR-32/F447/F501 — `email_exists`/`sku_exists` filtre soft-deleted strict (UNIQUE partial WHERE is_active) | P1 | 0.5 j | aucun |
| **B4.S6.T4** | Validation finale Bloc 4 : audit cohérence StockItem + Category + Pricing + PII | P1 | 0.5 j | aucun |

**Total effort** : 4.5 jours-homme.

---

# Story B4.S6.T1 — CSV import bulk transactionnel (TR-31/F446)

## Contexte

**Friction** : TR-31, F446 (cf. `architecture-cible.md §5.1`)
**Sévérité** : P0 — 30 min sur RDS pour 10000 lignes (commit/ligne) → HTTP timeout, UX cassée
**Code source** : `app/services/customers/import_csv.py`

### Description

Aujourd'hui : `for row in csv: await db.commit()` → 10000 TX, latence catastrophique. Cible :
1. Validation préalable (Pydantic) en mémoire
2. `COPY FROM STDIN` PostgreSQL pour insertion bulk
3. 1 TX globale, rollback total si erreur
4. Async background si > 1000 lignes (Celery + status tracking)

## Solution

### Service

```python
# app/services/customers/import_csv.py (refacto)
class CustomerCsvImporter:
    BULK_THRESHOLD = 1000  # > 1000 lignes → async Celery

    async def import_csv(
        self,
        csv_content: bytes,
        tenant_id: int,
        actor_id: UUID,
    ) -> ImportResult:
        # 1. Validation Pydantic en mémoire
        rows = list(csv.DictReader(StringIO(csv_content.decode())))
        validated: list[CustomerCreate] = []
        errors: list[ImportError] = []
        for i, row in enumerate(rows):
            try:
                validated.append(CustomerCreate(**row))
            except ValidationError as e:
                errors.append(ImportError(line=i + 2, errors=e.errors()))

        if errors:
            return ImportResult(status="rejected", errors=errors, count=0)

        # 2. Bulk insert
        if len(validated) > self.BULK_THRESHOLD:
            # Async via Celery
            task = bulk_insert_customers_task.delay(
                tenant_id=tenant_id,
                actor_id=str(actor_id),
                payloads=[c.dict() for c in validated],
            )
            return ImportResult(status="queued", task_id=task.id, count=len(validated))

        # Sync : COPY FROM STDIN dans 1 TX
        async with self.db.begin():
            await self._bulk_insert(validated, tenant_id)
        return ImportResult(status="completed", count=len(validated), errors=[])

    async def _bulk_insert(self, customers: list[CustomerCreate], tenant_id: int):
        """COPY FROM STDIN — 1000× plus rapide qu'INSERT loop."""
        buf = StringIO()
        writer = csv.writer(buf, delimiter="\t")
        for c in customers:
            writer.writerow([
                tenant_id,
                c.email,
                # PII chiffré — note : COPY FROM ne déclenche PAS EncryptedField
                # Donc soit pre-encrypt en Python, soit utiliser INSERT + executemany
                # Pattern safe : INSERT executemany (10× plus lent que COPY mais correct)
            ])

        # Pattern safe pour PII : executemany (pas COPY) qui passe par ORM
        await self.db.execute(
            insert(Customer),
            [c.dict() | {"tenant_id": tenant_id} for c in customers],
        )
        # SQLAlchemy execute many invoque EncryptedField correctement
```

### Celery task async

```python
# app/workers/tasks/bulk_insert_customers.py
@shared_task(name="bulk_insert_customers", bind=True)
def bulk_insert_customers_task(self, tenant_id, actor_id, payloads):
    async def _run():
        async with AsyncSessionLocal() as db:
            async with db.begin():
                await db.execute(insert(Customer), [p | {"tenant_id": tenant_id} for p in payloads])
            await audit_service.log(
                action="customer.bulk_import",
                entity_type="Customer", entity_id="bulk",
                description=f"Bulk import {len(payloads)} customers",
                account_id=UUID(actor_id), tenant_id=tenant_id,
            )
        return len(payloads)
    return asyncio.run(_run())
```

### Test

```python
async def test_csv_import_10k_rows_under_30s(client, csv_file_10k):
    start = time.time()
    response = await client.post("/api/v1/customers/import", files={"file": csv_file_10k})
    elapsed = time.time() - start
    assert response.status_code == 202  # async
    assert elapsed < 5  # endpoint retourne queued en <5s

async def test_csv_validation_errors_rollback_complete(client, csv_with_invalid_email):
    response = await client.post("/api/v1/customers/import", files={"file": csv_with_invalid_email})
    assert response.status_code == 400
    # Vérifier 0 customer créé
    count = await db.scalar(select(func.count(Customer.id)))
    assert count == 0  # rollback complet
```

## DoD

- [ ] Validation Pydantic préalable en mémoire
- [ ] Bulk insert 1 TX globale
- [ ] Async Celery si > 1000 lignes
- [ ] Test 10k lignes < 30s (sync) ou queued < 5s (async)
- [ ] Test rollback : 1 ligne invalide → 0 customer créé

---

# Story B4.S6.T2 — `Bundle.check_availability(qty)` + `bundle_unit_price_cents`

## Contexte

**Friction** : TR-34, F500, F510 (cf. `architecture-cible.md §4.2.11`)
**Sévérité** : P0 — Bundle "Mariage 100 personnes" réservable même si 30 verres manquent ; facturation détaillée impossible

### Description

Cible :
1. `Bundle.check_availability(qty: int) -> bool` — vérifie que pour chaque `BundleItem`, stock disponible >= `qty * bundle_item.qty`
2. `BundleItem.bundle_unit_price_cents BIGINT NULL` — si NULL, prorata depuis `Bundle.price_ttc_cents`. Si non-NULL, prix unitaire de la ligne dans le bundle (facturation détaillée).

## Solution

### Migration

```python
def upgrade() -> None:
    op.add_column("bundle_items", sa.Column("bundle_unit_price_cents", sa.BigInteger, nullable=True))
    op.create_check_constraint(
        "ck_bundle_items_unit_price_positive",
        "bundle_items",
        "bundle_unit_price_cents IS NULL OR bundle_unit_price_cents >= 0",
    )
```

### Service

```python
# app/services/bundle.py
class BundleService:
    async def check_availability(self, bundle_id: int, qty: int, tenant_id: int) -> dict:
        """Renvoie {available: bool, missing_items: [{product, required, available}]}.

        Pour chaque item, vérifie product_stock_view.available >= item.qty * qty.
        """
        bundle = await self.db.get(Bundle, bundle_id, options=[selectinload(Bundle.items)])
        missing = []
        for item in bundle.items:
            stock = await self.db.scalar(
                select(ProductStockView.available)
                .where(
                    ProductStockView.product_id == item.product_id,
                    ProductStockView.tenant_id == tenant_id,
                )
            )
            required = item.qty * qty
            if (stock or 0) < required:
                missing.append({
                    "product_id": item.product_id,
                    "required": required,
                    "available": stock or 0,
                })
        return {"available": len(missing) == 0, "missing_items": missing}

    def line_unit_price_for_item(self, bundle: Bundle, item: BundleItem) -> int:
        """Prix unitaire facturé pour cette ligne du bundle.
        
        Si bundle_unit_price_cents NON NULL → utilisé direct.
        Sinon → prorata : qty_total = sum(items.qty) ; share = item.qty / qty_total ; line = bundle.price * share.
        """
        if item.bundle_unit_price_cents is not None:
            return item.bundle_unit_price_cents
        qty_total = sum(i.qty for i in bundle.items)
        if qty_total == 0:
            return 0
        return bundle.price_ttc_cents * item.qty // qty_total
```

### Endpoint

```python
@router.get("/bundles/{id}/check-availability")
async def check_bundle_availability(
    id: int, qty: int = Query(1, ge=1),
    user: User = Depends(require_scope(Scope.PRODUCTS_READ)),
):
    return await bundle_service.check_availability(id, qty, user.tenant_id)
```

### Tests

```python
async def test_bundle_check_availability_ok(db, tenant, bundle_with_stock):
    result = await service.check_availability(bundle_with_stock.id, qty=2, tenant_id=tenant.id)
    assert result["available"] is True

async def test_bundle_check_availability_missing(db, tenant, bundle):
    # Stock insufficient for one item
    result = await service.check_availability(bundle.id, qty=100, tenant_id=tenant.id)
    assert result["available"] is False
    assert any(m["available"] < m["required"] for m in result["missing_items"])

async def test_bundle_unit_price_explicit_overrides_prorata(db, bundle):
    bundle.items[0].bundle_unit_price_cents = 5000  # explicite
    bundle.price_ttc_cents = 10000
    price = service.line_unit_price_for_item(bundle, bundle.items[0])
    assert price == 5000  # pas prorata
```

## DoD

- [ ] `Bundle.check_availability(qty)` opérationnel
- [ ] `BundleItem.bundle_unit_price_cents` migration
- [ ] Endpoint `/bundles/{id}/check-availability`
- [ ] Test stock insuffisant → missing_items détaillé
- [ ] Test prorata vs explicite

---

# Story B4.S6.T3 — Soft-delete UNIQUE strict (TR-32/F447/F501)

## Contexte

**Friction** : TR-32, F447, F501
**Sévérité** : P1 — `email_exists()` filtre `is_active=True` mais UNIQUE DB est strict → IntegrityError 500 au lieu de 409 propre

### Description

Cible : UNIQUE partial `WHERE is_active=True` côté DB pour cohérence avec service. Permet de re-créer un email après soft-delete.

## Solution

```python
def upgrade() -> None:
    # Drop UNIQUE strict
    with contextlib.suppress(Exception):
        op.drop_constraint("uq_customers_tenant_email", "customers", type_="unique")
    # UNIQUE partial WHERE is_active
    op.create_index(
        "uq_customers_tenant_email_active",
        "customers",
        ["tenant_id", "email"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    # Idem produits/SKU
    op.drop_constraint("uq_products_tenant_sku", "products", type_="unique")
    op.create_index(
        "uq_products_tenant_sku_active",
        "products",
        ["tenant_id", "sku"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
```

### Test

```python
async def test_recreate_customer_after_soft_delete(db, tenant):
    c1 = Customer(tenant_id=tenant.id, email="x@y.com", first_name="A", last_name="B")
    db.add(c1); await db.commit()
    
    # Soft delete
    c1.is_active = False
    await db.commit()
    
    # Re-créer avec même email → OK
    c2 = Customer(tenant_id=tenant.id, email="x@y.com", first_name="C", last_name="D")
    db.add(c2)
    await db.commit()  # OK car partial UNIQUE WHERE is_active

async def test_409_if_email_active_collision(client, customer_active):
    response = await client.post("/api/v1/customers", json={"email": customer_active.email, ...})
    assert response.status_code == 409  # propre, pas 500
```

## DoD

- [ ] UNIQUE partial sur customers + products (et autres tables si applicable)
- [ ] Service retourne 409 propre vs 500 IntegrityError
- [ ] Test : soft-delete puis re-create email → OK
- [ ] Test : conflit email actif → 409

---

# Story B4.S6.T4 — Audit cohérence final Bloc 4

## Contexte

**Sévérité** : P1 — sprint final Bloc 4, audit que tout est cohérent

### Description

Checklist post-Bloc 4 :
1. **StockItem** : FSM enforced + view matérialisée fraîche
2. **Category** : FK obligatoire + cycle prevention + tva_rate
3. **Pricing** : simulate=apply au cent + cumul additif
4. **PII** : 14 colonnes chiffrées + scope `customers:read_pii`
5. **Audit** : `@audit_action` sur tous les services Catalogue
6. **Performance** : view RFM + cache pricing 5min + bulk import

## Solution

### Test E2E cohérence

```python
async def test_bloc4_e2e_marveline_workflow(client, tenant_marveline, customer):
    # 1. Créer Category Marveline (TVA 20%)
    cat = await client.post("/api/v1/categories", json={"code": "chaises", "tva_rate": 0.20, ...})
    
    # 2. Créer Product avec category_id (pas string)
    product = await client.post("/api/v1/products", json={"name": "Chaise Louis XV", "category_id": cat.json()["id"]})
    
    # 3. Réception fournisseur 100 unités → 100 stock_items + view refresh
    await create_supplier_receipt(product["id"], qty=100, unit_cost=2000)
    
    # 4. Devis : check pricing simulate == apply
    sim = await client.post("/api/v1/pricing/simulate", json={"customer_id": customer.id, "lines": [...]})
    devis = await client.post("/api/v1/devis", json={"customer_id": customer.id, "lines": [...]})
    assert sim.json()["total_ttc_cents"] == devis.json()["total_ttc_cents"]
    
    # 5. Conversion devis → resa → invoice émise (B3.S4) avec stock réservé
    await client.post(f"/api/v1/devis/{devis.json()['id']}/convert")
    
    # 6. View matérialisée reflète : available = 100 - qty_reserved
    view = await db.scalar(select(ProductStockView).where(ProductStockView.product_id == product.id))
    assert view.available + view.reserved == 100
    
    # 7. PII customer masqué sans scope read_pii
    customer_response = await client.get(f"/api/v1/customers/{customer.id}")
    assert customer_response.json()["first_name"] == "***"
```

## DoD

- [ ] Test E2E Marveline workflow complet pass
- [ ] Test E2E Splendid workflow (TVA 0.10)
- [ ] Test E2E Restaurant workflow (TVA 0.10 + Category)
- [ ] Audit : checklist 6 points OK

---

## Critères de succès Sprint B4.S6

- [ ] **TR-31 résolu** : CSV import bulk + async Celery > 1000 lignes
- [ ] **TR-34 résolu** : `Bundle.check_availability` + `bundle_unit_price_cents`
- [ ] **TR-32 résolu** : UNIQUE partial `WHERE is_active` sur customers + products
- [ ] Test E2E Bloc 4 complet : Category → Product → Stock → Pricing → Devis → Resa → Invoice
- [ ] **Bloc 4 verrouillé** : 6 sprints livrés (B4.S1 → B4.S6), TR-16 à TR-38 résolus

---

**Fin du document — 14-sprint-B4.S6.md**
