# V2 API Admin — Documentation Technique
# Version: 1.0
# Statut: Référence — Domaine Admin/ETL
# Portée: Backend FastAPI + composants React frontend
# Sources: V2_ARCHITECTURE_PLAN.md §§4,6 + ADR-01,05,07,08

---

## Tableau récapitulatif des Celery tasks V2

> **ADR-08** : Le lancement ETL est exclusivement asynchrone via Celery.
> Il n'existe **aucun endpoint REST `POST /etl/run`** — toute tentative d'en créer un est une violation de l'ADR.

| Nom de la task | Queue | Trigger | Description |
|----------------|-------|---------|-------------|
| `etl.tasks.import_metro` | `etl_imports` | Upload fichier via UI (platform_ops) | Parse PDF facture METRO, upsert `catalogue_produits`, calcule scores Jaro-Winkler, insère `etl_conflicts` si score ∈ [0.75, 0.92[ |
| `etl.tasks.import_taiyat` | `etl_imports` | Upload fichier via UI (platform_ops) | Parse fichier TAIYAT (regex), même pipeline déduplication |
| `etl.tasks.import_eurociel` | `etl_imports` | Upload fichier via UI (platform_ops) | Parse PDF EUROCIEL (1 PDF = N factures), même pipeline |
| `etl.tasks.import_ethan` | `etl_imports` | Upload fichier via UI (platform_ops) | Parse XLSX ETHAN, même pipeline |
| `etl.tasks.import_gnanam` | `etl_imports` | Upload fichier via UI (platform_ops) | Parse Excel + OCR GNANAM, même pipeline |
| `etl.tasks.merge_conflict` | `etl_dedup` | Résolution manuelle (platform_ops → PATCH conflit) | Merge automatisé : désactive `catalogue_id_b`, re-route les FK vers `catalogue_id_a` |
| `etl.tasks.dedup_batch` | `etl_dedup` | Celery Beat nocturne | Recalcul batch des scores de déduplication sur les nouvelles entrées non encore comparées |
| `catalogue.tasks.refresh_cache` | `catalogue` | Post-migration Alembic (hook) | Invalide le cache Redis `categories_produit` (TTL 24h, ADR-14) |

**Queues Celery V2** :

| Queue | Workers | Timeout soft | Timeout hard | DLQ |
|-------|---------|-------------|-------------|-----|
| `etl_imports` | 2 | 10 min | 12 min | `etl_imports_dlq` |
| `etl_dedup` | 1 | 5 min | 6 min | `etl_dedup_dlq` |
| `catalogue` | 1 | 30 s | 60 s | — |

---

## Page: ETL Conflicts

Route React : `/admin/etl-conflicts`
Rôles : `platform_ops` (résolution), `super_admin` (lecture + résolution)

### Endpoints API

| Méthode | Path | Params / Body | Réponse |
|---------|------|---------------|---------|
| `GET` | `/api/v2/admin/etl-conflicts` | `?statut=ouvert\|resolu\|tous&score_min=0.75&score_max=0.92&suggestion=MERGE\|DIFFERER\|REJETER&page=1&per_page=20` | `ConflictListResponse` |
| `GET` | `/api/v2/admin/etl-conflicts/stats` | — | `ConflictStatsResponse` |
| `GET` | `/api/v2/admin/etl-conflicts/{id}` | — | `ConflictDetailResponse` |
| `PATCH` | `/api/v2/admin/etl-conflicts/{id}/resolve` | `ConflictResolveBody` | `ConflictDetailResponse` |
| `POST` | `/api/v2/admin/etl-conflicts/batch-resolve` | `ConflictBatchResolveBody` | `BatchResolveResponse` |

#### Shape JSON — `ConflictListResponse`

```json
{
  "items": [
    {
      "id": 42,
      "catalogue_a": {
        "id": 101,
        "ean": "3228857000166",
        "designation": "COCA COLA 1.5L PET",
        "designation_norm": "coca cola 1 5l pet",
        "categorie_code": "BOISSON_GAZEUX",
        "source_fournisseur": "METRO",
        "marque": "Coca-Cola"
      },
      "catalogue_b": {
        "id": 204,
        "ean": null,
        "designation": "Coca-Cola 1,5 litre",
        "designation_norm": "coca cola 1 5 litre",
        "categorie_code": "BOISSON_GAZEUX",
        "source_fournisseur": "TAIYAT",
        "marque": null
      },
      "score_similarite": 0.88,
      "suggestion": "MERGE",
      "statut": "ouvert",
      "created_at": "2026-03-09T08:00:00Z",
      "resolu_at": null,
      "resolu_by": null
    }
  ],
  "total": 47,
  "page": 1,
  "per_page": 20,
  "pages": 3
}
```

#### Shape JSON — `ConflictStatsResponse`

```json
{
  "count_ouvert": 47,
  "count_review": 12,
  "count_resolu": 183,
  "distribution_suggestions": {
    "MERGE": 31,
    "DIFFERER": 9,
    "REJETER": 7
  },
  "score_moyen": 0.84,
  "score_min": 0.75,
  "score_max": 0.919
}
```

#### Shape JSON — `ConflictResolveBody`

```json
{
  "resolution": "MERGE",
  "catalogue_id_a_gagne": 101
}
```

> `resolution` ∈ `{ "MERGE", "DIFFERER", "REJETER" }`.
> `catalogue_id_a_gagne` : requis uniquement si `resolution = "MERGE"` (identifie le produit maître).

#### Shape JSON — `ConflictBatchResolveBody`

```json
{
  "ids": [42, 43, 58],
  "resolution": "REJETER"
}
```

> La résolution batch n'est autorisée qu'avec `REJETER` ou `DIFFERER`.
> Une résolution `MERGE` batch n'est pas supportée (ambiguïté sur le produit maître).

#### Shape JSON — `BatchResolveResponse`

```json
{
  "resolved": 3,
  "failed": 0,
  "errors": []
}
```

### Règles métier

- Un conflit est créé par le pipeline ETL lorsque `score_similarite ∈ [0.75, 0.92[` (ADR-07). Score ≥ 0.92 → merge automatique sans création de conflit. Score < 0.75 → ignoré.
- `MERGE` déclenche la Celery task `etl.tasks.merge_conflict` : `catalogue_id_b.is_active = false`, toutes les FK vers `catalogue_id_b` (articles_epicerie, ingredients) sont re-routées vers `catalogue_id_a` de manière atomique. L'opération est idempotente.
- `DIFFERER` : statut passe à `review`, le conflit reste visible mais filtrable séparément.
- `REJETER` : statut passe à `resolu`, les deux entrées catalogue coexistent.
- `resolu_by` est rempli avec `user_id` de l'opérateur qui résout.
- Les endpoints de résolution loggent une entrée dans `audit_log` (action=`etl_conflict_resolved`, entity=`etl_conflicts`, entity_id=`{id}`). Mutation non auditée = violation A2.
- Seuls `platform_ops` et `super_admin` peuvent écrire. Lecture : idem (données techniques, pas exposées aux tenants).

### Arbre de composants React

```
src/pages/admin/EtlConflictsPage.tsx          (page racine, route /admin/etl-conflicts)
  src/components/admin/etl/ConflictStatsBar.tsx
    -- Affiche count_ouvert, count_review, score_moyen, distribution_suggestions
    -- Badges colorés : MERGE=bleu, DIFFERER=orange, REJETER=gris

  src/components/admin/etl/ConflictFilters.tsx
    -- Filtres : statut (select), score_min/max (range slider), suggestion (select)
    -- Reset filtres button

  src/components/admin/etl/ConflictTable.tsx
    -- Tableau paginé (useConflicts hook)
    -- Colonnes : ID, Désignation A, Désignation B, Score (badge couleur), Suggestion, Statut, Actions
    -- Checkbox multi-sélection pour batch
    -- Score badge : vert ≥ 0.90, orange [0.80,0.90[, rouge [0.75,0.80[
    src/components/admin/etl/ConflictRow.tsx
      -- Ligne expandable : affiche EAN, catégorie, source fournisseur
      -- Bouton "Détail" → ouvre ConflictDrawer

  src/components/admin/etl/ConflictDrawer.tsx
    -- Panel latéral (drawer) côte-à-côte A vs B
    src/components/admin/etl/ConflictProductCard.tsx
      -- Carte produit : EAN, désignation, designation_norm, catégorie, source, marque
      -- Mise en évidence des différences (diff visuel sur les champs)
    src/components/admin/etl/ConflictResolveForm.tsx
      -- Select résolution (MERGE/DIFFERER/REJETER)
      -- Si MERGE : radio "Garder A" / "Garder B"
      -- Bouton "Confirmer" → PATCH /etl-conflicts/{id}/resolve
      -- Gestion erreur via normalizeError (pattern fetchClient MassaCorp)

  src/components/admin/etl/ConflictBatchBar.tsx
    -- Barre contextuelle visible si sélection > 0
    -- Affiche "N sélectionnés", boutons DIFFERER / REJETER
    -- Désactive MERGE en batch (règle métier)
    -- POST /etl-conflicts/batch-resolve

src/hooks/admin/useConflicts.ts               (SWR/React Query, pagination, filtres)
src/hooks/admin/useConflictDetail.ts          (détail unique + mutation résolution)
src/hooks/admin/useConflictStats.ts           (stats header, polling 30s)
```

---

## Page: Catalogue Produits

Route React : `/admin/catalogue`
Rôles : `manager`, `staff` (lecture seule), `platform_ops`, `super_admin`

> **Accès lecture seule pour manager/staff** : Pas de création ni modification via l'UI.
> Le catalogue est alimenté exclusivement par les imports ETL (ADR-01).

### Endpoints API

| Méthode | Path | Params / Body | Réponse |
|---------|------|---------------|---------|
| `GET` | `/api/v2/admin/catalogue` | `?search=coca&ean=3228857&categorie_code=BOISSON_GAZEUX&fournisseur_id=3&is_active=true&page=1&per_page=20` | `CatalogueListResponse` |
| `GET` | `/api/v2/admin/catalogue/{id}` | — | `CatalogueProduitDetail` |
| `GET` | `/api/v2/admin/catalogue/{id}/imports` | `?page=1&per_page=10` | `CatalogueImportHistoryResponse` |
| `GET` | `/api/v2/admin/categories` | — | `CategoriesResponse` (lecture seule, cache Redis 24h) |
| `GET` | `/api/v2/admin/fournisseurs-alim` | — | `FournisseursResponse` (pour filtre dropdown) |

#### Shape JSON — `CatalogueListResponse`

```json
{
  "items": [
    {
      "id": 101,
      "ean": "3228857000166",
      "designation": "COCA COLA 1.5L PET",
      "designation_norm": "coca cola 1 5l pet",
      "marque": "Coca-Cola",
      "unite_base": "piece",
      "conditionnement": "1 carton de 6",
      "source_fournisseur": "METRO",
      "categorie_code": "BOISSON_GAZEUX",
      "categorie_nom": "Boissons gazeuses",
      "is_active": true,
      "nb_sources_fournisseur": 2,
      "derniere_date_import": "2026-03-01T00:00:00Z"
    }
  ],
  "total": 1247,
  "page": 1,
  "per_page": 20,
  "pages": 63
}
```

> `search` effectue une recherche fulltext sur `designation` ET sur `ean` (ILIKE ou index tsvector).
> `designation_norm` n'est pas exposé dans la liste (champ technique interne ETL).

#### Shape JSON — `CatalogueProduitDetail`

```json
{
  "id": 101,
  "ean": "3228857000166",
  "designation": "COCA COLA 1.5L PET",
  "designation_norm": "coca cola 1 5l pet",
  "marque": "Coca-Cola",
  "unite_base": "piece",
  "conditionnement": "1 carton de 6",
  "source_fournisseur": "METRO",
  "categorie": {
    "code": "BOISSON_GAZEUX",
    "nom": "Boissons gazeuses",
    "famille": "Boissons",
    "tva_defaut": 0.055,
    "est_ingredient_resto": false
  },
  "is_active": true,
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-03-01T08:30:00Z",
  "conflicts_ouverts": 1
}
```

#### Shape JSON — `CatalogueImportHistoryResponse`

```json
{
  "items": [
    {
      "etl_import_id": 88,
      "date_import": "2026-03-01T08:00:00Z",
      "fournisseur": "METRO",
      "fichier_nom": "METRO_20260301.pdf",
      "action": "created",
      "ancien_prix_achat_cts": null,
      "nouveau_prix_achat_cts": 149,
      "statut_import": "succes"
    }
  ],
  "total": 5,
  "page": 1,
  "per_page": 10,
  "pages": 1
}
```

> `action` ∈ `{ "created", "updated_designation", "updated_prix", "conflict_detected" }`.

### Règles métier

- `categories_produit` est en **lecture seule** dans toute l'UI — seedée par la migration M00, aucune interface de gestion de catégories n'est prévue (ADR-05). L'endpoint `GET /categories` retourne la liste complète pour alimenter les dropdowns.
- `catalogue_produits` est sans `tenant_id` (ADR-01). Les endpoints catalogue sont accessibles à tous les rôles en lecture, pas de filtre tenant.
- Un produit avec `is_active = false` a été désactivé suite à un MERGE (il était `catalogue_id_b`). Il reste visible dans le catalogue avec un badge "Fusionné".
- `conflicts_ouverts` dans le détail indique si des conflits actifs existent pour ce produit. Si > 0, affichage d'un lien vers la page ETL Conflicts filtrée sur ce produit.
- Aucune création manuelle de produit catalogue via l'UI (insertion uniquement via ETL). Endpoint `POST` non exposé.

### Arbre de composants React

```
src/pages/admin/CataloguePage.tsx             (page racine, route /admin/catalogue)
  src/components/admin/catalogue/CatalogueFilters.tsx
    -- Input search (EAN ou désignation, debounce 300ms)
    -- Select catégorie (arbre 3 niveaux : famille > catégorie > sous-catégorie)
    -- Select fournisseur (METRO, TAIYAT, EUROCIEL, ETHAN, GNANAM)
    -- Toggle is_active (par défaut: actifs uniquement)

  src/components/admin/catalogue/CatalogueTable.tsx
    -- Tableau paginé (useCatalogue hook)
    -- Colonnes : EAN, Désignation, Marque, Catégorie, Fournisseur, Sources, Actif, Dernière import
    -- Ligne cliquable → ouvre CatalogueProductPanel
    src/components/admin/catalogue/CatalogueProductRow.tsx
      -- Badge "Fusionné" si is_active=false
      -- Icône alerte si conflicts_ouverts > 0

  src/components/admin/catalogue/CatalogueProductPanel.tsx
    -- Panel latéral ou modal : détail produit complet
    src/components/admin/catalogue/ProductDetailCard.tsx
      -- Tous les champs du CatalogueProduitDetail
      -- Lien vers conflits si conflicts_ouverts > 0
    src/components/admin/catalogue/ProductImportHistory.tsx
      -- Tableau historique des imports ETL pour ce produit
      -- Colonnes : date, fournisseur, fichier, action, prix avant/après
      -- Pagination interne

src/hooks/admin/useCatalogue.ts               (liste + filtres + pagination)
src/hooks/admin/useCatalogueDetail.ts         (détail + historique imports)
src/hooks/admin/useCategories.ts              (lecture seule, cache SWR long TTL)
```

---

## Page: ETL Imports Log

Route React : `/admin/etl-imports`
Rôles : `super_admin` uniquement

> **Rappel ADR-08** : Cette page affiche uniquement le journal des imports passés.
> Il n'y a **aucun bouton "Lancer un import"** sur cette page.
> Le déclenchement ETL se fait via upload de fichier → dispatch Celery task (interface distincte, hors scope de ce document).

### Endpoints API

| Méthode | Path | Params / Body | Réponse |
|---------|------|---------------|---------|
| `GET` | `/api/v2/admin/etl-imports` | `?fournisseur_id=3&statut=succes\|partiel\|echec&date_from=2026-01-01&date_to=2026-03-31&page=1&per_page=20` | `EtlImportListResponse` |
| `GET` | `/api/v2/admin/etl-imports/{id}` | — | `EtlImportDetailResponse` |
| `GET` | `/api/v2/admin/etl-imports/{id}/conflicts` | `?page=1&per_page=20` | `ConflictListResponse` (filtré par import_id) |
| `GET` | `/api/v2/admin/etl-imports/{id}/task-status` | — | `CeleryTaskStatusResponse` |

#### Shape JSON — `EtlImportListResponse`

```json
{
  "items": [
    {
      "id": 88,
      "fournisseur": {
        "id": 1,
        "nom": "METRO",
        "code_fournisseur": "METRO"
      },
      "fichier_nom": "METRO_20260301.pdf",
      "date_import": "2026-03-01T08:00:00Z",
      "nb_lignes": 312,
      "nb_nouveaux": 14,
      "nb_erreurs": 2,
      "statut": "partiel",
      "celery_task_id": "a3f1b2c4-d5e6-7890-abcd-ef1234567890"
    }
  ],
  "total": 88,
  "page": 1,
  "per_page": 20,
  "pages": 5
}
```

#### Shape JSON — `EtlImportDetailResponse`

```json
{
  "id": 88,
  "fournisseur": {
    "id": 1,
    "nom": "METRO",
    "code_fournisseur": "METRO"
  },
  "fichier_nom": "METRO_20260301.pdf",
  "date_import": "2026-03-01T08:00:00Z",
  "nb_lignes": 312,
  "nb_nouveaux": 14,
  "nb_mis_a_jour": 296,
  "nb_erreurs": 2,
  "nb_conflicts_crees": 5,
  "statut": "partiel",
  "detail_erreurs": "Ligne 45: EAN invalide (longueur 7)\nLigne 203: designation vide",
  "celery_task_id": "a3f1b2c4-d5e6-7890-abcd-ef1234567890",
  "created_at": "2026-03-01T08:00:00Z"
}
```

#### Shape JSON — `CeleryTaskStatusResponse`

```json
{
  "task_id": "a3f1b2c4-d5e6-7890-abcd-ef1234567890",
  "status": "SUCCESS",
  "ready": true,
  "successful": true,
  "progress": {
    "current": 100,
    "total": 100,
    "percent": 100,
    "status": "Import terminé"
  }
}
```

> `status` ∈ `{ "PENDING", "STARTED", "PROGRESS", "SUCCESS", "FAILURE", "RETRY" }` (états natifs Celery).

### Règles métier

- Accès restreint à `super_admin` (log technique, pas exposé aux opérateurs).
- La page ne permet pas de relancer un import en échec directement. Le `celery_task_id` est conservé pour diagnostic uniquement.
- `detail_erreurs` est un champ texte brut (stacktrace ou liste d'erreurs ligne par ligne). Affiché dans un bloc `<pre>` dans l'UI.
- L'onglet "Conflits générés" du détail réutilise `ConflictTable` filtré sur `import_id` (si cette FK est présente dans `etl_conflicts`). Avertissement : si `etl_conflicts` ne porte pas `etl_import_id`, ce filtre n'est pas disponible — à confirmer lors de l'implémentation.
- `GET /task-status` interroge le backend Redis/Celery via `AsyncResult`. Polling 5s côté frontend si statut non terminal.

### Arbre de composants React

```
src/pages/admin/EtlImportsPage.tsx            (page racine, route /admin/etl-imports)
  src/components/admin/etl/EtlImportFilters.tsx
    -- Select fournisseur, Select statut, DateRange picker (date_from / date_to)

  src/components/admin/etl/EtlImportTable.tsx
    -- Tableau paginé (useEtlImports hook)
    -- Colonnes : ID, Fournisseur, Fichier, Date, Lignes, Nouveaux, Erreurs, Statut, Task ID
    -- Badge statut : succes=vert, partiel=orange, echec=rouge
    -- Ligne cliquable → EtlImportDetailPage ou drawer

  src/components/admin/etl/EtlImportDetail.tsx
    -- Résumé chiffres : nb_lignes, nb_nouveaux, nb_mis_a_jour, nb_erreurs, nb_conflicts_crees
    -- Bloc erreurs texte (detail_erreurs) dans <pre> avec copier dans le presse-papier
    -- Onglets : "Résumé" | "Conflits générés" | "Statut task"
    src/components/admin/etl/EtlTaskStatusBadge.tsx
      -- Polling /task-status, affichage barre progression si PROGRESS
      -- État final : succès / échec avec timestamp
    src/components/admin/etl/EtlImportConflictsTab.tsx
      -- Réutilise ConflictTable (filtré import_id)
      -- Lien "Résoudre" → /admin/etl-conflicts?import_id={id}

src/hooks/admin/useEtlImports.ts              (liste + filtres)
src/hooks/admin/useEtlImportDetail.ts         (détail + polling task status)
```

---

## Page: Fournisseurs Alimentaires

Route React : `/admin/fournisseurs-alim`
Rôles : `manager` (lecture), `platform_ops` (lecture), `super_admin` (lecture)

> **Lecture seule** : La liste des fournisseurs est constituée lors de l'onboarding de la plateforme et alimentée par les imports ETL. Aucune création via l'UI n'est prévue en V2.

### Endpoints API

| Méthode | Path | Params / Body | Réponse |
|---------|------|---------------|---------|
| `GET` | `/api/v2/admin/fournisseurs-alim` | `?page=1&per_page=20` | `FournisseurListResponse` |
| `GET` | `/api/v2/admin/fournisseurs-alim/{id}` | — | `FournisseurDetailResponse` |
| `GET` | `/api/v2/admin/fournisseurs-alim/{id}/stats` | — | `FournisseurStatsResponse` |

#### Shape JSON — `FournisseurListResponse`

```json
{
  "items": [
    {
      "id": 1,
      "nom": "METRO Cash & Carry",
      "code_fournisseur": "METRO",
      "type_facturation": "pdf",
      "nb_produits_catalogue": 847,
      "derniere_date_import": "2026-03-01T08:00:00Z",
      "nb_imports_total": 24
    }
  ],
  "total": 5,
  "page": 1,
  "per_page": 20,
  "pages": 1
}
```

#### Shape JSON — `FournisseurDetailResponse`

```json
{
  "id": 1,
  "nom": "METRO Cash & Carry",
  "code_fournisseur": "METRO",
  "type_facturation": "pdf",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-03-01T08:00:00Z"
}
```

#### Shape JSON — `FournisseurStatsResponse`

```json
{
  "fournisseur_id": 1,
  "nb_produits_catalogue": 847,
  "nb_produits_actifs": 831,
  "nb_produits_fusionnes": 16,
  "nb_imports_total": 24,
  "derniere_date_import": "2026-03-01T08:00:00Z",
  "nb_conflicts_generes": 58,
  "nb_conflicts_resolus": 51,
  "nb_conflicts_ouverts": 7,
  "prix_moyen_achat_cts": 312,
  "distribution_categories": [
    { "famille": "Boissons", "nb_produits": 203 },
    { "famille": "Épicerie Salée", "nb_produits": 187 }
  ]
}
```

### Règles métier

- `nb_produits_catalogue` est calculé par agrégation sur `catalogue_produits WHERE source_fournisseur = code_fournisseur AND is_active = true`.
- `nb_produits_fusionnes` = produits désactivés suite à un MERGE ETL (is_active=false).
- `prix_moyen_achat_cts` est calculé sur `prix_fournisseur_historique` (ADR-13), jointure sur `catalogue_id` pour ce fournisseur. Valeur indicative, exprimée en centimes.
- La liste des fournisseurs est également utilisée comme source pour les dropdowns de filtres dans le catalogue et les imports. L'endpoint `GET /fournisseurs-alim` est appelé au chargement du contexte admin.
- `categories_produit` est en lecture seule (ADR-05) : aucun endpoint CRUD n'est exposé pour cette table. La `distribution_categories` dans les stats est calculée à la volée.

### Arbre de composants React

```
src/pages/admin/FournisseursAlimPage.tsx      (page racine, route /admin/fournisseurs-alim)
  src/components/admin/fournisseurs/FournisseurTable.tsx
    -- Tableau simple (peu de lignes : 5 fournisseurs max en V2)
    -- Colonnes : Nom, Code, Format, Nb produits, Dernière import, Conflits ouverts
    -- Ligne cliquable → FournisseurDetailPanel

  src/components/admin/fournisseurs/FournisseurDetailPanel.tsx
    -- Panel latéral : informations fournisseur + stats
    src/components/admin/fournisseurs/FournisseurStatsCard.tsx
      -- Métriques clés : produits actifs, fusionnés, imports total
      -- Barre de progression "conflits résolus vs ouverts"
    src/components/admin/fournisseurs/FournisseurCategoryDistribution.tsx
      -- Tableau ou bar chart : distribution produits par famille de catégorie
      -- Données issues de distribution_categories dans FournisseurStatsResponse
    src/components/admin/fournisseurs/FournisseurImportHistory.tsx
      -- Lien vers /admin/etl-imports filtré sur fournisseur_id
      -- Aperçu des 3 derniers imports (date, nb_lignes, statut)

src/hooks/admin/useFournisseurs.ts            (liste)
src/hooks/admin/useFournisseurDetail.ts       (détail + stats)
```

---

## Notes transversales

### Catégories produit — lecture seule (ADR-05)

`categories_produit` est une **table de référence seedée par la migration M00**.
Elle contient 50 entrées en 3 niveaux (12 familles). Elle n'est pas gérée via l'UI.
Cache Redis TTL 24h (ADR-14), invalidé uniquement lors des migrations Alembic.

L'endpoint `GET /api/v2/admin/categories` est le seul point d'accès. Il n'existe pas
d'endpoints `POST`, `PATCH` ou `DELETE` pour `categories_produit`.

### Sécurité transversale

- Tous les endpoints `/api/v2/admin/*` requièrent `Authorization: Bearer <JWT>` (invariant A4).
- Les rôles sont vérifiés côté backend via le middleware RBAC existant.
  Le frontend ne doit jamais masquer une action sur la base d'un rôle sans vérification backend.
- Toute mutation (résolution conflit) est auditée dans `audit_log` (invariant A2).
- Aucun `tenant_id` n'est requis dans les endpoints admin — les tables du domaine Admin
  (catalogue, etl_imports, etl_conflicts, fournisseurs_alim, categories_produit)
  sont sans tenant_id (ADR-01, ADR-02, ADR-05).

### Gestion des erreurs frontend

Pattern standard `fetchClient` MassaCorp :

```typescript
import { normalizeError } from '@/errors/normalizer'

try {
  await resolveConflict(id, body)
} catch (err) {
  const appErr = normalizeError(err)
  if (appErr.category === 'validation') {
    // appErr.fieldErrors pour les 422
  }
  setError(appErr.message || 'Une erreur est survenue')
}
```

Ne jamais accéder directement à `(err as any).response?.data?.detail` (pattern Axios incompatible avec fetchClient).

### Structure des fichiers src/

```
src/
  pages/
    admin/
      EtlConflictsPage.tsx
      CataloguePage.tsx
      EtlImportsPage.tsx
      FournisseursAlimPage.tsx
  components/
    admin/
      etl/
        ConflictStatsBar.tsx
        ConflictFilters.tsx
        ConflictTable.tsx
        ConflictRow.tsx
        ConflictDrawer.tsx
        ConflictProductCard.tsx
        ConflictResolveForm.tsx
        ConflictBatchBar.tsx
        EtlImportFilters.tsx
        EtlImportTable.tsx
        EtlImportDetail.tsx
        EtlTaskStatusBadge.tsx
        EtlImportConflictsTab.tsx
      catalogue/
        CatalogueFilters.tsx
        CatalogueTable.tsx
        CatalogueProductRow.tsx
        CatalogueProductPanel.tsx
        ProductDetailCard.tsx
        ProductImportHistory.tsx
      fournisseurs/
        FournisseurTable.tsx
        FournisseurDetailPanel.tsx
        FournisseurStatsCard.tsx
        FournisseurCategoryDistribution.tsx
        FournisseurImportHistory.tsx
  hooks/
    admin/
      useConflicts.ts
      useConflictDetail.ts
      useConflictStats.ts
      useCatalogue.ts
      useCatalogueDetail.ts
      useCategories.ts
      useEtlImports.ts
      useEtlImportDetail.ts
      useFournisseurs.ts
      useFournisseurDetail.ts
```
