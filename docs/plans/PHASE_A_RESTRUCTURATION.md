# Plan de Restructuration — Phase A
# Version: 1.0
# Statut: Prêt à implémenter
# Périmètre: M00 (categories_produit) → M04 (etl_conflicts) + parseur METRO + Celery ETL
# Prérequis: V2_ARCHITECTURE_PLAN.md v1.3 validé

---

## §1 — Contexte et contraintes

### Ce que Phase A implémente (5 migrations)

| Migration | Table(s) créées | Nature |
|-----------|-----------------|--------|
| M00 | `categories_produit` + seed 50 catégories | Référentiel partagé, aucun tenant_id |
| M01 | `catalogue_produits` | Référentiel ETL EAN-normalisé, aucun tenant_id |
| M02 | `fournisseurs_alim` | Référentiel partagé, aucun tenant_id |
| M03 | `etl_imports` | Journal des imports ETL |
| M04 | `etl_conflicts` | File de conflits à résoudre |

### Contraintes non négociables

- Les modèles, repositories, services V2 vont dans des **sous-répertoires subdomain** (ADR-04).
- L'existant (location, auth, RBAC) **ne bouge pas** — aucune migration destructive.
- `app/models/__init__.py` est mis à jour **dans la même session** que la création de chaque modèle (CLAUDE.md §A.2).
- `asyncpg` est déjà dans `pyproject.toml` — `AsyncBaseRepository` est disponible dans `repositories/base.py`.
- Aucun secret en code, aucun tenant_id sur les tables référentiel (ADR-01, ADR-02).

---

## §2 — Arborescence Phase A (delta uniquement)

Seuls les fichiers **nouveaux ou modifiés** sont listés. Tout le reste reste intact.

```
FUTUR PROJ/
│
├── pyproject.toml                              ← MODIFIER : ajouter rapidfuzz
│
├── app/
│   ├── models/
│   │   ├── __init__.py                         ← MODIFIER : importer les 5 nouveaux modèles
│   │   └── catalogue/                          ← CRÉER répertoire
│   │       ├── __init__.py                     ← CRÉER
│   │       ├── categories_produit.py           ← CRÉER (M00)
│   │       ├── catalogue_produits.py           ← CRÉER (M01)
│   │       ├── fournisseur_alim.py             ← CRÉER (M02)
│   │       ├── etl_import.py                   ← CRÉER (M03)
│   │       └── etl_conflict.py                 ← CRÉER (M04)
│   │
│   ├── repositories/
│   │   ├── __init__.py                         ← MODIFIER : exporter nouveaux repos
│   │   └── catalogue/                          ← CRÉER répertoire
│   │       ├── __init__.py                     ← CRÉER
│   │       ├── categories_produit_repo.py      ← CRÉER
│   │       ├── catalogue_produits_repo.py      ← CRÉER
│   │       ├── fournisseur_alim_repo.py        ← CRÉER
│   │       ├── etl_import_repo.py              ← CRÉER
│   │       └── etl_conflict_repo.py            ← CRÉER
│   │
│   ├── schemas/
│   │   └── catalogue/                          ← CRÉER répertoire
│   │       ├── __init__.py                     ← CRÉER
│   │       ├── categories_produit_schema.py    ← CRÉER
│   │       ├── catalogue_produits_schema.py    ← CRÉER
│   │       ├── fournisseur_alim_schema.py      ← CRÉER
│   │       ├── etl_import_schema.py            ← CRÉER
│   │       └── etl_conflict_schema.py          ← CRÉER
│   │
│   ├── services/
│   │   └── catalogue/                          ← CRÉER répertoire
│   │       ├── __init__.py                     ← CRÉER
│   │       ├── deduplication_service.py        ← CRÉER (Jaro-Winkler via rapidfuzz)
│   │       └── etl_pipeline_service.py         ← CRÉER (orchestration import)
│   │
│   ├── constants/
│   │   ├── approvisionnement.py                ← CRÉER (constantes Phase A)
│   │   └── epicerie.py                         ← CRÉER (constantes Phase B — placeholder)
│   │
│   └── tasks/
│       ├── celery_app.py                       ← MODIFIER : queue etl + autodiscover
│       └── etl_tasks.py                        ← CRÉER (tâches Celery ETL)
│
├── scripts/
│   └── etl/                                    ← CRÉER répertoire
│       ├── __init__.py                         ← CRÉER
│       ├── parsers/                            ← CRÉER répertoire
│       │   ├── __init__.py                     ← CRÉER
│       │   └── metro.py                        ← CRÉER (parseur CSV METRO)
│       └── import_pipeline.py                  ← CRÉER (script CLI import)
│
├── alembic/
│   ├── data_migrations/                        ← CRÉER répertoire
│   │   ├── __init__.py                         ← CRÉER
│   │   └── seed_categories_produit.py          ← CRÉER (50 catégories M00)
│   └── versions/
│       ├── v2a0_m00_categories_produit.py      ← CRÉER migration M00
│       ├── v2b1_m01_catalogue_produits.py      ← CRÉER migration M01
│       ├── v2c2_m02_fournisseurs_alim.py       ← CRÉER migration M02
│       ├── v2d3_m03_etl_imports.py             ← CRÉER migration M03
│       └── v2e4_m04_etl_conflicts.py           ← CRÉER migration M04
│
└── tests/
    └── unit/
        └── catalogue/                          ← CRÉER répertoire
            ├── __init__.py                     ← CRÉER
            ├── test_deduplication.py           ← CRÉER (Jaro-Winkler + normalisation)
            ├── test_metro_parser.py            ← CRÉER (parseur CSV METRO)
            └── test_etl_pipeline.py            ← CRÉER (pipeline + conflits)
```

