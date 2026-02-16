# Plan d'alignement Frontend ↔ Backend — CaroCorp_new (Marveline)

> Date : 2026-02-15
> Scope : Toutes les incohérences entre frontend et backend
> Principe directeur : sécurité > fonctionnalité > esthétique

---

## 1. État des lieux

### 1.1 Chiffres

| Métrique | Valeur |
|---|---|
| Endpoints backend | 82 |
| Appels frontend | ~75 |
| Frontend → backend inexistant | **~30** |
| Backend sans frontend | **~38** |
| Path mismatches | **5** |
| Pages stub (ComingSoon) | **7** |
| Pages réelles implémentées | **14** |

### 1.2 Ce qui fonctionne (vérifié)

- Login / Logout / Token refresh (brute force protection, timing-safe)
- MFA TOTP (setup, verify, recovery codes) — **mais paths frontend incorrects**
- Profil utilisateur (GET + PATCH /users/me)
- Produits CRUD basique (list, get, create, update, delete)
- Catégories CRUD + arborescence
- Bundles CRUD — **mais paths items incorrects côté frontend**
- Réservations CRUD + workflow (confirm, cancel)
- Customers list + get (frontend) / CRUD complet (backend)
- Sessions management (list, revoke, revoke-all)
- Audit logs (list) — backend a aussi user-trail et entity-trail
- API Keys CRUD (backend only, pas de frontend)
- Feature Flags CRUD (backend only, pas de frontend)
- VPN WireGuard proxy (backend only, pas de frontend)
- Invoices CRUD (backend only, pas de frontend)

### 1.3 Ce qui est cassé

| Problème | Type | Sévérité |
|---|---|---|
| MFA : frontend appelle `/mfa/enable`, backend attend `/mfa/verify-setup` | Path mismatch | **P0** |
| MFA : frontend appelle `POST /mfa/disable`, backend attend `DELETE /mfa` | Méthode mismatch | **P0** |
| MFA : frontend appelle `/auth/login/mfa`, backend attend `/mfa/verify` | Path mismatch | **P0** |
| Bundle items : frontend omet `bundle_id` dans le path | Path mismatch | **P1** |
| SecurityPage appelle `/auth/change-password` — endpoint inexistant | Missing endpoint | **P1** |
| RegisterPage appelle `/auth/register` — endpoint inexistant | Missing endpoint | **P1** |
| ForgotPasswordPage / ResetPasswordPage — stubs + backend inexistant | Missing feature | **P2** |
| MFASetupPage appelle `/mfa/backup-codes/regenerate` — inexistant | Missing endpoint | **P2** |
| Inventory movements — 13 appels frontend, 0 endpoint backend | Missing feature | **P2** |
| Admin users — frontend attend CRUD, backend n'a que /users/me | Missing feature | **P2** |
| Product variations/images/stats — frontend appelle, backend n'a pas | Missing feature | **P3** |

---

## 2. Décisions architecturales

### 2.1 Inscription utilisateurs

**Décision : Pas de self-registration. Admin-only.**

Raison : Marveline est un SaaS B2B multi-tenant (gestion événementielle).
L'inscription libre n'a pas de sens — un admin crée les comptes de son équipe.

Actions :
- ~~`POST /auth/register`~~ → Ne PAS créer cet endpoint
- `RegisterPage.tsx` → Supprimer ou convertir en page d'invitation
- Ajouter `POST /users` (admin) et `GET/PATCH/DELETE /users/{id}` (admin)
- `UsersPage.tsx` → Implémenter le CRUD admin (c'est ici qu'on crée des users)

### 2.2 Forgot / Reset password

**Décision : Implémenter — c'est une obligation sécurité.**

Un utilisateur qui ne peut pas reset son password est un utilisateur bloqué.
L'infrastructure email existe (Celery + MailHog en dev, SMTP en prod).

