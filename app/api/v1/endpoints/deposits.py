"""Endpoints cautions (deposits) — vue globale admin."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.common import PaginatedResponse
from app.schemas.deposit import DepositWithReservation, DepositSummary
from app.services.deposit import DepositService

router = APIRouter(prefix="/deposits", tags=["deposits"])


@router.get("", response_model=PaginatedResponse[DepositWithReservation])
async def list_all_deposits(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
    status: str | None = Query(default=None, description="Filtrer par statut (held/released/retained)"),
    date_from: date | None = Query(default=None, description="Date de creation min"),
    date_to: date | None = Query(default=None, description="Date de creation max"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> PaginatedResponse[DepositWithReservation]:
    """Liste toutes les cautions du tenant avec filtres et pagination."""
    service = DepositService(db)
    items, total = await service.list_all_deposits(
        tenant_id=current_user.tenant_id,
        deposit_status=status,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/summary", response_model=DepositSummary)
async def get_deposits_summary(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> DepositSummary:
    """KPI agreges des cautions du tenant."""
    service = DepositService(db)
    return await service.get_summary(current_user.tenant_id)
