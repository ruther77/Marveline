# Sprint B4.S3 — Category FK obligatoire + tva_rate sur Category

> **STATUT** : ⏳ À démarrer après B4.S2
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev2
> **BLOQUE** : B4.S4 (PricingEngine fusion utilise category_id), B5.S5 (categorie_id FK ETL pattern parallèle)
> **DÉPEND DE** : B4.S2 (StockItemFSM stable)
> **OBJECTIF** : Faire de `Category` une **FK obligatoire** de `Product` (TR-16). Drop la String CHECK 20 valeurs schizophrène. Migrer `tva_rate` de `Product` vers `Category` (TR-18, F487). Migrer `advance_booking_days` (TR-33, F496). Ajouter trigger cycle prevention + depth max 5 (TR-35, F493/F494). **NB** : `brand_code` retiré de ce sprint, drop intégral via B7.S2 (Q43=B).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B4.S3.T1** | TR-16 — `Category` FK obligatoire `Product.category_id NOT NULL` + drop String CHECK | P0 | 2.5 j | T2 |
| **B4.S3.T2** | TR-18/F487 / **Q23=A** — `Category.tva_rate Numeric(5,4)` + `Product.tva_rate_override Numeric(5,4) NULL` + drop `Product.tva_rate float` + service resolver cascade | P0 | 1.75 j | aucun |
| **B4.S3.T3** | TR-33/F496 — `Category.advance_booking_days` + drop `Product.requires_advance_booking_days` | P1 | 0.5 j | aucun |
| **B4.S3.T4** | TR-35/F493/F494 — Trigger cycle prevention + depth max 5 | P1 | 1 j | aucun |
| **B4.S3.T5** | Seed Category — 20 valeurs Marveline + per-tenant initial | P0 | 1 j | T1 |
| **B4.S3.T6** | TR-37 — Vocabulaire `condition` Product unifié avec MovementItem (`good`, `damaged`, `missing`, `perfect`) | P1 | 0.5 j | aucun |

**Total effort** : 7 jours-homme.

---

# Story B4.S3.T1 — `Category` FK obligatoire (TR-16)

## Contexte

**Friction** : TR-16 (cf. `architecture-cible.md §4.2.1`)
**Sévérité** : P0 — `Product.category String CHECK 20` + table `Category` orpheline jamais référencée = catégorie schizophrène
**Code source** : `app/models/product.py`, `app/models/category.py`

### Description

Aujourd'hui :
- `Product.category String(64) CHECK (category IN ('assiettes', 'verres', ...))`  — 20 valeurs hardcoded
- Table `Category` existe mais aucun FK depuis Product
- Ajouter une catégorie = migration Alembic + DROP CHECK + ALTER ADD CHECK

Cible :
- `Product.category_id INT NOT NULL FK Category(id)`
- Drop colonne `Product.category String`
- Drop CHECK 20 valeurs
- Table `Category` devient source de vérité

## Solution

### Migration backward-compatible 4 étapes

```python
# alembic/versions/h1a2b3c4d5f7_category_fk_step1_seed_table.py
"""Étape 1 : seed Category per-tenant avec 20 valeurs canoniques."""
def upgrade() -> None:
    # Seed pour chaque tenant existant (cf. T5 pour détail)
    op.execute(text("""
        INSERT INTO categories (tenant_id, code, name, tva_rate, depth, is_active)
        SELECT t.id, c.code, c.name, 0.20, 0, true
        FROM tenants t
        CROSS JOIN (VALUES
            ('assiettes', 'Assiettes'),
            ('verres', 'Verres'),
            ('couverts', 'Couverts'),
            -- ... 20 valeurs
        ) AS c(code, name)
        ON CONFLICT (tenant_id, code) DO NOTHING
    """))

# alembic/versions/h1a2b3c4d5f8_category_fk_step2_add_nullable.py
"""Étape 2 : ajouter category_id nullable + backfill."""
def upgrade() -> None:
    op.add_column("products", sa.Column("category_id", sa.Integer, nullable=True))
    op.create_foreign_key(
        "fk_products_category_id", "products", "categories",
        ["category_id"], ["id"], ondelete="RESTRICT",
    )
    # Backfill : products.category String → category_id via JOIN sur Category.code
    op.execute(text("""
        UPDATE products p
        SET category_id = c.id
        FROM categories c
        WHERE c.tenant_id = p.tenant_id
          AND c.code = p.category
          AND p.category_id IS NULL
    """))

# alembic/versions/h1a2b3c4d5f9_category_fk_step3_not_null.py
"""Étape 3 : NOT NULL après audit backfill."""
def upgrade() -> None:
    # Audit pré-NOT NULL
    orphans = op.get_bind().scalar(text("SELECT COUNT(*) FROM products WHERE category_id IS NULL"))
    if orphans > 0:
        raise Exception(f"{orphans} products sans category_id — fix avant migration")
    op.alter_column("products", "category_id", nullable=False)

# alembic/versions/h1a2b3c4d5fa_category_fk_step4_drop_legacy.py
"""Étape 4 : drop colonne + drop CHECK constraint legacy."""
def upgrade() -> None:
    with contextlib.suppress(Exception):
        op.drop_constraint("check_product_category_valid", "products")
    with contextlib.suppress(Exception):
        op.drop_column("products", "category")
```

