# Sprint B3.S3 — PricingEngine + tva_rate_snapshot

> **STATUT** : ⏳ À démarrer après B3.S2
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev1
> **BLOQUE** : B3.S4 (conversion atomique consomme `PricingEngine.quote()`), B4.S4 (fusion engine + simulate)
> **DÉPEND DE** : B3.S2 (FSM helper appliqué Devis/Reservation/Invoice/Vente)
> **OBJECTIF** : Livrer le `PricingEngine` centralisé (TR-14) qui sert de source unique pour Devis, Reservation, Vente, Invoice — discount **cumul additif** (jamais multiplicatif, F565). Garantir `tva_rate_snapshot NOT NULL` sur les 4 tables de lignes facturables (TR-3) avec backfill historique. Drop fallback `0.20` hardcoded.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B3.S3.T1** | TR-3 — `tva_rate_snapshot` NOT NULL sur 4 tables (devis_lines, reservation_lines, vente_lines, invoice_lines) + backfill | P0 | 1.5 j | T2, T3 |
| **B3.S3.T2** | TR-14 — `PricingEngine` centralisé `quote()` + `PricingResult` snapshot | P0 | 2 j | T3, B3.S4 |
| **B3.S3.T3** | F565 — Discount cumul additif (jamais multiplicatif) — invariant CI | P0 | 0.5 j | aucun |
| **B3.S3.T4** | Drop fallback `0.20` hardcoded sur Devis/Reservation/Vente/Invoice services | P0 | 1 j | aucun |
| **B3.S3.T5** | Table `tva_rates` per-country avec `valid_from`/`valid_to` (Splendid TVA 0.10 vs Marveline 0.20) | P1 | 1 j | T1 |

**Total effort** : 6 jours-homme.

---

# Story B3.S3.T1 — `tva_rate_snapshot NOT NULL` sur lignes facturables

## Contexte

**Friction** : TR-3 (cf. `architecture-cible.md §3.2.3`)
**Sévérité** : P0 — comptabilité fausse pour Splendid (TVA 10% location événementiel) car fallback service hardcodé à `0.20`
**Code source** : `app/services/devis.py`, `app/services/reservation.py`, `app/services/vente.py`, `app/services/invoice.py`

### Description

Aujourd'hui : aucune des 4 tables `devis_lines`, `reservation_lines`, `vente_lines`, `invoice_lines` ne porte le taux de TVA capturé à l'émission. Les services calculent la TVA au runtime via `Product.tva_rate_id → tva_rates.rate` mais avec **fallback à `Decimal("0.20")` si NULL**. Conséquence pour Splendid (TVA 0.10) : si `Product.tva_rate_id` est NULL ou la jointure échoue → ligne portée à 20% → comptabilité fausse + déclaration TVA erronée.

L'invariant fiscal **article 289 CGI** : la facture émise est immutable, donc le taux TVA appliqué doit être figé sur la ligne (snapshot), pas recalculé.

## Solution

### Migration Alembic

```python
# alembic/versions/e3f4a5b6c7d8_add_tva_rate_snapshot_lines.py
def upgrade() -> None:
    # 1. Ajouter colonne nullable + backfill
    for table in ("devis_lines", "reservation_lines", "vente_lines", "invoice_lines"):
        op.add_column(
            table,
            sa.Column("tva_rate_snapshot", sa.Numeric(5, 4), nullable=True),
        )
        # Backfill : Product.tva_rate_id → tva_rates.rate
        op.execute(text(f"""
            UPDATE {table} l
            SET tva_rate_snapshot = COALESCE(tr.rate, 0.20)
            FROM products p
            LEFT JOIN tva_rates tr ON tr.id = p.tva_rate_id
            WHERE l.product_id = p.id
              AND l.tva_rate_snapshot IS NULL
        """))
        # NOT NULL après backfill
        op.alter_column(table, "tva_rate_snapshot", nullable=False)
        # CHECK : taux dans [0, 1]
        op.create_check_constraint(
            f"ck_{table}_tva_rate_snapshot_range",
            table,
            "tva_rate_snapshot >= 0 AND tva_rate_snapshot <= 1",
        )

def downgrade() -> None:
    for table in ("devis_lines", "reservation_lines", "vente_lines", "invoice_lines"):
        op.drop_constraint(f"ck_{table}_tva_rate_snapshot_range", table)
        op.drop_column(table, "tva_rate_snapshot")
```

### Modèles SQLAlchemy

