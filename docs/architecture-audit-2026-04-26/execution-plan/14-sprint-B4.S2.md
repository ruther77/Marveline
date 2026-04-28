# Sprint B4.S2 — StockItemFSM + product_stock_view + PMP/WAC

> **STATUT** : ⏳ À démarrer après B4.S1 (parallélisable Bloc 3 sauf T6)
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev2
> **BLOQUE** : B4.S3 (Category FK), B5.S3 (FSM cascade resto/épicerie réutilise pattern)
> **DÉPEND DE** : B3.S2 (FSM helper) — **dépendance hard**.
> **DÉPEND POST-DEPLOY DE** : B3.S7.T4 (trigger receipt sync stock_items) pour validation E2E T6 uniquement.
> **OBJECTIF** : Faire de `StockItem` la **source unique de vérité** stock (TR-17, Q22=A) — drop colonnes denorm `Product.available_quantity`, créer `product_stock_view` matérialisée. Livrer `StockItemFSM` (TR-22) avec matrice DB-enforced + `release_n(reservation_id=...)` mandatory (TR-23, F641). Implémenter PMP/WAC (Q13=A — `inventory_movement.unit_cost_at_entry_cents` + `stock_management.weighted_avg_cost_cents` recalcul à chaque entrée).
>
> **Note Vague 2 cohérence** : T1-T5 indépendants de B3.S7 (ne touchent que `stock_items` existant pré-refonte). Seul T6 nécessite B3.S7.T4 livré (test cohérence E2E supplier_receipt → stock_items → view). Cohérent avec parallélisation Bloc 3+4 du `60-rollout-plan.md` ligne 92.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B4.S2.T1** | TR-22 — StockItemFSM matrice + trigger DB BEFORE UPDATE + CHECK status | P0 | 1.5 j | T2 |
| **B4.S2.T2** | TR-23 — `release_n(reservation_id=...)` mandatory + `transition_n` ValueError si None | P0 | 1 j | aucun |
| **B4.S2.T3** | TR-17 — `product_stock_view` matérialisée + REFRESH CONCURRENTLY trigger debounced 5s | P0 | 2 j | T4 |
| **B4.S2.T4** | TR-17 (cont.) — Drop colonnes denorm + drop `sync_available_from_variants` | P0 | 1 j | aucun |
| **B4.S2.T5** | Q13=A — `inventory_movement.unit_cost_at_entry_cents` + `stock_management.weighted_avg_cost_cents` recalcul WAC | P0 | 1.5 j | aucun |
| **B4.S2.T6** | **Test cohérence post-deploy** StockItem ↔ supplier_receipt (B3.S7.T4 trigger livré) — assert tenant_id propagé. **Marqué post-B3.S7** : story livrable mais validation effective après livraison B3.S7. | P1 | 0.5 j | aucun |

**Total effort** : 7.5 jours-homme.

---

# Story B4.S2.T1 — StockItemFSM matrice + DB enforcement

## Contexte

**Friction** : TR-22 (cf. `architecture-cible.md §4.2.3`)
**Sévérité** : P0 — `StockItem.transition_status` accepte n'importe quelle valeur (ex `damaged → reserved` silencieux)
**Code source** : `app/models/stock_item.py`, `app/services/stock.py:transition_status`

### Description

Cible : matrice transitions enforced à 3 niveaux :
1. **FSM helper Python** (B3.S2) — `FSM_MATRICES["stock_item"]`
2. **CHECK constraint** sur `stock_items.status` (enum)
3. **Trigger DB BEFORE UPDATE** vérifiant `OLD.status → NEW.status ∈ matrix`

Matrice (cf. architecture-cible §4.2.3) :
```
available   → {reserved, damaged, in_repair, retired}
reserved    → {available, on_location, damaged}
on_location → {available, damaged}
damaged     → {in_repair, retired}
in_repair   → {available, retired}
retired     → ∅ (terminal)
```

## Solution

### Migration

