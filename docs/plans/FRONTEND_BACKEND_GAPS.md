# Plan d'Architecture : Audit Complet — CaroCorp_new (Marveline)

**Date** : 2026-02-16
**Statut** : Draft — en attente validation utilisateur

---

## 1. Inventaire actuel

### Backend : 95 endpoints, 16 domaines, 15 services exposés

| Domaine | Endpoints | Statut |
|---------|-----------|--------|
| auth | 6 | Complet |
| products | 5 | Complet |
| categories | 6 | Complet |
| bundles | 9 | Complet |
| customers | 5 | Complet |
| reservations | 6 | Complet |
| invoices | 7 | Complet |
| inventory-movements | 12 | Complet |
| users | 7 | Complet |
| mfa | 5 | Complet |
| sessions | 3 | Complet |
| api-keys | 6 | Complet |
| features | 6 | Complet |
| vpn | 12 | Complet |
| audit | 3 | Complet |
| health | 3 | Complet |

### Frontend : 23 routes, 10 API clients, ~70 fonctions endpoint

| Page | Route | Statut |
|------|-------|--------|
| Dashboard | `/dashboard` | Minimal (3 cartes nav, 0 KPI) |
| Products | `/products` | Complet |
| Categories | `/products/categories` | Complet |
| Bundles | `/products/bundles` | Complet |
| Events/Reservations | `/events` | Complet |
| Inventory | `/inventory/stock` | Complet |
| Movements | `/inventory/movements` | **PLACEHOLDER** |
| Agenda | `/agenda` | **PLACEHOLDER** |
| Agenda Mobile | `/agenda/mobile` | **PLACEHOLDER** |
| Users | `/admin/users` | Complet |
| Sessions | `/admin/sessions` | Complet |
| Audit Logs | `/admin/audit-logs` | Complet |
| Profile | `/profile` | Complet |
| Security | `/profile/security` | Complet |
| MFA | `/profile/mfa` | Complet |
| Login | `/login` | Complet |
| Forgot Password | `/forgot-password` | **PLACEHOLDER** |
| Reset Password | `/reset-password` | **PLACEHOLDER** |

---

## 2. BUGS & ERREURS CRITIQUES

### BUG P0 — Endpoints VPN sans authentification

**Fichier** : `app/api/v1/endpoints/vpn.py`
**Problème** : Les 13 endpoints VPN ont `current_user: VpnReader = None` — le `= None` désactive le check FastAPI Depends. Tout utilisateur non authentifié peut accéder aux endpoints VPN.

**Endpoints affectés** : create/list/get/update/delete peers, rotate/enable/disable, config, ip-pools, status

**Correction** : Retirer `= None` de tous les paramètres `current_user`.

### BUG P1 — Exception handling silencieux (40+ endpoints)

**Fichiers** : `bundles.py`, `categories.py`, `products.py`, `customers.py`, `invoices.py`, `inventory_movements.py`, `reservations.py`
**Problème** : Pattern `except Exception as e: raise HTTPException(500, f"Error: {str(e)}")` sans `logger.exception()`. Les erreurs sont perdues — impossible de diagnostiquer en production.

### BUG P1 — Incohérence exceptions NotFound vs HTTPException

**Problème** : `app/core/exceptions.py` définit `NotFound` mais les endpoints utilisent `HTTPException(404)` directement. Mélange de patterns.

### BUG P1 — Broad except sans logging dans services

**Fichiers** : `feature_flag.py`, `token.py`, `cache.py`, `api_key.py`, `rate_limit_utils.py`, `middleware/security.py`
**Problème** : `except Exception: pass` — erreurs silencieusement ignorées.

### BUG P2 — N+1 queries potentiels

**Fichier** : `app/repositories/` (tous)
**Problème** : `.all()` utilisé ~40 fois, `joinedload`/`selectinload` seulement 12 fois. Relations non chargées eagerly.

---

## 3. DÉCALAGES FRONTEND ↔ BACKEND (Mismatches API)

### Mismatch CRITIQUE — Inventory Movements dates

- **Frontend** : Envoie `start_date`/`end_date` sur `GET /inventory-movements/statistics`
- **Backend** : N'accepte PAS ces paramètres
- **Impact** : Filtrage par date impossible sur les statistiques

### Mismatch CRITIQUE — Sessions response structure

- **Frontend** : Attend `{ sessions, total, active_count }`
- **Backend** : Retourne `{ sessions, count }`
- **Impact** : `total` et `active_count` indéfinis côté frontend

### Mismatch MOYEN — Bundles param naming

- **Frontend** : Envoie `is_active` (mappé depuis `active_only`)
- **Backend** : Attend `active_only`
- **Impact** : Filtre actif/inactif potentiellement cassé

### Mismatch MOYEN — Audit logs pagination