```python
# app/models/devis.py, reservation.py, vente.py, invoice.py
class DevisLine(Base):
    __tablename__ = "devis_lines"
    # ... existing
    tva_rate_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False
    )

class ReservationLine(Base):
    __tablename__ = "reservation_lines"
    tva_rate_snapshot: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)

class VenteLine(Base):
    __tablename__ = "vente_lines"
    tva_rate_snapshot: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)

class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    tva_rate_snapshot: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
```

### Schemas Pydantic

```python
# app/schemas/lines.py
class LineCreate(BaseSchema):
    product_id: int
    qty: int
    unit_price_ht_cents: int
    # tva_rate_snapshot calculé serveur — JAMAIS depuis le client
    # (sécurité : empêche un client de fausser le taux à 0)
```

### Tests

```python
# tests/test_tva_rate_snapshot.py
async def test_tva_rate_snapshot_required(db, tenant, product):
    """TR-3 : insertion sans tva_rate_snapshot → IntegrityError."""
    line = DevisLine(devis_id=..., product_id=product.id, qty=1, unit_price_ht_cents=1000)
    db.add(line)
    with pytest.raises(IntegrityError, match="tva_rate_snapshot"):
        await db.commit()

async def test_tva_rate_range_check(db, tenant, product):
    """CHECK : taux > 1 (200%) → IntegrityError."""
    line = DevisLine(..., tva_rate_snapshot=Decimal("2.0"))
    db.add(line)
    with pytest.raises(IntegrityError, match="ck_devis_lines_tva_rate_snapshot_range"):
        await db.commit()
```

## DoD

- [ ] Migration appliquée sur les 4 tables
- [ ] Backfill historique vérifié : `SELECT COUNT(*) FROM devis_lines WHERE tva_rate_snapshot IS NULL` = 0
- [ ] Modèles SQLAlchemy : `Mapped[Decimal] = mapped_column(Numeric(5,4), nullable=False)`
- [ ] CHECK constraint `tva_rate_snapshot >= 0 AND <= 1` actif
- [ ] Tests : insertion NULL → IntegrityError ; insertion > 1 → IntegrityError

---

# Story B3.S3.T2 — `PricingEngine` centralisé

## Contexte

**Friction** : TR-14 (cf. `architecture-cible.md §3.2.4`)
**Sévérité** : P0 — divergence calcul prix entre Devis, Reservation, Vente
**Code source** : `app/services/devis.py:calculate_total`, `app/services/reservation.py:_compute_total`, `app/services/vente.py:_total`, `app/services/pricing_engine.py` (existant mais non utilisé par les 3 autres)

### Description

Aujourd'hui : 4 services calculent indépendamment `total_ht`, `total_tva`, `total_ttc` avec des règles légèrement divergentes (arrondis, ordre application discount, snapshot TVA). Symptômes :
- Devis dit `1100€ TTC`, Reservation convertie dit `1099,99€` (drift arrondi)
- `app/services/pricing_engine.py` n'est appelé que par `/api/v1/pricing/simulate`, jamais par Devis/Reservation
- Discount Marveline `-10% fidélité` + `-5% saisonnier` : Devis applique `-15%` (additif), Reservation applique `(1-0.10)×(1-0.05) = -14.5%` (multiplicatif) — **drift comptable**

## Solution

### Architecture cible