### Modèles

```python
# app/models/category.py
class Category(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tva_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)  # T2
    advance_booking_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # T3
    cleaning_fee_cents_default: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_categories_tenant_code"),
        CheckConstraint("depth <= 5", name="ck_categories_depth_max"),
    )

# app/models/product.py
class Product(Base):
    # ... existing
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)
    # tva_rate, advance_booking_days : DROP (dérivés Category via T2/T3)
    category: Mapped["Category"] = relationship("Category")
```

### Test

```python
async def test_product_requires_category_id(db, tenant):
    with pytest.raises(IntegrityError, match="category_id"):
        product = Product(tenant_id=tenant.id, name="X")  # pas de category_id
        db.add(product); await db.commit()

async def test_product_category_string_dropped(db, tenant, category):
    product = Product(tenant_id=tenant.id, name="X", category_id=category.id)
    db.add(product); await db.commit()
    with pytest.raises(AttributeError):
        _ = product.category_string  # ancienne colonne droppée
```

## DoD

- [ ] Migration 4 étapes (seed → add nullable → NOT NULL → drop legacy)
- [ ] Modèle `Category` avec FK self parent_id, depth, tva_rate, advance_booking_days
- [ ] Drop colonne `Product.category String` + CHECK constraint
- [ ] Test : INSERT Product sans category_id → IntegrityError
- [ ] Test : 200 Products historiques migrés avec succès

---

# Story B4.S3.T2 — `Category.tva_rate` + `Product.tva_rate_override` (TR-18/F487/Q23=A)

## Contexte

**Friction** : TR-18, F487 (cf. `architecture-cible.md §4.2.1` + Q23=A verrouillée)
**Décision** : **Q23=A** — `Category.tva_rate Numeric(5,4) NOT NULL` + `Product.tva_rate_override Numeric(5,4) NULL` pour exception métier (un produit avec TVA différente de sa catégorie)
**Sévérité** : P0 — `Product.tva_rate float default 0.20` Marveline-spécifique → Restaurant 10% / Épicerie 5,5% impossibles, défaut hardcoded faux
**Code source** : `app/models/product.py`

### Description

Cible (Q23=A) :
1. `tva_rate` migre de `Product` vers `Category` (hiérarchie : "tous les verres ont la même TVA")
2. **`Product.tva_rate_override Numeric(5,4) NULL`** pour cas dérogatoires (un produit hors-norme)
3. `TvaRateResolver` lit `Product.tva_rate_override ?? Product.category.tva_rate`

## Solution

### Migration

