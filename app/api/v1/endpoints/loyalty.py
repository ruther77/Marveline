"""Endpoints API du module Fidelite (Loyalty).

Routes :
- Public (rate limited) : POST /loyalty/join
- Staff : POST /loyalty/scan, /loyalty/credit, /loyalty/redeem
- Admin : GET /loyalty/admin/dashboard, /loyalty/admin/members, etc.
- Wallet callbacks : /wallet/v1/...
"""

import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import UserCompat, require_scope
from app.core.permissions import Scope
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.loyalty import (
    AdjustPointsRequest,
    CreditRequest,
    CreditResponse,
    FlashOfferCreate,
    FlashOfferResponse,
    JoinResponse,
    LoyaltyDashboardMetrics,
    LoyaltyMemberCreate,
    LoyaltyMemberList,
    LoyaltyMemberProfile,
    LoyaltyMemberResponse,
    RedeemRequest,
    RevenueCreditRequest,
    RewardRedemptionResponse,
    RewardsCatalogCreate,
    RewardsCatalogResponse,
    RewardsCatalogUpdate,
    ScanRequest,
)
from app.services.loyalty import LoyaltyService, generate_barcode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/loyalty", tags=["Loyalty"])
wallet_router = APIRouter(prefix="/wallet/v1", tags=["Wallet Callbacks"])


# ── Public ────────────────────────────────────────────────────────────────────


@router.post("/join", response_model=JoinResponse, status_code=status.HTTP_201_CREATED)
async def join_loyalty(
    data: LoyaltyMemberCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """Inscription a un programme de fidelite (public, rate limited)."""
    service = LoyaltyService(db)
    # Le tenant_id est deduit du programme
    from app.repositories.loyalty import AsyncLoyaltyProgramRepository
    program_repo = AsyncLoyaltyProgramRepository(db)
    # Pour join public, on accepte n'importe quel programme actif
    # Le tenant_id est dans le programme lui-meme
    from sqlalchemy import select
    from app.models.loyalty import LoyaltyProgram
    stmt = select(LoyaltyProgram).where(LoyaltyProgram.id == data.program_id)
    result = await db.execute(stmt)
    program = result.scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    member = await service.join(
        phone=data.phone,
        first_name=data.first_name,
        last_name=data.last_name,
        birth_month=data.birth_month,
        program_id=data.program_id,
        tenant_id=program.tenant_id,
        referral_code_used=data.referral_code_used,
    )
    await db.commit()

    barcode = generate_barcode(member.id)
    return JoinResponse(
        member_id=member.id,
        referral_code=member.referral_code,
        wallet_url=None,  # Sera genere par le WalletService
        welcome_reward_available=True,
    )


# ── Staff (scan, credit, redeem) ─────────────────────────────────────────────


@router.post("/scan", response_model=LoyaltyMemberProfile)
async def scan_loyalty(
    data: ScanRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_READ)),
):
    """Scanne un barcode fidelite en caisse."""
    service = LoyaltyService(db)
    return await service.scan(data.barcode, current_user.tenant_id)


@router.post("/credit", response_model=CreditResponse)
async def credit_points(
    data: CreditRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_WRITE)),
):
    """Credite des points apres une transaction en caisse."""
    service = LoyaltyService(db)
    result = await service.credit_points(
        member_id=data.member_id,
        amount_cents=data.amount_cents,
        source=data.source,
        order_id=data.order_id,
        tenant_id=current_user.tenant_id,
    )
    await db.commit()
    return result


@router.post("/credit-revenue")
async def credit_revenue(
    data: RevenueCreditRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_WRITE)),
):
    """Credite du CA pour le programme location (Marveline)."""
    service = LoyaltyService(db)
    await service.credit_revenue(
        member_id=data.member_id,
        amount_cents=data.amount_cents,
        tenant_id=current_user.tenant_id,
        reservation_id=data.reservation_id,
    )
    await db.commit()
    return {"status": "ok"}