```python
# app/services/pricing/engine.py (NEW — fusion services/pricing_engine.py)
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence


@dataclass(frozen=True)
class LineInput:
    product_id: int
    qty: int
    unit_price_ht_cents: int
    tva_rate: Decimal  # snapshot capturé en amont


@dataclass(frozen=True)
class DiscountRule:
    code: str  # 'fidelity_l_incontournable', 'seasonal_summer', etc.
    discount_pct: Decimal  # Numeric(5,4) — ex: 0.1000 pour 10%
    applies_to: str  # 'all' | 'product' | 'category'
    target_id: int | None = None


@dataclass(frozen=True)
class LineSnapshot:
    """Snapshot exact à inscrire en ligne — source unique."""
    product_id: int
    qty: int
    unit_price_ht_cents: int
    tva_rate_snapshot: Decimal
    discount_pct_applied: Decimal  # cumul additif total
    line_total_ht_cents: int   # qty × unit × (1 - discount)
    line_total_tva_cents: int
    line_total_ttc_cents: int


@dataclass(frozen=True)
class PricingResult:
    lines: tuple[LineSnapshot, ...]
    total_ht_cents: int
    total_tva_cents: int
    total_ttc_cents: int
    discounts_applied: tuple[DiscountRule, ...]


class PricingEngine:
    """Source unique de calcul prix pour Devis, Reservation, Vente, Invoice.

    Cumul additif (Q25=A, F565) : discount_pct_total = sum(rule.discount_pct).
    Clamp [0, 1] (jamais > 100%).
    """

    def quote(
        self,
        lines: Sequence[LineInput],
        discounts: Sequence[DiscountRule],
        tenant_id: int,
    ) -> PricingResult:
        line_snapshots: list[LineSnapshot] = []
        total_ht = 0
        total_tva = 0

        for line in lines:
            # 1. Sélectionner règles applicables à cette ligne
            applicable = self._filter_rules(line, discounts)
            # 2. Cumul additif (jamais multiplicatif)
            discount_total = sum((r.discount_pct for r in applicable), Decimal("0"))
            discount_total = max(Decimal("0"), min(Decimal("1"), discount_total))

            # 3. Calcul ligne (centimes, arrondi banker fiscal)
            gross_ht = Decimal(line.unit_price_ht_cents) * Decimal(line.qty)
            net_ht = (gross_ht * (Decimal("1") - discount_total)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            line_tva = (net_ht * line.tva_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            line_ttc = net_ht + line_tva

            line_snapshots.append(LineSnapshot(
                product_id=line.product_id,
                qty=line.qty,
                unit_price_ht_cents=line.unit_price_ht_cents,
                tva_rate_snapshot=line.tva_rate,
                discount_pct_applied=discount_total,
                line_total_ht_cents=int(net_ht),
                line_total_tva_cents=int(line_tva),
                line_total_ttc_cents=int(line_ttc),
            ))
            total_ht += int(net_ht)
            total_tva += int(line_tva)

        return PricingResult(
            lines=tuple(line_snapshots),
            total_ht_cents=total_ht,
            total_tva_cents=total_tva,
            total_ttc_cents=total_ht + total_tva,
            discounts_applied=tuple(discounts),
        )

    def _filter_rules(self, line: LineInput, rules: Sequence[DiscountRule]) -> list[DiscountRule]:
        return [
            r for r in rules
            if r.applies_to == "all"
            or (r.applies_to == "product" and r.target_id == line.product_id)
            or (r.applies_to == "category" and self._product_in_category(line.product_id, r.target_id))
        ]
```

### Intégration services

```python
# app/services/devis.py (refacto)
class DevisService:
    def __init__(self, db: AsyncSession, pricing: PricingEngine, tva_resolver: TvaRateResolver):
        self.db = db
        self.pricing = pricing
        self.tva = tva_resolver

    async def create_devis(self, tenant_id: int, lines_input: list[LineCreate]) -> Devis:
        # 1. Capturer tva_rate snapshot par produit (T1 + T5)
        line_inputs = [
            LineInput(
                product_id=l.product_id,
                qty=l.qty,
                unit_price_ht_cents=l.unit_price_ht_cents,
                tva_rate=await self.tva.resolve_for_product(l.product_id, tenant_id),
            )
            for l in lines_input
        ]
        # 2. Discounts depuis tenant + customer (LoyaltyTier, etc.)
        discounts = await self._resolve_discounts(tenant_id, customer_id)
        # 3. Calcul unique via PricingEngine
        result = self.pricing.quote(line_inputs, discounts, tenant_id)
        # 4. Persister snapshot
        devis = Devis(
            tenant_id=tenant_id,
            total_ht_cents=result.total_ht_cents,
            total_tva_cents=result.total_tva_cents,
            total_ttc_cents=result.total_ttc_cents,
            lines=[
                DevisLine(
                    product_id=ls.product_id,
                    qty=ls.qty,
                    unit_price_ht_cents=ls.unit_price_ht_cents,
                    tva_rate_snapshot=ls.tva_rate_snapshot,
                    discount_pct_applied=ls.discount_pct_applied,
                    line_total_ht_cents=ls.line_total_ht_cents,
                    line_total_tva_cents=ls.line_total_tva_cents,
                )
                for ls in result.lines
            ],
        )
        self.db.add(devis)
        return devis
```

### Tests d'invariance cross-service

