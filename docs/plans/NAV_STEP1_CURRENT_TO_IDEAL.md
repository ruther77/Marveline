# Step 1 — Navigation: Current State to Ideal

Date: 2026-03-06  
Scope: Frontend routes (`frontend/src/routes/_app/*`) + backend API domains (`app/api/v1/endpoints/*`)

---

## 1) Current State by Domain (Concrete)

### 1.1 Cross-domain / shell
- Front current:
  - `/dashboard`
  - `/notifications`, `/notifications/settings`
  - `/search`
  - `/more` (currently redirect-style transition page)
- Backend current:
  - `/dashboard`, `/notifications`, `/search`
- Finding:
  - Shell entries exist, but `/more` is not a real hub.

### 1.2 Planning
- Front current:
  - Canonical family already present: `/planning/*`
  - Legacy duplicate family also present: `/agenda/*`
- Backend current:
  - `/planning/*` (day/week/month/resources/today/assign)
- Finding:
  - Functional duplication (`agenda` vs `planning`) creates navigation drift.

### 1.3 Reservations vs Events (main ambiguity)
- Front current:
  - Reservation-like flows under `/events/*` (`/events/:id`, `/events/:id/lines`, `/events/new`, `/events/signature...`)
  - Incident flows also under `/events/*` (`/events/incidents`, `/events/:id/incidents`)
  - Legacy namespace `/evenements/*` still exists.
- Backend current:
  - Reservations domain: `/reservations/*`
  - Events/incident domain: `/evenements/*`
  - Operations domain: `/operations/*`
- Finding:
  - One frontend namespace (`events`) currently mixes 2 business domains.

### 1.4 Operations
- Front current:
  - `/operations/scan`
  - `/operations/departure...`
  - `/operations/return...`
- Backend current:
  - `/operations/*` (departure/return/qr/damage photo)
- Finding:
  - Domain is coherent; route shape can be normalized (segment naming only).

### 1.5 Catalogue
- Front current:
  - `/products/*` carries most catalogue features
  - `/catalogue/search`, `/catalogue/builder` exist separately
  - `/parc` used as top-level hub alias
- Backend current:
  - `/products`, `/bundles`, `/categories`, `/collections`, `/delivery-zones`, `/formulas`, `/suppliers`, `/supplier-orders`
- Finding:
  - Catalogue surface is broad but split over multiple route roots.

### 1.6 Stock / Physical inventory
- Front current:
  - `/inventory/*` (stock, movements, returns, repairs, reorder, adjustments, coverage, inventaire)
  - plus `/parc` overlap
- Backend current:
  - `/stock/*` (inventory sessions, adjustments, coverage, levels)
  - `/inventory-movements/*` (movement journal and movement items)
  - models include both `stock_item` and `inventory_movement`
- Finding:
  - This is not duplicate data; it is two subdomains:
  - `stock` = physical state and levels
  - `inventory-movements` = movement ledger over time
  - Front naming does not make this distinction clear enough.

### 1.7 Commerce (devis / ventes / commandes)
- Front current:
  - `/devis/*`
  - `/ventes/*`
  - `/commandes` unified list entry
- Backend current:
  - `/devis/*`, `/ventes/*`, `/orders/*` (aggregator)
- Finding:
  - Domain is valid; `/commandes` should be kept as the canonical aggregate hub.
  - Drill-down from `/commandes` must target canonical domains (`/devis/:id`, `/reservations/:id`, `/ventes/:id`).

### 1.8 CRM (customers)
- Front current:
  - `/customers/*` + duplicate `/clients` + top-level `/relances`
- Backend current:
  - `/customers/*`, `/relances/*`
- Finding:
  - Alias duplication should be collapsed to `/customers`.

### 1.9 Finance
- Front current:
  - `/finances/*`, `/invoices/*`, `/tresorerie`, `/tarification`
- Backend current:
  - `/invoices/*`, `/pricing/*`, dashboard-finance endpoints
- Finding:
  - Finance area is fragmented across 4 roots.

### 1.10 Admin / Profile
- Front current:
  - `/admin/*`, `/profile/*`
- Backend current:
  - `/api-keys`, `/features`, `/audit`, `/users`, `/sessions`, `/admin/settings`, etc.
- Finding:
  - Domain structure is acceptable; mostly shell/navigation consistency work.

---

## 2) Vocabulary Canonicalization (to remove ambiguity)

- `Reservation`:
  - Contract/commercial file with customer, lines, pricing, deposits, status lifecycle.
- `Evenement`:
  - Operational occurrence and incident handling (field execution context).
- `Operation`:
  - Checklist and execution actions (departure, return, scan, damage workflow).
- `Catalogue`:
  - Product master data (product/bundle/category/collection/supplier/formula definitions).
- `Stock`:
  - Physical quantities, stock items, adjustments, coverage, inventory sessions.
- `Inventory movement`:
  - Temporal ledger of stock movements (departure/return flows and movement items).

Decision:
- Keep `inventory-movements` as backend technical ledger domain.
- Expose it in frontend under the `stock` domain UX (e.g., `/stock/movements`), not as separate L1 concept.

---

## 3) Ideal Canonical Route Tree (corrected)

Note:
- Typo fixed: use `/evenements` (not `/evements`).
- `events` namespace is demoted to legacy redirects.

```text
/dashboard
/notifications
/notifications/settings
/search

/planning/today
/planning/day
/planning/week
/planning/month
/planning/resources
/planning/affectation
/planning/conflicts
/planning/event/:id

/operations
/operations/scan
/operations/departure/:reservationId
/operations/departure/:reservationId/check
/operations/departure/:reservationId/blocked
/operations/return/:reservationId
/operations/return/:reservationId/damage

/reservations
/reservations/new
/reservations/:id
/reservations/:id/edit
/reservations/:id/lines
/reservations/:id/phases
/reservations/:id/signature

/evenements
/evenements/:id

/catalogue
/catalogue/search
/catalogue/builder
/catalogue/products
/catalogue/products/new
/catalogue/products/:id
/catalogue/products/:id/editor
/catalogue/products/:id/audit
/catalogue/products/:id/availability
/catalogue/products/:id/maintenance
/catalogue/products/:id/photos
/catalogue/products/:id/states
/catalogue/products/:id/variants
/catalogue/bundles
/catalogue/bundles/:id
/catalogue/categories
/catalogue/collections
/catalogue/collections/:id
/catalogue/availability
/catalogue/media
/catalogue/import
/catalogue/tools
/catalogue/qr
/catalogue/pilotage
/catalogue/delivery-zones
/catalogue/formulas
/catalogue/suppliers
/catalogue/supplier-orders
/catalogue/comparator

/stock
/stock/items
/stock/items/:id
/stock/items/:id/edit
/stock/movements
/stock/movements/:id
/stock/returns
/stock/repairs
/stock/reorder
/stock/adjustments
/stock/coverage
/stock/inventory
/stock/damage-types
/stock/alerts/:id

/devis
/devis/new
/devis/:id
/devis/:id/edit
/devis/:id/modules
/devis/:id/phases
/devis/:id/couverture
/devis/:id/versions
/devis/:id/negotiation
/devis/:id/change-requests
/devis/:id/source

/ventes
/ventes/new
/ventes/:id
/ventes/:id/edit

/customers
/customers/:id
/customers/:id/edit
/customers/:id/history
/customers/relances
/customers/rfm

/finance
/finance/period
/finance/export
/finance/treasury
/finance/pricing

/finance/invoices
/finance/invoices/new
/finance/invoices/:id
/finance/invoices/:id/edit
/finance/invoices/:id/audit
/finance/invoices/:id/avoir
/finance/invoices/cautions
/finance/invoices/rapport-mensuel
/finance/invoices/tva-report
/finance/invoices/rapprochement

/admin
/admin/users
/admin/users/:id
/admin/sessions
/admin/api-keys
/admin/features
/admin/audit-logs
/admin/vpn
/admin/settings

/profile
/profile/security
/profile/mfa

/plus
```

---

## 3.1 L1 Navigation Constraint (max 5 tabs)

Rule:
- persistent L1 must stay at max 5 tabs.

Canonical L1:
- `/dashboard`
- `/planning/today`
- `/reservations`
- `/operations/scan`
- `/plus` (overflow hub)

Implications:
- `catalogue`, `stock`, `finance`, `customers`, `devis`, `ventes`, `admin`, `profile`, `commandes` are domain hubs/pages, not always-visible L1 tabs.
- `/commandes` stays reachable via `/plus` and contextual actions.

---

## 4) Mapping: Current -> Ideal (execution-ready)

## 4.1 Strict migration order

1. Split `events` before any broad redirect:
- `/events/incidents` -> `/evenements`
- `/events/:id/incidents` -> `/evenements/:id`
- `/evenements` -> `/evenements` (canonical keep)
- `/evenements/:id` -> `/evenements/:id` (canonical keep)

2. Then migrate reservation-like `events/*`:
- `/events` -> `/reservations`
- `/events/new` -> `/reservations/new`
- `/events/:id` -> `/reservations/:id`
- `/events/:id/edit` -> `/reservations/:id/edit`
- `/events/:id/lines` -> `/reservations/:id/lines`
- `/events/:id/phases` -> `/reservations/:id/phases`
- `/events/signature/:reservationId` -> `/reservations/:id/signature`

3. Migrate planning aliases:
- `/agenda` -> `/planning/today`
- `/agenda/mobile` -> `/planning/today?view=mobile`
- `/agenda/resources` -> `/planning/resources`
- `/agenda/affectation` -> `/planning/affectation`

