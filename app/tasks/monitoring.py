"""Celery periodic tasks for monitoring (late movements, low stock)."""
import logging

from sqlalchemy import distinct

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(queue="default")
def check_late_movements():
    """Log late movements for each active tenant."""
    from app.core.database import get_db_context
    from app.models.user import User
    from app.repositories.inventory_movement import MovementRepository

    with get_db_context() as db:
        tenant_ids = [
            r[0]
            for r in db.query(distinct(User.tenant_id))
            .filter(User.is_active == True)  # noqa: E712
            .all()
        ]

        for tid in tenant_ids:
            repo = MovementRepository(db)
            late, count = repo.list_late(tid)
            if count > 0:
                logger.warning("Tenant %d: %d late movements", tid, count)


@celery_app.task(queue="default")
def check_low_stock(threshold: int = 5):
    """Detect products with available stock below threshold."""
    from app.core.database import get_db_context
    from app.models.product import Product
    from app.models.user import User

    with get_db_context() as db:
        tenant_ids = [
            r[0]
            for r in db.query(distinct(User.tenant_id))
            .filter(User.is_active == True)  # noqa: E712
            .all()
        ]

        for tid in tenant_ids:
            low = (
                db.query(Product)
                .filter(
                    Product.tenant_id == tid,
                    Product.is_active == True,  # noqa: E712
                    Product.available_quantity < threshold,
                )
                .all()
            )
            if low:
                logger.warning("Tenant %d: %d products with low stock (threshold=%d)", tid, len(low), threshold)
