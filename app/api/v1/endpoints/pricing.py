"""Endpoints CRUD pour les règles de pricing."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants.errors import ErrorMessages
from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.models.pricing import PricingRule, PricingTier
from app.models.product import Product
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.pricing import (
    PricingRuleCreate,
    PricingRuleResponse,
    PricingRuleUpdate,
    PricingSimulateRequest,
    PricingSimulateResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pricing", tags=["Pricing"])


async def _get_or_404(rule_id: int, tenant_id: int, db: AsyncSession) -> PricingRule:
    result = await db.execute(
        select(PricingRule)
        .options(selectinload(PricingRule.tiers))
        .filter(
            PricingRule.id == rule_id,
            PricingRule.tenant_id == tenant_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.PRICING_RULE_NOT_FOUND,
        )
    return rule


@router.get("/rules", response_model=PaginatedResponse[PricingRuleResponse])
async def list_pricing_rules(
    active_only: bool = True,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRICING_READ)),
) -> PaginatedResponse[PricingRuleResponse]:
    """Liste les règles de pricing du tenant."""
    from sqlalchemy import func
    base = select(PricingRule).filter(PricingRule.tenant_id == current_user.tenant_id)
    if active_only:
        base = base.filter(PricingRule.active == True)  # noqa: E712
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar() or 0
    query = base.options(selectinload(PricingRule.tiers)).order_by(PricingRule.id)
    query = query.offset(pagination.skip).limit(pagination.limit)
    rules = (await db.execute(query)).scalars().all()
    return PaginatedResponse(
        items=[PricingRuleResponse.model_validate(r) for r in rules],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.post("/rules", response_model=PricingRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_pricing_rule(
    data: PricingRuleCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRICING_WRITE)),
) -> PricingRuleResponse:
    """Crée une règle de pricing."""
    now = datetime.now(tz=timezone.utc)
    rule = PricingRule(
        tenant_id=current_user.tenant_id,
        name=data.name,
        rule_type=data.rule_type,
        applies_to=data.applies_to,
        target_id=data.target_id,
        discount_pct=data.discount_pct,
        valid_from=data.valid_from,
        valid_to=data.valid_to,
        active=data.active,
        created_at=now,
        updated_at=now,
    )
    db.add(rule)
    await db.flush()

    for tier_data in data.tiers:
        tier = PricingTier(
            rule_id=rule.id,
            tenant_id=current_user.tenant_id,
            min_qty=tier_data.min_qty,
            max_qty=tier_data.max_qty,
            unit_price_cents=tier_data.unit_price_cents,
        )
        db.add(tier)

    await db.commit()
    return PricingRuleResponse.model_validate(
        await _get_or_404(rule.id, current_user.tenant_id, db)
    )


@router.get("/rules/{rule_id}", response_model=PricingRuleResponse)
async def get_pricing_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRICING_READ)),
) -> PricingRuleResponse:
    """Récupère une règle par ID."""
    rule = await _get_or_404(rule_id, current_user.tenant_id, db)
    return PricingRuleResponse.model_validate(rule)


@router.patch("/rules/{rule_id}", response_model=PricingRuleResponse)
async def update_pricing_rule(
    rule_id: int,
    data: PricingRuleUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRICING_WRITE)),
) -> PricingRuleResponse:
    """Met à jour une règle (PATCH partiel)."""
    rule = await _get_or_404(rule_id, current_user.tenant_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    rule.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    return PricingRuleResponse.model_validate(
        await _get_or_404(rule.id, current_user.tenant_id, db)
    )


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pricing_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRICING_WRITE)),
) -> None:
    """Soft-delete : désactive la règle (active=False)."""
    rule = await _get_or_404(rule_id, current_user.tenant_id, db)
    rule.active = False
    rule.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()


@router.get("/rules/product/{product_id}", response_model=PaginatedResponse[PricingRuleResponse])
async def get_rules_for_product(
    product_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRICING_READ)),
) -> PaginatedResponse[PricingRuleResponse]:
    """Retourne les règles applicables à un produit (product direct + all)."""
    rules = (await db.execute(
        select(PricingRule)
        .options(selectinload(PricingRule.tiers))
        .filter(
            PricingRule.tenant_id == current_user.tenant_id,
            PricingRule.active == True,  # noqa: E712
            PricingRule.applies_to.in_(["product", "all"]),
        ).filter(
            (PricingRule.target_id == product_id) | (PricingRule.applies_to == "all")
        ).order_by(PricingRule.id)
    )).scalars().all()
    items = [PricingRuleResponse.model_validate(r) for r in rules]
    return PaginatedResponse[PricingRuleResponse](items=items, total=len(items), skip=0, limit=max(len(items), 1))


@router.post("/simulate", response_model=PricingSimulateResponse)
async def simulate_pricing(
    data: PricingSimulateRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRICING_WRITE)),
) -> PricingSimulateResponse:
    """Simule le prix final d'un produit selon les règles de pricing actives.

    Applique la première règle trouvée par priorité : product > category > all.
    Pour les règles tiered, sélectionne le palier correspondant à la quantité.
    """
    simulation_date = data.simulation_date or datetime.now(tz=timezone.utc).date()

    # Récupérer le produit pour le prix de base
    product = (await db.execute(
        select(Product).filter(
            Product.id == data.product_id,
            Product.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produit {data.product_id} introuvable",
        )

    base_price = getattr(product, "price_per_day_cents", 0) or 0

    # Chercher les règles actives applicables (product-specific d'abord, puis all)
    rules_query = select(PricingRule).options(selectinload(PricingRule.tiers)).filter(
        PricingRule.tenant_id == current_user.tenant_id,
        PricingRule.active == True,  # noqa: E712
        or_(
            and_(PricingRule.applies_to == "product", PricingRule.target_id == data.product_id),
            PricingRule.applies_to == "all",
        ),
    ).filter(
        or_(PricingRule.valid_from == None, PricingRule.valid_from <= simulation_date),  # noqa
        or_(PricingRule.valid_to == None, PricingRule.valid_to >= simulation_date),  # noqa
    ).order_by(
        # Product-specific avant all
        (PricingRule.applies_to == "all").asc(),
        PricingRule.id.asc(),
    )
    rules = (await db.execute(rules_query)).scalars().all()

    applied_rule = None
    final_price = base_price
    discount_pct = None

    for rule in rules:
        if rule.rule_type == "tiered" and rule.tiers:
            # Trouver le palier correspondant à la quantité
            matching_tier = None
            for tier in sorted(rule.tiers, key=lambda t: t.min_qty):
                if tier.min_qty <= data.quantity:
                    if tier.max_qty is None or tier.max_qty >= data.quantity:
                        matching_tier = tier
                        break
            if matching_tier:
                applied_rule = rule
                final_price = matching_tier.unit_price_cents
                break
        elif rule.discount_pct is not None:
            applied_rule = rule
            discount_pct = rule.discount_pct
            final_price = round(base_price * (1 - rule.discount_pct / 10000))
            break

    total = final_price * data.quantity * data.rental_days

    return PricingSimulateResponse(
        product_id=data.product_id,
        quantity=data.quantity,
        rental_days=data.rental_days,
        base_unit_price_cents=base_price,
        applied_rule_id=applied_rule.id if applied_rule else None,
        applied_rule_name=applied_rule.name if applied_rule else None,
        discount_pct=discount_pct if discount_pct is not None else 0,
        final_unit_price_cents=final_price,
        total_cents=total,
    )
