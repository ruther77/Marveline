"""Repositories du module Fidelite (Loyalty).

Repos async specialises pour les entites loyalty.
Le PointsLedger et RevenueLedger sont append-only (jamais d'update/delete).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.loyalty import (
    FlashOffer,
    LoyaltyMember,
    LoyaltyNotificationLog,
    LoyaltyProgram,
    PointsLedger,
    ReferralLink,
    RevenueLedger,
    RewardRedemption,
    RewardsCatalog,
    TierHistory,
    WalletPass,
)
from app.repositories.base import AsyncBaseRepository

logger = logging.getLogger(__name__)


# ── LoyaltyProgramRepository ─────────────────────────────────────────────────


class AsyncLoyaltyProgramRepository(AsyncBaseRepository["LoyaltyProgram"]):

    def __init__(self, db: AsyncSession):
        super().__init__(db, LoyaltyProgram)

    async def get_by_name(self, name: str, tenant_id: int) -> Optional[LoyaltyProgram]:
        stmt = select(LoyaltyProgram).where(
            and_(
                LoyaltyProgram.tenant_id == tenant_id,
                LoyaltyProgram.name == name,
                LoyaltyProgram.is_active.is_(True),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


# ── LoyaltyMemberRepository ──────────────────────────────────────────────────


class AsyncLoyaltyMemberRepository(AsyncBaseRepository["LoyaltyMember"]):

    def __init__(self, db: AsyncSession):
        super().__init__(db, LoyaltyMember)

    async def get_by_phone(
        self, phone: str, program_id: int, tenant_id: int
    ) -> Optional[LoyaltyMember]:
        stmt = select(LoyaltyMember).where(
            and_(
                LoyaltyMember.tenant_id == tenant_id,
                LoyaltyMember.phone == phone,
                LoyaltyMember.program_id == program_id,
                LoyaltyMember.is_active.is_(True),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_referral_code(
        self, referral_code: str, tenant_id: int
    ) -> Optional[LoyaltyMember]:
        stmt = select(LoyaltyMember).where(
            and_(
                LoyaltyMember.tenant_id == tenant_id,
                LoyaltyMember.referral_code == referral_code,
                LoyaltyMember.is_active.is_(True),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def count_by_program(self, program_id: int, tenant_id: int) -> int:
        stmt = select(func.count(LoyaltyMember.id)).where(
            and_(
                LoyaltyMember.tenant_id == tenant_id,
                LoyaltyMember.program_id == program_id,
                LoyaltyMember.is_active.is_(True),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def count_by_tier(
        self, program_id: int, tier: str, tenant_id: int
    ) -> int:
        stmt = select(func.count(LoyaltyMember.id)).where(
            and_(
                LoyaltyMember.tenant_id == tenant_id,
                LoyaltyMember.program_id == program_id,
                LoyaltyMember.current_tier == tier,
                LoyaltyMember.is_active.is_(True),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def list_at_risk(
        self, program_id: int, tenant_id: int,
        min_days: int, max_days: int,
        skip: int = 0, limit: int = 50,
    ) -> list[LoyaltyMember]:
        """Membres a risque de churn (pas de transaction depuis min_days..max_days)."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(LoyaltyMember)
            .outerjoin(
                PointsLedger,
                and_(
                    PointsLedger.member_id == LoyaltyMember.id,
                    PointsLedger.entry_type == "earn",
                )
            )
            .where(
                and_(
                    LoyaltyMember.tenant_id == tenant_id,
                    LoyaltyMember.program_id == program_id,
                    LoyaltyMember.is_active.is_(True),
                )
            )
            .group_by(LoyaltyMember.id)
            .having(
                and_(
                    func.max(PointsLedger.created_at) < now - timedelta(days=min_days),
                    func.max(PointsLedger.created_at) >= now - timedelta(days=max_days),
                )
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_birthday_members(
        self, program_id: int, tenant_id: int, month: int
    ) -> list[LoyaltyMember]:
        """Membres VIP dont le mois d'anniversaire correspond."""
        stmt = select(LoyaltyMember).where(
            and_(
                LoyaltyMember.tenant_id == tenant_id,
                LoyaltyMember.program_id == program_id,
                LoyaltyMember.birth_month == month,
                LoyaltyMember.current_tier == "vip",
                LoyaltyMember.is_active.is_(True),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


# ── PointsLedgerRepository ────────────────────────────────────────────────────


class AsyncPointsLedgerRepository:
    """Repository append-only pour le journal de points.

    Pas de BaseRepository — pas d'update/delete.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def append(self, entry: PointsLedger) -> PointsLedger:
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_balance(self, member_id: int, tenant_id: int) -> int:
        """Solde courant = somme de toutes les entrees."""
        stmt = select(func.coalesce(func.sum(PointsLedger.amount), 0)).where(
            and_(
                PointsLedger.member_id == member_id,
                PointsLedger.tenant_id == tenant_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_last_entry(
        self, member_id: int, tenant_id: int
    ) -> Optional[PointsLedger]:
        """Derniere entree du ledger (pour balance_after)."""
        stmt = (
            select(PointsLedger)
            .where(
                and_(
                    PointsLedger.member_id == member_id,
                    PointsLedger.tenant_id == tenant_id,
                )
            )
            .order_by(PointsLedger.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_points_earned_in_window(
        self, member_id: int, tenant_id: int, months: int
    ) -> int:
        """Points gagnes (EARN) dans les N derniers mois (pour evaluation palier)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
        stmt = select(func.coalesce(func.sum(PointsLedger.amount), 0)).where(
            and_(
                PointsLedger.member_id == member_id,
                PointsLedger.tenant_id == tenant_id,
                PointsLedger.entry_type == "earn",
                PointsLedger.created_at >= cutoff,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_expiring_entries(
        self, tenant_id: int, before: datetime
    ) -> list[PointsLedger]:
        """Entrees qui expirent avant la date donnee (non encore expirees)."""
        stmt = (
            select(PointsLedger)
            .where(
                and_(
                    PointsLedger.tenant_id == tenant_id,
                    PointsLedger.expires_at.isnot(None),
                    PointsLedger.expires_at <= before,
                    PointsLedger.entry_type.in_(["earn", "bonus"]),
                    PointsLedger.amount > 0,
                )
            )
            .order_by(PointsLedger.expires_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_entries_by_order(
        self, order_id: int, tenant_id: int
    ) -> list[PointsLedger]:
        """Entrees liees a une commande (pour annulation)."""
        stmt = select(PointsLedger).where(
            and_(
                PointsLedger.order_id == order_id,
                PointsLedger.tenant_id == tenant_id,
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_points_this_month(self, tenant_id: int, entry_type: str) -> int:
        """Total points du mois courant par type (pour dashboard)."""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.coalesce(func.sum(func.abs(PointsLedger.amount)), 0)).where(
            and_(
                PointsLedger.tenant_id == tenant_id,
                PointsLedger.entry_type == entry_type,
                PointsLedger.created_at >= month_start,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_total_points_in_circulation(self, tenant_id: int) -> int:
        """Somme de tous les soldes positifs (liability)."""
        stmt = select(func.coalesce(func.sum(PointsLedger.amount), 0)).where(
            PointsLedger.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()


# ── RevenueLedgerRepository ───────────────────────────────────────────────────


class AsyncRevenueLedgerRepository:
    """Repository append-only pour le journal de CA (Marveline location)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def append(self, entry: RevenueLedger) -> RevenueLedger:
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_cumulative(self, member_id: int, tenant_id: int) -> int:
        """CA cumule courant en centimes."""
        stmt = select(func.coalesce(func.sum(RevenueLedger.amount_cents), 0)).where(
            and_(
                RevenueLedger.member_id == member_id,
                RevenueLedger.tenant_id == tenant_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_cumulative_in_window(
        self, member_id: int, tenant_id: int, months: int
    ) -> int:
        """CA cumule dans les N derniers mois (fenetre glissante)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
        stmt = select(func.coalesce(func.sum(RevenueLedger.amount_cents), 0)).where(
            and_(
                RevenueLedger.member_id == member_id,
                RevenueLedger.tenant_id == tenant_id,
                RevenueLedger.created_at >= cutoff,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_last_entry(
        self, member_id: int, tenant_id: int
    ) -> Optional[RevenueLedger]:
        stmt = (
            select(RevenueLedger)
            .where(
                and_(
                    RevenueLedger.member_id == member_id,
                    RevenueLedger.tenant_id == tenant_id,
                )
            )
            .order_by(RevenueLedger.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


# ── RewardsCatalogRepository ─────────────────────────────────────────────────


class AsyncRewardsCatalogRepository(AsyncBaseRepository["RewardsCatalog"]):

    def __init__(self, db: AsyncSession):
        super().__init__(db, RewardsCatalog)

    async def list_by_tier(
        self, program_id: int, tier: str, tenant_id: int,
        active_only: bool = True,
    ) -> list[RewardsCatalog]:
        conditions = [
            RewardsCatalog.tenant_id == tenant_id,
            RewardsCatalog.program_id == program_id,
            RewardsCatalog.tier == tier,
        ]
        if active_only:
            conditions.append(RewardsCatalog.is_active.is_(True))
        stmt = select(RewardsCatalog).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_active_by_program(
        self, program_id: int, tenant_id: int
    ) -> list[RewardsCatalog]:
        stmt = select(RewardsCatalog).where(
            and_(
                RewardsCatalog.tenant_id == tenant_id,
                RewardsCatalog.program_id == program_id,
                RewardsCatalog.is_active.is_(True),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


# ── RewardRedemptionRepository ────────────────────────────────────────────────


class AsyncRewardRedemptionRepository(AsyncBaseRepository["RewardRedemption"]):

    def __init__(self, db: AsyncSession):
        super().__init__(db, RewardRedemption)

    async def has_used_welcome(self, member_id: int) -> bool:
        stmt = select(func.count(RewardRedemption.id)).where(
            and_(
                RewardRedemption.member_id == member_id,
                RewardRedemption.points_spent == 0,
                RewardRedemption.status == "used",
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one() > 0

    async def get_by_order(
        self, order_id: int
    ) -> list[RewardRedemption]:
        stmt = select(RewardRedemption).where(
            RewardRedemption.order_id == order_id
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


# ── ReferralLinkRepository ────────────────────────────────────────────────────


class AsyncReferralLinkRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def count_referrals(self, sponsor_member_id: int) -> int:
        stmt = select(func.count(ReferralLink.id)).where(
            ReferralLink.sponsor_member_id == sponsor_member_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_pending_referral(
        self, referred_member_id: int
    ) -> Optional[ReferralLink]:
        """Lien de parrainage en attente de credit."""
        stmt = select(ReferralLink).where(
            and_(
                ReferralLink.referred_member_id == referred_member_id,
                ReferralLink.credited_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, link: ReferralLink) -> ReferralLink:
        self.db.add(link)
        await self.db.flush()
        return link


# ── FlashOfferRepository ──────────────────────────────────────────────────────


class AsyncFlashOfferRepository(AsyncBaseRepository["FlashOffer"]):

    def __init__(self, db: AsyncSession):
        super().__init__(db, FlashOffer)

    async def get_active_offer(
        self, program_id: int, tenant_id: int, member_tier: str
    ) -> Optional[FlashOffer]:
        """Offre flash active applicable au membre."""
        now = datetime.now(timezone.utc)
        conditions = [
            FlashOffer.tenant_id == tenant_id,
            FlashOffer.program_id == program_id,
            FlashOffer.status == "active",
            FlashOffer.starts_at <= now,
            FlashOffer.ends_at > now,
        ]
        if member_tier != "vip":
            conditions.append(FlashOffer.target == "all")

        stmt = select(FlashOffer).where(and_(*conditions)).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_scheduled(self, tenant_id: int) -> list[FlashOffer]:
        stmt = select(FlashOffer).where(
            and_(
                FlashOffer.tenant_id == tenant_id,
                FlashOffer.status == "scheduled",
            )
        ).order_by(FlashOffer.starts_at.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


# ── WalletPassRepository ──────────────────────────────────────────────────────


class AsyncWalletPassRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_serial(self, serial_number: str) -> Optional[WalletPass]:
        stmt = select(WalletPass).where(
            WalletPass.serial_number == serial_number
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_member(self, member_id: int) -> list[WalletPass]:
        stmt = select(WalletPass).where(
            and_(
                WalletPass.member_id == member_id,
                WalletPass.status == "active",
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, wallet_pass: WalletPass) -> WalletPass:
        self.db.add(wallet_pass)
        await self.db.flush()
        return wallet_pass

    async def get_by_device(
        self, device_id: str, pass_type_id: str
    ) -> list[WalletPass]:
        stmt = select(WalletPass).where(
            and_(
                WalletPass.device_id == device_id,
                WalletPass.status == "active",
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


# ── TierHistoryRepository ────────────────────────────────────────────────────


class AsyncTierHistoryRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, entry: TierHistory) -> TierHistory:
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def list_by_member(
        self, member_id: int, limit: int = 20
    ) -> list[TierHistory]:
        stmt = (
            select(TierHistory)
            .where(TierHistory.member_id == member_id)
            .order_by(TierHistory.evaluated_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


# ── NotificationLogRepository ─────────────────────────────────────────────────


class AsyncLoyaltyNotifLogRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def has_been_sent(
        self, member_id: int, notif_type: str, since: datetime
    ) -> bool:
        """Verifie si une notification a deja ete envoyee depuis la date."""
        stmt = select(func.count(LoyaltyNotificationLog.id)).where(
            and_(
                LoyaltyNotificationLog.member_id == member_id,
                LoyaltyNotificationLog.notif_type == notif_type,
                LoyaltyNotificationLog.sent_at >= since,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one() > 0

    async def log_sent(
        self, member_id: int, notif_type: str, channel: str
    ) -> LoyaltyNotificationLog:
        entry = LoyaltyNotificationLog(
            member_id=member_id,
            notif_type=notif_type,
            channel=channel,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry
