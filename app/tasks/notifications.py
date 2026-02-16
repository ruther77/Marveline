"""Celery tasks for async email notifications."""
import logging
from datetime import date

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True, queue="notifications", max_retries=3, default_retry_delay=60
)
def send_reservation_confirmed_email(
    self,
    email: str,
    customer_name: str,
    reference: str,
    event_date_iso: str,
    delivery_date_iso: str,
    return_date_iso: str,
    event_location: str,
    total_cents: int,
    deposit_cents: int,
):
    """Send reservation confirmation email (async)."""
    from app.services.notification import notification_service

    try:
        notification_service.send_reservation_confirmed(
            email=email,
            customer_name=customer_name,
            reference=reference,
            event_date=date.fromisoformat(event_date_iso),
            delivery_date=date.fromisoformat(delivery_date_iso),
            return_date=date.fromisoformat(return_date_iso),
            event_location=event_location,
            total_cents=total_cents,
            deposit_cents=deposit_cents,
        )
    except Exception as exc:
        logger.exception("Failed to send reservation email to %s", email)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True, queue="notifications", max_retries=3, default_retry_delay=60
)
def send_invoice_created_email(
    self,
    email: str,
    customer_name: str,
    invoice_number: str,
    reservation_reference: str,
    total_cents: int,
    due_date_iso: str,
    issue_date_iso: str,
):
    """Send invoice created notification email (async)."""
    from app.services.notification import notification_service

    try:
        notification_service.send_invoice_created(
            email=email,
            customer_name=customer_name,
            invoice_number=invoice_number,
            reservation_reference=reservation_reference,
            total_cents=total_cents,
            due_date=date.fromisoformat(due_date_iso),
            issue_date=date.fromisoformat(issue_date_iso),
        )
    except Exception as exc:
        logger.exception("Failed to send invoice email to %s", email)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True, queue="notifications", max_retries=3, default_retry_delay=60
)
def send_delivery_completed_email(
    self,
    email: str,
    customer_name: str,
    reservation_reference: str,
    delivery_address: str,
    delivery_date_iso: str,
):
    """Send delivery completed notification email (async)."""
    from app.services.notification import notification_service

    try:
        notification_service.send_delivery_completed(
            email=email,
            customer_name=customer_name,
            reservation_reference=reservation_reference,
            delivery_address=delivery_address,
            delivery_date=date.fromisoformat(delivery_date_iso),
        )
    except Exception as exc:
        logger.exception("Failed to send delivery email to %s", email)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True, queue="notifications", max_retries=3, default_retry_delay=60
)
def send_return_completed_email(
    self,
    email: str,
    customer_name: str,
    reservation_reference: str,
    return_date_iso: str,
):
    """Send return completed notification email (async)."""
    from app.services.notification import notification_service

    try:
        notification_service.send_return_completed(
            email=email,
            customer_name=customer_name,
            reservation_reference=reservation_reference,
            return_date=date.fromisoformat(return_date_iso),
        )
    except Exception as exc:
        logger.exception("Failed to send return email to %s", email)
        raise self.retry(exc=exc)