```python
# alembic/versions/f1a2b3c4d5e7_stock_item_fsm.py
def upgrade() -> None:
    # ENUM strict
    op.execute(text("""
        CREATE TYPE stock_item_status AS ENUM (
            'available', 'reserved', 'on_location', 'damaged', 'in_repair', 'retired'
        )
    """))
    # Backfill valeurs invalides → 'available' (audit log)
    op.execute(text("""
        UPDATE stock_items SET status = 'available'
        WHERE status NOT IN ('available','reserved','on_location','damaged','in_repair','retired')
    """))
    op.execute(text("""
        ALTER TABLE stock_items ALTER COLUMN status TYPE stock_item_status
        USING status::stock_item_status
    """))

    # Trigger BEFORE UPDATE matrice
    op.execute(text("""
        CREATE OR REPLACE FUNCTION stock_item_fsm_check()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status = NEW.status THEN
                RETURN NEW;
            END IF;
            -- Matrice transitions valides
            IF NOT (
                (OLD.status = 'available' AND NEW.status IN ('reserved','damaged','in_repair','retired'))
                OR (OLD.status = 'reserved' AND NEW.status IN ('available','on_location','damaged'))
                OR (OLD.status = 'on_location' AND NEW.status IN ('available','damaged'))
                OR (OLD.status = 'damaged' AND NEW.status IN ('in_repair','retired'))
                OR (OLD.status = 'in_repair' AND NEW.status IN ('available','retired'))
            ) THEN
                RAISE EXCEPTION 'stock_item_fsm_invalid: % -> % (item %)',
                    OLD.status, NEW.status, OLD.id;
            END IF;
            RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """))
    op.execute(text("""
        CREATE TRIGGER trg_stock_items_fsm_check
        BEFORE UPDATE OF status ON stock_items
        FOR EACH ROW EXECUTE FUNCTION stock_item_fsm_check();
    """))
```

### FSM matrix Python

```python
# app/services/fsm.py — registry
STOCK_ITEM_FSM = FSMMatrix(
    entity_type="stock_item",
    transitions={
        ("available", "reserved"), ("available", "damaged"),
        ("available", "in_repair"), ("available", "retired"),
        ("reserved", "available"), ("reserved", "on_location"), ("reserved", "damaged"),
        ("on_location", "available"), ("on_location", "damaged"),
        ("damaged", "in_repair"), ("damaged", "retired"),
        ("in_repair", "available"), ("in_repair", "retired"),
    },
    initial_states={"available"},
    terminal_states={"retired"},
)
FSM_MATRICES["stock_item"] = STOCK_ITEM_FSM
```

### Test

```python
async def test_stock_item_damaged_to_reserved_refused(db, stock_item_damaged):
    with pytest.raises(IntegrityError, match="stock_item_fsm_invalid"):
        await db.execute(
            update(StockItem).where(StockItem.id == stock_item_damaged.id).values(status="reserved")
        )

async def test_stock_item_retired_terminal(db, stock_item_retired):
    """Aucune transition depuis retired."""
    for target in ("available", "reserved", "damaged", "in_repair"):
        with pytest.raises(IntegrityError, match="stock_item_fsm_invalid"):
            await db.execute(
                update(StockItem).where(StockItem.id == stock_item_retired.id).values(status=target)
            )
```

## DoD

- [ ] ENUM `stock_item_status` créé + colonne migrée
- [ ] Trigger DB `trg_stock_items_fsm_check` actif
- [ ] FSM matrix Python registrée
- [ ] Test : transition illégale `damaged → reserved` → IntegrityError
- [ ] Test : retired terminal (toute transition refusée)

---

# Story B4.S2.T2 — `release_n(reservation_id=...)` mandatory

## Contexte

**Friction** : TR-23, F641 (BUG STOCK-RELEASE-BLIND-01 résolu partiellement 2026-04-25 mais signature accepte toujours None)
**Sévérité** : P0 — libération aveugle items d'autres résa

### Description

`release_n(items, reservation_id=None)` accepte `None` → libère items sans vérifier qu'ils appartiennent à la résa. Cible :
- `reservation_id` **mandatory positional** (pas keyword default)
- ValueError si appel avec None malgré tout (ceinture + bretelle)
- Filtre SQL `WHERE reserved_for_reservation_id = :rid` strict

## Solution

