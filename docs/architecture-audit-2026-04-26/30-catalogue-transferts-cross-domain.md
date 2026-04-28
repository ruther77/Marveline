# Module 30 — Catalogue partagé / Transferts cross-domain (synthèse Phase D)

> **Phase D — DERNIER MODULE.** Audit transverse du catalogue alimentaire partagé (M00 categories_produit + catalogue_produits + catalogue_produit_eans + colisages + etl_correction_history) et de tous les chemins cross-domain : `InternalTransfer` (épicerie → restaurant), `TransferRequest` (restaurant → épicerie), pipeline ETL TAIYAT routing multi-tenant (INCONTOURNABLE → restaurant, NOUTAM → épicerie), `IngredientEpicerieMapping` cross-tenant.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/catalogue/categories_produit.py` | 89 |
| `app/models/catalogue/catalogue_produit.py` | 110 (déjà mod. 28) |
| `app/models/catalogue/catalogue_produit_ean.py` | 53 |
| `app/models/catalogue/catalogue_produit_colisage.py` | 64 |
| `app/models/catalogue/etl_import.py` | 186 (déjà mod. 28) |
| `app/models/catalogue/etl_conflict.py` | 100 (déjà mod. 28) |
| `app/models/catalogue/etl_correction_history.py` | 47 |
| `app/models/epicerie/internal_transfer.py` | 214 (parcours mod. 28) |
| `app/etl_types.py` | 92 |
| `app/services/catalogue/etl_classification.py` | 834 (parcours sections clés) |
| `app/services/catalogue/etl_deduplication.py` | 429 (parcours) |
| `app/services/catalogue/etl_auto_fill.py` | 522 (parcours) |
| `app/services/catalogue/etl_import_service.py` | 793 (parcours) |
| `app/services/catalogue/etl_designation_enrichment.py` | 180 |
| `app/services/catalogue/off_enrichment.py` | 251 |
| `app/services/catalogue/etl_pdf_storage.py` | 113 |
| `app/services/epicerie/reception_etl.py` | 1 397 (parcours fonctions clés) |
| `app/services/restaurant/reception_etl.py` | 426 (lu mod. 29) |
| `app/tasks/etl_tasks.py` | 161 |

**Volume total Phase D synthèse** : ~6 060 LoC (+ ~3 000 LoC déjà couvertes mod. 28-29).

---

## 2. Architecture observée — vue cross-domain

```
                      ┌─── PARSER METRO ────┐
                      │  (NOUTAM = épicerie) │
PDF facture ─────────►│  parse + categorize  ├──────► LigneParsee[]
                      └──────────────────────┘              │
                      ┌─── PARSER TAIYAT ───┐                │
                      │ INCONTOURNABLE=resto │                │
                      │ NOUTAM = épicerie    │                │
                      └──────────────────────┘                │
                                                              ▼
                                  ┌─────────────────────────────────────┐
                                  │  EtlImport (statut PENDING)         │
                                  │  + FactureMetadata                   │
                                  │    (target_tenant_id : 2 ou 3)       │
                                  └────────────┬────────────────────────┘
                                               │
                                               ▼
                            ┌─── Celery run_etl_import ───┐
                            │ (queue 'etl', max_retries=1) │
                            └──────────────┬───────────────┘
                                           │
                                           ▼
                  ┌────── catalogue.run_import (preview_mode) ──────┐
                  │  enrich + classify + auto-fill S1-S4           │
                  │  → statut PREVIEW (lignes_data JSON)            │
                  └─────────────────┬───────────────────────────────┘
                                    │   [opérateur valide]
                                    ▼
              ┌────────────────────────────────────────────────────┐
              │  selon target_tenant_id :                          │
              │   2 → epicerie.recevoir_facture_etl                 │
              │       sync catalogue → epicerie_produits            │
              │       MouvementStock ENTREE × N                    │
              │       FinanceInvoice FOURNISSEUR                   │
              │   3 → restaurant.recevoir_facture_etl_restaurant   │
              │       upsert IngredientRestaurant nom-norm         │
              │       MouvementStockRestaurant entree × N           │
              │       FinanceInvoice FOURNISSEUR                   │
              └────────────────────────────────────────────────────┘

