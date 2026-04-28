# Module 03 — Core observabilité (logging / metrics / health / rate limiting)

## 1. Périmètre

| Fichier | LoC | Rôle |
|---|---|---|
| `app/core/logging.py` | 253 | Structured JSON logging, sanitization secrets, ContextVars (request_id, tenant_id, user_id), formatters JSON + Console |
| `app/core/metrics.py` | 340 | 12 métriques Prometheus (RED + DB + Redis + Cache + Business), `metrics_endpoint` |
| `app/core/health.py` | 122 | `check_postgres`, `check_redis`, `check_redis_async` |
| `app/core/rate_limiter.py` | 218 | `RateLimiter` Redis INCR+EXPIRE, `get_scope_config`, `build_key` |
| `app/core/rate_limit_utils.py` | 123 | `_decode_jwt_claims`, `get_user_id_from_jwt`, `get_tenant_id_from_jwt`, `determine_rate_limit_scope` |
| `app/core/slow_query.py` | 59 | (déjà couvert module 01 — F33, F39, F40) |

**Total** : 1 115 LoC.

**Dépend de** : `app/core/{config, security, redis}`, `app/constants/{security, http, limits}`, `prometheus_client`, `redis.asyncio`.

**Dépendu par** : middlewares (cf. module 04 — `MetricsMiddleware`, `RateLimitMiddleware`, `RequestContextMiddleware`), `app/main.py` (configure_logging au boot), endpoint `/metrics`, endpoints `/health`.

---

## 2. Lecture par fichier

### 2.1 `logging.py` (253 LoC)

#### Structure
- 3 ContextVars (lignes 29-31) : `request_id_var: Optional[str]`, `tenant_id_var: Optional[int]`, `user_id_var: Optional[int]`. Default `None` pour distinguer "non set" de "set à 0/vide" (commentaire ligne 26 : "fix M6").
- `SENSITIVE_FIELDS: Set[str]` (lignes 38-56) : 16 entrées — `password, password_hash, token, access_token, refresh_token, secret, api_key, authorization, cookie, session_id, credit_card, card_number, cvv, ssn, social_security, private_key, encryption_key`.
- `REDACTED = "[REDACTED]"`.
- `sanitize_value(key, value)` (ligne 61) :
  - `key_lower = key.lower()`.
  - `if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS)` → si str et len>8, `f"{value[:4]}...{REDACTED}"`, sinon `REDACTED`.
- `sanitize_dict(data)` (ligne 74) : récursif sur dicts et listes de dicts.
- `mask_email(email)` (ligne 93) : `j***n@example.com` (ou `j*@…` si local ≤ 2).
- `_LOGRECORD_BUILTIN_ATTRS` (ligne 109) : 22 attrs built-in à exclure.
- `JSONFormatter` (ligne 118) :
  - Champs : `timestamp`, `level`, `logger`, `message`.
  - ContextVars conditionnels (only if not None).
  - `extra` = `record.__dict__` filtré sur builtins → `sanitize_dict`.
  - `exception` si `exc_info`.
- `ConsoleFormatter` (ligne 161) : ANSI colors par level. Truncate `request_id[:8]`.
- `configure_logging(level, json_format, include_console)` (ligne 195) :
  - `root_logger.handlers.clear()` puis ajout d'un handler stdout.
  - Réduction third-party : `uvicorn.access`, `sqlalchemy.engine`, `httpx`, `httpcore` → WARNING.
- `set_request_context(request_id, tenant_id, user_id)` / `clear_request_context` (lignes 235, 249).

### 2.2 `metrics.py` (340 LoC)

12 métriques Prometheus exposées :

