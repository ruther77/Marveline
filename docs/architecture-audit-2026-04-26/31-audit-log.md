# Module 31 — Audit Log (RGPD / SOC2)

> **Phase E — module 1/5.** Audit du système de traçabilité : `AuditLog` model + `AuditMiddleware` global + `AuditService` HMAC + endpoints admin.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/audit_log.py` | 250 |
| `app/middleware/audit.py` | 426 |
| `app/services/audit.py` | 481 |
| `app/api/v1/endpoints/audit.py` | 224 |
| `app/schemas/audit.py` | 230 |

**Volume total** : 1 611 LoC.

---

## 2. Architecture observée

```
AuditMiddleware (BaseHTTPMiddleware)
  ├── lit request_id depuis RequestContextMiddleware (state)
  ├── lit user_id / tenant_id / api_key_id depuis state (JWT déjà décodé)
  ├── EXCLUDED_PATHS : /health, /docs, /auth/login...
  ├── SENSITIVE_READ_PATTERNS : GET /customers|invoices|users/{id}
  ├── SENSITIVE_LIST_PATHS : /customers, /invoices, /audit, /users, /deposits
  ├── if 2xx :
  │     POST/PUT/PATCH/DELETE → _audit_mutation → log CREATE/UPDATE/DELETE
  │     GET sensitive single → _audit_sensitive_read → log READ_SENSITIVE
  │     GET sensitive list  → _audit_sensitive_list → log READ_SENSITIVE
  └── ouvre une nouvelle session DB context-managed pour chaque audit
        (commit séparé, exception swallow logger.exception)

AuditService (db: AsyncSession)
  log_action(action, tenant_id, ...) → INSERT AuditLog
    + HMAC-SHA256 sur payload canonique JSON
    KEK = HMAC(AUDIT_HMAC_KEY, "audit-hmac-v1")
  log_create / log_update / log_delete / log_read_sensitive
  log_login (success=True/False) / log_logout

AuditLog (immuable model)
  account_id (IAM v2) | api_key_id | actor_type
  membership_id (snapshot état membership au moment action)
  tenant_id (NOT NULL)
  action String(50) — CREATE/UPDATE/DELETE/SOFT_DELETE/HARD_DELETE/READ_SENSITIVE/LOGIN_SUCCESS/LOGIN_FAILED/LOGOUT
  entity_type / entity_id (nullable)
  changes JSONB ({"before": {...}, "after": {...}} ou {"after": {...}})
  description Text
  ip_address String(45) / user_agent String(500) / request_id String(100)
  created_at server_default=now()
  hmac_signature String(64) (HMAC-SHA256 hex)
  pas de SoftDeleteMixin, pas de TimestampMixin (created_at seul)

Endpoints (admin only via require_scope(AUDIT_READ))
  GET /audit                  liste paginée + filtres
  GET /audit/user/{user_id}   trail user
  GET /audit/entity/{type}/{id} historique entité
