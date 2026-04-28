# Module 01 — Core foundations

## 1. Périmètre

| Fichier | LoC | Rôle |
|---|---|---|
| `app/core/config.py` | 333 | Pydantic Settings — config app (DB, JWT, Redis, OAuth, SMTP, KMS, Apple/Google Wallet, Boxtal, …) |
| `app/core/database.py` | 144 | Engine sync + async, sessions, RLS context tenant via ContextVar |
| `app/core/deps.py` | **1066** | Dependencies FastAPI — auth, RBAC v2 (Permission), RBAC v3 (Scope), IAM v2 (Account/Membership), 60+ type aliases |
| `app/core/exceptions.py` | 175 | Hiérarchie `AppException` → 401/403/404/409/422/429 |
| `app/core/redis.py` | **831** | `RedisSecClient` (FAIL-CLOSED) + `RedisCacheClient` (FAIL-OPEN), Lua scripts, ~50 méthodes |
| `app/core/cache.py` | 344 | `CacheService` (async wrapper) + décorateurs |
| `app/core/slow_query.py` | 59 | Listener SQLAlchemy slow query + N+1 detection |
| `app/core/__init__.py` | 120 | Re-export massif (60+ symboles dans `__all__`) |

**Total** : 3 072 LoC.

**Dépend de** : `app/constants/` (RedisKeys, Limits, ErrorMessages, etc.), `app/services/{token,rbac,api_key,mfa}`, `app/models/{account,api_key}`, `app/repositories/{account,tenant_membership,api_key}`, `app/core/{security,permissions,kms}` (modules 02/03).

**Dépendu par** : tous les autres modules (chargé au boot).

---

## 2. Lecture par fichier

### 2.1 `config.py` (333 LoC)

#### Structure
- `Settings(BaseSettings)` — ~100 champs, sources `.env` + valeurs default.
- `model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")` (ligne 36-41).
- 2 validateurs `@model_validator(mode='after')` :
  - `expand_dev_network` (ligne 208-241) : si `DEBUG`, ajoute origins/hosts pour `localhost:{3000,3002,5173,80}` puis tente d'auto-détecter une URL ngrok via HTTP synchrone (timeout 0.3s) ligne 243-267.
  - `validate_production_secrets` (ligne 269-324) : check 5 secrets obligatoires + 4 optionnels — non vides, ≥32 chars, pas de préfixe `dev_`. Lève `ValueError` agrégeant toutes les violations.
- `@property COOKIE_SECURE` (ligne 199-206) : `not self.DEBUG`.
- `settings = get_settings()` exposé module-level (ligne 333), `lru_cache` sur `get_settings`.

#### Champs notables
- `APP_NAME = "CaroCorp"` (ligne 44) — incohérent avec le reste qui parle de Marveline.
- `JWT_ISSUER = "marveline.com"`, `JWT_AUDIENCE = "marveline-api"` (lignes 65-66).
- `JWT_AUDIENCES: dict[str, str] = {"marveline": "marveline-api", "epicerie": "epicerie-api", "restaurant": "restaurant-api"}` (lignes 69-73) — dict statique 3 entrées en dur.
- `MFA_ISSUER_NAME = "Marveline"` (ligne 114) — label TOTP.
- `SMTP_FROM = "noreply@marveline.com"` (ligne 175).
- `CORS_ORIGINS = ["http://localhost:3000", "http://localhost:3002"]` (ligne 94) — port 3002 = legacy Marveline.
- `FRONTEND_URL = "http://localhost:3000"` (ligne 170) — un seul, alors qu'on déploie 4 apps.
- 6 secrets obligatoires : `PASSWORD_PEPPER`, `ENCRYPTION_KEY`, `TOTP_DEV_MASTER_KEY`, `AUDIT_HMAC_KEY`, `WG_INTERNAL_API_KEY` + `DATABASE_URL`.
- 4 secrets optionnels surveillés (interdiction préfixe `dev_`) : `HCAPTCHA_SECRET_KEY`, `OAUTH_GOOGLE_CLIENT_SECRET`, `OAUTH_GITHUB_CLIENT_SECRET`, `OAUTH_FACEBOOK_CLIENT_SECRET`.
- Champs Apple Wallet : `APPLE_PASS_TYPE_ID`, `APPLE_TEAM_ID`, `APPLE_PASS_CERT_PATH`, `APPLE_PASS_KEY_PATH`, `APPLE_WWDR_CERT_PATH`, `APNS_KEY_PATH`, `APNS_KEY_ID`, `APNS_USE_SANDBOX` (lignes 145-152).
- Champs Google Wallet : `GOOGLE_WALLET_ISSUER_ID`, `GOOGLE_WALLET_SERVICE_ACCOUNT_JSON`, `GOOGLE_WALLET_CLASS_SUFFIX` (lignes 155-157).
- Champs Boxtal : `BOXTAL_LOGIN`, `BOXTAL_PASSWORD`, `BOXTAL_ENV`, `BOXTAL_WEBHOOK_SECRET` (lignes 164-167).

### 2.2 `database.py` (144 LoC)

#### Structure
- ContextVar `_current_tenant_id` (ligne 17-19) avec setter/clearer (lignes 22-29).
- Engine **sync** `engine` (ligne 43) avec `pool_size`, `max_overflow`, `pool_pre_ping=True`, `pool_recycle=3600`, `echo=settings.DEBUG`. Bootstrap `install_slow_query_listener(engine)` ligne 47.
- `SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)` ligne 50.
- Engine **async** `async_engine` (ligne 58) avec mêmes paramètres. Bootstrap `install_slow_query_listener(async_engine.sync_engine)` ligne 68.
- Event listener `_inject_rls_tenant` sur `before_cursor_execute` (lignes 72-82) :
  ```python
  cursor.execute(f"SET LOCAL app.current_tenant_id = '{tid}'")
  ```
