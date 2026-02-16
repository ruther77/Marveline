# Plan Phase 2 : Complétion Frontend — CaroCorp_new (Marveline)

**Date** : 2026-02-16
**Statut** : Draft — en attente validation utilisateur
**Pré-requis** : Phases 0A, 0B, 1.1, 1.2, 1.3, 1.4 terminées (commit 2731d6b)

---

## 1. État des lieux post-Phase 1.4

### 1.1 Backend : COMPLET (15 domaines, ~100 endpoints)

| Domaine | Endpoints | Tests | Celery |
|---------|-----------|-------|--------|
| auth | 6 | ✅ integ | — |
| users (admin) | 7 | ✅ 34 integ | — |
| mfa | 5 | ✅ unit + integ | — |
| sessions | 3 | ✅ integ | — |
| products | 5 | ✅ integ | — |
| categories | 6 | ✅ integ | — |
| bundles | 9 | ✅ integ | — |
| customers | 5 | ✅ integ | — |
| reservations | 6 | ✅ integ + workflow | ✅ async email |
| invoices | 7 | ✅ integ | ✅ overdue check (beat) |
| inventory-movements | 12 | ✅ 58 unit + 9 integ | ✅ late check + async email |
| audit | 3 | ✅ e2e | — |
| api-keys | 6 | ✅ unit + integ | — |
| features | 6 | ✅ unit + integ | — |
| vpn (proxy WG) | 12 | ✅ security | — |
| health | 3 | — | — |
| **Total** | **~101** | **1631 pass** | **7 tasks (4 async + 3 beat)** |

### 1.2 Frontend : 11 pages réelles, 5 placeholders, 5 domaines sans page

#### Pages FONCTIONNELLES (11)

| Page | Route | Couverture backend |
|------|-------|--------------------|
| LoginPage | `/login` | Complète |
| ProfilePage | `/profile` | Complète |
| SecurityPage | `/profile/security` | Complète |
| MFAPage | `/profile/mfa` | Complète |
| ProductsPage | `/products` | Complète |
| CategoriesPage | `/products/categories` | Complète |
| BundlesPage | `/products/bundles` | Partielle (pas de gestion items post-création) |
| ReservationsPage | `/events` | Complète |
| UsersPage | `/admin/users` | Complète |
| SessionsPage | `/admin/sessions` | Complète |
| AuditLogsPage | `/admin/audit-logs` | Partielle (search non fonctionnel, date filters UI absents) |

#### Pages PLACEHOLDER — "Coming Soon" (5)

| Page | Route | Backend | API Client frontend |
|------|-------|---------|---------------------|
| MovementsPage | `/inventory/movements` | 12 endpoints | `inventory.ts` complet |
| AgendaPage | `/agenda` | `getAgenda()` endpoint | `inventory.ts` |
| AgendaMobilePage | `/agenda/mobile` | idem | idem |
| ForgotPasswordPage | `/forgot-password` | `POST /auth/forgot-password` | `auth.ts` |
| ResetPasswordPage | `/reset-password` | `POST /auth/reset-password` | `auth.ts` |

#### Pages INEXISTANTES — backend complet, 0 frontend (5 domaines)

| Domaine | Endpoints backend | API Client | Priorité |
|---------|-------------------|------------|----------|
| Invoices | 7 endpoints CRUD + workflow | **À créer** | Haute (module métier core) |
| Customers | 5 endpoints CRUD | `customers.ts` partiel (read + create/update/delete) | Moyenne |
| Feature Flags | 6 endpoints CRUD + toggle | **À créer** | Basse (admin) |
| API Keys | 6 endpoints CRUD + rotate | **À créer** | Basse (admin) |
| VPN | 12 endpoints proxy WG | **À créer** | Basse (admin) |

#### Pages INCOMPLÈTES (4 problèmes)