---

## §3 — Modifications de fichiers existants

### 3.1 `pyproject.toml` — Ajouter rapidfuzz

```toml
# Dans [tool.poetry.dependencies], après argon2-cffi :
rapidfuzz = "^3.10.0"    # Jaro-Winkler deduplication ETL (ADR-06)
```

### 3.2 `app/tasks/celery_app.py` — Queue ETL

**Modification 1** — `task_routes` : ajouter la queue `etl`

```python
celery_app.conf.task_routes = {
    "app.tasks.reservations.*": {"queue": "reservations"},
    "app.tasks.invoicing.*":    {"queue": "invoicing"},
    "app.tasks.notifications.*":{"queue": "notifications"},
    "app.tasks.monitoring.*":   {"queue": "default"},
    "app.tasks.etl_tasks.*":    {"queue": "etl"},   # ← AJOUTER
}
```

**Modification 2** — `autodiscover_tasks` : ajouter `etl_tasks`

```python
celery_app.autodiscover_tasks([
    "app.tasks.invoicing",
    "app.tasks.notifications",
    "app.tasks.monitoring",
    "app.tasks.access_review",
    "app.tasks.etl_tasks",   # ← AJOUTER
])
```

**Modification 3** — `beat_schedule` : ajouter tâche ETL hebdomadaire

```python
"etl-catalogue-sync-weekly": {
    "task": "app.tasks.etl_tasks.sync_catalogue_from_metro",
    "schedule": crontab(day_of_week=1, hour=3, minute=0),
    # Lundi 03:00 UTC — hors pics d'activité
},
```

### 3.3 `app/models/__init__.py` — Ajouter les 5 modèles V2

Ajouter en bas des imports existants (après `PasswordResetToken`) :

```python
# ── V2 : Domaines alimentaires ──────────────────────────────────────────────
# Catalogue partagé (sans tenant_id — ADR-01, ADR-02)
from app.models.catalogue.categories_produit import CategorieProduit
from app.models.catalogue.catalogue_produits import CatalogueProduit
from app.models.catalogue.fournisseur_alim import FournisseurAlim
from app.models.catalogue.etl_import import EtlImport
from app.models.catalogue.etl_conflict import EtlConflict
```

Et dans `__all__` :

```python
# V2 — Catalogue partagé
"CategorieProduit",
"CatalogueProduit",
"FournisseurAlim",
"EtlImport",
"EtlConflict",
```

---

## §4 — Spécification des modèles Phase A

### 4.1 `CategorieProduit` (M00)

```python
# app/models/catalogue/categories_produit.py
class CategorieProduit(Base, TimestampMixin):
    __tablename__ = "categories_produit"

    id:          Mapped[int]  — PK autoincrement
    code:        Mapped[str]  — VARCHAR(20) UNIQUE NOT NULL  ex: "frais_viande"
    libelle:     Mapped[str]  — VARCHAR(100) NOT NULL         ex: "Viandes fraîches"
    parent_code: Mapped[Optional[str]]  — VARCHAR(20) FK(categories_produit.code) nullable
    # Pas de tenant_id (ADR-01 — référentiel partagé)
    # Index : UNIQUE sur code (déjà via constraint)
```

Seed : 50 catégories définies dans `alembic/data_migrations/seed_categories_produit.py`.
Le seed est appelé dans la migration M00 via `op.execute()` ou script séparé.

### 4.2 `CatalogueProduit` (M01)

```python
# app/models/catalogue/catalogue_produits.py
class CatalogueProduit(Base, TimestampMixin):
    __tablename__ = "catalogue_produits"

    id:               Mapped[int]   — PK autoincrement
    ean:              Mapped[Optional[str]]  — VARCHAR(20) UNIQUE nullable (produits maison = NULL)
    designation_norm: Mapped[str]   — VARCHAR(200) NOT NULL (désignation normalisée)
    designation_raw:  Mapped[str]   — VARCHAR(200) NOT NULL (désignation METRO originale)
    categorie_code:   Mapped[str]   — VARCHAR(20) FK(categories_produit.code) NOT NULL
    unite_achat:      Mapped[str]   — VARCHAR(10) NOT NULL  ex: "KG", "L", "PIECE", "CARTON"
    conditionnement:  Mapped[Optional[Decimal]]  — NUMERIC(8,3) nullable (quantité par unité)
    fournisseur_id:   Mapped[Optional[int]]  — FK(fournisseurs_alim.id) nullable
    is_active:        Mapped[bool]  — BOOLEAN NOT NULL DEFAULT true
    # Index : (categorie_code), (fournisseur_id), (designation_norm) TRGM si PostgreSQL
    # Pas de tenant_id (ADR-01)
```

