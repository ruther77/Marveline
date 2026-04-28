"""Celery periodic task: detection automatique des risques sur reservations actives.

Scanne quotidiennement les reservations dont l'event_date approche (J-7) ou dont
les factures sont overdue, et persiste les risques detectes dans
`reservation_risks`. Deduplication par (reservation_id, type) sur risques actifs
(resolved_at IS NULL) pour eviter les doublons inter-runs.
"""
import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("confirmed", "confirmed_risk", "pre_check", "delivered", "extended")


@celery_app.task(bind=True, queue="default", max_retries=2, default_retry_delay=120)
def detect_reservation_risks_daily(self):
    """Scanne toutes les reservations actives et persiste les risques detectes.

    Returns dict avec compteurs par tenant pour observabilite.
    """
    try:
        return asyncio.run(_run_detection())
    except Exception as exc:
        logger.exception("detect_reservation_risks_daily failed")
        raise self.retry(exc=exc)


async def _run_detection() -> dict:
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.reservation import Reservation, ReservationRisk
    from app.models.tenant import Tenant
    from app.services.reservation_workflow import ReservationWorkflowService

    total_scanned = 0
    total_created = 0
    per_tenant: dict[int, dict[str, int]] = {}

    async with AsyncSessionLocal() as db:
        tenants_res = await db.execute(
            select(Tenant.id).where(Tenant.status == "active")
        )
        tenant_ids = [r[0] for r in tenants_res.all()]

        workflow = ReservationWorkflowService(db)

        for tid in tenant_ids:
            scanned = 0
            created = 0

            res_q = await db.execute(
                select(Reservation.id).where(
                    Reservation.tenant_id == tid,
                    Reservation.status.in_(ACTIVE_STATUSES),
                )
            )
            reservation_ids = [r[0] for r in res_q.all()]

            for rid in reservation_ids:
                scanned += 1
                detected = await workflow.detect_risks(rid, tid)
                if not detected:
                    continue

                existing_q = await db.execute(
                    select(ReservationRisk.type).where(
                        ReservationRisk.reservation_id == rid,
                        ReservationRisk.tenant_id == tid,
                        ReservationRisk.resolved_at.is_(None),
                    )
                )
                existing_types = {r[0] for r in existing_q.all()}

                for risk in detected:
                    if risk["type"] in existing_types:
                        continue
                    db.add(
                        ReservationRisk(
                            tenant_id=tid,
                            reservation_id=rid,
                            type=risk["type"],
                            severity=risk["severity"],
                            description=risk["description"],
                            blocking=risk.get("blocking", False),
                        )
                    )
                    created += 1

            await db.commit()
            per_tenant[tid] = {"scanned": scanned, "created": created}
            total_scanned += scanned
            total_created += created

            if created:
                logger.info(
                    "Tenant %d: %d risks created (scanned %d reservations)",
                    tid, created, scanned,
                )

    logger.info(
        "detect_reservation_risks_daily complete: scanned=%d created=%d tenants=%d",
        total_scanned, total_created, len(per_tenant),
    )
    return {
        "scanned": total_scanned,
        "created": total_created,
        "tenants": per_tenant,
    }