| Page | Problème | Impact |
|------|----------|--------|
| DashboardPage | 3 cartes de navigation, 0 KPI, 0 stats, 0 graphique | UX pauvre — première impression |
| BundlesPage | Pas de page détails bundle. Message "Utilisez la page détails..." mais `/products/bundles/:id` n'existe pas | Items non gérables post-création |
| AuditLogsPage | Search bar non fonctionnelle, filtres date non exposés dans l'UI | Admin ne peut pas filtrer efficacement |
| InventoryPage | Vue stock read-only, pas d'ajustement manuel | Stock non ajustable hors mouvement |

### 1.3 Mismatches API restants (post-corrections)

| Mismatch | Sévérité | Détail |
|----------|----------|--------|
| Audit logs `pages` | Mineur | Backend ne retourne pas `pages`, frontend calcule localement. Fonctionne mais incohérent. |
| `NotFound` vs `HTTPException(404)` | Mineur | Pattern hybride — endpoints utilisent `HTTPException(404)` directement au lieu de `NotFound` custom. Pas de bug runtime. |
| N+1 queries potentiels | Moyen | `joinedload`/`selectinload` sous-utilisés dans repositories. Pas de bug mais perf dégradée sous charge. |

---

## 2. Plan de sessions

### Priorité : Flux métier opérateur > Admin tools > Polish

Un opérateur Marveline doit pouvoir : créer une réservation → gérer les mouvements de stock → envoyer/suivre les factures → voir le calendrier. Les pages admin (VPN, API Keys, Feature Flags) sont secondaires.

---

### Session 2.1 : MovementsPage (placeholder → réelle)

**Justification** : Module métier core. L'API client `inventory.ts` est complet avec tous les types. Le backend a 12 endpoints. C'est la page la plus "prête" à implémenter.

**Livrables** :

| # | Tâche | Fichier(s) | Critère |
|---|-------|------------|---------|
| 1 | Page liste mouvements (tableau paginé, filtres statut/type/date) | `frontend/src/pages/inventory/MovementsPage.tsx` | Remplace "Coming Soon", affiche liste paginée |
| 2 | Modal création mouvement (type, date prévue, notes, lien réservation optionnel) | `MovementFormModal.tsx` ou inline | Formulaire crée un mouvement via API |
| 3 | Modal détails mouvement + gestion items (ajout/modif/suppression produits) | `MovementDetailModal.tsx` | CRUD items dans un mouvement |
| 4 | Action "Compléter" mouvement (avec saisie quantités réelles + état) | Bouton dans la liste ou détails | Appelle `PATCH /{id}/complete` |
| 5 | Indicateurs visuels : badges statut (draft/scheduled/in_transit/completed), retard (rouge si date dépassée) | Composants | Badges colorés |

**Complexité** : Haute (CRUD + items imbriqués + workflow statut)
**Estimation** : 1 session

---

### Session 2.2 : InvoicesPage + API client

**Justification** : Module métier core. Les factures sont auto-générées à la confirmation réservation (Phase 1.1) mais actuellement invisibles côté frontend. L'opérateur ne peut pas les consulter.

**Livrables** :

| # | Tâche | Fichier(s) | Critère |
|---|-------|------------|---------|
| 1 | API client invoices | `frontend/src/api/invoices.ts` | CRUD + add-payment + check-overdue + mark-paid |
| 2 | Types TypeScript | `frontend/src/types/invoice.ts` | Invoice, InvoiceItem, InvoiceStatus, Payment |
| 3 | Page liste factures (tableau paginé, filtres statut/date/client) | `frontend/src/pages/invoices/InvoicesPage.tsx` | Liste avec badges statut (draft/sent/paid/overdue/cancelled) |
| 4 | Modal détails facture (lignes, paiements, totaux) | `InvoiceDetailModal.tsx` | Affiche détail complet |
| 5 | Action "Enregistrer paiement" | Bouton dans détails | Appelle add-payment, met à jour statut |
| 6 | Route + menu sidebar | `App.tsx`, `DashboardLayout.tsx` | `/invoices` accessible depuis navigation |