```python
# app/services/stock.py
class StockService:
    async def release_n(
        self,
        items: list[UUID],
        reservation_id: UUID,  # mandatory positional, pas Optional
        actor_id: UUID,
        tenant_id: int,
    ) -> int:
        if reservation_id is None:
            # Ceinture : refus runtime même si type system ignoré
            raise ValueError("release_n: reservation_id is mandatory (cf. STOCK-RELEASE-BLIND-01)")

        async with self.db.begin():
            # Lock items + filtre strict reservation_id
            result = await self.db.execute(
                update(StockItem)
                .where(
                    StockItem.id.in_(items),
                    StockItem.tenant_id == tenant_id,
                    StockItem.reserved_for_reservation_id == reservation_id,  # ANTI-AVEUGLE
                    StockItem.status == "reserved",
                )
                .values(status="available", reserved_for_reservation_id=None)
                .returning(StockItem.id)
            )
            released_ids = [r[0] for r in result.fetchall()]

            if len(released_ids) != len(items):
                missing = set(items) - set(released_ids)
                logger.warning(
                    "release_n_partial_refusal",
                    requested=len(items), released=len(released_ids),
                    missing=list(missing),
                    reservation_id=str(reservation_id),
                )

            return len(released_ids)

    async def transition_n(
        self,
        items: list[UUID],
        from_status: str,
        to_status: str,
        reservation_id: UUID,  # mandatory même pour transitions hors release
        actor_id: UUID,
        tenant_id: int,
    ) -> int:
        if reservation_id is None:
            raise ValueError("transition_n: reservation_id is mandatory")
        # ... même filtre strict
```

### Tests

```python
async def test_release_n_refuses_none(stock_service):
    with pytest.raises(ValueError, match="reservation_id is mandatory"):
        await stock_service.release_n([uuid4()], reservation_id=None, actor_id=user_id, tenant_id=1)

async def test_release_n_refuses_other_resa_items(db, tenant, resa_a, resa_b):
    """release_n(reservation_id=A) ne touche pas items réservés par B."""
    item_a = StockItem(tenant_id=tenant.id, status="reserved", reserved_for_reservation_id=resa_a.id)
    item_b = StockItem(tenant_id=tenant.id, status="reserved", reserved_for_reservation_id=resa_b.id)
    db.add_all([item_a, item_b]); await db.commit()

    released = await stock_service.release_n(
        items=[item_a.id, item_b.id],  # tente les 2
        reservation_id=resa_a.id,       # mais filtre A
        actor_id=user_id, tenant_id=tenant.id,
    )
    assert released == 1
    await db.refresh(item_a)
    await db.refresh(item_b)
    assert item_a.status == "available"
    assert item_b.status == "reserved"  # intact
```

## DoD

- [ ] `release_n(items, reservation_id, ...)` mandatory positional
- [ ] ValueError runtime si None
- [ ] Filtre SQL `WHERE reserved_for_reservation_id = :rid` strict
- [ ] Idem `transition_n`
- [ ] Tests : None refusé, items autre résa intacts

---

# Story B4.S2.T3 — `product_stock_view` matérialisée + REFRESH debounced

## Contexte

**Friction** : TR-17 (cf. `architecture-cible.md §4.2.2`)
**Décision** : Q22=A (verrouillée 2026-04-27) — StockItem source unique + view matérialisée refresh debounced 5s

### Description

3 sources de vérité actuelles :
- `Product.available_quantity` (denorm écrite par triggers)
- `SUM(ProductVariant.available_quantity)` (sync function `sync_available_from_variants`)
- `stock_items` (source physique réelle)

Cible : 1 source physique (`stock_items`) + 1 view matérialisée (`product_stock_view`). Drop des autres en B4.S2.T4.

## Solution

### Migration

```python
# alembic/versions/f1a2b3c4d5e8_product_stock_view.py
def upgrade() -> None:
    op.execute(text("""
        CREATE MATERIALIZED VIEW product_stock_view AS
        SELECT
            si.tenant_id,
            si.product_id,
            si.variant_id,
            COUNT(*) FILTER (WHERE si.status = 'available')               AS available,
            COUNT(*) FILTER (WHERE si.status = 'reserved')                AS reserved,
            COUNT(*) FILTER (WHERE si.status = 'on_location')             AS on_location,
            COUNT(*) FILTER (WHERE si.status IN ('damaged','in_repair'))  AS unavailable,
            COUNT(*) FILTER (WHERE si.status != 'retired')                AS total_active
        FROM stock_items si
        WHERE si.status != 'retired'
        GROUP BY si.tenant_id, si.product_id, si.variant_id
        WITH NO DATA;
    """))
    # UNIQUE INDEX requis pour REFRESH CONCURRENTLY
    op.execute(text("""
        CREATE UNIQUE INDEX uq_product_stock_view ON product_stock_view (tenant_id, product_id, variant_id)
    """))
    op.execute(text("REFRESH MATERIALIZED VIEW product_stock_view"))
```