| Métrique | Type | Labels | Source |
|---|---|---|---|
| `http_requests_total` | Counter | `method, path, status` | `MetricsMiddleware` |
| `http_request_duration_seconds` | Histogram (11 buckets 5ms→10s) | `method, path` | idem |
| `http_requests_in_progress` | Gauge | `method, path` | idem |
| `rate_limit_hits_total` | Counter | `scope, identifier_type` | `RateLimitMiddleware` |
| `db_queries_total` | Counter | `operation` | (consommateur non identifié au grep) |
| `db_query_duration_seconds` | Histogram (11 buckets 1ms→5s) | `operation` | idem |
| `redis_commands_total` | Counter | `command` | `core/cache.py:170` |
| `redis_command_duration_seconds` | Histogram (9 buckets 0.1ms→100ms) | `command` | idem |
| `cache_hits_total` | Counter | `entity` | `repositories/base.py` |
| `cache_misses_total` | Counter | `entity` | idem |
| `cache_hit_rate` | Gauge | `entity` | `repositories/base.py:_update_cache_hit_rate` |
| `reservations_total` | Counter | `status` | (consommateur non identifié au grep) |
| `invoices_total` | Counter | `status` | idem |

`metrics_endpoint() -> Response` (ligne 310) renvoie `generate_latest()` au format texte Prometheus, sans authentification (commentaire ligne 335 : "metrics endpoint public").

#### Aucun label tenant-aware
- Tous les Counter/Histogram exposent `path`, `method`, `status`, `command`, `operation`, `scope`, `entity`, mais **aucune métrique n'inclut `tenant`, `app_code`, ni `brand_code`**.

### 2.3 `health.py` (122 LoC)

3 fonctions :
- `check_postgres(db: Session) -> Tuple[bool, dict]` (ligne 26) :
  - `db.execute(text("SELECT 1"))` + mesure latence.
  - `engine.pool.size()`, `engine.pool.checkedout()` si `hasattr(engine, 'pool')`.
  - Retourne `(False, {error})` sur exception.
- `check_redis(redis_client: Redis) -> Tuple[bool, dict]` (ligne 87) :
  - `redis_client.ping()` + `redis_client.info()`.
  - Métadonnées : `latency_ms`, `memory_used_mb`, `connected_clients`.
- `check_redis_async(redis_client) -> Tuple[bool, dict]` (ligne 106) : version async, signature param non typée.

Aucune fonction pour Celery, WireGuard, SMTP, tiers (Boxtal, Wallet, OAuth providers).

### 2.4 `rate_limiter.py` (218 LoC)

#### `RateLimiter` (ligne 47)
- `__init__(redis_client: AsyncRedis)`.
- `check_rate_limit(key, limit, window_seconds) -> (allowed, metadata)` (ligne 65) :
  - `current_count = await self.redis.incr(key)` (atomique).
  - Si `current_count == 1` → `await self.redis.expire(key, window_seconds)`.
  - Lecture `ttl`. Si `ttl == -1` (pas de TTL — race condition) → re-EXPIRE (ligne 117-120).
  - `allowed = current_count <= limit`.
  - Metadata : `limit, remaining=max(0, limit-count), reset, retry_after, current`.
  - **FAIL-CLOSED** : exception → `(False, {error: rate_limiter_unavailable, retry_after: 30})`.

#### `get_scope_config(scope) -> (limit, window_seconds)` (ligne 155)

Dict hardcodé inline (lignes 179-191) :

| Scope | Limit | Window | Commentaire |
|---|---|---|---|
| `GLOBAL_IP` | 1000 | 60s | anti-DDoS général |
| `LOGIN` | 5 | 60s | anti brute-force |
| `USER_AUTHENTICATED` | 200 | 60s | « quota Marveline » |
| `API_KEY_AUTHENTICATED` | 1000 | 60s | M2M |
| `MUTATIONS` | 100 | 60s | POST/PUT/DELETE non auth |
| `READS` | 300 | 60s | GET non auth |
| `EPICERIE_AUTHENTICATED` | 500 | 60s | POS scan haute fréquence |
| `EPICERIE_MUTATIONS` | 300 | 60s | ventes POS |
| `RESTAURANT_AUTHENTICATED` | 500 | 60s | service salle |
| `RESTAURANT_MUTATIONS` | 300 | 60s | commandes cuisine |

Lève `ValueError` si scope inconnu (ligne 193).

#### `build_key(scope, identifier) -> str` (ligne 198)
`f"{RedisKeys.RATE_LIMIT}{scope}:{identifier}"` — pattern `rate_limit:{scope}:{identifier}`.

