# Sprint B6.S6 — Observability mTLS + OpenTelemetry + cardinality whitelist

> **STATUT** : ⏳ À démarrer après B6.S5
> **DURÉE MAX** : 2 semaines
> **OWNER** : Ops
> **BLOQUE** : B6.S7 (RabbitMQ migration)
> **DÉPEND DE** : B6.S2 (audit), B6.S5 (httpx async)
> **OBJECTIF** : Sécuriser `/metrics` via mTLS pur (Q40=B) — service mesh ou nginx-ingress + cert-manager rotation. Sanitize status page (`/health/status`). Health 100% async + yield test (F1125). Cardinality whitelist Prometheus (`'other'` fallback) cohérent F1126 Sprint 1. Label `tenant_id` cap top 100. OpenTelemetry tracing FastAPI+SQLA+Redis+Celery+httpx (Q37=A). Cache hit rate Gauge multi-process (F1139).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B6.S6.T1** | Q40=B — `/metrics` mTLS pur via service mesh ou nginx-ingress + cert-manager | P0 | 3 j | T2 |
| **B6.S6.T2** | F1123 — Status page sanitize (`/health/status` EMERGENCY_BYPASS → "degraded") | P0 | 0.5 j | aucun |
| **B6.S6.T3** | F1125 — Health 100% async + yield test (`await asyncio.sleep(0)`) | P0 | 0.5 j | aucun |
| **B6.S6.T4** | F1126 cont. — Cardinality whitelist `'other'` consolidation + invariants CI | P0 | 0.5 j | aucun |
| **B6.S6.T5** | F83/F84/F1128/F1131 — Labels `app_code` + `tenant_id` cap top 100 sur métriques HTTP/rate-limit | P1 | 1 j | aucun |
| **B6.S6.T6** | Q37=A — OpenTelemetry tracing instrumentation (FastAPI+SQLA+Redis+Celery+httpx) | P0 | 2 j | aucun |
| **B6.S6.T7** | F1139 — `cache_hit_rate` Gauge multi-process safe | P1 | 0.5 j | aucun |
| **B6.S6.T8** | TR-97 — `db_queries_total` / `redis_commands_total` adapter OTel→Prometheus | P1 | 0.5 j | T6 |

**Total effort** : 8.5 jours-homme.

---

# Story B6.S6.T1 — `/metrics` mTLS pur (Q40=B)

## Contexte

**Décision** : Q40=B — mTLS pur sur `/metrics`
**Sévérité** : P0 — `/metrics` actuellement public sans auth = reconnaissance attaquant + business data leak
**Code source** : `app/api/v1/endpoints/metrics.py`, infra K8s/Docker

### Description

Cible :
- Si infra K8s : service mesh Istio/Linkerd + cert-manager
- Si infra Docker : nginx-ingress avec mTLS
- Prometheus scraper avec client cert
- Validation côté serveur : SPIFFE ID dans cert

## Solution

### nginx-ingress mTLS (option Docker prod)

```nginx
# infra/nginx/metrics.conf
server {
    listen 443 ssl;
    server_name metrics.devup.fr;
    
    ssl_certificate /etc/letsencrypt/live/metrics.devup.fr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/metrics.devup.fr/privkey.pem;
    
    # mTLS : require client cert
    ssl_client_certificate /etc/nginx/client_ca.pem;
    ssl_verify_client on;
    
    location /metrics {
        # Verify SPIFFE ID
        if ($ssl_client_s_dn !~ "^.*spiffe://devup/prometheus-scraper.*$") {
            return 401;
        }
        proxy_pass http://app:8000/metrics;
        proxy_set_header X-Client-Cert-DN $ssl_client_s_dn;
    }
}
```

### Service mesh K8s (option future)

```yaml
# istio/peer-authentication.yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: metrics-mtls
spec:
  selector:
    matchLabels:
      app: devup-api
  mtls:
    mode: STRICT
```

### Application-side fallback check

