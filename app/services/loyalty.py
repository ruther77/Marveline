"""Service principal du module Fidelite (Loyalty).

Logique metier pour les deux programmes :
- L'Incontournable (restau + epicerie) : points, rewards, parrainage
- Marveline (location) : remise par palier CA cumule
"""

import hashlib
import hmac
import logging
import math
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.errors import ErrorMessages
from app.constants.loyalty import (
    CHURN_RISK_MAX_DAYS,
    CHURN_RISK_MIN_DAYS,
    DISCOUNT_HABITUE_PERCENT,
    DISCOUNT_PRIVILEGIE_PERCENT,
    MAX_REFERRALS_PER_MEMBER,
    POINTS_EXPIRY_MONTHS_BONUS,
    POINTS_EXPIRY_MONTHS_EARNED,
    POINTS_PER_EUR_EPICERIE,
    POINTS_PER_EUR_RESTAURANT,
    REFERRAL_BONUS_POINTS,
    REFERRAL_CODE_DIGITS,
    REVENUE_WINDOW_MONTHS,
    REWARD_TIER_1_COST,
    REWARD_TIER_2_COST,
    REWARD_TIER_3_COST,
    TIER_HABITUE_THRESHOLD_CENTS,
    TIER_PRIVILEGIE_THRESHOLD_CENTS,
    VIP_GRACE_DAYS,
    VIP_MULTIPLIER,
    VIP_THRESHOLD_POINTS_PER_YEAR,
)
from app.core.config import settings
from app.models.loyalty import (
    LoyaltyMember,
    LoyaltyProgram,
    PointsLedger,
    ReferralLink,
    RevenueLedger,
    RewardRedemption,
    TierHistory,
)
from app.repositories.loyalty import (
    AsyncFlashOfferRepository,
    AsyncLoyaltyMemberRepository,
    AsyncLoyaltyProgramRepository,
    AsyncPointsLedgerRepository,
    AsyncReferralLinkRepository,
    AsyncRevenueLedgerRepository,
    AsyncRewardRedemptionRepository,
    AsyncRewardsCatalogRepository,
    AsyncTierHistoryRepository,
)
from app.schemas.loyalty import (
    CreditResponse,
    LoyaltyDashboardMetrics,
    LoyaltyMemberProfile,
    RewardAvailable,
    TopReferrer,
)

logger = logging.getLogger(__name__)

# Clé HMAC pour les barcodes — provient de la config
_BARCODE_SECRET_KEY = getattr(settings, "LOYALTY_BARCODE_SECRET", "loyalty-barcode-default-key")


def _base58_encode(data: bytes) -> str:
    """Encode bytes en Base58 (sans caracteres ambigus)."""
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    num = int.from_bytes(data, "big")
    if num == 0:
        return alphabet[0]
    result = []
    while num > 0:
        num, remainder = divmod(num, 58)
        result.append(alphabet[remainder])
    return "".join(reversed(result))


def generate_barcode(member_id: int) -> str:
    """Genere un barcode HMAC-SHA256 Base58 pour un membre."""
    msg = str(member_id).encode()
    sig = hmac.new(_BARCODE_SECRET_KEY.encode(), msg, hashlib.sha256).digest()
    return f"{member_id}-{_base58_encode(sig[:16])}"


def verify_barcode(barcode: str) -> Optional[int]:
    """Verifie un barcode et retourne le member_id, ou None si invalide."""
    parts = barcode.split("-", 1)
    if len(parts) != 2:
        return None
    try:
        member_id = int(parts[0])
    except ValueError:
        return None
    expected = generate_barcode(member_id)
    if hmac.compare_digest(barcode, expected):
        return member_id
    return None


def generate_referral_code(first_name: str) -> str:
    """Genere un code parrain PRENOM + N chiffres (ex: JEAN4827)."""
    clean_name = first_name.strip().upper()[:10]
    digits = "".join(random.choices(string.digits, k=REFERRAL_CODE_DIGITS))
    return f"{clean_name}{digits}"


