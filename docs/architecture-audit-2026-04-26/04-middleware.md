# Module 04 — Middlewares

## 1. Périmètre

| Fichier | LoC | Rôle |
|---|---|---|
| `app/middleware/__init__.py` | 23 | Re-export des classes (mais `StrictCORSMiddleware`, `DegradedModeMiddleware`, `AppEnforcementMiddleware` sont absents du `__all__`) |
| `app/middleware/timing.py` | 48 | `TimingMiddleware` — header `X-Response-Time`, log WARN si > 1000ms |
| `app/middleware/cors.py` | 92 | `StrictCORSMiddleware` — defense-in-depth CORS, bloque origines hors whitelist en 403 |
| `app/middleware/app_enforcement.py` | 119 | `AppEnforcementMiddleware` — ISO-APP-01, vérifie `tenant.app_code == X-App-Code` (déjà couvert §S03 module 01) |
| `app/middleware/degraded.py` | 161 | `DegradedModeMiddleware` — 4 niveaux (NOMINAL, READ_ONLY, AUTH_DOWN, EMERGENCY_BYPASS) + dégradation par app |
| `app/middleware/request_context.py` | 165 | `RequestContextMiddleware` — UUID request_id, dual-mode JWT/API-key, peuple `request.state` + ContextVars |
| `app/middleware/metrics.py` | 181 | `MetricsMiddleware` — Prometheus RED + path normalization + détection 429 |
| `app/middleware/exception_handler.py` | 232 | `register_exception_handlers` — handlers AppException, HTTPException, ValidationError, generic |
| `app/middleware/security.py` | 405 | `CSRFProtectionMiddleware`, `SecurityHeadersMiddleware`, `RateLimitMiddleware` |
| `app/middleware/audit.py` | 426 | `AuditMiddleware` — log mutations + lectures sensibles RGPD |
| `app/main.py` (extrait) | 90-160 | Ordre d'ajout des middlewares (LIFO) |

**Total** : 1 852 LoC.

**Dépend de** : `app/core/{config, database, security, redis, rate_limiter, rate_limit_utils, deps, logging, metrics}`, `app/services/{audit, api_key}`, `app/models/tenant`, `app/constants/*`.

**Dépendu par** : `app/main.py` (composition de la chaîne), tous les endpoints (transitivement).

---

## 2. Lecture par fichier

### 2.1 Ordre d'exécution effectif

