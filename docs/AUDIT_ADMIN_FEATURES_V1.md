# Audit Admin Features — V1

**Date** : 2026-03-29
**Methode** : Simulation utilisateur via API (curl) + verification code source
**Compte teste** : admin@carocorp.dev (tenant_admin, tenant 1 — CaroCorp Dev)
**Tenants en DB** : CaroCorp Dev (id=1), MassaCorp (id=2), Restaurant MassaCorp (id=3)

> Chaque observation a ete verifiee dans le code source. Les references fichier:ligne sont incluses.

---

## 1. Gestion Utilisateurs (`/api/v1/users`)

### Ce qui fonctionne

| Action | Endpoint | HTTP | Resultat |
|--------|----------|------|----------|
| Lister | `GET /users` | 200 | Liste paginee, filtrage tenant OK |
| Detail | `GET /users/{id}` | 200 | Retourne le user complet |
| Creer | `POST /users` | 200 | Cree compte + membership, CSRF requis |
| Modifier | `PATCH /users/{id}` | 200 | Mise a jour partielle OK |
| Supprimer | `DELETE /users/{id}` | 200 | Soft-delete (is_active=false, membership suspended) |
| Cross-tenant | `GET /users/{id_autre_tenant}` | 404 | Isolation correcte |
| Mot de passe faible | `POST /users` | 422 | Rejete (min 8 chars) |
| Audit trail | Automatique | — | CREATE, UPDATE, DELETE, USER_DEACTIVATED logues |

### Bugs et gaps

| # | Severite | Description |
|---|----------|-------------|
| **ADM-01** | **P0-SECU** | **Escalade de privilege CONFIRMEE dans le code.** `app/services/user.py:178-181` — `create_user()` assigne `role_name=role` directement depuis la requete sans appeler `can_manage_role()`. La fonction `can_manage_role()` EXISTE dans `app/services/rbac.py:228-236` avec la hierarchie correcte (super_admin=0, tenant_admin=2, manager=3, staff=4, viewer=5) mais n'est JAMAIS appelee. Meme probleme dans `update_user()` (ligne 230-232) : seule l'auto-promotion est bloquee (`admin_user.id == user_id`), mais promouvoir un AUTRE user est autorise sans controle. |
| **ADM-02** | P2 | Message erreur cross-tenant doublon : `"User 2 not found in tenant 1 not found"` — mot "not found" repete. |
| **ADM-03** | P3 | `GET /users/` (trailing slash) → 307 redirect au lieu de 200. Incoherence potentielle avec le frontend. |
| **ADM-04** | P3 | `DELETE /users/{id}` retourne 200 avec le body du user. Devrait retourner 204 No Content ou un message explicite de desactivation. Trompe le consommateur API (semble etre un GET). |
| **ADM-05** | P2 | **Validation mdp robuste MAIS role non passe.** `password_policy.py` est complet (majuscule, minuscule, chiffre, special, common passwords, sequences, contexte email). CEPENDANT `user.py:150` appelle `validate_password_strength(data.password)` **sans passer le role** → la longueur min reste 8 au lieu de 12 pour admin/manager (conf `PasswordPolicy.ELEVATED_ROLES`). Fix : passer `role=data.role`. |

---

## 2. Sessions (`/api/v1/sessions`)

### Ce qui fonctionne

| Action | Endpoint | HTTP | Resultat |
|--------|----------|------|----------|
| Lister mes sessions | `GET /sessions` | 200 | Liste avec session_id, device_id, ip, user_agent, is_current |
| Revoquer une session | `DELETE /sessions/{session_id}` | 200 | Session revoquee, token invalide |
| Revoquer toutes | `DELETE /sessions` | 200 | Toutes sessions revoquees, y compris la courante |
| Token invalide apres revoke | `GET /users` | 401 | Token correctement invalide via whitelist Redis |

### Bugs et gaps