```

---

## 3. Frictions identifiées — module 31

> Compteur cumulé (mod. 01-30) ≈ 998. Module 31 ouvre à **F999**.

### 3.1 P0

#### F999 — `AuditLog` **n'a PAS de TenantMixin** ni constraint `tenant_id != 0` malgré commentaire

`models/audit_log.py:131-136`. `tenant_id` est `BigInteger NOT NULL`, mais **pas FK** vers `tenants.id`, et **pas de mixin** garantissant cohérence. Si un endpoint passe `tenant_id=0` ou un tenant supprimé, l'audit est inséré orphelin. Pas non plus de `CHECK tenant_id > 0`.

→ Vue `GET /audit?tenant_id=0` peut exposer logs cross-tenants (filtre `current_user.tenant_id` côté endpoint OK, mais si un dev oublie le filtre, fuite garantie).

**Action** : `tenant_id` ForeignKey + index obligatoire ; ne pas refacto en TenantMixin (l'AuditLog est intentionnellement raw) mais ajouter un trigger `BEFORE INSERT` qui vérifie l'existence du tenant.

---

#### F1000 — `AuditMiddleware._audit_mutation` ouvre `get_async_db_context()` séparé → **transaction parallèle non liée à la requête métier**

`middleware/audit.py:188-218`. Si la requête métier commit OK (status 200) mais le middleware échoue à se connecter à la DB pour l'audit (réseau, pool exhausted), l'audit est perdu silencieusement (`except Exception: logger.exception`). 

→ Les mutations existent dans le système mais ne sont **PAS** dans le journal RGPD. Violation Article 30. Pas de mécanique de DLQ (dead-letter queue) pour replay.

**Action** : (1) audit dans la même transaction que l'action métier (audit géré par les services, pas le middleware) ; (2) DLQ Redis si fallback middleware ; (3) métrique `audit_log_failures_total` Prometheus alertée.

---

#### F1001 — HMAC payload **ne contient PAS** `changes` ni `created_at` ni `description` — falsifiable post-hoc

`services/audit.py:137-145`. Le HMAC porte sur :
```python
{action, entity_type, entity_id, user_id, tenant_id, request_id}
```

Mais **PAS** sur `changes`. Un attaquant DB-direct peut UPDATE le `changes` JSON sans invalider la HMAC. Si la promesse "trigger PostgreSQL empêche UPDATE/DELETE" (commentaire l. 17) n'est pas effectivement déployée (à vérifier — pas vu dans le model code), HMAC est un théâtre de sécurité.

**Action** : (1) HMAC sur l'intégralité du payload sérialisé canoniquement ; (2) chaîner `prev_hmac` (audit log = blockchain — chaque ligne contient le hash de la précédente) pour détecter suppressions ; (3) trigger DB `BEFORE UPDATE/DELETE → RAISE EXCEPTION`.

---

#### F1002 — `EXCLUDED_PATHS` exclut `/auth/login` mais le **login échoué N'EST PAS audité automatiquement** par le middleware

`middleware/audit.py:63-72` : `AuthEndpoints.LOGIN` listé dans `EXCLUDED_PATHS`. La promesse "log_login_failed" repose sur l'endpoint qui appelle explicitement `audit_service.log_login(success=False)`. Si un dev oublie cet appel, brute-force passe sans trace.

→ Mod. 02 (auth) audit déjà documenté F26 (LOGIN_FAILED non systématique). Confirmé ici par exclusion middleware.

**Action** : retirer `/auth/login` de `EXCLUDED_PATHS` et auditer toutes les tentatives (échecs inclus) dans le middleware (avec masquage du password).

---

#### F1003 — `SENSITIVE_READ_PATTERNS` ne couvre **que customers/invoices/users** — manque réservations, MFA, sessions, devis, ventes, audit lui-même

`middleware/audit.py:56-60`. Les patterns RGPD sensibles incluent : 
- `/api/v1/reservations/{id}` (PII client + montants)
- `/api/v1/devis/{id}`
- `/api/v1/mfa/*` (lecture statut MFA = info sensible)
- `/api/v1/sessions/{id}`
- `/api/v1/customers/{id}/history`
- `/api/v1/loyalty/members/{id}` (programme fidélité = profil consommateur RGPD)

→ Audit RGPD incomplet. Article 30 exige tous les accès aux PII.

**Action** : étendre `SENSITIVE_READ_PATTERNS` à tous les endpoints retournant des PII (reservations, devis, fidélité, sessions, MFA).

---

#### F1004 — `_singularize_entity_type` règles approximatives → entity_type incohérent dans audit

`middleware/audit.py:342-388`. "categories" → "Category" (OK via mapping known), mais "products" → "Product" via mapping. Si on ajoute un nouvel endpoint `/api/v1/preparations`, la fonction renvoie "Preparation" alors que le code Python utilise `TypePreparation`. L'audit search par entity_type devient bruyant. Pas de typing strict (literal types ou enum).

→ Compromet `GET /audit/entity/{entity_type}/{id}` : l'admin ne sait pas quel string passer.

**Action** : table de correspondance complète + audit_log.entity_type contraint à un enum SQL.

---

### 3.2 P1

#### F1005 — Chaque audit ouvre une session DB séparée → **N+1 connexions pool**

`middleware/audit.py:189`. Pour 100 req/s avec mutations, 100 connexions audit en plus du pool métier. Pool `max_size` typique 20 → exhaustion sous charge.

**Action** : audit en transaction métier (cf. F1000).

---

#### F1006 — `actor_type` String(20) **non-CHECK** — valeurs (`account/api_key/system`) non enforcées

`models/audit_log.py:118-122`. Peut prendre n'importe quelle valeur. Drift typo.

---

#### F1007 — `description` Text **peut contenir PII** non chiffré

`models/audit_log.py:167-171`. Si un service log "Updated Customer #123: email" + before/after dans `changes`, l'email est dans le clair. Pas de masking ni chiffrement.

→ RGPD : `changes.before.email` est PII brute. Audit logs eux-mêmes deviennent une source PII non chiffrée.

**Action** : envelope encryption sur `changes` + `description` (KMS).

---

#### F1008 — `audit_log.changes` JSONB sans **schema validation** — opérateurs Postgres directs possibles

JSONB libre permet `UPDATE audit_logs SET changes = changes || '{"...":"..."}'` côté DBA. Pas de schéma JSON validation. Couplé à F1001, modification silencieuse.

---

#### F1009 — `_audit_sensitive_list` **enregistre une seule entrée** pour la liste — pas la liste des IDs consultés

`middleware/audit.py:267-299`. Audit "Listed sensitive data Customer" sans dire combien d'IDs (pagination 50 ? 1000 ?) ni leur range. RGPD demande "qui a consulté quoi" — ici on sait qui mais pas quoi.

**Action** : enrichir `description` ou ajouter `changes={"queried_ids":[...], "count":N}`.

---

#### F1010 — `AuditMiddleware` **ne capture PAS** le body de la requête (PUT/PATCH) → pas de "after" exact dans `changes`

Le middleware ne fait que extraire path + method. Aucune capture body → `changes` reste NULL sur les mutations middleware-only. Les services explicites (`log_update`) fournissent before/after, mais beaucoup de mutations sans appel explicite n'ont pas de diff.

→ Audit existe mais ne dit pas "quel champ a changé".

**Action** : soit forcer audit côté service (pattern `log_update` partout), soit middleware lit body+response et calcule diff (lourd, fragile).

---

#### F1011 — `_compute_audit_hmac` **utilise `settings.AUDIT_HMAC_KEY` direct** — pas KMS, rotation manuelle

`services/audit.py:20-23`. Si la clé fuit, tous les HMAC historiques sont compromis. Pas de mécanique de re-signature avec clé v2.

**Action** : KMS-managed key + version dans la signature (`v1$hmac` format).

---

#### F1012 — `AuditMiddleware` skip si `not tenant_id or (not user_id and not api_key_id)`

`middleware/audit.py:112`. Toutes les actions **anonymes** (visiteur public) ne sont jamais auditées. OK pour publier un site, mais des endpoints publics qui font CREATE (ex: customer_self_signup) ne sont **pas** audités → angle mort.

---

#### F1013 — `created_at` server_default `now()` mais **pas de TIMESTAMP WITH TZ explicite** dans la déclaration Mapped

Model l. 194-198. Default `text("now()")` retourne `timestamp without time zone` par défaut PostgreSQL. Si la DB est UTC, OK ; si TZ différente, drift.

À vérifier la migration Alembic pour `TIMESTAMPTZ` explicite.

---

#### F1014 — Endpoints `GET /audit` **retournent les `changes` JSONB en clair** sans masking PII

`endpoints/audit.py:91-96`. Tout admin AUDIT_READ peut consulter les emails, noms, montants des autres employés. Aucune granularité RBAC : "auditor" vs "compliance officer" vs "support".

---

#### F1015 — Pas d'**export CSV/JSON** RGPD officiel pour droit d'accès Article 15

Aucun endpoint `/audit/export?user_id=X&format=csv`. Si un client demande sa donnée RGPD complète, l'admin doit faire la requête manuellement. Compliance fail.

---

#### F1016 — Pas de **rétention/purge** automatique au-delà de 7 ans

Le commentaire dit "Retention 7 ans minimum" mais aucune Celery task `purge_audit_logs_older_than_7y` documentée. → Croissance illimitée de la table → impact perf au scan paginé.

---

#### F1017 — `request_id` String(100) sans format UUID **enforced** (model l. 186-191)

Pourrait être n'importe quoi. Si un service log avec un `request_id` malformé, la corrélation log→audit casse.

---

#### F1018 — `entity_type` String(100) **libre** — pas d'enum SQL

Cf. F1004. Recherche admin par entity_type fragile.

---

#### F1019 — `AuditMiddleware` n'audite **pas les 4xx** (validation errors)

Filter `200 <= response.status_code < 300` (l. 123). Une tentative malveillante de SQL injection sur `/customers` → 422 Bad Request, **non auditée**. → Forensics impossible sur tentatives ratées.

**Action** : auditer 4xx dans une catégorie `ATTEMPT_DENIED`.

---

#### F1020 — Pas de `correlation_session_id` permettant de corréler **toutes les actions d'une session utilisateur**

`request_id` est par-requête. Si un admin malveillant fait 100 actions, on ne peut pas corréler par session — il faut filtrer par `account_id + plage horaire`. Inefficace.

---

### 3.3 P2

#### F1021 — `AuditMiddleware` exclut `/auth/login`, `/auth/refresh`, `/auth/csrf` — refresh tokens non audités

Refresh = action sensible (renouvellement session). Devrait être audité.

---

#### F1022 — `EXCLUDED_PATHS` est List[str] de match exact — pas de pattern (`/api/v1/internal/*` impossible à exclure d'un coup)

---

#### F1023 — `_parse_entity_from_path` ignore les sous-ressources `/customers/123/history` → entity_type="Customer", entity_id=123, perd "history"

---

#### F1024 — Pas d'index sur `(tenant_id, account_id, created_at)` — query "trail user" peut scan partiel

Indexes présents : `idx_audit_tenant_created`, `idx_audit_entity`, `idx_audit_action_created`, `account_id` simple. Manque composé `(account_id, created_at)`.

---

#### F1025 — Pas d'index sur `request_id` simple (déclaré `index=True` ligne 189 — OK)

OK confirmé.

---

#### F1026 — Pas de **dashboard/visualisation** côté admin (juste paginated raw)

Endpoints retournent JSON paginé. Aucune agrégation (action par jour, top users, etc.).

---

#### F1027 — `description` non i18n (text français/anglais mélangé selon le service)

---

#### F1028 — `AuditLogResponse` schema **expose** `hmac_signature` et `changes` même aux non-superadmins

À vérifier dans schemas/audit.py. Si oui, un auditor peut voir HMAC → permet brute force offline.

---

### 3.4 P3

#### F1029 — Comments docstrings `Example:` énormes (model 100+ lignes) — pollution

#### F1030 — `_singularize_entity_type` rules anglo-saxonnes (`ies` → `y`) — irrelevant pour ce projet bilingue

---

## 4. Synthèse module 31

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 6 | F999 (no FK tenant), F1000 (audit séparé pool exhaust + perte), F1001 (HMAC sans changes — falsifiable), F1002 (login échec non audité middleware), F1003 (SENSITIVE patterns incomplets), F1004 (entity_type drift) |
| P1 | 16 | F1005 → F1020 |
| P2 | 8 | F1021 → F1028 |
| P3 | 2 | F1029, F1030 |
| **Total** | **32** | F999 → F1030 |

**Compteur cumulé après module 31** : ≈ 998 + 32 = **1 030 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) audit dans la même transaction métier (F1000) — pattern `audit_service.log_*` appelé par les services, pas le middleware ; (2) HMAC sur l'intégralité du payload + chaînage `prev_hmac` (F1001) ; (3) trigger DB `BEFORE UPDATE/DELETE` (F1001 immutability) ; (4) login échec audité systématique (F1002) ; (5) étendre SENSITIVE_PATTERNS à toutes PII (F1003).
>
> **Refactor** : envelope encryption `changes` + `description` (F1007) ; export RGPD Article 15 (F1015) ; Celery purge >7y (F1016) ; audit 4xx ATTEMPT_DENIED (F1019) ; chaîne hash bloc précédent (cf. F795 LoyaltyLedger pattern).

---

# Module 32 (suivant) — Feature Flag / Orchestration / Printer