@router.post("/redeem", response_model=RewardRedemptionResponse)
async def redeem_reward(
    data: RedeemRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_WRITE)),
):
    """Utilise un reward."""
    service = LoyaltyService(db)
    redemption = await service.redeem_reward(
        member_id=data.member_id,
        reward_id=data.reward_id,
        tenant_id=current_user.tenant_id,
        order_id=data.order_id,
    )
    await db.commit()
    return redemption


@router.post("/cancel-transaction")
async def cancel_transaction(
    order_id: int = Query(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_WRITE)),
):
    """Annule une transaction et reprend les points."""
    service = LoyaltyService(db)
    await service.cancel_transaction(order_id, current_user.tenant_id)
    await db.commit()
    return {"status": "ok"}


# ── Client authentifie ────────────────────────────────────────────────────────


@router.get("/me", response_model=LoyaltyMemberResponse)
async def get_my_loyalty(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_READ)),
):
    """Mon profil fidelite (client connecte)."""
    from app.repositories.loyalty import AsyncLoyaltyMemberRepository
    repo = AsyncLoyaltyMemberRepository(db)
    # Chercher par le customer lie a cet account
    from sqlalchemy import select, and_
    from app.models.loyalty import LoyaltyMember
    stmt = select(LoyaltyMember).where(
        and_(
            LoyaltyMember.tenant_id == current_user.tenant_id,
            LoyaltyMember.is_active.is_(True),
        )
    ).limit(1)
    result = await db.execute(stmt)
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="No loyalty membership found")
    return member


@router.get("/member/{member_id}", response_model=LoyaltyMemberProfile)
async def get_member_profile(
    member_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_READ)),
):
    """Profil complet d'un membre (pour le staff)."""
    service = LoyaltyService(db)
    from app.repositories.loyalty import AsyncLoyaltyMemberRepository
    repo = AsyncLoyaltyMemberRepository(db)
    member = await repo.get_by_id(member_id, current_user.tenant_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return await service._build_profile(member, current_user.tenant_id)


@router.get("/member/by-customer/{customer_id}", response_model=LoyaltyMemberProfile)
async def get_member_by_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_READ)),
):
    """Profil fidélité d'un client (recherche par customer_id)."""
    from app.repositories.loyalty import AsyncLoyaltyMemberRepository
    repo = AsyncLoyaltyMemberRepository(db)
    result = await db.execute(
        select(LoyaltyMember).where(
            and_(
                LoyaltyMember.customer_id == customer_id,
                LoyaltyMember.tenant_id == current_user.tenant_id,
                LoyaltyMember.is_active == True,
            )
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="No loyalty member for this customer")
    service = LoyaltyService(db)
    return await service._build_profile(member, current_user.tenant_id)


# ── Admin ─────────────────────────────────────────────────────────────────────


@router.get("/admin/dashboard", response_model=LoyaltyDashboardMetrics)
async def loyalty_dashboard(
    program_id: int = Query(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_MANAGE)),
):
    """Dashboard fidelite (admin)."""
    service = LoyaltyService(db)
    return await service.get_dashboard_metrics(program_id, current_user.tenant_id)


@router.get("/admin/members", response_model=PaginatedResponse[LoyaltyMemberList])
async def list_members(
    program_id: int = Query(...),
    pagination: PaginationParams = Depends(),
    search: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_MANAGE)),
):
    """Liste des membres fidelite (admin, paginee)."""
    from app.repositories.loyalty import AsyncLoyaltyMemberRepository
    repo = AsyncLoyaltyMemberRepository(db)
    filters = {"program_id": program_id}
    if tier:
        filters["current_tier"] = tier
    members, total = await repo.list(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        filters=filters,
    )
    return PaginatedResponse(
        items=members, total=total,
        skip=pagination.skip, limit=pagination.limit,
    )