4. Normalize operations path aliases:
- `/operations/departure-check/:reservationId` -> `/operations/departure/:reservationId/check`
- `/operations/departure-blocked/:reservationId` -> `/operations/departure/:reservationId/blocked`
- `/operations/return-damage/:reservationId` -> `/operations/return/:reservationId/damage`

5. Migrate catalogue surface:
- `/products` -> `/catalogue/products`
- `/products/new` -> `/catalogue/products/new`
- `/products/:id*` -> `/catalogue/products/:id*`
- `/products/bundles/*` -> `/catalogue/bundles/*`
- `/products/categories` -> `/catalogue/categories`
- `/products/collections/*` -> `/catalogue/collections/*`
- `/products/availability` -> `/catalogue/availability`
- `/products/media` -> `/catalogue/media`
- `/products/import` -> `/catalogue/import`
- `/products/tools` -> `/catalogue/tools`
- `/products/qr` -> `/catalogue/qr`
- `/products/pilotage` -> `/catalogue/pilotage`
- `/products/delivery-zones` -> `/catalogue/delivery-zones`
- `/products/formulas` -> `/catalogue/formulas`
- `/products/suppliers` -> `/catalogue/suppliers`
- `/products/supplier-orders` -> `/catalogue/supplier-orders`
- `/products/comparateur` -> `/catalogue/comparator`
- `/catalogue/search` and `/catalogue/builder` stay canonical

6. Migrate stock aliases:
- `/inventory` -> `/stock`
- `/inventory/stock` -> `/stock/items`
- `/inventory/stock/:id` -> `/stock/items/:id`
- `/inventory/stock/:id/edit` -> `/stock/items/:id/edit`
- `/inventory/movements` -> `/stock/movements`
- `/inventory/movements/:id` -> `/stock/movements/:id`
- `/inventory/returns` -> `/stock/returns`
- `/inventory/repairs` -> `/stock/repairs`
- `/inventory/reorder` -> `/stock/reorder`
- `/inventory/adjustments` -> `/stock/adjustments`
- `/inventory/coverage` -> `/stock/coverage`
- `/inventory/inventaire` -> `/stock/inventory`
- `/inventory/damage-types` -> `/stock/damage-types`
- `/inventory/stock-alert/:id` -> `/stock/alerts/:id`
- `/parc` -> `/stock`

7. Migrate CRM aliases:
- `/clients` -> `/customers`
- `/relances` -> `/customers/relances`

8. Migrate finance aliases:
- `/finances` -> `/finance`
- `/finances/period` -> `/finance/period`
- `/finances/export` -> `/finance/export`
- `/tresorerie` -> `/finance/treasury`
- `/tarification` -> `/finance/pricing`
- `/invoices/*` -> `/finance/invoices/*`

9. Global entries:
- `/more` -> `/plus` (real hub page, no auto-redirect to `/commandes`)
- `/commandes` stays aggregate hub (no alias-to-reservations policy)

## 4.2 Keep-as-is routes (already ideal or near-ideal)

- `/dashboard`
- `/notifications`, `/notifications/settings`
- `/search`
- `/planning/*` (except alias back-compat handling)
- `/operations/*` (with legacy `departure-check|departure-blocked|return-damage` aliases redirected to canonical nested paths)
- `/commandes` (kept as aggregate hub; drill-down canonicalized)
- `/devis/*`
- `/ventes/*`
- `/customers/*` (becomes canonical)
- `/admin/*`
- `/profile/*`

---

## 5) Domain-by-domain Gaps to close in Step 1

- Reservations/Evenements:
  - Enforce strict boundary: reservation pages under `/reservations`, incidents under `/evenements`.
- Planning:
  - Remove `agenda` as a first-class namespace (redirect-only).
- Catalogue/Stock:
  - Present one user-facing split:
  - `catalogue` for master data
  - `stock` for physical state + movement operations
- Finance:
  - Collapse to one root (`/finance`) with `invoices` as subdomain.
- Shell:
  - Replace `/more` transition with a true `/plus` hub.

---

## 6) Output Artifacts for Next Step

- This file: canonical source of truth.
- Next execution file (Step 2): `NAV_STEP2_REDIRECT_IMPLEMENTATION.md`
  - exact route files to create/update
  - redirect code snippets
  - deprecation timeline per legacy namespace
  - test checklist (route resolve + deep-link + back/forward + active-nav)

---

## 7) Point 3 — Planning Migration (scope complet, validé) ✅ DONE 2026-03-07

### 7.1 Scope exact

1. `/agenda` -> `/planning/today`
2. `/agenda/mobile` -> `/planning/today?view=mobile`
3. `/agenda/resources` -> `/planning/resources`
4. `/agenda/affectation` -> `/planning/affectation`
5. `/planning` -> `/planning/today` (redirect explicite obligatoire)

### 7.2 État actuel (constaté)

1. `agenda/*` est encore un namespace fonctionnel (pas uniquement des redirects):
   - `frontend/src/routes/_app/agenda.tsx`
   - `frontend/src/routes/_app/agenda/index.tsx`
   - `frontend/src/routes/_app/agenda/mobile.tsx`
   - `frontend/src/routes/_app/agenda/resources.tsx`
   - `frontend/src/routes/_app/agenda/affectation.tsx`
2. `planning/*` existe déjà, mais sans index route `/planning`:
   - `frontend/src/routes/_app/planning.tsx`
   - absence de `frontend/src/routes/_app/planning/index.tsx`
3. Contrat data encore mixte:
   - `agenda` consomme `/inventory-movements/agenda` (`frontend/src/api/inventory.ts`).
   - `planning` consomme `/planning/*` (`frontend/src/api/planning.ts`).
4. Backend:
   - domaine canonique déjà présent en `/planning/*` (`app/api/v1/endpoints/planning.py`).
   - endpoint agenda legacy encore public (`/inventory-movements/agenda`, `app/api/v1/endpoints/inventory_movements.py`).

### 7.3 Décision architecture (meilleure option retenue)

Ne pas conserver `/inventory-movements/agenda` comme endpoint legacy actif.

Décision:
1. Canonique UX + API planning: uniquement `/planning/*`.
2. Les vues agenda/mobile sont migrées vers un contrat planning.
3. `/inventory-movements/agenda` sort du flux produit:
   - soit supprimé directement,
   - soit placé en `410 Gone` une release courte, sans logique métier active.
4. `inventory-movements` reste un domaine technique stock (journal et CRUD), mais plus une surface planning UI.

Justification:
- évite la double vérité fonctionnelle (`agenda` vs `planning`);
- supprime la dérive de scénarios causée par deux payloads concurrents;
- ferme le domaine planning sur un seul contrat maintenable.

### 7.4 Task list Frontend (Point 3)

1. Créer `/_app/planning/index.tsx` avec redirect `/planning/today`.
2. Sortir `/_app/agenda/*` de l'arbre actif (hard cut interne, pas de maintien applicatif).
3. Migrer `AgendaPage` et `AgendaMobilePage`:
   - retirer `useAgenda` basé sur `/inventory-movements/agenda`;
   - consommer le nouvel agrégat `GET /planning/timeline` (source unique calendrier + mobile).
4. Introduire un renderer mobile sur `/planning/today?view=mobile`.
5. Supprimer tous liens durs vers `/agenda` dans le frontend.
6. Option externe seulement (si contrainte réelle): gérer un redirect court au niveau gateway, hors app frontend.

### 7.5 Task list Backend (Point 3)

1. Converger vers un contrat planning unique avec **Option B validée**:
   - ajouter `GET /planning/timeline` (superset pour vues calendrier/mobile).
   - paramètres cibles: `start_date`, `end_date`, `view` (`day|week|month|mobile`), `tz`.
   - payload cible: blocs `reservations`, `movements`, `kpi`, `days`, et `by_date`.
2. Déplacer l'agrégation planning depuis `AsyncMovementService.get_agenda` vers un service planning dédié.
3. Sortir `/inventory-movements/agenda` du produit:
   - suppression directe prioritaire, ou
   - `410 Gone` transitoire technique (sans maintien fonctionnel).
4. Laisser inchangé le cœur stock/mouvement:
   - `/inventory-movements` CRUD/list/items reste le ledger technique.
5. Ajouter tests d'intégration planning couvrant `GET /planning/timeline` (schéma, filtres date, tenant isolation, perf baseline).

### 7.6 Task list DB (Point 3)

1. Aucun DDL obligatoire.
2. Vérifications perf recommandées:
   - index `(tenant_id, event_date)` sur `reservations`;
   - index `(tenant_id, scheduled_date)` sur `inventory_movements`.
3. Vérifications cohérence:
   - `delivery_date`, `event_date`, `return_date` cohérentes pour éviter des écarts entre vues.

### 7.7 Validation / tests (Point 3)

1. Route-level frontend:
   - `/planning` redirige vers `/planning/today`;
   - `/agenda*` n'est plus servi par l'app (hard cut interne);
   - `view=mobile` est rendu par le namespace planning.
2. API:
   - tests `planning` verts sur contrat final;
   - tests dédiés verts sur `GET /planning/timeline`;
   - aucun test frontend/qa ne dépend encore de `/inventory-movements/agenda`.
3. Régression navigation:
   - plus aucun lien dur vers `/agenda`.
4. Régression domaine:
   - `inventory-movements` continue de couvrir les besoins stock (hors calendrier UI).

