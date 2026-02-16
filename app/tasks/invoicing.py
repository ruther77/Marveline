"""Celery periodic tasks for invoicing."""
import logging

from sqlalchemy import distinct

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(queue="invoicing")
def check_overdue_invoices():
    """Detect and mark overdue invoices for all active tenants."""
    from app.core.database import get_db_context
    from app.models.user import User
    from app.services.invoice import InvoiceService

    with get_db_context() as db:
        tenant_ids = [
            r[0]
            for r in db.query(distinct(User.tenant_id))
            .filter(User.is_active == True)  # noqa: E712
            .all()
        ]

        total_updated = 0
        for tid in tenant_ids:
            svc = InvoiceService(db)
            updated = svc.check_overdue_invoices(tid)
            if updated:
                total_updated += len(updated)
                db.commit()

        if total_updated:
            logger.info("Marked %d invoices as overdue across %d tenants", total_updated, len(tenant_ids))