- **Frontend** : Attend `pages` (nombre total de pages) dans la réponse
- **Backend** : Retourne `skip/limit` sans `pages` calculé

### Mismatch MINEUR — Response wrapping inconsistant

- **Frontend** : Fait des fallbacks (`data.items || data.data || data`) à plusieurs endroits
- **Impact** : Fragile, masque des vrais bugs de structure

---

## 4. WORKFLOWS MÉTIER — Connexions & Déconnexions

### Connexions FORTES (fonctionnelles)

| Workflow | Statut |
|----------|--------|
| Reservation.confirm() → ProductService.reserve_stock() | ✅ Atomique |
| Reservation.cancel() → ProductService.release_stock() | ✅ Atomique |
| ReservationLine → snapshot prix produit | ✅ Copie au create |

### Connexions FAIBLES (manuelles)

| Workflow | Problème |
|----------|----------|
| Reservation → Invoice | Création MANUELLE via POST /invoices séparé. Pas d'auto-génération à la confirmation. |
| Invoice → Payment | Endpoint add-payment existe, mais pas de webhook Stripe. Paiement = saisie manuelle. |

### Connexions ABSENTES (critiques)

| Workflow attendu | Réalité |
|------------------|---------|
| Reservation → InventoryMovement | **AUCUN lien**. Pas de FK, pas d'auto-trigger. Mouvements créés manuellement sans référence à une réservation. |
| Movement.complete() → Reservation.status (delivered/returned) | **ABSENT**. Compléter un mouvement ne met pas à jour la réservation. |
| Movement.complete() → Product stock update | **ABSENT**. Le stock n'est PAS mis à jour quand un mouvement est complété. |
| Invoice.paid → Notification client | **ABSENT**. Aucun email envoyé au paiement. |
| Reservation.confirm → Notification client | **ABSENT**. Aucun email de confirmation. |
| Damage detected → Frais ajoutés à Invoice | **ABSENT**. `damage_fee` stocké dans Movement mais jamais appliqué à Invoice. |
| Business events → AuditService | **ABSENT dans services métier**. AuditService existe mais n'est appelé QUE par le middleware (requêtes HTTP), pas dans ReservationService/InvoiceService/MovementService. |

### Flux complet IDÉAL vs RÉALITÉ

```
Étape                                          Idéal    Réalité
─────────────────────────────────────────────  ─────    ──────
1. Créer réservation (draft)                    ✅       ✅
2. Confirmer → réserver stock                   ✅       ✅
3. [AUTO] Créer facture                         AUTO     ❌ MANUEL
4. [AUTO] Envoyer facture au client             AUTO     ❌ ABSENT
5. Client paie (webhook Stripe)                 AUTO     ❌ ABSENT (saisie manuelle)
6. [AUTO] Notifier "paiement reçu"              AUTO     ❌ ABSENT
7. [AUTO] Créer mouvement "departure"           AUTO     ❌ MANUEL
8. Compléter mouvement → marquer "delivered"    AUTO     ❌ ABSENT
9. [AUTO] Créer mouvement "return"              AUTO     ❌ MANUEL
10. Inspection retour + dommages                ✅       ✅ (endpoint existe)
11. [AUTO] Ajouter frais dommage à facture      AUTO     ❌ ABSENT
12. [AUTO] Envoyer appel de frais               AUTO     ❌ ABSENT
```

**Bilan** : 4/12 étapes fonctionnelles. 8 étapes manuelles ou absentes.

---

## 5. AUTOMATISMES MANQUANTS

### A — Celery Tasks (infrastructure prête, 0 tâche définie)

**Situation** : `celery_app.py` existe avec broker Redis, queues définies (`default`, `reservations`, `invoicing`, `notifications`), worker Docker configuré. Mais **AUCUNE tâche** n'est enregistrée (seulement `debug_task`).

**Tâches à créer** :
- `create_invoice_for_reservation(reservation_id)` — Auto-facturation
- `send_reservation_confirmation(reservation_id)` — Email confirmation
- `send_invoice_email(invoice_id)` — Email facture
- `send_payment_received(invoice_id)` — Email paiement reçu
- `check_overdue_invoices()` — Relance quotidienne factures en retard
- `check_late_movements()` — Alerte mouvements en retard
- `low_stock_alerts()` — Alerte stock faible

### B — Webhooks Stripe (0 implémentation)

**Situation** : Aucun endpoint webhook Stripe. Pas de handler pour `checkout.session.completed`, `payment_intent.succeeded/failed`, `charge.refunded`.

### C — Notifications (1 seul template sur ~8 nécessaires)

**Situation** : `NotificationService` ne gère que `send_password_reset_email()`. Aucun template pour :
- Confirmation réservation
- Facture générée
- Relance paiement
- Paiement reçu
- Mouvement en retard
- Alerte stock faible
- Dommage détecté

### D — Celery Beat (0 tâche périodique)

