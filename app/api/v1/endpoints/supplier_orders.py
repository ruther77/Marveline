"""Endpoints CRUD + workflow pour les commandes fournisseurs."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.supplier_order import (
    SupplierOrderCreate,
    SupplierOrderListItem,
    SupplierOrderRead,
    SupplierOrderReceiptCreate,
    SupplierOrderUpdate,
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services.supplier_order import SupplierOrderService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/supplier-orders", tags=["Supplier Orders"])


@router.get("", response_model=PaginatedResponse[SupplierOrderListItem])
async def list_orders(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(None),
    supplier_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_READ)),
) -> PaginatedResponse[SupplierOrderListItem]:
    """Liste paginée des commandes fournisseurs."""
    svc = SupplierOrderService(db)
    return await svc.list_orders(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        status=status,
        supplier_id=supplier_id,
    )


@router.post("", response_model=SupplierOrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: SupplierOrderCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_WRITE)),
) -> SupplierOrderRead:
    """Crée une commande fournisseur en statut draft."""
    svc = SupplierOrderService(db)
    order = await svc.create_order(data, current_user.tenant_id)
    return SupplierOrderRead.model_validate(order)


@router.get("/{order_id}", response_model=SupplierOrderRead)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_READ)),
) -> SupplierOrderRead:
    """Retourne une commande avec ses lignes et bons de réception."""
    svc = SupplierOrderService(db)
    order = await svc.get_order(order_id, current_user.tenant_id)
    return SupplierOrderRead.model_validate(order)


@router.patch("/{order_id}", response_model=SupplierOrderRead)
async def update_order(
    order_id: int,
    data: SupplierOrderUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_WRITE)),
) -> SupplierOrderRead:
    """Met à jour référence / dates / notes (hors statut)."""
    svc = SupplierOrderService(db)
    order = await svc.update_order(order_id, data, current_user.tenant_id)
    return SupplierOrderRead.model_validate(order)


@router.post("/{order_id}/confirm", response_model=SupplierOrderRead)
async def confirm_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_WRITE)),
) -> SupplierOrderRead:
    """Confirme la commande : draft → ordered."""
    svc = SupplierOrderService(db)
    order = await svc.confirm_order(order_id, current_user.tenant_id)
    return SupplierOrderRead.model_validate(order)


@router.post("/{order_id}/receive", response_model=SupplierOrderRead)
async def receive_order(
    order_id: int,
    data: SupplierOrderReceiptCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_WRITE)),
) -> SupplierOrderRead:
    """Enregistre une réception (partielle ou totale).

    Crée automatiquement des StockAdjustments pour chaque ligne reçue.
    Met à jour le statut : ordered/partially_received → partially_received/fully_received.
    """
    svc = SupplierOrderService(db)
    order = await svc.receive(order_id, data, current_user.tenant_id, current_user.id)
    return SupplierOrderRead.model_validate(order)


@router.post("/{order_id}/cancel", response_model=SupplierOrderRead)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_WRITE)),
) -> SupplierOrderRead:
    """Annule une commande."""
    svc = SupplierOrderService(db)
    order = await svc.cancel_order(order_id, current_user.tenant_id)
    return SupplierOrderRead.model_validate(order)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_WRITE)),
) -> None:
    """Supprime (soft delete) une commande."""
    svc = SupplierOrderService(db)
    await svc.delete_order(order_id, current_user.tenant_id)


@router.get("/prices/{supplier_id}")
async def get_supplier_prices(
    supplier_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_READ)),
) -> list[dict]:
    """Prix d'achat de reference par produit pour un fournisseur."""
    svc = SupplierOrderService(db)
    return await svc.get_supplier_prices(supplier_id, current_user.tenant_id)
