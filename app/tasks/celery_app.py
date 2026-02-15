"""Configuration Celery pour les tâches asynchrones CaroCorp."""
import logging

from celery import Celery
from app.core.config import settings

logger = logging.getLogger(__name__)

# Créer l'application Celery
celery_app = Celery(
    "carocorp",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Configuration Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Paris",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
)

# Queues pour différents types de tâches
# NOTE: task_routes et autodiscover activés quand les modules existent
# celery_app.conf.task_routes = {
#     "app.tasks.reservations.*": {"queue": "reservations"},
#     "app.tasks.invoicing.*": {"queue": "invoicing"},
#     "app.tasks.notifications.*": {"queue": "notifications"},
#     "app.tasks.reports.*": {"queue": "reports"},
# }
# celery_app.autodiscover_tasks([
#     "app.tasks.reservations",
#     "app.tasks.invoicing",
#     "app.tasks.notifications",
#     "app.tasks.reports",
# ])


@celery_app.task(bind=True)
def debug_task(self):
    """Tâche de debug pour tester Celery."""
    logger.debug("Request: %r", self.request)
    return {"status": "ok", "task_id": self.request.id}
