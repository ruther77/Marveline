# Phase 1 — Alignment Frontend/Backend (version usage-first)

Date: 2026-03-05
Contexte: SaaS multi-tenant de gestion locative (matériel événementiel)
Périmètre analysé: `frontend/src` + `app/api`

## Decisions ratifiees (2026-03-05)
1. Taxonomie endpoints adoptee: `product-required` / `admin/internal` / `platform/system`.
2. Source de verite identite: lecture canonique via `auth/me` (edition profil a clarifier sur `users/me`).
3. Regle frontend imposee: `hooks query-first`, pas d'appel `api.*` direct dans les pages.
4. Priorite livraison P0: transitions Reservation + Facturation + Vente + Incidents.
5. Gate qualite impose avant merge: contract tests + hooks tests + E2E parcours critiques.

Reference taxonomie v1: `docs/ENDPOINT_TAXONOMY_V1.md` et `docs/endpoint_taxonomy_v1.csv`.
Reference regle frontend v1: `docs/FRONTEND_API_ACCESS_RULE_V1.md`.

## Execution status (G0)
- `G0-01` Taxonomie endpoint: **Done** (V1.0 locked).
- `G0-02` Regle architecture frontend + checker: **Done** (`npm run check:api-access`).
- `G0-03` Matrice parcours + etats canoniques: **Done** (`docs/CANONICAL_STATE_MACHINES_V1.md`).
- `G0-04` Gate CI coverage contractuelle: **In Progress** (allowlist delta gate livré et verrouillé à 0, matrice contractuelle complète restante).
- `G0-05` Lint rule bloquante (apres burn-down allowlist): **Done** (`no-restricted-imports` sur runtime FE, exceptions `src/api/**`, `src/api/queries/**`, tests) + budget warnings CI (`lint:warnings:budget`).
- `G0-05` Burn-down progress (2026-03-05): **Done** (`no-restricted-syntax` warnings reduced from 1603 to 0, `npm run lint:strict` green).

## Hook coverage status (H1)
- `H1-01` Hooks critiques manquants (`devis`, `reservations`, `invoices`, `ventes`): **Done** (couche `frontend/src/api/*` + `frontend/src/api/queries/*` completee).
- `H1-02` Branchage pages critiques U4/U5/U7/U10 vers hooks canoniques: **Done** (`ReservationDetailsModal`, `InvoiceAuditPage`, `InvoiceDetailModal`, `Devis*`, `VentesListPage`).
- `H2-01` Coverage complémentaire par module: **Done (slice 1)** — hooks/API ajoutés pour `audit user/entity`, `inventory today`, `orders detail`, `products low-stock` (registre: `docs/PHASE2_HOOK_BACKEND_GAP_REGISTER.md`).
- `H2-02` Coverage closure + taxonomy sync: **Done** — taxonomy V1 sync sur transitions devis avancées + rapport AST coverage (`npm run report:endpoint-coverage`) montrant `product_missing_in_frontend=0`, `api_functions_without_hook=0`.
- `H2-03` Wiring produit des hooks H2: **Done** — hooks branchés sur pages cibles (`commandes`, `inventory`, `devis`) avec transitions backend explicites (`negotiation/start`, `version-pending`).
- `H2-04` CI observabilité coverage: **Done** — ajout en CI frontend d’un reporting non bloquant `report-endpoint-coverage` + upload artefact JSON.
- `H2-05` Gouvernance scanner coverage: **Done** — exception système JWKS explicitement gérée dans le reporter (`system_exceptions`), `taxonomy_orphans_count=0`.
- `H2-06` Alignement contrats FE/BE statuts+signatures ventes: **Done** — `sale_date` remplacé par `created_at` côté FE, signature backend `list_ventes` alignée sur `date_from/date_to/search`, gate `check-critical-contracts` étendue à `ERR-020`.

## Product-required backlog status
- `PR-01` Task list executable par sprint/module (scope `product-required`): **Done** (`docs/PHASE1_PRODUCT_REQUIRED_TASKLIST.md`).

## Snapshot autoritatif actuel (2026-03-05)
- Backend endpoints uniques détectés: **329**
- Endpoints `product-required` (taxonomy): **314**
- Surface API frontend unique détectée: **314**
- `product-required` sans surface frontend: **0**
- Fonctions API frontend sans hook query: **0**
- Fichiers runtime frontend avec appels API directs hors couche query: **0** (budget allowlist verrouillé à `0`)
- CI:
  - gate bloquant: `check:api-access`, `check:critical-contracts`, `lint:strict`
  - reporting non bloquant: `report:endpoint-coverage` + artefact JSON