```python
# tests/test_pricing_engine.py
async def test_devis_reservation_invoice_same_total(db, tenant, customer):
    """Invariant : Devis → Reservation → Invoice donne même total au cent."""
    devis = await devis_service.create_devis(tenant_id, lines, customer_id)
    reservation = await reservation_service.from_devis(devis.id)
    invoice = await invoice_service.from_reservation(reservation.id)

    assert devis.total_ht_cents == reservation.total_ht_cents == invoice.total_ht_cents
    assert devis.total_tva_cents == reservation.total_tva_cents == invoice.total_tva_cents

async def test_pricing_engine_consistency_simulate_vs_apply(db):
    """B4.S4 prep : POST /pricing/simulate retourne EXACTEMENT le même résultat
    que PricingEngine.quote() utilisé en interne."""
    payload = {"lines": [...], "customer_id": 42}
    response = await client.post("/api/v1/pricing/simulate", json=payload)
    engine_result = pricing_engine.quote(...)
    assert response.json()["total_ttc_cents"] == engine_result.total_ttc_cents
```

## DoD

- [ ] `app/services/pricing/engine.py` livré avec `PricingEngine.quote()`
- [ ] `LineInput`, `DiscountRule`, `LineSnapshot`, `PricingResult` dataclasses frozen
- [ ] Refacto `DevisService`, `ReservationService`, `VenteService`, `InvoiceService` pour appeler `pricing.quote()`
- [ ] Suppression des `_compute_total`, `_calculate_total`, `_total` dupliqués
- [ ] Test d'invariance cross-service : Devis→Reservation→Invoice → même total au cent
- [ ] Test consistency `/pricing/simulate` ↔ `PricingEngine` (préparation B4.S4)

---

# Story B3.S3.T3 — Discount cumul additif (F565)

## Contexte

**Friction** : F565 (cf. `architecture-cible.md §3.2.4`, vague 1)
**Sévérité** : P0 — drift comptable Marveline (clients fidélité Incontournable + saisonnier)
**Code source** : `app/services/loyalty.py:apply_tier_discount` × `app/services/pricing_engine.py:_apply_seasonal`

### Description

Aujourd'hui : `LoyaltyService` applique `total *= (1 - 0.10)` puis `PricingEngine` applique `total *= (1 - 0.05)`. Résultat : `1000 × 0.90 × 0.95 = 855€` au lieu de `1000 × 0.85 = 850€` attendu. **Drift 5€ par devis × 200 devis/mois = 1000€/mois sur Marveline**.

Décision Q25=A : cumul **additif** (sum des `discount_pct`, clamp [0, 1]). Cohérent avec règles métier France ("addition des remises").

## Solution

```python
# app/services/pricing/engine.py (déjà couvert par T2)
discount_total = sum((r.discount_pct for r in applicable), Decimal("0"))
discount_total = max(Decimal("0"), min(Decimal("1"), discount_total))
net_ht = gross_ht * (Decimal("1") - discount_total)
```

### Invariant CI

```python
# tools/check_no_multiplicative_discount.py
"""Refuse `* (1 - discount)` chainés dans le code services."""
import ast, sys
from pathlib import Path

FORBIDDEN = re.compile(r"\*\s*\(\s*1\s*-\s*\w+\s*\)\s*\*\s*\(\s*1\s*-")

violations = []
for py in Path("app/services").rglob("*.py"):
    if FORBIDDEN.search(py.read_text()):
        violations.append(str(py))

if violations:
    print(f"❌ Multiplicative discount détecté dans : {violations}")
    sys.exit(1)
print("✅ Cumul additif respecté")
```

Ajouté à `54-ci-invariants.md` script #24.

### Test

```python
async def test_discount_additif_pas_multiplicatif():
    rules = [
        DiscountRule(code="fidelity", discount_pct=Decimal("0.10"), applies_to="all"),
        DiscountRule(code="seasonal", discount_pct=Decimal("0.05"), applies_to="all"),
    ]
    line = LineInput(product_id=1, qty=1, unit_price_ht_cents=10000, tva_rate=Decimal("0.20"))
    result = engine.quote([line], rules, tenant_id=1)
    # 10000 × (1 - 0.15) = 8500 (additif)  vs  10000 × 0.90 × 0.95 = 8550 (multiplicatif)
    assert result.lines[0].line_total_ht_cents == 8500

async def test_discount_clamp_above_100pct():
    rules = [
        DiscountRule(code="r1", discount_pct=Decimal("0.60"), applies_to="all"),
        DiscountRule(code="r2", discount_pct=Decimal("0.50"), applies_to="all"),
    ]
    line = LineInput(product_id=1, qty=1, unit_price_ht_cents=10000, tva_rate=Decimal("0.20"))
    result = engine.quote([line], rules, tenant_id=1)
    # 0.60 + 0.50 = 1.10 → clamp à 1.0 → ligne gratuite, JAMAIS négative
    assert result.lines[0].line_total_ht_cents == 0
```