### 4.3 `FournisseurAlim` (M02)

```python
# app/models/catalogue/fournisseur_alim.py
class FournisseurAlim(Base, TimestampMixin):
    __tablename__ = "fournisseurs_alim"

    id:                Mapped[int]  — PK autoincrement
    code:              Mapped[str]  — VARCHAR(20) UNIQUE NOT NULL  ex: "METRO", "TAIYAT"
    nom:               Mapped[str]  — VARCHAR(100) NOT NULL
    type_import:       Mapped[str]  — VARCHAR(20) NOT NULL CHECK('csv_metro','csv_taiyat','manuel')
    format_fichier:    Mapped[str]  — VARCHAR(10) NOT NULL  ex: "CSV", "XLSX"
    encodage_defaut:   Mapped[str]  — VARCHAR(20) NOT NULL DEFAULT 'utf-8'
    separateur_csv:    Mapped[Optional[str]]  — VARCHAR(5) nullable  ex: ";"
    is_active:         Mapped[bool] — BOOLEAN NOT NULL DEFAULT true
    # Pas de tenant_id (ADR-02)
    # Index : UNIQUE sur code (déjà via constraint)
```

### 4.4 `EtlImport` (M03)

```python
# app/models/catalogue/etl_import.py
class EtlImport(Base, TimestampMixin):
    __tablename__ = "etl_imports"

    id:               Mapped[int]  — PK autoincrement
    fournisseur_id:   Mapped[int]  — FK(fournisseurs_alim.id) NOT NULL
    fichier_nom:      Mapped[str]  — VARCHAR(255) NOT NULL
    fichier_hash:     Mapped[str]  — VARCHAR(64) NOT NULL  (SHA-256 du fichier)
    statut:           Mapped[str]  — VARCHAR(20) NOT NULL CHECK('pending','running','done','failed')
    lignes_total:     Mapped[Optional[int]]  — INTEGER nullable
    lignes_importees: Mapped[Optional[int]]  — INTEGER nullable
    lignes_conflits:  Mapped[Optional[int]]  — INTEGER nullable
    erreur_message:   Mapped[Optional[str]]  — TEXT nullable
    started_at:       Mapped[Optional[datetime]]  — TIMESTAMPTZ nullable
    finished_at:      Mapped[Optional[datetime]]  — TIMESTAMPTZ nullable
    # Index : (fournisseur_id), (statut), (fichier_hash) pour éviter double-import
```

### 4.5 `EtlConflict` (M04)

```python
# app/models/catalogue/etl_conflict.py
class EtlConflict(Base, TimestampMixin):
    __tablename__ = "etl_conflicts"

    id:                  Mapped[int]  — PK autoincrement
    import_id:           Mapped[int]  — FK(etl_imports.id) NOT NULL
    ean:                 Mapped[Optional[str]]  — VARCHAR(20) nullable
    designation_source:  Mapped[str]  — VARCHAR(200) NOT NULL
    designation_existante: Mapped[Optional[str]]  — VARCHAR(200) nullable
    score_similarite:    Mapped[Optional[Decimal]]  — NUMERIC(5,4) nullable  (0.0–1.0)
    type_conflit:        Mapped[str]  — VARCHAR(30) NOT NULL CHECK('ean_collision','designation_proche','categorie_inconnue')
    statut_resolution:   Mapped[str]  — VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK('pending','resolved_merge','resolved_create','resolved_ignore')
    resolved_by:         Mapped[Optional[int]]  — FK(accounts.id) nullable  (admin qui résout)
    resolved_at:         Mapped[Optional[datetime]]  — TIMESTAMPTZ nullable
    # Index : (import_id), (statut_resolution), (ean)
```

---

## §5 — Spécification des repositories Phase A

Tous héritent de `AsyncBaseRepository(Generic[T])` de `app/repositories/base.py`.

Les modèles sans `tenant_id` (CategorieProduit, CatalogueProduit, FournisseurAlim) utilisent
`BaseRepository` avec une surcharge : **pas de filtre tenant** sur les `select`.

```
CategoriesProduitRepository  → AsyncBaseRepository[CategorieProduit]
    + get_by_code(code: str) → Optional[CategorieProduit]
    + list_by_parent(parent_code: str) → list[CategorieProduit]
    + get_tree() → list[CategorieProduit]  (toutes catégories, triées)

CatalogueProduitRepository   → AsyncBaseRepository[CatalogueProduit]
    + get_by_ean(ean: str) → Optional[CatalogueProduit]
    + search_by_designation(q: str, limit: int) → list[CatalogueProduit]
    + list_by_categorie(categorie_code: str) → list[CatalogueProduit]
    + list_by_fournisseur(fournisseur_id: int) → list[CatalogueProduit]

FournisseurAlimRepository    → AsyncBaseRepository[FournisseurAlim]
    + get_by_code(code: str) → Optional[FournisseurAlim]
    + list_actifs() → list[FournisseurAlim]

EtlImportRepository          → AsyncBaseRepository[EtlImport]
    + get_by_hash(fichier_hash: str) → Optional[EtlImport]
    + list_by_fournisseur(fournisseur_id: int) → list[EtlImport]
    + list_en_cours() → list[EtlImport]  (statut in pending, running)

EtlConflictRepository        → AsyncBaseRepository[EtlConflict]
    + list_pending(import_id: int) → list[EtlConflict]
    + count_pending(import_id: int) → int
    + resolve(conflict_id: int, resolution: str, admin_id: int) → EtlConflict
```