**Complexité** : Haute (nouveau domaine complet)
**Estimation** : 1 session

---

### Session 2.3 : ForgotPassword + ResetPassword + BundleDetailPage

**Justification** : Auth pages = obligation sécurité. Bundle detail = promesse UI non tenue.

**Livrables** :

| # | Tâche | Fichier(s) | Critère |
|---|-------|------------|---------|
| 1 | ForgotPasswordPage réelle (formulaire email + message succès) | `ForgotPasswordPage.tsx` | Remplace "Coming Soon", appelle `POST /auth/forgot-password` |
| 2 | ResetPasswordPage réelle (formulaire nouveau mot de passe + token URL) | `ResetPasswordPage.tsx` | Remplace "Coming Soon", appelle `POST /auth/reset-password` |
| 3 | BundleDetailPage (vue détails + CRUD items) | `frontend/src/pages/products/BundleDetailPage.tsx` | Nouvelle page |
| 4 | Route `/products/bundles/:id` | `App.tsx` | Navigation depuis BundlesPage |
| 5 | Lien "Voir détails" dans BundlesPage | `BundlesPage.tsx` | Bouton/lien vers page détails |

**Complexité** : Moyenne (3 formulaires simples + 1 page détails)
**Estimation** : 1 session

---

### Session 2.4 : CustomersPage + AgendaPage

**Justification** : Customers = utilisé dans réservations, mérite sa propre page. Agenda = visualisation calendrier des événements.

**Livrables** :

| # | Tâche | Fichier(s) | Critère |
|---|-------|------------|---------|
| 1 | CustomersPage (tableau CRUD, recherche, détails) | `frontend/src/pages/customers/CustomersPage.tsx` | CRUD complet via `customers.ts` existant |
| 2 | Route `/customers` + menu sidebar | `App.tsx`, `DashboardLayout.tsx` | Accessible depuis navigation |
| 3 | AgendaPage (calendrier mensuel/semaine avec réservations + mouvements) | `AgendaPage.tsx` | Remplace "Coming Soon" |
| 4 | Choix librairie calendrier | `package.json` | react-big-calendar ou @fullcalendar/react |
| 5 | AgendaMobilePage (vue liste jour) | `AgendaMobilePage.tsx` | Remplace "Coming Soon", vue simplifiée |