```python
# app/api/v1/endpoints/metrics.py
@router.get("/metrics")
async def prometheus_metrics(request: Request):
    client_cert_dn = request.headers.get("X-Client-Cert-DN", "")
    if not client_cert_dn.startswith("spiffe://devup/prometheus-scraper"):
        raise HTTPException(401, "mTLS client cert required")
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

### Cert rotation (cert-manager)

```yaml
# infra/cert-manager/prometheus-cert.yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: prometheus-scraper
spec:
  secretName: prometheus-scraper-tls
  duration: 720h  # 30 days
  renewBefore: 168h  # 7 days
  subject:
    organizations: [DEVUP]
  uris:
    - spiffe://devup/prometheus-scraper
  issuerRef:
    name: ca-issuer
    kind: ClusterIssuer
```

## DoD

- [ ] mTLS configuré (nginx-ingress ou service mesh)
- [ ] SPIFFE ID validé côté serveur
- [ ] cert-manager rotation 30j
- [ ] Test : scrape sans cert → 401
- [ ] Test : scrape avec cert valide → 200

---

# Story B6.S6.T2 — Status page sanitize (F1123)

## Contexte

**Friction** : F1123
**Sévérité** : P0 — `/health/status` retourne `EMERGENCY_BYPASS`, `READ_ONLY`, etc. → info disclosure utile à attaquant

### Description

Cible : statut public sanitize (`operational | degraded`) ; détail interne uniquement avec scope `admin:health_detail`.

## Solution

```python
# app/api/v1/endpoints/health.py
@router.get("/health/status")
async def public_status(request: Request, has_admin: bool = Depends(check_scope(Scope.ADMIN_HEALTH_DETAIL, optional=True))):
    internal = await health_service.get_full_status()  # READ_ONLY, AUTH_DOWN, EMERGENCY_BYPASS, etc.
    if has_admin:
        return internal  # détaillé
    # Sanitize public
    if internal.degraded_mode in ("READ_ONLY", "AUTH_DOWN", "EMERGENCY_BYPASS"):
        return {"status": "degraded", "message": "Service partiellement disponible"}
    return {"status": "operational"}
```

## DoD

- [ ] Public retourne `operational | degraded` seulement
- [ ] Admin retourne détail
- [ ] Test : sans scope → "degraded" ; avec scope → "EMERGENCY_BYPASS"

---

# Story B6.S6.T3 — Health 100% async + yield test (F1125)

## Contexte

**Friction** : F1125
**Sévérité** : P0 — liveness probe sync ne détecte pas event loop bloqué → K8s ne redémarre jamais

### Description

Cible : `/health/live` async + `await asyncio.sleep(0)` (yield test) pour détecter event loop bloqué.

## Solution

```python
# app/api/v1/endpoints/health.py
@router.get("/health/live")
async def liveness():
    # Yield test : si event loop bloqué, asyncio.sleep(0) timeout
    await asyncio.wait_for(asyncio.sleep(0), timeout=0.5)
    return {"status": "alive"}
```

## DoD

- [ ] `/health/live` async + yield test
- [ ] Test : event loop bloqué simulé → timeout → K8s redémarre

---

# Story B6.S6.T4 — Cardinality whitelist consolidation (F1126)

## Contexte

Sprint 1 a livré le fix tactique (`_normalize_path` retourne `'other'` en fallback). Cette story consolide :
1. Whitelist explicite `KNOWN_PATH_PATTERNS`
2. CI invariant `tools/check_metrics_path_patterns.py`

## Solution

```python
# app/middleware/metrics.py
KNOWN_PATH_PATTERNS = [
    re.compile(r"^/api/v1/customers(/\{?\w+\}?)?(/\w+)?$"),
    re.compile(r"^/api/v1/products(/\{?\w+\}?)?(/\w+)?$"),
    # ... ~50 patterns ciblés
]

def _normalize_path(path: str) -> str:
    for pattern in KNOWN_PATH_PATTERNS:
        if pattern.match(path):
            return pattern.pattern
    return "other"  # fallback anti-cardinality
```

## DoD

- [ ] Whitelist explicite ~50 patterns
- [ ] CI invariant
- [ ] Test : path random → "other"

---

# Story B6.S6.T5 — Labels `app_code` + `tenant_id` cap top 100 (F83/F84/F1128/F1131)

## Solution

```python
# app/middleware/metrics.py
TOP_TENANTS_CACHE_TTL = 300  # 5 min