---

## §6.bis — Spécification des schemas Phase A

Pattern : `XxxCreate` / `XxxUpdate` / `XxxResponse` par entité.
Héritage : référentiels sans `tenant_id` → `IDSchema + TimestampSchema` (pas `EntityResponseSchema`).

### CategorieProduit

```python
# app/schemas/catalogue/categories_produit_schema.py

class CategorieProduitCreate(BaseSchema):
    code:        str         Field(max_length=20)
    libelle:     str         Field(max_length=100)
    parent_code: Optional[str] = None   Field(max_length=20)

class CategorieProduitUpdate(BaseSchema):
    libelle:     Optional[str] = None
    parent_code: Optional[str] = None

class CategorieProduitResponse(IDSchema, TimestampSchema):
    code:        str
    libelle:     str
    parent_code: Optional[str] = None

class CategorieProduitTree(CategorieProduitResponse):
    """Réponse enrichie pour l'arbre de catégories."""
    children: list["CategorieProduitTree"] = []
```

### CatalogueProduit

```python
# app/schemas/catalogue/catalogue_produits_schema.py

class CatalogueProduitCreate(BaseSchema):
    ean:              Optional[str] = None   Field(max_length=20)
    designation_norm: str                    Field(max_length=200)
    designation_raw:  str                    Field(max_length=200)
    categorie_code:   str                    Field(max_length=20)
    unite_achat:      str                    Field(max_length=10)
    conditionnement:  Optional[Decimal] = None
    fournisseur_id:   Optional[int] = None

class CatalogueProduitUpdate(BaseSchema):
    designation_norm: Optional[str] = None
    categorie_code:   Optional[str] = None
    unite_achat:      Optional[str] = None
    conditionnement:  Optional[Decimal] = None
    fournisseur_id:   Optional[int] = None
    is_active:        Optional[bool] = None

class CatalogueProduitResponse(IDSchema, TimestampSchema):
    ean:              Optional[str]
    designation_norm: str
    designation_raw:  str
    categorie_code:   str
    unite_achat:      str
    conditionnement:  Optional[Decimal]
    fournisseur_id:   Optional[int]
    is_active:        bool

class CatalogueProduitSearch(BaseSchema):
    """Paramètres de recherche (query params)."""
    q:              Optional[str] = None    # recherche désignation
    categorie_code: Optional[str] = None
    fournisseur_id: Optional[int] = None
    limit:          int = Field(default=20, ge=1, le=100)
    offset:         int = Field(default=0, ge=0)
```

### FournisseurAlim

```python
# app/schemas/catalogue/fournisseur_alim_schema.py

class FournisseurAlimCreate(BaseSchema):
    code:             str   Field(max_length=20)
    nom:              str   Field(max_length=100)
    type_import:      str   Field(max_length=20)   # csv_metro | csv_taiyat | manuel
    format_fichier:   str   Field(max_length=10)
    encodage_defaut:  str = "utf-8"
    separateur_csv:   Optional[str] = None

class FournisseurAlimUpdate(BaseSchema):
    nom:              Optional[str] = None
    type_import:      Optional[str] = None
    format_fichier:   Optional[str] = None
    encodage_defaut:  Optional[str] = None
    separateur_csv:   Optional[str] = None
    is_active:        Optional[bool] = None

class FournisseurAlimResponse(IDSchema, TimestampSchema):
    code:             str
    nom:              str
    type_import:      str
    format_fichier:   str
    encodage_defaut:  str
    separateur_csv:   Optional[str]
    is_active:        bool
```

### EtlImport

```python
# app/schemas/catalogue/etl_import_schema.py

class EtlImportCreate(BaseSchema):
    """Lancé par l'API admin ou la tâche Celery."""
    fournisseur_id: int
    fichier_nom:    str   Field(max_length=255)
    fichier_hash:   str   Field(max_length=64)

class EtlImportResponse(IDSchema, TimestampSchema):
    fournisseur_id:   int
    fichier_nom:      str
    fichier_hash:     str
    statut:           str
    lignes_total:     Optional[int]
    lignes_importees: Optional[int]
    lignes_conflits:  Optional[int]
    erreur_message:   Optional[str]
    started_at:       Optional[datetime]
    finished_at:      Optional[datetime]

class EtlImportStats(BaseSchema):
    """Résumé retourné après un import."""
    import_id:  int
    importees:  int
    merges:     int
    conflits:   int
    creates:    int
    erreurs:    int
    statut:     str
```

### EtlConflict