- `AsyncSessionLocal = async_sessionmaker(...)` ligne 84.
- 4 dépendances : `get_db()` (sync FastAPI), `get_db_context()` (sync Celery), `get_async_db_context()` (async hors FastAPI), `get_async_db()` (async FastAPI).

### 2.3 `deps.py` (1066 LoC)

#### Structure (8 sections distinctes)

**Section A — Principal Protocol + Auth Models** (lignes 31-200)
- `Principal` Protocol (`@runtime_checkable`) avec 4 propriétés : `tenant_id`, `principal_type`, `principal_id`, `permissions`.
- `ApiKeyClient` dataclass (lignes 54-84).
- `UserCompat` agrégat Account+Membership (lignes 87-200) — 110 LoC pour exposer 13 propriétés `id, tenant_id, role, membership_status, email, first_name, last_name, full_name, is_active, password_change_required, hashed_password, created_at, updated_at, principal_type, principal_id, permissions`.

**Section B — get_current_user** (lignes 203-352)
13 vérifications successives :
1. Token absent → 401 (ligne 226-227)
2. Decode JWT (lignes 229-238) : `TokenExpired` → `TOKEN_EXPIRED`, `TokenInvalid` → 401
3. Type check `payload.get("type") != ACCESS` → 401 INVALID_TOKEN_TYPE (ligne 240-245)
4. Client binding hash (M-02) : compute `cbh` depuis IP `/24` + UA, compare avec claim `cbh` (lignes 247-265)
5. Cast `sub`/`tid` en int (lignes 267-276)
6. JTI blacklist (`is_access_blacklisted`) (ligne 279)
7. Device revoked (`_handle_revoked_device` qui INCR un compteur d'attempts dans Redis-SEC) (ligne 287)
8. Account lookup `AsyncAccountRepository.get_active_by_id` (ligne 293)
9. Membership lookup par `mid` ou `(account_id, tenant_id)` (lignes 297-309)
10. Membership status check (`revoked_at`, `status != active`) (ligne 311-315)
11. Account `is_active` (ligne 317-321)
12. `password_change_required` + URL allowlist `PASSWORD_CHANGE_ALLOWED` (lignes 323-327)
13. `X-Tenant-ID` header cross-membership check (lignes 331-344) → si différent du JWT, vérifie un membership actif sur le tenant header.

Side-effect : `set_tenant_context(user.tenant_id)` (ligne 350).

**Section C — get_current_principal (dual-mode JWT/API key)** (lignes 356-379)
- Si Bearer présent → `get_current_user`.
- Sinon header `X-API-Key` présent → `_resolve_api_key_async`.
- Sinon → 401.

**Section D — _resolve_api_key (sync + async)** (lignes 382-424 + 531-582)
La version async :
- Hash SHA-256 du `full_key` (ligne 539).
- `select(ApiKey).where(key_hash == hash, is_active.is_(True))` (lignes 541-546).
- Vérification `expires_at` (lignes 557-568).
- Update `last_used_at`, `last_used_ip`, `usage_count` + `await db.flush()` (lignes 571-575).
- Retour `ApiKeyClient(_tenant_id, _api_key_id, name, set(scopes))`.

⚠️ **Aucun `set_tenant_context()` n'est appelé** — confirmé.

**Section E — RBAC v2 (Permission)** (lignes 427-462 + 589-611)
- `require_permission(*permissions: Permission)` dependency factory.
- Si `ApiKeyClient` → match par valeurs string (`p.value`).
- Si user → match contre `get_effective_permissions_cached(principal.role)`.
- Lève 403 avec liste des permissions manquantes.

**Section F — Type aliases v2** (lignes 466-493)
14 aliases : `CurrentUser, CurrentPrincipal, ProductWriter, ProductDeleter, CategoryWriter, BundleWriter, ReservationWriter, InvoiceWriter, CustomerWriter, InventoryWriter, UserReader, UserWriter, UserAdmin, SessionAdmin, AuditReader, ApiKeyAdmin, FeatureAdmin, VpnReader, VpnWriter, VpnAdmin`.

**Section G — RBAC v3 (Scope)** (lignes 614-722)
- `_get_principal_scopes` (lignes 619-640) : ApiKey → `principal.scopes` ; User → JWT claim `scopes` (depuis `request.state.jwt_scopes`) ou fallback statique `ROLE_SCOPES_FALLBACK` avec un warning P1-04.
- `require_scope(*scopes)` (lignes 643-693) : valide que chaque arg est un `Scope` enum (P1-05 type guard), construit `required = {s.value}`, lève 403 avec `{error, required, missing}` si manque.
- `require_scope_async(*scopes: str)` (lignes 696-722) : variante async, mais accepte `str` au lieu de `Scope` enum (régression du type guard P1-05).
- `require_scope_user(*scopes: str)` (lignes 725-755) : variante User-only, fait `await get_role_scopes(user.role, None)` au lieu d'utiliser le cache.
- `require_stepup` (lignes 758-788) : check MFA step-up via `mfa_service.is_stepup_valid(user.id, device_id)`.

**Section H — Type aliases v3 + IAM v2** (lignes 793-1066)
- ~50 aliases pour Reservations, Stock, Users, Sessions, Devices, Audit, Billing, Config, Reports, Products, Categories, Bundles, Customers, Invoices, Devis, Ventes, Evenements, Relances, Pricing, Suppliers, VPN, Settings, ApiKeys, Features.
- `get_current_account` (lignes 911-982) : 9 vérifications (token, decode, type, sub cast, JTI blacklist, device revoked, account fetch).
- `get_current_membership` (lignes 985-1060) : décode JWT, lookup membership par `mid` (avec fallback `(account_id, tenant_id)`), check `revoked_at` et `status`.
- `CurrentAccount` et `CurrentMembership` typés `Annotated[object, ...]` (lignes 1064-1065).

### 2.4 `exceptions.py` (175 LoC)

- `AppException(Exception)` racine (lignes 19-48) : attributs class `status_code, error_code, message`, instance `details`. `to_dict()` retourne `{error, message, details?}`.
- 6 sections par status HTTP :
  - **401** : `InvalidCredentials`, `TokenExpired`, `TokenInvalid`, `TokenRevoked`, `TokenReplayDetected` (lignes 53-80).
  - **403** : `AccountLocked` (avec `until`/`minutes` détails), `AccountInactive`, `PermissionDenied`, `TenantMismatch` (lignes 85-118).
  - **404/409** : `NotFound` (avec resource), `AlreadyExists`, `EmailAlreadyExists` (lignes 123-141).
  - **400/422** : `BadRequest`, `BusinessValidationError`, `PasswordTooWeak` (lignes 146-161).
  - **429** : `RateLimitExceeded` (avec `retry_after`) (lignes 166-175).

Tous les messages en anglais. Pas de traduction côté backend.

### 2.5 `redis.py` (831 LoC)

#### `RedisSecClient` (lignes 33-715, ~683 LoC)

11 domaines fonctionnels mêlés :

| Domaine | Lignes | Méthodes | FAIL strategy |
|---|---|---|---|
| Lua loader | 64-87 | `load_lua_scripts`, `evalsha` | warning silencieux + RuntimeError au runtime |
| CSRF tokens | 89-139 | `store_csrf_token`, `validate_csrf_token`, `revoke_csrf_token`, `revoke_all_csrf_tokens` | FAIL-CLOSED implicite (return False) |
| Refresh whitelist | 141-183 | `store_refresh_jti`, `get_refresh_jti`, `revoke_refresh_jti` | idem |
| Access blacklist | 185-200 | `blacklist_access_jti`, `is_access_blacklisted` | idem |
| JTI meta | 202-221 | `store_jti_meta`, `get_jti_meta` | idem |
| Token family | 223-269 | `store_token_family`, `add_jti_to_family`, `is_jti_in_family`, `family_exists`, `revoke_token_family` | idem |
| User sessions index | 271-382 | `add_session_to_index`, `remove_session_from_index`, `list_user_session_ids`, `revoke_all_user_sessions`, `revoke_single_session`, `revoke_sessions_except_device`, `logout_device` (+ `_logout_device_fallback`), `logout_other_sessions` | idem |
| Devices revoked | 384-417 | `mark_device_revoked`, `is_device_revoked`, `incr_revoked_device_attempt` | **FAIL-CLOSED explicite** : `is_device_revoked` retourne `True` si Redis down (ligne 405) |
| Sessions HASH | 419-480 | `store_session`, `get_session`, `delete_session`, `update_session_activity` | FAIL-CLOSED implicite |
| Brute force | 482-537 | `increment_brute_force`, `get_brute_force_count`, `reset_brute_force`, `set_brute_force_lock`, `is_brute_force_locked`, `get_brute_force_lock_ttl`, `set_brute_force_alert_sent` | **FAIL-CLOSED explicite** : `is_brute_force_locked` retourne `True` si Redis down (ligne 522) |
| Credential stuffing | 539-578 | `increment_credential_stuffing`, `is_captcha_required`, `set_captcha_required`, `is_login_blocked`, `set_login_blocked` | **FAIL-CLOSED explicite** : `is_captcha_required`, `is_login_blocked` retournent `True` si Redis down (lignes 557, 571) |
| Password reset rate | 580-603 | `increment_password_reset_rate`, `get_password_reset_rate` | FAIL-CLOSED |
| WS ticket | 605-632 | `store_ws_ticket`, `consume_ws_ticket` (constante `WS_TICKET_TTL_SECONDS = 30` en attribut classe ligne 607) | FAIL-CLOSED |
| Mode dégradé | 634-669 | `set_degraded_flag`, `clear_degraded_flag`, `is_degraded`, `get_degradation_level` | mix : `is_degraded` FAIL-OPEN ligne 656, `get_degradation_level` retourne `"AUTH_DOWN"` si Redis down ligne 669 |
| OAuth state | 671-698 | `store_oauth_state`, `consume_oauth_state` | **FAIL-CLOSED par exception** (`raise`) lignes 680, 698 |
| Health | 700-715 | `health_check` | retourne `{status: unhealthy}` |

Particularités :
- Singleton `redis_sec = RedisSecClient()` ligne 827.
- Connexion lazy via `@property client` (ligne 45).
- `decode_responses=True` mais code défensif `member.decode() if isinstance(member, bytes)` à plusieurs endroits (lignes 134, 327, 358).
- Convention de clés : la plupart utilisent un callable `RedisKeys.xxx(...)` mais `set_brute_force_lock`, `set_brute_force_alert_sent`, `increment_password_reset_rate` font `f"{RedisKeys.BRUTE_FORCE_LOCK}{identifier}"` — concaténation manuelle d'un préfixe constant (lignes 511, 534, 588).

#### `RedisCacheClient` (lignes 718-822, ~104 LoC)

3 domaines :

| Domaine | Lignes | Méthodes |
|---|---|---|
| Generic cache | 749-765 | `cache_get`, `cache_set`, `cache_delete` |
| RBAC scope cache | 767-789 | `get_cached_scopes`, `set_cached_scopes`, `invalidate_cached_scopes` |
| Compteurs métier | 791-805 | `incr_reservation_counter(year)`, `incr_invoice_counter(year)` |

Particularités :
- Pas de Lua loader (asymétrie avec `RedisSecClient`).
- FAIL-OPEN partout (return None / False / 0).
- Singleton `redis_cache = RedisCacheClient()` ligne 828.
- Compat `redis_client = redis_sec` ligne 831.

### 2.6 `cache.py` (344 LoC)

Structure :
- `_DateEncoder` JSON encoder pour `datetime`, `date`, `Decimal` (lignes 45-55).
- `CacheService` (lignes 63-293) avec méthodes async :
  - `get(key)` : `cache_get` + JSON parse + métriques (ligne 85).
  - `set(key, value, ttl=300)` : sérialise dict/list en JSON (avec `_DateEncoder`) ou `str()` (ligne 132).
  - `delete(key)` : ligne 180.
  - `invalidate_pattern(pattern)` : SCAN itératif `count=100`, supprime par batch (ligne 216).
  - `flush_all()` : `flushdb()` avec warning "JAMAIS en production" (ligne 272).
- Comment ligne 296 : "P1-03 : decorateur @cached() supprime (code mort — jamais appele dans le codebase)".
- Décorateur `cache_invalidate(patterns: List[str])` (lignes 299-340) :
  ```python
  def decorator(func: Callable) -> Callable:
      @wraps(func)
      def wrapper(*args, **kwargs):
          result = func(*args, **kwargs)
          cache = CacheService()
          for pattern in patterns:
              cache.invalidate_pattern(pattern)   # ⚠️ async appelé sans await
          return result
  ```
- Singleton `cache_service = CacheService()` ligne 344.

### 2.7 `slow_query.py` (59 LoC)

- 2 ContextVar `_query_count`, `_query_start` (lignes 18-19).
- 2 constantes module-level : `SLOW_QUERY_THRESHOLD_MS = 100`, `MAX_QUERIES_PER_REQUEST = 20` (lignes 14-15).
- `install_slow_query_listener(engine)` installe `before_cursor_execute` + `after_cursor_execute` :
  - Mesure elapsed_ms, log WARNING si > 100ms (ligne 47).
  - INCR compteur, log WARNING N+1 quand le seuil 20 est ATTEINT (ligne 55 : `count == MAX_QUERIES_PER_REQUEST` strict equality, donc le warning sort une seule fois à la 20e query).
- `reset_query_counter()` exposé pour les middlewares (ligne 22).

### 2.8 `__init__.py` (120 LoC)

Re-exporte 60+ symboles depuis 7 sous-modules, eager-loaded :
- `rate_limiter` → `RateLimiter`
- `metrics` → `metrics_endpoint`
- `rate_limit_utils` → `determine_rate_limit_scope`, `get_user_id_from_jwt`
- `exceptions` → 16 classes
- `logging` → 9 fonctions/vars
- `validators` → 5 helpers
- `password_policy` → `validate_password`
- `crypto` → 2 fonctions TOTP
- `permissions` → 8 symboles RBAC

`__all__` liste 60 entrées.

---

## 3. Frictions identifiées

### 3.1 Frictions P0 (bloquantes — à fixer en priorité)

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F01** | database (RLS) | f-string SQL pour injecter `current_tenant_id` | `database.py:82` — `cursor.execute(f"SET LOCAL app.current_tenant_id = '{tid}'")` | En pratique `tid` est cast `int(tid)` dans `deps.py:274,1027`, donc l'injection est neutralisée par le typage. Mais le pattern `f"SET ..."` propage un anti-pattern dans le code-foundation. Tout futur callsite (Celery, batch script, ETL) qui oublie le cast → SQL injection sur **le contexte RLS**. Le risque n'est pas l'exfiltration mais la **désactivation des policies tenant** sur tout le batch. |
| **F02** | deps + database | RLS non activé pour `ApiKeyClient` | `deps.py:531-582` (`_resolve_api_key_async`) ne contient **aucun appel à `set_tenant_context()`** ; comparer avec `deps.py:349-350` pour les users | Une requête authentifiée par API key exécute des SELECT sans `current_setting('app.current_tenant_id')` côté Postgres. Toutes les RLS policies basées sur ce setting **ne s'appliquent pas**. La sécurité tenant ne tient plus que par les filtres Python explicites dans les repositories. Un repository qui oublie un filtre = leak cross-tenant garanti pour les API keys. |
| **F03** | deps | Fichier 1066 LoC, 8 sections fonctionnelles distinctes | `deps.py` entier | Cohésion proche de zéro. Auth, RBAC v2, RBAC v3, IAM v2, type aliases, helpers privés, dual-mode resolver — chaque section devrait être un module. Refactor par découpage (auth/principal.py, auth/dependencies.py, auth/authz.py, auth/types.py) bloqué par la taille. Un test unitaire de `require_scope` charge ~3 000 LoC de dépendances. |
| **F04** | redis | `RedisSecClient` 683 LoC, 11 domaines fonctionnels | `redis.py:33-715` | Cohésion ~10%. CSRF, tokens, sessions, brute force, credential stuffing, password reset, WS, dégradé, OAuth — un changement sur un domaine impacte la lisibilité de tous les autres. Tests unitaires impossibles sans mock du client entier. Devrait être 7-9 stores spécialisés. |
| **F05** | cache + repos | Décorateur `cache_invalidate` cassé : appelle un async sans await | `cache.py:328-339` — `wrapper` est sync, appelle `cache.invalidate_pattern(pattern)` qui est `async def` (ligne 216). La coroutine est créée puis perdue sans await | Le décorateur ne fait littéralement rien (la coroutine garbage-collectée donne un `RuntimeWarning: coroutine was never awaited`). Pas exploité dans le repo (`grep` confirme : 0 usages réels), donc impact prod = 0 aujourd'hui. **Mais** : le même pattern est répété dans `repositories/base.py:216,262,400,437,470,694,708` qui consomme `cache_service.get/set/delete` — fonctions toutes `async def` — depuis des méthodes **synchrones** `BaseRepository.get_by_id, list, count, create, update, soft_delete, hard_delete`. Si ces méthodes sont effectivement appelées (à confirmer module 06), la couche cache **est non-fonctionnelle** et le code "Cache HIT" branche sur des coroutines au lieu de dicts (NB: `if cached_data is not None` est toujours `True` car une coroutine n'est pas None). Probabilité haute d'exception masquée par try/except global ou de fallback DB systématique. |