```python
# alembic/versions/h1a2b3c4d5fb_category_tva_rate_and_product_override.py
def upgrade() -> None:
    # Already added via T1 step1. Update tva_rate selon catégorie historique.
    # Backfill : pour chaque category, récupérer tva_rate moyenne des products historiques
    op.execute(text("""
        UPDATE categories c
        SET tva_rate = (
            SELECT AVG(p.tva_rate)::numeric(5,4)
            FROM products p
            WHERE p.tenant_id = c.tenant_id AND p.category = c.code
        )
        WHERE c.tva_rate = 0.20  -- placeholder T1
        AND EXISTS (SELECT 1 FROM products p WHERE p.tenant_id = c.tenant_id AND p.category = c.code)
    """))

    # Q23=A — Ajouter Product.tva_rate_override pour exceptions métier
    op.add_column(
        "products",
        sa.Column("tva_rate_override", sa.Numeric(5, 4), nullable=True),
    )
    op.create_check_constraint(
        "ck_products_tva_rate_override_range",
        "products",
        "tva_rate_override IS NULL OR (tva_rate_override >= 0 AND tva_rate_override <= 1)",
    )
    # Backfill : si Product.tva_rate diverge de sa Category.tva_rate → save dans override
    op.execute(text("""
        UPDATE products p
        SET tva_rate_override = p.tva_rate
        FROM categories c
        WHERE c.tenant_id = p.tenant_id
          AND c.code = p.category
          AND p.tva_rate IS NOT NULL
          AND p.tva_rate != c.tva_rate
    """))

    # Drop Product.tva_rate (remplacé par Category + override)
    op.drop_column("products", "tva_rate")
```

### Modèle

```python
# app/models/product.py
class Product(Base):
    # ...
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    tva_rate_override: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True,
        comment="Q23=A : NULL = hérite Category.tva_rate ; sinon override ce produit",
    )
```

### TvaRateResolver update (Q23=A cascade)

```python
# app/services/pricing/tva.py (livré B3.S3.T4)
class TvaRateResolver:
    async def resolve_for_product(self, product_id: int, tenant_id: int) -> Decimal:
        # Q23=A : Product.tva_rate_override ?? Category.tva_rate
        result = await self.db.execute(
            select(
                func.coalesce(Product.tva_rate_override, Category.tva_rate).label("rate")
            )
            .join(Category, Product.category_id == Category.id)
            .where(
                Product.id == product_id,
                Product.tenant_id == tenant_id,
                Category.is_active.is_(True),
            )
        )
        rate = result.scalar_one_or_none()
        if rate is None:
            raise TvaResolutionError(f"Product {product_id} sans Category tva_rate (tenant={tenant_id})")
        return rate
```

### Tests

```python
async def test_tva_rate_derived_from_category(db, tenant, restaurant_category):
    restaurant_category.tva_rate = Decimal("0.10")
    product = Product(tenant_id=tenant.id, name="Plat", category_id=restaurant_category.id)
    db.add(product); await db.commit()

    rate = await tva_resolver.resolve_for_product(product.id, tenant.id)
    assert rate == Decimal("0.10")  # hérite Category

async def test_tva_rate_override_wins_over_category(db, tenant, category_20):
    """Q23=A : override produit-spécifique pour exception métier."""
    category_20.tva_rate = Decimal("0.20")
    product = Product(
        tenant_id=tenant.id, name="Plat exceptionnel",
        category_id=category_20.id,
        tva_rate_override=Decimal("0.055"),  # exception : TVA réduite
    )
    db.add(product); await db.commit()

    rate = await tva_resolver.resolve_for_product(product.id, tenant.id)
    assert rate == Decimal("0.055")  # override gagne

async def test_tva_rate_override_range_check(db, tenant, category):
    """CHECK : override > 1 (200%) → IntegrityError."""
    product = Product(tenant_id=tenant.id, category_id=category.id, tva_rate_override=Decimal("2.0"))
    db.add(product)
    with pytest.raises(IntegrityError, match="ck_products_tva_rate_override_range"):
        await db.commit()
```

## DoD

- [ ] Drop `Product.tva_rate` colonne
- [ ] `Category.tva_rate Numeric(5,4)` NOT NULL
- [ ] **Q23=A livré** : `Product.tva_rate_override Numeric(5,4) NULL` + CHECK [0,1]
- [ ] Backfill : Products dont `tva_rate` divergeait de leur Category → `tva_rate_override` sauvé
- [ ] `TvaRateResolver` cascade : `tva_rate_override ?? Category.tva_rate`
- [ ] Test : Restaurant Category 10% → Product hérite 10%
- [ ] Test : override 5.5% sur Category 20% → 5.5% wins
- [ ] Test : override > 1 → IntegrityError

---

# Story B4.S3.T3 — `Category.advance_booking_days` (TR-33/F496)

## Contexte

**Friction** : TR-33, F496
**Sévérité** : P1 — "90 jours pour nappages, 0 sinon" dupliqué sur N rows Product

### Description

