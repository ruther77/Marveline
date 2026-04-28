# ARCHITECTURE_ANALYSIS — Édition granulaire post-validation ETL (Option B)

**Date** : 2026-04-11
**Contexte** : UX ETL post-validation cul-de-sac — seul `revert` existe (binaire, destructif).
**Objectif** : permettre la correction granulaire d'attributs de ligne et de métadonnées facture après `VALIDATED`, avec cascades automatiques stock/facture/catalogue et audit.

---

## 1. Décisions verrouillées

| # | Point | Décision |
|---|---|---|
| 1 | Champs éditables P1 | `quantite`, `prix_unitaire_cts`, `taux_tva_centieme` |
| 1b | Champs éditables P2 | + `marque`, `categorie_code` |
| 1c | Champs INTERDITS | `ean`, `designation` (reparenting produit ingérable) |
| 2 | Quantité → 0 | Laissée à 0, pas de delete (delete = revert individuel, hors scope) |
| 3 | Concurrence | Verrou optimiste via header `If-Match: <etl_imports.updated_at ISO>` |
| 4 | Métadonnées facture | Endpoint PATCH distinct `PATCH /imports/{id}/invoice-meta` (en P2) |
| 5 | Audit | `audit_logs` row par mutation avec diff `{field, old, new}` |
| 6 | Garde facture payée/transférée | **Différenciée** : bloque si modif financière (qte/prix/tva), autorise si modif non-financière (marque/cat) |
| 7 | RBAC | `Scope.SETTINGS_WRITE` (même niveau que validate) |
| 8 | Statut `REVERTED` | Édition interdite (409) quel que soit le champ |

## 2. Cascades par champ

### 2.1 `quantite: float` (delta = new − old)
1. Ligne `etl_imports.lignes_data[idx]` → update champ + recalcul `montant_ht_cts` / `montant_ttc_cts`
2. Totaux EtlImport : `montant_ht_total`, `montant_ttc_total`, `ecart_reconciliation`
3. **Stock** : créer mouvement `AJUSTEMENT` delta (positif ou négatif), `epicerie_stock.quantite += delta`
4. **Facture** `finance_invoices_achat` (via `etl_import_id`) : recalcul `montant_ht`, `montant_tva`, `montant_ttc`
5. **Gate** : facture statut `PAYEE`/`TRANSFEREE` → 409

