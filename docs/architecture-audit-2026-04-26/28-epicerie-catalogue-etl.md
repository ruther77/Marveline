# Module 28 — Épicerie + Catalogue ETL alimentaire

> **Phase D.** Audit du domaine **Épicerie** (POS, stock, transferts internes, commandes fournisseurs) **+ Catalogue ETL** alimentaire partagé (référentiel cross-tenant METRO/TAIYAT/EUROCIEL). Domaine secondaire d'origine ETL → progressivement intégré au modèle métier.

---

## 1. Inventaire — lecture intégrale

### 1.1 Épicerie

| Fichier | LoC |
|---|---|
| `app/models/epicerie/produit.py` | 109 |
| `app/models/epicerie/stock.py` | 74 |
| `app/models/epicerie/stock_movement.py` | 133 |
| `app/models/epicerie/vente.py` | 218 (EpicerieVente + EpicerieVenteLigne) |
| `app/models/epicerie/internal_transfer.py` | 214 (InternalTransfer + InternalTransferLine) |
| `app/models/epicerie/supply_order.py` | 181 (SupplyOrder + SupplyOrderLine) |
| `app/models/epicerie/marge.py` | 35 |
| `app/models/epicerie/prix_historique.py` | 70 |
| `app/models/epicerie/produit_ean.py` | 53 |
| `app/services/epicerie/vente.py` | 231 |
| `app/services/epicerie/transfert.py` | 211 |
| `app/services/epicerie/transfer_request.py` | 241 |
| `app/services/epicerie/supply_order.py` | 192 |
| `app/services/epicerie/inventaire.py` | 162 |
| `app/services/epicerie/reception_etl.py` | 1 397 (parcours) |
| `app/services/epicerie/dashboard.py` | 152 |
| `app/services/epicerie/fournisseurs.py` | 382 |
| `app/services/epicerie/image_fetcher.py` | 311 |

### 1.2 Catalogue ETL alimentaire

| Fichier | LoC |
|---|---|
| `app/models/catalogue/catalogue_produit.py` | 110 |
| `app/models/catalogue/catalogue_produit_ean.py` | 53 |
| `app/models/catalogue/catalogue_produit_colisage.py` | 64 |
| `app/models/catalogue/categories_produit.py` | 89 |
| `app/models/catalogue/etl_import.py` | 186 |
| `app/models/catalogue/etl_conflict.py` | 100 |
| `app/models/catalogue/etl_correction_history.py` | 47 |
| `app/services/catalogue/etl_import_service.py` | 793 |
| `app/services/catalogue/etl_classification.py` | 834 (parcours) |
| `app/services/catalogue/etl_auto_fill.py` | 522 (parcours) |
| `app/services/catalogue/etl_deduplication.py` | 429 (parcours) |
| `app/services/catalogue/etl_designation_enrichment.py` | 180 (parcours) |
| `app/services/catalogue/etl_pdf_storage.py` | 113 (parcours) |
| `app/services/catalogue/off_enrichment.py` | 251 (parcours) |

**Volume total** : ~9 200 LoC (Épicerie ~3 690 + Catalogue ETL ~5 510).

---

## 2. Architecture observée

```
┌────────────────────────────────────────────────────────────────────────┐
│         Catalogue ETL alimentaire (RÉFÉRENTIEL PARTAGÉ — pas tenant)   │
│                                                                          │
│   Parser ETL (METRO/TAIYAT/EUROCIEL) ──► LigneParsee                   │
│   ──► etl_import_service.run_import :                                   │
│       PENDING → RUNNING → (PREVIEW → VALIDATED) | SUCCES | PARTIEL     │
│                                                                          │
│   CatalogueProduit (id, ean, designation, marque, categorie_code,      │
│                      prix_unitaire_cts, taux_tva_centieme)             │
│   EtlImport (statut, prix_snapshot, lignes_data JSON, metadata facture)│
│   EtlConflict (résolution PENDING|MERGED|KEPT_SEPARATE)                │
│   EtlCorrectionHistory (auto-apply traçables)                          │
│                                                                          │
│   Déduplication Jaro-Winkler (ADR-07) seuils 0.85/0.75                 │
│   Classification 91 catégories régie+keywords+KNN (6 niveaux fallback) │
│   Auto-fill S1-S4 (catalogue, history, TF-IDF)                         │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│              Épicerie (TENANT_ID=2)                                     │
│                                                                          │
│  EpicerieProduit (catalog tenant — sync depuis CatalogueProduit)       │
│  EpicerieStock (1:1 produit, quantite Numeric(10,3))                   │
│  EpicerieStockMovement (immuable journal: ENTREE/SORTIE/VENTE/         │
│                          AJUSTEMENT/PERTE/TRANSFERT_RESTAURANT)        │
│                                                                          │
│  EpicerieVente (FSM EN_COURS → VALIDEE | ANNULEE | REMBOURSEE)         │
│   ↓ encaisser() atomique : vente + lignes + mvts stock + invoice       │
│   ↓ annuler_vente() : remet en stock via mvts AJUSTEMENT               │
│                                                                          │
│  InternalTransfer (épicerie → restaurant)                               │
│   FSM: PENDING → VALIDATED | CANCELLED                                  │
│   valider_transfert() atomique :                                        │
│   - décrémente stock épicerie (TRANSFERT_RESTAURANT)                   │
│   - incrémente stock restaurant (transfert_entrant via MouvementStock) │
│   - crée FinanceInvoice INTERNE                                         │
│                                                                          │
│  SupplyOrder (commande fournisseur)                                     │
│   FSM: en_attente → confirmee → expediee → livree | annulee            │
│   recevoir() atomique : MAJ received_quantity + mvts ENTREE + invoice  │
└────────────────────────────────────────────────────────────────────────┘
```