Cible : déplacer `requires_advance_booking_days` de Product vers Category.

## Solution

```python
def upgrade() -> None:
    # Backfill depuis Product
    op.execute(text("""
        UPDATE categories c
        SET advance_booking_days = COALESCE(
            (SELECT MAX(p.requires_advance_booking_days)
             FROM products p
             WHERE p.category_id = c.id), 0
        )
    """))
    op.drop_column("products", "requires_advance_booking_days")
```

### Test

```python
async def test_advance_booking_days_per_category(db, nappages_cat):
    nappages_cat.advance_booking_days = 90
    await db.commit()
    # Service ReservationValidator lit category.advance_booking_days
    days = await reservation_validator.required_advance(product.id)
    assert days == 90
```

## DoD

- [ ] Drop `Product.requires_advance_booking_days`
- [ ] `Category.advance_booking_days INT default 0`
- [ ] Service `ReservationValidator` lit via Category
- [ ] Test cohérence per-category

---

# Story B4.S3.T4 — Cycle prevention + depth max 5 (TR-35)

## Contexte

**Friction** : TR-35, F493, F494
**Sévérité** : P1 — boucle parent_id possible → stack overflow récursion ; pas de depth max

### Description

Cible :
1. Trigger BEFORE INSERT/UPDATE qui détecte cycle (`WITH RECURSIVE`)
2. CHECK constraint `depth <= 5`
3. Trigger BEFORE INSERT/UPDATE recalcule `depth` automatiquement

## Solution

```python
# alembic/versions/h1a2b3c4d5fc_category_cycle_depth_triggers.py
def upgrade() -> None:
    # Trigger cycle detect + depth recompute
    op.execute(text("""
        CREATE OR REPLACE FUNCTION category_cycle_depth_check()
        RETURNS TRIGGER AS $$
        DECLARE
            new_depth INT;
            cycle_check INT;
        BEGIN
            IF NEW.parent_id IS NULL THEN
                NEW.depth := 0;
                RETURN NEW;
            END IF;
            -- Cycle detect : NEW.id ne doit pas apparaître dans la lignée parent
            WITH RECURSIVE lineage AS (
                SELECT id, parent_id, 1 AS lvl
                FROM categories WHERE id = NEW.parent_id
                UNION ALL
                SELECT c.id, c.parent_id, l.lvl + 1
                FROM categories c JOIN lineage l ON c.id = l.parent_id
                WHERE l.lvl < 10  -- safety bound
            )
            SELECT COUNT(*) INTO cycle_check FROM lineage WHERE id = NEW.id;
            IF cycle_check > 0 THEN
                RAISE EXCEPTION 'category_cycle: parent chain cycles back to category %', NEW.id;
            END IF;
            -- Recompute depth from parent
            SELECT depth + 1 INTO new_depth FROM categories WHERE id = NEW.parent_id;
            IF new_depth > 5 THEN
                RAISE EXCEPTION 'category_depth_max_exceeded: depth=% > 5', new_depth;
            END IF;
            NEW.depth := new_depth;
            RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """))
    op.execute(text("""
        CREATE TRIGGER trg_categories_cycle_depth
        BEFORE INSERT OR UPDATE OF parent_id ON categories
        FOR EACH ROW EXECUTE FUNCTION category_cycle_depth_check()
    """))
```

### Test

```python
async def test_category_cycle_refused(db, cat_a, cat_b):
    cat_a.parent_id = cat_b.id
    cat_b.parent_id = cat_a.id  # cycle
    with pytest.raises(IntegrityError, match="category_cycle"):
        await db.commit()

async def test_category_depth_max_5(db, tenant):
    # Créer chaîne 6 niveaux
    cats = []
    for i in range(7):
        c = Category(tenant_id=tenant.id, code=f"c{i}", name=f"C{i}",
                     parent_id=cats[-1].id if cats else None,
                     tva_rate=Decimal("0.20"))
        db.add(c)
        if i < 6:
            await db.commit()
            cats.append(c)
        else:
            with pytest.raises(IntegrityError, match="depth_max_exceeded"):
                await db.commit()
```

## DoD

- [ ] Trigger cycle prevention + depth recompute
- [ ] CHECK `depth <= 5`
- [ ] Test cycle 2-niveaux → IntegrityError
- [ ] Test depth 6 → IntegrityError
- [ ] Test depth recompute auto