### Trigger debounced 5s

```python
# app/services/stock_view.py (NEW)
class StockViewRefresher:
    """Debounce REFRESH MATERIALIZED VIEW via Redis lock 5s."""

    LOCK_KEY = "stock_view:refresh:lock"
    LOCK_TTL = 5  # seconds

    def __init__(self, redis: Redis, db_engine):
        self.redis = redis
        self.engine = db_engine

    async def schedule_refresh(self):
        # Première écriture du lock → planifier refresh
        # Si lock déjà présent → no-op (refresh déjà en attente)
        acquired = await self.redis.set(self.LOCK_KEY, "1", ex=self.LOCK_TTL, nx=True)
        if not acquired:
            return
        # Schedule refresh après TTL via Celery
        from app.workers.tasks.stock_view_refresh import refresh_stock_view_task
        refresh_stock_view_task.apply_async(countdown=self.LOCK_TTL)


# app/workers/tasks/stock_view_refresh.py
@shared_task(name="refresh_stock_view")
def refresh_stock_view_task():
    """REFRESH CONCURRENTLY (lock-free, requires UNIQUE INDEX)."""
    async def _run():
        async with engine.begin() as conn:
            await conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY product_stock_view"))
    asyncio.run(_run())


# app/models/stock_item.py — hook SQLAlchemy events
from sqlalchemy import event

@event.listens_for(StockItem, "after_insert")
@event.listens_for(StockItem, "after_update")
@event.listens_for(StockItem, "after_delete")
def _schedule_refresh(mapper, connection, target):
    # Hors TX async (post-commit), enqueue debounced refresh
    asyncio.create_task(stock_view_refresher.schedule_refresh())
```

### Modèle ORM lecture seule

```python
# app/models/product_stock_view.py (NEW)
class ProductStockView(Base):
    __tablename__ = "product_stock_view"
    __table_args__ = {"info": {"is_view": True}}  # signal lecture seule
    
    tenant_id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int | None] = mapped_column(primary_key=True, nullable=True)
    available: Mapped[int]
    reserved: Mapped[int]
    on_location: Mapped[int]
    unavailable: Mapped[int]
    total_active: Mapped[int]


# app/models/product.py — relation lecture seule
class Product(Base):
    # ... existing
    stock_view: Mapped["ProductStockView"] = relationship(
        "ProductStockView",
        primaryjoin="and_(Product.id == ProductStockView.product_id, "
                    "Product.tenant_id == ProductStockView.tenant_id, "
                    "ProductStockView.variant_id.is_(None))",
        viewonly=True,
        uselist=False,
    )
```

### Tests

```python
async def test_stock_view_reflects_stock_items(db, tenant, product):
    for _ in range(10):
        db.add(StockItem(tenant_id=tenant.id, product_id=product.id, status="available"))
    db.add(StockItem(tenant_id=tenant.id, product_id=product.id, status="damaged"))
    await db.commit()

    # Force refresh (debounced normalement 5s)
    await db.execute(text("REFRESH MATERIALIZED VIEW product_stock_view"))

    view = await db.scalar(
        select(ProductStockView).where(
            ProductStockView.product_id == product.id,
            ProductStockView.tenant_id == tenant.id,
        )
    )
    assert view.available == 10
    assert view.unavailable == 1
    assert view.total_active == 11
```

## DoD

- [ ] Materialized view `product_stock_view` créée + UNIQUE INDEX
- [ ] Trigger SQLAlchemy hooks `after_insert/update/delete` schedule refresh
- [ ] Debounce Redis lock 5s + Celery countdown
- [ ] Task `refresh_stock_view` REFRESH CONCURRENTLY
- [ ] Modèle ORM `ProductStockView` lecture seule
- [ ] `Product.stock_view` relation lecture seule
- [ ] Test : 10 stock_items available + 1 damaged → view available=10, unavailable=1

