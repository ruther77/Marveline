# Sprint B4.S4 — PricingEngine fusion + RFMService + validators

> **STATUT** : ⏳ À démarrer après B4.S3
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev2
> **BLOQUE** : B4.S5, B5.S3 (RFM réutilisé pour resto/épicerie segmentation)
> **DÉPEND DE** : B3.S3 (PricingEngine Bloc 3 livré), B4.S3 (Category FK pour applies_to='category')
> **OBJECTIF** : Fusionner `services/pricing_engine.py` + endpoints `/pricing/simulate` derrière une seule classe `PricingEngine.calculate(lines, customer, event_date) -> PricingResult` (TR-21 cont.). Documenter et unifier la **stratégie cumulative additive** (F532 — vs first-match historique). Livrer scope `pricing:read` séparé pour `/simulate` (F533). Extraire `RFMService` partagé (TR-30) avec view matérialisée. Ajouter validators ISO country, SIRET Luhn, VAT VIES (TR-32 cont.).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B4.S4.T1** | TR-21 cont. — Fusion `PricingEngine.calculate()` + `/pricing/simulate` invariant CI | P0 | 2 j | T2 |
| **B4.S4.T2** | F532 — Stratégie cumul **additive** documentée et unifiée (drop first-match) | P0 | 1 j | aucun |
| **B4.S4.T3** | F533 — Scope `pricing:read` pour `/simulate` vs `pricing:write` pour `/apply` | P0 | 0.5 j | aucun |
| **B4.S4.T4** | F499 — Drop `calculate_price` variants éparpillés (consolidation PricingEngine) | P0 | 1 j | aucun |
| **B4.S4.T5** | TR-30 / **Q27=B** — `RFMService` per-tenant via `tenant_settings.rfm_thresholds JSONB` + view matérialisée + Celery refresh | P0 | 2 j | aucun |
| **B4.S4.T6** | Validators — ISO country, SIRET Luhn, VAT VIES (Q5 Bloc 1 cont.) | P1 | 1 j | aucun |
| **B4.S4.T7** | Cache Redis 5 min sur `_get_active_rules(tenant_id)` per-tenant | P1 | 0.5 j | aucun |

**Total effort** : 7.5 jours-homme.

---

# Story B4.S4.T1 — Fusion `PricingEngine.calculate()` (TR-21 cont.)

## Contexte

**Friction** : TR-21 (cf. `architecture-cible.md §4.2.5`)
**Sévérité** : P0 — `simulate` et `apply` divergent encore après B4.S1.T2 (convention `÷100` unifiée mais classes distinctes)
**Code source** : `app/services/pricing_engine.py`, `app/api/v1/endpoints/pricing.py`

### Description

Aujourd'hui (post B4.S1.T2 et B3.S3) :
- `PricingEngine.quote(lines, discounts, tenant_id)` (B3.S3) — utilisé par Devis/Resa/Vente/Invoice
- `app/api/v1/endpoints/pricing.py:simulate` — réimplémente une logique pricing parallèle pour preview admin

Cible : **une seule classe** `PricingEngine.calculate(lines, customer, event_date, tenant_id) -> PricingResult` qui :
1. Résout les `DiscountRule` actives (cache Redis 5min, T7)
2. Applique cumul additif (T2)
3. Retourne `PricingResult` snapshot identique pour simulate ET apply

`/pricing/simulate` devient un wrapper trivial qui sérialise `PricingResult`.

## Solution

### Refactor

```python
# app/services/pricing/engine.py (refacto post-B3.S3)
class PricingEngine:
    """Source unique pour Devis/Resa/Vente/Invoice + endpoint simulate."""

    async def calculate(
        self,
        lines: Sequence[LineInput],
        customer_id: UUID | None,
        event_date: date,
        tenant_id: int,
    ) -> PricingResult:
        # 1. Résoudre règles actives à event_date (cache Redis T7)
        rules = await self._get_active_rules(tenant_id, event_date)
        # 2. Filtrer rules applicables au customer (LoyaltyTier, segment RFM, etc.)
        customer_rules = await self._filter_customer_rules(rules, customer_id, tenant_id)
        # 3. Appel quote() partagé (B3.S3.T2)
        return self.quote(lines, customer_rules, tenant_id)


# app/api/v1/endpoints/pricing.py (refacto)
@router.post(
    "/pricing/simulate",
    dependencies=[Depends(require_scope(Scope.PRICING_READ))],
)
async def simulate_pricing(
    payload: SimulateRequest,
    user: User = Depends(get_current_user),
    engine: PricingEngine = Depends(get_pricing_engine),
):
    result = await engine.calculate(
        lines=[LineInput(**l.dict()) for l in payload.lines],
        customer_id=payload.customer_id,
        event_date=payload.event_date,
        tenant_id=user.tenant_id,
    )
    return PricingResultSchema.from_orm(result)
```