---

# Story B4.S3.T5 — Seed Category 20 valeurs Marveline + per-tenant

## Contexte

Migration data : créer Category par tenant avec les valeurs canoniques actuelles.

### Description

Pour chaque tenant existant, seed `categories` avec les 20 valeurs string actuelles de `Product.category`. Code = lower_snake.

## Solution

```python
# tools/seed_categories_per_tenant.py (one-shot pré-deploy)
MARVELINE_CATEGORIES = [
    ("assiettes", "Assiettes", Decimal("0.20"), 0),
    ("verres", "Verres", Decimal("0.20"), 0),
    ("couverts", "Couverts", Decimal("0.20"), 0),
    ("nappes", "Nappes", Decimal("0.20"), 90),  # advance_booking_days
    ("chaises", "Chaises", Decimal("0.20"), 30),
    # ... 20 valeurs
]

async def seed_for_tenant(tenant_id: int, vertical: str):
    if vertical == "location":
        return MARVELINE_CATEGORIES
    if vertical == "restaurant":
        return RESTAURANT_CATEGORIES  # tva_rate=0.10
    if vertical == "epicerie":
        return EPICERIE_CATEGORIES  # tva_rate=0.055 sur produits frais
    return []
```

## DoD

- [ ] Script seed paramétré par vertical
- [ ] Seed 20 valeurs Marveline + 15 Restaurant + 12 Épicerie
- [ ] Test : tenant Marveline a Categories 'nappes' avec `advance_booking_days=90`
- [ ] Test : tenant Restaurant a Categories tva_rate=0.10

---

# Story B4.S3.T6 — Vocabulaire `condition` unifié (TR-37)

## Contexte

**Friction** : TR-37, F495, F650
**Sévérité** : P1 — `Product.condition` = (`neuf/bon/use/hors_service`) ≠ `MovementItem.condition` = (`perfect/good/damaged/missing`). Typo `'use'` historique.

### Description

Cible : ENUM unique `item_condition` partagé : `perfect | good | damaged | missing | retired`.

## Solution

```python
def upgrade() -> None:
    op.execute(text("""
        CREATE TYPE item_condition AS ENUM ('perfect', 'good', 'damaged', 'missing', 'retired')
    """))
    # Backfill Product
    op.execute(text("""
        UPDATE products SET condition = CASE
            WHEN condition = 'neuf' THEN 'perfect'
            WHEN condition = 'bon' THEN 'good'
            WHEN condition = 'use' THEN 'damaged'  -- typo historique
            WHEN condition = 'hors_service' THEN 'retired'
            ELSE 'good'
        END
    """))
    op.execute(text("""
        ALTER TABLE products ALTER COLUMN condition TYPE item_condition USING condition::item_condition
    """))
    op.execute(text("""
        ALTER TABLE movement_items ALTER COLUMN condition TYPE item_condition USING condition::item_condition
    """))
```

```python
# app/constants/business.py
class ItemCondition(str, Enum):
    PERFECT = "perfect"
    GOOD = "good"
    DAMAGED = "damaged"
    MISSING = "missing"
    RETIRED = "retired"
```

## DoD

- [ ] ENUM `item_condition` unique
- [ ] Backfill Product + MovementItem
- [ ] Constants Python alignée
- [ ] Test : valeur invalide refusée
- [ ] Test : `'use'` typo historique migré → `'damaged'`

---

## Critères de succès Sprint B4.S3

- [ ] **TR-16 résolu** : `Category` FK obligatoire ; drop string CHECK 20 valeurs
- [ ] **TR-18/F487/Q23=A résolu** : `Category.tva_rate` + `Product.tva_rate_override` (exception métier) ; drop `Product.tva_rate` ; resolver cascade `override ?? category.rate`
- [ ] **TR-33/F496 résolu** : `Category.advance_booking_days`
- [ ] **TR-35/F493/F494 résolu** : trigger cycle + CHECK depth ≤ 5
- [ ] **TR-37 résolu** : ENUM `item_condition` unifié
- [ ] Seed per-tenant exécuté (Marveline / Restaurant / Épicerie)
- [ ] Test : Marveline Restaurant TVA cohérente per-Category
- [ ] Test : 200 produits backfillés

---

**Fin du document — 14-sprint-B4.S3.md**
