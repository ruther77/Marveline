# Sprint B5.S5 — categorie_id FK + drop _FINAL_CATEGORIES + drop _TENANT_RESTAURANT hardcoded

> **STATUT** : ⏳ À démarrer après B5.S4
> **DURÉE MAX** : 1 semaine
> **OWNER** : Dev3
> **BLOQUE** : B5.S6 (TransferRequest workflow)
> **DÉPEND DE** : B5.S2 (tenant_id ETL), B5.S4 (Celery tenant-aware)
> **OBJECTIF** : Migrer `categorie_code String` → `categorie_id FK NOT NULL` sur 3 catalogues ETL (TR-53, F956). Drop `_FINAL_CATEGORIES` frozenset hardcoded ~91 codes (TR-60, F987). Drop `_TENANT_RESTAURANT = 3` hardcoded (Q34=A). Fixer `lookup_correction_history` Layer 0 placeholder (TR-59, F976).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B5.S5.T1** | TR-53 / F956 — `categorie_code → categorie_id FK NOT NULL` migration backfill 3 catalogues | P0 | 2 j | T2 |
| **B5.S5.T2** | TR-60 / F987 — Drop `_FINAL_CATEGORIES` frozenset hardcoded + DB-driven lookup | P0 | 1 j | aucun |
| **B5.S5.T3** | TR-59 / F976 — `lookup_correction_history` Layer 0 fonctionnel + drop dup inline | P0 | 1 j | aucun |
| **B5.S5.T4** | Q34=A / F944/F945 — Drop `_TENANT_RESTAURANT = 3` hardcoded sur services restaurant | P1 | 1 j | aucun |
| **B5.S5.T5** | TR-25 — `Mapped[datetime]` typing strict (drop `Mapped[str]` couplé `DateTime`) — F648/F649/F771 | P1 | 0.5 j | aucun |

**Total effort** : 5.5 jours-homme.

---

# Story B5.S5.T1 — `categorie_code → categorie_id FK NOT NULL` (TR-53)

## Contexte

**Friction** : TR-53, F956 (cf. `architecture-cible.md §5.1`)
**Sévérité** : P0 — migration M00 rename → produits orphelins silencieux (`categorie_code='legumes_anciens'` rename → `categorie_code='legumes-anciens'` casse cross-tables)
**Code source** : `app/models/catalogue.py`, `app/models/categorie_produit.py`, `app/models/etl_correction_history.py`

### Description

Cible : 3 catalogues ETL (`CatalogueProduit`, `CategorieProduit`, `EtlCorrectionHistory`) ont actuellement `categorie_code: str` non FK. Migrer vers `categorie_id INT FK CategorieProduit(id) NOT NULL`.

## Solution

### Migration backward-compatible 4 étapes

```python
# alembic/versions/j1a2b3c4d600_categorie_fk_step1_add_nullable.py
def upgrade() -> None:
    op.add_column("catalogue_produit", sa.Column("categorie_id", sa.Integer, nullable=True))
    op.create_foreign_key(
        "fk_catalogue_produit_categorie_id", "catalogue_produit", "categorie_produit",
        ["categorie_id"], ["id"], ondelete="RESTRICT",
    )

# alembic/versions/j1a2b3c4d601_categorie_fk_step2_backfill.py
def upgrade() -> None:
    op.execute(text("""
        UPDATE catalogue_produit cp
        SET categorie_id = c.id
        FROM categorie_produit c
        WHERE c.code = cp.categorie_code
          AND c.tenant_id = cp.tenant_id
          AND cp.categorie_id IS NULL
    """))

# alembic/versions/j1a2b3c4d602_categorie_fk_step3_not_null.py
def upgrade() -> None:
    orphans = op.get_bind().scalar(text("SELECT COUNT(*) FROM catalogue_produit WHERE categorie_id IS NULL"))
    if orphans > 0:
        # Audit : créer category 'AUTRE' per-tenant pour orphelins
        op.execute(text("""
            INSERT INTO categorie_produit (tenant_id, code, libelle, is_active)
            SELECT DISTINCT tenant_id, 'autre', 'Autre (orphelin)', true
            FROM catalogue_produit WHERE categorie_id IS NULL
            ON CONFLICT (tenant_id, code) DO NOTHING
        """))
        op.execute(text("""
            UPDATE catalogue_produit cp SET categorie_id = c.id
            FROM categorie_produit c WHERE c.tenant_id = cp.tenant_id AND c.code = 'autre' AND cp.categorie_id IS NULL
        """))
    op.alter_column("catalogue_produit", "categorie_id", nullable=False)

# alembic/versions/j1a2b3c4d603_categorie_fk_step4_drop_legacy.py
def upgrade() -> None:
    op.drop_column("catalogue_produit", "categorie_code")
    # Idem etl_correction_history.categorie_code
```

