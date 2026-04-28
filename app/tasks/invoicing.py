"""Celery periodic tasks for invoicing."""
import logging
from datetime import date, datetime, timedelta, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

RELANCE_THRESHOLDS_DAYS = [7, 30, 60]


@celery_app.task(queue="invoicing")
def check_overdue_invoices():
    """Detect overdue invoices and auto-schedule relances.

    Pour chaque facture dont due_date < today et status in (sent, overdue):
    1. Marque la facture OVERDUE si pas deja fait
    2. Auto-cree une Relance scheduled si aucune relance scheduled n'existe
       et que le delai depasse un seuil (7j, 30j, 60j)
    """
    from app.core.database import get_db_context
    from app.models.tenant import Tenant
    from app.models.invoice import Invoice
    from app.models.relance import Relance

    today = date.today()
    now = datetime.now(timezone.utc)

    with get_db_context() as db:
        tenant_ids = [
            r[0]
            for r in db.query(Tenant.id)
            .filter(Tenant.status == "active")
            .all()
        ]

        total_overdue = 0
        total_relances = 0

        for tid in tenant_ids:
            invoices = (
                db.query(Invoice)
                .filter(
                    Invoice.tenant_id == tid,
                    Invoice.status.in_(["sent", "overdue"]),
                    Invoice.due_date < today,
                )
                .limit(200)
                .all()
            )

            for invoice in invoices:
                if invoice.status != "overdue":
                    invoice.status = "overdue"
                    total_overdue += 1

                days_overdue = (today - invoice.due_date).days
                relance_created = _maybe_schedule_relance(
                    db, tid, invoice, days_overdue, now,
                )
                if relance_created:
                    total_relances += 1

            db.commit()

        if total_overdue or total_relances:
            logger.info(
                "[invoicing] Marked %d overdue, created %d relances across %d tenants",
                total_overdue, total_relances, len(tenant_ids),
            )
        return {"overdue": total_overdue, "relances": total_relances}


def _maybe_schedule_relance(db, tenant_id, invoice, days_overdue, now):
    """Cree une relance si le seuil est atteint et aucune relance scheduled n'existe."""
    from app.models.relance import Relance

    for threshold in RELANCE_THRESHOLDS_DAYS:
        if days_overdue < threshold:
            continue

        existing = (
            db.query(Relance)
            .filter(
                Relance.tenant_id == tenant_id,
                Relance.invoice_id == invoice.id,
                Relance.status == "scheduled",
            )
            .first()
        )
        if existing:
            return False

        sent_count = (
            db.query(Relance)
            .filter(
                Relance.tenant_id == tenant_id,
                Relance.invoice_id == invoice.id,
                Relance.status == "sent",
            )
            .count()
        )

        expected_for_threshold = RELANCE_THRESHOLDS_DAYS.index(threshold)
        if sent_count > expected_for_threshold:
            continue

        relance = Relance(
            tenant_id=tenant_id,
            invoice_id=invoice.id,
            scheduled_at=now,
            status="scheduled",
            channel="email",
            message=f"Relance automatique — facture {invoice.invoice_number} "
                    f"en retard de {days_overdue} jours",
            created_at=now,
        )
        db.add(relance)
        logger.info(
            "Auto-scheduled relance for invoice %s (overdue %dd, tenant=%d)",
            invoice.invoice_number, days_overdue, tenant_id,
        )
        return True

    return False


DEPOSIT_REMIND_AFTER_DAYS = 3


@celery_app.task(queue="invoicing")
def check_unreturned_deposits():
    """Detecte les deposits HELD dont la reservation est terminee et envoie un rappel.

    Conditions pour rappel :
    - Deposit status = 'held'
    - Reservation status in (returned, completed, returned_dispute)
    - Reservation return_date + DEPOSIT_REMIND_AFTER_DAYS < today
    """
    from app.core.database import get_db_context
    from app.models.tenant import Tenant
    from app.models.deposit import Deposit
    from app.models.reservation import Reservation
    from app.models.customer import Customer

    today = date.today()
    threshold = today - timedelta(days=DEPOSIT_REMIND_AFTER_DAYS)

    with get_db_context() as db:
        tenant_ids = [
            r[0]
            for r in db.query(Tenant.id)
            .filter(Tenant.status == "active")
            .all()
        ]

        total_reminded = 0

        for tid in tenant_ids:
            deposits = (
                db.query(Deposit, Reservation, Customer)
                .join(Reservation, Deposit.reservation_id == Reservation.id)
                .outerjoin(Customer, Reservation.customer_id == Customer.id)
                .filter(
                    Deposit.tenant_id == tid,
                    Deposit.status == "held",
                    Reservation.status.in_(["returned", "completed", "returned_dispute"]),
                    Reservation.return_date <= threshold,
                )
                .limit(100)
                .all()
            )

            for dep, resa, customer in deposits:
                if not customer or not customer.email:
                    continue

                try:
                    from app.tasks.notifications import send_deposit_reminder_email
                    send_deposit_reminder_email.delay(
                        email=customer.email,
                        customer_name=customer.first_name or "",
                        reservation_reference=resa.reference,
                        event_date_iso=str(resa.event_date) if resa.event_date else str(today),
                        amount_cents=dep.amount_cents,
                        tenant_id=tid,
                    )
                    total_reminded += 1
                    logger.info(
                        "Auto-deposit-remind: deposit %d, reservation %s, customer %s (tenant=%d)",
                        dep.id, resa.reference, customer.email, tid,
                    )
                except Exception:
                    logger.exception(
                        "Failed to queue deposit reminder for deposit %d", dep.id
                    )

        db.commit()

        if total_reminded:
            logger.info(
                "[deposits] Sent %d deposit reminders across %d tenants",
                total_reminded, len(tenant_ids),
            )
        return {"reminded": total_reminded}


@celery_app.task(queue="invoicing")
def expire_overdue_devis():
    """Passe les devis SENT/NEGOTIATION dont valid_until < today en EXPIRED.

    Beat schedule : quotidien a 07:30 UTC.
    """
    from app.core.database import get_db_context
    from app.models.tenant import Tenant
    from app.models.devis import Devis

    today = date.today()

    with get_db_context() as db:
        tenant_ids = [
            r[0]
            for r in db.query(Tenant.id)
            .filter(Tenant.status == "active")
            .all()
        ]

        total_expired = 0

        for tid in tenant_ids:
            devis_list = (
                db.query(Devis)
                .filter(
                    Devis.tenant_id == tid,
                    Devis.status.in_(["sent", "negotiation", "version_pending"]),
                    Devis.valid_until < today,
                    Devis.is_active.is_(True),
                )
                .limit(200)
                .all()
            )

            for devis in devis_list:
                devis.status = "expired"
                total_expired += 1
                logger.info(
                    "Auto-expired devis %s (valid_until=%s, tenant=%d)",
                    devis.reference, devis.valid_until, tid,
                )

        db.commit()

        if total_expired:
            logger.info(
                "[devis] Expired %d devis across %d tenants",
                total_expired, len(tenant_ids),
            )
        return {"expired": total_expired}