### 3.2 Frictions P1 (dette structurelle)

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F06** | config | Brand strings hardcodés dans la config globale | `config.py:65-66,114,175` (`JWT_ISSUER="marveline.com"`, `JWT_AUDIENCE="marveline-api"`, `MFA_ISSUER_NAME="Marveline"`, `SMTP_FROM="noreply@marveline.com"`) | Splendid (brand_code=lesplendid) hérite de l'identité Marveline pour : émission JWT, label TOTP authenticator, email expéditeur. Toute identité par-tenant nécessite override `.env` global qui change la valeur **pour tous les tenants à la fois**. Pas de mécanisme par-tenant. |
| **F07** | config | `JWT_AUDIENCES` dict statique 3 entrées | `config.py:69-73` | Toute nouvelle app/brand exigeant son propre namespace JWT requiert édition du code Python. Devrait être dérivé de `tenant.app_code` ou `tenant.brand_code` à l'émission. |
| **F08** | config | `expand_dev_network` fait un appel HTTP synchrone à ngrok au boot | `config.py:243-267` (appelé depuis le validator ligne 231) | Le validator s'exécute à l'instanciation de `Settings`, donc à l'`import` de `config.py`. Si ngrok est down et que le timeout 0.3s ne suffit pas (DNS, latence VPN), tout démarrage de process est ralenti. Devrait être un side-effect optionnel post-startup (lifespan FastAPI). |
| **F09** | config | Mélange des préoccupations dans une seule classe | `config.py:33-329` (~100 champs) | Sécurité (JWT keys, ENCRYPTION_KEY, AUDIT_HMAC_KEY) + infra (DB pool, Redis URLs) + business (LOYALTY_BARCODE_SECRET) + tiers (BOXTAL, APPLE, GOOGLE, OAUTH × 3) cohabitent. Modifier un secret WireGuard force la relecture de la config Apple Wallet. À éclater en `SecuritySettings`, `DatabaseSettings`, `RedisSettings`, `IntegrationSettings`. |
| **F10** | deps | 4 systèmes RBAC parallèles | `deps.py:427-462` (Permission v2 sync), `:589-611` (v2 async), `:643-693` (Scope v3), `:725-755` (Scope v3 user-only) | Tout endpoint a 4 façons d'être protégé. Audit de couverture impossible. Le système "canonique" n'existe pas formellement. Voir module 11 pour décision système unique. |
| **F11** | deps | `UserCompat` wrapper de 110 LoC pour préserver une API legacy | `deps.py:87-200` | "drop-in replacement pour User (IAM v2, Lot 8A)" — la migration est inachevée, "Lot 8C" mentionné ligne 91. Tout endpoint qui consomme `UserCompat` reste dans le legacy. Le coût d'écriture (et de lecture) pour Splendid/futurs tenants est multiplié par cette indirection. |
| **F12** | deps | `get_current_user` cumule 13 vérifications dans une seule fonction | `deps.py:203-352` | Token decode, type check, client binding (CBH), JTI blacklist, device revocation, account fetch, membership fetch ou lookup-by-id, status checks, password_change_required, header X-Tenant-ID cross-membership, RLS context set. Aucune extraction en sub-fonctions testables. Toute évolution = risque de régression. À refactor en chaîne de validateurs composables. |
| **F13** | deps + redis | Singletons module-level (`redis_sec`, `redis_cache`, `redis_client`, `cache_service`) | `redis.py:827-831` ; `cache.py:344` ; consommés via `from app.core.X import singleton` partout | Aucun mécanisme d'injection. Tests doivent monkey-patcher l'import. Failover Redis impossible sans process restart. Convention DI cassée à la racine du graph. |
| **F14** | deps | Imports locaux pour casser des cycles | `deps.py:217-218,250,349,400,414,511,524,924-925,998-1000` | `from app.repositories.account import …` à l'intérieur de fonctions. Symptôme d'un graphe de dépendances mal posé : `core/deps` dépend de `services/`, qui dépendent de `core/exceptions`, qui parfois importent depuis `core/`. Un découpage `core/` (foundations pures) vs `services/` propre résoudrait. |
| **F15** | redis | Lua scripts loadés best-effort sans erreur | `redis.py:79-80` (catch silencieux) | `Failed to load Lua script` sort un log mais le client reste utilisable. Le premier appel à `evalsha("revoke_all_user_tokens", ...)` lèvera `RuntimeError("Lua script not loaded")` en runtime. Plus grave : `logout_device` (ligne 339) et `logout_other_sessions` (ligne 367) catchent ce `RuntimeError` et basculent sur des fallbacks **non-atomiques** sans alerte. Un Redis correctement up + Lua mal chargé = perte silencieuse d'atomicité sur toutes les sessions. |
| **F16** | redis | Triple FAIL-CLOSED en cascade : Redis-SEC down → app totalement inutilisable | `redis.py:405,521-522,557,571` | `is_device_revoked`, `is_brute_force_locked`, `is_captcha_required`, `is_login_blocked` retournent toutes `True` si Redis-SEC est down. Conséquence : un tenant totalement bloqué (login impossible pour 100% des users) dès Redis-SEC indisponible. Le mode `EMERGENCY_BYPASS` (cf `redis.py:661`) existe mais nécessite Redis-SEC up pour être activé — paradoxe. Devrait être un **circuit breaker** géré au niveau du middleware avec basculement contrôlé. |
| **F17** | redis | `RedisCacheClient` héberge des **compteurs métier critiques** | `redis.py:793-805` — `incr_reservation_counter(year)`, `incr_invoice_counter(year)` sur Redis-CACHE (`allkeys-lru`) | Si la pression mémoire évince les clés `reservation_counter:2026` ou `invoice_counter:2026`, **les numéros de réservation/facture redémarrent à 1** → collisions dans la DB (qui a des contraintes uniques). Compteurs critiques métier doivent être : (a) en DB via une `Sequence` Postgres, ou (b) sur Redis-SEC noeviction au minimum. **De plus**, ces deux méthodes ne sont **utilisées nulle part** dans le codebase (`grep` confirme : seulement définies + clés dans `constants/security.py:131-132,231-236`) — code mort dangereux qui suggère que la numérotation officielle passe ailleurs (probablement par DB), donc ces méthodes peuvent être supprimées. |

