"""Taches Celery pour le module Fidelite (Loyalty).

Jobs :
- daily : expire_points_fifo, send_expiration_warnings, send_birthday_rewards
- daily (dispatch) : evaluate_all_tiers → evaluate_member_tier
- every 5min : activate_flash_offers, deactivate_flash_offers
"""

import logging
from datetime import datetime, timedelta, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_sync_session():
    """Obtient une session DB synchrone pour les tasks Celery."""
    from app.core.database import SessionLocal
    return SessionLocal()


@celery_app.task(bind=True, queue="loyalty", max_retries=3, default_retry_delay=120)
def expire_points_fifo(self):
    """Expire les points FIFO (12 mois EARN, 6 mois BONUS).

    Tourne quotidiennement. Insere des lignes EXPIRE dans le ledger.
    """
    from sqlalchemy import and_, select
    from app.models.loyalty import PointsLedger

    db = _get_sync_session()
    try:
        now = datetime.now(timezone.utc)

        stmt = (
            select(PointsLedger)
            .where(
                and_(
                    PointsLedger.expires_at.isnot(None),
                    PointsLedger.expires_at <= now,
                    PointsLedger.entry_type.in_(["earn", "bonus"]),
                    PointsLedger.amount > 0,
                )
            )
            .order_by(PointsLedger.expires_at.asc())
            .limit(1000)
        )
        result = db.execute(stmt)
        expired_entries = result.scalars().all()

        if not expired_entries:
            logger.info("No points to expire")
            return {"expired": 0}

        members_to_expire: dict[int, list] = {}
        for entry in expired_entries:
            members_to_expire.setdefault(entry.member_id, []).append(entry)

        total_expired = 0
        for member_id, entries in members_to_expire.items():
            for entry in entries:
                balance_stmt = (
                    select(PointsLedger.balance_after)
                    .where(PointsLedger.member_id == member_id)
                    .order_by(PointsLedger.created_at.desc())
                    .limit(1)
                )
                balance_result = db.execute(balance_stmt)
                current_balance = balance_result.scalar_one_or_none() or 0
                new_balance = current_balance - entry.amount

                expire_entry = PointsLedger(
                    tenant_id=entry.tenant_id,
                    member_id=member_id,
                    amount=-entry.amount,
                    entry_type="expire",
                    source=None,
                    balance_after=new_balance,
                    metadata_json={"expired_entry_id": entry.id},
                )
                db.add(expire_entry)

                entry.expires_at = None
                total_expired += entry.amount

        db.commit()
        logger.info("Expired %d points across %d members", total_expired, len(members_to_expire))
        return {"expired": total_expired, "members": len(members_to_expire)}

    except Exception as exc:
        db.rollback()
        logger.exception("Failed to expire points")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, queue="loyalty", max_retries=3, default_retry_delay=120)
def evaluate_all_tiers(self):
    """Dispatch l'evaluation de palier pour tous les membres actifs."""
    from sqlalchemy import select
    from app.models.loyalty import LoyaltyMember

    db = _get_sync_session()
    try:
        stmt = select(LoyaltyMember.id, LoyaltyMember.tenant_id).where(
            LoyaltyMember.is_active.is_(True)
        ).limit(5000)
        result = db.execute(stmt)
        rows = result.all()

        for member_id, tenant_id in rows:
            evaluate_member_tier.delay(member_id, tenant_id)

        logger.info("Scheduled tier check for %d members", len(rows))
        return {"scheduled": len(rows)}

    except Exception as exc:
        logger.exception("Failed to schedule tier checks")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, queue="loyalty", max_retries=2, default_retry_delay=30)
def evaluate_member_tier(self, member_id: int, tenant_id: int):
    """Evalue le palier d'un seul membre."""
    import asyncio
    from app.core.database import async_session_factory

    async def _run():
        async with async_session_factory() as db:
            from app.services.loyalty import LoyaltyService
            service = LoyaltyService(db)
            change = await service.evaluate_tier(member_id, tenant_id)
            await db.commit()
            return change

    try:
        change = asyncio.run(_run())
        if change:
            logger.info("Tier changed member %d: %s -> %s", member_id, change.from_tier, change.to_tier)
    except Exception as exc:
        logger.exception("Failed tier check for member %d", member_id)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, queue="loyalty", max_retries=3, default_retry_delay=60)
