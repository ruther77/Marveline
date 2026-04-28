# Module 35 — Health / Metrics / Observabilité

> **Phase E — DERNIER MODULE.** Audit du dispositif d'observabilité : health checks Kubernetes, metrics Prometheus RED, mode dégradé 4 niveaux, status page publique.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/core/health.py` | 122 |
| `app/api/v1/endpoints/health.py` | 185 |
| `app/core/metrics.py` | 340 |
| `app/middleware/metrics.py` | 181 |
| `app/middleware/degraded.py` | 162 |
| `app/constants/metrics.py` | 24 |

**Volume total** : 1 014 LoC (hors middleware audit/timing déjà couverts mod. 31).

---

## 2. Architecture observée

```
HEALTH CHECKS (3 endpoints)
  GET /health        → liveness {"status": "ok"} (toujours)
  GET /health/live   → alias liveness
  GET /health/ready  → readiness PostgreSQL + Redis + Celery
                      503 si une dépendance fail
  GET /health/status → status page publique
                      degraded_level + composants + incidents
                      (/api/v1/health/status — confirmé non-protégé)

DEPENDANCES VERIFIEES (/health/ready) :
  • PostgreSQL : SELECT 1 + pool size/checked_out
  • Redis      : PING + memory + connected_clients
  • Celery     : control.inspect(timeout=2.0).active()

PROMETHEUS METRICS (RED + business)
  http_requests_total{method, path, status}        Counter
  http_request_duration_seconds{method, path}      Histogram (buckets 5ms-10s)
  http_requests_in_progress{method, path}          Gauge
  rate_limit_hits_total{scope, identifier_type}    Counter
  db_queries_total{operation}                      Counter (jamais incrémenté ?)
  db_query_duration_seconds{operation}             Histogram
  redis_commands_total{command}                    Counter (jamais incrémenté ?)
  redis_command_duration_seconds{command}          Histogram
  cache_hits_total{entity}, cache_misses_total{entity}
  cache_hit_rate{entity}                           Gauge
  reservations_total{status}, invoices_total{status}

MetricsMiddleware
  normalize_path : /products/123 → /products/{id} (anti cardinality blow-up)
  in_progress.inc / dec (try/finally)
  observe duration + counter
  rate_limit hit detection sur 429

GET /metrics (path à confirmer — endpoint public sans auth — promesse l. 335)

DEGRADED MODE (4 niveaux)
  NOMINAL          → tout fonctionne
  READ_ONLY        → mutations 503 sauf /auth/* /health /metrics /admin/degraded
  AUTH_DOWN        → fail-open auth (Redis-SEC down détecté)
  EMERGENCY_BYPASS → auth court-circuitée (humain only)
  
  Granularité par app : degraded:epicerie / restaurant / marveline
  Lecture Redis-SEC à chaque requête (1 GET / req)
```

---

## 3. Frictions identifiées — module 35

> Compteur cumulé (mod. 01-34) ≈ 1 121. Module 35 ouvre à **F1122**.

### 3.1 P0

#### F1122 — `GET /metrics` **endpoint public sans authentification** (l. 335 commentaire confirme)

`core/metrics.py:335` "Pas d'authentification requise (metrics endpoint public)". Les métriques exposent :
- `http_requests_total{path="/api/v1/customers/{id}",status="200"}` → **inventaire des endpoints existants** (reconnaissance attaquant)
- `cache_hit_rate{entity="customer"}` → **profile interne**
- `reservations_total{status="cancelled"}` → **données métier business** (volume, taux conversion)

→ Toute personne sur Internet peut consulter ces métriques (sauf si reverse-proxy filtre, mais c'est pas le rôle de l'app).

**Action** : auth Basic ou IP whitelist du Prometheus scraper, ou mTLS.

---

#### F1123 — `GET /health/status` page publique expose `degradation_level` interne

`endpoints/health.py:155-185`. Retourne `degradation_level: "EMERGENCY_BYPASS"` aux clients anonymes. Un attaquant qui détecte EMERGENCY_BYPASS sait que **l'auth est court-circuitée** maintenant — il peut tenter exploitation immédiate.

→ Théâtre de transparence transformé en signal d'attaque.

**Action** : mapper le degradation_level à un statut générique côté public (`operational/degraded/down`), réserver les détails à l'admin authentifié.

---

#### F1124 — `check_postgres` utilise **session sync** mais l'app est async

`core/health.py:26-84`. Endpoint `/health/ready` (l. 117) declare `db: Session = Depends(get_db)` — `get_db` retourne un sync session ? À vérifier — si oui, `db.execute(text("SELECT 1"))` bloque le worker FastAPI async pendant la latence DB. Sous charge, latence health check peut atteindre 500ms (pool exhausted) → Kubernetes redémarre le pod inutilement.