### 3.3 Frictions P2 (incohérence convention)

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F18** | config | `settings = get_settings()` exposé module-level | `config.py:333` | Tout import de `config` exécute la lecture `.env` + validators. Le `lru_cache` empêche de rebuild simplement en tests. À convertir en `Depends(get_settings)`. |
| **F19** | config | `CORS_ORIGINS` default contient le port 3002 (legacy Marveline) | `config.py:94` | Couplage Marveline historique dans la config par défaut. Devrait être `[]` et `.env.example` documenter les valeurs dev. |
| **F20** | config | `APP_NAME = "CaroCorp"` mais reste de la config = "marveline" | `config.py:44` vs `:65,66,114,175` | Naming interne incohérent (CaroCorp = nom legacy, Marveline = nom actuel, en pratique 4 marques sont opérées sur cette codebase). |
| **F21** | database | Dual engine sync + async (legacy "migration en cours") | `database.py:32,43,58` | Commentaire "Sync (Celery + migration en cours)" qui dure. Double pool, double config, double event listener. Coût de maintenance × 2. À terminer la migration ou la formaliser comme architecture cible. |
| **F22** | database | `pool_recycle=3600` valeur magique non documentée | `database.py:39,63` | Devrait référencer une constante (ex `Limits.DB_POOL_RECYCLE_SECONDS`) avec une documentation prod (cohérence vs `wait_timeout` PG/PgBouncer). |
| **F23** | deps | Type aliases prolifèrent (60+) | `deps.py:472-902` | Pour chaque ressource × 3 versions (v2 Permission, v3 Scope Union, v3 Scope User-only). Effet combinatoire : ajouter une ressource = ajouter 3-6 aliases. À générer depuis l'enum `Scope`. |
| **F24** | deps | Inconsistance typage `principal_id: str` vs `id: int` | `deps.py:79,103,193` | `Principal.principal_id` retourne `str` (compat API key string-based) mais `UserCompat.id` retourne `int`. Caller doit caster — cast oublié = bug silencieux. |
| **F25** | deps | `password_change_required` check par allowlist d'URLs | `deps.py:323` (`request.url.path not in PASSWORD_CHANGE_ALLOWED`) | Couplage URL-routing. Si on renomme `/api/v1/users/me/password` en `/api/v1/auth/change-password`, la liste devient obsolète sans erreur. Devrait être marqué par scope/decorator. |
| **F26** | deps | `require_scope_async` accepte `str` au lieu de `Scope` enum | `deps.py:696` (signature `*scopes: str`) | Régresse le type guard P1-05 présent dans `require_scope` ligne 662-667. Une typo string passe silencieusement (jamais matchée), donc 403 systématique invisible. |
| **F27** | exceptions | Messages exposés en anglais | `exceptions.py:55,61,67,87,...` | App francophone, exceptions publiques renvoyées tel quel. Au minimum les `error_code` sont exploitables — donc les `message` sont soit du bruit, soit à internationaliser côté frontend. |
| **F28** | exceptions vs middleware | Format réponse erreur incohérent | `exceptions.py:42-48` retourne `{error, message, details}` ; `middleware/app_enforcement.py:108-117` retourne `{success, error, message, detail}` (champs différents) | Frontend doit gérer 2 formats. Middlewares devraient passer par les exceptions de `app/core/exceptions`. |
| **F29** | redis | `RedisSecClient` mêle 11 domaines | `redis.py:33-715` | Voir F04. À éclater en 7-9 stores : `CsrfStore`, `RefreshTokenStore`, `AccessBlacklistStore`, `TokenFamilyStore`, `SessionStore` + index, `BruteForceStore`, `CredentialStuffingStore`, `OAuthStateStore`, `DegradationStore`. |
| **F30** | redis | Convention de clés incohérente : callable `RedisKeys.foo(...)` vs concat `f"{RedisKeys.FOO}{x}"` | callable : `redis.py:103,159,190,...` ; concat : `redis.py:511,518,526,534,588,599` | Mix de styles. Tout devrait être callable pour permettre la validation d'argument et le re-typage centralisé. |
| **F31** | redis | Defensive `member.decode() if isinstance(member, bytes)` malgré `decode_responses=True` | `redis.py:134,327,358` | `decode_responses=True` à la création (lignes 50, 733) garantit `str` partout. Code défensif mort + dette de lecture. |
| **F32** | redis | OAuth state FAIL-CLOSED par exception alors que tout le reste FAIL-CLOSED par retour | `redis.py:680,698` (`raise`) vs partout ailleurs (`return False/None/True`) | API du client incohérente. Force le caller à try/except au lieu de check du retour. |
| **F33** | redis | `WS_TICKET_TTL_SECONDS = 30` hardcodé en attribut classe | `redis.py:607` | À déplacer dans `app/constants/`. |
| **F34** | redis | `RedisCacheClient` n'a pas de Lua loader | `redis.py:725-739` (vs `redis.py:42-87` pour Sec) | Asymétrie d'API. Probablement intentionnel mais documenter. |
| **F35** | cache | `flush_all()` exposé en API publique | `cache.py:272-292` | Comment "JAMAIS en production" sans guard runtime. Un usage accidentel via REPL ou import erroné détruit tout le cache. À déplacer dans `tests/utils/cache_helpers.py`. |
| **F36** | cache | Duplication `cache_service` (singleton module-level) + `CacheService()` (instanciable) | `cache.py:344` (singleton) ; `cache.py:333` (instance ad hoc dans le décorateur cassé) | Convention hésitante. Imposer le singleton ou rendre l'instance stateless. |
| **F37** | cache | TTL hardcodés dans la docstring (5min, 10min) | `cache.py:6-9` ; valeurs réelles dans `repositories/base.py:58-63` (dict `_cache_ttl_map`) | Aucune constante centralisée. Chaque caller passe `ttl=300` à la main. |
| **F38** | __init__ | Re-export massif eager | `__init__.py:1-120` | `from app.core import Permission` charge `permissions.py`, `validators.py`, `password_policy.py`, `crypto.py`, `metrics.py`, `rate_limiter.py`, `logging.py`, `exceptions.py`. Aucune lazy-loading. |
| **F39** | slow_query | Constantes hardcodées `SLOW_QUERY_THRESHOLD_MS = 100`, `MAX_QUERIES_PER_REQUEST = 20` | `slow_query.py:14-15` | À déplacer dans `app/constants/limits.py` ou `observability.py`. |
| **F40** | slow_query | Warning N+1 sort une seule fois (au seuil exact) | `slow_query.py:55` (`if count == MAX_QUERIES_PER_REQUEST`) | Strict equality au lieu de `>=`. Une requête à 21 queries ne re-warnera pas. |

