# Sprint B3.S7 — Supplier + Vente fiscal + Deposit immutable + Evenement

> **STATUT** : ⏳ NOUVEAU sprint (vague 6 audit cohérence — angles morts Phase 3)
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev1
> **BLOQUE** : B4.S2 (Supplier receipt → trigger sync stock), B6.S1 (Audit refondu sur evenements)
> **DÉPEND DE** : B3.S2 (FSM helper + triggers), B3.S3 (`tva_rate_snapshot`), B3.S5 (EmailGateway)
> **OBJECTIF** : Combler les angles morts Phase 3 identifiés vague 6 — modules Suppliers (26), Vente fiscal (22), Deposit immutable (20), Evenement (24). Livrer `Supplier.code UNIQUE per-tenant`, `supplier_orders` workflow + CHECK consistency + trigger sync stock, `vente_lines.tva_rate_snapshot`, `Vente.payment_method` ENUM, `Deposit.amount_cents` immutable trigger, `Evenement.reference UNIQUE per-tenant`, `incident_sla_hours` per-tenant settings.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B3.S7.T1** | F826 — `Supplier.code` UNIQUE per-tenant | P0 | 0.5 j | T2 |
| **B3.S7.T2** | F827/F828 — `SupplierOrder.reference` UNIQUE per-tenant + CHECK status enum | P0 | 0.5 j | T3 |
| **B3.S7.T3** | F829/F833 — `supplier_order_receipt_lines` CHECK qty consistency + dédup `lines_json` | P0 | 1 j | T4 |
| **B3.S7.T4** | F830 — Trigger AFTER INSERT receipt → auto-sync stock_items + inventory_movement | P0 | 1.5 j | B4.S2 |
| **B3.S7.T5** | F728 — `vente_lines.tva_rate_snapshot NUMERIC(5,4)` (cohérent B3.S3 sur Vente directe) | P0 | 0.5 j | T6 |
| **B3.S7.T6** | F737 — `Vente.payment_method` ENUM (`cash`, `card`, `transfer`, `check`, `mixed`) | P1 | 0.5 j | aucun |
| **B3.S7.T7** | F739 — Vente CHECK `total_ttc = SUM(lines.line_total_ttc)` via trigger | P1 | 1 j | aucun |
| **B3.S7.T8** | F767 — `Evenement.reference` UNIQUE per-tenant + drop FK orpheline `event_id` | P0 | 0.5 j | aucun |
| **B3.S7.T9** | F773 — `Tenant.incident_sla_hours` per-tenant + service `IncidentSlaResolver` | P1 | 0.5 j | aucun |

**Total effort** : 6.5 jours-homme.

---

# Story B3.S7.T1 — `Supplier.code` UNIQUE per-tenant (F826)

## Contexte

**Friction** : F826 (vague 6, angle mort module 26 Suppliers)
**Sévérité** : P0 — doublons silencieux fournisseurs
**Code source** : `app/models/supplier.py`

### Description

Aujourd'hui : `Supplier.code` UNIQUE global ou non-unique selon historique. Conséquence :
- Tenant Marveline a fournisseur `code='METRO'` ; Tenant CaroCorp ne peut pas créer le sien (collision globale)
- OU pas de UNIQUE → 2 fournisseurs `code='METRO'` chez Marveline → ETL parser échoue à mapper

Cible TR-27 : UNIQUE `(tenant_id, code)` cohérent avec Reservation/Devis/Invoice (B3.S1.T4).

## Solution

```python
# alembic/versions/e3f4a5b6c7e1_supplier_code_unique_per_tenant.py
def upgrade() -> None:
    # Drop UNIQUE global existant si présent
    with contextlib.suppress(Exception):
        op.drop_constraint("uq_suppliers_code", "suppliers", type_="unique")
    # Recreate UNIQUE per-tenant
    op.create_unique_constraint(
        "uq_suppliers_tenant_code", "suppliers", ["tenant_id", "code"]
    )
    # Idem si table `supplier_contacts` ou similaire existe
```

### Test

