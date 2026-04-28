"""Celery task — execution des relances planifiees."""
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.relances.execute_scheduled_relances", queue="notifications")
def execute_scheduled_relances():
    """Execute les relances dont scheduled_at <= now et status = 'scheduled'.

    Pour chaque relance :
    1. Charger facture + reservation + customer
    2. Skip si invoice.status in ('paid', 'cancelled') ou customer.email absent
    3. Appeler notification_service.send_relance_email() (F1058 fix Sprint 1)
    4. Si gateway succès -> status='sent', sent_at=now()
    5. Si gateway échec -> status='failed', email_send_error=<msg>, retry next cycle
    6. Mettre a jour first_reminder_sent_at / last_reminder_sent_at sur la facture (sent only)

    Beat schedule : toutes les heures.
    """
    from app.core.database import get_db_context
    from app.models.relance import Relance
    from app.models.invoice import Invoice
    from app.models.reservation import Reservation
    from app.models.customer import Customer
    from app.models.tenant import Tenant
    from app.services.notification import notification_service

    now = datetime.now(timezone.utc)

    with get_db_context() as db:
        tenant_ids = [
            r[0]
            for r in db.query(Tenant.id).filter(Tenant.status == "active").all()
        ]

        total_sent = 0
        total_failed = 0
        total_skipped = 0
        total_processed = 0

        for tid in tenant_ids:
            relances = (
                db.query(Relance)
                .filter(
                    Relance.tenant_id == tid,
                    Relance.status == "scheduled",
                    Relance.scheduled_at <= now,
                )
                .limit(100)
                .all()
            )

            for relance in relances:
                total_processed += 1
                try:
                    invoice = db.get(Invoice, relance.invoice_id)
                    if not invoice:
                        logger.warning("Relance %d skip: invoice %d not found", relance.id, relance.invoice_id)
                        relance.status = "cancelled"
                        relance.cancelled_at = now
                        total_skipped += 1
                        continue

                    if invoice.status in ("paid", "cancelled"):
                        logger.info("Relance %d skip: invoice %s already %s", relance.id, invoice.invoice_number, invoice.status)
                        relance.status = "cancelled"
                        relance.cancelled_at = now
                        total_skipped += 1
                        continue

                    reservation = db.get(Reservation, invoice.reservation_id) if invoice.reservation_id else None
                    customer = db.get(Customer, reservation.customer_id) if reservation else None

                    if not customer or not customer.email:
                        logger.warning("Relance %d skip: no customer email (invoice=%s)", relance.id, invoice.invoice_number)
                        relance.status = "cancelled"
                        relance.cancelled_at = now
                        total_skipped += 1
                        continue

                    # F1058 FIX Sprint 1 — envoi réel via gateway avant marquage 'sent'
                    tenant = db.get(Tenant, tid)
                    customer_name = (
                        f"{customer.first_name or ''} {customer.last_name or ''}".strip()
                        or getattr(customer, "company_name", None)
                        or "Client"
                    )
                    brand_name = getattr(tenant, "brand_display_name", None) or getattr(tenant, "nom", None) or "Marveline"
                    due_date_str = invoice.due_date.isoformat() if invoice.due_date else ""
                    total_cts = invoice.total_ttc_cents or 0

                    email_error = None
                    try:
                        sent_ok = notification_service.send_relance_email(
                            email=customer.email,
                            customer_name=customer_name,
                            invoice_number=invoice.invoice_number,
                            invoice_total_cts=total_cts,
                            invoice_due_date=due_date_str,
                            tenant_brand_name=brand_name,
                        )
                    except Exception as exc:
                        logger.exception("Relance %d email gateway error: %s", relance.id, exc)
                        sent_ok = False
                        email_error = str(exc)[:500]

                    if sent_ok:
                        relance.status = "sent"
                        relance.sent_at = now
                        relance.email_send_error = None
                        if not invoice.first_reminder_sent_at:
                            invoice.first_reminder_sent_at = now
                        invoice.last_reminder_sent_at = now

                        total_sent += 1
                        logger.info(
                            "Relance %d sent OK: invoice=%s customer=%s channel=%s tenant=%d",
                            relance.id, invoice.invoice_number, customer.email,
                            relance.channel, tid,
                        )
                    else:
                        relance.status = "failed"
                        relance.email_send_error = email_error or "gateway returned False"
                        total_failed += 1
                        logger.error(
                            "Relance %d FAILED: invoice=%s customer=%s error=%s",
                            relance.id, invoice.invoice_number, customer.email,
                            relance.email_send_error,
                        )
                except Exception:
                    logger.exception("Relance %d unexpected failure — will retry next cycle", relance.id)
                    total_failed += 1

        db.commit()
        logger.info(
            "[relances] Executed sent=%d failed=%d skipped=%d total=%d across %d tenants",
            total_sent, total_failed, total_skipped, total_processed, len(tenant_ids),
        )
        return {
            "sent": total_sent,
            "failed": total_failed,
            "skipped": total_skipped,
            "total": total_processed,
        }