### Modèles

```python
# app/models/catalogue.py
class CatalogueProduit(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    categorie_id: Mapped[int] = mapped_column(
        ForeignKey("categorie_produit.id", ondelete="RESTRICT"),
        nullable=False,
    )
    categorie: Mapped["CategorieProduit"] = relationship("CategorieProduit")
```

### Test

```python
async def test_catalogue_produit_categorie_id_required(db, tenant):
    with pytest.raises(IntegrityError, match="categorie_id"):
        cp = CatalogueProduit(tenant_id=tenant.id, ean="123", libelle="X")
        db.add(cp); await db.commit()

async def test_categorie_rename_no_orphan(db, tenant, category_legumes):
    cp = CatalogueProduit(tenant_id=tenant.id, ean="123", libelle="Tomate", categorie_id=category_legumes.id)
    db.add(cp); await db.commit()
    
    # Rename category code (FK ne casse pas)
    category_legumes.code = "legumes-frais"
    await db.commit()
    
    await db.refresh(cp)
    assert cp.categorie.code == "legumes-frais"  # FK suit le rename
```

## DoD

- [ ] Migration 4 étapes appliquée 3 tables
- [ ] FK `RESTRICT` (pas SET NULL) pour intégrité
- [ ] Drop colonnes `categorie_code` legacy
- [ ] Test : INSERT sans categorie_id → IntegrityError
- [ ] Test : rename category → produits suivent

---

# Story B5.S5.T2 — Drop `_FINAL_CATEGORIES` frozenset (TR-60)

## Contexte

**Friction** : TR-60, F987
**Sévérité** : P0 — `_FINAL_CATEGORIES = frozenset({...91 codes...})` Python ↔ table `categorie_produit` → drift garanti
**Code source** : `app/services/etl/parsers/_shared/categorie_classifier.py`

### Description

Cible : drop frozenset hardcoded, lookup DB-driven sur `categorie_produit` per-tenant (cohérent B5.S2.T1 tenant_id NOT NULL).

## Solution

```python
# app/services/etl/parsers/_shared/categorie_classifier.py — avant
_FINAL_CATEGORIES = frozenset({"legumes", "fruits", "viandes", ...})  # 91 codes

def is_valid_categorie_code(code: str) -> bool:
    return code in _FINAL_CATEGORIES

# après
class CategorieClassifier:
    def __init__(self, db: AsyncSession, tenant_id: int):
        self.db = db
        self.tenant_id = tenant_id
        self._cache: set[str] | None = None

    async def _load_codes(self) -> set[str]:
        if self._cache is None:
            codes = await self.db.scalars(
                select(CategorieProduit.code).where(CategorieProduit.tenant_id == self.tenant_id)
            )
            self._cache = {c for c in codes.all()}
        return self._cache

    async def is_valid(self, code: str) -> bool:
        codes = await self._load_codes()
        return code in codes
```

### Test

```python
async def test_classifier_uses_db_not_frozenset(db, tenant):
    # Ajouter une catégorie nouvelle en DB
    new_cat = CategorieProduit(tenant_id=tenant.id, code="surgeles_premium", libelle="Surgelés Premium")
    db.add(new_cat); await db.commit()
    
    classifier = CategorieClassifier(db, tenant.id)
    assert await classifier.is_valid("surgeles_premium")  # passe car DB-driven

# AVANT le fix : aurait retourné False car pas dans frozenset
```