### 2.5 `rate_limit_utils.py` (123 LoC)

- `X_API_KEY_HEADER = "X-API-Key"` (ligne 14) — **dupliqué depuis deps.py** (commentaire ligne 12 : "briser le circular import").
- `_decode_jwt_claims(request) -> Optional[dict]` (ligne 17) : extract Bearer, `decode_token(token)` (sans audience), swallow `Exception` retourne None.
- `get_user_id_from_jwt(request) -> Optional[int]` (ligne 33).
- `get_tenant_id_from_jwt(request) -> Optional[int]` (ligne 42).
- `determine_rate_limit_scope(request) -> str` (ligne 51) :
  1. `path == LOGIN` ou `path == CSRF` → `LOGIN` scope.
  2. Header `X-API-Key` présent → `API_KEY_AUTHENTICATED`.
  3. JWT valide → :
     - `path` contient `/epicerie/` → `EPICERIE_MUTATIONS` (POST/PUT/PATCH/DELETE) ou `EPICERIE_AUTHENTICATED`.
     - `path` contient `/restaurant/` → `RESTAURANT_MUTATIONS` ou `RESTAURANT_AUTHENTICATED`.
     - sinon → `USER_AUTHENTICATED`.
  4. Mutation non auth → `MUTATIONS`.
  5. Sinon → `READS`.

---

## 3. Frictions identifiées

(Numérotation continue — F83 commence après le module 02.)

### 3.1 Frictions P0

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F83** | metrics | **Aucune métrique n'a de label `tenant_id` / `app_code` / `brand_code`** | `metrics.py:38-307` (toutes les définitions) | Conséquence directe pour SaaS multi-tenant à scalabilité maximale :<br>(a) **Impossible de mesurer la charge par tenant** (Marveline vs Splendid vs Épicerie vs Restaurant). Les dashboards Grafana tenant-aware sont impossibles.<br>(b) **Pas de SLO par tenant** — un tenant gourmand qui dégrade le p99 ne peut pas être identifié.<br>(c) **Facturation à l'usage impossible** (modèle SaaS courant : facturer au req/min, au stockage, au compute par tenant).<br>(d) **Détection d'anomalies par tenant impossible** (un user d'un tenant abuse → invisible, fondu dans la masse).<br>**Mitigation cardinality** : ajouter `app_code` (3-4 valeurs) au lieu de `tenant_id` (potentiellement N tenants), ou un label `tenant_bucket` agrégé. À fixer dès maintenant : tout middleware qui INC une métrique doit lire le tenant_id depuis `request.state` et l'ajouter en label. |
| **F84** | rate_limiter | **Rate limit non scopé par tenant** | `rate_limiter.py:198-218` (`build_key(scope, identifier)` n'inclut pas `tenant_id`) ; `rate_limit_utils.py:33-48,93-123` (le scope est dérivé de path/JWT mais l'identifier est juste IP ou user_id) | Conséquences :<br>(a) Un user A d'un tenant Marveline et un user B d'un tenant Splendid avec le même `account_id` (un Account peut avoir plusieurs memberships) **partagent leur quota** `USER_AUTHENTICATED`.<br>(b) **Pas de quota par tenant** : impossible de limiter un client gourmand sans pénaliser tous les autres tenants partageant le scope.<br>(c) **Attaque cross-tenant amplifiée** : un attaquant qui flood Marveline épuise le quota global IP `1000/min` qui est ensuite refusé pour un user légitime de Splendid sur le même IP.<br>**Multi-tenant à scalabilité maximale** : la clé Redis doit être `rate_limit:{tenant_id}:{scope}:{identifier}` ou au moins `rate_limit:{app_code}:{scope}:{identifier}`. |