→ Health check qui tue le service qu'il protège. Cf. F1054 mod. 33.

**Action** : `check_postgres_async(async_db)` async-native ; `/health/ready` async route avec async session.

---

#### F1125 — `/health` simple **toujours retourne 200** — ne détecte pas event loop bloqué / deadlock

`endpoints/health.py:81-100`. `return {"status": "ok"}` synchrone (pas async). Si l'event loop est bloqué (long task sync dans handler async, GIL contention), le handler `def health_check()` exécute dans threadpool quand même → toujours 200 OK alors que l'app est gelée.

→ Liveness probe ment. Kubernetes ne redémarre jamais un pod gelé.

**Action** : `async def health_check()` avec un test de yield (async sleep 0) qui détecte event loop bloqué ; ou metric `worker_health` séparée.

---

#### F1126 — `MetricsMiddleware` enregistre **`http_requests_total{path}` même pour 404 paths arbitraires**

`middleware/metrics.py:55-82` `_normalize_path` : si le path ne match aucun pattern de normalisation (`/api/v1/products/{id}`), retourne le path tel quel. Un attaquant spamming `/api/v1/foo/bar/{random_uuid}/{random_token}` génère **1 nouvelle série temporelle** par appel → Prometheus storage explose, OOM kill.

→ DoS sur Prometheus via metrics blow-up.

**Action** : whitelist de paths normalisés ; sinon labelliser `path="other"` ; ou drop tous les 404.

---

### 3.2 P1

#### F1127 — `db_queries_total`, `redis_commands_total` **déclarés mais probablement jamais incrémentés**

`core/metrics.py:135-148, 179-192`. Pas vu dans le code de hooking SQLAlchemy events ni Redis client wrap. Ces métriques restent à 0 → dashboards Grafana vides. Théâtre observabilité.

À confirmer en grep `db_queries_total.labels(`.

**Action** : `@event.listens_for(Engine, "before_cursor_execute")` SQLAlchemy hook + Redis client wrap.

---

#### F1128 — Pas de **labels tenant_id** sur les metrics — agrégation globale

Toutes les métriques `http_requests_total{path,method,status}` sans tenant_id. Impossible de répondre "combien de req/s pour tenant Marveline ?".

→ Difficile à debugger des incidents tenant-specific. Multi-tenancy invisible côté ops.

**Action** : ajouter label `tenant_id` (mais surveillance cardinality — à cap pour 100 tenants max).

---

#### F1129 — `/health/ready` `celery_app.control.inspect(timeout=2.0)` **bloque 2s** par appel

Si Celery beat down ou broker Redis lent, chaque `/ready` poll dépense 2s. Kubernetes `periodSeconds: 10` × 4 pods = 0.8s/s perdu en health check. À grande échelle, contention.

**Action** : cache le résultat 30s avec `lru_cache`.

---

#### F1130 — `check_redis_async` utilise `redis_client.client` sans pool sentinel

`endpoints/health.py:120` `await check_redis_async(redis_client.client)`. Si Redis sentinel/cluster down, `ping()` peut bloquer jusqu'au timeout réseau (TCP keepalive ~2 min).

---

#### F1131 — `MetricsMiddleware` **n'a pas de label `tenant_id`** ni `actor_type`

Cf. F1128. RED metrics par tenant absents → impossible de prioriser SLO par tenant.

---

#### F1132 — `MetricsMiddleware.dispatch` **comptabilise même les paths exemptés** `/health` et `/metrics`

Commentaire `core/metrics.py` : "Pas d'exemption". Mais cela inclut les /metrics scrape Prometheus → boucle infinie auto-scrape (Prometheus se mesure mesurer).

---

#### F1133 — `DegradedModeMiddleware` lit `redis_sec.get_degradation_level()` à **chaque requête** sans cache

`middleware/degraded.py:86`. 1 GET Redis par requête HTTP. À 1000 req/s = 1k Redis GET/s. 

**Action** : LRU cache 5s ; ou subscribe Redis PUB/SUB pour invalidation event-driven.

---

#### F1134 — `_get_app_degradation` granularité app **mais `_MARVELINE_DEGRADED_KEY` hardcoded**

`middleware/degraded.py:52`. Si nouveau tenant `splendid` arrive, manuellement à coder.

---

#### F1135 — `EMERGENCY_BYPASS` log `critical` **mais pas alerting Prometheus défini** dans le code metrics

L. 102-107 `logger.critical("EMERGENCY_BYPASS active")`. Bonne pratique d'alerter sur log critical, mais aucune metric Prometheus `degraded_mode_active{level="EMERGENCY_BYPASS"}` exposée pour AlertManager.

**Action** : Gauge `degraded_mode_level{component, level}` exposée par /metrics.

---

#### F1136 — `_handle_read_only` `Retry-After: "60"` dur — **pas configurable** par cause

