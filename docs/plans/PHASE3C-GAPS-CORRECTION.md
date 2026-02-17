# Phase 3C — Correction Gaps Identifiés

**Date création** : 2026-02-16
**Source** : Context-engine scan + ANALYSE_*.md
**Priorité** : P0 (E2E tests + missing endpoint) → P1 (RESTful consistency)

---

## 📋 Résumé Gaps

### P0 — Critique
1. **E2E Tests Manquants** : 0 tests pour CSRF flow, MFA flow, session expiration
2. **Frontend Endpoint Manquant** : `cancelInvoice()` absent de `frontend/src/api/invoices.ts`

### P1 — Important
3. **RESTful Inconsistency** : Inventory items endpoints pattern mixé (nested POST vs flat PATCH/DELETE)

---

## 🎯 Stratégie de Correction

### Découpage en Sessions (Règle #2: Max 2 features/session)

**Session 3C-1** : E2E Tests CSRF + MFA (2 features)
**Session 3C-2** : E2E Tests Sessions + Frontend cancelInvoice (2 features)
**Session 3C-3** : RESTful Refactoring Inventory Items (1 feature, breaking change)

---

## 📝 Session 3C-1 — E2E Tests CSRF + MFA

### Objectif
Couvrir les flows critiques CSRF et MFA avec tests E2E Playwright.

### Pré-requis
- ☐ Playwright installé et configuré (`npx playwright install`)
- ☐ Backend running (docker-compose up)
- ☐ Test user avec MFA activé existe en DB

### Tasks Détaillées

#### Task 3C-1.1 : Setup Playwright
**Critères de complétude VÉRIFIABLES** :
- ☐ Fichier `frontend/playwright.config.ts` existe
- ☐ Fichier `frontend/package.json` contient `@playwright/test` dans devDependencies
- ☐ Dossier `frontend/tests/e2e/` créé
- ☐ Fichier `frontend/tests/e2e/setup.ts` existe (helpers login, logout, etc.)
- ☐ Script `"test:e2e": "playwright test"` dans package.json
- ☐ Commande `npm run test:e2e` execute sans erreur (même 0 tests)

**Fichiers à créer** :
```
frontend/
├── playwright.config.ts
└── tests/
    └── e2e/
        ├── setup.ts
        ├── csrf.spec.ts (next task)
        └── mfa.spec.ts (next task)
```

**Checkpoint** : Après création config + setup.ts (2 fichiers)

#### Task 3C-1.2 : E2E CSRF Flow
**Critères de complétude VÉRIFIABLES** :
- ☐ Fichier `frontend/tests/e2e/csrf.spec.ts` existe
- ☐ Minimum 5 tests dans le fichier :
  1. ☐ Test "doit auto-fetch CSRF token au mount de App.tsx"
  2. ☐ Test "doit inclure X-CSRF-Token header dans POST requests"
  3. ☐ Test "doit renouveler token si 403 CSRF error"
  4. ☐ Test "doit retry request après renouvellement token"
  5. ☐ Test "doit afficher toast error si CSRF renewal échoue"
- ☐ Commande `npm run test:e2e -- csrf.spec.ts` passe 5/5 tests
- ☐ Backend logs montrent `GET /csrf-token` appelé au moins 2 fois pendant test suite

**Fichiers à modifier** :
- `frontend/tests/e2e/csrf.spec.ts` (création)

**Checkpoint** : Après 5 tests CSRF (1 fichier, milestone important)

#### Task 3C-1.3 : E2E MFA Flow
**Critères de complétude VÉRIFIABLES** :
- ☐ Fichier `frontend/tests/e2e/mfa.spec.ts` existe
- ☐ Minimum 6 tests dans le fichier :
  1. ☐ Test "doit setup MFA et afficher QR code"
  2. ☐ Test "doit enable MFA avec code TOTP valide"
  3. ☐ Test "doit rejeter code TOTP invalide"
  4. ☐ Test "doit require MFA à login si enabled"
  5. ☐ Test "doit obtenir access token après MFA verify success"
  6. ☐ Test "doit disable MFA avec mot de passe + code TOTP"
- ☐ Commande `npm run test:e2e -- mfa.spec.ts` passe 6/6 tests
- ☐ Backend logs montrent flow complet : `/mfa/setup` → `/mfa/enable` → `/auth/login` → `/mfa/verify`

**Fichiers à modifier** :
- `frontend/tests/e2e/mfa.spec.ts` (création)