### Test invariant CI

```python
# tests/test_pricing_simulate_apply_invariant.py
async def test_simulate_equals_apply_to_the_cent(client, tenant, customer, product):
    """CI invariant : /simulate retourne EXACTEMENT le même résultat que appliqué par devis."""
    payload = {
        "customer_id": str(customer.id),
        "event_date": "2026-09-15",
        "lines": [{"product_id": product.id, "qty": 5, "unit_price_ht_cents": 10000}],
    }
    sim = await client.post("/api/v1/pricing/simulate", json=payload)
    devis = await client.post("/api/v1/devis", json={**payload, "customer_id": str(customer.id)})

    assert sim.json()["total_ht_cents"] == devis.json()["total_ht_cents"]
    assert sim.json()["total_tva_cents"] == devis.json()["total_tva_cents"]
    assert sim.json()["total_ttc_cents"] == devis.json()["total_ttc_cents"]
```

## DoD

- [ ] `PricingEngine.calculate()` méthode unique
- [ ] `/pricing/simulate` wrapper trivial
- [ ] Test invariant CI : simulate == apply au cent
- [ ] Drop logique pricing parallèle dans endpoint

---

# Story B4.S4.T2 — Stratégie cumul additive documentée (F532)

## Contexte

**Friction** : F532 (cf. `architecture-cible.md Q25=A` lignes 1100)
**Sévérité** : P0 — code historique a `first-match` (premier rule matchant gagne) tandis que B3.S3.T3 utilise `cumul additif` → behavior split

### Description

Décision Q25=A verrouillée : **cumul additif** (`sum(rule.discount_pct), clamp [0, 1]`). Drop intégral de toute branche `first-match` dans le code legacy.

## Solution

### Audit

```bash
grep -rn "first.*match\|break\b.*pricing_rule\|return rule\b" app/services/pricing/
```

### Code refacto

```python
# app/services/pricing/engine.py (déjà fait B3.S3.T2, mais audit complet)
def _apply_discounts(self, line: LineInput, applicable_rules: list[DiscountRule]) -> Decimal:
    # CUMUL ADDITIF (Q25=A)
    total = sum((r.discount_pct for r in applicable_rules), Decimal("0"))
    return max(Decimal("0"), min(Decimal("1"), total))
    # ❌ JAMAIS : for rule in applicable_rules: return rule.discount_pct
```

### Documentation

Ajout au commentaire de classe `PricingEngine` :
```python
class PricingEngine:
    """Calcul prix unique pour Devis/Reservation/Vente/Invoice.

    Stratégie cumul (Q25=A 2026-04-27) : ADDITIF.
    - sum(applicable_rules.discount_pct) clamp [0, 1]
    - Cohérent avec règles métier France ("addition des remises")
    - INTERDIT first-match : drift comptable garanti

    Cf. tools/check_no_multiplicative_discount.py + check_no_pricing_first_match.py
    """
```

### Script CI complémentaire

```python
# tools/check_no_pricing_first_match.py
"""Refuse `return rule.discount_pct` ou pattern first-match dans services/pricing."""
PATTERN = re.compile(r"for\s+\w+\s+in\s+\w+_rules:\s*\n\s*return")
violations = [...]
```

## DoD

- [ ] `grep` confirme aucun `first-match` dans pricing
- [ ] Script CI `check_no_pricing_first_match.py` actif
- [ ] Documentation classe `PricingEngine` explicite Q25=A
- [ ] Test : 2 rules matchant 10% + 5% → discount appliqué = 15% (cumul) pas 10% (first)

---

# Story B4.S4.T3 — Scope `pricing:read` vs `pricing:write` (F533)

## Contexte

**Friction** : F533 (cf. `architecture-cible.md §4.2.5`)
**Sévérité** : P0 — actuellement `/simulate` requiert `pricing:write` qui est trop large