### 3.4 Frictions P3 (cosmétique)

| ID | Couche | Friction | Citation |
|---|---|---|---|
| **F41** | redis | Alias compat `redis_client = redis_sec` | `redis.py:831` — backward compat à dégager après audit des imports. |
| **F42** | cache | Docstring décrit `@cached()` qui n'existe plus | `cache.py:28-31` (exemple `@cached(...)`) — supprimé ligne 296, doc orpheline. |
| **F43** | cache | `_DateEncoder` redéfini localement | `cache.py:45-55` — Pydantic `model_dump_json()` gère déjà datetime/Decimal. |
| **F44** | exceptions | `EmailAlreadyExists` hérite de `AlreadyExists` mais ne réutilise pas le `status_code` parent (pas un bug, juste redondant) | `exceptions.py:139-141` — héritage utilisé pour 1 attribut diff (error_code). |
| **F45** | redis | `revoke_sessions_except_device` parse `"did:sid"` avec `split(":", 1)` | `redis.py:330` — fragile si `did` contient `:` (caractère valide en UUID4 hex non, mais en UUID base64url oui). À documenter ou normaliser le format. |
| **F46** | config | Default `BOXTAL_ENV="test"` mélange config tiers et environnement | `config.py:166` — devrait suivre `SENTRY_ENVIRONMENT`. |