---

# Story B4.S2.T4 — Drop colonnes denorm + `sync_available_from_variants`

## Contexte

**Friction** : TR-17 — finir le travail T3 en éliminant les sources fantômes
**Sévérité** : P0 — drift garanti tant que les colonnes denorm coexistent avec la view

### Description

Drop :
- `Product.available_quantity`, `Product.stock_quantity`
- `ProductVariant.available_quantity`, `ProductVariant.stock_quantity`
- Fonction PostgreSQL `sync_available_from_variants()` + tous ses triggers

Migration backward-compatible 4 étapes :
1. **B4.S2.T3** : créer view + relation `Product.stock_view`
2. Refacto endpoints API : `Product.available_quantity` → `Product.stock_view.available`
3. Drop colonnes denorm + drop function (cette story)
4. Cleanup tests qui référencaient `available_quantity` direct

## Solution

```python
# alembic/versions/f1a2b3c4d5e9_drop_denorm_stock_columns.py
def upgrade() -> None:
    # 1. Drop triggers utilisant la function
    op.execute(text("""
        DROP TRIGGER IF EXISTS trg_variants_sync_product ON product_variants;
        DROP TRIGGER IF EXISTS trg_stock_items_sync_product ON stock_items;
        DROP TRIGGER IF EXISTS trg_stock_items_sync_variants ON stock_items;
    """))
    # 2. Drop function
    op.execute(text("DROP FUNCTION IF EXISTS sync_available_from_variants() CASCADE"))
    # 3. Drop colonnes
    op.drop_column("products", "available_quantity")
    op.drop_column("products", "stock_quantity")
    op.drop_column("product_variants", "available_quantity")
    op.drop_column("product_variants", "stock_quantity")
```

### Refacto endpoints

```python
# app/api/v1/endpoints/products.py — avant
@router.get("/products/{id}")
async def get_product(id: int):
    product = await db.get(Product, id)
    return ProductRead(
        id=product.id,
        name=product.name,
        available_quantity=product.available_quantity,  # ❌ colonne droppée
    )

# après — lecture via view
@router.get("/products/{id}")
async def get_product(id: int):
    product = (await db.execute(
        select(Product).options(selectinload(Product.stock_view)).where(Product.id == id)
    )).scalar_one()
    return ProductRead(
        id=product.id,
        name=product.name,
        available_quantity=product.stock_view.available if product.stock_view else 0,
    )
```

### Script CI invariant

```python
# tools/check_no_available_quantity_attr.py
"""Refuse `Product.available_quantity` ou `ProductVariant.available_quantity`."""
import re, sys
from pathlib import Path

PATTERN = re.compile(r"\b(Product|ProductVariant)\.available_quantity\b")
violations = []
for py in Path("app").rglob("*.py"):
    if PATTERN.search(py.read_text()):
        violations.append(str(py))
if violations:
    print(f"❌ Drop achevée mais usage résiduel: {violations}")
    sys.exit(1)
```

## DoD

- [ ] Migration drop 4 colonnes + function + 3 triggers
- [ ] Endpoints API consomment via `selectinload(Product.stock_view)`
- [ ] Script CI bloque réintroduction `Product.available_quantity`
- [ ] Test : `Product.available_quantity` accessor → AttributeError (preuve drop)
- [ ] Test invariant : view consistente après 100 mutations stock_items

---

# Story B4.S2.T5 — PMP/WAC `weighted_avg_cost_cents`

## Contexte

**Décision** : Q13=A (verrouillée 2026-04-27) — PMP partout (épicerie + Marveline)
**Sévérité** : P0 — calcul COGS invalide sans WAC ; reporting marge fausse

### Description