class LoyaltyService:
    """Service principal fidelite."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.program_repo = AsyncLoyaltyProgramRepository(db)
        self.member_repo = AsyncLoyaltyMemberRepository(db)
        self.points_repo = AsyncPointsLedgerRepository(db)
        self.revenue_repo = AsyncRevenueLedgerRepository(db)
        self.rewards_repo = AsyncRewardsCatalogRepository(db)
        self.redemption_repo = AsyncRewardRedemptionRepository(db)
        self.referral_repo = AsyncReferralLinkRepository(db)
        self.flash_repo = AsyncFlashOfferRepository(db)
        self.tier_repo = AsyncTierHistoryRepository(db)

    # ── Inscription ───────────────────────────────────────────────────────

    async def join(
        self,
        phone: str,
        first_name: str,
        last_name: str,
        birth_month: Optional[int],
        program_id: int,
        tenant_id: int,
        referral_code_used: Optional[str] = None,
    ) -> LoyaltyMember:
        """Inscrit un nouveau membre au programme de fidelite."""
        program = await self.program_repo.get_by_id(program_id, tenant_id)
        if not program:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.LOYALTY_PROGRAM_NOT_FOUND,
            )

        existing = await self.member_repo.get_by_phone(phone, program_id, tenant_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorMessages.LOYALTY_MEMBER_ALREADY_EXISTS,
            )

        # Determiner le palier initial
        if program.program_type == "points":
            initial_tier = "standard"
        else:
            initial_tier = "nouveau"

        # Generer le code parrain unique
        referral_code = generate_referral_code(first_name)
        # Verifier unicite (retry si collision)
        for _ in range(10):
            check = await self.member_repo.get_by_referral_code(referral_code, tenant_id)
            if not check:
                break
            referral_code = generate_referral_code(first_name)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate unique referral code",
            )

        member = LoyaltyMember(
            tenant_id=tenant_id,
            program_id=program_id,
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            birth_month=birth_month,
            referral_code=referral_code,
            current_tier=initial_tier,
            transaction_count=0,
        )
        self.db.add(member)
        await self.db.flush()

        # Lier le parrainage si code fourni
        if referral_code_used:
            await self._link_referral(member, referral_code_used, tenant_id)

        return member

    async def _link_referral(
        self, member: LoyaltyMember, code: str, tenant_id: int
    ) -> None:
        """Lie un filleul a son parrain."""
        sponsor = await self.member_repo.get_by_referral_code(code, tenant_id)
        if not sponsor:
            logger.warning("Referral code %s not found for tenant %d", code, tenant_id)
            return

        if sponsor.id == member.id:
            return

        count = await self.referral_repo.count_referrals(sponsor.id)
        if count >= MAX_REFERRALS_PER_MEMBER:
            logger.info("Sponsor %d reached referral limit", sponsor.id)
            return

        link = ReferralLink(
            sponsor_member_id=sponsor.id,
            referred_member_id=member.id,
        )
        await self.referral_repo.create(link)

    # ── Scan barcode ──────────────────────────────────────────────────────

    async def scan(
        self, barcode: str, tenant_id: int
    ) -> LoyaltyMemberProfile:
        """Scanne un barcode et retourne le profil du membre."""
        member_id = verify_barcode(barcode)
        if member_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.LOYALTY_BARCODE_INVALID,
            )

        member = await self.member_repo.get_by_id(member_id, tenant_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.LOYALTY_MEMBER_NOT_FOUND,
            )

        return await self._build_profile(member, tenant_id)

    async def _build_profile(
        self, member: LoyaltyMember, tenant_id: int
    ) -> LoyaltyMemberProfile:
        """Construit le profil complet d'un membre (pour affichage caissier)."""
        points_balance = await self.points_repo.get_balance(member.id, tenant_id)
        cumulative_ca = await self.revenue_repo.get_cumulative(member.id, tenant_id)

        # Calculer la remise applicable (programme location)
        discount = 0
        if cumulative_ca >= TIER_PRIVILEGIE_THRESHOLD_CENTS:
            discount = DISCOUNT_PRIVILEGIE_PERCENT
        elif cumulative_ca >= TIER_HABITUE_THRESHOLD_CENTS:
            discount = DISCOUNT_HABITUE_PERCENT

        # Rewards disponibles
        available_rewards = await self._get_available_rewards(member, points_balance)
        has_welcome = not await self.redemption_repo.has_used_welcome(member.id)

        return LoyaltyMemberProfile(
            member_id=member.id,
            first_name=member.first_name,
            last_name=member.last_name,
            current_tier=member.current_tier,
            points_balance=points_balance,
            cumulative_ca_cents=cumulative_ca,
            discount_percent=discount,
            available_rewards=available_rewards,
            has_welcome_reward=has_welcome and member.transaction_count == 0,
        )

    async def _get_available_rewards(
        self, member: LoyaltyMember, balance: int
    ) -> list[RewardAvailable]:
        """Liste les rewards que le membre peut utiliser."""
        rewards = await self.rewards_repo.list_active_by_program(
            member.program_id, member.tenant_id
        )
        available = []
        for r in rewards:
            if r.tier == "welcome":
                continue  # Gere separement
            if r.points_cost <= balance:
                available.append(RewardAvailable(
                    reward_id=r.id,
                    name=r.name,
                    tier=r.tier,
                    points_cost=r.points_cost,
                ))
        return available

    # ── Credit de points ──────────────────────────────────────────────────

    async def credit_points(
        self,
        member_id: int,
        amount_cents: int,
        source: str,
        order_id: int,
        tenant_id: int,
    ) -> CreditResponse:
        """Credite des points apres une transaction."""
        member = await self.member_repo.get_by_id(member_id, tenant_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.LOYALTY_MEMBER_NOT_FOUND,
            )

        # Verifier double scan
        existing = await self.points_repo.get_entries_by_order(order_id, tenant_id)
        if any(e.entry_type == "earn" for e in existing):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorMessages.LOYALTY_DOUBLE_SCAN,
            )

        # Calculer les points
        amount_eur = amount_cents / 100
        if source == "restaurant":
            base_points = POINTS_PER_EUR_RESTAURANT
        else:
            base_points = POINTS_PER_EUR_EPICERIE

        raw_points = amount_eur * base_points

        # Multiplicateur VIP
        multiplier = 1.0
        if member.current_tier == "vip":
            multiplier *= VIP_MULTIPLIER

        # Multiplicateur flash offer (cumulatif)
        flash_multiplier = None
        flash_offer = await self.flash_repo.get_active_offer(
            member.program_id, tenant_id, member.current_tier
        )
        if flash_offer:
            multiplier *= float(flash_offer.multiplier)
            flash_multiplier = float(flash_offer.multiplier)

        points = math.ceil(raw_points * multiplier)

        # Calculer expiration
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=POINTS_EXPIRY_MONTHS_EARNED * 30)

        # Obtenir le solde actuel
        last_entry = await self.points_repo.get_last_entry(member.id, tenant_id)
        current_balance = last_entry.balance_after if last_entry else 0
        new_balance = current_balance + points

        # Inserer l'entree
        entry = PointsLedger(
            tenant_id=tenant_id,
            member_id=member.id,
            order_id=order_id,
            amount=points,
            entry_type="earn",
            source=source,
            balance_after=new_balance,
            expires_at=expires_at,
            metadata_json={"flash_offer_id": flash_offer.id} if flash_offer else None,
        )
        await self.points_repo.append(entry)

        # Incrementer le compteur de transactions
        member.transaction_count += 1
        await self.db.flush()

        # Crediter le parrainage si c'est la 1ere transaction
        if member.transaction_count == 1:
            await self._credit_referral(member, tenant_id)

        return CreditResponse(
            points_added=points,
            new_balance=new_balance,
            tier=member.current_tier,
            flash_multiplier=flash_multiplier,
        )

    async def _credit_referral(
        self, member: LoyaltyMember, tenant_id: int
    ) -> None:
        """Credite les points de parrainage a la 1ere transaction du filleul."""
        link = await self.referral_repo.get_pending_referral(member.id)
        if not link:
            return

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=POINTS_EXPIRY_MONTHS_BONUS * 30)

        # Credit filleul
        last_entry = await self.points_repo.get_last_entry(member.id, tenant_id)
        balance = last_entry.balance_after if last_entry else 0
        await self.points_repo.append(PointsLedger(
            tenant_id=tenant_id,
            member_id=member.id,
            amount=REFERRAL_BONUS_POINTS,
            entry_type="bonus",
            source="referral",
            balance_after=balance + REFERRAL_BONUS_POINTS,
            expires_at=expires_at,
        ))

        # Credit parrain
        sponsor_last = await self.points_repo.get_last_entry(link.sponsor_member_id, tenant_id)
        sponsor_balance = sponsor_last.balance_after if sponsor_last else 0
        await self.points_repo.append(PointsLedger(
            tenant_id=tenant_id,
            member_id=link.sponsor_member_id,
            amount=REFERRAL_BONUS_POINTS,
            entry_type="bonus",
            source="referral",
            balance_after=sponsor_balance + REFERRAL_BONUS_POINTS,
            expires_at=expires_at,
        ))

        link.credited_at = now
        await self.db.flush()

    # ── Credit CA (programme location) ────────────────────────────────────

    async def credit_revenue(
        self,
        member_id: int,
        amount_cents: int,
        tenant_id: int,
        reservation_id: Optional[int] = None,
    ) -> None:
        """Credite du CA pour le programme location (Marveline)."""
        member = await self.member_repo.get_by_id(member_id, tenant_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.LOYALTY_MEMBER_NOT_FOUND,
            )

        last_entry = await self.revenue_repo.get_last_entry(member.id, tenant_id)
        current = last_entry.cumulative_after_cents if last_entry else 0
        new_cumulative = current + amount_cents

        entry_type = "purchase" if amount_cents >= 0 else "refund"

        entry = RevenueLedger(
            tenant_id=tenant_id,
            member_id=member.id,
            reservation_id=reservation_id,
            amount_cents=amount_cents,
            entry_type=entry_type,
            cumulative_after_cents=new_cumulative,
        )
        await self.revenue_repo.append(entry)

        member.transaction_count += 1
        await self.db.flush()

    # ── Redemption ────────────────────────────────────────────────────────

    async def redeem_reward(
        self,
        member_id: int,
        reward_id: int,
        tenant_id: int,
        order_id: Optional[int] = None,
    ) -> RewardRedemption:
        """Utilise un reward."""
        member = await self.member_repo.get_by_id(member_id, tenant_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.LOYALTY_MEMBER_NOT_FOUND,
            )

        reward = await self.rewards_repo.get_by_id(reward_id, tenant_id)
        if not reward or not reward.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.LOYALTY_REWARD_NOT_AVAILABLE,
            )

        # Welcome reward : gratuit, une seule fois
        if reward.tier == "welcome":
            if await self.redemption_repo.has_used_welcome(member.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=ErrorMessages.LOYALTY_WELCOME_ALREADY_USED,
                )
            points_to_spend = 0
        else:
            points_to_spend = reward.points_cost
            balance = await self.points_repo.get_balance(member.id, tenant_id)
            if balance < points_to_spend:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.LOYALTY_INSUFFICIENT_POINTS,
                )

        # Creer la redemption
        redemption = RewardRedemption(
            member_id=member.id,
            reward_id=reward_id,
            order_id=order_id,
            points_spent=points_to_spend,
            status="used",
        )
        self.db.add(redemption)
        await self.db.flush()

        # Debiter les points si necessaire
        if points_to_spend > 0:
            last_entry = await self.points_repo.get_last_entry(member.id, tenant_id)
            current_balance = last_entry.balance_after if last_entry else 0
            await self.points_repo.append(PointsLedger(
                tenant_id=tenant_id,
                member_id=member.id,
                order_id=order_id,
                amount=-points_to_spend,
                entry_type="redeem",
                source=None,
                balance_after=current_balance - points_to_spend,
            ))

        return redemption

    # ── Annulation de transaction ─────────────────────────────────────────

    async def cancel_transaction(
        self, order_id: int, tenant_id: int
    ) -> None:
        """Annule une transaction : reprend les points et revoque les rewards."""
        # Reprendre les points
        entries = await self.points_repo.get_entries_by_order(order_id, tenant_id)
        for entry in entries:
            if entry.entry_type in ("earn", "bonus") and entry.amount > 0:
                last = await self.points_repo.get_last_entry(entry.member_id, tenant_id)
                balance = last.balance_after if last else 0
                await self.points_repo.append(PointsLedger(
                    tenant_id=tenant_id,
                    member_id=entry.member_id,
                    order_id=order_id,
                    amount=-entry.amount,
                    entry_type="adjust",
                    source=None,
                    balance_after=balance - entry.amount,
                    metadata_json={"reason": "transaction_cancelled"},
                ))

        # Revoquer les rewards
        redemptions = await self.redemption_repo.get_by_order(order_id)
        now = datetime.now(timezone.utc)
        for r in redemptions:
            if r.status == "used":
                r.status = "revoked"
                r.revoked_at = now
                # Recrediter les points
                if r.points_spent > 0:
                    last = await self.points_repo.get_last_entry(r.member_id, tenant_id)
                    balance = last.balance_after if last else 0
                    await self.points_repo.append(PointsLedger(
                        tenant_id=tenant_id,
                        member_id=r.member_id,
                        order_id=order_id,
                        amount=r.points_spent,
                        entry_type="adjust",
                        source=None,
                        balance_after=balance + r.points_spent,
                        metadata_json={"reason": "reward_revoked"},
                    ))

        await self.db.flush()

    # ── Evaluation palier ─────────────────────────────────────────────────

    async def evaluate_tier(
        self, member_id: int, tenant_id: int
    ) -> Optional[TierHistory]:
        """Evalue et met a jour le palier d'un membre."""
        member = await self.member_repo.get_by_id(member_id, tenant_id)
        if not member:
            return None

        program = await self.program_repo.get_by_id(member.program_id, tenant_id)
        if not program:
            return None

        now = datetime.now(timezone.utc)

        if program.program_type == "points":
            return await self._evaluate_points_tier(member, tenant_id, now)
        else:
            return await self._evaluate_revenue_tier(member, tenant_id, now)

    async def _evaluate_points_tier(
        self, member: LoyaltyMember, tenant_id: int, now: datetime
    ) -> Optional[TierHistory]:
        """Evaluation palier programme L'Incontournable."""
        earned_year = await self.points_repo.get_points_earned_in_window(
            member.id, tenant_id, 12
        )

        if earned_year >= VIP_THRESHOLD_POINTS_PER_YEAR:
            target_tier = "vip"
        else:
            target_tier = "standard"

        return await self._apply_tier_change(member, target_tier, now)

    async def _evaluate_revenue_tier(
        self, member: LoyaltyMember, tenant_id: int, now: datetime
    ) -> Optional[TierHistory]:
        """Evaluation palier programme Marveline."""
        ca = await self.revenue_repo.get_cumulative_in_window(
            member.id, tenant_id, REVENUE_WINDOW_MONTHS
        )

        if ca >= TIER_PRIVILEGIE_THRESHOLD_CENTS:
            target_tier = "privilegie"
        elif ca >= TIER_HABITUE_THRESHOLD_CENTS:
            target_tier = "habitue"
        else:
            target_tier = "nouveau"

        return await self._apply_tier_change(member, target_tier, now)

    async def _apply_tier_change(
        self, member: LoyaltyMember, target_tier: str, now: datetime
    ) -> Optional[TierHistory]:
        """Applique le changement de palier avec gestion de la grace."""
        current = member.current_tier

        if target_tier == current:
            member.tier_evaluated_at = now
            member.grace_until = None
            await self.db.flush()
            return None

        # Upgrade : immediat
        tier_order = {"standard": 0, "vip": 1, "nouveau": 0, "habitue": 1, "privilegie": 2}
        if tier_order.get(target_tier, 0) > tier_order.get(current, 0):
            reason = f"upgrade: {current} → {target_tier}"
            return await self._record_tier_change(member, target_tier, reason, now)

        # Downgrade : grace d'abord
        if member.grace_until is None:
            member.grace_until = now + timedelta(days=VIP_GRACE_DAYS)
            member.tier_evaluated_at = now
            await self.db.flush()
            return None

        if now < member.grace_until:
            return None

        reason = f"downgrade: {current} → {target_tier} (grace expired)"
        return await self._record_tier_change(member, target_tier, reason, now)

    async def _record_tier_change(
        self, member: LoyaltyMember, new_tier: str, reason: str, now: datetime
    ) -> TierHistory:
        old_tier = member.current_tier
        member.current_tier = new_tier
        member.tier_evaluated_at = now
        member.grace_until = None

        entry = TierHistory(
            member_id=member.id,
            from_tier=old_tier,
            to_tier=new_tier,
            reason=reason,
            evaluated_at=now,
        )
        await self.tier_repo.create(entry)
        await self.db.flush()
        return entry

    # ── Ajustement manuel (geste commercial) ──────────────────────────────

    async def adjust_points(
        self,
        member_id: int,
        amount: int,
        reason: str,
        tenant_id: int,
        admin_id: int,
    ) -> int:
        """Ajuste manuellement les points d'un membre. Retourne le nouveau solde."""
        member = await self.member_repo.get_by_id(member_id, tenant_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.LOYALTY_MEMBER_NOT_FOUND,
            )

        last_entry = await self.points_repo.get_last_entry(member.id, tenant_id)
        current_balance = last_entry.balance_after if last_entry else 0
        new_balance = current_balance + amount

        await self.points_repo.append(PointsLedger(
            tenant_id=tenant_id,
            member_id=member.id,
            amount=amount,
            entry_type="adjust",
            source="manual",
            balance_after=new_balance,
            metadata_json={"reason": reason, "admin_id": admin_id},
        ))

        return new_balance

    # ── Dashboard ─────────────────────────────────────────────────────────

    async def get_dashboard_metrics(
        self, program_id: int, tenant_id: int
    ) -> LoyaltyDashboardMetrics:
        """Metriques du dashboard fidelite."""
        total = await self.member_repo.count_by_program(program_id, tenant_id)
        vip_count = await self.member_repo.count_by_tier(program_id, "vip", tenant_id)
        points_circulation = await self.points_repo.get_total_points_in_circulation(tenant_id)
        earned_month = await self.points_repo.get_points_this_month(tenant_id, "earn")
        redeemed_month = await self.points_repo.get_points_this_month(tenant_id, "redeem")
        at_risk = await self.member_repo.list_at_risk(
            program_id, tenant_id, CHURN_RISK_MIN_DAYS, CHURN_RISK_MAX_DAYS
        )

        redemption_rate = 0.0
        if earned_month > 0:
            redemption_rate = min(redeemed_month / earned_month, 1.0)

        return LoyaltyDashboardMetrics(
            total_members=total,
            active_members=total,
            vip_members=vip_count,
            total_points_in_circulation=points_circulation,
            points_earned_this_month=earned_month,
            points_redeemed_this_month=redeemed_month,
            redemption_rate=round(redemption_rate, 3),
            churn_risk_count=len(at_risk),
            top_referrers=[],
        )