---

## 4. Dépendances inter-modules / fuites

### 4.1 Couplages observés

- `core/database` ← `core/slow_query` (import direct au module-load) → couplage fort, pas de DI
- `core/deps` ← `services/{token,rbac,api_key,mfa}` → core dépend des services (inversion saine attendue : services dépendent du core, pas l'inverse) — F14
- `core/deps` ← `repositories/{account,tenant_membership,api_key}` → idem
- `core/cache` ← `core/redis`, `core/metrics` → OK
- `repositories/base` → `core.cache` (lazy import pour casser le cycle) — voir module 06
- `core/redis` ← `app/constants` → OK (constantes < core, sain)

### 4.2 Cycle latent

`core/cache` ↔ `repositories/base` :
- `repositories/base.py:14-16` fait un import lazy de `app.core.cache.cache_service` "pour éviter le circular import : repositories.base → core.cache → core.__init__ → core.deps → services → repositories.base".
- Symptôme : `core/__init__` re-exporte `Permission`, donc tout import de `core.cache` charge `core.deps` qui charge `services.token` qui charge des repositories. Le problème est résolu par lazy import mais la dette reste.

### 4.3 Fuites identité Marveline / Splendid (renvoi vers module 09)

- `JWT_ISSUER = "marveline.com"` — émis pour tous les tenants, y compris brand_code=lesplendid
- `MFA_ISSUER_NAME = "Marveline"` — TOTP label
- `SMTP_FROM = "noreply@marveline.com"` — emails Splendid envoyés depuis ce from
- `FRONTEND_URL = "http://localhost:3000"` (default) — un seul frontend, alors qu'on a 4 apps

→ Voir `09-tenant-multi-app-brand.md` pour analyse approfondie.

---

## 5. Recommandations de refonte

### 5.1 Ordonnancement (le plus dépendant en premier)

#### Priorité 1 — Étanchéité tenant (P0)
1. **F01** : remplacer `f"SET LOCAL app.current_tenant_id = '{tid}'"` par paramètre lié. SQLAlchemy `text("SET LOCAL app.current_tenant_id = :tid").bindparams(tid=str(tid))` ou `cursor.execute("SET LOCAL app.current_tenant_id = %s", (str(tid),))`. Audit de tous les sites SQL générés par f-string dans le repo (`grep -rn 'f".*\(SET\|SELECT\|INSERT\|UPDATE\|DELETE\)'`).
2. **F02** : `_resolve_api_key_async` doit appeler `set_tenant_context(api_key.tenant_id)` avant return. Tests cross-tenant doivent inclure un cas API-key. Idem `_resolve_api_key` sync.
3. **F05** : déterminer si `BaseRepository` (sync) est appelé en prod. Si oui, supprimer la branche cache (qui ne fonctionne pas) ou ajouter un wrapper sync `cache_service_sync` qui appelle Redis via `redis-py` synchrone. Si non, dégager le code mort.

#### Priorité 2 — Découpage infrastructure (P0)
4. **F03** : éclater `deps.py` en :
   - `core/auth/principal.py` (Principal Protocol, ApiKeyClient, UserCompat)
   - `core/auth/dependencies.py` (get_current_user, get_current_principal, get_current_account, get_current_membership)
   - `core/auth/authz.py` (require_scope, require_permission, require_stepup)
   - `core/auth/types.py` (type aliases — générés depuis `Scope` enum)
5. **F04, F29** : éclater `redis.py` en `core/storage/redis_client.py` (clients bruts) + 1 store par domaine fonctionnel dans `core/auth/stores/`, `core/security/stores/`.
6. **F10** : décider du système d'autorisation canonique (recommandation : Scope v3) et déprécier les 3 autres avec migration progressive endpoint par endpoint. Décision actée dans le module 11 (RBAC).
7. **F11** : finir la migration Account+Membership → supprimer `UserCompat`. Ré-écrire les endpoints v1 pour consommer `(Account, Membership)` directement.

#### Priorité 3 — Sûreté opérationnelle (P1)
8. **F16** : circuit breaker centralisé pour Redis-SEC. Quand le breaker est ouvert, la stratégie FAIL-CLOSED est désactivée et bascule en `EMERGENCY_BYPASS` automatiquement. Évite le scénario "Redis-SEC down → app totalement bloquée".
9. **F17** : confirmer que `incr_reservation_counter` / `incr_invoice_counter` sont bien morts (modules 19/22 le confirmeront). Si oui, supprimer les méthodes + clés dans `constants/security.py:131-132,231-236`. Si non, migrer vers une `Sequence` Postgres ou Redis-SEC noeviction.
10. **F15** : `load_lua_scripts` doit lever fatal si un script échoue à charger en prod (différencier `if settings.DEBUG`). Les fallbacks non-atomiques `_logout_device_fallback` / `revoke_sessions_except_device` doivent émettre un WARNING explicit "ATOMICITY LOST".

#### Priorité 4 — Identité multi-brand (P1)
11. **F06, F07** : remplacer les hardcodes par lookup `tenant_brand` / `tenant.brand_code` :
   - JWT issuer/audience dérivés de `tenant.app_code` + `tenant.brand_code` lors de l'émission (service `token`).
   - SMTP_FROM dérivé de `tenant_brand.contact_email` lors de l'envoi (service `notification`).
   - MFA_ISSUER_NAME dérivé de `tenant_brand.display_name` lors de l'enrôlement TOTP.
   - `config.py` ne porte que les défauts (nouveau tenant sans brand row).

#### Priorité 5 — Hygiène config (P1-P2)
12. **F09** : éclater `Settings` en classes thématiques composées (`SecuritySettings`, `DatabaseSettings`, `RedisSettings`, `AuthProviderSettings`, `WalletSettings`, `IntegrationSettings`).
13. **F08** : sortir le ngrok auto-detect du model_validator. Hook startup async (`lifespan` FastAPI) qui peuple un cache si DEBUG.
14. **F18** : remplacer `settings = get_settings()` module-level par `Depends(get_settings)`. Garder le singleton seulement pour les imports historiques.

#### Priorité 6 — Conventions (P2-P3)
15. **F28** : centraliser les réponses d'erreur via `AppException.to_dict` dans tous les middlewares. Définir un schema Pydantic `ErrorResponse` partagé.
16. **F37, F39** : extraire toutes les valeurs magiques (TTL cache, seuils slow query, pool sizes) dans `app/constants/limits.py` ou `observability.py`.
17. **F23** : générer les type aliases Scope depuis l'enum `Scope` directement (boucle sur `Scope.__members__`). Évite la duplication mécanique.
18. **F30** : harmoniser les clés Redis en callables. Audit `RedisKeys` complet dans le module 07 (constants).
19. **F32** : harmoniser le FAIL-CLOSED par retour vs exception. Choisir un style et appliquer.

### 5.2 Tests à écrire avant refonte

Pour figer le comportement actuel avant de casser :
- Test : `_inject_rls_tenant` injecte bien `app.current_tenant_id` au format attendu.
- Test d'intégration : auth via API key → query DB → RLS policy filtre par tenant (devrait actuellement échouer → confirme F02).
- Test : `get_current_user` rejette un token avec `mid` membership d'un autre account.
- Test : 4 systèmes RBAC bloquent et autorisent identiquement pour un même couple `(role, scope, resource:action)` — sinon la migration vers v3 unique cassera des endpoints.
- Test : `_resolve_api_key_async` set bien le RLS context (devrait échouer aujourd'hui).
- Test : `cache_service.get` appelée depuis `BaseRepository.get_by_id` (sync) sur un tenant valide retourne un dict, pas une coroutine. Devrait échouer aujourd'hui → confirme F05.
- Test : `incr_reservation_counter` et `incr_invoice_counter` ne sont pas appelés dans le code de génération des numéros (grep négatif → confirme F17).
- Test : `_logout_device_fallback` émet un log WARNING si appelé.

### 5.3 Hors-scope de cette refonte (à laisser pour modules suivants)

- `core/security`, `core/crypto`, `core/kms`, `core/permissions`, `core/validators`, `core/upload_validator`, `core/password_policy` → module 02
- `core/logging`, `core/metrics`, `core/rate_limiter`, `core/rate_limit_utils`, `core/health` → module 03
- `app/middleware/*` → module 04

---

## 6. Verdict module 01

| Aspect | État |
|---|---|
| Convention 4 couches | N/A (infrastructure transverse) |
| Étanchéité tenant | **Cassée pour API keys** (F02) + injection SQL latente (F01) + cache cassé sur sync repos (F05) |
| Multi-app/multi-brand | **Identité Marveline hardcodée** (F06, F07), Splendid hérite |
| Cohésion modules | **Faible** : 1 fichier de 1066 LoC, 1 de 831 LoC, mélange de domaines fonctionnels |
| Atomicité opérations sécurité | **Fragile** : Lua best-effort + fallback silencieux (F15), triple FAIL-CLOSED en cascade (F16) |
| Risque numérotation métier | **Latent** : compteurs réservations/factures sur Redis LRU (F17), même si actuellement non utilisés |
| Dette | 46 frictions documentées : 5 P0, 12 P1, 23 P2, 6 P3 |

**Conclusion** : `core/` est le socle qui pollue tout le reste du codebase. Toute amélioration architecturale en aval (modules métier) sera limitée par ce qui n'est pas corrigé ici. **Les 5 P0 (F01, F02, F03, F04, F05) doivent être traités avant toute refonte de domaine métier**, sinon la dette se propage à chaque nouveau module et les fixes deviennent de la cosmétique sur fondation pourrie.

→ Module suivant : `02-core-security.md` (security, crypto, kms, password_policy, permissions, validators, upload_validator).