## Open items (source de vérité)
Aucun item bloquant restant sur le périmètre Phase 1 (`ERR-016/018/019/020/025` soldés).

Note: les sections détaillées ci-dessous servent de **baseline historique** et de trace de décision.

## 0) Décision de méthode (avant de coder)
Nous ne lançons pas de développement feature tant que les 4 points suivants ne sont pas cadrés:
1. Classifier tous les endpoints en `product-required`, `admin/internal`, `platform/system`.
2. Stabiliser une architecture d'accès API unique côté frontend (`hooks query-first`, exceptions documentées).
3. Définir les parcours utilisateur critiques (E2E) et leurs critères d'acceptation métier.
4. Aligner les états métier canoniques (devis, réservation, vente, facture, stock) entre UI/API.

## 1) État des lieux chiffré (baseline historique pré-hardening)
- Endpoints backend détectés: **328**
- Patterns d'appels frontend détectés: **276**
- Routes frontend (`createFileRoute`) détectées: **151**
- Modules API frontend: **32**
- Endpoints backend sans couverture frontend directe: **52**
- Endpoints frontend sans backend: **0**
- Fichiers frontend avec appels API hors couche hooks query: **43**

Lecture senior:
- Le problème principal n'est pas "il manque X endpoints", mais "la valeur métier n'est pas pilotée par parcours".
- Sans backlog orienté usage, on produit des écrans incomplets et des transitions d'état incohérentes.

## 2) Cartographie des parcours métier (source de vérité backlog)

### U1 — Authentification, session, sécurité compte
Objectif usage: un utilisateur se connecte, gère son MFA, change son mot de passe, révoque ses sessions.
- Couverture actuelle: bonne mais fragmentée (`auth`, `mfa`, `sessions`, `profile/security`).
- Gaps: cohérence `auth/me` vs `users/me`, logout device granulaire non exposé partout.

### U2 — Construire le catalogue louable
Objectif usage: créer/maintenir produits, variantes, médias, catégories, bundles, collections, disponibilité.
- Couverture actuelle: large.
- Gaps: low-stock actionnable, certains flux encore en appels API directs hors hooks.

### U3 — Tarification exploitable en exploitation
Objectif usage: définir règles de pricing et simuler rapidement pour devis/vente.
- Couverture actuelle: correcte.
- Gaps: usage de `features/check` non systématique pour rollout conditionnel.

### U4 — Cycle Devis complet (création -> négociation -> signature -> conversion)
Objectif usage: produire un devis fiable et convertible sans rupture d'information.
- Couverture actuelle: élevée.
- Gaps critiques: lecture explicite `coverage/modules/phases` incomplète dans certains parcours, action `renew` non industrialisée.

### U5 — Cycle Réservation / Événement (préparation -> exécution)
Objectif usage: transformer devis en réservation, préparer lignes, risques, dépôts, pré-check, assignation.
- Couverture actuelle: partielle.
- Gaps critiques: `assign`, `full`, `complete`, `remind-deposit`.

### U6 — Opérations terrain (départ/retour/scan/incident)
Objectif usage: opérer départ-retour en condition réelle sans dette de stock/facturation.
- Couverture actuelle: bonne.
- Gaps: consolidation événement/incident (`evenements/{id}/incidents`) et liaison forte avec clôture litige.

### U7 — Facturation / encaissement / relances
Objectif usage: créer facture, encaisser, rapprocher, relancer, gérer avoirs/TVA/exports.
- Couverture actuelle: large mais dispersée.
- Gaps critiques: `invoices/{id}/full`, `invoices/{id}/audit`, `invoices/{id}/remind`, `invoices/damage`.

### U8 — Stock et mouvements
Objectif usage: maintenir stock juste (inventaire, mouvements, ajustements, retours, réassort).
- Couverture actuelle: bonne.
- Gaps: endpoints agenda/statistics/today à valider dynamiquement dans couverture CI (faux positifs statiques possibles).

### U9 — CRM client (RFM, historique, relances)
Objectif usage: segmenter et réactiver les clients avec relances traçables.
- Couverture actuelle: bonne.
- Gaps: industrialisation import clients et campagnes RFM avec retours opérables.

### U10 — Vente directe
Objectif usage: vendre hors réservation avec paiements et statut fiable.
- Couverture actuelle: partielle.
- Gaps critiques: `ventes/overdue`, `ventes/{id}/payments`, `PATCH /ventes/{id}`.

### U11 — Approvisionnement fournisseur
Objectif usage: commander, recevoir, ajuster stock fournisseur.
- Couverture actuelle: bonne.
- Gaps: faible.