## DoD

- [ ] Cumul additif implémenté dans `PricingEngine.quote()`
- [ ] Clamp `[0, 1]` testé (somme > 100% → 100%, jamais négatif)
- [ ] Script CI `tools/check_no_multiplicative_discount.py` actif
- [ ] Test cross-règles fidélité + saisonnier → résultat additif

---

# Story B3.S3.T4 — Drop fallback `0.20` hardcoded

## Contexte

**Friction** : conséquence directe TR-3 — fallback fiscal incorrect
**Sévérité** : P0 — Splendid (TVA 0.10) facturée à 20%
**Code source** : `app/services/devis.py`, `app/services/reservation.py`, `app/services/vente.py`, `app/services/invoice.py`, `app/services/pricing_engine.py`

### Description

Aujourd'hui :
```python
# app/services/devis.py:148
tva_rate = product.tva_rate.rate if product.tva_rate else Decimal("0.20")
# app/services/vente.py:92
TVA_DEFAULT = Decimal("0.20")
```

Ce fallback masque toute donnée incohérente (Product.tva_rate_id NULL, jointure échouée) au lieu de **fail-fast**.

## Solution

### Suppression hardcoded + fail-fast

> **Note Vague 5 — étape transitoire** : ce résolveur via `Product.tva_rate_id → TvaRate` est livré en B3.S3 pour débloquer `tva_rate_snapshot NOT NULL` sur les lignes (TR-3). Il sera **remplacé en B4.S3.T2** (Vague 1 patch Q23=A) par la cascade `coalesce(Product.tva_rate_override, Category.tva_rate)`. Le modèle `TvaRate(Base)` table reste comme **catalog FR législatif** (FR_STANDARD=0.20, FR_INTERMEDIATE=0.10, etc.) consulté par UI admin pour seeder `Category.tva_rate` au provisioning. La colonne `Product.tva_rate_id` sera droppée en B4.S3.T2 après backfill `Category.tva_rate`.

```python
# app/services/pricing/tva.py (NEW — étape B3.S3, remplacé B4.S3.T2)
class TvaResolutionError(Exception):
    """Levée si Product.tva_rate_id NULL ou tva_rate inactive — pas de fallback silencieux."""

class TvaRateResolver:
    """B3.S3 — résolveur transitoire via Product.tva_rate_id. Remplacé B4.S3.T2 par cascade Q23=A."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_for_product(self, product_id: int, tenant_id: int) -> Decimal:
        result = await self.db.execute(
            select(TvaRate.rate)
            .join(Product, Product.tva_rate_id == TvaRate.id)
            .where(
                Product.id == product_id,
                Product.tenant_id == tenant_id,
                TvaRate.is_active.is_(True),
            )
        )
        rate = result.scalar_one_or_none()
        if rate is None:
            raise TvaResolutionError(
                f"Product {product_id} sans tva_rate_id valide (tenant={tenant_id}). "
                "Corriger via /api/v1/products/{id}/tva avant émission ligne."
            )
        return rate
```

### Migration tests legacy

```bash
# Search & destroy
grep -rn 'Decimal("0.20")\|TVA_DEFAULT\|tva_default' app/ tests/
# Remplacer par TvaRateResolver.resolve_for_product()
# Tests qui mockaient le fallback : injecter TvaRate explicite dans la fixture
```

### Endpoint admin pour corriger les Product orphelins

```python
# app/api/v1/endpoints/products.py
@router.get("/products/orphan-tva", dependencies=[require_scope(Scope.PRODUCTS_WRITE)])
async def list_products_without_tva(tenant_id: int = Depends(...)):
    """Liste produits dont tva_rate_id IS NULL — bloquant pour émission devis/facture."""
    return await product_service.list_orphan_tva(tenant_id)
```

### Test fail-fast

```python
async def test_devis_creation_fails_if_product_without_tva(db, tenant):
    product = Product(tenant_id=tenant.id, name="orphan", tva_rate_id=None)
    db.add(product); await db.flush()

    with pytest.raises(TvaResolutionError, match="sans tva_rate_id valide"):
        await devis_service.create_devis(tenant.id, [LineCreate(product_id=product.id, qty=1, ...)])
```