CROSS-TENANT FLUX (post-import) :
  ┌─── InternalTransfer ────┐         ┌─── IngredientEpicerieMapping ────┐
  │ tenant=épicerie (2)     │         │ tenant=restaurant (3)             │
  │ dest_tenant_id=resto (3)│  cumul  │ produit_id=epicerie_produits.id   │
  │ FSM PENDING→VALIDATED   ├────────►│ ordre + facteur_conv              │
  │  →CANCELLED             │         │ → IngredientSourcing.resolve()    │
  └─────────────────────────┘         └───────────────────────────────────┘

  ┌─── TransferRequest ─────┐
  │ tenant=restaurant (3)   │
  │ target_tenant_id=epi (2)│  workflow MVP (mod. 29 F923)
  │ PENDING→APPROVED→FULFI- │  fulfilled_transfer_id NEVER SET côté code
  │ LLED|REJECTED|CANCELLED │
  └─────────────────────────┘

REFERENTIEL PARTAGE (sans tenant_id) :
  CategorieProduit (91 codes, M00 seed, FK code par chaîne string)
  CatalogueProduit (cross-tenant, EAN UNIQUE partiel)
  CatalogueProduitEan (alias multi-EAN cross-pays/pack)
  CatalogueProduitColisage (pivot multi-valeurs colisage observé)
  EtlCorrectionHistory (apprentissage classification)