### U12 — Administration & gouvernance multi-tenant
Objectif usage: piloter utilisateurs, clés API, flags, audit, settings, VPN, sessions.
- Couverture actuelle: partielle côté super-admin.
- Gaps: endpoints de provisioning et sessions multi-tenant à classifier (scope produit vs internal ops).

## 3) Registre d’écarts qui bloquent le delivery

### A) Architecture/UI
- **A1 (High)**: 43 fichiers en appels API directs hors hooks query. **Status: Closed** (résiduel runtime = 0).
- **A2 (High)**: pas de contrat explicite "un parcours = une API surface minimale". **Status: Closed** (`check-critical-contracts` en CI).
- **A3 (Medium)**: duplication `events` / `evenements` augmente le coût cognitif et les risques de divergence. **Status: Closed** (canonicalisation routes).

### B) Métier
- **B1 (High)**: transitions réservation non totalement opérables (`assign`, `complete`, `remind-deposit`, `full`). **Status: Closed**
- **B2 (High)**: transitions facture incomplètes (`full`, `audit`, `remind`, `damage`). **Status: Closed**
- **B3 (High)**: vente directe incomplète (`overdue`, `payments`, `PATCH`). **Status: Closed** (revalidation overdue finalisée, `ERR-019` clôturé)
- **B4 (Medium)**: devis avancé (`coverage/modules/phases/renew`) non consolidé en parcours unique. **Status: Closed** (transitions explicites revalidées sur `ERR-018`)

### C) Plateforme
- **C1 (Medium)**: mélange endpoints système/admin avec endpoints produit dans la même vue de gap. **Status: Closed** (exception JWKS traitée explicitement dans le scanner coverage)
- **C2 (Medium)**: absence de garde CI stricte sur `backend routes -> frontend api -> hooks -> pages`. **Status: Closed**

## 4) Task list complète orientée usage (priorisée)
Référence: cette liste est la baseline historique initiale. Le backlog exécutable courant est maintenu dans `docs/PHASE1_PRODUCT_REQUIRED_TASKLIST.md`.

Format: `ID | Priorité | Usage | Livrable | Dépendances`

### Bloc G0 — Pré-requis de gouvernance (obligatoire avant feature)
1. `G0-01 | P0 | Tous | Taxonomie endpoint (product/admin/system) versionnée | -`
2. `G0-02 | P0 | Tous | Règle d'architecture frontend: hooks query-first + exceptions listées | G0-01`
3. `G0-03 | P0 | Tous | Matrice de parcours (U1..U12) avec états métier canoniques | G0-01`
4. `G0-04 | P0 | Tous | CI coverage contractuelle (routes backend vs appels frontend vs hooks) | G0-02`
5. `G0-05 | P0 | Tous | Lint rule interdisant `api.*` hors dossiers autorisés | G0-02`

### Bloc U5/U6/U7/U10 — Valeur métier critique (go-live integrity)
6. `RZ-01 | P0 | U5 | Exposer et intégrer `PATCH /reservations/{id}/assign` (UI + mutations + tests) | G0-03`
7. `RZ-02 | P0 | U5 | Exposer et intégrer `POST /reservations/{id}/complete` | RZ-01`
8. `RZ-03 | P0 | U5 | Exposer et intégrer `POST /reservations/{id}/remind-deposit` | RZ-01`
9. `RZ-04 | P0 | U5 | Intégrer `GET /reservations/{id}/full` dans vues d'orchestration | RZ-01`
10. `OP-01 | P0 | U6 | Unifier incident workflow: `evenements/{id}/incidents` + clôture litige | RZ-04`
11. `INV-01 | P0 | U7 | Intégrer `GET /invoices/{id}/full` | G0-03`
12. `INV-02 | P0 | U7 | Intégrer `GET /invoices/{id}/audit` + timeline exploitable | INV-01`
13. `INV-03 | P0 | U7 | Intégrer `POST /invoices/{id}/remind` (UX opérateur + feedback) | INV-01`
14. `INV-04 | P0 | U7 | Intégrer `POST /invoices/damage` dans chaîne retour/incident | OP-01`
15. `VE-01 | P0 | U10 | Intégrer `GET /ventes/overdue` | G0-03`
16. `VE-02 | P0 | U10 | Intégrer `GET /ventes/{id}/payments` | VE-01`
17. `VE-03 | P0 | U10 | Intégrer `PATCH /ventes/{id}` + règles de transition | VE-02`