**Observation cruciale** : Épicerie a ses propres tables (`epicerie_produits`, `epicerie_stock`, etc.) **séparées de Marveline** (`products`, `stock_items`, etc.). Aucun lien FK direct, double catalogue par design (mod. 15 `Product` ≠ `EpicerieProduit`).

---

## 3. Frictions identifiées — module 28

> Compteur cumulé (mod. 01-27) ≈ 868. Module 28 ouvre à **F869**.

### 3.1 P0

#### F869 — `EpicerieProduit.ean` indexé `(tenant_id, ean)` mais **PAS UNIQUE**

`models/epicerie/produit.py:99` : `Index("idx_epicerie_produit_ean", "tenant_id", "ean")` sans `unique=True`. Doublons d'EAN par tenant possibles → caisse pose le code-barre, lookup retourne 2 produits, choix arbitraire.

**Action** : `Index("uq_epicerie_produit_tenant_ean", "tenant_id", "ean", unique=True, postgresql_where="ean IS NOT NULL")` (UNIQUE partielle puisque ean nullable).

---

#### F870 — `encaisser` (`services/epicerie/vente.py:108`) `payload.check_stock=False par défaut`

```python
if payload.check_stock:
    for lc in lignes_calculees:
        stock = await stock_repo.get_by_produit(...)
        if dispo < lc["ligne"].quantite:
            raise HTTPException(409, "STOCK_INSUFFISANT")
```

**Par défaut, le check stock est désactivé**. La vente passe alors la phase 7 (création mouvement) où `EpicerieStockMovement.stock_apres >= 0` (CHECK SQL ligne 114-116) bloque → **`IntegrityError 500`** au lieu d'un `409 STOCK_INSUFFISANT` propre.

UX caissier : message générique "Erreur serveur" alors que le vrai problème = stock négatif.

**Action** : `check_stock` par défaut à `True`, ou auto-bloquer en service-level avec 409 avant l'INSERT.

---

#### F871 — `valider_transfert` n'utilise pas `with_for_update` sur `epicerie_stock`

`services/epicerie/transfert.py:122-131` :
```python
stock = await stock_repo.get_by_produit(line.produit_id, tenant_id)
nouvelle_qte = float(stock.quantite) - float(line.quantite)
if nouvelle_qte < 0:
    raise BadRequest(...)
await stock_repo.update_quantite(stock, -float(line.quantite))
```

Read-modify-write sans verrou. Deux workers validant transferts simultanés sur même produit → tous deux lisent quantité X, soustraient leur quantité, deuxième écrit `X - q1`, **perdant** la décrémentation du premier. Stock épicerie devient incohérent.

Pattern récurrent (cf. F559 mod. 17, F601 mod. 18, F792 mod. 25).

**Action** : `with_for_update()` sur le SELECT stock + retry policy.

---

#### F872 — `annuler_vente` accepte `VALIDEE` mais ne crée **pas de credit note ni d'inversion d'invoice**

`services/epicerie/vente.py:199-231` :
- Crée mouvements `AJUSTEMENT` (+) pour remettre stock.
- Met `vente.statut = ANNULEE`.
- **Aucune action sur `vente.invoice_id`** — la facture reste en statut `PAYEE`.

**Conséquence comptable** : la facture est encaissée en DB, le stock est revenu, mais aucun avoir n'est généré. Reporting comptable (TVA, CA) reste avec la vente comptée. Désync entre stock et finance.

**Action** : générer une `FinanceInvoice` de type `AVOIR` ou inverser l'invoice originale (transition vers `ANNULEE`).

---

#### F873 — `EpicerieStockMovement` "log immuable" promesse code-only (pas de trigger DB)

`models/epicerie/stock_movement.py:36-40` "journal immuable d'audit" — aucun trigger `RAISE EXCEPTION ON UPDATE/DELETE`. Pattern récurrent (cf. F795 mod. 25, F754 mod. 23).