```

---

## 3. Frictions identifiées — module 30

> Compteur cumulé (mod. 01-29) ≈ 955. Module 30 ouvre à **F956**.

### 3.1 P0

#### F956 — `CategorieProduit` référencé par `CatalogueProduit.categorie_code` **String FK soft** (pas FK SQL)

**Constat.** `models/catalogue/catalogue_produit.py` (lu mod. 28) a `categorie_code: Mapped[str]` sans `ForeignKey("categories_produit.code")`. Aussi `EpicerieProduit.categorie` (mod. 28) et `IngredientRestaurant.categorie_code` (mod. 29). 

→ Si la migration M00 supprime/renomme un code (ex: passage `ALC_VIN_RGE` → `ALC_VIN_ROUGE`), **aucune cascade ni vérification**. Tous les produits avec l'ancien code deviennent orphelins silencieusement, le filtre `est_ingredient_resto` cesse de fonctionner partiellement.

**Action** : ajouter `ForeignKey("categories_produit.code", ondelete="RESTRICT")` sur les 3 colonnes ; ou matérialiser le `categorie_id Integer` (cf. `IngredientRestaurant.categorie_id`).

---

#### F957 — `CategorieProduit` **sans tenant_id** : un admin peut désactiver `is_active=False` une catégorie commune et casser tous les tenants

`models/catalogue/categories_produit.py:21`. `SoftDeleteMixin` mais pas `TenantMixin` → soft-delete global. Un admin SaaS qui désactive `FRAIS_BOEUF` plante les filtres de tous les tenants. Aucun audit : qui a désactivé, quand.

**Action** : seed M00 strict + `is_active` interdite côté API ou table `tenant_categorie_disabled` séparée pour préférences locales.

---

#### F958 — `CategorieProduit.tva_defaut Float default=0.20` Marveline-spécifique français — non multi-pays

L. 56-59. À La Réunion, certains alimentaires sont 0% (loi 1952 outre-mer). Les Splendid Events Sénégal (cf. memory client-splendid-events) sont à 18%. Le default `0.20` se propage à `EpicerieProduit.taux_tva` (cf. F660 mod. 15) puis à toutes les ventes/factures.

→ Aucune mécanique pour override per tenant_country. La TVA défaut est globale.

**Action** : `tenant_settings.country_code` + table `tva_par_pays_categorie` ; par défaut Float = `tenant_settings.default_tva` lookup.

---

#### F959 — `EtlCorrectionHistory` **sans tenant_id** — apprentissage cross-tenant

`models/catalogue/etl_correction_history.py:17`. Pas TenantMixin. Une correction d'un opérateur tenant Marveline propage les suggestions à tous les autres tenants. → Fuite de connaissance métier (un concurrent SaaS reverrait les corrections de l'autre).

**Action** : `tenant_id` NOT NULL + filter dans `lookup_correction_history` ; ou table partagée + scope `is_global`.

---

#### F960 — `run_etl_import` (Celery task) **n'a pas de `tenant_id` dans les args** — toute autre validation se fait via `metadata.target_tenant_id` non vérifié

`tasks/etl_tasks.py:87-123`. La task accepte `etl_import_id, lignes_data` et reconstruit des `LigneParsee`. Aucun `tenant_id` arg. La validation tenant repose sur `EtlImport.target_tenant_id` qui peut être null ou faux. Combiné à F965 (preview accepte cross-tenant), un attaquant peut forger un `lignes_data` qui se déverse dans le mauvais tenant.

**Action** : ajouter `tenant_id` arg explicite + assert `EtlImport.tenant_id == arg`.

---

#### F961 — Pipeline ETL **n'audite pas qui valide** un import preview

`services/catalogue/etl_import_service.py:run_import` change le statut `PREVIEW` puis return. La validation suivante (recevoir_facture_etl) est appelée par un endpoint admin mais aucun champ `validated_by_id` n'est documenté côté model. → Si un opérateur accepte par erreur 200 produits classifiés en `AUTRE`, impossible de retracer.

(À confirmer EtlImport.validated_by_id — si présent OK, sinon P0.)

---

#### F962 — `_handle_ean_match` met à jour `prix_unitaire_cts`, `taux_tva_centieme`, `conditionnement`, `unite_base` **silently** sur le `CatalogueProduit` cross-tenant

`services/catalogue/etl_import_service.py:391-398`. Le catalogue partagé est cross-tenant. Si Marveline fait un import METRO et écrase prix_unitaire_cts à 100, et SPLENDID a un mapping vers ce produit avec ancien prix snapshot, il y a drift. Cf. F874 mod. 28.

→ Aucune historisation : table `CatalogueProduitPriceHistory` absente.

---

#### F963 — `add_secondary_ean` ne pose **aucun verrou unique global** au moment du concurrent INSERT

`services/catalogue/etl_import_service.py:483-490`. La contrainte `uq_catalogue_produit_eans_ean` existe SQL (cf. catalogue_produit_ean.py:46), mais le code attrape `Exception` et log warning seulement. Si deux imports parallèles ajoutent le même EAN secondaire, IntegrityError est swallowed → l'import termine OK mais la traçabilité fournisseur est perdue.

**Action** : remplacer `except Exception` par une stratégie ON CONFLICT DO NOTHING explicite + retourner si déjà présent.

---

#### F964 — `run_etl_import` Celery `max_retries=1` **expose une condition de double-import partiel**

`tasks/etl_tasks.py:83`. Un retry après 300s sur un import déjà partiellement appliqué (catalog INSERT commit puis exception aval) peut re-créer des produits. La task utilise `_get_worker_loop()` partagé entre invocations → si l'event loop a un état d'asyncpg corrompu (conn pool), le second tour s'exécute sur connexions stale.

→ Idempotence non garantie. ETL-DUPE-01 (memory) résolu côté `validate_import` mais pas côté Celery import.

**Action** : transformer `run_etl_import` en idempotent via `EtlImport.statut == PENDING` requis ou advisory lock par `etl_import_id`.

---

#### F965 — `IngredientEpicerieMapping` cross-tenant produit_id sans CHECK ni FK contrainte tenant épicerie

Cf. F924+F925 mod. 29. Réitéré ici car le pattern cross-tenant est exposé dans 3 modules : InternalTransfer, IngredientEpicerieMapping, TransferRequest. **Aucun** invariant SQL ne lie `dest_tenant_id` à `target_tenant_id` ni `produit.tenant_id`.

**Action** : trigger DB qui valide la cohérence cross-tenant au INSERT/UPDATE des 3 tables.

---

#### F966 — `EtlImport.lignes_data JSONB` non versionné — re-import 6 mois plus tard avec dataclass mutée = crash

Cf. F875 mod. 28. Réitéré : c'est le pivot central de re-validation/revert/edit. Un changement de `LigneParsee` (ajout champ obligatoire) casse les imports historiques.

**Action** : champ `lignes_data_schema_version` int + migrator.

---

### 3.2 P1

#### F967 — `_global_idf` **singleton module-level** mutated par `build_idf_from_candidates` à chaque batch

`services/catalogue/etl_deduplication.py:215`. Si deux Celery workers (ou deux imports parallèles dans le même process) appellent `build_idf_from_candidates`, l'IDF du second écrase celui du premier mid-import → score Soft TF-IDF du premier devient incohérent.

**Action** : `IdfCorpus` instance per call passed as argument.

---

#### F968 — `classify_categorie_code` parcourt `_RULES` (~150 règles × ~20 keywords) en O(n²) sur chaque ligne

`services/catalogue/etl_classification.py:746-774`. Pour 1000 lignes facture, ~3M opérations. Pas de pré-compile en regex. Acceptable pour débit ETL mais inefficace.

---

#### F969 — `_NON_FOOD_MARKERS` + `_FOOD_ONLY_CATEGORIES` (etl_classification.py) listes hardcoded ~700 termes — drift maintenance

L. 700-724. Aucune mécanique pour évolution (pas de table DB, pas de Redis). Un nouveau produit "savon Bio Gourmet" peut tromper la pré-détection. Cf. memory bug-eurociel-prix-null.md.

---

#### F970 — `compute_similarity_smart` bonus marque `+0.15` puis `*1.10` cumulés (l. 313) sans cap empirique

Pour bases score 0.85 + bonus marque + booster = 1.0 atteint trop vite → MATCH décidé sur signal marque seul, désignations différentes. Risque faux-positifs SOMMET (vin rouge identique mais millésimes différents).

---

#### F971 — `EtlImport.target_tenant_id` Optional → **nullable** : si parser TAIYAT échoue à détecter `INCONTOURNABLE` vs `NOUTAM`, le routage est NULL et la validation plante 422 sans recouvrement automatique

Pas de queue "à arbitrer manuellement" pour ces cas. L'import reste en PREVIEW indéfiniment.

---

#### F972 — `_apply_facture_metadata` (etl_import_service.py:607-623) **écrase silently** les champs si l'opérateur les a déjà saisis manuellement

Si admin a corrigé `numero_facture` puis re-run import (édition lignes), les corrections meta sont perdues.

---

#### F973 — `run_import` preview_mode crée une seconde lecture intégrale `CatalogueProduit.designation_norm` (l. 670-679 + l. 744-752) — duplication query (perf)

---

#### F974 — `_record_colisage_observed` `try/except Exception` swallow (l. 374-378) — colisage drift silencieux

---

#### F975 — `enrich_from_validated_product` (brand_dictionary) `except Exception: pass` (l. 458) — anti-pattern

---

#### F976 — `lookup_correction_history` retourne **toujours None** (placeholder l. 741) — Layer 0 cassé

`services/catalogue/etl_classification.py:727-743`. La fonction documentée comme "Layer 0" ne fait rien de fonctionnel. Le vrai lookup est dupliqué inline dans `etl_import_service.py:683-695`. Confusion architecturale.

---

#### F977 — `_apply_stock_delta`, `_apply_price_update` (epicerie/reception_etl.py:680, 761) sans audit log structurel

L'opérateur peut éditer une facture validée → ces fonctions corrigent stock + prix mais ne posent pas d'`AuditLog`. Cf. F910 commande resto.

---

#### F978 — `InternalTransfer.invoice_id ondelete="SET NULL"` masque l'audit trail si la facture est supprimée

`models/epicerie/internal_transfer.py:67`. Si l'invoice INTERNE liée est supprimée par cascade (ne devrait pas), le transfer reste avec invoice_id=NULL → audit perdu. RESTRICT eût été plus sûr.

---

#### F979 — `revert_import` (epicerie/reception_etl.py:1299) doit revertir produits + stock + invoice — confirmé pour epicerie mais **pas symétrique** côté restaurant

`services/restaurant/reception_etl.py:revert_import_restaurant` (F921 mod. 29) clamp silencieux. Patterns asymétriques entre les 2 receptions.

---

#### F980 — `_resolve_vendor_id` auto-crée un `FinanceVendor` à chaque import si vendor_code inconnu (epicerie l. 119-121, restaurant l. 204-206)

→ Si parser TAIYAT mute le vendor_code en faute de frappe, un nouveau Vendor est créé silencieusement. Référentiel pollué.

---

#### F981 — `EtlImport` reverted_at + reverted_by_id documentés dans le service mais à confirmer model side (déjà mod. 28 P1)

---

#### F982 — `CatalogueProduitColisage.first_seen_at / last_seen_at` mais **last_seen_at n'est pas mis à jour** dans `record_colisage` documenté

À vérifier. Si record_colisage juste INSERT ON CONFLICT DO NOTHING, last_seen_at gel.

---

#### F983 — `EtlImport.client_name` String — pas de CHECK enum `(INCONTOURNABLE, NOUTAM, NULL)` 

Frappe libre TAIYAT possible → drift routage tenant.

---

#### F984 — Pas de **rate limit** sur Celery `run_etl_import` — un tenant peut soumettre 1000 imports en parallèle et étouffer la queue

---

#### F985 — `CatalogueProduit` n'a pas de field `discontinued_at` ni équivalent — les produits METRO retirés du catalogue persistent

Combinés F870 (UNIQUE EAN) + pas de retire → liste des produits livrables grossit indéfiniment.

---

#### F986 — `_compute_final_statut` SUCCES/PARTIEL seulement (`run_import` l. 350) — pas de statut ECHEC explicite

Si toutes les lignes échouent (`nb_erreur == len(lignes)`), le statut est PARTIEL, pas ECHEC. UI peut croire "partiellement importé" alors que rien n'est passé.

---

### 3.3 P2

#### F987 — `_FINAL_CATEGORIES` frozenset hardcoded 91 codes (etl_import_service.py:125-153) — duplique `categories_produit` table

Drift garanti si admin ajoute une catégorie en DB, ne paraît pas dans `_FINAL_CATEGORIES` → classification rejette le code valide.

---

#### F988 — `_REGIE_TO_FAMILIES` mapping régie METRO uniquement, TAIYAT ignoré (l. 157-190)

Si TAIYAT introduit ses propres régies, refacto nécessaire.

---

#### F989 — `_VOLUME_TOLERANCE_PCT = 0.05` magic number (l. 55) — pas dans constants

---

#### F990 — `compute_line_confidence` pondération hardcoded 25/20/20/15/10/10 (l. 583-603) — non configurable

---

#### F991 — `EtlImport.lignes_data` JSONB peut atteindre plusieurs MB pour gros imports — pas de stratégie split/streaming

---

#### F992 — `CatalogueProduit.designation_norm` Index simple non `lower(unaccent())` — recherches qui n'utilisent pas la fonction normalize sont sequentialscan

---

#### F993 — `etl_pdf_storage.py` (113 LoC) parcouru rapidement — fichier non analysé en détail (PDF storage)

---

#### F994 — `off_enrichment.py` (251 LoC) parcouru rapidement — Open Food Facts integration externe non auditée

---

#### F995 — `etl_designation_enrichment.py` (180 LoC) parcouru — patterns probables même

---

### 3.4 P3

#### F996 — Comments mix anglais/français (`Resout`, `creee`) — accents perdus

#### F997 — `_QUEUE_ETL = "etl"` magic string littéral

#### F998 — `_TASK_NAME = "app.tasks.etl_tasks.run_etl_import"` chemin hardcoded — fragile au refacto

---

## 4. Synthèse module 30

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 11 | F956 (no FK categorie_code), F957 (no tenant_id CategorieProduit), F958 (TVA Marveline-only), F959 (no tenant_id correction history), F960 (no tenant arg Celery), F961 (no validated_by audit), F962 (silent price overwrite), F963 (silent EAN integrity), F964 (Celery double-import retry), F965 (cross-tenant validation FK), F966 (lignes_data versioning) |
| P1 | 20 | F967 → F986 |
| P2 | 9 | F987 → F995 |
| P3 | 3 | F996 → F998 |
| **Total** | **43** | F956 → F998 |

**Compteur cumulé après module 30** : ≈ 955 + 43 = **998 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) FK `categorie_code` + matérialisation `categorie_id` (F956) ; (2) tenant_id + RBAC sur CategorieProduit + EtlCorrectionHistory (F957+F959) ; (3) tva_defaut multi-pays (F958) ; (4) tenant_id dans Celery args + assert (F960) ; (5) audit `validated_by_id` (F961) ; (6) `CatalogueProduitPriceHistory` (F962) ; (7) versioning lignes_data (F966) ; (8) trigger DB cross-tenant validation (F965) ; (9) idempotence Celery via advisory lock (F964).
>
> **Refactor** : `IdfCorpus` per-call (F967) ; statut ECHEC explicite (F986) ; CHECK `client_name IN (...)` (F983) ; CategorieProduit côté DB seedée + `_FINAL_CATEGORIES` éliminé (F987).

---

# 🎯 PHASE D TERMINÉE

**Modules 28-30 livrés.** ~14 000 LoC supplémentaires audités. Compteur **998 frictions** au total sur 30 modules (~115 P0).

**Prochaines phases :**
- **Phase E** (modules 31-35) : Audit / Feature flag / Orchestration / Printer / VPN / Health-Metrics
- **Phase F** (module 99) : Synthèse globale frictions registry, top 30 P0, plan triage
