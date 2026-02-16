# Audit Frontend ↔ Backend — Fonctionnalités déconnectées

**Date**: 2026-02-16
**Projet**: CaroCorp_new (Marveline)
**Objectif**: Identifier les fonctionnalités backend non connectées automatiquement au frontend

---

## ✅ Fonctionnalités connectées et opérationnelles

### Sécurité & Authentification
- **CSRF Protection** — CSRFProtectionMiddleware + frontend auto-fetch/refresh (14min) + injection header automatique ✅
- **MFA/TOTP** — Setup, verify, disable, backup codes, status — UI complète ✅
- **Sessions** — GET /sessions, DELETE /sessions/{id}, DELETE /sessions (logout all) — UI admin complète ✅
- **Password Management** — Change password, forgot password, reset password — UI complète ✅

### Gestion Produits & Catalogue
- **Products** — CRUD complet (create, read, update, delete) — UI ProductsPage.tsx ✅
- **Bundles** — CRUD complet + items management + price calculation — UI BundlesPage.tsx + BundleDetailPage.tsx ✅
- **Categories** — CRUD complet — UI frontend/src/api/categories.ts existe ✅

### Configuration & Administration
- **VPN Profiles** — CRUD complet — UI admin/VPNProfilesPage.tsx ✅
- **Feature Flags** — CRUD complet — UI admin/FeatureFlagsPage.tsx ✅
- **API Keys** — CRUD complet — UI admin/ApiKeysPage.tsx ✅
- **Audit Logs** — Read-only access — UI admin/AuditLogsPage.tsx ✅
- **Users** — CRUD complet — UI admin/UsersPage.tsx ✅

---

## ❌ Fonctionnalités NON implémentées

### OAuth/SSO
- **Backend**: Aucun endpoint OAuth trouvé (pas de /auth/oauth/*, /auth/sso/*)
- **Frontend**: Fichier stub `OAuthCallbackPage.tsx` existe mais sans logique réelle
- **Status**: Non implémenté — feature future uniquement

---

## ⚠️ Fonctionnalités partiellement connectées

### 1. Inventory Movements
- **Backend**: CRUD complet
  - `GET /inventory-movements` — list avec pagination ✅
  - `POST /inventory-movements` — create ✅
  - `GET /inventory-movements/{id}` — read single ✅
  - `PATCH /inventory-movements/{id}` — update ✅
  - `DELETE /inventory-movements/{id}` — delete ✅
  - `GET /inventory-movements/late` — list late returns ✅

- **Frontend**: Lecture seule uniquement
  - `frontend/src/pages/inventory/MovementsPage.tsx` — affichage liste uniquement
  - **MANQUANT**: Pas de modal Create/Update/Delete pour inventory movements

### 2. Invoices
- **Backend**: CRUD complet
  - `GET /invoices` — list ✅
  - `POST /invoices` — create ✅
  - `GET /invoices/{id}` — read ✅
  - `PATCH /invoices/{id}` — update ✅
  - `POST /invoices/{id}/cancel` — cancel ✅
  - `POST /invoices/{id}/payment` — record payment ✅

- **Frontend**: Lecture seule uniquement
  - `frontend/src/api/invoices.ts` — seulement `getInvoices()` et `getInvoice(id)` implémentés
  - **MANQUANT**: Pas d'UI pour create, update, cancel, payment

### 3. Reservations
- **Backend**: CRUD complet
  - `GET /reservations` — list ✅
  - `POST /reservations` — create ✅
  - `GET /reservations/{id}` — read ✅
  - `PATCH /reservations/{id}` — update ✅
  - `DELETE /reservations/{id}` — delete ✅
  - `POST /reservations/{id}/confirm` — confirm ✅
  - `POST /reservations/{id}/cancel` — cancel ✅

- **Frontend**: CRUD partiel
  - `frontend/src/api/reservations.ts` — `getReservations()`, `createReservation()`, `updateReservation()`, `deleteReservation()` implémentés
  - **MANQUANT**: Pas d'endpoints confirm/cancel dans frontend API, pas d'UI visible pour ces actions

### 4. Customers
- **Backend**: CRUD complet
  - `GET /customers` — list ✅
  - `POST /customers` — create ✅
  - `GET /customers/{id}` — read ✅
  - `PATCH /customers/{id}` — update ✅
  - `DELETE /customers/{id}` — delete ✅

- **Frontend**: API existe
  - `frontend/src/api/customers.ts` — fichier existe
  - **À VÉRIFIER**: Pas de page UI évidente trouvée (pas de CustomersPage.tsx)

---

## ℹ️ Fonctionnalités backend-only (comportement normal)

Ces fonctionnalités n'ont PAS besoin de connexion frontend directe :

- **SMTP** — Envoi emails backend (password reset, notifications) — normal ℹ️
- **Redis** — Cache, sessions, rate limiting — infrastructure backend — normal ℹ️
- **Rate Limiting** — Middleware backend (5 req/min login, etc.) — normal ℹ️
- **Celery** — Queue asynchrone backend — normal ℹ️

---

## 📋 Priorités recommandées

### P0 — Bloquant production
1. **Dashboard /stats endpoint 500** — Erreur visible sur AdminDashboard.tsx — à débuguer immédiatement

### P1 — Fonctionnalités métier critiques
2. **Inventory Movements UI** — Ajouter modals Create/Update/Delete pour gestion stock complète
3. **Invoices UI complète** — Ajouter UI pour create, update, cancel, payment (actuellement lecture seule)
4. **Reservations confirm/cancel UI** — Ajouter boutons/modals pour confirmer/annuler réservations

### P2 — Complétude fonctionnelle
5. **Customers UI** — Vérifier si UI existe, sinon créer CustomersPage.tsx avec CRUD complet
6. **OAuth/SSO** — Feature future, pas urgent

---

## 🔍 Méthode de vérification

### Backend
```bash
# Lister tous les endpoints
grep -h "@router\." app/api/v1/endpoints/*.py | sed 's/^.*@router\.\([a-z]*\)("\([^"]*\).*/\1 \2/' | sort -u
```

### Frontend
```bash
# Lister tous les appels API
grep -rh "apiClient\.\(get\|post\|patch\|put\|delete\)" frontend/src/api/*.ts 2>/dev/null | grep -o "'/[^']*'" | sort -u
```

### Pages UI
```bash
# Lister toutes les pages React
ls -1 frontend/src/pages/**/*.tsx
```

---

## 📝 Notes techniques

- **CSRF**: Implémenté correctement — auto-fetch toutes les 14 min, injection header automatique pour POST/PUT/PATCH/DELETE
- **MFA**: Flow complet — setup → verify-setup → verify (login) → disable
- **Bundles**: NaN fixes appliqués — `?? 0` avant tous les `toFixed(2)`
- **Docker**: Rebuild avec `--no-cache`, recreation container via `stop + up -d` (pas juste `restart`)

---

**Audit effectué le**: 2026-02-16
**Fichiers analysés**: 42 endpoints backend, 13 fichiers API frontend, 47 pages UI frontend