## DoD

- [ ] Drop frozenset hardcoded
- [ ] Classifier instancié per ETL call (cohérent IdfCorpus per-call B5.S4.T3)
- [ ] Cache local au classifier (pas global)
- [ ] Test : nouvelle category DB → classifier la connaît

---

# Story B5.S5.T3 — `lookup_correction_history` Layer 0 fonctionnel (TR-59)

## Contexte

**Friction** : TR-59, F976
**Sévérité** : P0 — `lookup_correction_history` Layer 0 retourne toujours `None` (placeholder) ; vrai lookup dupliqué inline
**Code source** : `app/services/etl/correction_history_resolver.py`

### Description

Cible :
1. `LookupCorrectionHistoryService.lookup(original_text, tenant_id) -> CorrectionResult | None` — retourne la meilleure correction historique
2. Drop le code dupliqué inline dans le parser
3. Apprentissage automatique : si correction utilisée 3+ fois → boost confidence

## Solution

```python
# app/services/etl/correction_history_resolver.py
@dataclass(frozen=True)
class CorrectionResult:
    corrected_categorie_code: str
    confidence: float
    history_count: int


class LookupCorrectionHistoryService:
    async def lookup(self, original_text: str, tenant_id: int) -> CorrectionResult | None:
        normalized = _normalize(original_text)
        rows = await self.db.execute(
            select(
                EtlCorrectionHistory.corrected_categorie_code,
                func.count(EtlCorrectionHistory.id).label("count"),
            )
            .where(
                EtlCorrectionHistory.tenant_id == tenant_id,
                EtlCorrectionHistory.original_text_normalized == normalized,
            )
            .group_by(EtlCorrectionHistory.corrected_categorie_code)
            .order_by(func.count(EtlCorrectionHistory.id).desc())
        )
        results = rows.all()
        if not results:
            return None
        top = results[0]
        confidence = min(1.0, top.count / 3)  # 3+ → 100%
        return CorrectionResult(
            corrected_categorie_code=top.corrected_categorie_code,
            confidence=confidence,
            history_count=top.count,
        )

    async def record(self, original_text: str, corrected_categorie_code: str, tenant_id: int):
        normalized = _normalize(original_text)
        self.db.add(EtlCorrectionHistory(
            tenant_id=tenant_id,
            original_text=original_text,
            original_text_normalized=normalized,
            corrected_categorie_code=corrected_categorie_code,
        ))
```

### Migration

```python
def upgrade() -> None:
    op.add_column("etl_correction_history", sa.Column("original_text_normalized", sa.String(512), nullable=True))
    op.create_index(
        "ix_etl_correction_history_lookup",
        "etl_correction_history",
        ["tenant_id", "original_text_normalized"],
    )
    # Backfill normalized
    op.execute(text("""
        UPDATE etl_correction_history
        SET original_text_normalized = LOWER(TRIM(original_text))
        WHERE original_text_normalized IS NULL
    """))
    op.alter_column("etl_correction_history", "original_text_normalized", nullable=False)
```

### Test

```python
async def test_lookup_returns_top_correction(db, tenant):
    # Seed 3 corrections "POMMES GLUNEX 6 1KG" → "fruits"
    for _ in range(3):
        await service.record("POMMES GLUNEX 6 1KG", "fruits", tenant.id)
    # Et 1 correction → "legumes" (typo)
    await service.record("POMMES GLUNEX 6 1KG", "legumes", tenant.id)
    
    result = await service.lookup("POMMES GLUNEX 6 1KG", tenant.id)
    assert result.corrected_categorie_code == "fruits"
    assert result.confidence >= 0.99
    assert result.history_count == 3
```

## DoD

- [ ] Layer 0 retourne meilleure correction historique (pas None)
- [ ] Confidence basée sur count
- [ ] Drop dup inline dans parser
- [ ] Migration `original_text_normalized` + index lookup
- [ ] Test : 3 corrections → lookup confidence 1.0

---