### 7.8 Definition of Done (Point 3 fermé)

1. Un seul namespace visible utilisateur pour le planning: `/planning/*`.
2. Un seul contrat backend planning utilisé côté client.
   - contrat cible = `GET /planning/timeline`.
3. `agenda` n'est plus un namespace frontend actif.
4. Aucune nouvelle feature livrée sur `/inventory-movements/agenda`.

---

## 8) Point 4 — Operations Path Normalization (scope complet, validé) ✅ DONE 2026-03-07

### 8.1 Scope exact

1. `/operations/departure-check/:reservationId` -> `/operations/departure/:reservationId/check`
2. `/operations/departure-blocked/:reservationId` -> `/operations/departure/:reservationId/blocked`
3. `/operations/return-damage/:reservationId` -> `/operations/return/:reservationId/damage`
4. Maintenir `/operations` -> `/operations/scan` (déjà en place, reste canonique).

### 8.2 État actuel (constaté)

1. Les routes frontend actives sont encore sur les anciens segments:
   - `frontend/src/routes/_app/operations/departure-check.$reservationId.tsx`
   - `frontend/src/routes/_app/operations/departure-blocked.$reservationId.tsx`
   - `frontend/src/routes/_app/operations/return-damage.$reservationId.tsx`
2. La navigation interne utilise encore ces chemins legacy:
   - `DepartureInventoryPage` -> lien vers `/operations/departure-check/$reservationId`
   - `ArticleCheckPage` -> navigation vers `/operations/departure-check/$reservationId`
3. L'API backend operations est déjà cohérente et stable:
   - `GET/POST /operations/departure/{reservation_id}`
   - `POST /operations/departure/{reservation_id}/block`
   - `GET/POST /operations/return/{reservation_id}`
   - `POST /operations/return/{reservation_id}/damage`
4. Il n'existe pas d'API `/operations/departure-check/*` ni `/operations/return-damage/*`:
   - le legacy est uniquement dans les routes frontend.

### 8.3 Décision architecture

Décision:
1. Canoniser les chemins UI sur la forme hiérarchique:
   - `departure/:id/check`, `departure/:id/blocked`, `return/:id/damage`.
2. Garder les endpoints backend métier actuels (pas de refonte API obligatoire pour ce point).
3. Zéro legacy interne: retirer `departure-check`, `departure-blocked`, `return-damage` de l'arbre frontend actif.
4. Option externe seulement (si contrainte réelle): compatibilité courte au niveau gateway/reverse-proxy, hors app frontend.

Justification:
- ferme l'incohérence de structure URL sans risquer une régression métier backend;
- aligne les routes operations sur l'arborescence cible Step 1;
- réduit la dette de navigation avec un coût de migration faible.

### 8.4 Task list Frontend (Point 4)

1. Créer les nouvelles routes canoniques:
   - `/_app/operations/departure/$reservationId/check`
   - `/_app/operations/departure/$reservationId/blocked`
   - `/_app/operations/return/$reservationId/damage`
2. Supprimer les routes legacy de l'app:
   - `departure-check.$reservationId.tsx`
   - `departure-blocked.$reservationId.tsx`
   - `return-damage.$reservationId.tsx`
3. Corriger toutes les navigations internes `navigate/to` vers les routes canoniques.
4. Régénérer et valider `frontend/src/routeTree.gen.ts`.
5. Vérifier qu'aucune navigation interne ne cible encore les segments legacy.

### 8.5 Task list Backend (Point 4)

1. Aucun changement d'endpoint métier requis pour fermer le point.
2. Vérifier que la documentation API expose explicitement les endpoints operations actuels (éviter confusion avec les noms de routes frontend).
3. Optionnel (si clients externes couplés au vocabulaire UI):
   - ajouter alias non bloquants documentés, puis déprécier.
   - ne pas changer la logique métier existante.
4. Conserver la suite de tests operations existante comme garde-fou de non-régression.

### 8.6 Task list DB (Point 4)

1. Aucun DDL requis.
2. Aucun changement de modèle de données requis.
3. Vérification post-migration:
   - aucun impact sur transitions de statut réservation (`confirmed/pre_check/delivered/returned/confirmed_risk`).

### 8.7 Validation / tests (Point 4)

1. Route-level frontend:
   - `/operations/departure/:id/check` ouvre `ArticleCheckPage`;
   - `/operations/departure/:id/blocked` ouvre `DepartureBlockedPage`;
   - `/operations/return/:id/damage` ouvre `DamageDeclareFullPage`.
2. Hard cut interne:
   - les anciennes routes `departure-check|departure-blocked|return-damage` ne sont plus servies par l'app frontend.
3. Backend:
   - la suite `tests/integration/test_operations.py` reste verte.
4. Régression navigation:
   - plus aucun lien dur vers les segments legacy.

### 8.8 Definition of Done (Point 4 fermé)

1. Les trois URLs operations canoniques sont actives et utilisées partout en frontend.
2. Les segments legacy ne sont plus présents dans l'app frontend.
3. Aucune régression backend/API sur les flux départ/retour/dommage.
4. Toute compatibilité éventuelle est externalisée (gateway) et limitée dans le temps.

---

## 9) Point 2 — Events -> Reservations (reprise ferme)

### 9.1 Scope exact

Migrer uniquement les routes réservation de `events` vers `reservations` (les incidents restent traités au Point 1):

1. `/events` -> `/reservations`
2. `/events/new` -> `/reservations/new`
3. `/events/:id` -> `/reservations/:id`
4. `/events/:id/edit` -> `/reservations/:id/edit`
5. `/events/:id/lines` -> `/reservations/:id/lines`
6. `/events/:id/phases` -> `/reservations/:id/phases`
7. `/events/signature/:reservationId` -> `/reservations/:id/signature`

### 9.2 État actuel (factuel)

1. Les routes FE réservation sont encore sous `events`:
   - `frontend/src/routes/_app/events/index.tsx`
   - `frontend/src/routes/_app/events/new.tsx`
   - `frontend/src/routes/_app/events/$id.tsx`
   - `frontend/src/routes/_app/events/$id/index.tsx`
   - `frontend/src/routes/_app/events/$id/edit.tsx`
   - `frontend/src/routes/_app/events/$id/lines.tsx`
   - `frontend/src/routes/_app/events/$id/phases.tsx`
   - `frontend/src/routes/_app/events/signature.$reservationId.tsx`
2. Le backend métier est déjà canonique en `/reservations`:
   - `app/api/v1/endpoints/reservations.py`
   - `GET /{reservation_id}/lines` existe.
   - `GET /{reservation_id}/deposits/{deposit_id}` existe.
3. La data layer frontend consomme déjà `/reservations/*`:
   - `frontend/src/api/reservations.ts`
4. Le couplage navigation reste legacy:
   - backend search émet encore un `url` legacy pour les réservations (`/evenements`) dans `app/api/v1/endpoints/search.py`;
   - backend dashboard activity émet `link` legacy dans `app/api/v1/endpoints/dashboard.py`;
   - frontend search navigue directement sur `result.url` (`frontend/src/components/layout/GlobalSearch.tsx`, `frontend/src/pages/search/SearchPage.tsx`);
   - frontend notifications navigue directement sur `n.link` (`frontend/src/pages/dashboard/NotificationsPage.tsx`);
   - modèle DB notifications stocke un `link` brut (`app/models/notification.py`).

### 9.3 Pré-requis architecture (bloquant)

`/events/$id/incidents` dépend aujourd'hui de l'arbre `/events/$id`:
- `frontend/src/routes/_app/events/$id/incidents.tsx`

Donc:
1. soit Point 1 (incidents -> `evenements`) est appliqué en premier;
2. soit on isole techniquement le parent incidents avant de couper les routes réservation `events/$id`.

Sans ce pré-requis, la suppression dure des routes réservation peut casser les incidents.

### 9.4 Décision architecture (zéro legacy interne)