### Description

Cible :
- `Scope.PRICING_READ = 'pricing:read'` pour `/pricing/simulate`, `GET /pricing/rules`
- `Scope.PRICING_WRITE = 'pricing:write'` pour `POST /pricing/rules`, `PATCH`, `DELETE`

## Solution

```python
# app/constants/security.py
class Scope(str, Enum):
    PRICING_READ = "pricing:read"  # F533 fix — déjà ajouté Phase 1
    PRICING_WRITE = "pricing:write"
    # ...

# app/api/v1/endpoints/pricing.py
@router.post("/simulate", dependencies=[Depends(require_scope(Scope.PRICING_READ))])
async def simulate(...):
    ...

@router.get("/rules", dependencies=[Depends(require_scope(Scope.PRICING_READ))])
async def list_rules(...):
    ...

@router.post("/rules", dependencies=[Depends(require_scope(Scope.PRICING_WRITE))])
async def create_rule(...):
    ...
```

### Test

```python
async def test_simulate_with_pricing_read_only(client_pricing_read):
    response = await client_pricing_read.post("/api/v1/pricing/simulate", json={...})
    assert response.status_code == 200

async def test_create_rule_refused_with_only_pricing_read(client_pricing_read):
    response = await client_pricing_read.post("/api/v1/pricing/rules", json={...})
    assert response.status_code == 403
```

## DoD

- [ ] Scope `PRICING_READ` séparé de `PRICING_WRITE`
- [ ] `/simulate` requiert `PRICING_READ`
- [ ] `/rules` POST/PATCH/DELETE requiert `PRICING_WRITE`
- [ ] Test : user `pricing:read` peut simulate mais pas créer de rule

---

# Story B4.S4.T4 — Drop `calculate_price` variants (F499)

## Contexte

**Friction** : F499 (vague 1)
**Sévérité** : P0 — `calculate_price`, `compute_price`, `_apply_pricing` éparpillés dans 5 fichiers

### Description

Audit + cleanup : tous les sites doivent appeler `PricingEngine.calculate()` ou `PricingEngine.quote()`.

## Solution

```bash
grep -rn "def calculate_price\|def compute_price\|def _apply_pricing" app/
```

Pour chaque fonction trouvée :
1. Vérifier qu'aucun caller ne l'utilise plus → drop
2. Sinon : refacto caller pour utiliser `PricingEngine`

### Test

```python
# Module bytecode importable mais aucune fonction calculate_price standalone
import app.services
assert not any(hasattr(m, "calculate_price") for m in vars(app.services).values())
```

## DoD

- [ ] `grep "def calculate_price\|def compute_price"` → 0 résultat hors `PricingEngine`
- [ ] Tous les callers passent par `PricingEngine.calculate()`
- [ ] Script CI bloque réintroduction

---

# Story B4.S4.T5 — `RFMService` extrait per-tenant (TR-30 / Q27=B)

## Contexte

**Friction** : TR-30, F443 (cf. `architecture-cible.md §4.2.10` + Q27=B verrouillée)
**Décision** : **Q27=B** — Seuils RFM **per-tenant** via `tenant_settings.rfm_thresholds JSONB` (pas constantes globales)
**Sévérité** : P0 — RFM dupliqué 3× (endpoints/customers.py:173, 251, 331) → drift segmentation = email envoyé à mauvaise cohorte. Sans Q27=B, Splendid B2B premium long cycle ↔ Marveline B2C court cycle → seuils figés impossibles.

### Description

Cible (cohérent Q27=B) :
1. `app/services/rfm.py:RFMService.compute_segment(tenant_settings, recency_days, frequency, monetary_cents) -> RFMSegment` — lit seuils depuis `tenant_settings.rfm_thresholds`
2. Schema Pydantic `RFMThresholds` valide la structure JSONB
3. Constants `app/constants/business.py:RFM_DEFAULTS` servent de **fallback** si `tenant_settings.rfm_thresholds IS NULL`
4. View matérialisée `customer_rfm_view` recalcule par tenant avec ses propres seuils
5. UI admin : page `Tenant Settings → Fidélité` permet d'ajuster
6. Test invariant CI : `/customers/rfm` et `/customers/{id}/rfm-profile` retournent même segment **avec mêmes seuils tenant**