```python
# app/schemas/catalogue/etl_conflict_schema.py

class EtlConflictResponse(IDSchema, TimestampSchema):
    import_id:               int
    ean:                     Optional[str]
    designation_source:      str
    designation_existante:   Optional[str]
    score_similarite:        Optional[Decimal]
    type_conflit:            str
    statut_resolution:       str
    resolved_by:             Optional[int]
    resolved_at:             Optional[datetime]

class EtlConflictResolve(BaseSchema):
    """Payload pour résoudre un conflit (admin uniquement)."""
    resolution: str   # resolved_merge | resolved_create | resolved_ignore
    # Validator : resolution doit être l'une des 3 valeurs
```

---

## §6 — Spécification des services Phase A

### 6.1 `deduplication_service.py`

Responsabilité unique : décider si deux désignations produits sont "le même produit".

```
DeduplicationService
    SEUIL_MERGE     = 0.92   # similarité → merge automatique (constante nommée)
    SEUIL_CONFLIT   = 0.75   # similarité → conflit à résoudre manuellement

    normalize(designation: str) → str
        — minuscules, supprime stopwords FR ("de", "du", "les", "kg", "g", etc.)
        — supprime ponctuation, double espaces
        — strip

    score(a: str, b: str) → float
        — rapidfuzz.distance.JaroWinkler.normalized_similarity(normalize(a), normalize(b))

    classify(ean: str | None, designation: str, existing: CatalogueProduit | None) → DeduplicationResult
        — Si EAN identique → MERGE automatique
        — Si EAN différent mais designation score ≥ SEUIL_MERGE → MERGE automatique
        — Si score entre SEUIL_CONFLIT et SEUIL_MERGE → CONFLIT à résoudre
        — Sinon → CREATE nouveau produit

DeduplicationResult = Merge(target_id: int) | Conflit(score: float) | Create()
```

### 6.2 `etl_pipeline_service.py`

Orchestration : fichier brut → `CatalogueProduit` + `EtlConflict`.

```
EtlPipelineService
    Deps: CatalogueProduitRepository, EtlImportRepository,
          EtlConflictRepository, DeduplicationService

    run_import(import_id: int, rows: list[dict]) → EtlImportResult
        — Pour chaque ligne :
            1. Vérifier EAN déjà importé (hash check) → skip si doublon
            2. Appeler DeduplicationService.classify()
            3. Merge → mettre à jour CatalogueProduit existant
            4. Conflit → créer EtlConflict (statut pending)
            5. Create → insérer nouveau CatalogueProduit
        — Mettre à jour EtlImport (lignes_importees, lignes_conflits, statut)
        — Retourner EtlImportResult (stats)

EtlImportResult:
    import_id: int
    importees: int
    merges: int
    conflits: int
    creates: int
    erreurs: int
```

---

## §7 — Spécification du parseur METRO

```
# scripts/etl/parsers/metro.py

MetroParser
    # Format CSV METRO :
    # Colonnes attendues (à valider) :
    #   Code article | Désignation | EAN | Unité | Conditionnement | Prix HT | Famille
    EXPECTED_COLUMNS = [...]

    parse(filepath: str | Path, encoding: str = "utf-8", sep: str = ";") → list[MetroRow]
        — Valider présence des colonnes attendues
        — Normaliser types (float → Decimal, strip strings)
        — Skip lignes vides / lignes d'en-tête parasites
        — Retourner MetroRow (dataclass)

MetroRow (dataclass):
    ean:              str | None
    designation:      str
    unite_achat:      str
    conditionnement:  Decimal | None
    prix_ht_centimes: int   # float METRO → centimes entiers
    famille_metro:    str | None
```

**Note** : Le parseur ne touche pas la DB. Il retourne des `MetroRow` pures.
L'écriture en DB est faite par `EtlPipelineService`.

---

## §8 — Spécification `etl_tasks.py`

```python
# app/tasks/etl_tasks.py

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_catalogue_from_metro(self, import_id: int, filepath: str) → dict:
    """Tâche Celery : parse fichier METRO + pipeline ETL."""
    # 1. Parser le fichier
    # 2. Mettre EtlImport.statut = 'running'
    # 3. Appeler EtlPipelineService.run_import()
    # 4. Mettre EtlImport.statut = 'done' | 'failed'
    # 5. Retourner stats

@celery_app.task(bind=True)
def resolve_etl_conflicts_report(self) → dict:
    """Tâche Celery : génère rapport des conflits en attente (monitoring)."""
    # Liste EtlConflict.statut = pending, groupés par fournisseur
    # Log warning si > seuil
```

---

## §9 — Constantes Phase A

### `app/constants/approvisionnement.py`

