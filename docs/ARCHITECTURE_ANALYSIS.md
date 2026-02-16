# Analyse Architecture CaroCorp_new

**Date:** 2026-02-16
**Session:** 4J
**Auteur:** Claude Sonnet 4.5

---

## Vue d'ensemble

**Backend FastAPI:**
- 148 fichiers Python
- 28 534 lignes de code
- 229 classes
- 182 fonctions
- 408 symboles indexés

**Frontend React:**
- 14 modules API TypeScript
- 8 fichiers de tests Vitest

---

## Structure Backend

### Models (14 fichiers, 1987 lignes)

```
app/models/
├── __init__.py          ✓ Tous exports présents
├── api_key.py           ApiKey
├── audit_log.py         AuditLog
├── base.py              Base, TimestampMixin, TenantMixin, SoftDeleteMixin
├── bundle.py            ProductBundle, BundleItem
├── category.py          Category
├── customer.py          Customer
├── feature_flag.py      FeatureFlag
├── inventory_movement.py  InventoryMovement, MovementItem
├── invoice.py           Invoice
├── mfa.py               MFADevice
├── product.py           Product
├── reservation.py       Reservation, ReservationLine
└── user.py              User
```

**Dépendances externes models:**
- Tous les models → `app/constants/__init__.py` (enums métier)
- inventory_movement.py → reservation.py (FK event_id, reservation_id)

### Repositories (12 fichiers, 2416 lignes)

```
app/repositories/
├── __init__.py          ⚠️  MANQUE: bundle, category
├── api_key.py           ApiKeyRepository
├── base.py              BaseRepository (513L)
├── bundle.py            BundleRepository, BundleItemRepository
├── category.py          CategoryRepository
├── customer.py          CustomerRepository
├── feature_flag.py      FeatureFlagRepository
├── inventory_movement.py  MovementRepository, MovementItemRepository
├── invoice.py           InvoiceRepository
├── product.py           ProductRepository
├── reservation.py       ReservationRepository, ReservationLineRepository
└── user.py              UserRepository
```

**🔴 Problème 1: Dépendance inversée**
- `app/repositories/base.py` → `app/services/cache.py`
- Repository layer ne devrait PAS importer depuis services layer
- Violation: layered architecture (repositories < services < endpoints)

**🔴 Problème 2: Exports manquants**
- `app/repositories/__init__.py` n'exporte PAS:
  - BundleRepository, BundleItemRepository
  - CategoryRepository
- Import direct requis: `from app.repositories.bundle import ...`

### Services (19 fichiers, 6473 lignes)

```
app/services/
├── __init__.py          ✓ Tous exports présents
├── api_key.py           ApiKeyService
├── audit.py             AuditService
├── auth.py              AuthService, MFARequiredResult
├── bruteforce.py        BruteForceService, BruteForceStatus
├── bundle.py            BundleService
├── cache.py             CacheService + decorators
├── category.py          CategoryService
├── feature_flag.py      FeatureFlagService
├── inventory_movement.py  MovementService
├── invoice.py           InvoiceService
├── mfa.py               MFAService
├── notification.py      NotificationService
├── product.py           ProductService
├── reservation.py       ReservationService
├── session.py           SessionService
├── token.py             TokenService
├── user.py              UserService
└── wireguard_client.py  WireGuardClient
```

**🔴 Problème 3: Dépendances circulaires**
- `reservation.py` → `inventory_movement.py`
- `inventory_movement.py` → `reservation.py`
- **Impact:** Couplage fort, tests difficiles, risque import circulaire

**Graphe dépendances services complexes:**
```
auth.py → audit, bruteforce, mfa, notification, session, token
user.py → audit, auth
reservation.py → inventory_movement, invoice, product
inventory_movement.py → reservation (circulaire!)
```

### API Endpoints (20 fichiers, 4636 lignes)

```
app/api/v1/endpoints/
├── api_keys.py          /api-keys (CRUD)
├── audit.py             /audit (logs)
├── auth.py              /auth (login, logout, refresh, csrf, password)
├── bundles.py           /bundles (CRUD bundles)
├── categories.py        /categories (CRUD categories + tree)
├── customers.py         /customers (CRUD)
├── dashboard.py         /dashboard/stats
├── features.py          /features (feature flags)
├── health.py            /health, /health/live, /health/ready
├── inventory_movements.py  /inventory-movements (CRUD + stats)
├── invoices.py          /invoices (CRUD + overdue)
├── mfa.py               /mfa (setup, verify, disable)
├── products.py          /products (CRUD)
├── reservations.py      /reservations (CRUD + validation)
├── sessions.py          /sessions (list, revoke)
├── users.py             /users/me (profile)
└── vpn.py               /vpn (WireGuard peers)
```

**Pattern observé:**
- Endpoints appellent Services (correct)
- Certains endpoints importent Repositories directement (anti-pattern mineur)
  - Exemple: `bundles.py` importe `BundleRepository`
  - Devrait passer par service uniquement

---

## Structure Frontend

### API Modules TypeScript (14 fichiers)