## Solution

### Schema Pydantic + JSONB

```python
# app/schemas/rfm.py (NEW)
from pydantic import BaseModel, Field, ConfigDict

class RFMThresholds(BaseModel):
    """Q27=B — Seuils RFM per-tenant stockés dans tenant_settings.rfm_thresholds JSONB."""
    model_config = ConfigDict(extra="forbid")

    champion_recency_days: int = Field(ge=1, le=365)
    champion_frequency: int = Field(ge=1)
    champion_monetary_cents: int = Field(ge=0)
    loyal_recency_days: int = Field(ge=1, le=365)
    loyal_frequency: int = Field(ge=1)
    potential_recency_days: int = Field(ge=1, le=365)
    at_risk_recency_days: int = Field(ge=1, le=730)
    hibernating_recency_days: int = Field(ge=1, le=730)
    monetary_high_cents: int = Field(ge=0)


# app/constants/business.py — FALLBACK uniquement si tenant_settings.rfm_thresholds IS NULL
RFM_DEFAULTS = RFMThresholds(
    champion_recency_days=30,
    champion_frequency=10,
    champion_monetary_cents=1_000_000,  # 10k€
    loyal_recency_days=60,
    loyal_frequency=5,
    potential_recency_days=90,
    at_risk_recency_days=180,
    hibernating_recency_days=365,
    monetary_high_cents=500_000,  # 5k€
)
```

### Migration `tenant_settings.rfm_thresholds`

> **Note Vague 8** : la table `tenant_settings` **existe déjà** (cf. `app/models/tenant_settings.py`, migration `v3w4x5y6z7a8`). B4.S4 livre une migration ALTER pour AJOUTER la colonne `rfm_thresholds JSONB` à la table existante. NULL = fallback `RFM_DEFAULTS` runtime.

```python
# alembic/versions/f1a2b3c4d5f8a_tenant_settings_add_rfm_thresholds.py
def upgrade() -> None:
    op.add_column(
        "tenant_settings",
        sa.Column("rfm_thresholds", postgresql.JSONB, nullable=True),
    )

def downgrade() -> None:
    op.drop_column("tenant_settings", "rfm_thresholds")
```

### Service

```python
# app/services/rfm.py (NEW) — Q27=B per-tenant
from enum import Enum
from app.schemas.rfm import RFMThresholds
from app.constants.business import RFM_DEFAULTS

class RFMSegment(str, Enum):
    CHAMPION = "champion"
    LOYAL = "loyal"
    POTENTIAL = "potential"
    NEW = "new"
    AT_RISK = "at_risk"
    HIBERNATING = "hibernating"
    LOST = "lost"


class RFMService:
    @staticmethod
    def resolve_thresholds(tenant_settings: TenantSettings | None) -> RFMThresholds:
        """Q27=B — lit tenant_settings.rfm_thresholds, sinon fallback RFM_DEFAULTS."""
        if tenant_settings and tenant_settings.rfm_thresholds:
            return RFMThresholds.model_validate(tenant_settings.rfm_thresholds)
        return RFM_DEFAULTS

    @staticmethod
    def compute_segment(
        tenant_settings: TenantSettings | None,
        recency_days: int,
        frequency: int,
        monetary_cents: int,
    ) -> RFMSegment:
        t = RFMService.resolve_thresholds(tenant_settings)
        if (recency_days <= t.champion_recency_days
            and frequency >= t.champion_frequency
            and monetary_cents >= t.champion_monetary_cents):
            return RFMSegment.CHAMPION
        if recency_days <= t.loyal_recency_days and frequency >= t.loyal_frequency:
            return RFMSegment.LOYAL
        if recency_days <= t.potential_recency_days and frequency >= 2:
            return RFMSegment.POTENTIAL
        if recency_days <= 30 and frequency == 1:
            return RFMSegment.NEW
        if recency_days <= t.at_risk_recency_days:
            return RFMSegment.AT_RISK
        if recency_days <= t.hibernating_recency_days:
            return RFMSegment.HIBERNATING
        return RFMSegment.LOST
```

### Endpoint admin

