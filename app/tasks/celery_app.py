"""Configuration Celery pour les tâches asynchrones CaroCorp."""
import logging

from celery import Celery
from celery.schedules import crontab

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
celery_app.conf.task_routes = {
    "app.tasks.reservations.*": {"queue": "reservations"},
    "app.tasks.invoicing.*": {"queue": "invoicing"},
    "app.tasks.notifications.*": {"queue": "notifications"},
    "app.tasks.monitoring.*": {"queue": "default"},
    "app.tasks.etl_tasks.*": {"queue": "etl"},
    "app.tasks.restaurant_export.*": {"queue": "exports"},
}
celery_app.autodiscover_tasks([
    "app.tasks.invoicing",
    "app.tasks.notifications",
    "app.tasks.monitoring",
    "app.tasks.access_review",
    "app.tasks.etl_tasks",
    "app.tasks.restaurant_export",
    "app.tasks.relances",
    "app.tasks.loyalty",
    "app.tasks.risk_detection",
])

# Beat schedule — tâches périodiques
celery_app.conf.beat_schedule = {
    "check-overdue-invoices-daily": {
        "task": "app.tasks.invoicing.check_overdue_invoices",
        "schedule": crontab(hour=8, minute=0),
    },
    "check-late-movements-hourly": {
        "task": "app.tasks.monitoring.check_late_movements",
        "schedule": crontab(minute=0),
    },
    "check-low-stock-daily": {
        "task": "app.tasks.monitoring.check_low_stock",
        "schedule": crontab(hour=7, minute=0),
    },
    # ── Access reviews (§S-13.3 §10-MULTI-TENANT-OPS) ──────────────────────
    "privileged-access-review-monthly": {
        "task": "app.tasks.access_review.run_privileged_access_review",
        "schedule": crontab(day_of_month=1, hour=6, minute=0),
        # 1er de chaque mois à 06:00 UTC
    },
    "tenant-admin-review-quarterly": {
        "task": "app.tasks.access_review.run_tenant_admin_review",
        "schedule": crontab(day_of_month=1, hour=6, minute=30, month_of_year="1,4,7,10"),
        # 1er janvier, avril, juillet, octobre
    },
    "recertification-review-biannual": {
        "task": "app.tasks.access_review.run_recertification_review",
        "schedule": crontab(day_of_month=1, hour=7, minute=0, month_of_year="1,7"),
        # 1er janvier + 1er juillet
    },
    "auto-suspend-uncertified-biannual": {
        "task": "app.tasks.access_review.run_auto_suspend_uncertified",
        "schedule": crontab(day_of_month=1, hour=7, minute=30, month_of_year="2,8"),
        # 1er février + 1er août (J+30 après lancement recertification)
    },
    # ── Deposits non restitues ────────────────────────────────────────────────
    "expire-overdue-devis-daily": {
        "task": "app.tasks.invoicing.expire_overdue_devis",
        "schedule": crontab(hour=7, minute=30),  # 07:30 UTC quotidien
    },
    "check-unreturned-deposits-daily": {
        "task": "app.tasks.invoicing.check_unreturned_deposits",
        "schedule": crontab(hour=9, minute=0),  # 09:00 UTC quotidien
    },
    # ── Relances automatiques ────────────────────────────────────────────────
    "execute-relances-hourly": {
        "task": "app.tasks.relances.execute_scheduled_relances",
        "schedule": crontab(minute=15),  # Toutes les heures à :15
    },
    # ── Loyalty ─────────────────────────────────────────────────────────────
    "loyalty-expire-points-daily": {
        "task": "app.tasks.loyalty.expire_points_fifo",
        "schedule": crontab(hour=3, minute=0),  # 03:00 UTC
    },
    "loyalty-evaluate-tiers-daily": {
        "task": "app.tasks.loyalty.evaluate_all_tiers",
        "schedule": crontab(hour=4, minute=0),  # 04:00 UTC
    },
    "loyalty-expiration-warnings-daily": {
        "task": "app.tasks.loyalty.send_expiration_warnings",
        "schedule": crontab(hour=9, minute=0),  # 09:00 UTC
    },
    "loyalty-birthday-rewards-daily": {
        "task": "app.tasks.loyalty.send_birthday_rewards",
        "schedule": crontab(hour=8, minute=30),  # 08:30 UTC
    },
    "loyalty-activate-flash-offers": {
        "task": "app.tasks.loyalty.activate_flash_offers",
        "schedule": crontab(minute="*/5"),  # Toutes les 5 minutes
    },
    "loyalty-deactivate-flash-offers": {
        "task": "app.tasks.loyalty.deactivate_flash_offers",
        "schedule": crontab(minute="*/5"),  # Toutes les 5 minutes
    },
    # ── Detection auto risques reservations ─────────────────────────────────
    "detect-reservation-risks-daily": {
        "task": "app.tasks.risk_detection.detect_reservation_risks_daily",
        "schedule": crontab(hour=9, minute=0),  # 09:00 UTC quotidien
    },
}


@celery_app.task(bind=True)
def debug_task(self):
    """Tâche de debug pour tester Celery."""
    logger.debug("Request: %r", self.request)
    return {"status": "ok", "task_id": self.request.id}