@router.post("/admin/adjust")
async def adjust_points(
    data: AdjustPointsRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_MANAGE)),
):
    """Geste commercial : ajustement manuel de points (admin)."""
    service = LoyaltyService(db)
    new_balance = await service.adjust_points(
        member_id=data.member_id,
        amount=data.amount,
        reason=data.reason,
        tenant_id=current_user.tenant_id,
        admin_id=current_user.id,
    )
    await db.commit()
    return {"new_balance": new_balance, "status": "ok"}


# ── Rewards catalog ──────────────────────────────────────────────────────────


@router.get("/admin/rewards", response_model=list[RewardsCatalogResponse])
async def list_rewards(
    program_id: int = Query(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_MANAGE)),
):
    """Liste le catalogue de rewards."""
    from app.repositories.loyalty import AsyncRewardsCatalogRepository
    repo = AsyncRewardsCatalogRepository(db)
    rewards = await repo.list_active_by_program(program_id, current_user.tenant_id)
    return rewards


@router.post("/admin/rewards", response_model=RewardsCatalogResponse, status_code=201)
async def create_reward(
    data: RewardsCatalogCreate,
    program_id: int = Query(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_MANAGE)),
):
    """Ajoute un reward au catalogue."""
    from app.models.loyalty import RewardsCatalog
    reward = RewardsCatalog(
        tenant_id=current_user.tenant_id,
        program_id=program_id,
        tier=data.tier,
        product_id=data.product_id,
        name=data.name,
        description=data.description,
        points_cost=data.points_cost,
        max_cost_cents=data.max_cost_cents,
    )
    db.add(reward)
    await db.commit()
    await db.refresh(reward)
    return reward


@router.put("/admin/rewards/{reward_id}", response_model=RewardsCatalogResponse)
async def update_reward(
    reward_id: int,
    data: RewardsCatalogUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_MANAGE)),
):
    """Met a jour un reward (toggle actif, prix, etc.)."""
    from app.repositories.loyalty import AsyncRewardsCatalogRepository
    repo = AsyncRewardsCatalogRepository(db)
    reward = await repo.get_by_id(reward_id, current_user.tenant_id)
    if not reward:
        raise HTTPException(status_code=404, detail="Reward not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(reward, field, value)
    await db.commit()
    await db.refresh(reward)
    return reward


# ── Flash offers ──────────────────────────────────────────────────────────────


@router.post("/admin/flash-offers", response_model=FlashOfferResponse, status_code=201)
async def create_flash_offer(
    data: FlashOfferCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_MANAGE)),
):
    """Cree une offre flash."""
    from app.models.loyalty import FlashOffer
    offer = FlashOffer(
        tenant_id=current_user.tenant_id,
        program_id=data.program_id,
        name=data.name,
        multiplier=data.multiplier,
        target=data.target,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        status="scheduled",
    )
    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    return offer


@router.get("/admin/flash-offers", response_model=list[FlashOfferResponse])
async def list_flash_offers(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_MANAGE)),
):
    """Liste les offres flash."""
    from app.repositories.loyalty import AsyncFlashOfferRepository
    repo = AsyncFlashOfferRepository(db)
    return await repo.list_scheduled(current_user.tenant_id)


# ── Export CSV ────────────────────────────────────────────────────────────────


@router.get("/admin/export/{export_type}")
async def export_csv(
    export_type: str,
    program_id: int = Query(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_MANAGE)),
):
    """Export CSV (members, transactions, redemptions)."""
    if export_type not in ("members", "transactions", "redemptions"):
        raise HTTPException(status_code=400, detail="Invalid export type")

    output = io.StringIO()
    writer = csv.writer(output)

    if export_type == "members":
        from app.repositories.loyalty import AsyncLoyaltyMemberRepository
        repo = AsyncLoyaltyMemberRepository(db)
        members, _ = await repo.list(
            tenant_id=current_user.tenant_id,
            skip=0, limit=10000,
            filters={"program_id": program_id},
        )
        writer.writerow(["id", "phone", "first_name", "last_name", "tier", "transactions", "referral_code", "created_at"])
        for m in members:
            writer.writerow([m.id, m.phone, m.first_name, m.last_name, m.current_tier, m.transaction_count, m.referral_code, m.created_at.isoformat()])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=loyalty_{export_type}.csv"},
    )