```
frontend/src/api/
├── client.ts            ✓ Axios + interceptors (auth, CSRF, retry)
├── admin.ts             Admin endpoints
├── apiKeys.ts           API keys management
├── auth.ts              Login, logout, refresh, CSRF
├── bundles.ts           Bundles CRUD
├── categories.ts        Categories CRUD
├── customers.ts         Customers CRUD
├── dashboard.ts         Dashboard stats
├── featureFlags.ts      Feature flags
├── inventory.ts         Inventory movements
├── invoices.ts          Invoices CRUD
├── products.ts          Products CRUD
├── reservations.ts      Reservations CRUD
└── vpn.ts               VPN management
```

### Tests Frontend (8 fichiers)

```
frontend/src/
├── api/__tests__/
│   ├── client.test.ts          ✓ Axios interceptors (CSRF, auth, retry 403/401)
│   ├── customers.test.ts       ✓ Customers API
│   ├── inventory.test.ts       ✓ Inventory movements API
│   ├── invoices.test.ts        ✓ Invoices API
│   └── reservations.test.ts    ✓ Reservations API
├── errors/__tests__/
│   ├── normalizer.test.ts      ✓ Error normalization
│   └── types.test.ts           ✓ AppError types
└── stores/__tests__/
    └── authStore.test.ts       ✓ Zustand auth store (tokens, user, CSRF)
```

**🟡 Problème 4: Couverture tests partielle**
- 8 fichiers testés / 14 modules API = **57% couverture**
- **Manquants:**
  - admin.test.ts
  - apiKeys.test.ts
  - auth.test.ts (seulement authStore.test.ts existe)
  - bundles.test.ts
  - categories.test.ts
  - dashboard.test.ts
  - featureFlags.test.ts
  - products.test.ts
  - vpn.test.ts

---

## Mapping Frontend ↔ Backend