```python
# app/api/v1/endpoints/tenant_settings.py
@router.put("/admin/tenant-settings/rfm-thresholds",
            dependencies=[Depends(require_scope(Scope.ADMIN_TENANT_SETTINGS))])
async def update_rfm_thresholds(
    payload: RFMThresholds,
    user: User = Depends(get_current_user),
):
    settings = await db.scalar(select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id))
    settings.rfm_thresholds = payload.model_dump()
    await db.commit()
    # Invalidation view matérialisée pour ce tenant
    await refresh_rfm_view_task.delay(user.tenant_id)
    return {"status": "updated"}
```

### Tests

```python
async def test_rfm_thresholds_per_tenant_splendid_vs_marveline(db, tenant_marveline, tenant_splendid):
    # Marveline B2C : Champion 10k€/an
    settings_m = await db.scalar(select(TenantSettings).where(TenantSettings.tenant_id == tenant_marveline.id))
    settings_m.rfm_thresholds = RFMThresholds(
        champion_recency_days=30, champion_frequency=10,
        champion_monetary_cents=1_000_000, ...
    ).model_dump()
    # Splendid B2B premium : Champion 50k€/an, cycle plus long
    settings_s = await db.scalar(select(TenantSettings).where(TenantSettings.tenant_id == tenant_splendid.id))
    settings_s.rfm_thresholds = RFMThresholds(
        champion_recency_days=180, champion_frequency=3,
        champion_monetary_cents=5_000_000, ...
    ).model_dump()
    await db.commit()

    # Customer 12k€ / 11 commandes / 25j → Champion Marveline
    seg_m = RFMService.compute_segment(settings_m, 25, 11, 1_200_000)
    assert seg_m == RFMSegment.CHAMPION
    # Même customer côté Splendid → pas Champion (seuil 50k€)
    seg_s = RFMService.compute_segment(settings_s, 25, 11, 1_200_000)
    assert seg_s != RFMSegment.CHAMPION

async def test_rfm_fallback_when_tenant_settings_null(db, tenant_no_settings):
    seg = RFMService.compute_segment(None, 25, 11, 1_200_000)
    assert seg == RFMSegment.CHAMPION  # RFM_DEFAULTS appliqué
```

### View matérialisée

```python
# alembic/versions/h1a2b3c4d5fd_customer_rfm_view.py
def upgrade() -> None:
    op.execute(text("""
        CREATE MATERIALIZED VIEW customer_rfm_view AS
        SELECT
            c.id AS customer_id,
            c.tenant_id,
            EXTRACT(DAY FROM (NOW() - MAX(i.emitted_at)))::int AS recency_days,
            COUNT(DISTINCT i.id) AS frequency,
            COALESCE(SUM(i.total_ttc_cents), 0) AS monetary_cents,
            NOW() AS computed_at
        FROM customers c
        LEFT JOIN invoices i ON i.customer_id = c.id AND i.status = 'paid'
        GROUP BY c.id, c.tenant_id
        WITH NO DATA;
    """))
    op.execute(text("CREATE UNIQUE INDEX uq_customer_rfm_view ON customer_rfm_view (customer_id)"))
    op.execute(text("REFRESH MATERIALIZED VIEW customer_rfm_view"))
```

### Celery task

```python
# app/workers/tasks/rfm_refresh.py
@shared_task(name="refresh_rfm_view")
def refresh_rfm_view_task():
    async def _run():
        async with engine.begin() as conn:
            await conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY customer_rfm_view"))
    asyncio.run(_run())

# Beat schedule daily 03:30
celery_app.conf.beat_schedule["refresh-rfm-daily"] = {
    "task": "refresh_rfm_view",
    "schedule": crontab(hour=3, minute=30),
}
```

### Test invariant

```python
async def test_rfm_consistent_across_endpoints(client, customer):
    rfm_list = await client.get("/api/v1/customers/rfm")
    rfm_profile = await client.get(f"/api/v1/customers/{customer.id}/rfm-profile")

    customer_in_list = next(c for c in rfm_list.json() if c["id"] == str(customer.id))
    assert customer_in_list["segment"] == rfm_profile.json()["segment"]
```

## DoD