Décision retenue:
1. Canonique utilisateur: `reservations/*` uniquement pour tout le domaine réservation.
2. Zéro legacy interne: plus aucun lien/appui UI vers `events/*` (hors incidents tant que Point 1 n'est pas finalisé).
3. Les routes `events/*` de réservation sortent du produit (pas de maintien long de redirects).
4. Compatibilité externe éventuelle uniquement si contrainte réelle (clients externes), courte et datée.

### 9.5 Task list Frontend (Point 2)

1. Créer le namespace canonique `/_app/reservations/*` avec les composants actuels `pages/events/*` (hors incidents).
2. Mettre à jour layout et subnav réservation pour n'exposer que `reservations`.
3. Retirer "Incidents" du layout réservation (`EventIdLayout`) pour fermer le mélange domaine.
4. Remplacer tous les `navigate/to/href` `/events...` non-incidents dans:
   - dashboard, operations, planning, customers, invoices, commandes, devis, catalogue builder, nav shell.
5. Basculer l'activation nav principale vers le préfixe `/reservations` (`DashboardLayout`).
6. Sortir les routes `events/*` réservation de l'arbre actif une fois le pré-requis incidents validé.

### 9.6 Task list Backend (Point 2)

1. Aucun nouvel endpoint métier obligatoire (backend `/reservations` déjà complet).
2. Migrer les champs navigation émis par API:
   - search: ne plus émettre de `url` réservation legacy;
   - dashboard activity: ne plus émettre de `link` legacy pour les réservations.
3. Introduire un contrat navigation stable en complément de `url/link`:
   - `target: { domain, route_name, params }`.
4. Ajouter tests d'intégration empêchant la réintroduction de chemins legacy réservation dans les payloads API.

### 9.7 Task list DB (Point 2)

1. Aucun DDL obligatoire.
2. Migration de données recommandée:
   - convertir `notifications.link` de `/events...` vers `/reservations...` (et incidents vers `/evenements...`).
3. Contrôle post-migration:
   - plus aucun `link` persistant `/events` hors incidents.

### 9.8 Validation / tests (Point 2)

1. FE route-level:
   - `/reservations` + sous-routes (`new`, `:id`, `edit`, `lines`, `phases`, `signature`) fonctionnent.
2. Navigation UX:
   - depuis dashboard, operations, commandes, customers, invoices: actions réservation ouvrent `reservations/*`.
3. API:
   - suite réservations (`tests/integration/test_reservations_endpoints.py`) reste verte.
   - payloads search/dashboard ne réémettent pas de liens réservation legacy.
4. Régression:
   - aucun nouveau lien dur `/events` hors incidents dans frontend.

### 9.9 Definition of Done (Point 2 fermé)

1. Le domaine réservation est visible uniquement sous `/reservations/*`.
2. Le frontend n'utilise plus `events/*` pour les parcours réservation.
3. Les payloads backend n'émettent plus de liens réservation legacy.
4. Les liens DB persistés sont nettoyés pour le domaine réservation.

---

## 10) Point 5 — Products -> Catalogue (scope complet, validé)

### 10.1 Scope exact

Migrer la surface catalogue UI de `products/*` vers `catalogue/*`:

1. `/products` -> `/catalogue/products`
2. `/products/new` -> `/catalogue/products/new`
3. `/products/:id` -> `/catalogue/products/:id`
4. `/products/:id/editor` -> `/catalogue/products/:id/editor`
5. `/products/:id/audit` -> `/catalogue/products/:id/audit`
6. `/products/:id/availability` -> `/catalogue/products/:id/availability`
7. `/products/:id/maintenance` -> `/catalogue/products/:id/maintenance`
8. `/products/:id/photos` -> `/catalogue/products/:id/photos`
9. `/products/:id/states` -> `/catalogue/products/:id/states`
10. `/products/:id/variants` -> `/catalogue/products/:id/variants`
11. `/products/bundles` -> `/catalogue/bundles`
12. `/products/bundles/:id` -> `/catalogue/bundles/:id`
13. `/products/categories` -> `/catalogue/categories`
14. `/products/collections` -> `/catalogue/collections`
15. `/products/collections/:id` -> `/catalogue/collections/:id`
16. `/products/availability` -> `/catalogue/availability`
17. `/products/media` -> `/catalogue/media`
18. `/products/import` -> `/catalogue/import`
19. `/products/tools` -> `/catalogue/tools`
20. `/products/qr` -> `/catalogue/qr`
21. `/products/pilotage` -> `/catalogue/pilotage`
22. `/products/delivery-zones` -> `/catalogue/delivery-zones`
23. `/products/formulas` -> `/catalogue/formulas`
24. `/products/suppliers` -> `/catalogue/suppliers`
25. `/products/supplier-orders` -> `/catalogue/supplier-orders`
26. `/products/comparateur` -> `/catalogue/comparator`
27. `/catalogue/search` et `/catalogue/builder` restent canoniques.
28. `/catalogue` doit être une vraie entrée domaine (index/hub ou redirect explicite vers `/catalogue/products`).

### 10.2 État actuel (constaté)

1. Le namespace `products/*` est encore la surface fonctionnelle principale:
   - layout `frontend/src/routes/_app/products.tsx`
   - nombreuses routes actives sous `frontend/src/routes/_app/products/*`
2. Le namespace `catalogue/*` existe mais partiel:
   - `frontend/src/routes/_app/catalogue.tsx` (subnav mélange encore des liens `/products`)
   - `frontend/src/routes/_app/catalogue/search.tsx`
   - `frontend/src/routes/_app/catalogue/builder.tsx`
   - absence de `frontend/src/routes/_app/catalogue/index.tsx`
3. Incohérence UX concrète:
   - `ProductsPage` navigue vers `/products/search` alors que la route active est `/catalogue/search`.
4. Incohérence de naming:
   - route active `frontend/src/routes/_app/products/comparateur.tsx` alors que la cible Step 1 est `/catalogue/comparator`.
5. Couplage navigation transversal encore legacy:
   - liens `/products/*` présents dans pages catalogue/parc et dans le shell nav (`DashboardLayout` prefixes).
6. Backend:
   - API métier catalogue reste technique et cohérente sous `/products`, `/bundles`, `/categories`, `/collections`, `/delivery-zones`, `/formulas`, `/suppliers`, `/supplier-orders`.
   - endpoint search émet encore `url="/products"` pour les résultats type product (`app/api/v1/endpoints/search.py`).
   - aucun endpoint backend n'expose aujourd'hui de chemin UI `/catalogue/*` (absence de mapping de navigation côté API).
   - `SearchResult` est encore un contrat `url: str` non structuré (`app/schemas/search.py`), donc couplage direct backend -> route frontend.
   - note transverse hors scope strict Point 5: le dashboard émet encore un lien stock legacy `"/inventory/stock"` (`app/api/v1/endpoints/dashboard.py`).

### 10.3 Décision architecture (zéro legacy interne)

Décision retenue:
1. Canonique UX: toute navigation utilisateur catalogue passe par `/catalogue/*`.
2. API backend catalogue: on conserve les préfixes techniques existants (`/products`, `/bundles`, etc.), sans refonte d'endpoint pour ce point.
3. Zéro legacy interne frontend: `products/*` sort de l'arbre actif (pas de maintien applicatif long).
4. Compatibilité éventuelle uniquement hors app (gateway/reverse-proxy), courte et datée, si contrainte externe réelle.
5. Naming canonique: `comparator` devient la seule forme exposée côté routes UI.

Justification:
- clarifie le domaine catalogue pour l'utilisateur;
- évite d'ajouter une migration backend lourde non nécessaire à ce point;
- ferme les ambiguïtés de parcours (`/products/search`, `comparateur/comparator`, double subnav).

### 10.4 Task list Frontend (Point 5)

1. Créer le namespace complet `/_app/catalogue/*` selon la cible Step 1:
   - `products`, `products/new`, `products/$id/*`,
   - `bundles`, `categories`, `collections`,
   - `availability`, `media`, `import`, `tools`, `qr`, `pilotage`,
   - `delivery-zones`, `formulas`, `suppliers`, `supplier-orders`, `comparator`.
2. Ajouter `/_app/catalogue/index.tsx`:
   - soit hub catalogue explicite,
   - soit redirect explicite vers `/catalogue/products`.
3. Migrer les composants/pages existants `pages/products/*` vers les nouvelles routes `catalogue/*` (sans changer le métier).
4. Corriger tous les `navigate/to/href` internes `/products...` vers `/catalogue...`:
   - pages catalogue/parc,
   - modales de détails réservations/mouvements qui lient vers les produits,
   - nav shell (prefixes/actives).
5. Corriger les incohérences fonctionnelles immédiates:
   - `/products/search` -> `/catalogue/search`,
   - `/products/comparateur` -> `/catalogue/comparator`.
6. Sortir `/_app/products/*` de l'arbre frontend actif (hard cut interne).
7. Régénérer et valider `frontend/src/routeTree.gen.ts`.

### 10.5 Task list Backend (Point 5)

1. Aucun renommage massif d'API requis pour fermer ce point.
2. Mettre à jour les URLs de navigation émises par backend:
   - search `product.url` ne doit plus pointer vers `/products`;
   - cible recommandée: `/catalogue/products/:id` (ou contrat target structuré).
3. Vérifier les autres payloads backend (`url`, `link`) pour éliminer toute émission `/products...` côté UI.
4. Aligner avec le contrat de navigation stable (introduit au Point 2):
   - `target: { domain, route_name, params }` en complément de `url`.
5. Ajouter des tests d'intégration search pour figer la destination catalogue canonique.
6. Ajouter une assertion contractuelle backend:
   - absence de toute émission UI `/products...` dans les endpoints de navigation (`search`, `dashboard`, `notifications`).
7. Tracer la dépendance inter-point:
   - migration `dashboard.link="/inventory/stock"` vers route stock canonique traitée au Point 6 (non bloquant pour fermeture Point 5).

### 10.6 Task list DB (Point 5)

1. Aucun DDL obligatoire.
2. Migration de données recommandée sur les liens persistés (si présents):
   - convertir `/products...` -> `/catalogue...` dans `notifications.link` et autres colonnes de navigation persistée.
3. Contrôle post-migration:
   - aucun lien persistant `/products` côté parcours UI.

### 10.7 Validation / tests (Point 5)

1. FE route-level:
   - toutes les routes `catalogue/*` du scope sont accessibles;
   - `/catalogue` a un comportement explicite (hub ou redirect);
   - `/catalogue/comparator` remplace `comparateur`.
2. Hard cut interne:
   - `products/*` n'est plus servi par l'app frontend.
3. Backend:
   - search produit renvoie une destination UI canonique catalogue.
   - aucun endpoint de navigation backend ne réémet `/products...`.
4. Régression navigation:
   - plus aucun lien dur `/products` dans routes/pages/composants frontend (hors couche API HTTP vers backend).
5. Contrat:
   - `tests/integration/test_search.py` couvre explicitement la destination produit canonique.

### 10.8 Definition of Done (Point 5 fermé)

1. Le domaine catalogue est visible uniquement via `/catalogue/*` côté utilisateur.
2. Le frontend ne dépend plus de routes `products/*`.
3. Les payloads backend n'émettent plus de liens UI `/products...`.
4. Les liens persistés DB liés au catalogue sont nettoyés.

---

## 11) Point 6 — Inventory/Parc -> Stock (scope complet, validé)

### 11.1 Scope exact

Migrer la surface stock UI de `inventory/*` et `parc` vers `stock/*`:

1. `/inventory` -> `/stock`
2. `/inventory/stock` -> `/stock/items`
3. `/inventory/stock/:id` -> `/stock/items/:id`
4. `/inventory/stock/:id/edit` -> `/stock/items/:id/edit`
5. `/inventory/movements` -> `/stock/movements`
6. `/inventory/movements/:id` -> `/stock/movements/:id`
7. `/inventory/returns` -> `/stock/returns`
8. `/inventory/repairs` -> `/stock/repairs`
9. `/inventory/reorder` -> `/stock/reorder`
10. `/inventory/adjustments` -> `/stock/adjustments`
11. `/inventory/coverage` -> `/stock/coverage`
12. `/inventory/inventaire` -> `/stock/inventory`
13. `/inventory/damage-types` -> `/stock/damage-types`
14. `/inventory/stock-alert/:id` -> `/stock/alerts/:id`
15. `/parc` -> `/stock`

### 11.2 État actuel (constaté)

1. Le namespace frontend actif est encore `inventory/*`:
   - layout `frontend/src/routes/_app/inventory.tsx`
   - sous-routes `frontend/src/routes/_app/inventory/*` (stock, movements, returns, repairs, reorder, adjustments, coverage, inventaire, damage-types, stock-alert)
2. Le hub `parc` est encore la porte d'entrée stock/catalogue:
   - route `frontend/src/routes/_app/parc.tsx`
   - navigation shell `DashboardLayout` pointe vers `/parc` et active le prefix `/inventory`
3. Le namespace `stock/*` frontend n'existe pas encore:
   - absence de `frontend/src/routes/_app/stock.tsx`
   - absence de `frontend/src/routes/_app/stock/index.tsx`
4. Trous de navigation frontend:
   - pas d'index `/_app/inventory/index.tsx` (comportement `/inventory` implicite/non piloté);
   - pas de route détail mouvement (`/inventory/movements/:id`) alors que le mapping cible la prévoit;
   - page `/inventory/coverage` existante mais non exposée dans la subnav inventory.
5. Contrat data frontend déjà mixte:
   - `inventoryApi` consomme `/inventory-movements/*` + `/products/{id}/stock*` (`frontend/src/api/inventory.ts`);
   - `stockApi` consomme `/stock/*` (`frontend/src/api/stock.ts`);
   - `damageTypesApi` consomme `/damage-types` (`frontend/src/api/damage_types.ts`).
   - écart de contrat à corriger: `stockApi` type certaines réponses en listes directes alors que backend renvoie `PaginatedResponse` (`/stock/levels`, `/stock/reorder`, `/stock/adjustments`).
   - même écart sur `damageTypesApi` (liste typée tableau alors que `/damage-types` renvoie `PaginatedResponse`).
6. Backend confirmé:
   - domaine stock physique canonique: `/stock/*` (`app/api/v1/endpoints/stock_management.py`);
   - domaine ledger mouvements: `/inventory-movements/*` (`app/api/v1/endpoints/inventory_movements.py`);
   - référentiel dommages: `/damage-types/*` (`app/api/v1/endpoints/damage_types.py`);
   - détail stock unitaire encore exposé sous `/products/{id}/stock*` (`app/api/v1/endpoints/products.py`).
7. Payloads backend navigation:
   - dashboard activity émet encore `link="/inventory/stock"` (`app/api/v1/endpoints/dashboard.py`).
8. Contrat backend sans endpoint dédié alerte stock par id:
   - pas de `GET /stock/alerts/{id}` côté API à ce stade (la page alerte se base sur `products/low-stock` + `products/{id}/stock`).

### 11.3 Décision architecture (zéro legacy interne)

Décision retenue:
1. Canonique UX: un seul namespace visible utilisateur pour le domaine stock: `/stock/*`.
2. Le hub `/parc` sort de l'arbre frontend actif (plus de concept domaine exposé).
3. Le backend conserve la séparation technique:
   - `/stock/*` = état physique / inventaire / réassort / couverture;
   - `/inventory-movements/*` = journal des mouvements;
   - `/damage-types/*` = référentiel dommages.
4. Les routes UI canoniques `/stock/*` sont servies par adaptation client/BFF vers ces endpoints techniques (pas de rename API massif requis pour fermer le point).
5. Zéro legacy interne frontend:
   - `inventory/*` et `parc` sortent de l'arbre actif;
   - compat externe éventuelle uniquement hors app (gateway), courte et datée.
6. Route détail mouvement canonique obligatoire côté UI: `/stock/movements/:id`.
7. Cible navigation backend canonique:
   - aucun `link/url` émis vers `/inventory...` ou `/parc...`.
8. Standard de contrat pagination (décision ferme):
   - toutes les listes backend restent/en deviennent `PaginatedResponse`;
   - le frontend consomme explicitement `{ items, total, skip, limit }` (pas de typage tableau direct).

Justification:
- clarifie la frontière UX `catalogue` vs `stock`;
- garde la stabilité backend sur des domaines techniques déjà testés;
- supprime la duplication de parcours et les liens legacy cross-domain.

### 11.4 Task list Frontend (Point 6)

1. Créer le namespace complet `/_app/stock/*` selon la cible Step 1:
   - `items`, `items/$id`, `items/$id/edit`,
   - `movements`, `movements/$id`,
   - `returns`, `repairs`, `reorder`, `adjustments`, `coverage`, `inventory`, `damage-types`, `alerts/$id`.
2. Ajouter `/_app/stock/index.tsx`:
   - hub stock explicite ou redirect explicite vers `/stock/items`.
3. Migrer les pages existantes `pages/inventory/*` vers routes `stock/*` (sans changement métier).
4. Remplacer tous les liens/navigations `/inventory...` et `/parc...`:
   - pages inventory/parc,
   - pages operations (`scan`, `return`) qui renvoient vers `/parc` ou `/inventory/stock`,
   - shell nav (`DashboardLayout`).
5. Exposer explicitement la couverture stock dans la navigation `stock` (page aujourd'hui orpheline).
6. Ajouter la route détail mouvement `stock/movements/:id` (vue page ou wrapper du modal existant).
7. Sortir `/_app/inventory/*` et `/_app/parc` de l'arbre frontend actif (hard cut interne).
8. Régénérer et valider `frontend/src/routeTree.gen.ts`.
9. Corriger l'adaptation data stock côté client:
   - `stockApi` retourne des `PaginatedResponse<T>` pour `levels`, `reorder`, `adjustments`;
   - `damageTypesApi.list` retourne `PaginatedResponse<DamageType>`;
   - les hooks/pages utilisent explicitement `data.items` + métadonnées pagination.

### 11.5 Task list Backend (Point 6)

1. Aucun renommage massif des endpoints techniques requis.
2. Mettre à jour les liens de navigation émis par API:
   - dashboard `link="/inventory/stock"` -> destination canonique `/stock/items`.
3. Vérifier tous payloads backend de navigation (`url`, `link`) pour supprimer `/inventory...` et `/parc...`.
4. Conserver `inventory-movements` comme ledger technique, mais hors exposition de namespace UX.
5. Dépendance inter-point:
   - le retrait de `/inventory-movements/agenda` reste piloté par Point 3 (planning canonique).
6. Option P1 (si besoin d'un contrat backend explicite pour la page alerte):
   - ajouter `GET /stock/alerts/{product_id}` agrégé;
   - sinon formaliser que l'alerte UI compose `products/low-stock` + `products/{id}/stock`.
7. Ajouter des tests d'intégration de contrat navigation backend pour empêcher la réintroduction de liens `inventory/parc`.
8. Standardiser explicitement les schémas de liste:
   - confirmer `PaginatedResponse` sur tous les endpoints liste des domaines stock/inventory-movements/damage-types;
   - interdire les retours liste brute pour ces endpoints.

### 11.6 Task list DB (Point 6)

1. Aucun DDL obligatoire.
2. Migration de données recommandée:
   - convertir les liens persistés `/inventory...` et `/parc...` vers `/stock...` (ex: `notifications.link`).
3. Vérifications performance recommandées:
   - index `(tenant_id, scheduled_date)` sur `inventory_movements`;
   - index `(tenant_id, available_quantity)` sur `products` pour listes low-stock/reorder.
4. Contrôle de cohérence:
   - cohérence des statuts/quantités entre `products.available_quantity`, `stock_items` et mouvements complétés.

### 11.7 Validation / tests (Point 6)

1. FE route-level:
   - toutes les routes `stock/*` du scope sont accessibles;
   - `/stock` a un comportement explicite (hub ou redirect);
   - `stock/movements/:id` est accessible.
2. Hard cut interne:
   - `inventory/*` et `/parc` ne sont plus servis par l'app frontend.
3. Backend:
   - suites `tests/integration/test_stock_management.py`,
     `tests/integration/test_inventory_movements_endpoints.py`,
     `tests/integration/test_damage_types.py`,
     `tests/integration/test_reservation_stock_workflow.py` restent vertes;
   - plus aucun payload navigation backend n'émet `/inventory...` ou `/parc...`.
   - les endpoints liste valident un contrat `PaginatedResponse` (présence `items,total,skip,limit`).
4. Régression navigation:
   - depuis dashboard, operations, alerts et search interne stock, toutes les actions ouvrent `stock/*`.

### 11.8 Definition of Done (Point 6 fermé)

1. Le domaine stock est visible uniquement via `/stock/*` côté utilisateur.
2. Le frontend ne dépend plus de routes `/inventory/*` ni de `/parc`.
3. Les payloads backend n'émettent plus de liens UI `/inventory...` ou `/parc...`.
4. Les liens persistés DB liés au stock sont nettoyés.
5. Tous les endpoints liste du domaine stock respectent `PaginatedResponse` et le frontend les consomme sans adaptation ad hoc.

---

## 12) Point 7 — CRM aliases -> Customers (scope complet, validé)

### 12.1 Scope exact

Migrer les alias CRM historiques vers le namespace canonique `customers`:

1. `/clients` -> `/customers`
2. `/relances` -> `/customers/relances`
3. `/customers/*` reste canonique (`/customers/:id`, `/customers/:id/edit`, `/customers/:id/history`, `/customers/rfm`).

### 12.2 État actuel (constaté)

1. Le namespace `customers/*` est déjà fonctionnel et quasi complet:
   - layout `frontend/src/routes/_app/customers.tsx`
   - routes `customers/index`, `customers/$id`, `customers/$id/edit`, `customers/$id/history`, `customers/relances`, `customers/rfm`.
2. `/clients` existe encore comme alias frontend (redirect):
   - `frontend/src/routes/_app/clients.tsx` redirige vers `/customers`.
3. `/relances` existe encore comme route frontend active (pas alias):
   - `frontend/src/routes/_app/relances.tsx`.
4. Double implémentation UI relances (incohérence fonctionnelle):
   - `/relances` -> `RelancesPlanifieesPage` (planification + workflow complet),
   - `/customers/relances` -> `ClientsRelancesPage` (version plus limitée).
5. Navigation shell encore legacy:
   - `DashboardLayout` pointe `Clients` sur `/clients` et conserve le prefix `/relances`.
6. Backend:
   - API canonique sous `/customers` et `/relances`;
   - aucun endpoint `/clients` côté API;
   - search émet déjà des URLs `/customers/{id}`.
7. Contrat pagination (point critique confirmé):
   - backend `/relances` renvoie `PaginatedResponse[RelanceResponse]` (`app/api/v1/endpoints/relances.py`);
   - frontend `relancesApi.list` est typé `RelanceResponse[]` (`frontend/src/api/relances.ts`);
   - `useRelances` et les pages relances consomment une liste brute;
   - `tests/integration/test_relances.py` vérifie encore un tableau brut.

### 12.3 Décision architecture (zéro legacy interne + pagination standard)

Décision retenue:
1. Canonique UX CRM: `/customers/*` uniquement.
2. Un seul écran relances canonique: `/customers/relances` (fusion des deux implémentations actuelles).
3. Zéro legacy interne frontend:
   - `/clients` et `/relances` sortent de l'arbre actif;
   - compat externe éventuelle uniquement hors app (gateway), courte et datée.
4. Backend API inchangé sur les domaines métier:
   - `/customers/*` et `/relances/*` restent les préfixes techniques.
5. Standard pagination (décision ferme):
   - la liste relances reste/en devient strictement `PaginatedResponse`;
   - frontend + tests s'alignent explicitement sur `{ items, total, skip, limit }`.

Justification:
- ferme la confusion UX créée par deux pages relances concurrentes;
- aligne la navigation CRM sur le canonique Step 1;
- applique la règle transversale de standardisation `PaginatedResponse`.

### 12.4 Task list Frontend (Point 7)

1. Basculer la nav principale CRM en canonique:
   - `DashboardLayout`: `href='/customers'`, suppression des prefixes legacy `/clients` et `/relances`.
2. Unifier les relances:
   - garder une seule page métier sur `/customers/relances`;
   - fusionner les capacités utiles de `RelancesPlanifieesPage` et `ClientsRelancesPage`;
   - supprimer la duplication de composants/pages.
3. Sortir `/_app/clients` et `/_app/relances` de l'arbre frontend actif (hard cut interne).
4. Remplacer tous les liens `navigate/to/href` restants `/clients` ou `/relances` vers `/customers` ou `/customers/relances`.
5. Standardiser le contrat API relances côté client:
   - `relancesApi.list` -> `PaginatedResponse<RelanceResponse>`;
   - `useRelances*` et les pages utilisent `data.items` + métadonnées pagination.
6. Mettre à jour les tests frontend associés:
   - `frontend/src/api/__tests__/relances.test.ts` attend un payload paginé.
7. Régénérer et valider `frontend/src/routeTree.gen.ts`.

### 12.5 Task list Backend (Point 7)

1. Aucun nouveau endpoint métier obligatoire.
2. Conserver et documenter explicitement le contrat:
   - `GET /relances` retourne `PaginatedResponse`.
3. Mettre à jour les tests backend qui sont encore sur liste brute:
   - `tests/integration/test_relances.py` doit valider `items,total,skip,limit`.
4. Vérifier les payloads backend de navigation:
   - aucune émission `url/link` vers `/clients` ou `/relances`.
5. Conserver search CRM sur `/customers/{id}` comme cible canonique.

### 12.6 Task list DB (Point 7)

1. Aucun DDL obligatoire.
2. Migration de données recommandée:
   - convertir les liens persistés `/clients...` -> `/customers...`;
   - convertir `/relances...` -> `/customers/relances...` si présents.
3. Contrôle post-migration:
   - plus aucun lien persistant CRM sur namespaces legacy.

### 12.7 Validation / tests (Point 7)

1. FE route-level:
   - `/customers`, `/customers/relances`, `/customers/rfm`, `/customers/:id*` fonctionnent.
2. Hard cut interne:
   - `/clients` et `/relances` ne sont plus servis par l'app frontend.
3. Backend:
   - suites `tests/integration/test_customers_endpoints.py`,
     `tests/integration/test_customer_history.py`,
     `tests/integration/test_rfm.py`,
     `tests/integration/test_relances.py` vertes;
   - `GET /relances` validé en contrat paginé.
4. Régression navigation:
   - plus aucun lien dur `/clients` ou `/relances` dans routes/pages/composants.

### 12.8 Definition of Done (Point 7 fermé)

1. Le domaine CRM est visible uniquement via `/customers/*`.
2. Un seul écran relances existe côté produit: `/customers/relances`.
3. `PaginatedResponse` est respecté de bout en bout sur la liste relances (backend, frontend, tests).
4. Aucun payload backend ni lien persistant n'utilise `/clients` ou `/relances`.

---

## 13) Point 8 — Finance aliases -> /finance (scope complet, validé)

### 13.1 Scope exact

Migrer la surface finance UI vers le namespace canonique `finance`:

1. `/finances` -> `/finance`
2. `/finances/period` -> `/finance/period`
3. `/finances/export` -> `/finance/export`
4. `/tresorerie` -> `/finance/treasury`
5. `/tarification` -> `/finance/pricing`
6. `/invoices/*` -> `/finance/invoices/*`

### 13.2 État actuel (constaté)

1. Le frontend expose encore les namespaces legacy:
   - `frontend/src/routes/_app/finances.tsx`
   - `frontend/src/routes/_app/finances/period.tsx`
   - `frontend/src/routes/_app/finances/export.tsx`
   - `frontend/src/routes/_app/tresorerie.tsx`
   - `frontend/src/routes/_app/tarification.tsx`
   - `frontend/src/routes/_app/invoices.tsx` + `frontend/src/routes/_app/invoices/*`
2. Il n'existe pas encore de namespace frontend canonique `/_app/finance/*`:
   - absence de `frontend/src/routes/_app/finance.tsx`
   - absence de `frontend/src/routes/_app/finance/index.tsx`
3. La navigation shell reste couplée legacy:
   - `DashboardLayout` pointe encore `href='/finances'` avec prefixes legacy (`/finances`, `/invoices`, `/tresorerie`, `/tarification`).
4. La sous-navigation facturation reste legacy:
   - `frontend/src/routes/_app/invoices.tsx` expose des liens `/invoices/*`.
5. Beaucoup de pages et CTA naviguent encore en dur vers `/invoices...` et `/finances/export` (dashboard, operations, customers, pages invoices).
6. Backend métier confirmé:
   - API factures canonique technique: `app/api/v1/endpoints/invoices.py` (`/invoices/*`),
   - API tarification technique: `app/api/v1/endpoints/pricing.py` (`/pricing/*`),
   - KPI/export finances dashboard: `app/api/v1/endpoints/dashboard.py` (`/dashboard/finances`, `/dashboard/finances/export`).
7. Payloads backend de navigation encore legacy UI:
   - search invoice: `url="/invoices"` (`app/api/v1/endpoints/search.py`),
   - activity feed: `link=f"/invoices/{inv.id}"` (`app/api/v1/endpoints/dashboard.py`).
8. Contrat pagination finance hétérogène (constat backend + frontend):
   - backend déjà paginé: `/invoices`, `/invoices/overdue`, `/invoices/payments`, `/pricing/rules`;
   - backend en liste brute: `/invoices/{id}/payments`, `/invoices/{id}/credit-notes`, `/invoices/{id}/audit`, `/pricing/rules/product/{id}`;
   - frontend API maintient des adaptations ad hoc `Array.isArray(...)` dans `frontend/src/api/invoices.ts` et `frontend/src/api/pricing.ts`;
   - écart client supplémentaire: `invoicesApi.getAllPayments` envoie `offset` alors que l'API attend `skip` via `PaginationParams`.

### 13.3 Décision architecture (zéro legacy interne + pagination standard)

Décision retenue:
1. Canonique UX finance: toutes les entrées utilisateur passent par `/finance/*`.
2. Les routes legacy `/finances`, `/invoices`, `/tresorerie`, `/tarification` sortent de l'arbre frontend actif (pas de maintien applicatif long).
3. Le backend conserve ses préfixes techniques (`/invoices`, `/pricing`, `/dashboard/finances`) pour limiter le risque.
4. Les payloads backend de navigation (`url/link`) doivent cibler les routes UI canoniques `/finance/*`.
5. Standard transversal ferme: toutes les listes du domaine finance sont `PaginatedResponse` (backend, frontend, tests), sans fallback tableau.

Justification:
- unifie un domaine aujourd'hui éclaté sur 4 racines frontend;
- supprime le couplage fragile backend -> routes legacy UI;
- ferme l'incohérence de contrat pagination qui crée des adaptations ad hoc côté client.

### 13.4 Task list Frontend (Point 8)

1. Créer le namespace canonique `/_app/finance/*`:
   - `index`, `period`, `export`, `treasury`, `pricing`,
   - `invoices/*` (index, new, `:id`, `:id/edit`, `:id/audit`, `:id/avoir`, `cautions`, `rapport-mensuel`, `tva-report`, `rapprochement`).
2. Créer `/_app/finance/index.tsx`:
   - hub explicite finance ou redirect explicite vers `/finance/invoices`.
3. Migrer les routes actuelles `finances/*`, `invoices/*`, `tresorerie`, `tarification` vers `finance/*` sans changement métier.
4. Mettre à jour `DashboardLayout`:
   - `href='/finance'`,
   - prefixes canoniques uniquement `/finance`.
5. Mettre à jour toutes les navigations internes `navigate/to/href`:
   - remplacer `/invoices...`, `/finances...`, `/tresorerie`, `/tarification` par `/finance/...`.
6. Mettre à jour la SubNav factures pour ne publier que `/finance/invoices/*`.
7. Sortir `/_app/finances*`, `/_app/invoices*`, `/_app/tresorerie`, `/_app/tarification` de l'arbre actif (hard cut interne).
8. Standardiser le contrat API côté client sur la finance:
   - supprimer `Array.isArray` fallback dans `frontend/src/api/invoices.ts` et `frontend/src/api/pricing.ts`;
   - typer explicitement les listes en `PaginatedResponse<T>`;
   - corriger `getAllPayments` pour envoyer `skip` (pas `offset`).
9. Mettre à jour les hooks et pages finance pour consommer `data.items` + `total/skip/limit`.
10. Mettre à jour tests frontend API (`invoices.test.ts`, `pricing.test.ts`) sur contrat paginé strict.
11. Régénérer et valider `frontend/src/routeTree.gen.ts`.

### 13.5 Task list Backend (Point 8)

1. Conserver les endpoints métier existants (`/invoices`, `/pricing`, `/dashboard/finances`) pour ce point.
2. Migrer les champs navigation émis par backend vers UI canonique finance:
   - `search.py`: `invoice.url` -> `/finance/invoices/{id}` (ou liste selon décision UX, mais plus `/invoices`);
   - `dashboard.py`: `activity.link` invoice -> `/finance/invoices/{id}`.
3. Vérifier tous les payloads backend (`url/link`) pour éliminer `/finances`, `/invoices`, `/tresorerie`, `/tarification` côté UI.
4. Standardiser `PaginatedResponse` sur les listes finance backend:
   - `GET /invoices/{id}/payments` -> `PaginatedResponse[PaymentRead]`,
   - `GET /invoices/{id}/credit-notes` -> `PaginatedResponse[CreditNoteResponse]`,
   - `GET /invoices/{id}/audit` -> `PaginatedResponse[AuditLogResponse]`,
   - `GET /pricing/rules/product/{product_id}` -> `PaginatedResponse[PricingRuleResponse]`.
5. Conserver la cohérence de pagination (`skip`/`limit`) sur tous les endpoints liste finance.
6. Ajouter/adapter les tests d'intégration:
   - `tests/integration/test_invoices_endpoints.py`,
   - `tests/integration/test_invoice_credit_notes.py`,
   - `tests/integration/test_payments.py`,
   - `tests/integration/test_pricing.py`,
   - tests search/dashboard pour les liens UI canoniques finance.

### 13.6 Task list DB (Point 8)

1. Aucun DDL obligatoire.
2. Migration de données recommandée sur liens persistés:
   - `/finances...` -> `/finance...`,
   - `/invoices...` -> `/finance/invoices...`,
   - `/tresorerie` -> `/finance/treasury`,
   - `/tarification` -> `/finance/pricing`.
3. Contrôle post-migration:
   - plus aucun lien persistant finance sur namespaces legacy.

### 13.7 Validation / tests (Point 8)

1. FE route-level:
   - `/finance`, `/finance/period`, `/finance/export`, `/finance/treasury`, `/finance/pricing` fonctionnent;
   - `/finance/invoices/*` couvre tout le périmètre facturation.
2. Hard cut interne:
   - `finances*`, `invoices*`, `tresorerie`, `tarification` ne sont plus servis par l'app frontend.
3. Backend:
   - payloads search/dashboard n'émettent plus de liens UI legacy finance;
   - tous les endpoints liste finance validés en `PaginatedResponse` (`items,total,skip,limit`).
4. Frontend data:
   - plus aucun fallback `Array.isArray` sur les APIs finance.
5. Régression navigation:
   - depuis dashboard, customers, operations, search, notifications: tous les parcours facturation/finance ouvrent `/finance/*`.

### 13.8 Definition of Done (Point 8 fermé)

1. Le domaine finance est visible uniquement via `/finance/*` côté utilisateur.
2. Le frontend n'utilise plus `finances|invoices|tresorerie|tarification` comme routes actives.
3. Les payloads backend n'émettent plus de liens UI finance legacy.
4. Les liens persistés DB finance sont nettoyés.
5. `PaginatedResponse` est standardisé de bout en bout sur les listes finance (backend, frontend, tests).

---

## 14) Point 9 — Entrées globales (`/more` -> `/plus`) + gouvernance L1

### 14.1 Scope exact

1. `/more` -> `/plus`.
2. `/plus` devient un vrai hub de navigation domaine (pas une page de transition).
3. `/commandes` reste un hub agrégé métier (devis + réservations + ventes), sans alias vers `/reservations`.
4. La contrainte produit "max 5 onglets L1" devient contractuelle avec l'ensemble canonique:
   - `/dashboard`,
   - `/planning/today`,
   - `/reservations`,
   - `/operations/scan`,
   - `/plus`.

### 14.2 État actuel (constaté)

1. La route frontend `/more` existe encore:
   - `frontend/src/routes/_app/more.tsx`.
2. `MorePage` est une redirection immédiate vers `/commandes`:
   - `frontend/src/pages/more/MorePage.tsx`.
3. Le namespace `/plus` n'existe pas:
   - aucune route `frontend/src/routes/_app/plus.tsx`.
4. Les 5 onglets L1 actuels ne respectent pas la cible Step 1:
   - `DashboardLayout` publie `Dashboard`, `Commandes`, `Clients`, `Parc`, `Finances`.
5. `/commandes` est bien actif et métier:
   - route `frontend/src/routes/_app/commandes.tsx`,
   - page `CommandesListPage` avec subnav devis/réservations/ventes.
6. Backend confirmé pour le hub commandes:
   - endpoint agrégé `/orders` paginé (`app/api/v1/endpoints/orders.py`),
   - service `orders` renvoie `PaginatedResponse` (`app/services/orders.py`).
7. Couplage backend/navigation:
   - aucun payload backend constaté n'émet aujourd'hui `/more`, `/plus` ou `/commandes`.
8. Gap qualité backend:
   - absence de tests d'intégration dédiés au domaine `/orders` (pas de `tests/integration/test_orders.py` à ce stade).

### 14.3 Décision architecture (zéro legacy interne)

Décision retenue:
1. `/plus` est canonique comme cinquième onglet L1 et hub overflow.
2. `/more` sort de l'arbre frontend actif (pas de maintien applicatif long).
3. `/commandes` reste une destination métier de niveau domaine, accessible depuis `/plus` et actions contextuelles.
4. `/commandes` n'est pas un alias de `/reservations` (aucune convergence forcée).
5. La gouvernance L1 est figée contractuellement à 5 onglets canoniques.

Justification:
- ferme la confusion actuelle "more = redirect vers commandes";
- maintient la valeur métier du hub agrégé commandes;
- impose une navigation stable et scalable avec la limite L1.

### 14.4 Task list Frontend (Point 9)

1. Créer `/_app/plus.tsx` et la page hub `/plus` (cartes/liens vers domaines non-L1).
2. Sortir `/_app/more.tsx` de l'arbre actif (hard cut interne).
3. Mettre à jour `DashboardLayout` pour n'exposer que les 5 onglets L1 canoniques:
   - Dashboard -> `/dashboard`,
   - Planning -> `/planning/today`,
   - Réservations -> `/reservations`,
   - Opérations -> `/operations/scan`,
   - Plus -> `/plus`.
4. Déplacer les entrées `Commandes`, `Clients`, `Parc`, `Finances` hors L1 vers le hub `/plus` (avec raccourcis explicites).
5. Conserver `/commandes` actif comme page domaine, accessible via `/plus`.
6. Supprimer toute navigation interne vers `/more` et la remplacer par `/plus`.
7. Vérifier les prefixes d'activation nav pour éviter les activations croisées parasites.
8. Régénérer et valider `frontend/src/routeTree.gen.ts`.

### 14.5 Task list Backend (Point 9)

1. Aucun endpoint métier supplémentaire requis pour `/plus`.
2. Conserver `/orders` comme backend canonique du hub commandes (déjà paginé).
3. Ajouter une couverture de tests d'intégration dédiée `/orders`:
   - liste paginée (`skip/limit/total/items`),
   - filtres `status` et `order_type`,
   - détail `/orders/{order_type}/{order_id}`,
   - isolation tenant.
4. Vérifier et figer la règle navigation backend:
   - aucun `url/link` émis vers `/more`;
   - si un lien d'overflow est émis, utiliser `/plus`.
5. Option P1 de découplage:
   - généraliser `target: {domain, route_name, params}` en complément de `url/link` pour éviter le recouplage aux chemins UI.

### 14.6 Task list DB (Point 9)

1. Aucun DDL obligatoire.
2. Migration de données recommandée:
   - convertir les liens persistés `/more...` vers `/plus...` (ex: `notifications.link`).
3. Contrôle post-migration:
   - plus aucun lien persistant `/more`.

### 14.7 Validation / tests (Point 9)

1. FE route-level:
   - `/plus` affiche le hub,
   - `/commandes` reste accessible et fonctionnel.
2. Hard cut interne:
   - `/more` n'est plus servi par l'app frontend.
3. L1 contractuel:
   - exactement 5 onglets visibles et conformes à la cible canonique.
4. Backend:
   - tests `/orders` verts (liste + détail + pagination + tenant isolation).
5. Régression navigation:
   - aucun lien dur `/more` dans routes/pages/composants,
   - parcours vers `customers`, `catalogue/stock`, `finance`, `commandes` opérationnels via `/plus`.

### 14.8 Definition of Done (Point 9 fermé)

1. `/plus` est le seul hub global overflow visible côté utilisateur.
2. `/more` est retiré de l'application frontend.
3. `/commandes` reste un hub agrégé métier autonome (pas alias réservation).
4. La contrainte L1=5 est appliquée et vérifiable en production.
5. Aucun payload backend ni lien persistant n'utilise `/more`.

---

## 15) Point 10 — Admin/Profile (cohérence finale)

### 15.1 Scope exact

Consolider les domaines `admin` et `profile` sans changer leur arborescence cible:

1. `/admin` doit avoir un comportement explicite (hub ou redirect vers `/admin/users`).
2. `/admin/*` reste canonique:
   - `/admin/users`, `/admin/users/:id`, `/admin/sessions`, `/admin/api-keys`, `/admin/features`, `/admin/audit-logs`, `/admin/vpn`, `/admin/settings`.
3. `/profile/*` reste canonique:
   - `/profile`, `/profile/security`, `/profile/mfa`.
4. Clarifier la frontière sessions:
   - sessions personnelles = domaine profile,
   - sessions tenant/admin = domaine admin.

### 15.2 État actuel (constaté)

1. Les routes frontend `admin/*` et `profile/*` existent déjà dans la forme cible:
   - `frontend/src/routes/_app/admin.tsx` + enfants,
   - `frontend/src/routes/_app/profile.tsx` + enfants.
2. Trou de route:
   - absence de `frontend/src/routes/_app/admin/index.tsx` (route `/admin` non pilotée explicitement).
3. Incohérence de domaine sur les sessions:
   - la page `/admin/sessions` (`SessionsPage`) consomme les endpoints user self-service `/sessions`;
   - les endpoints backend admin tenant sessions existent séparément sous `/admin/tenants/{tenant_id}/.../sessions` mais ne sont pas exploités côté frontend.
4. Incohérence UX profile:
   - `SecurityPage` renvoie vers `/admin/sessions` pour "Sessions actives", alors qu'il s'agit d'un besoin profil personnel.
5. Backend admin/profile confirmé:
   - users: `/users`, `/users/me`,
   - sessions self: `/sessions`,
   - sessions admin tenant: `/admin/tenants/{tenant_id}/sessions*`,
   - api keys: `/api-keys`,
   - feature flags: `/features`,
   - audit: `/audit`,
   - settings: `/admin/settings`,
   - vpn: `/vpn/*`,
   - mfa: `/mfa/*`.
6. Contrat pagination:
   - déjà standardisé sur `users`, `api-keys`, `features`, `audit`;
   - non standard sur `sessions` (schema `SessionListResponse`);
   - non standard strict sur `vpn` (schema `{items,total}` sans `skip/limit`).
7. Couverture tests backend:
   - bonne couverture intégration sur `users`, `sessions` self-service, `api-keys`, `features`, `vpn`, `admin/settings`, `mfa`;
   - trou de couverture sur les endpoints `/audit`;
   - trou de couverture sur les endpoints admin tenant sessions (`/admin/tenants/*/sessions`).

### 15.3 Décision architecture (frontière domaine + pagination)

Décision retenue:
1. `admin` et `profile` restent les namespaces canoniques sans alias additionnels.
2. `/admin` devient explicite (hub ou redirect), jamais implicite.
3. Séparation sessions ferme:
   - `profile/security` porte la gestion des sessions personnelles;
   - `/admin/sessions` porte la gestion des sessions tenant/admin.
4. Standard de pagination appliqué au domaine admin/profile:
   - toutes les listes exposent au minimum `items,total,skip,limit`.
5. Zéro recouplage route/backend:
   - les payloads de navigation backend doivent rester indépendants des chemins legacy et des conventions implicites.

Justification:
- ferme la confusion actuelle "route admin pour un besoin profil personnel";
- aligne la sémantique UI avec les endpoints backend existants;
- réduit les adaptations ad hoc côté client et fiabilise les tests de contrat.

### 15.4 Task list Frontend (Point 10)

1. Ajouter `/_app/admin/index.tsx`:
   - redirect explicite vers `/admin/users` ou hub admin explicite.
2. Clarifier la page `/admin/sessions`:
   - basculer le flux principal vers les endpoints sessions admin (tenant-level).
3. Déplacer le parcours "mes sessions" dans `profile/security`:
   - intégrer la liste self-service sur `/profile/security` (ou vue dédiée profile),
   - supprimer la dépendance UX profil vers `/admin/sessions`.
4. Garder `/admin/sessions` sous contrôle de scope admin (sessions read/revoke tenant).
5. Harmoniser les clients API admin/profile:
   - retirer les fallbacks de shape ambigus;
   - consommer des contrats liste standardisés.
6. Vérifier la subnav admin/profile pour éviter les actions cross-domain non intentionnelles.

### 15.5 Task list Backend (Point 10)

1. Conserver les domaines backend existants (pas de refonte globale d'URI requise).
2. Exposer un contrat frontend-friendly pour les sessions admin:
   - soit adapter le frontend aux endpoints `/admin/tenants/{tenant_id}/sessions*`,
   - soit ajouter une façade `/admin/sessions*` qui résout `tenant_id` depuis le principal.
3. Standardiser les réponses liste admin/profile:
   - `GET /sessions` -> contrat avec noyau `items,total,skip,limit` (extension possible `active_count`);
   - `GET /admin/tenants/{tenant_id}/sessions*` -> même noyau;
   - `GET /vpn/peers` et `GET /vpn/ip-pools` -> ajouter `skip/limit` (ou façade paginée), conserver `items,total`.
4. Ajouter tests d'intégration manquants:
   - `/audit` (list + filtres + tenant isolation),
   - `/admin/tenants/{tenant_id}/sessions*` (list + revoke + anti-escalade + step-up).
5. Vérifier la conformité des permissions sur les flux UI cibles (`users`, `sessions`, `audit`, `vpn`, `features`, `api-keys`).

### 15.6 Task list DB (Point 10)

1. Aucun DDL obligatoire.
2. Optimisation recommandée si volumétrie sessions admin élevée:
   - index partiel `user_sessions(tenant_id, expires_at)` avec filtre `revoked_at IS NULL`.
3. Vérifier la rétention et la volumétrie des `audit_logs` pour les écrans `/admin/audit-logs`.

### 15.7 Validation / tests (Point 10)

1. FE route-level:
   - `/admin` a un comportement explicite;
   - `/admin/*` et `/profile/*` restent accessibles selon permissions.
2. UX sessions:
   - "mes sessions" est géré depuis profile;
   - "sessions tenant" est géré depuis admin.
3. Backend:
   - toutes les listes admin/profile valident le noyau `PaginatedResponse` (`items,total,skip,limit`);
   - tests intégration `/audit` et admin sessions verts.
4. Régression navigation:
   - aucun parcours profil ne dépend d'une route admin pour les actions personnelles.

### 15.8 Definition of Done (Point 10 fermé)

1. `admin` et `profile` sont cohérents sémantiquement et techniquement.
2. `/admin` est explicite (hub/redirect), sans comportement implicite.
3. Sessions personnelles et sessions admin sont séparées sans ambiguïté.
4. Les listes admin/profile respectent le noyau `PaginatedResponse`.
5. Les trous de tests backend (`/audit`, admin sessions) sont fermés.