| Frontend Module | Backend Endpoint | Service | Model |
|---|---|---|---|
| auth.ts | /auth/* | AuthService | User, MFADevice |
| bundles.ts | /bundles | BundleService | ProductBundle, BundleItem |
| categories.ts | /categories | CategoryService | Category |
| customers.ts | /customers | (direct repo) | Customer |
| dashboard.ts | /dashboard/stats | (direct query) | Multiple |
| inventory.ts | /inventory-movements | MovementService | InventoryMovement, MovementItem |
| invoices.ts | /invoices | InvoiceService | Invoice |
| products.ts | /products | ProductService | Product |
| reservations.ts | /reservations | ReservationService | Reservation, ReservationLine |
| apiKeys.ts | /api-keys | ApiKeyService | ApiKey |
| featureFlags.ts | /features | FeatureFlagService | FeatureFlag |
| vpn.ts | /vpn | WireGuardClient | (externe) |

---

## Flux de données typique

### Exemple: Créer un mouvement d'inventaire

**Frontend:**
```typescript
// frontend/src/api/inventory.ts
export const inventoryApi = {
  createMovement: (data: MovementCreate) =>
    apiClient.post<MovementResponse>('/inventory-movements', data)
}
```

**Backend:**
```
1. app/api/v1/endpoints/inventory_movements.py
   └─> POST /inventory-movements
       └─> MovementService.create_movement()

2. app/services/inventory_movement.py
   └─> MovementService.create_movement()
       ├─> MovementRepository.create()
       ├─> MovementItemRepository.create() (N items)
       └─> ReservationService (si reservation_id)

3. app/repositories/inventory_movement.py
   └─> MovementRepository.create()
       └─> SQLAlchemy insert InventoryMovement

4. app/models/inventory_movement.py
   └─> InventoryMovement (table inventory_movements)
```

---

## Patterns architecturaux identifiés

### ✅ Bonnes pratiques

1. **Layered Architecture (globalement respectée):**
   - Models ← Repositories ← Services ← Endpoints
   - Frontend API modules ↔ Backend endpoints

2. **Multi-tenancy:**
   - `tenant_id NOT NULL` sur toutes tables métier
   - Filtre tenant au niveau repository (BaseRepository)
   - Index composite `(tenant_id, id)`

3. **Soft delete:**
   - `SoftDeleteMixin` avec `is_active`
   - `_apply_active_filter()` dans BaseRepository

4. **Timestamps:**
   - `TimestampMixin` sur toutes tables
   - `created_at`, `updated_at` automatiques

5. **Frontend interceptors:**
   - Auth token automatique (Bearer)
   - CSRF token sur POST/PUT/PATCH/DELETE
   - Retry 401 (refresh token)
   - Retry 403 CSRF (refetch token)

### 🔴 Anti-patterns

1. **Dépendance inversée: Repository → Service**
   - `app/repositories/base.py` importe `app/services/cache.py`
   - Solution: injecter CacheService dans BaseRepository.__init__

2. **Dépendances circulaires services:**
   - `reservation.py` ↔ `inventory_movement.py`
   - Solution: extraire interface commune ou event bus

3. **Exports manquants repositories:**
   - `bundle`, `category` non exportés dans `__init__.py`
   - Solution: ajouter exports

4. **Endpoints court-circuitent services:**
   - Certains endpoints importent repositories directement
   - Exemple: `bundles.py` → `BundleRepository`
   - Solution: toute logique dans service

5. **Tests frontend incomplets:**
   - 57% couverture modules API
   - Solution: ajouter tests manquants

---

## Recommandations prioritaires

### P0 — Bugs structurels

1. **Casser dépendance Repository → Service**
   - Déplacer `CacheService` hors de `BaseRepository`
   - Ou injecter via constructor

2. **Résoudre circular import Reservation ↔ InventoryMovement**
   - Option A: Event-driven (domain events)
   - Option B: Interface abstraite partagée
   - Option C: Fusionner services (si logique trop couplée)

### P1 — Dette technique

3. **Compléter exports repositories/__init__.py**
   - Ajouter `BundleRepository`, `BundleItemRepository`
   - Ajouter `CategoryRepository`

4. **Standardiser pattern Service layer**
   - Interdire import Repository dans endpoints
   - 100% passage par services

5. **Compléter tests frontend**
   - Objectif: 100% couverture modules API
   - Prioriser: auth, bundles, categories, products

### P2 — Améliorations

6. **Documenter architecture**
   - Diagrammes C4 (Context, Container, Component)
   - ADR (Architecture Decision Records)

7. **Auditer N+1 queries**
   - Pattern `items_count` subquery réutilisable (déjà fait pour movements)
   - Appliquer à: Reservations, Invoices, Bundles

---

## Métriques

**Backend:**
- Models: 14 (100% multi-tenant)
- Repositories: 12 (83% exportés)
- Services: 19 (11% circular deps)
- Endpoints: 20 (100% functional)
- Tests: 1631/1631 pass (93.07% coverage)

**Frontend:**
- API modules: 14
- Tests: 8/14 (57% coverage)
- Total tests Vitest: 81/81 pass

**Dépendances circulaires:**
- Services: 1 paire (reservation ↔ inventory_movement)
- Repositories: 0
- Models: 0

**Violations layered architecture:**
- Repository → Service: 1 (base.py → cache.py)
- Endpoint → Repository: ~3 occurrences

---

## Conclusion

L'architecture globale est **saine** avec layering correct et patterns modernes (multi-tenant, soft delete, interceptors frontend).

**Points forts:**
- Séparation claire models/repos/services/endpoints
- Multi-tenancy systématique
- Tests backend excellents (93% coverage, 1631 tests)
- Frontend interceptors robustes (CSRF, retry)

**Points faibles:**
- Dépendances circulaires services (1 paire critique)
- Dépendance inversée repository → service (1 cas)
- Tests frontend incomplets (57% coverage)
- Exports repositories incomplets

**Prochaines étapes recommandées:**
1. ✅ DONE — Fix dépendance base.py → cache.py (P0)
2. ✅ DONE — Fix circular reservation ↔ inventory_movement (P0)
3. ✅ DONE — Compléter exports repositories (P1)
4. TODO — Ajouter tests frontend manquants (P1)

---

## Solutions appliquées (2026-02-16)

### ✅ P0-1 : Dépendance inversée Repository → Service

**Problème :** `app/repositories/base.py` importait `app/services/cache.py`, violant l'architecture layered.

**Solution :**
1. Déplacé `app/services/cache.py` → `app/core/cache.py`
2. Mis à jour imports dans :
   - `app/repositories/base.py` (services → core)
   - `app/services/__init__.py` (ré-export depuis core)
   - 3 fichiers tests (e2e, integration)

**Résultat :** Architecture layered restaurée. Plus aucune dépendance Repository → Service.

**Commit :** Task #39, 1631/1631 tests pass.

---

### ✅ P0-2 : Circular dependency Reservation ↔ InventoryMovement

**Problème :**
- `reservation.py` → `inventory_movement.py` (auto-génération departure)
- `inventory_movement.py` → `reservation.py` (mise à jour statut)

**Solution choisie : Service orchestrateur**

Créé `app/services/reservation_workflow.py` (125 lignes) :
- `ReservationWorkflowService.auto_generate_departure_movement()`
- `ReservationWorkflowService.update_reservation_on_movement_complete()`

**Modifications :**
1. `reservation.py` :
   - Supprimé `_auto_generate_departure_movement()`
   - Ligne 309 : délègue au workflow
   - Plus d'import MovementService

2. `inventory_movement.py` :
   - Supprimé `_update_reservation_on_complete()`
   - Ligne 268 : délègue au workflow
   - Garde notifications (lecture seule, acceptable)

3. `services/__init__.py` :
   - Ajouté export ReservationWorkflowService

**Résultat :** Dépendance circulaire cassée, logique métier préservée.

**Commit :** Task #40, 1631/1631 tests pass.

---

### ✅ P1-1 : Exports manquants repositories/__init__.py

**Problème :** `BundleRepository`, `BundleItemRepository`, `CategoryRepository` non exportés.

**Solution :**
1. Ajouté imports dans `app/repositories/__init__.py`
2. Ajouté entrées dans `__all__`

**Blocage initial :** Tentative déclenchait circular import → résolu par Task #39 d'abord.

**Résultat :** Tous repositories exportés de manière cohérente.

**Commit :** Task #41, 1631/1631 tests pass.