Actions :
- `POST /auth/forgot-password` → génère token signé (HMAC-SHA256), envoie email via Celery
- `POST /auth/reset-password` → valide token, change password, invalide toutes les sessions
- Token : usage unique, TTL 1h, stocké hashé en Redis (pas en DB)
- Rate limit strict : 3 req/15min par email (anti-énumération)
- Réponse toujours 200 (pas de leak "email existe/n'existe pas")
- `ForgotPasswordPage.tsx` → Implémenter le formulaire (remplacer ComingSoon)
- `ResetPasswordPage.tsx` → Implémenter le formulaire (remplacer ComingSoon)

### 2.3 MFA alignment

**Décision : Corriger le frontend pour matcher le backend.**

Le backend a les bons noms (verify-setup, DELETE pour disable, /mfa/verify pour login).
Le frontend a des noms "simplifiés" qui ne matchent pas. On corrige le frontend.

Actions :
- `auth.ts` : `/mfa/enable` → `/mfa/verify-setup`
- `auth.ts` : `POST /mfa/disable` → `DELETE /mfa`
- `auth.ts` : `/auth/login/mfa` → `/mfa/verify`
- Backend : Ajouter `POST /mfa/backup-codes/regenerate` (service MFA le supporte déjà en partie)

### 2.4 Bundle items path

**Décision : Corriger le frontend pour matcher le backend.**

Backend : `PATCH/DELETE /bundles/{bundle_id}/items/{item_id}` (RESTful correct)
Frontend : `PATCH/DELETE /bundles/items/{itemId}` (raccourci incorrect)

Actions :
- `bundles.ts` : Passer `bundleId` + `itemId` dans les fonctions update/delete
- Composants qui appellent ces fonctions : adapter pour fournir `bundleId`

### 2.5 Change password

**Décision : Créer l'endpoint dédié `/auth/change-password`.**