http_requests = Counter(
    "http_requests_total",
    "HTTP requests",
    ["method", "path", "status", "tenant_id_bucket", "app_code"],
)

async def _bucket_tenant_id(tenant_id: int) -> str:
    """Cap top 100 ; autres → 'long_tail'."""
    top_100 = await redis.smembers("metrics:top_tenants_100")
    if str(tenant_id).encode() in top_100:
        return str(tenant_id)
    return "long_tail"
```

## DoD

- [ ] Labels `app_code` + `tenant_id` cap top 100
- [ ] Test cardinality < 10000 séries
- [ ] Refresh top_tenants daily

---

# Story B6.S6.T6 — OpenTelemetry tracing (Q37=A)

## Solution

```python
# app/core/observability.py
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def setup_tracing(app):
    provider = TracerProvider(resource=Resource.create({"service.name": "devup-api"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTLP_ENDPOINT)))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    RedisInstrumentor().instrument()
    CeleryInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
```

### Trace propagation Celery

```python
# Tasks reçoivent trace_id via header
@shared_task(bind=True)
def my_task(self, ..., traceparent: str | None = None):
    if traceparent:
        # Continue trace from caller
        carrier = {"traceparent": traceparent}
        ctx = TraceContextTextMapPropagator().extract(carrier=carrier)
```

## DoD

- [ ] Instrumentation auto 5 libs
- [ ] OTLP export vers Tempo/Datadog
- [ ] Trace_id propagé api → Celery → WG
- [ ] Test : trace span end-to-end visible

---

# Story B6.S6.T7 — `cache_hit_rate` Gauge multi-process (F1139)

## Solution

```python
# app/middleware/metrics.py
from prometheus_client import multiprocess, Gauge

# Multi-process safe
cache_hit_rate = Gauge(
    "cache_hit_rate",
    "Cache hit ratio",
    ["cache_name"],
    multiprocess_mode="livesum",
)
```

## DoD

- [ ] Gauge multi-process safe
- [ ] Test : 4 workers → metric agrégée correcte

---

# Story B6.S6.T8 — Adapter OTel → Prometheus pour `db_queries_total` / `redis_commands_total` (TR-97)

## Contexte

**Friction** : TR-97 — Métriques `db_queries_total{operation}` et `redis_commands_total{command}` déclarées dans `app/middleware/metrics.py` mais **jamais incrémentées** au runtime (F1127, F1141). Théâtre observabilité : dashboards Grafana vides.
**Sévérité** : P1 — Pas un blocker prod mais signal faux (UX ops trompeuse) et coût Prometheus pour rien.
**Décision architecture-cible §6.6** : Ne PAS dropper les Counters → les **brancher** sur les hooks OTel mis en place par T6, via un adapter custom qui réémet les events en métriques Prometheus.

> **Why** : Garde la rétro-compat des dashboards existants pendant que OTel devient source-of-truth pour le tracing.
> **How to apply** : Adapter idempotent posé une seule fois au boot après `setup_tracing(app)` (T6). Pas de refactor du code applicatif (pas d'`inc()` dispersés dans repos/services).

## Solution

```python
# app/core/observability_metrics_bridge.py
"""
Pont OTel → Prometheus pour réémettre db_queries_total et redis_commands_total
à partir des spans auto-instrumentés (SQLAlchemyInstrumentor, RedisInstrumentor).
"""
from opentelemetry import trace
from opentelemetry.sdk.trace import SpanProcessor, ReadableSpan
from app.middleware.metrics import db_queries_total, redis_commands_total