```python
async def test_supplier_code_unique_per_tenant(db, tenant_a, tenant_b):
    s_a = Supplier(tenant_id=tenant_a.id, code="METRO", name="Metro A")
    s_b = Supplier(tenant_id=tenant_b.id, code="METRO", name="Metro B")
    db.add_all([s_a, s_b])
    await db.commit()  # OK : 2 tenants distincts

    # Mais 2 METRO chez tenant_a → IntegrityError
    s_dup = Supplier(tenant_id=tenant_a.id, code="METRO", name="dup")
    db.add(s_dup)
    with pytest.raises(IntegrityError, match="uq_suppliers_tenant_code"):
        await db.commit()
```

## DoD

- [ ] Migration drop UNIQUE global, create UNIQUE `(tenant_id, code)`
- [ ] Test cross-tenant : 2 codes identiques sur 2 tenants → OK
- [ ] Test intra-tenant : 2 codes identiques → IntegrityError

---

# Story B3.S7.T2 — `SupplierOrder.reference` UNIQUE + status ENUM (F827/F828)

## Contexte

**Friction** : F827, F828 (vague 6)
**Sévérité** : P0 — bons de commande dupliqués + status string libre

### Description

Aujourd'hui :
- `SupplierOrder.reference` non unique → 2 BC `BC-2026-001` chez Marveline silencieusement
- `SupplierOrder.status: String(32)` accepte n'importe quelle valeur

Cible :
- UNIQUE `(tenant_id, reference)`
- ENUM `supplier_order_status` : `draft | sent | partial_received | received | cancelled`
- FSM matrix dans `FSM_MATRICES["supplier_order"]` (réutilise B3.S2)

## Solution

```python
# alembic/versions/e3f4a5b6c7e2_supplier_orders_constraints.py
def upgrade() -> None:
    # ENUM
    op.execute(text("""
        CREATE TYPE supplier_order_status AS ENUM (
            'draft', 'sent', 'partial_received', 'received', 'cancelled'
        )
    """))
    # Backfill données invalides → 'draft' (audit log entry par invalid)
    op.execute(text("""
        UPDATE supplier_orders SET status = 'draft'
        WHERE status NOT IN ('draft', 'sent', 'partial_received', 'received', 'cancelled')
    """))
    # ALTER COLUMN
    op.execute(text("""
        ALTER TABLE supplier_orders 
        ALTER COLUMN status TYPE supplier_order_status 
        USING status::supplier_order_status
    """))
    # UNIQUE per-tenant
    op.create_unique_constraint(
        "uq_supplier_orders_tenant_reference", "supplier_orders", ["tenant_id", "reference"]
    )

# app/services/fsm.py
SUPPLIER_ORDER_FSM = FSMMatrix(
    entity_type="supplier_order",
    transitions={
        ("draft", "sent"),
        ("sent", "partial_received"),
        ("sent", "received"),
        ("partial_received", "received"),
        ("draft", "cancelled"),
        ("sent", "cancelled"),
    },
    initial_states={"draft"},
    terminal_states={"received", "cancelled"},
)
FSM_MATRICES["supplier_order"] = SUPPLIER_ORDER_FSM
```

## DoD

- [ ] ENUM `supplier_order_status` créé + colonne migrée
- [ ] UNIQUE `(tenant_id, reference)` actif
- [ ] FSM matrix `supplier_order` registré
- [ ] Test : transition illégale `draft → received` → InvalidTransition
- [ ] Test : 2 BC même reference cross-tenant → OK ; intra-tenant → IntegrityError

---

# Story B3.S7.T3 — `supplier_order_receipt_lines` CHECK qty + dédup (F829/F833)

## Contexte

**Friction** : F829 (TR-28), F833 (vague 6)
**Sévérité** : P0 — bilans réception absurdes possibles

### Description

Aujourd'hui :
- `qty_received + qty_damaged + qty_missing` peut excéder `qty_ordered_for_line` → bilan invalide
- `lines_json` stocké à plusieurs endroits (`SupplierOrder.lines_json` + `SupplierOrderLine` + `receipt_lines`) → drift possible

## Solution