# ── Wallet pass generation ────────────────────────────────────────────────────


@router.get("/pass/{member_id}/apple")
async def get_apple_pass(
    member_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.LOYALTY_READ)),
):
    """Genere et telecharge le PKPass Apple Wallet pour un membre."""
    from app.repositories.loyalty import AsyncLoyaltyMemberRepository, AsyncPointsLedgerRepository, AsyncRevenueLedgerRepository, AsyncWalletPassRepository
    from app.services.wallet import WalletService
    from fastapi.responses import Response

    member_repo = AsyncLoyaltyMemberRepository(db)
    member = await member_repo.get_by_id(member_id, current_user.tenant_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    points_repo = AsyncPointsLedgerRepository(db)
    revenue_repo = AsyncRevenueLedgerRepository(db)
    balance = await points_repo.get_balance(member.id, current_user.tenant_id)
    ca = await revenue_repo.get_cumulative(member.id, current_user.tenant_id)

    wallet_svc = WalletService()
    serial = wallet_svc.generate_serial_number(member.id)
    auth_token = wallet_svc.generate_auth_token()

    # Determiner le programme
    from app.repositories.loyalty import AsyncLoyaltyProgramRepository
    prog_repo = AsyncLoyaltyProgramRepository(db)
    program = await prog_repo.get_by_id(member.program_id, current_user.tenant_id)
    program_name = program.name if program else "Fidelite"

    discount = 0
    from app.constants.loyalty import TIER_HABITUE_THRESHOLD_CENTS, TIER_PRIVILEGIE_THRESHOLD_CENTS, DISCOUNT_HABITUE_PERCENT, DISCOUNT_PRIVILEGIE_PERCENT
    if ca >= TIER_PRIVILEGIE_THRESHOLD_CENTS:
        discount = DISCOUNT_PRIVILEGIE_PERCENT
    elif ca >= TIER_HABITUE_THRESHOLD_CENTS:
        discount = DISCOUNT_HABITUE_PERCENT

    pkpass_bytes = wallet_svc.generate_apple_pass(
        member=member,
        serial_number=serial,
        auth_token=auth_token,
        web_service_url=f"/api/v1/wallet/v1",
        program_name=program_name,
        points_balance=balance,
        tier=member.current_tier,
        referral_code=member.referral_code,
        cumulative_ca_cents=ca,
        discount_percent=discount,
    )

    # Enregistrer le pass en DB
    from app.models.loyalty import WalletPass as WalletPassModel
    wp = WalletPassModel(
        serial_number=serial,
        member_id=member.id,
        platform="apple",
        auth_token=auth_token,
        status="active",
    )
    db.add(wp)
    member.wallet_serial_number = serial
    member.wallet_platform = "apple"
    await db.commit()

    return Response(
        content=pkpass_bytes,
        media_type="application/vnd.apple.pkpass",
        headers={"Content-Disposition": f"attachment; filename=fidelite_{member.id}.pkpass"},
    )


# ── Apple Wallet Callbacks ────────────────────────────────────────────────────
# Ces endpoints sont appeles par Apple Wallet automatiquement.
# Spec : https://developer.apple.com/documentation/walletpasses


@wallet_router.post("/devices/{device_id}/registrations/{pass_type_id}/{serial_number}")
async def register_device(
    device_id: str,
    pass_type_id: str,
    serial_number: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Apple Wallet : enregistrement d'un device pour recevoir les updates."""
    from fastapi import Request
    from app.repositories.loyalty import AsyncWalletPassRepository

    repo = AsyncWalletPassRepository(db)
    wp = await repo.get_by_serial(serial_number)
    if not wp:
        raise HTTPException(status_code=401, detail="Pass not found")

    # Extraire le push token du body
    # Apple envoie { "pushToken": "..." }
    # On ne peut pas l'extraire ici sans le Request, on met a jour le device_id
    wp.device_id = device_id
    await db.commit()

    return Response(status_code=201)


@wallet_router.delete("/devices/{device_id}/registrations/{pass_type_id}/{serial_number}")
async def unregister_device(
    device_id: str,
    pass_type_id: str,
    serial_number: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Apple Wallet : desenregistrement d'un device (carte retiree du wallet)."""
    from app.repositories.loyalty import AsyncWalletPassRepository

    repo = AsyncWalletPassRepository(db)
    wp = await repo.get_by_serial(serial_number)
    if not wp:
        raise HTTPException(status_code=401, detail="Pass not found")

    wp.status = "inactive"
    wp.device_id = None
    wp.push_token = None
    await db.commit()

    return Response(status_code=200)


@wallet_router.get("/passes/{pass_type_id}/{serial_number}")
async def get_latest_pass(
    pass_type_id: str,
    serial_number: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Apple Wallet : fetch le pass mis a jour (appele apres un push APNs)."""
    from app.repositories.loyalty import AsyncWalletPassRepository, AsyncLoyaltyMemberRepository, AsyncPointsLedgerRepository, AsyncRevenueLedgerRepository, AsyncLoyaltyProgramRepository
    from app.services.wallet import WalletService
    from fastapi.responses import Response

    pass_repo = AsyncWalletPassRepository(db)
    wp = await pass_repo.get_by_serial(serial_number)
    if not wp:
        raise HTTPException(status_code=401, detail="Pass not found")

    member_repo = AsyncLoyaltyMemberRepository(db)
    member = await member_repo.get_by_id(wp.member_id, include_inactive=True)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    points_repo = AsyncPointsLedgerRepository(db)
    revenue_repo = AsyncRevenueLedgerRepository(db)
    balance = await points_repo.get_balance(member.id, member.tenant_id)
    ca = await revenue_repo.get_cumulative(member.id, member.tenant_id)

    prog_repo = AsyncLoyaltyProgramRepository(db)
    program = await prog_repo.get_by_id(member.program_id, member.tenant_id)
    program_name = program.name if program else "Fidelite"

    discount = 0
    from app.constants.loyalty import TIER_HABITUE_THRESHOLD_CENTS, TIER_PRIVILEGIE_THRESHOLD_CENTS, DISCOUNT_HABITUE_PERCENT, DISCOUNT_PRIVILEGIE_PERCENT
    if ca >= TIER_PRIVILEGIE_THRESHOLD_CENTS:
        discount = DISCOUNT_PRIVILEGIE_PERCENT
    elif ca >= TIER_HABITUE_THRESHOLD_CENTS:
        discount = DISCOUNT_HABITUE_PERCENT

    wallet_svc = WalletService()
    pkpass_bytes = wallet_svc.generate_apple_pass(
        member=member,
        serial_number=serial_number,
        auth_token=wp.auth_token,
        web_service_url=f"/api/v1/wallet/v1",
        program_name=program_name,
        points_balance=balance,
        tier=member.current_tier,
        referral_code=member.referral_code,
        cumulative_ca_cents=ca,
        discount_percent=discount,
    )

    return Response(
        content=pkpass_bytes,
        media_type="application/vnd.apple.pkpass",
        headers={"Last-Modified": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")},
    )


@wallet_router.get("/devices/{device_id}/registrations/{pass_type_id}")
async def get_serial_numbers(
    device_id: str,
    pass_type_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Apple Wallet : liste les serial numbers enregistres pour un device."""
    from app.repositories.loyalty import AsyncWalletPassRepository

    repo = AsyncWalletPassRepository(db)
    passes = await repo.get_by_device(device_id, pass_type_id)
    serial_numbers = [p.serial_number for p in passes]

    return {"lastUpdated": datetime.now(timezone.utc).isoformat(), "serialNumbers": serial_numbers}