**Situation** : Pas de scheduler. Tâches périodiques nécessaires :
- Check factures overdue (quotidien)
- Check mouvements en retard (quotidien)
- Alertes stock faible (quotidien)
- Cleanup tokens expirés (hebdo)

---

## 6. PAGES FRONTEND MANQUANTES

### Pages PLACEHOLDER (backend prêt)

| Page | Backend | API Client | Travail |
|------|---------|------------|---------|
| MovementsPage | 12 endpoints | `inventory.ts` complet | UI CRUD |
| AgendaPage/Mobile | `getAgenda()` | Existe | UI calendrier |
| ForgotPasswordPage | `POST /auth/forgot-password` | Existe | Formulaire |
| ResetPasswordPage | `POST /auth/reset-password` | Existe | Formulaire |

### Pages INEXISTANTES (backend prêt, pas de frontend du tout)

| Page | Endpoints backend | API Client | Travail |
|------|-------------------|------------|---------|
| InvoicesPage | 7 endpoints | **À créer** | Page + API client |
| CustomersPage | 5 endpoints | Read-only, **compléter** | Page + CRUD client |
| FeatureFlagsPage | 6 endpoints | **À créer** | Page admin |
| ApiKeysPage | 6 endpoints | **À créer** | Page admin |
| VpnPage | 12 endpoints | **À créer** | Page admin |
| FinancesPage | (agrégation) | **À créer** | Dashboard financier |

### Pages INCOMPLÈTES

| Page | Problème |
|------|----------|
| DashboardPage | 0 KPI, 0 stats — juste 3 cartes de navigation |
| Menu "Finances" | Lien sidebar `/finances` mais aucune route dans App.tsx |

---

## 7. PLAN DE SESSIONS RÉVISÉ

### Phase 0 — Corrections critiques (AVANT toute feature)

#### Session 0A : Fix bugs sécurité & qualité
- **P0** : Retirer `= None` des 13 endpoints VPN (`vpn.py`)
- **P1** : Ajouter `logger.exception()` avant les `raise HTTPException(500)` (40+ endpoints)
- **P1** : Standardiser `NotFound` vs `HTTPException(404)` dans les endpoints
- **P1** : Ajouter logging dans les `except Exception: pass` des services
- **Fichiers** : ~15 fichiers endpoints + ~6 fichiers services
- **Tests** : Vérifier que les tests VPN passent toujours après le fix

#### Session 0B : Fix mismatches frontend ↔ backend
- **Critique** : Ajouter `start_date`/`end_date` params sur `GET /inventory-movements/statistics`
- **Critique** : Aligner response Sessions (`count` → `total` + ajouter `active_count`)
- **Moyen** : Corriger param Bundles (`is_active` → `active_only`)
- **Moyen** : Ajouter `pages` calculé dans response Audit Logs
- **Fichiers** : ~4 fichiers backend + ~2 fichiers frontend

### Phase 1 — Workflows métier (connexions inter-modules)

#### Session 1 : Connexion Reservation → Invoice (auto-facturation)
- Modifier `ReservationService.confirm_reservation()` pour appeler `InvoiceService.generate_from_reservation()`
- Ou ajouter endpoint `POST /reservations/{id}/generate-invoice`
- Ajouter test d'intégration du workflow complet
- **Fichiers** : `reservation.py` (service), `invoices.py` (endpoint optionnel), tests

#### Session 2 : Connexion Reservation → InventoryMovement
- Ajouter `reservation_id` FK optionnel dans modèle `InventoryMovement`
- Migration Alembic
- Modifier workflow : confirmation réservation → créer mouvement DEPARTURE auto
- Modifier workflow : mouvement RETURN complété → mettre à jour réservation "returned"
- **Fichiers** : modèle, migration, service reservation, service movement, tests

#### Session 3 : Notifications métier
- Créer templates email : confirmation réservation, facture, paiement reçu, relance
- Intégrer `NotificationService` dans `ReservationService` et `InvoiceService`
- **Fichiers** : `notification.py` (service), templates, services métier

#### Session 4 : Celery tasks & Beat
- Définir tâches asynchrones (auto-invoice, notifications, checks overdue)
- Configurer Celery Beat (tâches périodiques quotidiennes)
- **Fichiers** : `app/tasks/`, `celery_app.py`, config Beat

### Phase 2 — Pages frontend placeholder → réelles

#### Session 5 : ForgotPassword + ResetPassword
- Formulaires auth simples (API déjà connectée)
- **Complexité** : Faible

#### Session 6 : MovementsPage
- CRUD complet avec items, filtres, statuts
- **Complexité** : Moyenne-haute

#### Session 7 : AgendaPage + AgendaMobilePage
- Calendrier des réservations et mouvements
- Choix librairie : react-big-calendar ou FullCalendar
- **Complexité** : Moyenne-haute