```python
# Fournisseurs connus (codes)
FOURNISSEUR_METRO   = "METRO"
FOURNISSEUR_TAIYAT  = "TAIYAT"
FOURNISSEUR_EUROCIEL= "EUROCIEL"
FOURNISSEUR_ETHAN   = "ETHAN"
FOURNISSEUR_GNANAM  = "GNANAM"

# ETL — seuils déduplication (ADR-06)
ETL_SEUIL_MERGE_AUTO    = 0.92   # similarité Jaro-Winkler → merge automatique
ETL_SEUIL_CONFLIT_ALERTE= 0.75   # sous ce seuil → conflit à résoudre

# ETL — statuts imports
ETL_STATUT_PENDING  = "pending"
ETL_STATUT_RUNNING  = "running"
ETL_STATUT_DONE     = "done"
ETL_STATUT_FAILED   = "failed"

# ETL — types de conflits
ETL_CONFLIT_EAN_COLLISION      = "ean_collision"
ETL_CONFLIT_DESIGNATION_PROCHE = "designation_proche"
ETL_CONFLIT_CATEGORIE_INCONNUE = "categorie_inconnue"

# ETL — résolutions
ETL_RESOLUTION_PENDING         = "pending"
ETL_RESOLUTION_MERGE           = "resolved_merge"
ETL_RESOLUTION_CREATE          = "resolved_create"
ETL_RESOLUTION_IGNORE          = "resolved_ignore"

# Unités d'achat valides
UNITE_ACHAT_KG     = "KG"
UNITE_ACHAT_LITRE  = "L"
UNITE_ACHAT_PIECE  = "PIECE"
UNITE_ACHAT_CARTON = "CARTON"
UNITE_ACHAT_BOITE  = "BOITE"
UNITE_ACHAT_SACHET = "SACHET"
UNITES_ACHAT_VALIDES = {UNITE_ACHAT_KG, UNITE_ACHAT_LITRE, UNITE_ACHAT_PIECE,
                        UNITE_ACHAT_CARTON, UNITE_ACHAT_BOITE, UNITE_ACHAT_SACHET}
```

---

## §10 — Migrations Alembic Phase A

### Convention de nommage

Les migrations existantes suivent `[hash_8chars]_[description].py`.
Les migrations V2 utilisent le préfixe `v2[lettre][chiffre]_m[nn]_` pour les identifier.

```
alembic/versions/
  v2a0b1c2d3e4_m00_categories_produit.py
  v2b1c2d3e4f5_m01_catalogue_produits.py
  v2c2d3e4f5a6_m02_fournisseurs_alim.py
  v2d3e4f5a6b7_m03_etl_imports.py
  v2e4f5a6b7c8_m04_etl_conflicts.py
```

### Ordre d'application

```
M00 → M01 → M02 → M03 → M04
  │     │
  │     └── FK vers categories_produit.code
  └── Seed 50 catégories via post_migrate hook ou data_migration script
```

### M00 — `categories_produit`

```sql
CREATE TABLE categories_produit (
    id           SERIAL PRIMARY KEY,
    code         VARCHAR(20) NOT NULL UNIQUE,
    libelle      VARCHAR(100) NOT NULL,
    parent_code  VARCHAR(20) REFERENCES categories_produit(code),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_categories_produit_parent ON categories_produit(parent_code);
-- Seed : appelé depuis alembic/data_migrations/seed_categories_produit.py
```

### M01 — `catalogue_produits`

```sql
CREATE TABLE catalogue_produits (
    id                SERIAL PRIMARY KEY,
    ean               VARCHAR(20) UNIQUE,
    designation_norm  VARCHAR(200) NOT NULL,
    designation_raw   VARCHAR(200) NOT NULL,
    categorie_code    VARCHAR(20) NOT NULL REFERENCES categories_produit(code),
    unite_achat       VARCHAR(10) NOT NULL,
    conditionnement   NUMERIC(8,3),
    fournisseur_id    INTEGER,  -- FK ajoutée après M02
    is_active         BOOLEAN NOT NULL DEFAULT true,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_catalogue_produits_categorie ON catalogue_produits(categorie_code);
CREATE INDEX idx_catalogue_produits_fournisseur ON catalogue_produits(fournisseur_id);
CREATE INDEX idx_catalogue_produits_designation ON catalogue_produits(designation_norm);
```

**Note** : `fournisseur_id` sans FK dans M01 (FK ajoutée dans M02 après création de la table cible).

### M02 — `fournisseurs_alim`

```sql
CREATE TABLE fournisseurs_alim (
    id               SERIAL PRIMARY KEY,
    code             VARCHAR(20) NOT NULL UNIQUE,
    nom              VARCHAR(100) NOT NULL,
    type_import      VARCHAR(20) NOT NULL CHECK(type_import IN ('csv_metro','csv_taiyat','manuel')),
    format_fichier   VARCHAR(10) NOT NULL,
    encodage_defaut  VARCHAR(20) NOT NULL DEFAULT 'utf-8',
    separateur_csv   VARCHAR(5),
    is_active        BOOLEAN NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Ajouter FK sur catalogue_produits.fournisseur_id maintenant que la table existe :
ALTER TABLE catalogue_produits
    ADD CONSTRAINT fk_catalogue_fournisseur
    FOREIGN KEY (fournisseur_id) REFERENCES fournisseurs_alim(id) ON DELETE SET NULL;
-- Seed 5 fournisseurs connus
INSERT INTO fournisseurs_alim (code, nom, type_import, format_fichier, separateur_csv)
VALUES
  ('METRO',    'METRO Cash & Carry',    'csv_metro',   'CSV', ';'),
  ('TAIYAT',   'TAIYAT',               'csv_taiyat',  'CSV', ';'),
  ('EUROCIEL', 'EUROCIEL',             'manuel',      'CSV', ';'),
  ('ETHAN',    'ETHAN',                'manuel',      'CSV', ';'),
  ('GNANAM',   'GNANAM',               'manuel',      'CSV', ';');
```