### 3.2 Frictions P1

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F85** | logging | `SENSITIVE_FIELDS` couverture incomplète | `logging.py:38-56` (16 entrées) | Manque : `pin`, `mfa_code`, `totp`, `totp_secret`, `backup_code`, `webauthn`, `client_secret`, `kek`, `dek`, `pepper`, `salt`, `encrypted_dek`, `nonce`, `signature`, `peppered_password`. Termes utilisés dans le code (cf. `crypto.py`, `services/mfa`, `services/webauthn`, `core/security`). Un log avec `extra={"totp_secret": "JBSWY3DPEHPK3PXP"}` passe en clair en JSON. |
| **F86** | logging | `sanitize_value` substring match → faux positifs ET masquage de 4 premiers chars | `logging.py:67-70` | (a) `if any(sensitive in key_lower)` matche `password_history`, `oauth_authorization_code`, `cookie_consent` — masque inutile. (b) `f"{value[:4]}...{REDACTED}"` expose 4 chars d'un secret en clair pour aider au debug — pour un token JWT court (header seulement) ça expose la version, pour un PIN 4 chiffres ça expose tout. À borner : exact match sur le nom OU pattern regex (`^password$|password$|_password$`), et masquer 100% pour les secrets, exposer un hash court pour les tokens. |
| **F87** | metrics | `path` label sur HTTP métriques peut exploser la cardinalité | `metrics.py:38-94` (`path` libre, alimenté par `MetricsMiddleware`) | Si `path = request.url.path` brut, chaque ID dynamique (`/api/v1/products/123`, `/api/v1/products/124`, …) crée une métrique distincte. Pour un tenant avec 10k products + 100k réservations, c'est ~100k+ métriques `http_requests_total{path=...}`. Prometheus s'effondre, Grafana plante. **À normaliser** : utiliser `request.scope["route"].path_format` (template `/api/v1/products/{id}`) dans `MetricsMiddleware`. À confirmer dans module 04. |
| **F88** | metrics | `db_queries_total` / `db_query_duration_seconds` probablement morts | `metrics.py:135-175` ; aucun INC trouvé au grep | `slow_query.py` ne touche pas ces métriques (seulement WARNING log). Aucun service métier ne les inc explicitement. Probablement métriques orphelines — soit à brancher dans `slow_query.py:install_slow_query_listener`, soit à supprimer. |
| **F89** | metrics | Métriques business `reservations_total{status}`, `invoices_total{status}` couplées à Marveline | `metrics.py:276-306` | Statuts hardcodés en commentaire : `draft, confirmed, cancelled, completed` (réservations) et `draft, sent, paid, overdue, cancelled` (factures). Couplage à un domaine (location événementielle). Pour épicerie/restaurant, les statuts ventes sont différents. Et où sont incrémentées ces métriques ? Pas trouvé au grep — probablement orphelines comme F88. |
| **F90** | rate_limiter | `get_scope_config` dict hardcodé inline | `rate_limiter.py:179-191` | Limites par scope codées en dur. Conséquences :<br>(a) **Pas de surcharge par tenant** : un client premium avec quota élevé négocié = édition du code Python.<br>(b) **Pas de tuning à chaud** sans redéploiement.<br>(c) Splendid hérite du quota Marveline.<br>À déplacer dans `tenant_settings` (override par tenant) avec defaults dans `app/constants/limits.py`. |
| **F91** | rate_limit_utils | `determine_rate_limit_scope` détecte les apps via `path.startswith` | `rate_limit_utils.py:111-114` | Détection app par préfixe URL (`/epicerie/`, `/restaurant/`). Marveline = absent → tombe dans `USER_AUTHENTICATED` (200 req/min). Splendid (même app que Marveline) → idem. Devrait dériver de `tenant.app_code` lu depuis le JWT claim ou la session, pas de l'URL. **Scope multi-brand cassé** : un endpoint Marveline et un endpoint Splendid partagent `USER_AUTHENTICATED:user_id` Redis key (cf. F84). |
| **F92** | rate_limit_utils | `_decode_jwt_claims` décode le token à chaque call sans cache | `rate_limit_utils.py:17-30,33-48,93-123` | `determine_rate_limit_scope` appelle `get_user_id_from_jwt`. Dans le même middleware ou le même request lifecycle, si on appelle aussi `get_tenant_id_from_jwt`, le JWT est décodé 2 fois (RSA verify × 2 = ~2-5ms × 2). Devrait cacher dans `request.state.jwt_claims`. |
| **F93** | health | `check_postgres` ne définit pas le tenant context | `health.py:57-78` | `db.execute(text("SELECT 1"))` exécute sans `SET LOCAL app.current_tenant_id`. Pas critique pour `SELECT 1`, mais incohérent : montre que le tenant context n'est pas universel et peut être contourné par tout code qui obtient une session sans passer par `get_current_user`. |
| **F94** | rate_limiter | Race condition fenêtre TTL | `rate_limiter.py:107-120` | `INCR` puis `EXPIRE` séparés. Entre les deux, si le process crashe ou Redis evict, le compteur survit sans TTL. Le check ligne 117 (`if ttl == -1: EXPIRE`) limite mais ne supprime pas la fenêtre. Solution : Lua script atomique `INCR + EXPIRE-IF-NEW` ou `SET key value EX window_seconds NX` puis INCR. |