- [ ] **Q27=B livré** : `tenant_settings.rfm_thresholds JSONB` migration + schema Pydantic `RFMThresholds`
- [ ] `RFMService.compute_segment(tenant_settings, ...)` lit seuils per-tenant
- [ ] `RFM_DEFAULTS` constant fallback uniquement si `tenant_settings.rfm_thresholds IS NULL`
- [ ] Endpoint admin `PUT /admin/tenant-settings/rfm-thresholds` opérationnel
- [ ] Vue matérialisée `customer_rfm_view` + UNIQUE INDEX
- [ ] Celery task `refresh_rfm_view` daily 03:30
- [ ] Test invariant cross-endpoint avec **mêmes seuils tenant**
- [ ] Test cross-tenant : Marveline B2C vs Splendid B2B premium → segments différents pour même customer
- [ ] Test fallback : tenant sans settings → RFM_DEFAULTS appliqué
- [ ] Suppression 3 implémentations dupliquées dans endpoints/customers.py

---

# Story B4.S4.T6 — Validators ISO country / SIRET / VAT VIES

## Contexte

**Pré-requis** : B1 + B2 ont posé les bases ; cette story livre les validators côté Customer/Tenant.

### Description

**Décision** : **Q26=A** — SIRET Luhn strict + override admin via header `X-Force-Validation-Override: siret` (loggué Outbox audit)

Cible :
1. `validate_iso_country(code: str)` — ISO 3166-1 alpha-2
2. `validate_siret(siret: str)` — Luhn algorithm 14 digits + **override admin** via header
3. `validate_vat_vies(vat_number: str)` — appel VIES API EU avec cache 24h

## Solution

```python
# app/core/validators.py (NEW)
ISO_COUNTRIES = frozenset({"FR", "DE", "ES", "IT", ...})  # 249 codes

def validate_iso_country(code: str) -> str:
    if code not in ISO_COUNTRIES:
        raise ValueError(f"Invalid ISO country code: {code}")
    return code

def validate_siret(siret: str) -> str:
    """Luhn algorithm pour SIRET 14 digits."""
    if not siret.isdigit() or len(siret) != 14:
        raise ValueError("SIRET must be 14 digits")
    digits = [int(d) for d in siret]
    total = sum(d if i % 2 == 0 else (d * 2 - 9 if d * 2 > 9 else d * 2)
                for i, d in enumerate(digits))
    if total % 10 != 0:
        raise ValueError("SIRET Luhn check failed")
    return siret

# app/services/vat_vies.py (NEW)
class ViesValidator:
    CACHE_TTL = 86400  # 24h

    async def validate(self, vat_number: str) -> bool:
        cache_key = f"vies:{vat_number}"
        cached = await redis.get(cache_key)
        if cached is not None:
            return cached == "true"

        # Appel VIES SOAP API
        country = vat_number[:2]
        number = vat_number[2:]
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://ec.europa.eu/taxation_customs/vies/services/checkVatService",
                content=_build_vies_soap(country, number),
                timeout=10.0,
            )
        is_valid = "<valid>true</valid>" in response.text
        await redis.set(cache_key, "true" if is_valid else "false", ex=self.CACHE_TTL)
        return is_valid
```

### Schemas

```python
# app/schemas/customer.py
from pydantic import field_validator

class CustomerCreate(BaseSchema):
    country: str
    siret: str | None = None
    vat_number: str | None = None

    @field_validator("country")
    def _country(cls, v): return validate_iso_country(v)

    @field_validator("siret")
    def _siret(cls, v): return validate_siret(v) if v else None
```

### Override admin SIRET (Q26=A)

```python
# app/api/v1/endpoints/customers.py (et suppliers, tenants)
@router.post("/customers")
async def create_customer(
    payload: CustomerCreate,
    request: Request,
    user: User = Depends(require_scope(Scope.CUSTOMERS_WRITE)),
):
    override_header = request.headers.get("X-Force-Validation-Override")
    if override_header == "siret" and user.has_scope(Scope.ADMIN_VALIDATION_OVERRIDE):
        # Skip Luhn — mais audit Outbox obligatoire
        await audit_service.log(
            action="VALIDATION_OVERRIDE",
            entity_type="Customer",
            entity_id="pending",
            description=f"SIRET Luhn skipped: {payload.siret}",
            account_id=user.id,
            tenant_id=user.tenant_id,
        )
        # Insert sans validate_siret
    else:
        try:
            validate_siret(payload.siret)
        except ValueError as e:
            raise HTTPException(422, f"SIRET invalide: {e}")
    # ... création
```

```python
# app/constants/security.py
class Scope(str, Enum):
    # ...
    ADMIN_VALIDATION_OVERRIDE = "admin:validation_override"  # Q26=A
```