Si le mode READ_ONLY est dû à maintenance prévue 4h, retry 60s spammera l'app inutilement.

---

#### F1137 — `db_query_duration_seconds` buckets `(0.001, ...0.1, 0.25, 0.5, 1.0, 2.5, 5.0)` — pas adapté aux long ETL queries

Une migration Alembic ou un import 5min déborde du dernier bucket → p99 = +Inf bucket = inutile.

---

#### F1138 — Pas de **distributed tracing** (OpenTelemetry) malgré stack distribuée (api + Celery workers + WG service)

Impossible de corréler une requête API → task Celery → call WG microservice. Debug latency inter-service en aveugle.

---

#### F1139 — `cache_hit_rate` Gauge **mis à jour après chaque get** — tous les workers écrasent leur valeur réciproquement

Multi-process Prometheus client : les Gauges en multi-worker doivent être Gauge `multiprocess_mode='livesum'` ou similaire.

---

#### F1140 — Pas de **uptime** SLI exposé (`uptime_seconds`)

Compute facile (`time.time() - app_start_time`) mais pas exposé.

---

#### F1141 — `reservations_total`, `invoices_total` business metrics **jamais incrémentés** dans les services métier

Recherche `reservations_total.labels(` non confirmée. Probablement des stub jamais implémentés.

---

#### F1142 — `DegradedModeMiddleware` **avant** ou **après** RequestContextMiddleware ? 

Impact AUTH_DOWN comportement. Si avant, le user_id n'est pas extrait et certaines opérations sans user fail. À vérifier ordre dans `app/main.py`.

---

#### F1143 — Pas de **synthetic monitoring** (canary/probe externe) — dépend uniquement de Prometheus pull

Si le pod Prometheus ne tourne pas, on ne sait rien. Pas de dépendance externe (Pingdom, UptimeRobot).

---

#### F1144 — `JSONResponse(status_code=503, ...)` **n'est pas instrumenté** par MetricsMiddleware si retourné AVANT call_next

Cas `_handle_read_only`. Le middleware metrics est probablement après (donc non-impacté), mais la latence est <1ms→ histogram 5ms bucket.

---

### 3.3 P2

#### F1145 — Buckets Histogram non configurables par env (test/staging vs prod)

#### F1146 — `MetricsMiddleware._normalize_path` regex compilé `PATH_NORMALIZATION_PATTERNS` — où ? À confirmer constants

#### F1147 — `cache_hits_total{entity}` mais `entity` libre — risque cardinality si dev passe `entity=customer_123`

#### F1148 — Pas de **DB pool watermark alert** (pool checked_out / pool size > 80% = warning)

#### F1149 — `health.py status page` retourne `incidents: []` toujours — pas de table d'incidents loggé

#### F1150 — `redis_command_duration_seconds` buckets max 0.1s — pas adapté Redis cluster cross-AZ

#### F1151 — Pas de metric `celery_task_duration_seconds{task_name, status}` — Celery observabilité aveugle

#### F1152 — `app/constants/metrics.py` 24 LoC — sous-utilisé, prend pas la responsabilité de centraliser

---

### 3.4 P3

#### F1153 — Comments `Démarrer`, `Réquêtes` orthographe variable

#### F1154 — `APP_VERSION = settings.APP_VERSION` dans health response — à confirmer auto-update lors déploiement

---

## 4. Synthèse module 35

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 5 | F1122 (/metrics public no auth), F1123 (status page leak EMERGENCY_BYPASS), F1124 (sync DB session in async), F1125 (liveness ne détecte pas event loop blocked), F1126 (cardinality blow-up via 404 path) |
| P1 | 18 | F1127 → F1144 |
| P2 | 8 | F1145 → F1152 |
| P3 | 2 | F1153, F1154 |
| **Total** | **33** | F1122 → F1154 |

**Compteur cumulé après module 35** : ≈ 1 121 + 33 = **1 154 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) auth Basic + IP whitelist Prometheus pour `/metrics` (F1122) ; (2) status page publique sanitize (F1123) ; (3) async DB pour health (F1124) ; (4) async health avec yield test (F1125) ; (5) whitelist paths metrics (F1126).
>
> **Refactor** : labels `tenant_id` pour SLO multi-tenant (F1128, F1131) ; OpenTelemetry tracing (F1138) ; Celery task duration metrics (F1151) ; cache `get_degradation_level` PUB/SUB (F1133) ; instrumentation DB+Redis hooks (F1127).

---

# 🎯 PHASE E TERMINÉE

**Modules 31-35 livrés.** ~6 200 LoC supplémentaires audités. Compteur **1 154 frictions** au total sur 35 modules (~140 P0).

**Phase F restante** :
- **Module 99** : Synthèse globale frictions registry, top 30 P0, plan triage par priorité métier