### 2.2 `prix_unitaire_cts: int`
1. Ligne → recalcul HT/TTC (identique à 2.1 étapes 1-2)
2. **Stock** : pas de mouvement (la quantité ne change pas)
3. **Facture** : recalcul montants (comme 2.1)
4. **Prix achat produit** `epicerie_produits.prix_achat_cts` → mis à jour (dernier prix d'achat gagne)
5. **Prix de vente** : recalcul via `epicerie_marges_categories` (même formule que `reception_etl.py:305-340`)
6. **Prix historique** `epicerie_prix_historique` : nouvelle entrée (source `etl_correction`)
7. **Gate** : facture `PAYEE`/`TRANSFEREE` → 409

### 2.3 `taux_tva_centieme: int`
1. Ligne → recalcul TTC uniquement (HT inchangé)
2. Totaux facture → recalcul `montant_tva`, `montant_ttc`
3. **Produit epicerie** `epicerie_produits.taux_tva` → update
4. **Prix de vente** recalculé (TTC dépend du taux TVA)
5. **Gate** : facture `PAYEE`/`TRANSFEREE` → 409

### 2.4 `marque: str|None` (P2, non financier)
1. Ligne `lignes_data[idx].marque` → update
2. **Catalogue** `catalogue_produits.marque` → update (via EAN lookup)
3. **Épicerie** `epicerie_produits.marque` → update (même lookup)
4. **Aucun recalcul financier**, pas de mouvement
5. **Pas de gate facture** (non financier)

### 2.5 `categorie_code: str` (P2, non financier direct mais impact prix vente)
1. Ligne → update
2. Catalogue + épicerie → update champ `categorie` / `categorie_code`
3. **Prix de vente recalculé** (la marge dépend de la cat)
4. **Pas de gate facture payée** — le prix de vente change mais la facture achat reste intacte
5. Trace : `epicerie_prix_historique` nouvelle entrée si prix vente change

## 3. Contrats API

### 3.1 PATCH `/admin/etl/imports/{id}/validated-lignes` (P1)

**Auth** : `SETTINGS_WRITE`
**Pre** : `etl_imports.statut == 'VALIDATED'`, header `If-Match: <updated_at>`
**Body** :
```json
{
  "updates": [
    {
      "idx": 12,
      "quantite": 18.0,
      "prix_unitaire_cts": 1060,
      "taux_tva_centieme": 2000
    }
  ]
}
```
**Réponses** :
- `200` → `EtlImportDetail` enrichi (mêmes totaux calculés que PREVIEW)
- `409` → `{code: 'STALE', server_updated_at}` si If-Match ne matche pas
- `409` → `{code: 'INVOICE_LOCKED', invoice_statut}` si facture payée ET modif financière
- `422` → validation schema (qte < 0, etc.)

### 3.2 PATCH `/admin/etl/imports/{id}/validated-lignes` (P2 — champs non-financiers additionnels)
Même endpoint, schema étendu avec `marque`, `categorie_code`.

### 3.3 PATCH `/admin/etl/imports/{id}/invoice-meta` (P2)
Édition de `numero_facture`, `date_facture`, `vendor_code` sur un import VALIDATED.
Répercute sur `finance_invoices_achat.reference`, `date_facture`.

## 4. Contraintes transverses

- **Multi-tenant (A1)** : chaque query filtre sur `tenant_id = current_user.tenant_id`. Test anti cross-tenant obligatoire.
- **Montants** : BigInteger centimes. Aucun float sur montants.
- **Audit (A2)** : chaque ligne modifiée → `audit_logs` entry `{action: 'etl_line_edit_post_validation', entity: 'etl_import', entity_id, meta: {idx, field, old, new}}`.
- **Soft delete** : N/A (pas de delete ici).
- **Migration** : aucune (tables existantes suffisent, pas de nouveau champ).
- **Transaction** : tout en un seul `db.commit()` par appel endpoint. Rollback complet si une cascade échoue.

## 5. Découpage en phases (respect I1 : ≤3 fichiers/phase)

### Phase 1 — Backend édition financière (quantité/prix/TVA)
**Fichiers** :
1. `app/services/epicerie/reception_etl.py` → ajoute `edit_validated_ligne(db, etl_import, idx, updates, tenant_id, user_id)` avec cascades stock + facture
2. `app/api/v1/endpoints/admin/etl_imports.py` → nouvel endpoint PATCH `/imports/{id}/validated-lignes` + gate If-Match + gate invoice statut
3. `app/schemas/catalogue/etl_import.py` → `ValidatedLigneEditRequest`, `ValidatedLignesBatchEdit`

**Tests** (`tests/services/test_edit_validated_ligne.py`) :
- test nominal : qte +3 → AJUSTEMENT créé, stock delta, facture recalculée
- test delta négatif : qte −5 → ajustement négatif
- test anti cross-tenant : tenant A ne peut pas éditer l'import de tenant B → 404
- test gate facture payée : invoice PAYEE + qte → 409
- test gate reverted : statut REVERTED → 409
- test stale updated_at : If-Match obsolète → 409
- test recalcul facture : HT/TVA/TTC cohérents après batch update

### Phase 2 — Backend cascades catalogue (marque/cat) + endpoint métadonnées facture
**Fichiers** :
1. `app/services/epicerie/reception_etl.py` → étend `edit_validated_ligne` pour marque/cat + `edit_validated_invoice_meta`
2. `app/api/v1/endpoints/admin/etl_imports.py` → étend endpoint validated-lignes + ajoute `/imports/{id}/invoice-meta`
3. `app/schemas/catalogue/etl_import.py` → étend schemas

**Tests** : cascade cat → nouveau prix vente, cascade marque → catalogue/epicerie, invoice meta → finance_invoice sync

### Phase 3 — Frontend édition post-validated
**Fichiers** :
1. `frontend/apps/epicerie/src/pages/EtlImportDetailPage.tsx` → mode édition quand `statut === 'VALIDATED'` + bouton "Enregistrer les corrections" + header If-Match
2. `frontend/apps/epicerie/src/components/etl/LignesTable.tsx` / `LigneRow.tsx` → permissions inline sur VALIDATED, disable champs sensibles (ean, designation)
3. `frontend/apps/epicerie/src/api/etl_imports.ts` → `editValidatedLignes()`, `editInvoiceMeta()`

**Remarques UX (ui-ux.md)** :
- Bouton principal après validation : "Corriger une ligne" (non destructif) — **PAS** "Annuler cet import" en première place.
- Bouton "Annuler cet import" déplacé en **action secondaire** (menu kebab ou modale séparée) — réservé aux cas de vraie erreur totale.
- Feedback visuel post-edit : toast "Ligne corrigée • stock ajusté • facture recalculée".
- Skeleton sur la ligne en cours d'enregistrement (pas `Loader2` seul).

## 6. Risques & mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| Concurrence 2 éditeurs | Stock incohérent | Verrou optimiste If-Match |
| Facture déjà transférée en compta | Comptabilité faussée | Gate `INVOICE_LOCKED` 409 pour champs financiers |
| Stock négatif après ajustement | Vente impossible | Warning non bloquant + audit (c'est un état valide post-correction) |
| Cascade échouée partiellement | Données corrompues | Tout dans 1 transaction SQLAlchemy + savepoint sur recalcul prix (comme existant ligne 309) |
| Perte d'historique des corrections | Impossible d'auditer | `audit_logs` row par champ modifié |

## 7. Invariants vérifiés

- A1 (multi-tenant) ✓ via filtre + test anti cross-tenant
- A2 (audit) ✓ via `audit_logs` entry par mutation
- A3 (secrets) N/A
- A4 (auth) ✓ `SETTINGS_WRITE`
- A8 (prepare Python) ✓ `mcp__context-engine__prepare` avant chaque edit Python
- A9 (no lazy) ✓ chaque champ traité avec sa cascade complète, aucun TODO silencieux
- A10 (NOTE_BUG) ✓ pendant l'analyse, bug détecté à noter immédiatement

## 8. Definition of Done (par phase)

Chaque phase est terminée ssi :
- [ ] Code complet (aucun stub, aucun TODO)
- [ ] Tests écrits + exécutés : `Passing(n, total, file, date)` capturé verbatim
- [ ] `__init__.py` à jour si nouveau module
- [ ] Tests anti cross-tenant présents pour chaque endpoint métier
- [ ] `MEMORY.md` mis à jour (state.md + sessions.md)
- [ ] Cross-check des imports (grep des importers du fichier modifié)

---

**Validation utilisateur** : 2026-04-11 — décisions 1-8 verrouillées. Démarrage P1 en attente GO explicite.