### M03 — `etl_imports`

```sql
CREATE TABLE etl_imports (
    id                SERIAL PRIMARY KEY,
    fournisseur_id    INTEGER NOT NULL REFERENCES fournisseurs_alim(id) ON DELETE RESTRICT,
    fichier_nom       VARCHAR(255) NOT NULL,
    fichier_hash      VARCHAR(64) NOT NULL,
    statut            VARCHAR(20) NOT NULL DEFAULT 'pending'
                      CHECK(statut IN ('pending','running','done','failed')),
    lignes_total      INTEGER,
    lignes_importees  INTEGER,
    lignes_conflits   INTEGER,
    erreur_message    TEXT,
    started_at        TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_etl_imports_fournisseur ON etl_imports(fournisseur_id);
CREATE INDEX idx_etl_imports_statut ON etl_imports(statut);
CREATE INDEX idx_etl_imports_hash ON etl_imports(fichier_hash);
```

### M04 — `etl_conflicts`

```sql
CREATE TABLE etl_conflicts (
    id                      SERIAL PRIMARY KEY,
    import_id               INTEGER NOT NULL REFERENCES etl_imports(id) ON DELETE CASCADE,
    ean                     VARCHAR(20),
    designation_source      VARCHAR(200) NOT NULL,
    designation_existante   VARCHAR(200),
    score_similarite        NUMERIC(5,4),
    type_conflit            VARCHAR(30) NOT NULL
                            CHECK(type_conflit IN ('ean_collision','designation_proche','categorie_inconnue')),
    statut_resolution       VARCHAR(20) NOT NULL DEFAULT 'pending'
                            CHECK(statut_resolution IN ('pending','resolved_merge','resolved_create','resolved_ignore')),
    resolved_by             INTEGER REFERENCES accounts(id),
    resolved_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_etl_conflicts_import ON etl_conflicts(import_id);
CREATE INDEX idx_etl_conflicts_statut ON etl_conflicts(statut_resolution);
CREATE INDEX idx_etl_conflicts_ean ON etl_conflicts(ean);
```

---

## §11 — Seed `categories_produit` (50 catégories)

Fichier : `alembic/data_migrations/seed_categories_produit.py`

Appelé depuis la migration M00 via :
```python
from alembic.data_migrations.seed_categories_produit import run_seed
run_seed(op)
```

Structure hiérarchique (extrait — liste complète dans le fichier) :

```
# Niveau 1 (parent_code = NULL) :
frais, sec, boisson, surgele, epicerie_fine, boucherie, charcuterie,
poissonerie, boulangerie, fromages, produits_laitiers, huiles_condiments,
legumes, fruits, conserves, surimi_seafood, volailles, herbes_epices,
cereales_legumineuses, autres

# Niveau 2 (parent_code = niveau 1) :
frais_viande         → parent: frais
frais_poisson        → parent: frais
frais_legumes        → parent: frais
frais_fruits         → parent: frais
frais_fromage        → parent: frais
frais_laitage        → parent: frais
frais_charcuterie    → parent: frais
frais_traiteur       → parent: frais
sec_pates_riz        → parent: sec
sec_farine           → parent: sec
sec_sucre_confiture  → parent: sec
sec_cafe_the         → parent: sec
boisson_alcool       → parent: boisson
boisson_soft         → parent: boisson
boisson_eau          → parent: boisson
boisson_jus          → parent: boisson
surgele_viande       → parent: surgele
surgele_poisson      → parent: surgele
surgele_legumes      → parent: surgele
surgele_plat_prepare → parent: surgele
huile_olive          → parent: huiles_condiments
huile_tournesol      → parent: huiles_condiments
vinaigre_sauce       → parent: huiles_condiments
sel_poivre           → parent: herbes_epices
epices_orientales    → parent: herbes_epices
herbes_fraiches      → parent: herbes_epices
cereales_riz         → parent: cereales_legumineuses
lentilles_pois       → parent: cereales_legumineuses
# ... (total 50 codes)
```

---

## §12 — Tests Phase A

### Structure

```
tests/unit/catalogue/
├── __init__.py
├── test_deduplication.py      # DeduplicationService
├── test_metro_parser.py       # MetroParser
└── test_etl_pipeline.py       # EtlPipelineService (mocks DB uniquement)
```

### Cas de test obligatoires

**`test_deduplication.py`** :
- `normalize()` → minuscules, stopwords supprimés, ponctuation supprimée
- `score()` identique = 1.0, totalement différent < 0.5
- `classify()` EAN identique → `Merge`
- `classify()` score ≥ 0.92 → `Merge`
- `classify()` score 0.75–0.92 → `Conflit`
- `classify()` score < 0.75 → `Create`
- Anti-régression : "POULET ENTIER 1KG" vs "Poulet entier 1 kg" → Merge
- Anti-régression : "TOMATE CERISE 250G" vs "TOMATES CERISES" → Conflit