# Story B5.S5.T4 — Drop `_TENANT_RESTAURANT = 3` hardcoded (Q34=A)

## Contexte

**Friction** : TR-55, F944, F945
**Sévérité** : P1 — service restaurant singleton tenant unique, multi-restaurant impossible
**Code source** : `app/services/restaurant/dashboard.py`, `app/services/restaurant/reception_etl.py`

### Description

Cible :
- Drop `_TENANT_RESTAURANT = 3` constant
- Tous les services restaurant acceptent `tenant_id` paramètre explicite
- Drop assertions `assert tenant_id == 3` et autres patterns mono-restaurant

## Solution

```python
# app/services/restaurant/dashboard.py — avant
_TENANT_RESTAURANT = 3  # hardcoded

class DashboardService:
    async def _load_uplift_pct(self):
        return await db.scalar(select(...).where(Tenant.id == _TENANT_RESTAURANT))  # ❌

# après
class DashboardService:
    async def _load_uplift_pct(self, tenant_id: int):
        return await db.scalar(select(...).where(Tenant.id == tenant_id))


# app/services/restaurant/reception_etl.py — avant
def receive_etl(tenant_id: int, ...):
    assert tenant_id == 3, "Restaurant only"  # ❌

# après
def receive_etl(tenant_id: int, ...):
    # check tenant.vertical = 'restaurant' instead
    tenant = await db.get(Tenant, tenant_id)
    if tenant.vertical != "restaurant":
        raise InvalidTenantVertical(f"receive_etl requires vertical=restaurant, got {tenant.vertical}")
```

### Test

```python
async def test_dashboard_works_with_arbitrary_tenant(db, tenant_restaurant_5):
    """Tenant restaurant ID = 5 (pas 3) → dashboard fonctionne."""
    service = DashboardService(db)
    uplift = await service._load_uplift_pct(tenant_restaurant_5.id)
    assert uplift is not None  # pas d'erreur
```

## DoD

- [ ] `grep "_TENANT_RESTAURANT"` → 0 résultat
- [ ] Tous services restaurant `tenant_id` arg explicite
- [ ] Validation `tenant.vertical == "restaurant"` au lieu d'assert hardcoded
- [ ] Test : tenant restaurant ID arbitraire → service fonctionne

---

# Story B5.S5.T5 — `Mapped[datetime]` typing strict (TR-25)

## Contexte

**Friction** : TR-25, F648, F649, F771
**Sévérité** : P1 — `Mapped[str]` couplé `DateTime(timezone=True)` (annotation typing fausse) → mypy/IDE crash sur `scheduled_date.date()`

### Description

Cible : audit + fix typing sur 3 modules récurrents.

## Solution

```bash
grep -rn "Mapped\[str\].*DateTime\|Mapped\[Optional\[str\]\].*DateTime" app/models/
```

Pour chaque occurrence :
```python
# avant
scheduled_date: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=True)  # ❌ typing faux

# après
scheduled_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # ✅
```

### Script CI

```python
# tools/check_mapped_datetime.py
"""Refuse Mapped[str] couplé DateTime."""
PATTERN = re.compile(r"Mapped\[(Optional\[)?str(\])?\].*DateTime\(")
```

## DoD

- [ ] 3+ modules fixés
- [ ] Script CI actif
- [ ] mypy passe vert sur `app/models/`

---

## Critères de succès Sprint B5.S5

- [ ] **TR-53 / F956 résolu** : `categorie_id FK NOT NULL` 3 tables ETL
- [ ] **TR-60 / F987 résolu** : drop `_FINAL_CATEGORIES`, classifier DB-driven per-call
- [ ] **TR-59 / F976 résolu** : `lookup_correction_history` Layer 0 fonctionnel
- [ ] **Q34=A résolu** : drop `_TENANT_RESTAURANT=3`, multi-restaurant ready
- [ ] **TR-25 résolu** : `Mapped[datetime]` typing correct
- [ ] Test : nouveau tenant restaurant ID arbitraire fonctionne
- [ ] Test : rename category code → produits suivent (FK)

---

**Fin du document — 15-sprint-B5.S5.md**
