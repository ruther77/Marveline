# Infra — Observabilité

## OpenTelemetry (Tracing Distribué)

```python
# app/core/telemetry.py
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor

def setup_telemetry(app):
    provider = TracerProvider()
    exporter = OTLPSpanExporter(endpoint=settings.OTLP_ENDPOINT)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument()
    RedisInstrumentor().instrument()
    CeleryInstrumentor().instrument()

tracer = trace.get_tracer(__name__)

# Utilisation dans les services
with tracer.start_as_current_span("service.operation") as span:
    span.set_attribute("tenant_id", tenant_id)
    span.set_attribute("entity_id", entity_id)
    result = do_work()
```

## Propagation de Contexte (HTTP → Celery)

```python
from opentelemetry.propagate import inject, extract
from opentelemetry import context

# Avant d'envoyer une tâche Celery
def dispatch_task_with_context(task_fn, *args, **kwargs):
    carrier = {}
    inject(carrier)  # Injecter le contexte de tracing
    kwargs["otel_context"] = carrier
    return task_fn.delay(*args, **kwargs)

# Dans la tâche Celery
@celery_app.task
def my_task(*args, otel_context=None, **kwargs):
    ctx = extract(otel_context or {})
    token = context.attach(ctx)
    try:
        with tracer.start_as_current_span("celery.my_task"):
            do_work(*args, **kwargs)
    finally:
        context.detach(token)
```

## Slow Query Detection

```python
# app/core/database.py
from sqlalchemy import event
import logging, time

SLOW_QUERY_THRESHOLD_MS = 500

@event.listens_for(engine, "before_cursor_execute")
def before_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info["query_start_time"] = time.time()

@event.listens_for(engine, "after_cursor_execute")
def after_execute(conn, cursor, statement, parameters, context, executemany):
    elapsed = (time.time() - conn.info["query_start_time"]) * 1000
    if elapsed > SLOW_QUERY_THRESHOLD_MS:
        logger.warning("SLOW_QUERY %.2fms: %s", elapsed, statement[:500])
```

## SLO / Error Budget

```python
# Définir les SLOs dans le code (vérifiés par les métriques)
SLOS = {
    "api_availability": {
        "target": 99.9,           # % uptime sur 30 jours
        "error_budget_minutes": 43.2,  # 30 * 24 * 60 * (1 - 0.999)
    },
    "api_latency_p95": {
        "target_ms": 200,         # P95 < 200ms
    },
    "api_latency_p99": {
        "target_ms": 500,         # P99 < 500ms
    },
}

# Prometheus métriques
from prometheus_client import Histogram, Counter

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint", "status_code"],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
)

ERROR_COUNTER = Counter(
    "http_errors_total",
    "Total HTTP errors",
    ["method", "endpoint", "status_code"],
)
```

## Sentry

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    integrations=[FastApiIntegration(), SqlalchemyIntegration(), CeleryIntegration()],
    traces_sample_rate=0.1,     # 10% des requêtes tracées
    profiles_sample_rate=0.01,  # 1% profilé
    environment=settings.ENVIRONMENT,
    before_send=scrub_sensitive_data,  # Anonymiser les données sensibles
)

def scrub_sensitive_data(event, hint):
    """Retirer les données PII avant envoi à Sentry"""
    if "request" in event:
        event["request"].pop("cookies", None)
        headers = event["request"].get("headers", {})
        for key in ["authorization", "x-csrf-token"]:
            headers.pop(key, None)
    return event
```

## Structured Logging

```python
import structlog

logger = structlog.get_logger()

# Configuration
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)

# Utilisation
logger.info(
    "reservation_confirmed",
    tenant_id=tenant_id,
    reservation_id=reservation_id,
    actor_id=current_user.id,
)
```

## Alertes (Règles)

```yaml
# prometheus/alerts.yaml
groups:
  - name: marveline
    rules:
      - alert: HighErrorRate
        expr: rate(http_errors_total[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Error rate > 1%"

      - alert: SlowQueries
        expr: rate(slow_queries_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning

      - alert: CeleryQueueBacklog
        expr: celery_queue_length > 1000
        for: 10m
        labels:
          severity: warning
```

## Règles

- Tous les spans tracés → OTLP exporter
- Slow queries > 500ms → WARNING log + metric
- Sentry : `before_send` pour scrubber les PII
- Logs : JSON structuré, pas de logs plats
- Pas de données sensibles dans les traces/logs (RGPD)
- SLO définis en code et monitorés en continu