**`test_metro_parser.py`** :
- CSV valide → liste de MetroRow correctes
- Colonne manquante → ValueError avec message descriptif
- Prix float "3,50" → 350 centimes
- Ligne vide → skippée (aucune erreur)
- Encodage incorrect → erreur explicite

**`test_etl_pipeline.py`** :
- Import nominal → stats correctes (importees/merges/conflits/creates)
- Double import même hash → raise `DuplicateImportError`
- Ligne sans EAN + designation unique → Create
- Ligne sans EAN + designation proche existante → Conflit
- `EtlImport.statut` passe à `done` après succès
- `EtlImport.statut` passe à `failed` + message d'erreur après exception

### Couverture cible Phase A

| Module | Cible |
|--------|-------|
| `deduplication_service.py` | 95% |
| `metro.py` | 90% |
| `etl_pipeline_service.py` | 85% |
| Modèles (schéma) | 80% |

---

## §13 — Ordre d'implémentation recommandé

L'ordre respecte les dépendances et les invariants CLAUDE.md (max 3 fichiers modifiés par session) :

```
Session 1 — Fondation
  1. pyproject.toml           : +rapidfuzz
  2. app/constants/approvisionnement.py  : nouvelles constantes
  3. app/models/catalogue/__init__.py    : fichier vide (préparer namespace)

Session 2 — Modèles M00 + M01
  1. app/models/catalogue/categories_produit.py
  2. app/models/catalogue/catalogue_produits.py
  3. app/models/__init__.py   : +CategorieProduit, +CatalogueProduit

Session 3 — Modèles M02 + M03 + M04
  1. app/models/catalogue/fournisseur_alim.py
  2. app/models/catalogue/etl_import.py
  3. app/models/catalogue/etl_conflict.py
  (+ app/models/__init__.py dans la même session)

Session 4 — Schemas M00 + M01 + M02
  1. app/schemas/catalogue/categories_produit_schema.py
  2. app/schemas/catalogue/catalogue_produits_schema.py
  3. app/schemas/catalogue/fournisseur_alim_schema.py

Session 5 — Schemas ETL + Migrations M00 → M01
  1. app/schemas/catalogue/etl_import_schema.py
  2. app/schemas/catalogue/etl_conflict_schema.py
  3. app/schemas/catalogue/__init__.py : exports
  (migrations M00-M01 peuvent démarrer en parallèle)

Session 6 — Migrations M00 → M04
  1. alembic/data_migrations/seed_categories_produit.py
  2. alembic/versions/v2a0b1c2d3e4_m00_categories_produit.py
  3. alembic/versions/v2b1c2d3e4f5_m01_catalogue_produits.py
  (M02 à M04 en sessions suivantes, 1 migration par session max)

Session 7 — Repositories catalogue
  1. app/repositories/catalogue/categories_produit_repo.py
  2. app/repositories/catalogue/catalogue_produits_repo.py
  3. app/repositories/__init__.py : export

Session 8 — Repositories ETL
  1. app/repositories/catalogue/fournisseur_alim_repo.py
  2. app/repositories/catalogue/etl_import_repo.py
  3. app/repositories/catalogue/etl_conflict_repo.py

Session 9 — Services + Parseur
  1. scripts/etl/parsers/metro.py
  2. app/services/catalogue/deduplication_service.py
  3. tests/unit/catalogue/test_deduplication.py + test_metro_parser.py

Session 10 — ETL Pipeline + Celery
  1. app/services/catalogue/etl_pipeline_service.py
  2. app/tasks/etl_tasks.py
  3. app/tasks/celery_app.py   : +queue etl

Session 11 — Tests ETL Pipeline
  1. tests/unit/catalogue/test_etl_pipeline.py
  2. Validation couverture ≥ 85%
  3. Marquage Phase A DONE
```

---

## §14 — Checklist de fin de Phase A

```
[ ] M00 migrée + seed 50 catégories appliqué
[ ] M01 migrée
[ ] M02 migrée + FK catalogue_produits.fournisseur_id active
[ ] M03 migrée
[ ] M04 migrée
[ ] app/models/__init__.py inclut les 5 nouveaux modèles
[ ] app/schemas/catalogue/ : 5 fichiers schemas + __init__.py
[ ] rapidfuzz dans pyproject.toml
[ ] DeduplicationService : 95% coverage
[ ] MetroParser : 90% coverage
[ ] EtlPipelineService : 85% coverage
[ ] celery_app.py : queue etl + autodiscover etl_tasks
[ ] Aucun tenant_id sur les tables référentiel (ADR-01, ADR-02)
[ ] Aucun endpoint public exposant catalogue_produits directement (ADR-01)
[ ] Import METRO manuel fonctionnel via scripts/etl/import_pipeline.py
[ ] EtlConflict.resolved_by FK → accounts.id (pas user_id legacy)
```