def send_expiration_warnings(self):
    """Envoie les notifications d'expiration (J-14 et J-3)."""
    from sqlalchemy import select, and_, func
    from app.models.loyalty import PointsLedger
    from app.constants.loyalty import EXPIRY_WARNING_DAYS_FIRST, EXPIRY_WARNING_DAYS_SECOND

    db = _get_sync_session()
    try:
        now = datetime.now(timezone.utc)
        sent = 0

        for days, notif_type in [
            (EXPIRY_WARNING_DAYS_FIRST, "expiration_j14"),
            (EXPIRY_WARNING_DAYS_SECOND, "expiration_j3"),
        ]:
            target = now + timedelta(days=days)
            window_start = target - timedelta(hours=12)
            window_end = target + timedelta(hours=12)

            stmt = (
                select(PointsLedger.member_id, func.sum(PointsLedger.amount))
                .where(
                    and_(
                        PointsLedger.expires_at.isnot(None),
                        PointsLedger.expires_at.between(window_start, window_end),
                        PointsLedger.entry_type.in_(["earn", "bonus"]),
                        PointsLedger.amount > 0,
                    )
                )
                .group_by(PointsLedger.member_id)
            )
            rows = db.execute(stmt).all()

            for member_id, expiring_pts in rows:
                logger.info("%s: member %d has %d points expiring", notif_type, member_id, expiring_pts)
                sent += 1

        db.commit()
        return {"notifications_sent": sent}

    except Exception as exc:
        db.rollback()
        logger.exception("Failed to send expiration warnings")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, queue="loyalty", max_retries=2, default_retry_delay=60)
def send_birthday_rewards(self):
    """Envoie les rewards anniversaire VIP (1er du mois uniquement)."""
    now = datetime.now(timezone.utc)
    if now.day != 1:
        return {"status": "skipped", "reason": "not first of month"}

    from sqlalchemy import select, and_
    from app.models.loyalty import LoyaltyMember

    db = _get_sync_session()
    try:
        stmt = select(LoyaltyMember).where(
            and_(
                LoyaltyMember.birth_month == now.month,
                LoyaltyMember.current_tier == "vip",
                LoyaltyMember.is_active.is_(True),
            )
        )
        members = db.execute(stmt).scalars().all()

        for m in members:
            logger.info("Birthday reward: VIP member %d (%s %s)", m.id, m.first_name, m.last_name)

        return {"birthday_members": len(members)}

    except Exception as exc:
        logger.exception("Failed to send birthday rewards")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, queue="loyalty", max_retries=2, default_retry_delay=30)
def activate_flash_offers(self):
    """Active les offres flash dont starts_at est atteint."""
    from sqlalchemy import select, and_
    from app.models.loyalty import FlashOffer

    db = _get_sync_session()
    try:
        now = datetime.now(timezone.utc)
        stmt = select(FlashOffer).where(
            and_(FlashOffer.status == "scheduled", FlashOffer.starts_at <= now)
        )
        offers = db.execute(stmt).scalars().all()
        for o in offers:
            o.status = "active"
            logger.info("Activated flash offer %d: %s", o.id, o.name)
        db.commit()
        return {"activated": len(offers)}
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to activate flash offers")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, queue="loyalty", max_retries=2, default_retry_delay=30)
def deactivate_flash_offers(self):
    """Desactive les offres flash dont ends_at est depasse."""
    from sqlalchemy import select, and_
    from app.models.loyalty import FlashOffer

    db = _get_sync_session()
    try:
        now = datetime.now(timezone.utc)
        stmt = select(FlashOffer).where(
            and_(FlashOffer.status == "active", FlashOffer.ends_at <= now)
        )
        offers = db.execute(stmt).scalars().all()
        for o in offers:
            o.status = "ended"
            logger.info("Ended flash offer %d: %s", o.id, o.name)
        db.commit()
        return {"deactivated": len(offers)}
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to deactivate flash offers")
        raise self.retry(exc=exc)
    finally:
        db.close()