`main.py:104-159` ajoute les middlewares en LIFO (dernier ajouté = premier exécuté à l'inbound). Reconstitution de la chaîne réelle :

| # | Inbound (request) | Outbound (response) |
|---|---|---|
| 1 | `MetricsMiddleware` | `MetricsMiddleware` (record duration) |
| 2 | `TimingMiddleware` | `TimingMiddleware` (set X-Response-Time) |
| 3 | `TrustedHostMiddleware` (Starlette) | — |
| 4 | `StrictCORSMiddleware` | `StrictCORSMiddleware` (Vary: Origin) |
| 5 | `DegradedModeMiddleware` | — |
| 6 | `CORSMiddleware` (FastAPI) | `CORSMiddleware` (CORS headers) |
| 7 | `CSRFProtectionMiddleware` | — |
| 8 | `SecurityHeadersMiddleware` | `SecurityHeadersMiddleware` (security headers) |
| 9 | `RateLimitMiddleware` | `RateLimitMiddleware` (X-RateLimit-* headers) |
| 10 | `AppEnforcementMiddleware` | — |
| 11 | `GZipMiddleware` (Starlette) | `GZipMiddleware` (compress) |
| 12 | `RequestContextMiddleware` | `RequestContextMiddleware` (X-Request-ID) |
| 13 | `AuditMiddleware` | — |
| 14 | → handler | — |

**Conséquence majeure** : `RequestContextMiddleware` (qui peuple `request.state.tenant_id`, `user_id`, `api_key_id`, `jwt_scopes` et set les ContextVars de logging) est le **12ème** sur 14 dans la chaîne inbound. Tous les middlewares en amont ne peuvent **pas** lire ces valeurs.

### 2.2 `timing.py` (48 LoC)

- `TimingMiddleware` :
  - `__init__(app, slow_threshold_ms=1000)` (ligne 27).
  - Mesure `time.perf_counter()`, set header `X-Response-Time: {ms:.1f}ms` (ligne 37).
  - Log WARNING si > seuil (ligne 39-46).

### 2.3 `cors.py` (92 LoC)

- Constantes : `_NGROK_SUFFIX = ".ngrok-free.dev"`, `_TRYCF_SUFFIX = ".trycloudflare.com"` (lignes 19-20).
- `_is_ngrok_origin(origin)` (ligne 28) : si `DEBUG`, vérifie `parsed.hostname.endswith(_NGROK_SUFFIX)` ou `_TRYCF_SUFFIX`.
- `StrictCORSMiddleware` :
  - `__init__` : freeze `_allowed_origins = frozenset(settings.CORS_ORIGINS)` (ligne 68).
  - `dispatch` :
    - Si `Origin` absent → laissé passer.
    - Si `Origin in self._allowed_origins or _is_ngrok_origin(origin)` → laissé passer + `Vary: Origin`.
    - Sinon → 403 + log WARNING.

### 2.4 `degraded.py` (161 LoC)

- `_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}`.
- `_READ_ONLY_EXEMPT_PREFIXES` : 9 préfixes auth/health/docs.
- `_APP_PREFIX_MAP = {"/api/v1/epicerie/": "degraded:epicerie", "/api/v1/restaurant/": "degraded:restaurant"}`.
- `_MARVELINE_DEGRADED_KEY = "degraded:marveline"` (ligne 52).
- `DegradedModeMiddleware.dispatch` :
  - Lookup app-level via `_get_app_degradation` (lignes 80-83).
  - Si NULL/NOMINAL → lookup global `redis_sec.get_degradation_level()` (lignes 86-100).
  - 4 niveaux : NOMINAL (passe), READ_ONLY (block mutations), AUTH_DOWN (passe + log warning), EMERGENCY_BYPASS (passe + log critical).
- `_get_app_degradation` (ligne 134-161) : prefix match `_APP_PREFIX_MAP`, fallback `_MARVELINE_DEGRADED_KEY`, GET Redis-SEC.
- `_NO_DEGRADE_PREFIXES = ("/health", "/api/docs", "/api/redoc", "/openapi.json", "/.well-known/", "/metrics")`.

### 2.5 `request_context.py` (165 LoC)

- `_extract_jwt_claims(request)` (ligne 32) : `decode_token(token)` (sans audience), swallow Exception.
- `_extract_api_key_info(request)` async (ligne 57) : ouvre `get_async_db_context()`, `ApiKeyService(db).validate_key(value)`, retourne `{tenant_id, api_key_id, scopes}` ou `{}`. Exception → log WARNING + `{}`.
- `RequestContextMiddleware.dispatch` (ligne 100) :
  1. `reset_query_counter()` (slow_query).
  2. Generate ou propagate `X-Request-ID`.
  3. Tente JWT, sinon API key.
  4. Extract `tenant_id`, `user_id`, `api_key_id`, `principal_type`, `jwt_scopes`.
  5. Peuple `request.state.{request_id, tenant_id, user_id, principal_type, api_key_id, jwt_scopes}` (lignes 144-149).
  6. `set_request_context(...)` pour ContextVars logging (ligne 152).
  7. Append `X-Request-ID` à la response.
  8. `clear_request_context()` en finally.

### 2.6 `metrics.py` (181 LoC)

- `MetricsMiddleware._normalize_path(path)` (ligne 55) :
  ```python
  for pattern, replacement in PATH_NORMALIZATION_PATTERNS:
      if pattern.match(path):
          return pattern.sub(replacement, path)
  return path
  ```
  `PATH_NORMALIZATION_PATTERNS` (`constants/metrics.py:8-14`) ne contient **que 5 patterns** : `products/\d+`, `customers/\d+`, `reservations/\d+`, `invoices/\d+`, `audit/\d+`.
- `_get_identifier_type(request, scope)` (ligne 85) : `"user_id"` si scope `USER_AUTHENTICATED`, sinon `"ip"`.
- `dispatch` (ligne 107) :
  - INC `http_requests_in_progress{method,path}`.
  - timer + `call_next`.
  - INC `http_requests_total{method,path,status}`.
  - `observe http_request_duration_seconds{method,path}`.
  - Si `status==429` → `determine_rate_limit_scope(request)` puis INC `rate_limit_hits_total{scope, identifier_type}`.
  - Décrément Gauge en `finally`.

### 2.7 `exception_handler.py` (232 LoC)

- `create_error_response(status_code, error_code, message, details, errors, request_id)` (ligne 34) :
  - Format : `{success: False, error, message, detail: message, details?, errors?, request_id?}`.
  - **Note** : `detail = message` ligne 47 (compat FastAPI) — duplication.
- `app_exception_handler(request, exc: AppException)` (ligne 66) : log INFO si <500, ERROR si ≥500. Retourne `create_error_response`.
- `http_exception_handler(request, exc: StarletteHTTPException)` (ligne 94) :
  - Map `status_code` → `error_code` (dict 9 entrées).
  - Si `exc.detail` est `dict` → expose tel quel dans `detail`.
- `validation_exception_handler` (ligne 135) :
  - DEBUG : expose `field`, `message`, `type`.
  - PROD (`P3-09`) : remplace par `[{"message": "Validation error"}]` (anti-reconnaissance).
  - **Duplication** : `details={"errors": formatted_errors}` ET `errors=formatted_errors` (lignes 161-162).
- `generic_exception_handler` (ligne 167) :
  - Lazy import `sqlalchemy.exc.{OperationalError, InterfaceError, DatabaseError}`.
  - Si `is_infra` → 503 SERVICE_UNAVAILABLE.
  - Sinon → log CRITICAL + stack + 500 INTERNAL_ERROR.
- `register_exception_handlers(app)` (ligne 227) : 4 handlers ajoutés.

### 2.8 `security.py` (405 LoC)

#### `CSRFProtectionMiddleware` (lignes 17-141)
- `SAFE_METHODS = HTTPMethods.SAFE_METHODS`.
- 14 endpoints exempts (lignes 38-56) : Health, Docs, Login, Refresh, Logout, MFA Verify, Change Password, V2_Login, V2_Refresh, V2_Logout, V2_Register_Device, V2_Set_Pin, V2_Pin_Login + startswith `/api/v1/auth/v2/oauth/`.
- E2E bypass via `E2E_BYPASS_ENABLED=true` env + `X-E2E-Bypass` header (lignes 63-69).
- Skip si pas d'`Authorization` header.
- Extract `sid` claim depuis JWT (`_extract_session_id_from_jwt` ligne 101 → `decode_token`).
- Si `sid` absent → laisser passer.
- Vérifie `X-CSRF-Token` header.
- Validate via `redis_client.validate_csrf_token(session_id, token)` (ligne 136 — utilise `compare_digest` côté Redis).

#### `SecurityHeadersMiddleware` (lignes 144-166)
- `X-Content-Type-Options: nosniff`.
- `X-Frame-Options: SAMEORIGIN` si path startswith `/uploads/etl/` (lignes 154-157), sinon `DENY`.
- `X-XSS-Protection`, `Strict-Transport-Security`, `Referrer-Policy`.
- `Content-Security-Policy` **uniquement si `not settings.DEBUG`** (lignes 163-164).

#### `RateLimitMiddleware` (lignes 169-405)
- `EXEMPT_PATHS = {HealthEndpoints.{BASE,READY,LIVE}, PublicEndpoints.{DOCS,REDOC,OPENAPI}, "/metrics"}` (lignes 206-214).
- `_get_rate_limiter()` (ligne 221) : recâble la connexion Redis si elle a changé (test fixture).
- `_get_client_ip(request)` (ligne 232) :
  - Si `settings.TRUSTED_PROXY_HEADERS` → lit `X-Forwarded-For[0]`, normalise via `ipaddress.ip_address(...).compressed` (P2-02).
  - Sinon → `request.client.host`.
- `dispatch` (ligne 263) :
  1. Skip exempt paths.
  2. Whitelist `TRUSTED_PARTNER_IPS` (CIDR check) → exempt.
  3. **Niveau 1 — Global IP** : `RateLimitScope.GLOBAL_IP` (1000/min).
  4. **Niveau 2 — Scope spécifique** via `determine_rate_limit_scope(request)` :
     - LOGIN : identifier `email:{email}` si `request.state.parsed_body.email`, sinon IP (P2-09).
     - API_KEY_AUTHENTICATED : `apikey_{api_key_id}` depuis `request.state` (mais `request.state` n'est pas encore peuplé — voir F111).
     - USER_AUTHENTICATED ou EPICERIE_*/RESTAURANT_* : `t{tenant_id}:u{user_id}` ou `u{user_id}` ou IP fallback.
     - Sinon : IP.
  5. Si bloqué → `_rate_limit_response` (ligne 375) avec headers RFC 6585.
  6. Sinon → ajouter `X-RateLimit-{Limit,Remaining,Reset}`.

### 2.9 `audit.py` (426 LoC)

- `SENSITIVE_READ_PATTERNS` (lignes 56-60) : `customers/\d+`, `invoices/\d+`, `users/\d+`.
- `EXCLUDED_PATHS` (lignes 63-72) : Health, Docs, Login, Refresh, CSRF, Logout.
- `AuditMiddleware.dispatch` (ligne 74) :
  1. Skip si `request.state.request_id` absent (log ERROR — middleware mal configuré).
  2. Skip excluded paths.
  3. Lit `tenant_id, user_id, api_key_id, principal_type` depuis `request.state` (peuplé par `RequestContextMiddleware`).
  4. Skip si non auth (`tenant_id` absent ou ni user ni API key).
  5. Extract `ip_address`, `user_agent`.
  6. `call_next` puis :
     - Si 2xx + mutation (POST/PUT/PATCH/DELETE) → `_audit_mutation`.
     - Si 2xx + GET + path sensible → `_audit_sensitive_read` (avec entity_id) ou `_audit_sensitive_list`.
- `_audit_mutation` (ligne 165) :
  - Map `POST→CREATE, PUT/PATCH→UPDATE, DELETE→DELETE`.
  - `_parse_entity_from_path(path)` → `(entity_type, entity_id)`.
  - **Ouvre une nouvelle session DB** via `get_async_db_context()` (ligne 189).
  - `audit_service.log_action(...)` puis `await db.commit()`.
  - Catch all + log exception (pas de re-raise).
- `_audit_sensitive_read` (ligne 220) : idem, mais skip si `entity_id is None`.
- `_audit_sensitive_list` (ligne 267) : idem, action `READ_SENSITIVE` avec `entity_id=None`.
- `_parse_entity_from_path(path)` (ligne 301) :
  - Split `/api/v1/{entity_type_plural}/{entity_id?}`.
  - Skip si pas `parts[0]=="api"` ni `parts[1]=="v1"`.
  - **Pour `/api/v1/epicerie/produits/123`** : `parts[2]="epicerie"` → `entity_type = "Epicerie"` (au lieu de `EpicerieProduit`).
- `_singularize_entity_type(plural)` (ligne 342) :
  - Mapping hardcodé 11 entrées : customers, reservations, invoices, users, products, categories, bundles, services, sessions, mfa, audit.
  - Fallback règles génériques (`ies → y`, `ses/xes/zes → es`, `s → ""`).
- `SENSITIVE_LIST_PATHS` (lignes 415-421) : 5 paths exact match.

---

## 3. Frictions identifiées

(Numérotation continue — F111 commence après le module 03.)

### 3.1 Frictions P0

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F111** | Ordre middlewares | **`RequestContextMiddleware` exécuté en 12ème position — `request.state` n'est PAS disponible pour les middlewares amonts qui en ont besoin** | `main.py:104-159` (ordre LIFO) ; consommateurs de `request.state` :<br>- `security.py:329` (`api_key_id`)<br>- `security.py:339-342` (`tenant_id`, `user_id` pour scope identifier)<br>- `security.py:324` (`parsed_body.email` pour login scope)<br>- `metrics.py` indirectement via `determine_rate_limit_scope` | **`MetricsMiddleware`, `TimingMiddleware`, `TrustedHostMiddleware`, `StrictCORSMiddleware`, `DegradedModeMiddleware`, `CORSMiddleware`, `CSRFProtectionMiddleware`, `SecurityHeadersMiddleware`, `RateLimitMiddleware`, `AppEnforcementMiddleware`** s'exécutent **avant** que `request.state.tenant_id` et `request.state.api_key_id` ne soient peuplés.<br>Conséquences directes :<br>(a) `RateLimitMiddleware._dispatch` accède à `request.state.api_key_id` ligne 329 → toujours `None` (`getattr(..., None)`) → `identifier = client_ip` au lieu de `apikey_{id}`. Quota par-API-key inopérant.<br>(b) `RateLimitMiddleware` accède à `request.state.parsed_body` ligne 324 → toujours absent → `email_id = None` → fallback IP au lieu de email. Anti-brute-force email-based ne fonctionne pas.<br>(c) `MetricsMiddleware` ne peut pas tenant-labéliser ses métriques (cf F83 module 03) — non seulement le label manque, mais on ne pourrait pas l'ajouter sans refondre la chaîne.<br>(d) `AppEnforcementMiddleware` doit re-décoder le JWT et faire un SELECT DB (ligne 92-95) au lieu de lire `request.state`.<br>(e) `CSRFProtectionMiddleware` doit re-décoder le JWT pour extraire `sid` (ligne 114).<br>**Tout l'investissement de `RequestContextMiddleware` est gaspillé pour les 10 middlewares amont.** À fixer : déplacer `RequestContextMiddleware` au début de la chaîne (le rendre outermost), ou éclater en deux : un mini-extractor en amont (sans DB call), puis un enrichisseur en aval. |
| **F112** | metrics | **Path normalization couvre 5 patterns sur des dizaines** | `constants/metrics.py:8-14` : `products`, `customers`, `reservations`, `invoices`, `audit` ; **manquent** : `devis`, `ventes`, `evenements`, `relances`, `bundles`, `categories`, `formulas`, `deposits`, `payments`, `suppliers`, `supplier_orders`, `pricing`, `delivery_zones`, `loyalty`, `containers`, `damage_types`, `notifications`, `mfa`, `webauthn`, `api_keys`, `features`, `inventory_movements`, `stock_management`, `sessions`, `users` (présent dans audit mais pas dans metrics), `epicerie/*`, `restaurant/*`, sub-resources (`reservations/{id}/confirm`, `devis/{id}/duplicate`, etc.) | **Cardinalité explosable Prometheus**. Chaque endpoint avec ID dynamique non couvert crée 1 métrique par valeur d'ID. Pour Marveline avec ~1000 réservations actives × 30 endpoints non couverts = 30 000 séries Prometheus × `{method, status}` × tenants. Prometheus s'effondre, Grafana plante. Confirme et amplifie F87 module 03. À fixer : utiliser `request.scope["route"].path_format` (FastAPI fournit le template `/api/v1/products/{id}`) au lieu de patterns regex maintenus à la main. |
| **F113** | rate_limit | **Pas de scope `MARVELINE_*` ni `LESPLENDID_*`** | `rate_limiter.py:179-191` ; `rate_limit_utils.py:111-114` (matching `/epicerie/`, `/restaurant/`) | Marveline + Splendid (même app, mêmes routes) → tombent dans `USER_AUTHENTICATED` (200/min). Pour 4+ tenants avec usage haute fréquence (saisie réservation tablette terrain), 200 req/min/tenant peut être limitant. Et si on combine avec F84 (pas de tenant key Redis) + F111 (request.state vide) → un user Marveline et un user Splendid avec même `account_id` partagent **et** la limite générique **et** la clé Redis. Cross-tenant rate limit collision triple confirmée. |

### 3.2 Frictions P1

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F114** | app_enforcement | Une **transaction DB par requête** pour lookup `tenant.app_code` | `app_enforcement.py:92-95` (`async with get_async_db_context() as db: tenant_app_code = await db.scalar(...)`) | À chaque requête authentifiée non-exempt, un nouveau context DB est ouvert juste pour fetcher `tenant.app_code`. Sans cache. À 1000 req/s = 1000 SELECT redondants sur la même table. Devrait être :<br>(a) cacher dans `RequestContextMiddleware` après decode JWT (le claim `tid` peut résoudre `app_code` via cache Redis 60s),<br>(b) embarquer `app_code` dans le claim JWT à l'émission (ajout 1 string au token),<br>(c) consolider avec `RequestContextMiddleware` pour ne faire qu'une seule transaction. |
| **F115** | request_context | Une **transaction DB par requête** pour valider l'API key | `request_context.py:71-82` (`async with get_async_db_context() as db: api_key_service = ApiKeyService(db) ; api_key = await api_key_service.validate_key(...)`) | Si la requête vient avec API key (pas JWT), nouvelle transaction DB. Pas de cache Redis sur API key (vérifier dans module 13 — `app_key` service mentionne "cache Redis + DB fallback" ligne 60 doc, mais le commentaire reste à valider côté code). Si le cache existe : OK. Sinon : ×N requêtes API key. |
| **F116** | global | **JWT décodé jusqu'à 6 fois pour la même requête** | Chaîne d'appels :<br>1. `MetricsMiddleware` → `determine_rate_limit_scope` → `_decode_jwt_claims` (si 429)<br>2. `RateLimitMiddleware` → `determine_rate_limit_scope` → `_decode_jwt_claims`<br>3. `AppEnforcementMiddleware` → `decode_token` (`app_enforcement.py:78`)<br>4. `CSRFProtectionMiddleware` → `decode_token` (`security.py:114`)<br>5. `RequestContextMiddleware` → `decode_token` (`request_context.py:51`)<br>6. `get_current_user` (deps.py) → `decode_access_token` | RSA-2048 verify ≈ 0.1ms × 6 = 0.6ms par requête. À 10k req/s × 6 décodages = 60k RSA verifies/sec → CPU intensif. Solution : décoder une seule fois dans le middleware le plus en amont (`RequestContextMiddleware` rendu outermost, F111), cacher dans `request.state.jwt_claims`. |
| **F117** | audit | **Audit non-atomique avec la mutation métier** | `audit.py:188-218` (`_audit_mutation` ouvre une nouvelle session, `await db.commit()`) | Workflow réel d'une mutation (POST /customers) :<br>1. Handler ouvre session A, INSERT customer, COMMIT.<br>2. Response 201 retourne au middleware.<br>3. `_audit_mutation` ouvre **session B**, INSERT audit_log, COMMIT.<br>Si étape 3 échoue (Redis-SEC down → exception, DB busy → timeout), le `try/except` ligne 217 swallow → **mutation NON auditée silencieusement**. Pour RGPD/conformité, une mutation non auditée = trou. Solution : audit dans la même transaction que la mutation (via Outbox Pattern ou commit conjoint). |
| **F118** | audit | `SENSITIVE_READ_PATTERNS` ne couvre que customers/invoices/users | `audit.py:56-60` | Lectures de :<br>- `/api/v1/devis/\d+` → contient nom/adresse/email client → **non auditée**<br>- `/api/v1/reservations/\d+` → idem (customer_id, customer_name, addresses) → non auditée<br>- `/api/v1/relances/\d+` → email + montant → non auditée<br>- `/api/v1/loyalty/\d+` → comportement client → non auditée<br>- `/api/v1/audit/\d+` → audit logs eux-mêmes → non audité (méta-RGPD)<br>RGPD demande la traçabilité de toute lecture de données personnelles. Couverture ~30%. À étendre, ou inverser la logique (white-list des paths NON sensibles). |
| **F119** | audit | `_singularize_entity_type` ne gère pas les apps préfixées | `audit.py:301-340` (`_parse_entity_from_path`) | Pour `/api/v1/epicerie/produits/123` :<br>- `parts[2] = "epicerie"` → `entity_type = "Epicerie"`<br>- `parts[3] = "produits"` → ignoré (n'est pas digit, ligne 335).<br>- `parts[4] = "123"` → ignoré (out of range).<br>Résultat : `(entity_type="Epicerie", entity_id=None)` au lieu de `(entity_type="EpicerieProduit", entity_id=123)`. **Audit log épicerie/restaurant complètement faussé** : tous les mutations enregistrées sous `entity_type="Epicerie"` ou `"Restaurant"` génériques. Recherche/filtrage RGPD impossible. |
| **F120** | rate_limit | `_get_client_ip` sans `TRUSTED_PROXY_HEADERS` ne normalise pas l'IP | `security.py:248-260` | Si `TRUSTED_PROXY_HEADERS=False`, `request.client.host` peut être `::ffff:1.2.3.4` (IPv6-mapped IPv4). Comparé à `1.2.3.4` plain → 2 clés Redis distinctes pour le même client. **Bypass de rate limit** : un attaquant qui fait alterner les requêtes en IPv4 vs IPv6-mapped peut doubler son quota. La normalisation P2-02 ligne 257 n'est exécutée que si `TRUSTED_PROXY_HEADERS=True`. À normaliser systématiquement. |
| **F121** | degraded | `_MARVELINE_DEGRADED_KEY` partagé entre Marveline et Splendid | `degraded.py:51-52, 155` | Si un ops bascule la clé Redis `degraded:marveline` en `READ_ONLY`, **TOUS les tenants sur l'app `marveline`** (Marveline + Splendid + futurs brands) passent en lecture seule sans signal séparable. Pas de granularité par tenant ou par brand. Confirme F16 (module 01) côté middleware. |
| **F122** | degraded | **4 GET Redis-SEC par requête** pour le mode dégradé | `degraded.py:80-100` :<br>1. `_get_app_degradation` → 1 GET<br>2. `redis_sec.get_degradation_level()` → 3 GET (EMERGENCY_BYPASS, AUTH_DOWN, READ_ONLY) | À chaque requête (sauf exemptions) : 4 round-trips Redis-SEC. À 1000 req/s + Redis 1ms latence = 4ms × 1000 = 4 secondes CPU/sec en attente Redis. Devrait être :<br>(a) batch en 1 MGET avec 4 clés,<br>(b) cacher localement avec TTL court (5-10s) — la dégradation n'a pas besoin d'être lue en temps réel à 1000 req/s. |
| **F123** | request_context | FAIL-OPEN sur API key alors que rate_limiter est FAIL-CLOSED | `request_context.py:83-85` (`except Exception as e: logger.warning(...) ; return {}`) vs `rate_limiter.py:142-153` (`return False, ...` FAIL-CLOSED) | Inconsistance de stratégie : si la DB est down, l'API key validation échoue silencieusement (utilisateur passe en non-auth → 401 plus loin), mais le rate limiter Redis blocque tout. Soit on est FAIL-CLOSED partout (sécurité > disponibilité), soit FAIL-OPEN partout (l'inverse). Mix incohérent. |
| **F124** | csrf | Liste hardcodée de 14 endpoints exempts | `security.py:38-56,60` | Toute évolution des endpoints d'auth/MFA/OAuth exige édition de la liste. Devrait être un décorateur `@csrf_exempt` ou un attribut sur les routers (FastAPI tags). |
| **F125** | metrics | `MetricsMiddleware` ne tient pas compte des chemins exempts | `metrics.py:107-181` (aucun skip) | `/health/ready`, `/metrics`, `/api/docs` sont tous comptés dans `http_requests_total{path=...}`. Pour Prometheus qui scrape `/metrics` toutes les 15s, on a `http_requests_total{path="/metrics"}` qui s'auto-incrémente → métrique récursive polluant les graphes. Idem `/health/live` interrogé par Kubernetes. Devrait skip les endpoints d'observabilité comme `RateLimitMiddleware` le fait (`EXEMPT_PATHS`). |
| **F126** | global | `__init__.py` n'exporte pas `StrictCORSMiddleware`, `DegradedModeMiddleware`, `AppEnforcementMiddleware` | `__init__.py:14-22` (`__all__` de 8 entrées seulement) | Les 3 middlewares manquants sont importés directement depuis leurs sous-modules dans `main.py`. Convention `__all__` pas suivie. |

### 3.3 Frictions P2

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F127** | exception_handler | `create_error_response` pollue le payload : `detail` ET `message` ET `details` ET `errors` | `exception_handler.py:43-58` (champs `success, error, message, detail, details?, errors?, request_id?`) | Frontend doit gérer 4 façons de récupérer le même message. `detail = message` ligne 47 est explicitement pour "compat FastAPI". Schéma standardisé `ErrorResponse` Pydantic à figer. |
| **F128** | exception_handler | `validation_exception_handler` duplique `details.errors` et `errors` | `exception_handler.py:161-162` | Sortie : `{"details": {"errors": [...]}, "errors": [...]}`. À choisir un seul. |
| **F129** | exception_handler | `generic_exception_handler` log CRITICAL + stack pour TOUTE exception non gérée | `exception_handler.py:207-213` | Pour des exceptions normales mal classifiées (ex: `KeyError` dans une lib tier), log CRITICAL = bruit. À filtrer par allow-list ou raise level. |
| **F130** | security | `SecurityHeadersMiddleware` n'ajoute pas CSP en DEBUG | `security.py:163-164` (`if not settings.DEBUG`) | Différence comportementale dev/prod. Bugs CSP (script externe bloqué) découverts en prod. Devrait être `Content-Security-Policy-Report-Only` en dev. |
| **F131** | cors | `_allowed_origins` figé au `__init__`, mais `expand_dev_network` mute `settings.CORS_ORIGINS` | `cors.py:68` ; `config.py:208-241` | Si `expand_dev_network` ajoute des origins après `Settings` instanciation (ngrok détecté tardivement), le `frozenset` est figé sur la valeur initiale. Fonctionne car `_is_ngrok_origin` rattrape via le suffix-check, mais le lien est implicite. |
| **F132** | cors | `StrictCORSMiddleware` + `CORSMiddleware` (FastAPI) coexistent — defense-in-depth ou redondance ? | `main.py:126,151` | LIFO : `StrictCORSMiddleware` (#4) exécute avant `CORSMiddleware` (#6). Strict bloque les origins hors whitelist en 403 ; CORSMiddleware ajoute les headers CORS. Defense-in-depth justifiée mais l'overhead double-check sur chaque requête est non-négligeable. À documenter clairement. |
| **F133** | cors | `_is_ngrok_origin` accepte tous les sous-domaines `.ngrok-free.dev` en DEBUG | `cors.py:28-45` | Si DEBUG = True en environnement non-dev (ex: staging avec DEBUG accidentel), n'importe quel attaquant peut faire un tunnel ngrok et bypass CORS. Devrait aussi check `settings.SENTRY_ENVIRONMENT == "development"` ou un flag explicite. |
| **F134** | rate_limit | `EXEMPT_PATHS` set non immutable | `security.py:206-214` | Set Python mutable. Devrait être `frozenset`. |
| **F135** | audit | `AuditMiddleware` ouvre 1 nouvelle session DB par mutation | `audit.py:189,242,279` (3 `async with get_async_db_context()` distincts) | Cumulé avec F117 (audit non-atomique) : pour 1 POST mutation, on a 2 sessions DB ouvertes/fermées (handler + audit). À 1000 mutations/sec = 2000 sessions/sec → pression sur le pool. Solution : Outbox Pattern (insert dans `audit_outbox` dans la même transaction que la mutation, worker async qui flushe vers `audit_log`). |
| **F136** | audit | `_singularize_entity_type` règles génériques fragiles | `audit.py:379-386` | `categories.endswith("ies") → category` ✓, `services.endswith("es") → service` ✓ (par `.endswith("ses/xes/zes")`)... mais `addresses.endswith("ses") → address` ✓. Et `analyses.endswith("ses") → analy` ✗ (devrait être `analysis`). Le mapping explicite ligne 363-374 couvre les cas connus mais le fallback est faux pour les pluriels irréguliers. Use `inflect` package. |
| **F137** | audit | `EXCLUDED_PATHS` = liste, pas frozenset/set | `audit.py:63-72` (`EXCLUDED_PATHS = [PublicEndpoints...]`) | `if request.url.path in self.EXCLUDED_PATHS` (ligne 102) → recherche linéaire O(n). Fait sur chaque requête. Devrait être `frozenset`. |
| **F138** | request_context | `_extract_jwt_claims` swallow toutes les exceptions silencieusement | `request_context.py:53-54` | Idem F105 module 03 — un attaquant qui forge des tokens passe en silence. À logger en DEBUG ou compter via metrics. |
| **F139** | timing | `slow_threshold_ms = 1000` hardcodé | `timing.py:27` | À déplacer dans `app/constants/limits.py` ou `app/constants/observability.py`. |
| **F140** | timing | Header `X-Response-Time` préfixe X- déprécié RFC 6648 | `timing.py:16` | Naming legacy. RFC 6648 (2012) recommande de ne plus préfixer en `X-`. À renommer `Response-Time` ou conserver pour compat. |
| **F141** | degraded | `_NO_DEGRADE_PREFIXES` est un attribut de classe placé après les méthodes | `degraded.py:131` | Ordering atypique — convention Python est attributs en haut, méthodes après. À déplacer. |

### 3.4 Frictions P3

| ID | Couche | Friction | Citation |
|---|---|---|---|
| **F142** | exception_handler | `error_codes` dict 9 entrées hardcodé | `exception_handler.py:101-111` — à exploser dans `app/constants/http.py`. |
| **F143** | audit | `SENSITIVE_LIST_PATHS` séparé de `SENSITIVE_READ_PATTERNS` | `audit.py:56-60` (regex) vs `:415-421` (set exact) — 2 mécanismes distincts pour la même intention. À unifier. |
| **F144** | metrics | `_get_identifier_type` ne distingue que `user_id` vs `ip` | `metrics.py:85-105` — pour API key, devrait retourner `api_key`. Affecte le label `rate_limit_hits_total{identifier_type}`. |
| **F145** | csrf | E2E bypass via env + header | `security.py:63-69` (`E2E_BYPASS_ENABLED + X-E2E-Bypass`) — risque accidentel en prod si env mal configurée. Restriction RFC : également check `settings.DEBUG`. |
| **F146** | metrics | `dispatch` re-utilise le même `path` normalisé pour Counter et Histogram | `metrics.py:135-165` — déjà cohérent, juste une note de lecture. |
| **F147** | timing | `print` en docstring au lieu de log dans l'exemple | (aucun) — N/A. |

---

## 4. Dépendances inter-modules / fuites

### 4.1 Couplages observés

- `MetricsMiddleware` (outermost) → `core.metrics`, `core.rate_limit_utils`, `app.constants` → bonne séparation.
- `RateLimitMiddleware` → `core.redis.redis_client`, `core.rate_limiter`, `core.rate_limit_utils`, `core.security.decode_token` → couplage fort multi-modules.
- `CSRFProtectionMiddleware` → `core.redis.redis_client`, `core.security.decode_token` → couplage avec auth.
- `AppEnforcementMiddleware` → `models.tenant`, `core.database.get_async_db_context`, `core.security.decode_token` → DB direct depuis middleware (anti-pattern P1).
- `RequestContextMiddleware` → `core.database.get_async_db_context`, `services.api_key.ApiKeyService` → DB direct depuis middleware.
- `AuditMiddleware` → `services.audit.AuditService`, `core.database.get_async_db_context` → 3 sessions ouvertes par mutation.
- `DegradedModeMiddleware` → `core.redis.redis_sec` (lazy import ligne 77) → couplage fort.
- `exception_handler` → `core.exceptions.AppException`, `core.config.settings` (lignes 144-145), lazy import `sqlalchemy.exc` → propre.

### 4.2 Cycles évités

- `RequestContextMiddleware` importe `X_API_KEY_HEADER` depuis `core.deps` (ligne 23) — pas de cycle car `core.deps` ne ré-importe pas le middleware.
- `audit.py` lazy import au top du module → pas de cycle.

### 4.3 Fuites identité Marveline / Splendid

- **F121** : `_MARVELINE_DEGRADED_KEY` partagé Marveline/Splendid.
- **F113** : pas de scope rate-limit `MARVELINE_*` ni `LESPLENDID_*`.
- **F119** : audit ne distingue pas `EpicerieProduit` de `Epicerie` générique.
- `app_enforcement.py:6` (commentaire) : "X-App-Code=marveline" en exemple — couplage explicite.

### 4.4 Forward-references

- F115 (validate_key cache) → confirmer module 13 (api_key).
- F117 (Outbox audit pattern) → impact module 31 (audit-feature-flag).
- F119 (entity_type epicerie/restaurant) → impact modules 28 (epicerie) et 29 (restaurant).

---

## 5. Recommandations de refonte

### 5.1 Priorité 1 — Réordonner la chaîne (P0)

1. **F111** : déplacer `RequestContextMiddleware` au début de la chaîne (outermost). Ordre cible :
   ```python
   # Outermost (premier inbound)
   app.add_middleware(MetricsMiddleware)         # outermost
   app.add_middleware(TimingMiddleware)
   app.add_middleware(TrustedHostMiddleware, ...)
   app.add_middleware(StrictCORSMiddleware)
   app.add_middleware(CORSMiddleware, ...)
   app.add_middleware(RequestContextMiddleware)  # ← ici, AVANT toute logique tenant-aware
   app.add_middleware(DegradedModeMiddleware)
   app.add_middleware(CSRFProtectionMiddleware)
   app.add_middleware(SecurityHeadersMiddleware)
   app.add_middleware(RateLimitMiddleware)        # peut maintenant lire request.state
   app.add_middleware(AppEnforcementMiddleware)   # idem
   app.add_middleware(GZipMiddleware, ...)
   app.add_middleware(AuditMiddleware)            # innermost
   ```
   Conséquence : `MetricsMiddleware` ne peut plus lire `request.state` car il est outermost. Solution : utiliser un `try/finally` autour de `call_next` qui mesure d'abord, puis lit `request.state` après que les middlewares en aval l'aient peuplé.

2. **F112** : remplacer `_normalize_path` par lecture du template route :
   ```python
   def _normalize_path(self, request: Request) -> str:
       route = request.scope.get("route")
       if route and hasattr(route, "path_format"):
           return route.path_format
       return self._normalize_path_fallback(request.url.path)
   ```
   Test : 1000 GET `/api/v1/products/{1..1000}` → 1 série Prometheus.

3. **F113** : ajouter scopes `MARVELINE_*` (et `LESPLENDID_*` ou agréger via brand_code) dans `RateLimitScope` enum + `get_scope_config`. `determine_rate_limit_scope` lit `request.state.app_code` (peuplé par `AppEnforcementMiddleware` qui devient en aval de RequestContext) au lieu de matcher l'URL.

### 5.2 Priorité 2 — JWT décoding (P1)

4. **F116** : un seul décodage dans `RequestContextMiddleware` :
   ```python
   class RequestContextMiddleware:
       async def dispatch(self, request, call_next):
           # decode JWT once
           claims = self._extract_jwt_claims(request)
           request.state.jwt_claims = claims
           request.state.tenant_id = ...
           # ...
   ```
   `CSRFProtectionMiddleware`, `AppEnforcementMiddleware`, `RateLimitMiddleware`, `get_current_user` lisent `request.state.jwt_claims` au lieu de re-décoder.

5. **F114** : embarquer `app_code` dans le claim JWT à l'émission. `AppEnforcementMiddleware` lit `claims["app_code"]` au lieu de SELECT DB. Sinon, cache Redis 60s avec invalidation à la mutation tenant.

6. **F115** : confirmer que `ApiKeyService.validate_key` cache en Redis (module 13). Sinon implémenter cache fingerprint + TTL.

### 5.3 Priorité 3 — Audit RGPD complet et atomique (P1)

7. **F117** : implémenter l'**Outbox Pattern** :
   - Table `audit_outbox` (mêmes colonnes que `audit_log` + `processed_at`).
   - Service métier insère dans `audit_outbox` dans la même transaction que sa mutation.
   - Worker Celery lit `audit_outbox WHERE processed_at IS NULL`, réplique vers `audit_log`, marque processed.
   - `AuditMiddleware` devient un déclencheur opt-in (mutation HTTP) qui inscrit dans l'outbox sans 2ème commit.

8. **F118** : étendre `SENSITIVE_READ_PATTERNS` :
   ```python
   SENSITIVE_READ_PATTERNS = [
       r"^/api/v1/customers/\d+$",
       r"^/api/v1/invoices/\d+$",
       r"^/api/v1/users/\d+$",
       r"^/api/v1/devis/\d+$",          # nom + adresse client
       r"^/api/v1/reservations/\d+$",   # idem + montants + dates événement
       r"^/api/v1/relances/\d+$",       # email + montant dû
       r"^/api/v1/loyalty/\d+$",        # comportement client
       r"^/api/v1/audit/\d+$",          # méta-RGPD
   ]
   ```

9. **F119** : refondre `_parse_entity_from_path` pour gérer les apps préfixées :
   ```python
   ENTITY_TYPE_BY_ROUTE = {
       ("epicerie", "produits"): "EpicerieProduit",
       ("epicerie", "ventes"): "EpicerieVente",
       ("restaurant", "commandes"): "RestaurantCommande",
       # ...
   }
   ```
   Idéalement : ajouter un attribut `entity_type` sur la route FastAPI elle-même (via Tags ou metadata).

### 5.4 Priorité 4 — Sécurité (P1-P2)

10. **F120** : normaliser systématiquement l'IP via `ipaddress.ip_address(...).compressed`, peu importe `TRUSTED_PROXY_HEADERS`.

11. **F121** : remplacer `_MARVELINE_DEGRADED_KEY` par `f"degraded:tenant:{tenant_id}"` (lu depuis `request.state.tenant_id`). Ou par brand : `f"degraded:brand:{brand_code}"`. Granularité tenant ou brand au choix, mais par-app=marveline est trop large.

12. **F122** : batcher en MGET les 4 GET du `DegradedModeMiddleware`, ou cacher localement avec TTL 5s.

13. **F123** : décider de la stratégie de cohérence — recommandation : FAIL-CLOSED partout (sécurité > disponibilité), avec circuit breaker pour basculer manuellement en EMERGENCY_BYPASS si nécessaire.

14. **F130** : CSP en mode `Content-Security-Policy-Report-Only` en dev, `Content-Security-Policy` en prod.

### 5.5 Priorité 5 — Hygiène (P2-P3)

15. **F124** : décorateur `@csrf_exempt` sur les endpoints d'auth au lieu de la liste hardcodée.

16. **F125** : `MetricsMiddleware.EXEMPT_PATHS` pour `/health/*`, `/metrics`, `/api/docs`, `/api/redoc`, `/openapi.json`.

17. **F126** : ajouter les 3 middlewares manquants dans `__init__.py:__all__`.

18. **F127, F128** : figer un schema Pydantic `ErrorResponse` partagé. Supprimer la duplication `detail = message`.

19. **F133** : `_is_ngrok_origin` doit aussi check `settings.SENTRY_ENVIRONMENT == "development"`.

20. **F135, F137** : `EXCLUDED_PATHS` → `frozenset`.

21. **F139** : extraire `slow_threshold_ms` dans `app/constants/limits.py`.

### 5.6 Tests à écrire avant refonte

- **F111** : test que `request.state.tenant_id` est lisible depuis `RateLimitMiddleware`. Devrait actuellement échouer.
- **F112** : test cardinalité métriques — 1000 GET `/api/v1/devis/{1..1000}` doit créer 1 série Prometheus, pas 1000.
- **F116** : compteur de décodages JWT par requête doit être ≤ 1 (instrumenter via mock).
- **F117** : si `audit_service.log_action` lève, la mutation doit être rollback (devrait actuellement passer en silence).
- **F119** : POST `/api/v1/epicerie/produits` doit créer un audit_log avec `entity_type="EpicerieProduit"`, pas `"Epicerie"`.
- **F120** : GET avec IP `::ffff:1.2.3.4` et IP `1.2.3.4` doivent partager la même clé Redis rate-limit.
- **F121** : flag `degraded:tenant:5` (Splendid) ne doit PAS bloquer les requêtes du tenant 1 (Marveline).

---

## 6. Verdict module 04

| Aspect | État |
|---|---|
| Convention 4 couches | N/A (infrastructure transverse) |
| Ordre des middlewares | **Cassé** : `RequestContextMiddleware` exécuté en 12ème position alors que 5 middlewares amonts ont besoin de `request.state` (F111) |
| Cardinalité Prometheus | **Risque explosion** : 5 patterns hardcodés sur 30+ endpoints ID-spécifiques (F112) |
| Multi-tenant rate limit | **Inopérant** : `request.state.api_key_id` toujours None à l'exécution de RateLimit (F111), pas de scope `MARVELINE`/`LESPLENDID` (F113) |
| RGPD audit | **Couverture ~30%** : devis/ventes/relances/loyalty non auditées (F118), entity_type faussé pour épicerie/restaurant (F119), audit non-atomique (F117) |
| Performance | **6 décodages JWT par requête** (F116), **2-3 transactions DB par mutation** (F114, F115, F117), **4 GET Redis par requête** pour mode dégradé (F122) |
| Multi-brand | F113, F119, F121 — tout le brand-aware est cassé au niveau middleware |
| Couplage | DB direct depuis 4 middlewares (`RequestContext`, `AppEnforcement`, `Audit`, indirectement `Degraded` via `services.audit`) |
| Dette | 37 nouvelles frictions : 3 P0, 16 P1, 15 P2, 6 P3 |

**Conclusion** : la chaîne de middlewares est techniquement complète (auth, RBAC en aval, CSRF, CORS double-niveau, rate limit, audit, dégradé) mais **mal ordonnée et redondante**. `RequestContextMiddleware` qui devrait être en amont est en 12ème position, forçant 5+ middlewares à re-faire le travail (décodage JWT, lookup DB). Combiné avec F111+F112+F113, **toute la couche multi-tenant est cassée à ce niveau** :
- Métriques sans tenant label (F83 module 03 confirmé ici).
- Rate limit sans tenant key (F84 module 03 confirmé ici).
- Audit avec entity_type tronqué pour épicerie/restaurant (F119).
- Dégradation par app `marveline` qui inclut Splendid (F121).

Les 3 P0 (F111 ordre, F112 cardinalité, F113 scopes brand) sont des prérequis avant tout déploiement multi-tenant en production sérieuse.

→ Module suivant : `05-models-base-mixins.md` (`app/models/base.py` + mixins `TimestampMixin`, `TenantMixin`, `SoftDeleteMixin`).