**Checkpoint** : Après 6 tests MFA (1 fichier)

### Critères de Succès Session 3C-1
- ☐ 3 fichiers créés : `playwright.config.ts`, `csrf.spec.ts`, `mfa.spec.ts`
- ☐ Total 11+ tests E2E passent (5 CSRF + 6 MFA)
- ☐ Commande `npm run test:e2e` exécute tous les tests sans erreur
- ☐ MEMORY.md mis à jour avec chemins fichiers et résultats tests
- ☐ Checkpoint context-engine créé

---

## 📝 Session 3C-2 — E2E Sessions + cancelInvoice

### Objectif
Couvrir session expiration E2E + implémenter endpoint frontend manquant.

### Pré-requis
- ☐ Playwright configuré (Session 3C-1 complétée)
- ☐ Backend endpoint `POST /invoices/{id}/cancel` fonctionne (déjà vérifié)

### Tasks Détaillées

#### Task 3C-2.1 : E2E Session Expiration
**Critères de complétude VÉRIFIABLES** :
- ☐ Fichier `frontend/tests/e2e/sessions.spec.ts` existe
- ☐ Minimum 4 tests dans le fichier :
  1. ☐ Test "doit créer session à login et afficher dans /profile"
  2. ☐ Test "doit auto-refresh token avant expiration (59min mark)"
  3. ☐ Test "doit logout et clear session si token invalide"
  4. ☐ Test "doit afficher toutes sessions utilisateur dans /admin/sessions"
- ☐ Commande `npm run test:e2e -- sessions.spec.ts` passe 4/4 tests
- ☐ Backend logs montrent : `/auth/login` → `/sessions` → `/auth/refresh` → `/auth/logout`

**Fichiers à modifier** :
- `frontend/tests/e2e/sessions.spec.ts` (création)

**Checkpoint** : Après 4 tests sessions (1 fichier)

#### Task 3C-2.2 : Implémenter cancelInvoice() Frontend
**Critères de complétude VÉRIFIABLES** :
- ☐ Fichier `frontend/src/api/invoices.ts` contient méthode `cancelInvoice(id: number): Promise<Invoice>`
- ☐ Méthode utilise `POST /invoices/${id}/cancel` (backend endpoint existant)
- ☐ Fichier `frontend/src/api/__tests__/invoices.test.ts` créé avec minimum 3 tests :
  1. ☐ Test "annule une invoice et retourne invoice avec status cancelled"
  2. ☐ Test "propage les erreurs 404 si invoice non trouvée"
  3. ☐ Test "propage les erreurs 400 si invoice déjà cancelled"
- ☐ Commande `npm run test -- invoices.test.ts` passe 3/3 tests (nouveaux)
- ☐ Total tests frontend API : 189 + 3 = 192 tests passent

**Fichiers à modifier** :
- `frontend/src/api/invoices.ts` (ajout méthode)
- `frontend/src/api/__tests__/invoices.test.ts` (création)

**Checkpoint** : Après 2 fichiers modifiés

#### Task 3C-2.3 : Intégrer cancelInvoice dans UI
**Critères de complétude VÉRIFIABLES** :
- ☐ Identifier page(s) UI affichant invoices (probablement composant modal ou page liste)
- ☐ Ajouter bouton "Annuler" visible uniquement si `invoice.status !== 'cancelled'`
- ☐ Bouton appelle `invoicesApi.cancelInvoice(id)` au click
- ☐ Afficher toast success après annulation
- ☐ Afficher toast error si échec
- ☐ Re-fetch liste invoices après succès
- ☐ Test manuel : créer invoice → annuler → vérifier status change dans UI

**Fichiers à identifier puis modifier** :
- `frontend/src/pages/*/Invoice*.tsx` ou `frontend/src/components/*/Invoice*.tsx`

**Checkpoint** : Après modification UI (1-2 fichiers)

### Critères de Succès Session 3C-2
- ☐ 3 fichiers créés/modifiés : `sessions.spec.ts`, `invoices.ts`, `invoices.test.ts`
- ☐ Total 7+ nouveaux tests passent (4 E2E sessions + 3 unit invoices)
- ☐ Frontend tests total : 192+ tests
- ☐ Méthode `cancelInvoice()` callable depuis frontend UI
- ☐ MEMORY.md mis à jour avec résultats
- ☐ Checkpoint context-engine créé

---

## 📝 Session 3C-3 — RESTful Refactoring Inventory Items

