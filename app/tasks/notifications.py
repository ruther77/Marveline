"""Celery tasks for async email notifications."""
import logging
from datetime import date

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _parse_date(iso_str: str) -> date:
    """Parse an ISO date or datetime string to a date object.

    Handles both 'YYYY-MM-DD' and 'YYYY-MM-DD HH:MM:SS.ffffff+TZ' formats
    by taking only the date portion (first 10 characters).
    """
    return date.fromisoformat(iso_str[:10])


def _resolve_brand(brand_dict: dict | None, tenant_id: int | None) -> dict | None:
    """Retourne brand_dict si fourni, sinon charge depuis tenant_settings via tenant_id.

    Permet au caller de choisir : passer brand explicitement (cas des callers
    qui l'ont deja charge pour un autre usage), OU laisser la task le charger
    elle-meme via le tenant_id.
    """
    if brand_dict:
        return brand_dict
    if tenant_id is None:
        return None
    from app.core.database import get_db_context
    from app.services.invoice_pdf import load_brand_for_tenant_sync

    with get_db_context() as db:
        return load_brand_for_tenant_sync(db, tenant_id)


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
    brand_dict: dict | None = None,
    tenant_id: int | None = None,
):
    """Send reservation confirmation email (async). Brand propage par le caller."""
    from app.services.notification import notification_service

    try:
        notification_service.send_reservation_confirmed(
            email=email,
            customer_name=customer_name,
            reference=reference,
            event_date=_parse_date(event_date_iso),
            delivery_date=_parse_date(delivery_date_iso),
            return_date=_parse_date(return_date_iso),
            event_location=event_location,
            total_cents=total_cents,
            deposit_cents=deposit_cents,
            brand=_resolve_brand(brand_dict, tenant_id),
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
    brand_dict: dict | None = None,
    tenant_id: int | None = None,
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
            due_date=_parse_date(due_date_iso),
            issue_date=_parse_date(issue_date_iso),
            brand=_resolve_brand(brand_dict, tenant_id),
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
    brand_dict: dict | None = None,
    tenant_id: int | None = None,
):
    """Send delivery completed notification email (async)."""
    from app.services.notification import notification_service

    try:
        notification_service.send_delivery_completed(
            email=email,
            customer_name=customer_name,
            reservation_reference=reservation_reference,
            delivery_address=delivery_address,
            delivery_date=_parse_date(delivery_date_iso),
            brand=_resolve_brand(brand_dict, tenant_id),
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
    brand_dict: dict | None = None,
    tenant_id: int | None = None,
):
    """Send return completed notification email (async)."""
    from app.services.notification import notification_service

    try:
        notification_service.send_return_completed(
            email=email,
            customer_name=customer_name,
            reservation_reference=reservation_reference,
            return_date=_parse_date(return_date_iso),
            brand=_resolve_brand(brand_dict, tenant_id),
        )
    except Exception as exc:
        logger.exception("Failed to send return email to %s", email)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, queue='notifications', max_retries=3, default_retry_delay=60)
def send_deposit_reminder_email(
    self,
    email: str,
    customer_name: str,
    reservation_reference: str,
    event_date_iso: str,
    amount_cents: int,
    brand_dict: dict | None = None,
    tenant_id: int | None = None,
):
    """Send deposit reminder notification email (async)."""
    from app.services.notification import notification_service

    try:
        notification_service.send_deposit_reminder(
            email=email,
            customer_name=customer_name,
            reservation_reference=reservation_reference,
            event_date=_parse_date(event_date_iso),
            amount_cents=amount_cents,
            brand=_resolve_brand(brand_dict, tenant_id),
        )
    except Exception as exc:
        logger.exception("Failed to send deposit reminder email to %s", email)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, queue="notifications", max_retries=3, default_retry_delay=60)
def send_supplier_order_email(
    self,
    order_id: int,
    supplier_id: int,
    reference: str,
    tenant_id: int,
):
    """Envoie un email de confirmation de commande au fournisseur.

    Charge le brand via tenant_id (pas de brand_dict externe : le caller
    est interne a supplier_order.py et n'a pas besoin de le passer).
    """
    from app.core.database import get_db_context
    from app.models.supplier import Supplier
    from app.models.supplier_order import SupplierOrder, SupplierOrderLine
    from app.services.notification import notification_service
    from app.services.invoice_pdf import load_brand_for_tenant_sync

    try:
        with get_db_context() as db:
            supplier = db.get(Supplier, supplier_id)
            if not supplier or not supplier.email:
                logger.warning(
                    "Supplier %d has no email — skipping order notification for %s",
                    supplier_id, reference,
                )
                return

            order = db.get(SupplierOrder, order_id)
            lines = (
                db.query(SupplierOrderLine)
                .filter(SupplierOrderLine.order_id == order_id)
                .all()
            )

            total_cents = sum(l.unit_cost_cents * l.qty_ordered for l in lines)
            brand = load_brand_for_tenant_sync(db, tenant_id)

            notification_service.send_supplier_order_confirmation(
                email=supplier.email,
                supplier_name=supplier.name,
                reference=reference,
                order_date=str(order.order_date) if order and order.order_date else "",
                expected_date=str(order.expected_date) if order and order.expected_date else "",
                lines_count=len(lines),
                total_cents=total_cents,
                brand_name=brand["name"],
            )
            logger.info(
                "Sent supplier order email to %s for order %s",
                supplier.email, reference,
            )
    except Exception as exc:
        logger.exception("Failed to send supplier order email for %s", reference)
        raise self.retry(exc=exc)