### 3.3 Frictions P2

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F95** | logging | `JSONFormatter` log level réduit aux third-party non configurable | `logging.py:220-223` | `uvicorn.access`, `sqlalchemy.engine`, `httpx`, `httpcore` forcés à WARNING. Pour debug prod (audit accès), il faudrait pouvoir les remettre à INFO temporairement via env var. À paramétrer. |
| **F96** | logging | `ConsoleFormatter` truncate `request_id[:8]` mais `JSONFormatter` log complet | `logging.py:186` vs `:136` | Incohérence — le JSON et le console-dev devraient afficher le même request_id complet (un user qui debug en console puis grep dans JSON ne matchera pas). |
| **F97** | metrics | Documentation Prometheus très verbose dans les docstrings | `metrics.py:14-31, 43-54, 67-87, 95-108, 117-131, 140-148, 156-175, 184-192, 200-213, 222-230, 232-248, 255-272, 281-290, 295-306, 310-340` | ~50% du fichier est de la doc. Devrait être dans `docs/observabilite.md` pour ne pas alourdir le module Python. |
| **F98** | metrics | `cache_hit_rate` Gauge maintenu manuellement côté app | `metrics.py:250-272` ; mis à jour via `repositories/base.py:_update_cache_hit_rate` | Calcul dérivé qui devrait être fait par Prometheus (`rate(cache_hits_total) / (rate(cache_hits_total) + rate(cache_misses_total))`). Maintenir un Gauge manuellement = fragile (oubli d'update, race condition entre processes uvicorn workers). À supprimer le Gauge, calculer côté Prom. |
| **F99** | health | `check_postgres` ne checke pas overflow pool | `health.py:73-77` | Expose `pool_size` et `pool_checked_out` mais ne calcule pas `overflow = checkedout - size` ni n'alerte si proche saturation. Indicateur de saturation manqué. |
| **F100** | health | Health check incomplet | `health.py` entier | Aucun check pour : Celery (broker, workers), service WireGuard, SMTP, Sentry, OAuth providers, Boxtal, Apple/Google Wallet. Health check production = orchestration partielle. |
| **F101** | health | Pas de timeout explicite | `health.py:58-78` | Si Postgres bloque (deadlock, slow disk), `db.execute(SELECT 1)` pend jusqu'au timeout SQLAlchemy par défaut (souvent 30s+). `/health/ready` ne devrait pas pendre — `statement_timeout` 1s + `set_session(deferrable=True)`. |
| **F102** | health | `check_redis_async` paramètre non typé | `health.py:106` (`async def check_redis_async(redis_client) -> ...`) vs `:87` (`check_redis(redis_client: Redis)`) | Inconsistance type hints. À typer `AsyncRedis`. |
| **F103** | rate_limiter | Limites magiques sans constantes nommées | `rate_limiter.py:179-191` | `(1000, 60)`, `(5, 60)`, `(200, 60)` etc. À déplacer vers `app/constants/limits.py` (`Limits.RATE_LIMIT_GLOBAL_IP_PER_MIN`, etc.). |
| **F104** | rate_limiter | Window glissant approximatif (TTL-based) | `rate_limiter.py:107-138` | Pas de vrai sliding window. Effet bordure : à la transition de fenêtre, un attaquant peut faire 2× le quota en 2 secondes. Pour un anti-brute-force (`LOGIN: 5 req/60s`), ça permet 10 tentatives en 2s. Algo plus rigoureux : token bucket, sliding log (Redis sorted set), ou window + sub-buckets. |
| **F105** | rate_limit_utils | `_decode_jwt_claims` swallow `Exception` | `rate_limit_utils.py:29-30` | `except Exception: return None` cache toutes les erreurs. Un attaquant qui forge des tokens passe en silence. Devrait au moins logger en DEBUG ou compter via `metrics.invalid_jwt_total`. |
| **F106** | rate_limit_utils | `decode_token` appelé sans `expected_audience` | `rate_limit_utils.py:28` | Le rate limiter accepte n'importe quelle audience valide → couplé aux faiblesses F47/F60 du module 02 (audience non vérifiée si type absent). Pas critique pour le rate limiting mais pratique de defense-in-depth. |
| **F107** | rate_limit_utils | `X_API_KEY_HEADER` dupliqué pour casser un cycle | `rate_limit_utils.py:12-14` (commentaire explicite) | Symptôme du graphe d'imports tordu. À résoudre par découpage `core/auth/` (cf. F03 module 01). |

### 3.4 Frictions P3

| ID | Couche | Friction | Citation |
|---|---|---|---|
| **F108** | logging | Messages logs en anglais pas documenté comme convention | `logging.py` entier — pas une friction objective si la convention "logs en anglais" est claire, mais elle n'est ni dans CLAUDE.md ni dans `docs/conventions/`. |
| **F109** | metrics | `metrics_endpoint` non authentifié | `metrics.py:310,335` (commentaire « metrics endpoint public ») | OK pour réseau interne, mais exposer publiquement = leak d'infos opérationnelles (charges, statuts, erreurs). À protéger derrière une API key dédiée si exposé hors VPC. |
| **F110** | rate_limiter | Comment `# 200 req/minute (Marveline)` couplage explicite | `rate_limiter.py:182` |  À supprimer une fois F90 traité. |

---

## 4. Dépendances inter-modules / fuites

### 4.1 Couplages observés

- `logging` → standalone (aucun import `app.*` autre que standard).
- `metrics` → standalone (uniquement `prometheus_client`, `starlette`).
- `health` → SQLAlchemy + redis (via param injection — sain).
- `rate_limiter` → `app.constants` (RateLimitScope, RedisKeys).
- `rate_limit_utils` → `app.constants` + `app.core.security.decode_token` → couplage fort à la couche JWT pour décoder, mais utilisé en mode "best effort" (swallow exception).

### 4.2 Cycles évités par duplication / lazy

- `rate_limit_utils.X_API_KEY_HEADER = "X-API-Key"` — dupliqué depuis `deps.py` pour briser un cycle (F107).
- `core/health` consommé par `app/api/v1/endpoints/health.py` (à confirmer module 35).

### 4.3 Fuites identité Marveline / Splendid / Multi-tenant

- **F83** : Métriques sans label tenant → tout dashboard SaaS cassé.
- **F84** : Rate limit sans tenant key → cross-tenant leakage de quota.
- **F89** : Métriques business avec statuts Marveline-only.
- **F90** : Limites globales — Splendid hérite Marveline.
- **F91** : `determine_rate_limit_scope` ne distingue pas Marveline de Splendid.
- **F110** : Commentaire explicite « (Marveline) » sur le quota par défaut.

### 4.4 Forward-references

- F87 (cardinalité `path`) et F88 (`db_queries_total` orphelin) à confirmer dans le module 04 (middlewares).
- F89 (métriques business orphelines) à confirmer dans les modules métier (19 réservations, 22 factures).

---

## 5. Recommandations de refonte

### 5.1 Priorité 1 — Multi-tenancy observabilité (P0)

1. **F83** : ajouter `app_code` (et éventuellement `tenant_id_bucket`) en label sur les métriques HTTP, DB, Redis, business :
   ```python
   http_requests_total = Counter(
       'http_requests_total',
       'Total HTTP requests',
       ['method', 'path', 'status', 'app_code'],  # +app_code
   )
   ```
   Le middleware Metrics doit lire `request.state.app_code` (set par AppEnforcement middleware) et l'inclure. Pour limiter la cardinalité : `app_code ∈ {marveline, epicerie, restaurant, lesplendid, anonymous}`. Documentation `docs/observabilite.md`.

2. **F84** : modifier `RateLimiter.build_key` :
   ```python
   def build_key(self, scope: str, identifier: str, tenant_id: int | None = None) -> str:
       parts = [RedisKeys.RATE_LIMIT, scope]
       if tenant_id is not None:
           parts.append(f"t{tenant_id}")
       parts.append(identifier)
       return ":".join(parts)
   ```
   `determine_rate_limit_scope` doit retourner `(scope, tenant_id)` ou exposer le tenant via `request.state`. Tests : un user sur tenant 1 et un user sur tenant 5 (Splendid) ne doivent pas partager leur quota.

### 5.2 Priorité 2 — Hygiène logs et sécurité (P1)

3. **F85** : étendre `SENSITIVE_FIELDS` :
   ```python
   SENSITIVE_FIELDS: frozenset[str] = frozenset({
       "password", "password_hash", "peppered_password",
       "token", "access_token", "refresh_token", "csrf_token",
       "secret", "client_secret", "totp_secret", "backup_code",
       "api_key", "x-api-key", "authorization", "bearer",
       "cookie", "set-cookie", "session_id",
       "credit_card", "card_number", "cvv", "ssn", "social_security",
       "private_key", "encryption_key", "kek", "dek", "encrypted_dek",
       "pepper", "salt", "nonce", "signature",
       "pin", "mfa_code",
   })
   ```

4. **F86** : remplacer le substring match par exact ou regex bornée :
   ```python
   def sanitize_value(key: str, value: Any) -> Any:
       if key.lower() in SENSITIVE_FIELDS or key.lower().endswith(("_password", "_token", "_secret")):
           return REDACTED  # 100% mask, pas de teaser 4 chars
       return value
   ```

### 5.3 Priorité 3 — Cardinalité metrics et orphelines (P1)

5. **F87** : dans `MetricsMiddleware` (à confirmer module 04), normaliser le `path` via `request.scope["route"].path_format` au lieu de `request.url.path`. Tests : 1000 GET `/api/v1/products/{id}` doivent créer 1 métrique, pas 1000.

6. **F88, F89** : auditer chaque métrique :
   - Si pas de INC trouvé → supprimer.
   - Sinon documenter le call-site et le couvrir d'un test.

7. **F98** : supprimer `cache_hit_rate` Gauge. Le calcul se fait côté Prometheus (`rate(cache_hits_total) / (rate(cache_hits_total) + rate(cache_misses_total))`). Mettre à jour les dashboards Grafana.

### 5.4 Priorité 4 — Rate limiting robustesse (P1)

8. **F90, F103** : extraire `get_scope_config` dans `app/constants/limits.py` ou `tenant_settings` :
   ```python
   # tenant_settings table (DB) :
   # tenant_id, scope, limit, window_seconds — overrides par tenant
   # fallback : Limits.RATE_LIMIT_DEFAULTS (constantes)
   ```

9. **F91** : `determine_rate_limit_scope` doit prendre le `app_code` du tenant lui-même (depuis `request.state.tenant.app_code`) au lieu de matcher sur l'URL. Marveline et Splendid ont `app_code='marveline'` mais des tenant_id différents → la combinaison `(app_code, tenant_id)` permet un quota par-tenant correct.

10. **F94** : remplacer INCR + EXPIRE par un Lua atomique :
    ```lua
    -- rate_limit_check.lua
    local count = redis.call("INCR", KEYS[1])
    if count == 1 then redis.call("EXPIRE", KEYS[1], ARGV[1]) end
    return count
    ```
    Charger via `RedisSecClient.load_lua_scripts` (cf module 01) — éviter la race fenêtre.

11. **F104** (P2 → P1 si scaling élevé) : remplacer le compteur fixed-window par un sliding log (Redis sorted set + ZADD/ZREMRANGEBYSCORE) ou token bucket (Lua). Pour un quota anti-brute-force `LOGIN: 5 req/60s`, l'effet bordure est exploitable.

### 5.5 Priorité 5 — Health check production (P2)

12. **F100, F101** : étendre `health.py` :
    - `check_celery(broker_url)` : ping broker, count workers actifs.
    - `check_smtp(host, port)` : connexion socket.
    - `check_wireguard(service_url)` : HTTP GET `/health` du service WG.
    - Timeout 1s sur tous les checks (`asyncio.wait_for`).
    - `statement_timeout='1s'` pour `check_postgres` (via `SET LOCAL`).

### 5.6 Priorité 6 — Cosmétique (P3)

13. **F92** : dans `rate_limit_utils`, cacher les claims dans `request.state.jwt_claims` au premier décodage :
    ```python
    def _decode_jwt_claims(request: Request) -> Optional[dict]:
        if hasattr(request.state, "jwt_claims"):
            return request.state.jwt_claims
        # ... décode
        request.state.jwt_claims = claims
        return claims
    ```

14. **F107** : résoudre le cycle d'imports `rate_limit_utils ↔ deps` via le découpage `core/auth/` recommandé en module 01.

15. **F95** : exposer le log level third-party via env vars (`UVICORN_ACCESS_LOG_LEVEL=INFO` en dev, WARNING en prod par défaut).

16. **F96** : harmoniser le format `request_id` entre JSON et Console (full ou truncated, pas mix).

17. **F97** : sortir la doc Prometheus de `metrics.py` vers `docs/observabilite.md`.

### 5.7 Tests à écrire avant refonte

- **F83** : vérifier que `http_requests_total{app_code="marveline",method="GET",path="/api/v1/products"}` et `http_requests_total{app_code="lesplendid",...}` sont distincts.
- **F84** : un user tenant 1 fait 200 req → quota épuisé. Un user tenant 5 fait 1 req → autorisé (quota indépendant).
- **F87** : 1000 GET `/api/v1/products/{1..1000}` → 1 série Prometheus, pas 1000.
- **F88** : `db_queries_total{operation="select"}` doit être > 0 après 10 GET.
- **F94** : sous concurrent INCR (10 workers, même clé), aucun compteur ne survit sans TTL.

---

## 6. Verdict module 03

| Aspect | État |
|---|---|
| Convention 4 couches | N/A (infrastructure transverse) |
| Multi-tenant observabilité | **Cassée** : aucune métrique n'a de label tenant (F83), rate limit non-tenant-aware (F84) |
| Cardinalité metrics | **Risque explosion** : `path` non normalisé (F87) — à confirmer module 04 |
| Métriques orphelines | `db_queries_total`, `db_query_duration_seconds`, `reservations_total`, `invoices_total` probablement non-incrémentées (F88, F89) |
| Logging | Sanitization secrets incomplète (F85, F86) — fuites potentielles via log fields métiers |
| Rate limiting | Fenêtre glissante approximative (F104), race INCR/EXPIRE (F94), limites hardcodées Marveline (F90, F110), pas de tenant scoping (F84) |
| Health checks | Incomplets (Celery/WG/SMTP absents — F100), pas de timeout (F101) |
| Couplage | 1 cycle évité par duplication (F107), 1 décodage JWT non-cacheable (F92) |
| Multi-brand | F83, F84, F89, F90, F91, F110 — toutes les couches observabilité sont brand-blind |
| Dette | 28 nouvelles frictions : 2 P0, 12 P1, 13 P2, 3 P3 |

**Conclusion** : la couche observabilité est techniquement correcte (Prometheus, JSON logs, FAIL-CLOSED rate limit, ContextVars logging) mais **complètement aveugle au multi-tenant**. Pour un SaaS avec 4+ apps × N tenants, c'est rédhibitoire — pas de SLO par tenant, pas de facturation à l'usage, pas de détection d'anomalie par client. Les 2 P0 (F83 metrics tenant label, F84 rate limit tenant key) sont des prérequis avant tout déploiement multi-tenant en production.

→ Module suivant : `04-middleware.md` (`app/middleware/*` — app_enforcement, audit, cors, degraded, exception_handler, request_context, security, timing, metrics).