### Bloc U4 — Devis fiable et convertible
18. `DV-01 | P1 | U4 | Intégrer explicitement `GET /devis/{id}/coverage` | G0-03`
19. `DV-02 | P1 | U4 | Intégrer explicitement `GET /devis/{id}/modules` | DV-01`
20. `DV-03 | P1 | U4 | Intégrer explicitement `GET /devis/{id}/phases` | DV-01`
21. `DV-04 | P1 | U4 | Exposer `POST /devis/{id}/renew` avec règle métier claire | DV-01`
22. `DV-05 | P1 | U4/U5 | Contrat de conversion Devis->Réservation (invariants + tests E2E) | DV-01,RZ-01`

### Bloc U1/U12 — Identité, sécurité, admin
23. `ID-01 | P1 | U1 | Normaliser profil utilisateur (`auth/me` vs `users/me`) | G0-03`
24. `ID-02 | P1 | U1 | Exposer `POST /auth/logout/device/{device_id}` dans UX sessions | ID-01`
25. `ID-03 | P1 | U1 | Exposer `POST /mfa/stepup/verify` pour actions sensibles | ID-01`
26. `AD-01 | P1 | U12 | Exposer `POST /users/{id}/unlock` dans admin users | G0-03`
27. `AD-02 | P1 | U12 | Classer provisioning (`/admin/provision*`) comme internal ops ou produit | G0-01`
28. `AD-03 | P1 | U12 | Clarifier coverage sessions multi-tenant admin (`/admin/tenants/*`) | AD-02`

### Bloc U2/U3/U8/U9/U11 — Complétude opérationnelle
29. `CAT-01 | P1 | U2 | Intégrer `GET /products/low-stock` dans pilotage catalogue/stock | G0-03`
30. `CRM-01 | P1 | U9 | Intégrer `POST /customers/import` avec reporting d'erreurs opérable | G0-03`
31. `ORD-01 | P1 | U11/U5/U10 | Intégrer `GET /orders/{order_type}/{order_id}` pour vue unifiée commande | G0-03`
32. `FLT-01 | P2 | U3 | Exploiter `GET /features/check/{flag_name}` dans gating UI/rollout | AD-02`
33. `STK-01 | P2 | U8 | Vérifier dynamiquement coverage endpoints agenda/statistics/today (anti faux positifs) | G0-04`

### Bloc T — Dette technique transverse
34. `T-01 | P0 | Tous | Réduire de 43 -> 0 les fichiers API directs hors hooks (par lots usage) | G0-02`
35. `T-02 | P1 | Tous | Standardiser invalidation cache par domaine (keys + conventions) | T-01`
36. `T-03 | P1 | Tous | Harmoniser nomenclature `events` vs `evenements` (routing + API docs) | G0-03`
37. `T-04 | P2 | Tous | Instrumenter analytics parcours (drop-off par étape métier) | G0-03`

## 5) Séquencement recommandé (delivery plan)

### Sprint A (stabilisation)
- G0-01 à G0-05 + T-01 (minimum par domaines critiques).

### Sprint B (flux argent + exécution)
- RZ-01..RZ-04, OP-01, INV-01..INV-04, VE-01..VE-03.

### Sprint C (conversion commerciale)
- DV-01..DV-05 + ID-01..ID-03.

### Sprint D (complétude + hardening)
- AD-01..AD-03, CAT-01, CRM-01, ORD-01, FLT-01, STK-01, T-02..T-04.

## 6) Definition of Done (DoD) imposée par usage
Une task usage est "Done" uniquement si:
1. Endpoint/API/hook/page connectés de bout en bout.
2. États métier validés (transitions autorisées/interdites).
3. Tests: unit + integration API + E2E parcours critique.
4. Multi-tenant/rbac validés (pas de régression isolement).
5. Observabilité: logs auditables + métriques de succès/erreur.

## 7) Décision gate pour démarrage coding feature
On démarre seulement après validation explicite des items `G0-01..G0-05`.
Sans ce gate, le risque principal reste: livrer des écrans qui n'alignent pas les transitions métier critiques.

## 8) Artefacts
- Audit JSON brut: `/tmp/phase1_alignment.json`
- Registre erreurs détaillé: `docs/PHASE1_ERROR_REGISTER.md`
- Taxonomie endpoints V1.0: `docs/ENDPOINT_TAXONOMY_V1.md`, `docs/endpoint_taxonomy_v1.csv`
- Règle accès API frontend V1.0: `docs/FRONTEND_API_ACCESS_RULE_V1.md`
- Machines d'etats canoniques V1.0: `docs/CANONICAL_STATE_MACHINES_V1.md`
- Task list exécutable `product-required`: `docs/PHASE1_PRODUCT_REQUIRED_TASKLIST.md`
- Checker de conformité: `frontend/scripts/check-api-access.mjs`
- Budget/allowlist gate (état courant: 0 dette active): `frontend/config/api-access-allowlist.json`