```python
# alembic/versions/e3f4a5b6c7e3_receipt_lines_check_qty.py
def upgrade() -> None:
    # CHECK consistency qty
    op.create_check_constraint(
        "ck_receipt_lines_qty_consistency",
        "supplier_order_receipt_lines",
        "qty_received >= 0 AND qty_damaged >= 0 AND qty_missing >= 0 "
        "AND (qty_received + qty_damaged + qty_missing) <= qty_ordered_for_line",
    )
    # Drop colonne dupliquée si elle existe
    with contextlib.suppress(Exception):
        op.drop_column("supplier_orders", "lines_json")  # source unique = supplier_order_lines
    with contextlib.suppress(Exception):
        op.drop_column("supplier_order_receipts", "receipt_lines_json")  # source unique = receipt_lines
```

### Tests

```python
async def test_receipt_qty_consistency_check(db, supplier_order_with_line_qty_10):
    receipt = SupplierOrderReceipt(...)
    line = SupplierOrderReceiptLine(
        receipt_id=receipt.id,
        order_line_id=supplier_order_with_line_qty_10.id,
        qty_received=8,
        qty_damaged=2,
        qty_missing=3,  # total = 13 > 10 ordered
    )
    db.add(line)
    with pytest.raises(IntegrityError, match="ck_receipt_lines_qty_consistency"):
        await db.commit()

async def test_receipt_qty_negative_refused(db):
    line = SupplierOrderReceiptLine(qty_received=-5, ...)
    with pytest.raises(IntegrityError, match="ck_receipt_lines_qty_consistency"):
        await db.commit()
```

## DoD

- [ ] CHECK `(qty_received + qty_damaged + qty_missing) <= qty_ordered_for_line`
- [ ] CHECK `qty_* >= 0`
- [ ] Colonnes dupliquées `lines_json` droppées (source unique)
- [ ] Test sur somme dépassée → IntegrityError
- [ ] Test sur qty négative → IntegrityError

---

# Story B3.S7.T4 — Trigger auto-sync receipt → stock_items + inventory_movement (F830)

## Contexte