### Tests

```python
def test_siret_luhn_valid():
    assert validate_siret("12345678900014")  # SIRET test valide

def test_siret_luhn_invalid():
    with pytest.raises(ValueError, match="Luhn"):
        validate_siret("12345678901234")

async def test_siret_override_admin_creates_audit_log(client_admin, db):
    """Q26=A — admin avec scope override + header → bypass Luhn + audit."""
    response = await client_admin.post(
        "/api/v1/customers",
        json={"siret": "00000000000000", "first_name": "Test"},
        headers={"X-Force-Validation-Override": "siret"},
    )
    assert response.status_code == 201
    log = await db.scalar(
        select(AuditLog).where(AuditLog.action == "VALIDATION_OVERRIDE")
    )
    assert log is not None

async def test_siret_override_refused_without_scope(client_normal):
    """User sans `admin:validation_override` → header ignoré, Luhn enforced."""
    response = await client_normal.post(
        "/api/v1/customers",
        json={"siret": "00000000000000", "first_name": "Test"},
        headers={"X-Force-Validation-Override": "siret"},
    )
    assert response.status_code == 422  # Luhn fails

async def test_vies_cached_after_first_call(monkeypatch, redis):
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=MagicMock(text="<valid>true</valid>")))
    await vies.validate("FR12345678901")
    # 2e appel : pas de re-call HTTP
    httpx.AsyncClient.post.reset_mock()
    await vies.validate("FR12345678901")
    httpx.AsyncClient.post.assert_not_called()
```

## DoD

- [ ] `validate_iso_country`, `validate_siret`, `ViesValidator` livrés
- [ ] Schemas Pydantic Customer/Tenant utilisent validators
- [ ] **Q26=A override admin** : header `X-Force-Validation-Override: siret` + scope `admin:validation_override` + audit Outbox
- [ ] Cache Redis 24h sur VIES
- [ ] Tests unitaires Luhn + ISO + VIES cache + override admin (audit créé) + override refusé sans scope

---

# Story B4.S4.T7 — Cache Redis 5 min sur `_get_active_rules`

## Contexte

Performance : `_get_active_rules(tenant_id)` exécuté à chaque pricing.calculate → 200 calls/min sur prod = 200 SELECT/min sur `pricing_rules`.

## Solution

```python
# app/services/pricing/engine.py
class PricingEngine:
    CACHE_TTL = 300  # 5 min

    async def _get_active_rules(self, tenant_id: int, event_date: date) -> list[DiscountRule]:
        cache_key = f"pricing_rules:{tenant_id}:{event_date.isoformat()}"
        cached = await self.redis.get(cache_key)
        if cached:
            return [DiscountRule.parse_raw(r) for r in json.loads(cached)]

        rules = await self.repo.fetch_active_rules(tenant_id, event_date)
        await self.redis.set(
            cache_key,
            json.dumps([r.json() for r in rules]),
            ex=self.CACHE_TTL,
        )
        return rules

    async def invalidate_cache(self, tenant_id: int):
        """Appelé sur création/update/delete pricing_rule."""
        async for key in self.redis.scan_iter(f"pricing_rules:{tenant_id}:*"):
            await self.redis.delete(key)
```

## DoD

- [ ] Cache Redis 5 min implémenté
- [ ] Invalidation explicite sur mutation rule
- [ ] Test : 2 calls successifs → 1 SELECT seulement
- [ ] Test : update rule → cache invalidé

---

## Critères de succès Sprint B4.S4

- [ ] **TR-21 cont.** : `PricingEngine.calculate()` méthode unique simulate=apply
- [ ] **F532 résolu** : cumul additif documenté + script CI
- [ ] **F533 résolu** : scope `pricing:read` séparé
- [ ] **F499 résolu** : `calculate_price` variants droppés
- [ ] **TR-30 / Q27=B résolu** : `RFMService` per-tenant via `tenant_settings.rfm_thresholds JSONB` + fallback `RFM_DEFAULTS` + view matérialisée + Celery refresh
- [ ] Validators ISO/SIRET/VIES livrés avec cache
- [ ] Cache Redis 5 min PricingEngine
- [ ] Test invariant : simulate == apply au cent ; RFM consistent cross-endpoint

---

**Fin du document — 14-sprint-B4.S4.md**
