# Phase 2 — Hook/Backend Gap Register

Date: 2026-03-05  
Scope: `product-required` (taxonomy V1), couverture `backend -> frontend api -> query hooks`

## 1) Snapshot chiffré (après correctifs)
- Backend endpoints uniques détectés: **329**
- Endpoints `product-required` (taxonomy): **314**
- Surface API frontend unique détectée: **314**
- Endpoints backend `product-required` sans surface frontend: **0**
- Fonctions API frontend sans hook query référencé: **0**

## 2) Correctifs livrés dans ce lot
### COV-001 — Audit ciblé
- Ajout API frontend:
  - `GET /audit/user/{user_id}`
  - `GET /audit/entity/{entity_type}/{entity_id}`
- Ajout hooks:
  - `useUserAuditLogs`
  - `useEntityAuditLogs` (route dédiée backend, compat avec ancien paramètre `limit`)

### COV-002 — Inventory agenda “today”
- Ajout API frontend:
  - `GET /inventory-movements/today`
- Ajout hook:
  - `useTodayMovementsAgenda`

### COV-003 — Orders detail unifié
- Ajout API frontend:
  - `GET /orders/{order_type}/{order_id}`
- Ajouts type + hook:
  - `OrderDetail`, `OrderLineItem`
  - `useOrderDetail`

### COV-004 — Produits low-stock
- Ajout API frontend:
  - `GET /products/low-stock`
- Ajout hook:
  - `useLowStockProducts`

### COV-005 — Devis transitions avancées
- Ajout API frontend:
  - `POST /devis/{devis_id}/negotiation/start`
  - `POST /devis/{devis_id}/version-pending`
- Ajout hooks:
  - `useDevisMutations().startNegotiation`
  - `useDevisMutations().markVersionPending`

### COV-006 — Analyseur coverage AST durci
- Nouveau script:
  - `frontend/scripts/report-endpoint-coverage.mjs`
  - `npm run report:endpoint-coverage`
- Effet: réduction du bruit analytique sur paths dynamiques, sortie coverage exploitable (`backend -> frontend api -> hooks`).

### COV-007 — Wiring produit des hooks H2
- Hooks branchés en UI:
  - `useLowStockProducts`: `InventoryPage` (compteur low-stock + liste d'alertes) et `StockAlertPage` (contexte endpoint dédié).
  - `useTodayMovementsAgenda`: `InventoryPage` (bloc "Mouvements du jour").
  - `useOrderDetail`: `CommandesListPage` (panneau d'aperçu commande unifiée).
  - transitions devis avancées:
    - `startNegotiation` branché dans `DevisDetailPage` et `DevisIdLayout` (ouverture explicite côté backend).
    - `markVersionPending` branché dans `DevisDetailPage`, `DevisIdLayout` et `DevisChangeRequestPage` (passage explicite en révision après acceptation CR).

### COV-008 — Gouvernance scanner (exception système explicite)
- Script coverage mis à jour:
  - `frontend/scripts/report-endpoint-coverage.mjs`
- Règle:
  - `GET /.well-known/jwks.json` est traité comme exception système explicite (`system_exceptions`) et retiré de `taxonomy_orphans`.
- Résultat:
  - `system_exceptions_count=1`
  - `taxonomy_orphans_count=0`

### COV-009 — Contrat FE/BE statuts + signatures ventes
- Alignements livrés:
  - FE `ventes`: remplacement `sale_date` par `created_at` (types + pages `VentesList`/`VenteDetail`).
  - FE create flow: suppression du champ `Date de vente` non supporté backend.
  - Backend `GET /ventes`: support explicite `date_from`, `date_to`, `search` (endpoint + service + repository).
  - Gate CI: `check-critical-contracts` étendu à `ERR-020`.

## 3) Écarts/erreurs répertoriés (trace de clôture)
### GAP-ERR-001 (S3) — Orphelin taxonomy attendu hors `app/api/v1/endpoints` — Closed
- Symptôme: `GET /.well-known/jwks.json` apparaît comme orphelin dans le rapport coverage.
- Cause: endpoint défini hors répertoire scanné (`app/api/jwks.py`), comportement attendu.
- Impact: aucun sur le produit.
- Action appliquée: exception système explicite dans le scanner (champ `system_exceptions`).

## 3bis) Décision actée (2026-03-05)
- Décision: **conserver `GET /.well-known/jwks.json` hors périmètre `product-required` et l’exclure explicitement du reporting "taxonomy_orphans".**
- Rationale:
  - endpoint de plateforme (JWKS), non consommé par l’UI produit;
  - présence attendue hors `app/api/v1/endpoints`;
  - bruit analytique inutile si maintenu comme orphelin.
- Effet attendu sur le rapport:
  - `taxonomy_orphans_count` passe de `1` à `0` (pour ce cas).

## 4) Task list priorisée (usage-first)
1. `P1` Wiring produit: **Done** (COV-007).
2. `P1` CI observabilité coverage: **Done** — workflow CI frontend enrichi avec step non bloquant `report-endpoint-coverage` + upload artefact `endpoint-coverage-report` (`.github/workflows/ci.yml`).
3. `P2` Gouvernance scanner: **Done** (`TK-COV-SCANNER-001`, COV-008).

## 5) Validation technique
- `npm run lint:strict` ✅ (0 warning / 0 error)
- `npm run check:api-access` ✅ (allowlist active=0)
- `npm run check:critical-contracts` ✅ (inclut ERR-020)
- `npm run build` ✅
- `npm run report:endpoint-coverage` ✅ (`product_missing_in_frontend_count=0`, `api_functions_without_hook_count=0`, `system_exceptions_count=1`, `taxonomy_orphans_count=0`)