### ⚠️ BREAKING CHANGE — Nécessite Migration

### Objectif
Unifier endpoints inventory items en pattern nested uniquement.

### Pré-requis
- ☐ Aucun client externe ne consomme API `/inventory-movements/items/{id}` (vérifier)
- ☐ Frontend utilise uniquement ces endpoints (vérifier avec Grep)
- ☐ Tests backend inventory items identifiés (probablement `tests/integration/test_inventory*.py`)

### Tasks Détaillées

#### Task 3C-3.1 : Audit Usage Actuel
**Critères de complétude VÉRIFIABLES** :
- ☐ Commande `grep -r "inventory-movements/items" frontend/src/` exécutée, résultats sauvegardés
- ☐ Commande `grep -r "items/{.*id}" app/api/v1/endpoints/inventory*.py` exécutée
- ☐ Identifier tous les appels frontend actuels (PATCH/DELETE items)
- ☐ Identifier tous les tests backend touchant ces endpoints
- ☐ Document `docs/plans/INVENTORY-ITEMS-MIGRATION.md` créé avec :
  - Liste endpoints actuels
  - Liste endpoints cibles (nested)
  - Liste fichiers frontend à modifier
  - Liste fichiers tests à modifier

**Checkpoint** : Après audit complet (1 doc créé)

#### Task 3C-3.2 : Refactor Backend Endpoints
**Critères de complétude VÉRIFIABLES** :
- ☐ Fichier `app/api/v1/endpoints/inventory_movements.py` modifié
- ☐ Anciens endpoints dépréciés (garder avec `@deprecated` decorator temporairement) :
  ```python
  # DEPRECATED - Use nested routes
  PATCH /inventory-movements/items/{item_id}
  DELETE /inventory-movements/items/{item_id}
  ```
- ☐ Nouveaux endpoints créés :
  ```python
  PATCH /inventory-movements/{movement_id}/items/{item_id}
  DELETE /inventory-movements/{movement_id}/items/{item_id}
  ```
- ☐ Endpoint POST déjà nested, aucun changement requis
- ☐ Tests backend modifiés pour utiliser nouveaux endpoints
- ☐ Commande `docker compose run --rm api pytest tests/integration/test_inventory*.py -v` passe tous les tests

**Fichiers à modifier** :
- `app/api/v1/endpoints/inventory_movements.py`
- `tests/integration/test_inventory_movements.py` (probablement)

**Checkpoint** : Après refactor backend (2 fichiers modifiés)

#### Task 3C-3.3 : Refactor Frontend API Calls
**Critères de complétude VÉRIFIABLES** :
- ☐ Fichier `frontend/src/api/inventory.ts` modifié
- ☐ Méthodes `updateInventoryItem()` et `deleteInventoryItem()` modifiées pour accepter `movement_id` en paramètre :
  ```typescript
  // Avant
  updateInventoryItem(itemId: number, data: MovementItemUpdate)
  // Après
  updateInventoryItem(movementId: number, itemId: number, data: MovementItemUpdate)
  ```
- ☐ URLs changées vers pattern nested
- ☐ Tests frontend `frontend/src/api/__tests__/inventory.test.ts` modifiés (si existe)
- ☐ Commande `npm run test -- inventory.test.ts` passe tous les tests

**Fichiers à modifier** :
- `frontend/src/api/inventory.ts`
- `frontend/src/api/__tests__/inventory.test.ts` (si existe)

**Checkpoint** : Après refactor frontend API (1-2 fichiers)

#### Task 3C-3.4 : Update Frontend UI Calls
**Critères de complétude VÉRIFIABLES** :
- ☐ Grep pour identifier tous les appels UI : `grep -r "updateInventoryItem\|deleteInventoryItem" frontend/src/pages/ frontend/src/components/`
- ☐ Modifier chaque appel pour passer `movement_id` en 1er paramètre
- ☐ Vérifier que `movement_id` est disponible dans le contexte (probablement depuis parent component)
- ☐ Test manuel : ouvrir page inventory → créer mouvement → ajouter item → modifier item → supprimer item
- ☐ Aucun console error, aucun 404, toutes opérations fonctionnent

**Fichiers à identifier puis modifier** :
- `frontend/src/pages/inventory/*.tsx`
- `frontend/src/components/inventory/*.tsx` (si existent)

**Checkpoint** : Après update UI (2-4 fichiers)