class _MetricsBridgeSpanProcessor(SpanProcessor):
    """
    SpanProcessor read-only qui INC les counters Prometheus à la fin de chaque span
    SQLAlchemy / Redis. Ne touche pas au span lui-même.
    """

    _SQLA_OPERATIONS = {"SELECT", "INSERT", "UPDATE", "DELETE"}

    def on_start(self, span, parent_context=None):
        return  # no-op, on lit le span à la fin

    def on_end(self, span: ReadableSpan):
        instr = span.instrumentation_scope.name if span.instrumentation_scope else ""

        if instr == "opentelemetry.instrumentation.sqlalchemy":
            stmt = (span.attributes or {}).get("db.statement", "")
            op = stmt.split(" ", 1)[0].upper() if stmt else "OTHER"
            if op not in self._SQLA_OPERATIONS:
                op = "OTHER"
            db_queries_total.labels(operation=op.lower()).inc()
            return

        if instr == "opentelemetry.instrumentation.redis":
            cmd = (span.attributes or {}).get("db.statement", "").split(" ", 1)[0].upper()
            if not cmd:
                cmd = "OTHER"
            redis_commands_total.labels(command=cmd).inc()
            return

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True


def install_metrics_bridge():
    """Appelé APRÈS setup_tracing(app) dans app/main.py."""
    provider = trace.get_tracer_provider()
    provider.add_span_processor(_MetricsBridgeSpanProcessor())
```

```python
# app/main.py — ordre critique
setup_tracing(app)            # T6 — installe OTLP exporter + 5 instrumentors
install_metrics_bridge()      # T8 — branche les Counters Prometheus existants
```

### Cardinality cap

- `db_queries_total` : 5 valeurs `operation` (`select`/`insert`/`update`/`delete`/`other`) — pas de risque cardinality.
- `redis_commands_total` : whitelist top 20 commandes (`GET`/`SET`/`DEL`/`HGET`/`HSET`/`SADD`/`SREM`/`SMEMBERS`/`EXPIRE`/`INCR`/`DECR`/`EXISTS`/`SCAN`/`PUBLISH`/`SUBSCRIBE`/`EVAL`/`PERSIST`/`TTL`/`KEYS`/`OTHER`). Tout autre → `OTHER` (cohérent F1126 §T4).

## Tests

```python
# tests/observability/test_metrics_bridge.py
async def test_select_increments_db_queries_total():
    before = REGISTRY.get_sample_value("db_queries_total", {"operation": "select"}) or 0
    await db.execute(select(User).limit(1))
    after = REGISTRY.get_sample_value("db_queries_total", {"operation": "select"}) or 0
    assert after == before + 1


async def test_redis_get_increments_redis_commands_total():
    before = REGISTRY.get_sample_value("redis_commands_total", {"command": "GET"}) or 0
    await redis.get("foo")
    after = REGISTRY.get_sample_value("redis_commands_total", {"command": "GET"}) or 0
    assert after == before + 1


async def test_unknown_redis_command_falls_back_to_other():
    before = REGISTRY.get_sample_value("redis_commands_total", {"command": "OTHER"}) or 0
    await redis.execute_command("CLUSTER", "INFO")
    after = REGISTRY.get_sample_value("redis_commands_total", {"command": "OTHER"}) or 0
    assert after == before + 1
```

## DoD

- [ ] `app/core/observability_metrics_bridge.py` créé avec `_MetricsBridgeSpanProcessor`
- [ ] `install_metrics_bridge()` appelé dans `app/main.py` APRÈS `setup_tracing(app)`
- [ ] Whitelist Redis 20 commandes + fallback `OTHER`
- [ ] 3 tests pytest verts (SELECT inc, GET inc, fallback OTHER)
- [ ] Dashboard Grafana `db_queries_total` non vide après smoke test (preuve à coller dans la PR)

---

## Critères de succès Sprint B6.S6

- [ ] **Q40=B livré** : `/metrics` mTLS pur + SPIFFE ID
- [ ] **F1123 résolu** : status page sanitize
- [ ] **F1125 résolu** : health async + yield test
- [ ] **F1126 consolidé** : cardinality whitelist
- [ ] Labels `app_code` + `tenant_id` cap top 100
- [ ] **Q37=A livré** : OpenTelemetry tracing 5 libs
- [ ] **F1139 résolu** : cache_hit_rate multi-process
- [ ] **TR-97 résolu** : `db_queries_total` / `redis_commands_total` non vides via OTel→Prometheus bridge (T8)

---

**Fin du document — 16-sprint-B6.S6.md**