**Friction** : F830 (TR-29 — commentaire mensonger sur sync)
**Sévérité** : P0 — réception physique ≠ stock système
**Code source** : `app/services/supplier.py:receive_order` (commentaire dit "sync stock", code n'en fait rien)

### Description

Cible (architecture-cible §4.2.9) : trigger DB `AFTER INSERT ON supplier_order_receipt_lines` qui :
1. Crée `inventory_movement(type='supplier_receipt')` pour traçabilité
2. Insert `qty_received` rows `stock_items(status='available')`
3. Insert `qty_damaged` rows `stock_items(status='damaged')`
4. Émet Outbox event `SupplierReceiptCompleted`

## Solution

### Trigger DB

```python
# alembic/versions/e3f4a5b6c7e4_receipt_auto_sync_stock.py
def upgrade() -> None:
    op.execute(text("""
        CREATE OR REPLACE FUNCTION supplier_receipt_sync_stock()
        RETURNS TRIGGER AS $$
        DECLARE
            order_line RECORD;
            i INT;
        BEGIN
            -- 1. Charger order_line + product_id + tenant_id
            SELECT sol.product_id, sol.tenant_id, so.id AS order_id
            INTO order_line
            FROM supplier_order_lines sol
            JOIN supplier_orders so ON so.id = sol.supplier_order_id
            WHERE sol.id = NEW.order_line_id;

            -- 2. inventory_movement audit
            INSERT INTO inventory_movements (
                tenant_id, product_id, type, qty, source_type, source_id, created_at
            ) VALUES (
                order_line.tenant_id, order_line.product_id, 'supplier_receipt',
                NEW.qty_received + NEW.qty_damaged,
                'supplier_order_receipt_line', NEW.id, NOW()
            );

            -- 3. stock_items(status='available') × qty_received
            FOR i IN 1..NEW.qty_received LOOP
                INSERT INTO stock_items (
                    tenant_id, product_id, status, source_receipt_line_id, created_at
                ) VALUES (
                    order_line.tenant_id, order_line.product_id, 'available', NEW.id, NOW()
                );
            END LOOP;

            -- 4. stock_items(status='damaged') × qty_damaged
            FOR i IN 1..NEW.qty_damaged LOOP
                INSERT INTO stock_items (
                    tenant_id, product_id, status, source_receipt_line_id, created_at
                ) VALUES (
                    order_line.tenant_id, order_line.product_id, 'damaged', NEW.id, NOW()
                );
            END LOOP;

            -- 5. Outbox event
            INSERT INTO outbox_events (event_type, aggregate_id, tenant_id, payload, created_at)
            VALUES (
                'SupplierReceiptCompleted',
                NEW.id,
                order_line.tenant_id,
                jsonb_build_object(
                    'receipt_line_id', NEW.id,
                    'product_id', order_line.product_id,
                    'qty_received', NEW.qty_received,
                    'qty_damaged', NEW.qty_damaged,
                    'qty_missing', NEW.qty_missing
                ),
                NOW()
            );

            RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """))
    op.execute(text("""
        CREATE TRIGGER trg_receipt_lines_sync_stock
        AFTER INSERT ON supplier_order_receipt_lines
        FOR EACH ROW EXECUTE FUNCTION supplier_receipt_sync_stock();
    """))
```

### Drop manuel sync code (legacy)

```python
# app/services/supplier.py
class SupplierService:
    async def receive_order(self, order_id, receipt_data):
        # AVANT : code Python qui faisait `for _ in range(qty): db.add(StockItem(...))`
        # APRÈS : seulement insertion receipt_line — le trigger fait le reste
        receipt = SupplierOrderReceipt(supplier_order_id=order_id, ...)
        self.db.add(receipt)
        for line_data in receipt_data.lines:
            self.db.add(SupplierOrderReceiptLine(receipt_id=receipt.id, **line_data))
        await self.db.flush()
        # Trigger DB a déjà créé : inventory_movement + N stock_items + Outbox event
        return receipt
```

### Test

```python
async def test_receipt_auto_creates_stock_items(db, tenant, supplier_order_line_qty_10):
    receipt = SupplierOrderReceipt(supplier_order_id=supplier_order_line_qty_10.order_id)
    line = SupplierOrderReceiptLine(
        order_line_id=supplier_order_line_qty_10.id,
        qty_received=8, qty_damaged=2, qty_missing=0,
    )
    db.add_all([receipt, line])
    await db.commit()

    # Trigger doit avoir créé 8 stock_items available + 2 damaged + 1 inventory_movement
    available = await db.scalars(
        select(StockItem).where(StockItem.source_receipt_line_id == line.id, StockItem.status == "available")
    )
    damaged = await db.scalars(
        select(StockItem).where(StockItem.source_receipt_line_id == line.id, StockItem.status == "damaged")
    )
    movement = await db.scalar(
        select(InventoryMovement).where(InventoryMovement.source_id == line.id)
    )
    assert len(available.all()) == 8
    assert len(damaged.all()) == 2
    assert movement.qty == 10
    assert movement.type == "supplier_receipt"

    # Outbox event présent
    event = await db.scalar(
        select(OutboxEvent).where(OutboxEvent.aggregate_id == line.id)
    )
    assert event.event_type == "SupplierReceiptCompleted"
```

## DoD

- [ ] Trigger DB `trg_receipt_lines_sync_stock` actif
- [ ] Code Python `receive_order` simplifié (juste INSERT receipt + lines)
- [ ] Test : INSERT receipt_line(qty_received=8, qty_damaged=2) → 8 + 2 stock_items + 1 movement + 1 outbox event
- [ ] Test rollback : si trigger échoue → rollback complet (pas de stock_items orphelins)

---

# Story B3.S7.T5 — `vente_lines.tva_rate_snapshot` (F728)

## Contexte

**Friction** : F728 (cohérent B3.S3.T1 mais spécifique au flux Vente directe)
**Sévérité** : P0 — Vente épicerie/restaurant capture TVA seulement dans Vente, jamais en ligne → reporting impossible

### Description

B3.S3.T1 a déjà ajouté `tva_rate_snapshot` sur les 4 tables ligne. Cette story confirme que `vente_lines` (épicerie + restaurant) est inclus, et ajoute le `tva_total_per_line_cents` dénormalisé pour reporting fiscal rapide.

## Solution

Si pas déjà couvert par B3.S3.T1 (vérifier en pre-deploy) :

```python
# Vérification : la migration B3.S3.T1 a-t-elle inclus vente_lines ?
# Si oui → no-op
# Si non → migration corrective :

def upgrade() -> None:
    op.add_column("vente_lines", sa.Column("tva_rate_snapshot", sa.Numeric(5, 4), nullable=True))
    op.execute(text("""
        UPDATE vente_lines vl
        SET tva_rate_snapshot = COALESCE(tr.rate, 0.20)
        FROM products p
        LEFT JOIN tva_rates tr ON tr.id = p.tva_rate_id
        WHERE vl.product_id = p.id AND vl.tva_rate_snapshot IS NULL
    """))
    op.alter_column("vente_lines", "tva_rate_snapshot", nullable=False)
    op.create_check_constraint(
        "ck_vente_lines_tva_rate_range",
        "vente_lines",
        "tva_rate_snapshot >= 0 AND tva_rate_snapshot <= 1",
    )
```

## DoD

- [ ] `vente_lines.tva_rate_snapshot NOT NULL`
- [ ] CHECK `[0, 1]` actif
- [ ] Test : Vente épicerie produit TVA 5.5% → ligne portée à 0.055
- [ ] Test : Vente restaurant produit TVA 10% → ligne portée à 0.10

---

# Story B3.S7.T6 — `Vente.payment_method` ENUM (F737)

## Contexte

**Friction** : F737 (vague 6)
**Sévérité** : P1 — `payment_method String(32)` libre = saisies divergentes ("CB", "carte", "card") → reporting impossible

### Description

Cible : ENUM strict `cash | card | transfer | check | mixed | mobile_pay`.

## Solution

```python
def upgrade() -> None:
    op.execute(text("""
        CREATE TYPE vente_payment_method AS ENUM (
            'cash', 'card', 'transfer', 'check', 'mixed', 'mobile_pay'
        )
    """))
    # Backfill string libre → ENUM via mapping
    op.execute(text("""
        UPDATE ventes SET payment_method = CASE
            WHEN LOWER(payment_method) IN ('cb', 'carte', 'card', 'visa', 'mastercard') THEN 'card'
            WHEN LOWER(payment_method) IN ('especes', 'cash', 'liquide') THEN 'cash'
            WHEN LOWER(payment_method) IN ('virement', 'transfer') THEN 'transfer'
            WHEN LOWER(payment_method) IN ('cheque', 'chèque', 'check') THEN 'check'
            WHEN LOWER(payment_method) IN ('apple_pay', 'google_pay', 'mobile') THEN 'mobile_pay'
            ELSE 'mixed'
        END
    """))
    op.execute(text("""
        ALTER TABLE ventes 
        ALTER COLUMN payment_method TYPE vente_payment_method 
        USING payment_method::vente_payment_method
    """))
```

### Constants

```python
# app/constants/business.py
class VentePaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"
    CHECK = "check"
    MIXED = "mixed"
    MOBILE_PAY = "mobile_pay"
```

## DoD

- [ ] ENUM `vente_payment_method` créé
- [ ] Backfill via mapping insensible casse
- [ ] Test : insert string non valide → IntegrityError
- [ ] Constants Python alignée

---

# Story B3.S7.T7 — Vente CHECK `total = SUM(lines)` (F739)

## Contexte

**Friction** : F739 (vague 6)
**Sévérité** : P1 — `Vente.total_ttc_cents` peut diverger de `SUM(vente_lines.line_total_ttc_cents)` → comptabilité fausse

### Description

Cible : trigger `BEFORE INSERT/UPDATE ON ventes` qui valide que `total_ttc_cents = SUM(vente_lines.line_total_ttc_cents)` au tolerance 0 cent (round_half_up déjà fait par PricingEngine).

## Solution

```python
def upgrade() -> None:
    op.execute(text("""
        CREATE OR REPLACE FUNCTION vente_total_consistency_check()
        RETURNS TRIGGER AS $$
        DECLARE
            sum_lines_ttc BIGINT;
        BEGIN
            SELECT COALESCE(SUM(line_total_ttc_cents), 0)
            INTO sum_lines_ttc
            FROM vente_lines WHERE vente_id = NEW.id;

            IF NEW.total_ttc_cents != sum_lines_ttc THEN
                RAISE EXCEPTION 'vente_total_inconsistency: total_ttc=% but SUM(lines)=%',
                    NEW.total_ttc_cents, sum_lines_ttc;
            END IF;
            RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """))
    # Trigger DEFERRED — exécuté à COMMIT, pas à chaque INSERT (lignes insérées d'abord)
    op.execute(text("""
        CREATE CONSTRAINT TRIGGER trg_vente_total_consistency
        AFTER INSERT OR UPDATE ON ventes
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION vente_total_consistency_check();
    """))
```

### Test

```python
async def test_vente_total_match_lines(db, tenant, product):
    async with db.begin():
        vente = Vente(tenant_id=tenant.id, total_ttc_cents=1200, ...)
        line = VenteLine(vente_id=vente.id, line_total_ttc_cents=1200, ...)
        db.add_all([vente, line])
    # OK : total = sum

async def test_vente_total_mismatch_raises_at_commit(db, tenant, product):
    with pytest.raises(IntegrityError, match="vente_total_inconsistency"):
        async with db.begin():
            vente = Vente(tenant_id=tenant.id, total_ttc_cents=9999, ...)
            line = VenteLine(vente_id=vente.id, line_total_ttc_cents=1200, ...)
            db.add_all([vente, line])
```

## DoD

- [ ] CONSTRAINT TRIGGER DEFERRED actif
- [ ] Test : total = sum(lines) → OK
- [ ] Test : mismatch → IntegrityError au COMMIT

---

# Story B3.S7.T8 — `Evenement.reference` UNIQUE + drop FK orpheline (F767/TR-24)

## Contexte

**Friction** : F767, TR-24 (cf. `architecture-cible.md §4.2.8` + ligne 810)
**Sévérité** : P0 — `evenements` existe mais `inventory_movement.event_id Integer nullable sans FK` → références orphelines

### Description

Cible :
1. `Evenement.reference` UNIQUE per-tenant (cohérent B3.S1.T4)
2. Ajouter FK `inventory_movements.event_id → evenements.id ondelete=SET NULL`
3. Drop commentaire mensonger qui dit "FK non ajoutée car table absente"

## Solution

```python
def upgrade() -> None:
    # 1. UNIQUE per-tenant
    with contextlib.suppress(Exception):
        op.drop_constraint("uq_evenements_reference", "evenements", type_="unique")
    op.create_unique_constraint(
        "uq_evenements_tenant_reference", "evenements", ["tenant_id", "reference"]
    )
    # 2. FK manquante
    op.create_foreign_key(
        "fk_inventory_movements_event_id",
        "inventory_movements", "evenements",
        ["event_id"], ["id"],
        ondelete="SET NULL",
    )
```

### Test

```python
async def test_inventory_movement_event_fk(db, tenant, evenement):
    movement = InventoryMovement(tenant_id=tenant.id, event_id=evenement.id, ...)
    db.add(movement); await db.commit()

    # Delete evenement → SET NULL
    await db.delete(evenement)
    await db.commit()
    await db.refresh(movement)
    assert movement.event_id is None  # SET NULL appliqué

async def test_evenement_reference_unique_per_tenant(db, tenant_a, tenant_b):
    e_a = Evenement(tenant_id=tenant_a.id, reference="EVT-2026-001")
    e_b = Evenement(tenant_id=tenant_b.id, reference="EVT-2026-001")
    db.add_all([e_a, e_b]); await db.commit()  # OK cross-tenant

    e_dup = Evenement(tenant_id=tenant_a.id, reference="EVT-2026-001")
    db.add(e_dup)
    with pytest.raises(IntegrityError):
        await db.commit()
```

## DoD

- [ ] UNIQUE `(tenant_id, reference)` sur evenements
- [ ] FK `inventory_movements.event_id → evenements.id` ON DELETE SET NULL
- [ ] Test FK SET NULL fonctionne
- [ ] Test UNIQUE per-tenant

---

# Story B3.S7.T9 — `Tenant.incident_sla_hours` per-tenant (F773)

## Contexte

**Friction** : F773 (vague 6)
**Sévérité** : P1 — SLA incident hardcoded `24h` dans `IncidentService` → impossible de différencier Marveline (location évent, SLA 4h critique) vs CaroCorp (épicerie, SLA 24h OK)

### Description

Cible :
- `Tenant.incident_sla_hours: int = 24` (défaut 24h)
- Service `IncidentSlaResolver.resolve(tenant_id, severity) -> timedelta` qui retourne le délai selon tenant + severity

## Solution

```python
def upgrade() -> None:
    op.add_column("tenants", sa.Column(
        "incident_sla_hours", sa.Integer, nullable=False, server_default="24"
    ))
    op.create_check_constraint(
        "ck_tenants_incident_sla_positive", "tenants", "incident_sla_hours > 0"
    )

# app/services/incident/sla.py (NEW)
class IncidentSlaResolver:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve(self, tenant_id: int, severity: str) -> timedelta:
        tenant_sla = await self.db.scalar(
            select(Tenant.incident_sla_hours).where(Tenant.id == tenant_id)
        )
        # Modulation par severity
        if severity == "critical":
            return timedelta(hours=tenant_sla // 6)  # ex: tenant 24h → critical 4h
        if severity == "high":
            return timedelta(hours=tenant_sla // 2)  # ex: 24h → 12h
        return timedelta(hours=tenant_sla)  # standard
```

### Test

```python
async def test_sla_marveline_critical_4h(db, tenant_marveline):
    tenant_marveline.incident_sla_hours = 24  # tenant base
    sla = await resolver.resolve(tenant_marveline.id, severity="critical")
    assert sla == timedelta(hours=4)

async def test_sla_carocorp_critical_2h(db, tenant_carocorp):
    tenant_carocorp.incident_sla_hours = 12
    sla = await resolver.resolve(tenant_carocorp.id, severity="critical")
    assert sla == timedelta(hours=2)
```

## DoD

- [ ] Colonne `Tenant.incident_sla_hours` migration
- [ ] Service `IncidentSlaResolver` livré
- [ ] CHECK > 0
- [ ] Test : modulation critical/high/standard correcte

---

## Critères de succès Sprint B3.S7

- [ ] **F826** : `Supplier.code` UNIQUE per-tenant
- [ ] **F827/F828** : `SupplierOrder.reference` UNIQUE + status ENUM + FSM matrix
- [ ] **F829** : CHECK `qty_received + qty_damaged + qty_missing <= qty_ordered`
- [ ] **F833** : drop colonnes `lines_json` dupliquées (source unique)
- [ ] **F830** : trigger DB auto-sync receipt → stock_items + inventory_movement + Outbox
- [ ] **F728** : `vente_lines.tva_rate_snapshot NOT NULL` (vérification post-B3.S3)
- [ ] **F737** : `Vente.payment_method` ENUM avec backfill
- [ ] **F739** : trigger DEFERRED `total_ttc = SUM(lines)`
- [ ] **F767/TR-24** : `Evenement.reference` UNIQUE + FK `inventory_movements.event_id`
- [ ] **F773** : `Tenant.incident_sla_hours` + `IncidentSlaResolver`
- [ ] Test E2E supplier receipt : INSERT receipt_line(qty=10) → 10 stock_items + 1 movement + 1 outbox automatiquement

---

**Fin du document — 13-sprint-B3.S7.md**

**Bloc 3 Money complet : 7 sprints (S1-S7), ~10 semaines, livre toutes les frictions Money + angles morts vague 6.**