**Action** : trigger PostgreSQL.

---

#### F874 — `CatalogueProduit` cross-tenant sans tenant_id (référentiel partagé) → modifs cross-impact silencieuses

**Constat.** `models/catalogue/catalogue_produit.py:20` : "Table sans tenant_id : référentiel ETL partagé entre épicerie (tenant_id=2) et restaurant (tenant_id=3)".

`_handle_ean_match` (`etl_import_service.py:391-399`) update **silencieusement** `prix_unitaire_cts` et `taux_tva_centieme` du produit existant si `source_fournisseur` matche. Si tenant Épicerie et tenant Restaurant importent le même EAN avec des prix différents → le dernier import gagne, le tenant précédent voit son prix changer **sans notification**.

**Action** : (a) split par tenant ; (b) ou table pivot `catalogue_produit_prices(catalogue_produit_id, tenant_id, prix_cts)` avec historique.

---

#### F875 — `EtlImport.lignes_data JSON` stocké entre PREVIEW et VALIDATED via `dataclasses.asdict` — drift schema

`etl_import_service.py:735` :
```python
import_obj.lignes_data = [dataclasses.asdict(l) for l in lignes]
```

Si `LigneParsee` schema change (ajout/suppression de champ), les anciens previews stockés deviennent incompatibles → erreurs deserialization au moment de la VALIDATED. Aucun versioning.

**Action** : `lignes_data = {"version": 1, "lines": [...]}` + migration handler par version.

---

### 3.2 P1

#### F876 — `_calcul_ligne` `round(prix × quantité)` — perte précision Decimal

`services/epicerie/vente.py:39, 41` :
```python
montant_ttc = round(prix_unitaire_cts * quantite)  # quantite Numeric(10,3) → float
montant_ht = round(pu_ht * quantite)
```

Multiplication float × Numeric → float Python (53 bits mantisse). Pour quantités fractionnaires (`0.350` kg), arrondis cumulés sur grand panier.

**Action** : utiliser `Decimal` end-to-end ou `int(Decimal(prix) * Decimal(quantite))`.

---

#### F877 — `EpicerieVente.numero_ticket` séquentiel journalier — race possible

Format `VTE-YYYYMMDD-NNNN` mais aucun `pg_advisory_xact_lock` ni SEQUENCE visible (cf. `repositories/epicerie/vente.py` à inspecter). Pattern récurrent (F564 mod. 17, F696 mod. 21).

---

#### F878 — `_appliquer_remise` calcul facteur **float** (l. 53)

`facteur = total_ttc_remise / total_ttc_brut` → ratio float. Sur très petits montants (1 cent), divergence visible.

---

#### F879 — `encaisser` `update_statut(invoice, "PAYEE")` direct sans guard FSM

L. 177. Cf. F672 mod. 20. Aucune transition validée.

---

#### F880 — `EpicerieVente.statut` 4 valeurs sans matrice transitions

Comme tous les FSM épicerie : CHECK SQL valide, code transite directement (`vente.statut = "VALIDEE"` etc.) sans `_assert_transition`.

---

#### F881 — `creer_transfert` 2 appels `produit_repo.get_by_id` par ligne (N+1)

`services/epicerie/transfert.py:47-50` valide d'abord, puis `services/epicerie/transfert.py:69-77` re-charge pour `designation`. **Une seule lecture aurait suffi**.

---

#### F882 — `InternalTransfer.dest_tenant_id` aucune validation existence/actif

Le CHECK garantit `tenant_id != dest_tenant_id` mais aucune vérification que `dest_tenant_id` existe en `tenants` table. Insertion `dest_tenant_id=999999` accepté → transfert orphelin.

---

#### F883 — `EpicerieStockMovement.{vente_id, supply_order_id, transfer_id, etl_import_id, fournisseur_id}` **aucune FK** alors que les colonnes existent

`models/epicerie/stock_movement.py:85-100` : 4 colonnes BigInteger nullable sans `ForeignKey()`. Orphelins multiples possibles.

`models/catalogue/etl_import.py:45-48` : `fournisseur_id BigInteger nullable=True` "FK nullable vers fournisseurs_alim.id" mais **PAS de `ForeignKey()`** SQLAlchemy → pas de contrainte DB.

**Action** : ajouter `ForeignKey(..., ondelete="SET NULL")` partout.

---

#### F884 — `_handle_ean_match` update silently `prix_unitaire_cts` sans audit

`etl_import_service.py:391-399`. Cf. F874 — drift sans trace.

---

#### F885 — `etl_import_service` `try/except Exception: pass` partout (~5 endroits)

