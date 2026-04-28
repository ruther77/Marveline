# Infra — Celery & Tâches Async

## Configuration

```python
# app/tasks/celery_app.py
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "marveline",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.notifications", "app.tasks.reports", "app.tasks.cleanup"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,          # Acquitter après exécution (pas avant)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1, # Pas de prefetch pour les tâches longues
    task_routes={
        "app.tasks.reports.*": {"queue": "reports"},
        "app.tasks.notifications.*": {"queue": "notifications"},
    },
)
```

## Structure d'une Tâche

```python
# app/tasks/notifications.py
from celery import Task
from app.core.database import get_db_context
from app.services.notification import NotificationService
import logging

logger = logging.getLogger(__name__)

class BaseTask(Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "Task %s[%s] failed: %s",
            self.name, task_id, exc,
            exc_info=einfo,
        )

@celery_app.task(
    base=BaseTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 60s entre retries
    name="notifications.send_invoice",
)
def send_invoice_notification(self, tenant_id: int, invoice_id: int) -> dict:
    """Envoyer la notification de facture. Idempotente."""
    try:
        with get_db_context() as db:
            service = NotificationService(db)
            result = service.send_invoice(tenant_id, invoice_id)
            return {"success": True, "invoice_id": invoice_id}
    except Exception as exc:
        logger.warning("Retry %d/%d for invoice %d: %s",
                       self.request.retries, self.max_retries, invoice_id, exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

## Dead Letter Queue (DLQ)

```python
# Configurer la DLQ pour les tâches échouées après max_retries
celery_app.conf.update(
    task_queues={
        "default": {
            "exchange": "default",
            "routing_key": "default",
        },
        "dead_letter": {
            "exchange": "dead_letter",
            "routing_key": "dead_letter",
        },
    },
)

# Tâche DLQ : logger et alerter
@celery_app.task(queue="dead_letter")
def handle_dead_letter(task_name: str, args: list, kwargs: dict, exception: str):
    logger.critical(
        "Task permanently failed: %s args=%s kwargs=%s error=%s",
        task_name, args, kwargs, exception
    )
    # Alerter via Sentry ou Slack
    sentry_sdk.capture_message(f"DLQ: {task_name} failed permanently", level="critical")
```

## Idempotence des Tâches

```python
# Toujours rendre les tâches idempotentes — elles peuvent s'exécuter plusieurs fois
@celery_app.task(bind=True)
def process_payment(self, payment_id: int) -> dict:
    with get_db_context() as db:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()

        # Guard idempotence
        if payment.processed:
            logger.info("Payment %d already processed, skipping", payment_id)
            return {"skipped": True, "payment_id": payment_id}

        # Traiter
        payment.processed = True
        payment.processed_at = datetime.utcnow()
        db.commit()
        return {"success": True, "payment_id": payment_id}
```

## OpenTelemetry + Celery

```python
from opentelemetry.instrumentation.celery import CeleryInstrumentor

# Propager le contexte de tracing vers les workers Celery
CeleryInstrumentor().instrument()

# Dans la tâche : le span parent est automatiquement propagé
@celery_app.task
def my_task(tenant_id: int):
    with tracer.start_as_current_span("process_data") as span:
        span.set_attribute("tenant_id", tenant_id)
        # ...
```

## Beat Schedule (Tâches Périodiques)

```python
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "refresh-materialized-views": {
        "task": "app.tasks.reports.refresh_revenue_summary",
        "schedule": crontab(hour=2, minute=0),  # 2h du matin
    },
    "process-outbox": {
        "task": "app.tasks.events.process_outbox",
        "schedule": 30.0,  # toutes les 30 secondes
    },
    "cleanup-expired-sessions": {
        "task": "app.tasks.cleanup.cleanup_sessions",
        "schedule": crontab(hour=3, minute=0),
    },
}
```

## Règles

- `task_acks_late=True` : acquitter après exécution (garantie at-least-once)
- Toute tâche doit être idempotente
- `get_db_context()` TOUJOURS dans les tâches (jamais `next(get_db())`)
- Max retries = 3, délai exponentiel
- DLQ configurée pour les tâches définitivement échouées
- Pas de logique métier complexe dans les tâches → déléguer aux services
- OpenTelemetry instrumenté pour le tracing distribué