### Phase 3 — Nouvelles pages frontend

#### Session 8 : CustomersPage
- CRUD complet + compléter `customers.ts` (manque create/update/delete)
- Route `/customers` + menu sidebar
- **Complexité** : Moyenne

#### Session 9 : InvoicesPage
- Nouveau API client `invoices.ts` + page CRUD + modal paiement
- Route + menu sous "Finances"
- **Complexité** : Haute

#### Session 10 : FinancesPage (dashboard financier)
- Dépend de Session 9
- Graphiques, résumé factures, KPIs financiers
- **Complexité** : Moyenne-haute

### Phase 4 — Admin pages

#### Session 11 : FeatureFlagsPage
- API client + page admin CRUD + toggle/rollout
- **Complexité** : Moyenne

#### Session 12 : ApiKeysPage
- API client + page admin CRUD + rotation + affichage clé
- **Complexité** : Moyenne

#### Session 13 : VpnPage
- API client + page admin CRUD + config/QR code + statut serveur
- **Complexité** : Haute

### Phase 5 — Améliorations

#### Session 14 : DashboardPage (KPIs)
- Nouveau endpoint backend `/dashboard/stats`
- Widgets : réservations actives, CA mois, stock faible, factures overdue
- **Complexité** : Haute

#### Session 15 : Recherche produits backend
- Ajouter `search_query` ILIKE sur `GET /products`
- **Complexité** : Faible

#### Session 16 : Webhooks Stripe (optionnel)
- Endpoint `/webhooks/stripe` avec signature verification
- Handlers: `checkout.session.completed`, `payment_intent.succeeded/failed`
- **Complexité** : Haute

---

## 8. Récapitulatif

| Phase | Sessions | Scope | Effort |
|-------|----------|-------|--------|
| **Phase 0** (Fixes) | 0A-0B | Bugs sécurité + mismatches API | 2 sessions |
| **Phase 1** (Workflows) | 1-4 | Connexions inter-modules + automations | 4 sessions |
| **Phase 2** (Placeholders) | 5-7 | Pages frontend placeholder → réelles | 3 sessions |
| **Phase 3** (Nouvelles pages) | 8-10 | CustomersPage, InvoicesPage, FinancesPage | 3 sessions |
| **Phase 4** (Admin) | 11-13 | Features, API Keys, VPN | 3 sessions |
| **Phase 5** (Polish) | 14-16 | Dashboard KPIs, Search, Stripe webhooks | 3 sessions |
| **Total** | **16 sessions** | | |

---

## 9. Dépendances

```
Phase 0A (Fix sécurité)      → BLOQUANT, faire en premier
Phase 0B (Fix mismatches)    → BLOQUANT, faire en premier
Phase 1.1 (Reservation→Invoice) → indépendante
Phase 1.2 (Reservation→Movement) → indépendante
Phase 1.3 (Notifications)    → après 1.1 et 1.2 (pour notifier les nouveaux workflows)
Phase 1.4 (Celery)           → après 1.3 (pour rendre les notifications async)
Phase 2 (Placeholders)       → indépendante de Phase 1
Phase 3.9 (Invoices)         → idéalement après Phase 1.1 (auto-facturation)
Phase 3.10 (Finances)        → DÉPEND de 3.9 (InvoicesPage)
Phase 4 (Admin)              → indépendante
Phase 5.14 (Dashboard)       → après Phase 3 (pour inclure stats factures/clients)
Phase 5.16 (Stripe)          → après Phase 3.9 (InvoicesPage)
```

---

## 10. Automatismes existants (référence)

| Automatisme | Statut | Détails |
|-------------|--------|---------|
| Rate limiting (5 niveaux) | ✅ | Global IP, login, user, mutations, reads |
| Brute force detection | ✅ | Escalation progressive, lock après 10 échecs |
| Cache Redis | ✅ | Cache-aside, invalidation par pattern |
| Audit middleware | ✅ | Log auto mutations + lectures sensibles |
| Session management Redis | ✅ | TTL 7j, index user→sessions |
| JWT rotation + blacklist | ✅ | Token family tracking, replay detection |
| CSRF protection | ✅ | Redis-backed, multi-onglets |
| Security headers | ✅ | CSP, HSTS, X-Frame-Options |
| Password reset flow | ✅ | Single-use token, rate limited, anti-enum |
| Multi-tenant isolation | ✅ | tenant_id NOT NULL, filtre repository |
| **Celery tasks** | ❌ | Infrastructure prête, 0 tâche définie |
| **Webhooks Stripe** | ❌ | 0 implémentation |
| **Notifications métier** | ❌ | 1 template (password reset) sur ~8 nécessaires |
| **Celery Beat** | ❌ | 0 tâche périodique |
| **Audit dans services métier** | ❌ | Seulement middleware HTTP, pas dans services |