Bien que `PATCH /users/me` supporte `password`, un endpoint dédié est préférable :
- Exige `current_password` (preuve d'identité)
- Audit log spécifique `PASSWORD_CHANGE`
- Invalide toutes les sessions sauf la courante
- Le service `AuthService.change_password()` existe déjà

### 2.6 Inventory movements

**Décision : Implémenter — c'est un module métier core.**

Marveline gère des événements avec du matériel (tables, chaises, déco).
Les mouvements de stock (sorties, retours, inspections) sont au cœur du métier.
Les permissions `INVENTORY_READ` et `INVENTORY_WRITE` existent déjà.

Le frontend `inventory.ts` définit 13 endpoints + types complets — c'est la spec.

### 2.7 Product variations / images / stats

**Décision : Reporter à une phase ultérieure (Phase 5).**

Le modèle Product actuel est simplifié (`image_url` string, pas de variations).
Ajouter variations + images nécessite :
- 2 nouvelles tables + migration
- Nouveaux repositories, services, endpoints
- Refactoring du frontend ProductsPage

C'est un gros chantier qui n'est pas bloquant pour les fonctionnalités core.
On garde le frontend défensif (les appels échoueront gracieusement) et on priorise
les features qui cassent l'expérience utilisateur.

### 2.8 Invoices, VPN, API Keys, Features — frontend

**Décision : Reporter. Backend fonctionne, frontend viendra plus tard.**

Ces modules backend sont fonctionnels et testés. Le frontend peut attendre.
Priorité = corriger ce qui est cassé, pas ajouter du neuf.

---

## 3. Phases d'implémentation

### Phase 1 — Corrections critiques (frontend-only fixes)
**Objectif** : Réparer tout ce qui est cassé sans toucher au backend.
**Scope** : ~5 fichiers frontend, 0 fichier backend.
**Durée estimée** : 1 session.

| # | Tâche | Fichier(s) | Critère de complétude |
|---|---|---|---|
| 1.1 | Fix MFA paths dans auth.ts | `frontend/src/api/auth.ts` | `/mfa/enable` → `/mfa/verify-setup`, `POST /mfa/disable` → `DELETE /mfa`, `/auth/login/mfa` → `/mfa/verify` |
| 1.2 | Fix bundle items paths dans bundles.ts | `frontend/src/api/bundles.ts` | `updateBundleItem(bundleId, itemId, data)`, `deleteBundleItem(bundleId, itemId)` — paths incluent `bundle_id` |
| 1.3 | Adapter composants bundle qui appellent update/delete items | `frontend/src/pages/products/BundlesPage.tsx` + modals | Passe `bundleId` aux fonctions corrigées |
| 1.4 | Supprimer / désactiver RegisterPage | `frontend/src/pages/auth/RegisterPage.tsx`, `App.tsx` | Route `/register` supprimée ou redirige vers `/login`, lien "S'inscrire" retiré de LoginPage |
| 1.5 | Retirer liens vers endpoints produits inexistants | `frontend/src/api/products.ts` | Commenter/supprimer `getFeatured()`, `getStatistics()`, `updateStock()`, variations, images — ou ajouter `// TODO Phase 5` |

**Tests** : Vérifier manuellement dans le navigateur que MFA setup/disable fonctionne, que les bundle items se modifient/suppriment.

---

### Phase 2 — Auth & sécurité backend
**Objectif** : Compléter les fonctions d'authentification manquantes.
**Scope** : ~8 fichiers backend + tests.
**Durée estimée** : 1-2 sessions.
**Dépend de** : Rien (indépendant de Phase 1).

| # | Tâche | Fichier(s) | Critère de complétude |
|---|---|---|---|
| 2.1 | Endpoint `POST /auth/change-password` | `app/api/v1/endpoints/auth.py` | Endpoint existe, exige `current_password` + `new_password`, appelle `AuthService.change_password()`, audit log `PASSWORD_CHANGE`, invalide sessions sauf courante |
| 2.2 | Endpoint `POST /mfa/backup-codes/regenerate` | `app/api/v1/endpoints/mfa.py` | Endpoint existe, exige code TOTP valide, régénère 8 codes, retourne les nouveaux codes, audit log |
| 2.3 | Schema `PasswordResetRequest/Token` | `app/schemas/auth.py` | Schemas Pydantic pour forgot + reset password |
| 2.4 | Service `AuthService.forgot_password()` | `app/services/auth.py` | Génère token HMAC-SHA256, stocke hashé en Redis (TTL 1h), envoie email via Celery |
| 2.5 | Service `AuthService.reset_password()` | `app/services/auth.py` | Valide token, change password, invalide toutes les sessions, supprime token Redis |
| 2.6 | Endpoint `POST /auth/forgot-password` | `app/api/v1/endpoints/auth.py` | Rate limit 3/15min par email, réponse toujours 200, appelle service |
| 2.7 | Endpoint `POST /auth/reset-password` | `app/api/v1/endpoints/auth.py` | Valide token + nouveau password, appelle service |
| 2.8 | Email template reset password | `app/services/notification.py` ou nouveau | Template HTML simple avec lien + TTL |
| 2.9 | Tests | `tests/unit/test_auth_password.py`, `tests/integration/test_auth_endpoints.py` | change-password, forgot, reset — cas nominaux + edge cases (token expiré, token replay, email inexistant) |

**Sécurité** :
- Token reset : HMAC-SHA256(secret + user_id + timestamp), usage unique
- Stockage Redis : `sha256(token)` comme clé → `user_id` comme valeur
- Anti-énumération : même réponse que l'email existe ou non
- Rate limit : `3 req / 15 min / email` + `10 req / 15 min / IP`
- Après reset : invalider TOUTES les sessions + refresh tokens (force re-login)
- Log audit : `PASSWORD_RESET_REQUESTED`, `PASSWORD_RESET_COMPLETED`

---

### Phase 3 — Admin users CRUD
**Objectif** : Permettre aux admins de gérer les utilisateurs de leur tenant.
**Scope** : ~6 fichiers backend + frontend + tests.
**Durée estimée** : 1 session.
**Dépend de** : Rien.

| # | Tâche | Fichier(s) | Critère de complétude |
|---|---|---|---|
| 3.1 | Schema `UserCreate`, `UserUpdate`, `UserListResponse` | `app/schemas/user.py` | Schemas admin pour CRUD users |
| 3.2 | Repository `UserRepository` (si inexistant) | `app/repositories/user.py` | list_by_tenant, get_by_id, create, update, soft_delete — filtré tenant_id |
| 3.3 | Service `UserService` CRUD admin | `app/services/user.py` | create_user (appelle AuthService.create_user), update_user, deactivate_user, list_users — tout filtré tenant_id |
| 3.4 | Endpoints admin users | `app/api/v1/endpoints/users.py` | `GET /users` (USERS_READ), `GET /users/{id}` (USERS_READ), `POST /users` (USERS_ADMIN), `PATCH /users/{id}` (USERS_WRITE), `DELETE /users/{id}` (USERS_ADMIN) — coexiste avec `/users/me` |
| 3.5 | Frontend UsersPage | `frontend/src/pages/admin/UsersPage.tsx` | Tableau users, modals create/edit/delete, rôle dropdown (staff/manager/admin), badge actif/inactif |
| 3.6 | Frontend admin API client | `frontend/src/api/admin.ts` | Fonctions CRUD users alignées sur les endpoints |
| 3.7 | Tests | `tests/integration/test_admin_users.py` | CRUD + isolation tenant (user tenant 1 invisible depuis tenant 2) + permissions (staff ne peut pas créer) |

**Sécurité** :
- `POST /users` : admin-only (`USERS_ADMIN`)
- `DELETE /users/{id}` : admin-only, soft-delete, impossible de se supprimer soi-même
- `PATCH /users/{id}` : manager+ (`USERS_WRITE`), impossible de s'auto-promouvoir admin
- Isolation tenant absolue : `WHERE tenant_id = current_user.tenant_id` sur toute requête
- Un admin ne peut pas modifier un user d'un autre tenant (vérification explicite)
- Audit log : `USER_CREATED`, `USER_UPDATED`, `USER_DEACTIVATED`

---

### Phase 4 — Inventory movements (module métier core)
**Objectif** : Implémenter le tracking des mouvements de stock (sorties, retours, inspections).
**Scope** : ~15 fichiers (model, migration, repo, service, endpoints, tests, frontend).
**Durée estimée** : 2-3 sessions.
**Dépend de** : Rien (indépendant).

#### Étape 4a — Backend models + migration

| # | Tâche | Fichier(s) |
|---|---|---|
| 4a.1 | Model `InventoryMovement` | `app/models/inventory_movement.py` |
| 4a.2 | Model `MovementItem` | `app/models/movement_item.py` |
| 4a.3 | Migration Alembic | `alembic/versions/xxx_add_inventory_movements.py` |
| 4a.4 | `__init__.py` modèles | `app/models/__init__.py` |

**Modèle `InventoryMovement`** :
```
id              BigInteger PK
tenant_id       Integer NOT NULL (TenantMixin)
reference       String(50) UNIQUE per tenant (auto-généré MVT-2026-0001)
movement_type   Enum('outgoing', 'returning', 'transfer', 'inspection')
status          Enum('draft', 'confirmed', 'in_transit', 'completed', 'cancelled')
reservation_id  BigInteger FK → reservations.id (nullable)
scheduled_date  DateTime NOT NULL
completed_date  DateTime (nullable)
notes           Text (nullable)
created_by      BigInteger FK → users.id
is_active       Boolean (SoftDeleteMixin)
created_at      DateTime (TimestampMixin)
updated_at      DateTime (TimestampMixin)
```

**Modèle `MovementItem`** :
```
id                    BigInteger PK
tenant_id             Integer NOT NULL
movement_id           BigInteger FK → inventory_movements.id
product_id            BigInteger FK → products.id (nullable)
product_variation_id  BigInteger (nullable, pour futur Phase 5)
quantity_expected      Integer NOT NULL
quantity_actual        Integer (nullable, rempli au retour/inspection)
condition             Enum('good', 'damaged', 'lost', 'needs_repair') default 'good'
condition_notes       Text (nullable)
is_active             Boolean
created_at            DateTime
updated_at            DateTime
```

Index : `(tenant_id, movement_type)`, `(tenant_id, status)`, `(tenant_id, scheduled_date)`, `(tenant_id, reservation_id)`.

#### Étape 4b — Repository + Service

| # | Tâche | Fichier(s) |
|---|---|---|
| 4b.1 | `MovementRepository` | `app/repositories/movement.py` |
| 4b.2 | `MovementItemRepository` | `app/repositories/movement_item.py` |
| 4b.3 | `MovementService` | `app/services/movement_service.py` |

Repository : list (paginated, filtered), get, create, update, soft_delete, `list_late()`, `list_pending_inspections()`, `get_agenda()`, `get_statistics()`.

Service : orchestration create (auto-référence MVT-YYYY-NNNN via Redis counter), complete movement (met à jour stock produit), cancel, link to reservation.

#### Étape 4c — Endpoints API

| # | Tâche | Fichier(s) |
|---|---|---|
| 4c.1 | Schemas | `app/schemas/movement.py` |
| 4c.2 | Endpoints | `app/api/v1/endpoints/movements.py` |
| 4c.3 | Router | `app/api/v1/__init__.py` |

Endpoints (alignés sur ce que le frontend attend) :
```
GET    /inventory-movements                    (INVENTORY_READ)
GET    /inventory-movements/late               (INVENTORY_READ)
GET    /inventory-movements/pending-inspections (INVENTORY_READ)
GET    /inventory-movements/agenda             (INVENTORY_READ)
GET    /inventory-movements/statistics         (INVENTORY_READ)
GET    /inventory-movements/{id}               (INVENTORY_READ)
POST   /inventory-movements                    (INVENTORY_WRITE)
PATCH  /inventory-movements/{id}               (INVENTORY_WRITE)
DELETE /inventory-movements/{id}               (INVENTORY_WRITE)
PATCH  /inventory-movements/{id}/complete      (INVENTORY_WRITE)
POST   /inventory-movements/{movement_id}/items     (INVENTORY_WRITE)
PATCH  /inventory-movements/items/{item_id}         (INVENTORY_WRITE)
DELETE /inventory-movements/items/{item_id}         (INVENTORY_WRITE)
```

#### Étape 4d — Frontend

| # | Tâche | Fichier(s) |
|---|---|---|
| 4d.1 | MovementsPage réelle | `frontend/src/pages/inventory/MovementsPage.tsx` |
| 4d.2 | Composants modals | `frontend/src/pages/inventory/components/` |

Le fichier `frontend/src/api/inventory.ts` existe déjà avec tous les types et appels.
Il faut implémenter la page qui les consomme.

#### Étape 4e — Tests

| # | Tâche | Fichier(s) |
|---|---|---|
| 4e.1 | Tests unitaires service | `tests/unit/test_movement_service.py` |
| 4e.2 | Tests intégration endpoints | `tests/integration/test_movement_endpoints.py` |
| 4e.3 | Tests isolation tenant | `tests/integration/test_movement_tenant_isolation.py` |

**Sécurité** :
- Isolation tenant stricte sur mouvements ET items
- `complete` : met à jour `available_quantity` sur Product (transaction atomique)
- Référence auto-générée (pas de saisie utilisateur → pas d'injection)
- Audit log : `MOVEMENT_CREATED`, `MOVEMENT_COMPLETED`, `MOVEMENT_CANCELLED`
- Un mouvement `completed` ne peut plus être modifié (immutabilité)

---

### Phase 5 — Product enhancements (variations, images, stats)
**Objectif** : Enrichir le catalogue produits.
**Scope** : ~12 fichiers.
**Durée estimée** : 2 sessions.
**Dépend de** : Phase 4 (MovementItem.product_variation_id FK).

#### Étape 5a — Models + migration

| # | Tâche | Fichier(s) |
|---|---|---|
| 5a.1 | Model `ProductVariation` | `app/models/product_variation.py` |
| 5a.2 | Model `ProductImage` | `app/models/product_image.py` |
| 5a.3 | Migration | `alembic/versions/xxx_add_product_variations_images.py` |

**ProductVariation** : id, tenant_id, product_id FK, name, sku, price_override (nullable), stock_quantity, is_active.
**ProductImage** : id, tenant_id, product_id FK, url, alt_text, sort_order, is_primary, is_active.

#### Étape 5b — Backend (repo, service, endpoints)

| # | Tâche | Fichier(s) |
|---|---|---|
| 5b.1 | Repository + Service variations | `app/repositories/product_variation.py`, `app/services/product_service.py` |
| 5b.2 | Repository + Service images | `app/repositories/product_image.py`, `app/services/product_service.py` |
| 5b.3 | Endpoints variations | `app/api/v1/endpoints/products.py` (ajout) |
| 5b.4 | Endpoints images | `app/api/v1/endpoints/products.py` (ajout) |
| 5b.5 | Endpoint `GET /products/featured` | `app/api/v1/endpoints/products.py` |
| 5b.6 | Endpoint `GET /products/statistics` | `app/api/v1/endpoints/products.py` |
| 5b.7 | Endpoint `PATCH /products/{id}/stock` | `app/api/v1/endpoints/products.py` |

#### Étape 5c — Frontend + Tests

| # | Tâche | Fichier(s) |
|---|---|---|
| 5c.1 | Réactiver appels dans products.ts | `frontend/src/api/products.ts` |
| 5c.2 | UI variations dans ProductFormModal | Composants existants |
| 5c.3 | UI galerie images | Composants existants |
| 5c.4 | Tests | `tests/integration/test_product_variations.py`, `tests/integration/test_product_images.py` |

---

### Phase 6 — Forgot/Reset password + frontend auth
**Objectif** : Compléter le flow de récupération de compte.
**Scope** : ~6 fichiers.
**Durée estimée** : 1 session.
**Dépend de** : Phase 2 (backend auth).

| # | Tâche | Fichier(s) |
|---|---|---|
| 6.1 | ForgotPasswordPage réelle | `frontend/src/pages/auth/ForgotPasswordPage.tsx` |
| 6.2 | ResetPasswordPage réelle | `frontend/src/pages/auth/ResetPasswordPage.tsx` |
| 6.3 | Frontend auth.ts : forgot + reset | `frontend/src/api/auth.ts` |
| 6.4 | Test e2e flow complet | Manuel ou Playwright |

---

### Phase 7 — Pages secondaires (agenda, dashboard, customers)
**Objectif** : Compléter les pages existantes mais incomplètes.
**Scope** : ~8 fichiers frontend.
**Durée estimée** : 1-2 sessions.
**Dépend de** : Phases 1-4.

| # | Tâche | Fichier(s) |
|---|---|---|
| 7.1 | Customers : ajouter create/update/delete au frontend | `frontend/src/api/customers.ts`, pages |
| 7.2 | AgendaPage : calendrier réservations | `frontend/src/pages/agenda/AgendaPage.tsx` |
| 7.3 | DashboardPage : enrichir avec stats | `frontend/src/pages/dashboard/DashboardPage.tsx` |
| 7.4 | Audit : exploiter user-trail et entity-trail | `frontend/src/pages/admin/AuditLogsPage.tsx` |

---

### Phase 8 — Frontend modules admin (si besoin)
**Objectif** : Créer les pages frontend pour les modules backend-only.
**Scope** : Variable.
**Durée estimée** : 2-3 sessions.

| Module | Backend | Frontend à créer | Priorité |
|---|---|---|---|
| Invoices (7 endpoints) | Complet | Page factures + client API | Moyenne |
| VPN (13 endpoints) | Complet (proxy WG) | Page admin VPN | Basse |
| API Keys (6 endpoints) | Complet | Page gestion clés M2M | Basse |
| Feature Flags (6 endpoints) | Complet | Page feature toggles | Basse |
| Finances | Inexistant | Lien sidebar → à définir | Basse |

---

## 4. Ordre d'exécution recommandé

```
Phase 1 (frontend fixes)     ─── Session 1
    │
    ├── Phase 2 (auth backend)    ─── Sessions 2-3  (parallélisable)
    │       │
    │       └── Phase 6 (auth frontend forgot/reset) ─── Session 6
    │
    ├── Phase 3 (admin users)     ─── Session 4  (parallélisable)
    │
    └── Phase 4 (inventory)       ─── Sessions 5-7
            │
            └── Phase 5 (product enhancements) ─── Sessions 8-9
                    │
                    └── Phase 7 (pages secondaires) ─── Sessions 10-11
                            │
                            └── Phase 8 (admin frontend) ─── Sessions 12+
```

Les phases 2, 3 et 4 sont indépendantes et peuvent être entrelacées.
Phase 1 est prioritaire car elle corrige des bugs visibles.

---

## 5. Règles transversales (rappel CLAUDE.md)

### Sécurité
- [ ] Chaque endpoint a une permission RBAC vérifiée
- [ ] Chaque requête filtre par `tenant_id` (violation = P0)
- [ ] Aucun secret hardcodé, aucun token en log
- [ ] Rate limiting sur endpoints sensibles (auth, password)
- [ ] Audit log sur toute action sensible
- [ ] Validation input (Pydantic) + sanitization (SecurityValidators)

### Tests
- [ ] Tests unitaires service pour chaque feature
- [ ] Tests intégration endpoints (happy path + erreurs)
- [ ] Tests isolation tenant (cross-tenant = P0)
- [ ] Fichier `tests/test_*.py` doit exister (Règle 3 CLAUDE.md)
- [ ] Commande Docker : `docker compose run --rm --no-deps --entrypoint "" api python -m pytest tests/ -v`

### Processus
- [ ] Max 2 features par session (Règle 2)
- [ ] TaskCreate avant de coder (Règle 4)
- [ ] Checkpoint tous les 3 fichiers (Règle 5)
- [ ] MEMORY.md mis à jour avec chemins vérifiés (Règle 7)
- [ ] Context Engine : `prepare()` avant chaque Edit .py

### Conventions
- [ ] Montants en BigInteger centimes
- [ ] Soft delete via `is_active`
- [ ] Timestamps via mixins
- [ ] Constantes dans `app/constants/` (pas de strings magiques)
- [ ] Exceptions : `NotFound` (pas `NotFoundError`)
- [ ] Migrations expand/contract uniquement

---

## 6. Risques identifiés

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Forgot-password : enumération d'emails | Haute | Moyen | Réponse toujours 200 + rate limit |
| Admin users : escalade de privilèges | Moyenne | Critique | Interdiction auto-promotion, vérif backend |
| Inventory complete : désync stock | Moyenne | Élevé | Transaction atomique DB, pas de cache stock |
| Product variations : migration lourde | Basse | Moyen | Migration expand-only, pas de DROP |
| MFA path fix : régression frontend | Basse | Élevé | Tester manuellement chaque flow MFA |
| Bundle items fix : régression | Basse | Moyen | Vérifier que bundleId est toujours disponible dans le composant |

---

## 7. Métriques de succès (fin de toutes les phases)

| Métrique | Actuel | Cible |
|---|---|---|
| Frontend → backend inexistant | ~30 | 0 |
| Path mismatches | 5 | 0 |
| Pages stub | 7 | 2 max (VPN, Features — admin-only) |
| Endpoints backend sans frontend | ~38 | ~20 (modules admin optionnels) |
| Tests intégration | ~1300 | ~1500+ |
| Couverture modules critiques | ? | 80%+ |

---

## 8. Fichiers de référence

| Fichier | Rôle |
|---|---|
| `app/core/permissions.py` | RBAC — toutes les permissions définies |
| `app/constants/security.py` | Constantes sécurité (Redis, brute force, MFA, sessions) |
| `app/api/v1/__init__.py` | Routeur principal — tous les routers inclus |
| `frontend/src/api/auth.ts` | Client API auth — source des paths frontend |
| `frontend/src/api/inventory.ts` | Client API inventory — spec complète des endpoints attendus |
| `frontend/src/api/bundles.ts` | Client API bundles — paths à corriger |
| `tests/conftest.py` | Fixtures DB + auth — pattern SAVEPOINT |
| `CLAUDE.md` | Conventions et règles du projet |
| `~/.claude/CLAUDE.md` | Règles globales discipline de travail |