**Complexité** : Haute (calendrier = composant complexe)
**Estimation** : 1 session
**Dépend de** : Session 2.1 (MovementsPage pour le type Movement affiché dans l'agenda)

---

### Session 2.5 : DashboardPage (KPIs) + AuditLogsPage (amélioration)

**Justification** : Dashboard = première page après login, doit donner une vue d'ensemble. Audit = admin tool incomplet.

**Livrables** :

| # | Tâche | Fichier(s) | Critère |
|---|-------|------------|---------|
| 1 | Backend endpoint `GET /dashboard/stats` | `app/api/v1/endpoints/dashboard.py` | Retourne KPIs agrégés par tenant |
| 2 | DashboardPage enrichie : KPIs (réservations actives, CA mois, factures overdue, stock faible, mouvements en retard) | `DashboardPage.tsx` | Widgets avec données réelles |
| 3 | AuditLogsPage : filtres date fonctionnels (date picker) | `AuditLogsPage.tsx` | Date range filtre les résultats |
| 4 | AuditLogsPage : search fonctionnel | `AuditLogsPage.tsx` | Recherche par action/user/entity |
| 5 | Backend audit : ajouter `pages` dans la réponse paginée | `app/api/v1/endpoints/audit.py` | Cohérence avec autres endpoints |

**Complexité** : Moyenne-haute (nouveau endpoint backend + refonte dashboard)
**Estimation** : 1 session
**Dépend de** : Sessions 2.1-2.2 (pour avoir des données à afficher)

---

### Session 2.6 : Pages admin (Feature Flags + API Keys)

**Justification** : Outils d'administration. Basse priorité mais backend complet.

**Livrables** :

| # | Tâche | Fichier(s) | Critère |
|---|-------|------------|---------|
| 1 | API client feature-flags | `frontend/src/api/featureFlags.ts` | CRUD + toggle + rollout |
| 2 | FeatureFlagsPage (tableau + toggle switches) | `frontend/src/pages/admin/FeatureFlagsPage.tsx` | CRUD complet |
| 3 | API client api-keys | `frontend/src/api/apiKeys.ts` | CRUD + rotate |
| 4 | ApiKeysPage (tableau + modal création + affichage clé une seule fois) | `frontend/src/pages/admin/ApiKeysPage.tsx` | CRUD + UX sécurisée (clé visible 1x) |
| 5 | Routes + menu sidebar admin | `App.tsx`, `DashboardLayout.tsx` | `/admin/features`, `/admin/api-keys` |

**Complexité** : Moyenne (2 pages CRUD standard)
**Estimation** : 1 session

---

### Session 2.7 : VPN Page (admin)

**Justification** : Interface d'administration VPN WireGuard. Dernière priorité.

**Livrables** :

| # | Tâche | Fichier(s) | Critère |
|---|-------|------------|---------|
| 1 | API client VPN | `frontend/src/api/vpn.ts` | Peers CRUD + config + QR + IP pools |
| 2 | VpnPage (gestion peers + IP pools + statut serveur) | `frontend/src/pages/admin/VpnPage.tsx` | Liste peers, actions enable/disable/rotate |
| 3 | Modal config + QR code | `VpnConfigModal.tsx` | Affiche .conf + QR code téléchargeable |
| 4 | Route + menu sidebar admin | `App.tsx`, `DashboardLayout.tsx` | `/admin/vpn` |

**Complexité** : Moyenne-haute (QR code, config display)
**Estimation** : 1 session

---

## 3. Matrice complète : état actuel → cible

| Domaine | Backend | Frontend actuel | Frontend cible | Session |
|---------|---------|-----------------|----------------|---------|
| Auth (login/logout) | ✅ | ✅ | ✅ | — |
| Auth (forgot/reset) | ✅ | ❌ Placeholder | ✅ Formulaires | 2.3 |
| Profile + Security + MFA | ✅ | ✅ | ✅ | — |
| Products | ✅ | ✅ | ✅ | — |
| Categories | ✅ | ✅ | ✅ | — |
| Bundles (liste) | ✅ | ✅ | ✅ | — |
| Bundles (items détail) | ✅ | ❌ Page manquante | ✅ BundleDetailPage | 2.3 |
| Reservations | ✅ | ✅ | ✅ | — |
| **Movements** | ✅ | ❌ Placeholder | ✅ Page CRUD | **2.1** |
| **Invoices** | ✅ | ❌ Rien | ✅ Page + API client | **2.2** |
| Customers | ✅ | ⚠️ Autocomplete seul | ✅ Page CRUD | 2.4 |
| **Agenda** | ✅ | ❌ Placeholder | ✅ Calendrier | 2.4 |
| Inventory (stock) | ✅ | ⚠️ Read-only | ⚠️ (inchangé — ajustement via mouvements) | — |
| Users (admin) | ✅ | ✅ | ✅ | — |
| Sessions (admin) | ✅ | ✅ | ✅ | — |
| Audit logs | ✅ | ⚠️ Filtres incomplets | ✅ Filtres fonctionnels | 2.5 |
| **Dashboard** | ⚠️ Pas d'endpoint stats | ❌ 3 cartes nav | ✅ KPIs | **2.5** |
| Feature Flags | ✅ | ❌ Rien | ✅ Page admin | 2.6 |
| API Keys | ✅ | ❌ Rien | ✅ Page admin | 2.6 |
| VPN | ✅ | ❌ Rien | ✅ Page admin | 2.7 |

---

## 4. Dépendances entre sessions

```
Session 2.1 (Movements)        ─── indépendante, PRIORITÉ 1
Session 2.2 (Invoices)         ─── indépendante, PRIORITÉ 1
Session 2.3 (Password + Bundle detail) ─── indépendante
    │
    ├── Session 2.4 (Customers + Agenda) ─── après 2.1 (types Movement pour agenda)
    │
    └── Session 2.5 (Dashboard + Audit) ─── après 2.1 + 2.2 (données à afficher)
            │
            ├── Session 2.6 (Features + API Keys) ─── indépendante
            │
            └── Session 2.7 (VPN) ─── indépendante
```

**Sessions 2.1 et 2.2 peuvent être faites en parallèle** (domaines indépendants).
**Sessions 2.6 et 2.7 peuvent être reportées** si non prioritaires.

---

## 5. Backend à créer (nouveau code)

Seule la Session 2.5 nécessite du nouveau code backend :

| Élément | Fichier | Description |
|---------|---------|-------------|
| Endpoint dashboard stats | `app/api/v1/endpoints/dashboard.py` | `GET /dashboard/stats` — agrège KPIs par tenant |
| Schema dashboard | `app/schemas/dashboard.py` | `DashboardStats` — réservations actives, CA, overdue, stock bas |
| Router | `app/api/v1/__init__.py` | Inclure dashboard router |
| Audit `pages` response | `app/api/v1/endpoints/audit.py` | Ajouter `pages: int` au schema réponse |

Toutes les autres sessions sont **frontend-only** (le backend est complet).

---

## 6. Dette technique à traiter (opportuniste)

Ces items peuvent être adressés au fil des sessions, pas de session dédiée :

| Item | Sévérité | Action | Quand |
|------|----------|--------|-------|
| `NotFound` vs `HTTPException(404)` hybride | Mineur | Standardiser sur `NotFound` custom dans tous les endpoints | Lors de tout edit d'un endpoint |
| N+1 queries | Moyen | Ajouter `joinedload`/`selectinload` dans les repos qui chargent des relations | Lors de perf issues |
| InventoryPage read-only | Mineur | Ajustement stock = via MovementsPage (mouvement type "adjustment"). Pas de page dédiée. | Décision : hors scope |

---

## 7. Hors scope (Phase 3+)

- Product variations + images (table dédiée, migration, frontend)
- Webhooks Stripe (endpoint + signature verification)
- Finances dashboard (graphiques CA, projections)
- Notifications in-app (WebSocket, badge)
- Rapports PDF (factures, bons de livraison)
- Préférences notification par client
- Dashboard multi-tenant (super-admin)
- Monitoring Flower pour Celery
- i18n frontend (actuellement FR hardcodé)
- PWA / mode offline
- Tests e2e Playwright

---

## 8. Récapitulatif

| Session | Scope | Fichiers estimés | Complexité |
|---------|-------|------------------|------------|
| **2.1** | MovementsPage | ~4 frontend | Haute |
| **2.2** | InvoicesPage + API client | ~5 frontend | Haute |
| **2.3** | ForgotPassword + ResetPassword + BundleDetail | ~5 frontend | Moyenne |
| **2.4** | CustomersPage + AgendaPage | ~5 frontend + 1 dep | Haute |
| **2.5** | DashboardPage KPIs + AuditLogs fix | ~3 frontend + 3 backend | Moyenne-haute |
| **2.6** | FeatureFlags + ApiKeys pages | ~5 frontend | Moyenne |
| **2.7** | VPN page | ~4 frontend | Moyenne-haute |
| **Total** | **7 sessions** | **~30 fichiers** | |

**Ordre recommandé** : 2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6 → 2.7
**Sessions critiques** (flux métier opérateur) : 2.1, 2.2, 2.3
**Sessions optionnelles** (admin tools) : 2.6, 2.7