## DoD

- [ ] `grep -rn 'Decimal("0.20")' app/services/` → 0 résultat
- [ ] `TvaRateResolver` injecté DI sur tous services Money
- [ ] Endpoint `/products/orphan-tva` opérationnel pour audit pré-migration
- [ ] Test : Product sans `tva_rate_id` → `TvaResolutionError` 422
- [ ] Migration script : `UPDATE products SET tva_rate_id = (SELECT id FROM tva_rates WHERE rate=0.20 AND country='FR') WHERE tva_rate_id IS NULL` (correctif one-shot pré-deploy)

---

# Story B3.S3.T5 — Table `tva_rates` per-country avec validité temporelle

## Contexte

**Cible** : supporter Splendid (TVA 0.10 location événementiel) cohabitant avec Marveline (TVA 0.20) sur la même DB. Préparer B3.S6 e-invoicing UE (taux multi-pays).

### Description

Aujourd'hui : `tva_rates` table existe mais sans `country` ni `valid_from`/`valid_to`. Quand TVA réduite passe de 5.5% à 6% (hypothèse 2027), pas de moyen de gérer la transition sans casser les anciennes factures.

## Solution

### Migration

```python
# alembic/versions/e3f4a5b6c7d9_tva_rates_country_validity.py
def upgrade() -> None:
    op.add_column("tva_rates", sa.Column("country", sa.String(2), nullable=False, server_default="FR"))
    op.add_column("tva_rates", sa.Column("valid_from", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")))
    op.add_column("tva_rates", sa.Column("valid_to", sa.Date(), nullable=True))
    op.create_check_constraint(
        "ck_tva_rates_country_iso", "tva_rates", "country ~ '^[A-Z]{2}$'"
    )
    op.create_index(
        "ix_tva_rates_country_active",
        "tva_rates",
        ["country", "code"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    # Seed France : TVA standard 0.20, intermédiaire 0.10, réduit 0.055, super-réduit 0.021
    op.execute(text("""
        INSERT INTO tva_rates (code, rate, country, valid_from, is_active)
        VALUES
          ('FR_STANDARD', 0.20, 'FR', '2014-01-01', TRUE),
          ('FR_INTERMEDIATE', 0.10, 'FR', '2014-01-01', TRUE),
          ('FR_REDUCED', 0.055, 'FR', '2014-01-01', TRUE),
          ('FR_SUPER_REDUCED', 0.021, 'FR', '2014-01-01', TRUE)
        ON CONFLICT (code) DO NOTHING
    """))
```

### Modèle

```python
# app/models/tva_rate.py
class TvaRate(Base):
    __tablename__ = "tva_rates"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        CheckConstraint("rate >= 0 AND rate <= 1", name="ck_tva_rates_range"),
        CheckConstraint("country ~ '^[A-Z]{2}$'", name="ck_tva_rates_country_iso"),
    )
```

### Splendid Onboarding

```python
# Pour Splendid (TVA location événementiel = 10%) :
# Product.tva_rate_id pointe sur TvaRate(code='FR_INTERMEDIATE', rate=0.10)
# Capturé dans tva_rate_snapshot à émission ligne → comptabilité juste
```

## DoD

- [ ] Migration appliquée : colonnes `country`, `valid_from`, `valid_to`
- [ ] Seed France 4 taux standard
- [ ] CHECK ISO 3166-1 alpha-2 sur `country`
- [ ] Index unique `(country, code) WHERE valid_to IS NULL`
- [ ] Test : créer 2 taux `FR_STANDARD` actifs simultanément → IntegrityError

---

## Critères de succès Sprint B3.S3

- [ ] **TR-3 résolu** : 4 tables lignes facturables ont `tva_rate_snapshot NOT NULL`, 0 ligne historique sans valeur
- [ ] **TR-14 résolu** : `PricingEngine.quote()` utilisé par `DevisService`, `ReservationService`, `VenteService`, `InvoiceService` ; 0 `_compute_total` dupliqué
- [ ] **F565 résolu** : cumul additif vérifié en test + script CI bloque réintroduction
- [ ] Drop fallback `0.20` : `grep Decimal("0.20") app/services/` → 0
- [ ] Splendid TVA 10% testé end-to-end : devis → résa → invoice → ligne portée à 0.10 sur les 4 tables
- [ ] Invariant cross-service : Devis.total = Reservation.total = Invoice.total au cent près

---

**Fin du document — 13-sprint-B3.S3.md**