Cible :
1. `inventory_movements.unit_cost_at_entry_cents BIGINT` (centimes, snapshot coût à l'entrée)
2. `stock_management.weighted_avg_cost_cents BIGINT` recalculé sur trigger AFTER INSERT inventory_movement (type=`supplier_receipt`)
3. Formule : `WAC_new = (qty_old × WAC_old + qty_in × cost_in) / (qty_old + qty_in)`
4. Pour Marveline : `unit_cost` = coût d'amortissement par usage (rapport rentabilité, pas facturation client)

## Solution

### Migration

```python
# alembic/versions/f1a2b3c4d5ea_pmp_wac.py
def upgrade() -> None:
    op.add_column(
        "inventory_movements",
        sa.Column("unit_cost_at_entry_cents", sa.BigInteger, nullable=True),
    )
    op.create_check_constraint(
        "ck_inventory_movements_unit_cost_positive",
        "inventory_movements",
        "unit_cost_at_entry_cents IS NULL OR unit_cost_at_entry_cents >= 0",
    )
    op.add_column(
        "stock_management",
        sa.Column("weighted_avg_cost_cents", sa.BigInteger, nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_stock_management_wac_positive",
        "stock_management",
        "weighted_avg_cost_cents >= 0",
    )

    # Trigger WAC recompute on supplier_receipt
    op.execute(text("""
        CREATE OR REPLACE FUNCTION stock_management_wac_recompute()
        RETURNS TRIGGER AS $$
        DECLARE
            sm RECORD;
            new_wac BIGINT;
            new_qty BIGINT;
        BEGIN
            -- Seulement pour entrées supplier_receipt avec coût
            IF NEW.type != 'supplier_receipt' OR NEW.unit_cost_at_entry_cents IS NULL THEN
                RETURN NEW;
            END IF;

            SELECT current_qty, weighted_avg_cost_cents
            INTO sm
            FROM stock_management
            WHERE tenant_id = NEW.tenant_id AND product_id = NEW.product_id
            FOR UPDATE;

            IF sm IS NULL THEN
                INSERT INTO stock_management (tenant_id, product_id, current_qty, weighted_avg_cost_cents)
                VALUES (NEW.tenant_id, NEW.product_id, NEW.qty, NEW.unit_cost_at_entry_cents);
                RETURN NEW;
            END IF;

            -- WAC = (qty_old × WAC_old + qty_in × cost_in) / (qty_old + qty_in)
            new_qty := sm.current_qty + NEW.qty;
            IF new_qty = 0 THEN
                new_wac := 0;
            ELSE
                new_wac := (sm.current_qty * sm.weighted_avg_cost_cents + NEW.qty * NEW.unit_cost_at_entry_cents) / new_qty;
            END IF;

            UPDATE stock_management
            SET current_qty = new_qty,
                weighted_avg_cost_cents = new_wac
            WHERE tenant_id = NEW.tenant_id AND product_id = NEW.product_id;

            RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """))
    op.execute(text("""
        CREATE TRIGGER trg_stock_management_wac_recompute
        AFTER INSERT ON inventory_movements
        FOR EACH ROW EXECUTE FUNCTION stock_management_wac_recompute()
    """))
```

### Service capture coût à réception

```python
# app/services/supplier.py
class SupplierService:
    async def receive_order(self, order_id, receipt_data):
        # ... création receipt + receipt_lines (B3.S7.T4 trigger crée stock_items + inventory_movement)
        # Mais le movement créé par trigger n'a pas unit_cost — on l'enrichit ici post-trigger :
        for line in receipt_data.lines:
            await self.db.execute(
                update(InventoryMovement)
                .where(
                    InventoryMovement.source_type == "supplier_order_receipt_line",
                    InventoryMovement.source_id == line.receipt_line_id,
                )
                .values(unit_cost_at_entry_cents=line.unit_cost_cents)
            )
        # → Trigger WAC recompute déclenché par UPDATE
```

**Note** : pour rendre le pattern propre, B3.S7.T4 trigger devra propager `unit_cost_at_entry_cents` directement depuis `supplier_order_receipt_lines.unit_cost_cents` (à ajouter en migration cohérence).

### Tests

```python
async def test_wac_first_receipt(db, tenant, product):
    # Première réception : 100 unités à 5€
    await create_supplier_receipt(tenant.id, product.id, qty=100, unit_cost_cents=500)
    sm = await db.scalar(select(StockManagement).where(StockManagement.product_id == product.id))
    assert sm.current_qty == 100
    assert sm.weighted_avg_cost_cents == 500

async def test_wac_second_receipt_blends(db, tenant, product):
    # 1ère : 100 à 5€ → WAC=500
    await create_supplier_receipt(tenant.id, product.id, qty=100, unit_cost_cents=500)
    # 2ème : 50 à 8€ → WAC = (100×500 + 50×800) / 150 = 90000/150 = 600
    await create_supplier_receipt(tenant.id, product.id, qty=50, unit_cost_cents=800)
    sm = await db.scalar(select(StockManagement).where(StockManagement.product_id == product.id))
    assert sm.current_qty == 150
    assert sm.weighted_avg_cost_cents == 600
```

## DoD

- [ ] Migration colonnes `unit_cost_at_entry_cents` + `weighted_avg_cost_cents`
- [ ] CHECK >= 0 sur les 2 colonnes
- [ ] Trigger `stock_management_wac_recompute` actif AFTER INSERT
- [ ] Test 1ère réception : WAC = unit_cost
- [ ] Test 2 réceptions : WAC blend formule correcte
- [ ] Test Marveline : capture pour rapport rentabilité (pas facturation)

---

# Story B4.S2.T6 — Cohérence StockItem ↔ supplier_receipt

## Contexte

**Pré-requis** : B3.S7.T4 a livré le trigger `supplier_receipt_sync_stock` qui crée `stock_items` + `inventory_movement` automatiquement à l'INSERT receipt_line.

### Description

Audit de cohérence :
1. Vérifier que `StockItem.tenant_id` est correctement propagé par le trigger (pas NULL)
2. Vérifier que `StockItem.source_receipt_line_id` FK pointe correctement
3. Vérifier que `inventory_movement.unit_cost_at_entry_cents` est rempli via T5 supra

## Solution

### Test cohérence end-to-end

```python
async def test_supplier_receipt_to_stock_view_consistency(db, tenant, product, supplier_order):
    # 1. INSERT receipt_line — trigger B3.S7.T4 crée 8 stock_items available + 2 damaged
    receipt = SupplierOrderReceipt(supplier_order_id=supplier_order.id)
    line = SupplierOrderReceiptLine(
        receipt_id=receipt.id,
        order_line_id=supplier_order.lines[0].id,
        qty_received=8, qty_damaged=2, qty_missing=0,
        unit_cost_cents=500,
    )
    db.add_all([receipt, line]); await db.commit()

    # 2. inventory_movement créé avec unit_cost (B4.S2.T5)
    movement = await db.scalar(
        select(InventoryMovement).where(InventoryMovement.source_id == line.id)
    )
    assert movement is not None
    assert movement.tenant_id == tenant.id
    # unit_cost rempli via update post-trigger (T5)

    # 3. WAC stock_management mise à jour
    sm = await db.scalar(select(StockManagement).where(StockManagement.product_id == product.id))
    assert sm.current_qty >= 10  # 8 + 2
    assert sm.weighted_avg_cost_cents == 500

    # 4. View matérialisée refresh debounced (5s) → simuler refresh
    await db.execute(text("REFRESH MATERIALIZED VIEW product_stock_view"))
    view = await db.scalar(
        select(ProductStockView).where(ProductStockView.product_id == product.id)
    )
    assert view.available == 8
    assert view.unavailable == 2
```

## DoD

- [ ] Test E2E : INSERT receipt_line → 10 stock_items + 1 movement + WAC update + view refresh consistent
- [ ] tenant_id propagé sur tous les artefacts générés par trigger
- [ ] Si défaut détecté : patch B3.S7.T4 trigger pour cohérence

---

## Critères de succès Sprint B4.S2

- [ ] **TR-22 résolu** : StockItemFSM matrice DB-enforced + Python helper
- [ ] **TR-23 résolu** : `release_n(reservation_id=...)` mandatory ; libération aveugle impossible
- [ ] **TR-17 résolu** : StockItem source unique + `product_stock_view` matérialisée
- [ ] Drop colonnes denorm `Product.available_quantity` / `ProductVariant.available_quantity`
- [ ] Drop function `sync_available_from_variants` + 3 triggers legacy
- [ ] **Q13=A livré** : PMP/WAC sur `inventory_movements` + `stock_management` + trigger recompute
- [ ] Cohérence E2E supplier_receipt → stock_items → view consistente
- [ ] Script CI invariant `tools/check_no_available_quantity_attr.py`

---

**Fin du document — 14-sprint-B4.S2.md**