| # | Severite | Description |
|---|----------|-------------|
| **ADM-06** | **P1** | **Pas de vue admin des sessions de tous les users du tenant.** `GET /sessions` ne montre que les sessions du user connecte. Un admin ne peut pas voir/revoquer les sessions d'un employe compromis. Endpoint `/admin/sessions` → 404. |
| **ADM-07** | P2 | `DELETE /sessions` (revoke all) revoque aussi la session courante. Le user s'auto-deconnecte. Le frontend devrait avoir un "Deconnecter tous les autres appareils" qui preserve la session courante. |
| **ADM-08** | P3 | `GET /sessions/me` → 405 Method Not Allowed. Route manquante ou mal configuree. |
| **ADM-09** | P3 | Les sessions ne contiennent pas l'email/nom du user. Pour un admin qui verrait les sessions d'equipe (si ADM-06 etait corrige), il n'y aurait pas moyen d'identifier a qui appartient une session. |

---

## 3. Audit Logs (`/api/v1/audit`)

### Ce qui fonctionne

| Action | Endpoint | HTTP | Resultat |
|--------|----------|------|----------|
| Lister | `GET /audit` | 200 | 3096 logs, paginee (skip/limit) |
| Filtre action | `GET /audit?action=LOGIN_SUCCESS` | 200 | 451 resultats |
| Filtre entity_type | `GET /audit?entity_type=User` | 200 | 96 resultats |
| Action inexistante | `GET /audit?action=X` | 200 | 0 resultats (pas d'erreur) |
| Champs | — | — | id, account_id, tenant_id, action, entity_type, entity_id, changes, description, ip_address, user_agent, request_id, created_at |
| HMAC en DB | — | — | Champ `hmac_signature` present en base pour integrite |

### Bugs et gaps

| # | Severite | Description |
|---|----------|-------------|
| **ADM-10** | P2 | **Pagination off-by-one** : Page 1 ids=[3431,3430], Page 2 ids=[3430,3429]. L'id 3430 apparait dans les 2 pages. Cause probable : chaque `GET /audit` cree un log `READ_SENSITIVE` qui decale les resultats entre les requetes. |
| **ADM-11** | **P1** | **Filtre date audit → 500 Internal Error.** Les params `start_date`/`end_date` existent (`audit.py:22-23`) mais crashent avec `asyncpg.DataError: can't subtract offset-naive and offset-aware datetimes`. Le `Query(None)` parse la date en datetime naive (sans timezone) mais `AuditLog.created_at` est `timestamp with time zone`. Fix : ajouter `AwareDatetime` type hint ou forcer UTC dans le handler. |
| **ADM-12** | P3 | `hmac_signature` existe en DB mais n'est PAS expose dans la reponse API. Pas de endpoint de verification d'integrite. Le champ est inutilisable cote frontend/admin. |
| **ADM-13** | P3 | Boucle d'auto-audit : chaque `GET /audit` genere un log `READ_SENSITIVE`, gonflant les logs. Sur 3096 logs, une proportion significative est de la lecture d'audit. Devrait etre configurable ou exclu. |
| **ADM-14** | P3 | Pas de filtre par `account_id` pour voir les actions d'un user specifique. |

---

## 4. API Keys (`/api/v1/api-keys`)

### Ce qui fonctionne

| Action | Endpoint | HTTP | Resultat |
|--------|----------|------|----------|
| Lister | `GET /api-keys` | 200 | Liste avec key_prefix (pas la cle complete) |
| Creer | `POST /api-keys` | 200 | Retourne `full_key` une seule fois, bon pattern |
| Supprimer | `DELETE /api-keys/{id}` | 200 | Soft-delete (is_active=false), disparait du listing |
| Scopes | — | — | Scopes definis a la creation |

### Bugs et gaps

| # | Severite | Description |
|---|----------|-------------|
| **ADM-15** | **P1-SECU** | **500 Internal Error sur scope enforcement API key.** Cause racine verifiee : `GET /users` utilise `UserReaderScope` (`deps.py:810`) qui depend de `require_scope_user` (`deps.py:725`), qui appelle `get_current_user_async` (`deps.py:739`). Cette fonction ne gere QUE les JWT tokens. Avec une API key (header X-API-Key), `token` est `None` → 401 leve par `deps.py:226-227`. L'exception cascade et devient 500. La solution : utiliser `get_current_principal` au lieu de `get_current_user_async` dans `require_scope_user`, puis verifier les scopes de l'`ApiKeyClient`. |
| **ADM-16** | P2 | API key sur `/products` retourne une reponse incomplete (total absent). L'authentification par API key semble ne pas fonctionner correctement pour certains endpoints. |
| **ADM-17** | P3 | Pas de possibilite de renouveler/rotater une cle. Il faut supprimer et recreer. |
| **ADM-18** | P3 | Pas d'expiration automatique configurable a la creation (champ `expires_at` toujours null). |

---

## 5. Feature Flags (`/api/v1/features`)

### Ce qui fonctionne

| Action | Endpoint | HTTP | Resultat |
|--------|----------|------|----------|
| Lister | `GET /features` | 200 | Liste avec target_tenants, rollout_pct |
| Creer | `POST /features` | 200 | Cree avec name, description, is_enabled |
| Modifier | `PATCH /features/{id}` | 200 | Toggle is_enabled OK |
| Supprimer | `DELETE /features/{id}` | 204 | Suppression reelle (pas soft-delete) |

### Bugs et gaps

| # | Severite | Description |
|---|----------|-------------|
| **ADM-19** | P2 | **Pas de lookup par nom** : `PATCH /features/{name}` → 422 (attend un int). Le frontend doit connaitre l'ID numerique. |
| **ADM-20** | P3 | Schema reponse incoherent : GET list ne retourne pas `metadata_json`, POST/PATCH le retournent. |
| **ADM-21** | P2 | **Scope feature flags global** : un tenant_admin peut creer un flag sans `target_tenants` qui sera potentiellement visible par tous les tenants. Pas de contrainte forçant le flag au tenant courant. |
| **ADM-22** | P3 | Suppression reelle (204) vs soft-delete pour users/api-keys. Incoherence de pattern. |

---

## 6. VPN WireGuard (`/api/v1/vpn`)

### Comportement observe

| Action | Endpoint | HTTP | Resultat |
|--------|----------|------|----------|
| Status | `GET /vpn/status` | 503 | "WireGuard service unavailable" |
| Peers | `GET /vpn/peers` | 503 | Idem |

### Observations

| # | Severite | Description |
|---|----------|-------------|
| **ADM-23** | P3 | Service non deploye en dev, 503 attendu. Message d'erreur clair. |
| **ADM-24** | P3 | Le scope `vpn:admin` existe en DB mais n'est pas dans les permissions du tenant_admin (auth/me renvoie `vpn:read` et `vpn:write` mais pas `vpn:admin`). |

---

## 7. Settings Tenant (`/api/v1/admin/settings`)

### Ce qui fonctionne

| Action | Endpoint | HTTP | Resultat |
|--------|----------|------|----------|
| Lire | `GET /admin/settings` | 200 | Retourne company_name, rates, etc. |
| Modifier | `PATCH /admin/settings` | 200 | Mise a jour partielle OK |

### Bugs et gaps

| # | Severite | Description |
|---|----------|-------------|
| **ADM-25** | P3 | `PUT /admin/settings` → 405. Pas de full replace. Seul PATCH existe. |
| **ADM-26** | P3 | `/settings` (sans /admin/) → 404. Incoherence de nommage. Le frontend doit deviner le prefixe. |
| **ADM-27** | P2 | Valeurs initiales toutes null (company_name, email, phone, address). Le tenant est cree sans donnees d'entreprise. Pas de wizard/onboarding. |

---

## 8. Dashboard Admin

### Comportement observe

| Action | Endpoint | HTTP | Resultat |
|--------|----------|------|----------|
| Dashboard | `GET /dashboard` | 404 | Endpoint inexistant |
| Dashboard summary | `GET /dashboard/summary` | 404 | Idem |
| Operations | `GET /operations/summary` | 200 | Departs/retours du jour |

### Gaps

| # | Severite | Description |
|---|----------|-------------|
| **ADM-28** | P2 | **Pas d'endpoint dashboard consolide.** Le frontend doit appeler N endpoints separement. Pas de KPI admin (nb users, sessions actives, revenue, etc.). |

---

## 9. Observations transversales

| # | Severite | Description |
|---|----------|-------------|
| **ADM-29** | P2 | **1 seul user visible sur le frontend** (confirme par l'utilisateur). GET /users retourne 1 user pour tenant 1. Le 2e compte (admin@massacorp.fr) est sur tenant 2 → isolation OK, mais l'admin ne peut pas gerer les autres tenants. Pas de tenant switcher. |
| **ADM-30** | P1 | **Pas de gestion multi-tenant cote frontend admin.** L'admin@carocorp.dev a des memberships sur 3 tenants mais le token est lie a un seul tenant (tid=1). Pas de moyen de switcher de tenant sans refaire un login specifique. |
| **ADM-31** | P3 | Le login utilise `username` (form-encoded, OAuth2PasswordRequestForm) et non `email` (JSON). Incoherence avec le modele Account qui a un champ `email`. |
| **ADM-32** | P3 | `GET /health` retourne juste `{"status":"ok"}`. Pas de details (DB, Redis, Celery). Un admin ne peut pas diagnostiquer quel service est en panne. |

---

## 8bis. Dashboard Admin (endpoints reels)

Le dashboard a 6 sous-endpoints fonctionnels, contrairement a l'observation initiale (`/dashboard` seul → 404).

### Ce qui fonctionne

| Action | Endpoint | HTTP | Resultat |
|--------|----------|------|----------|
| Stats KPI | `GET /dashboard/stats` | 200 | active_reservations, monthly_revenue_cents, overdue_invoices, low_stock, etc. |
| Finances | `GET /dashboard/finances?year=2026` | 200 | 12 mois, revenue_cents, invoices_paid/overdue par mois |
| Today | `GET /dashboard/today` | 200 | Departs et retours du jour |
| Activity | `GET /dashboard/activity` | 200 | Feed d'activite recente (factures payees, etc.) |
| Analytics | `GET /dashboard/analytics` | 200 | avg_basket, utilization_rate, top_products, seasonality |
| Export | `GET /dashboard/finances/export` | 200 | CSV export (scope reports:export) |

**Correction ADM-28** : le dashboard existe bien via sub-endpoints. Le frontend doit appeler N endpoints et aggreger, mais les donnees sont la.

---

## 9. Frontend vs Backend — Gaps de cablage

Analyse croisee : ce que le frontend appelle vs ce que le backend expose.

### Endpoints mal cables (frontend appelle un path qui n'existe pas cote backend)

| # | Severite | Frontend appelle | Backend expose | Resultat | Impact |
|---|----------|------------------|----------------|----------|--------|
| ~~GAP-01~~ | ~~P1~~ | FAUX POSITIF — Verifie dans `frontend/apps/marveline/src/api/featureFlags.ts:17` : le frontend appelle bien `/features` (pas `/admin/features`). Paths alignes. ||
| ~~GAP-02~~ | ~~P1~~ | FAUX POSITIF — Verifie dans `frontend/apps/marveline/src/api/apiKeys.ts:22` : le frontend appelle bien `/api-keys` (pas `/api/keys`). Paths alignes. ||
| ~~GAP-03~~ | ~~P2~~ | FAUX POSITIF — Le frontend utilise `PATCH /features/{id}` avec `{ is_enabled }` (`featureFlags.ts:37`), pas `POST .../toggle`. Correct. ||

### Endpoints qui existent cote backend mais auxquels le frontend ne correspond pas

| # | Endpoint backend | Frontend | Gap |
|---|-----------------|----------|-----|
| **GAP-04** | `GET /admin/tenants/{tid}/sessions` | `AdminTenantSessionsPage` existe | Le frontend a la page mais le `tid` doit etre passe — le frontend hardcode-t-il le tenant_id courant ? |
| **GAP-05** | `GET /audit/user/{uid}` | `useUserAuditLogs(userId)` existe | **Retourne 0 resultats — 100% des 3388 logs ont `account_id=NULL`.** Cause racine : `app/services/audit.py:122-133` — `AuditLog()` est cree SANS passer `account_id`. Le parametre `user_id` est recu par `log_action()` (ligne 73) mais jamais assigne au modele AuditLog. Fix : ajouter `account_id=user_id` a la ligne 123. |
| ~~GAP-06~~ | ~~P2~~ | FAUX POSITIF — Verifie dans `frontend/apps/marveline/src/api/admin.ts:20-21` : le frontend convertit `from_date` → `start_date` et `to_date` → `end_date` avant envoi. Backend attend `start_date`/`end_date` (`audit.py:22-23`). Params alignes. |
| **GAP-07** | `POST /api-keys/{id}/rotate` | `useRotateApiKey()` existe | **Fonctionne** (teste 200) mais le frontend appelle-t-il le bon path ? |
| **GAP-08** | `POST /users/invite` | `useInviteUser()` existe | **Fonctionne** (teste 200, `invite_sent: true`) — pas de verification email Mailpit |
| **GAP-09** | `POST /users/{id}/unlock` | `useUnlockUser()` existe | Retourne 403 `STEP_UP_REQUIRED` — le frontend gere-t-il le flow step-up MFA ? |

### Donnees manquantes dans les reponses API

| # | Severite | Endpoint | Champ manquant | Impact frontend |
|---|----------|----------|----------------|-----------------|
| **GAP-10** | **P1** | `GET /admin/tenants/{tid}/sessions` | `account_id`, `email`, `user_name` absents | Confirme dans `sessions.py:194-203` : `_make_session_response()` ne mappe que 6 champs depuis `AccountSession` sans JOIN sur `accounts`. Le schema `SessionResponse` (`session.py:7-53`) ne definit pas de champs identite. Meme schema partage entre self-service et admin. |
| **GAP-11** | P2 | `GET /sessions` | `account_id`, `email` absents | Idem pour la vue self-service (moindre impact car c'est ses propres sessions) |
| **GAP-12** | P2 | `GET /audit` | `hmac_signature` absent de la reponse | Pas de verification d'integrite possible |
| **GAP-13** | P3 | `GET /features` (list) | `metadata_json`, `updated_at` absents | Schema incomplet vs POST/PATCH |

---

## 10. Health & Monitoring

### Ce qui fonctionne

| Action | Endpoint | HTTP | Resultat |
|--------|----------|------|----------|
| Liveness | `GET /health` | 200 | `{"status":"ok"}` — simple alive check |
| Liveness alias | `GET /health/live` | 200 | Idem |
| Readiness | `GET /health/ready` | 200 | Checks postgres (healthy, 114ms), redis (healthy, 1.3ms), celery (unreachable) |
| Status page | `GET /health/status` | 200 | degradation_level: NOMINAL, components: redis_sec, redis_cache, api |

### Observations

| # | Severite | Description |
|---|----------|-------------|
| **ADM-33** | P2 | `/health/ready` retourne `status: not_ready` car Celery est unreachable. Mais `/health/status` dit `NOMINAL`. Incoherence entre les deux endpoints de sante. |
| **ADM-34** | P3 | `/health/status` ne verifie pas Celery ni PostgreSQL — seulement Redis et API. Faux sentiment de securite. |

---

## 11. MFA / Step-up

### Ce qui fonctionne

| Action | Endpoint | HTTP | Resultat |
|--------|----------|------|----------|
| Status MFA | `GET /mfa/status` | 200 | `mfa_enabled: false, recovery_codes_remaining: 0` |
| Step-up requis | `POST /users/{id}/unlock` | 403 | `STEP_UP_REQUIRED` — protection correcte |

### Observations

| # | Severite | Description |
|---|----------|-------------|
| **ADM-35** | P2 | **MFA non active** pour le seul admin du systeme. Un compte `tenant_admin` devrait exiger MFA. Aucune politique forçant le setup MFA pour les roles privilegies. |
| **ADM-36** | P2 | Le flow step-up MFA bloque `POST /users/{id}/unlock` — mais MFA n'etant pas active (ADM-35), cette action est **permanemment inaccessible**. Impasse fonctionnelle. |

---

## 12. ETL Admin

### Ce qui fonctionne

| Action | Endpoint | HTTP | Resultat |
|--------|----------|------|----------|
| Conflicts | `GET /admin/etl/conflicts` | 200 | 843 conflits en base |
| Imports | `GET /admin/etl/imports` | 200 | 1078 imports en base |

### Observations

| # | Severite | Description |
|---|----------|-------------|
| **ADM-37** | P3 | 843 conflits ETL non resolus. Volume important qui pourrait necessiter une alerte admin. |
| **ADM-38** | P3 | Les pages ETL existent dans le frontend (`EtlImportsPage`, `EtlConflictsPage`) mais ne sont PAS dans la navigation admin SubNav. Pages orphelines. |

---

## 13. Loyalty Admin

Le frontend a 4 pages loyalty (`/admin/loyalty`, `/admin/loyalty-members`, `/admin/loyalty-rewards`, `/admin/loyalty-flash`) dans la nav admin.

### Non teste

Ces endpoints n'ont pas ete testes dans cette session. A verifier :
- `GET /loyalty/programs`
- `GET /loyalty/members`
- `GET /loyalty/rewards`
- Comportement backend reel vs frontend attendu

---

## Resume des severites (verifie dans le code)

| Severite | Count | IDs | Verifie |
|----------|-------|-----|---------|
| **P0** (bloquant secu) | 1 | ADM-01 (escalade privilege) | `rbac.py:228` existe, jamais appele dans `user.py:150,230` |
| **P1** (critique) | 4 | ADM-11 (audit date 500), ADM-15 (API key scope 500), GAP-05 (`account_id=NULL` dans 3388 logs), GAP-10 (sessions admin sans identite) | Toutes causes racines identifiees |
| **P2** (important) | 9 | ADM-02, ADM-05, ADM-07, ADM-10, ADM-14, ADM-16, ADM-21, ADM-27, ADM-29, ADM-30, ADM-33, ADM-35, ADM-36 | |
| **P3** (mineur) | 14 | ADM-03, ADM-04, ADM-08, ADM-09, ADM-12, ADM-13, ADM-17, ADM-18, ADM-19, ADM-20, ADM-22, ADM-23, ADM-24, ADM-25, ADM-26, ADM-31, ADM-34, ADM-37, ADM-38 | |
| **FAUX POSITIFS** | 4 | ~~GAP-01~~, ~~GAP-02~~, ~~GAP-03~~, ~~GAP-06~~ | Paths frontend/backend alignes (verifie dans le code) |

**Notes corrections** :
- ~~ADM-06~~ → reclasse. L'endpoint `/admin/tenants/{tid}/sessions` existe. Le vrai probleme est GAP-10 (pas de user info).
- ~~ADM-28~~ → corrige. Les endpoints `/dashboard/stats`, `/dashboard/finances`, etc. existent et fonctionnent.
- ~~ADM-32~~ → corrige. `/health/ready` donne les details (postgres, redis, celery). `/health` est le liveness probe minimal.
- ADM-11 → reclasse P1 (500 Internal Error, pas juste un gap fonctionnel)

---

## Actions prioritaires (classees par impact, avec fix exact)

### Immediate (P0 + P1 — causes racines identifiees)

| # | Bug | Fichier | Ligne | Fix |
|---|-----|---------|-------|-----|
| 1 | **ADM-01** | `app/services/user.py` | 150, 230 | Appeler `can_manage_role(admin_user.role, role)` de `rbac.py:228` avant d'assigner le role. Bloquer si `False`. |
| 2 | **GAP-05** | `app/services/audit.py` | 122-133 | Ajouter `account_id=user_id` dans le constructeur `AuditLog()`. Backfill les 3388 logs existants via migration. |
| 3 | **ADM-11** | `app/api/v1/endpoints/audit.py` | 22-23 | Changer le type hint de `datetime` a `AwareDatetime` (Pydantic) ou ajouter `.replace(tzinfo=timezone.utc)` si naive. |
| 4 | **ADM-15** | `app/core/deps.py` | 739 | Dans `require_scope_user`, utiliser `get_current_principal` au lieu de `get_current_user_async`. Gerer `ApiKeyClient` avec ses scopes propres. |
| 5 | **GAP-10** | `app/api/v1/endpoints/sessions.py` | 215-227 | JOIN `AccountSession` → `Account` dans la query admin. Ajouter `account_id`, `email` dans `SessionResponse` (ou creer `AdminSessionResponse`). |

### Court terme (P2 structurels)

| # | Bug | Description | Fix |
|---|-----|-------------|-----|
| 6 | **ADM-05** | `validate_password_strength` appele sans role | `user.py:150` → passer `role=data.role` |
| 7 | **ADM-35+36** | MFA non active pour admin, step-up bloquant | Politique MFA obligatoire pour tenant_admin/super_admin |
| 8 | **ADM-30** | Pas de tenant switcher | Designer `POST /auth/switch-tenant` avec re-emission JWT |
| 9 | **ADM-33** | `/health/ready` vs `/health/status` incoherents | Aligner les checks (Celery absent dans status) |
| 10 | **ADM-07** | `DELETE /sessions` revoque la session courante | Exclure la session courante du revoke all |