#### Task 3C-3.5 : Supprimer Endpoints Dépréciés
**Critères de complétude VÉRIFIABLES** :
- ☐ Retirer `@deprecated` decorator des anciens endpoints
- ☐ Supprimer définitions anciennes routes PATCH/DELETE flat
- ☐ Vérifier aucun import/référence restante dans codebase
- ☐ Tests backend passent toujours (aucun test ne doit utiliser anciennes routes)
- ☐ Commande `grep -r "items/{item_id}" app/` ne retourne AUCUN résultat dans endpoints

**Fichiers à modifier** :
- `app/api/v1/endpoints/inventory_movements.py`

**Checkpoint** : Après cleanup (1 fichier)

### Critères de Succès Session 3C-3
- ☐ 1 doc migration créé
- ☐ 5-9 fichiers modifiés (2 backend, 3-7 frontend)
- ☐ Tous tests backend passent (1183+ tests)
- ☐ Tous tests frontend passent (192+ tests)
- ☐ Pattern REST unifié : TOUS endpoints inventory items en nested
- ☐ Test manuel complet réussi
- ☐ MEMORY.md mis à jour avec breaking change documenté
- ☐ Checkpoint context-engine créé

---

## ✅ Règles Appliquées

### Règle #1 : Fix Before Feature ✅
- Ce plan CORRIGE des bugs (gaps) identifiés, pas de nouvelle feature

### Règle #2 : Max 2 features/session ✅
- Session 3C-1 : 2 features (E2E CSRF + MFA)
- Session 3C-2 : 2 features (E2E Sessions + cancelInvoice)
- Session 3C-3 : 1 feature (RESTful refactor, breaking change)

### Règle #3 : Rien n'est fait tant que non vérifiable ✅
- Chaque task a critères de complétude VÉRIFIABLES
- Format : "☐ Fichier X existe", "☐ Commande Y passe N/N tests"
- Pas de "implémenter X" vague

### Règle #4 : Checklist obligatoire ✅
- Checklist pour chaque task
- Critères : code produit, tests, __init__.py, migration (si nécessaire)

### Règle #5 : Checkpoint tous les 3 fichiers ✅
- Checkpoint explicite après chaque 1-3 fichiers modifiés

### Règle #6 : Pas de plan verbal ✅
- Plan persisté dans `docs/plans/PHASE3C-GAPS-CORRECTION.md`
- Relisible après compression contexte

### Règle #7 : MEMORY.md = faits vérifiés ✅
- Chaque session doit mettre à jour MEMORY.md avec :
  - Date vérification
  - Chemin fichiers créés/modifiés
  - Résultats tests (N/N pass)

### Règle #8 : Scoping strict ✅
- Chaque session : scope clair, fichiers estimés
- Session 3C-3 : breaking change, audit préalable obligatoire

### Règle #9 : Doctrine = pratique ✅
- Ce plan applique les règles .claude à lui-même

---

## 📊 Métriques Prévisionnelles

### Avant Phase 3C
- Backend : 1631 tests
- Frontend : 189 tests (81 stores/errors + 108 API)
- E2E : 0 tests

### Après Phase 3C (Objectif)
- Backend : 1631 tests (inchangé, sauf maj tests inventory items)
- Frontend : 192+ tests (189 + 3 cancelInvoice)
- E2E : 15+ tests (5 CSRF + 6 MFA + 4 Sessions)
- **Total tests frontend** : 207+ tests
- **Couverture E2E** : 3 flows critiques couverts

### Fichiers Créés (Estimation)
- Session 3C-1 : 3 fichiers (config, csrf.spec, mfa.spec)
- Session 3C-2 : 3 fichiers (sessions.spec, invoices.ts updates, invoices.test.ts)
- Session 3C-3 : 1 doc + 5-9 fichiers modifiés (backend, frontend, UI)

**Total** : 7 nouveaux fichiers + 1 doc + 5-9 modifs

---

## 🚀 Ordre d'Exécution Recommandé

1. **Session 3C-1** : Critique (P0), E2E CSRF + MFA
2. **Session 3C-2** : Critique (P0), E2E Sessions + cancelInvoice
3. **Session 3C-3** : Important (P1), breaking change (peut attendre si priorités changent)

**Durée estimée** : 3 sessions de travail distinctes (1-2h chacune)

---

**Créé par** : Claude Code (context-engine scan + règles .claude)
**Dernière mise à jour** : 2026-02-16
**Statut** : Plan validé, prêt pour exécution