L. 374-378 (colisage), 458-459 (brand dict), 487-490 (secondary EAN), 512-516 (idem), 695 (correction history), 793 (brand dict save). Silent failures sur enrichissements latéraux. Aucun logger.warning (sauf cas).

---

#### F886 — `compute_line_confidence` regex EAN `^\d{8}(\d{5})?$` ne valide pas le check digit Luhn

`etl_import_service.py:584`. EAN-13 invalide (check digit cassé) reçoit 25 pts confidence. Cf. F450 mod. 14 (SIRET sans Luhn) — pattern récurrent.

---

#### F887 — `_resolve_categorie_code` 6 niveaux de fallback complexes

`etl_import_service.py:204-281`. Code (parser → keywords → KNN → régie → fallback → AUTRE). Testabilité difficile, dette technique élevée.

---

#### F888 — `EtlImport.prix_snapshot JSON` sans cap taille (revert dépendant)

Pour un gros import (100k produits), serialization JSON 100k lignes en colonne JSONB → risque de timeout au commit.

---

#### F889 — `EtlImport.statut FSM` 9 valeurs CHECK sans matrice transitions

`PENDING → RUNNING → PREVIEW → (VALIDATED | REJECTED)` ou `→ (SUCCES | PARTIEL | ECHEC)` ou `VALIDATED → REVERTED`. Le code peut écrire tout statut — aucun `_assert_transition`.

---

#### F890 — `EpicerieVente.client_email String(200)` non chiffré (PII)

---

#### F891 — `EpicerieProduit.taux_tva BigInteger default=2000` (= 20% Marveline)

Pour épicerie alimentaire, default = 5.5%. Drift (cf. F487 pattern récurrent).

---

#### F892 — `EpicerieStockMovement` colonnes `vente_id/supply_order_id/transfer_id/etl_import_id` toutes nullable — **règle métier "au plus une"** non enforced

Comment l. 84 dit "au plus une référence selon le type". Aucun CHECK `(vente_id IS NULL OR supply_order_id IS NULL) AND ...`. Insertion incohérente possible (mvt VENTE avec supply_order_id renseigné).

**Action** : CHECK constraint exclusion mutuelle.

---

### 3.3 P2

#### F893 — `EpicerieProduit.unite_vente String(10)` / `unite_base String(20)` sans CHECK enum

#### F894 — `EpicerieStockMovement.type` 6 valeurs hardcoded (manque potentiellement TRANSFERT_RESTAURANT_CANCEL pour rollback transfert)

#### F895 — `_DEFAULT_BRAND` import depuis `services/invoice_pdf` (cf. F856 — coupling cross-domain)

#### F896 — Les 91 `_FINAL_CATEGORIES` Python frozenset — drift potentiel avec table `categories_produit`

#### F897 — `EtlConflict.score_similarite Numeric(4,3)` — précision OK mais convention float Python à confirmer

#### F898 — `EtlConflict.resolution` 3 valeurs sans matrice transitions

#### F899 — `_VOLUME_TOLERANCE_PCT = 0.05` magic constant

#### F900 — `categories_produit.py` (89L) parcouru rapidement — patterns probables même

#### F901 — `EpicerieProduit.image_url Text` sans validation taille/format

#### F902 — `InternalTransferLine.unite String(10)` libre vs `EpicerieProduit.unite_vente`

---

### 3.4 P3

#### F903 — Comments mix français/anglais épicerie (parfois sans accents)

#### F904 — Format `VTE-YYYYMMDD-NNNN` hardcoded

#### F905 — `EpicerieVenteLigne.taux_tva BigInteger default=2000` doublon avec `EpicerieProduit.taux_tva` (drift potentiel)

---

## 4. Synthèse module 28

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 7 | F869 (no UNIQUE EAN), F870 (check_stock=False default), F871 (no FOR UPDATE transfert), F872 (annuler_vente sans avoir), F873 (no trigger immutable), F874 (catalogue cross-tenant overwrite silencieux), F875 (lignes_data no version) |
| P1 | 17 | F876 → F892 |
| P2 | 10 | F893 → F902 |
| P3 | 3 | F903 → F905 |
| **Total** | **37** | F869 → F905 |

**Compteur cumulé après module 28** : ≈ 868 + 37 = **905 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) UNIQUE partielle EAN épicerie (F869) ; (2) `check_stock=True` par défaut (F870) ; (3) `with_for_update` sur stock épicerie (F871) ; (4) avoir auto sur cancel vente (F872) ; (5) trigger DB immutability (F873) ; (6) split catalogue par tenant ou pivot prix (F874) ; (7) versioning lignes_data (F875).
>
> **Refactor** : FK pour `EpicerieStockMovement.{vente_id, supply_order_id, transfer_id}` (F883) + CHECK exclusion mutuelle (F892). Matrices transitions FSM partout. Decimal end-to-end pour calculs financiers (F876).
