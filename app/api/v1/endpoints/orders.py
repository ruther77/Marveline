"""Endpoint agrégateur commandes unifiées (devis + réservations + ventes)."""
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.errors import ErrorMessages
from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.core.exceptions import NotFound
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.orders import OrderItem, OrderDetail
from app.services.orders import list_orders, get_order_detail

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=PaginatedResponse[OrderItem])
async def get_orders(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(default=None),
    order_type: Optional[str] = Query(default=None, description="devis | reservation | vente"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> PaginatedResponse[OrderItem]:
    """Liste unifiée des commandes (devis + réservations + ventes), triée par date desc."""
    return await list_orders(
        db=db,
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        status=status,
        order_type=order_type,
    )


@router.get("/{order_type}/{order_id}", response_model=OrderDetail)
async def get_order(
    order_type: str,
    order_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> OrderDetail:
    """Détail complet d'une commande (devis / réservation / vente)."""
    if order_type not in ("devis", "reservation", "vente"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="order_type must be devis, reservation, or vente")
    try:
        return await get_order_detail(
            db=db, tenant_id=current_user.tenant_id,
            order_type=order_type, order_id=order_id,
        )
    except NotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
