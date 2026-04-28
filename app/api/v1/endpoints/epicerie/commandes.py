"""Endpoints Commandes fournisseurs épicerie — CRUD et transitions."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope
from app.core.exceptions import NotFound
from app.core.permissions import Scope
from app.repositories.epicerie.supply_order import AsyncSupplyOrderRepository
from app.schemas.epicerie.supply_order import (
    SupplyOrderCreate,
    SupplyOrderListResponse,
    SupplyOrderRead,
    SupplyOrderLineRead,
    SupplyOrderUpdate,
)
from app.services.epicerie.supply_order import (
    changer_statut,
    creer_commande,
)

router = APIRouter(prefix="/epicerie/commandes", tags=["Épicerie — Commandes"])

_STATUTS_MODIFIABLES = {"en_attente", "brouillon"}


async def _build_order_read(order, repo: AsyncSupplyOrderRepository) -> SupplyOrderRead:
    """Construit un SupplyOrderRead avec total_cts et total_ligne_cts calculés."""
    lignes = await repo.list_lines(order.id)
    return SupplyOrderRead(
        id=order.id,
        vendor_id=order.vendor_id,
        vendor_nom=None,
        reference=order.reference,
        date_commande=order.date_commande,
        date_livraison_prevue=order.date_livraison_prevue,
        date_livraison_reelle=order.date_livraison_reelle,
        statut=order.statut,
        montant_ht=order.montant_ht,
        montant_tva=order.montant_tva,
        montant_ttc=order.montant_ttc,
        total_cts=order.montant_ttc,
        notes=order.notes,
        invoice_id=order.invoice_id,
        lignes=[
            SupplyOrderLineRead(
                id=l.id,
                order_id=l.order_id,
                produit_id=l.produit_id,
                designation=l.designation,
                quantity=l.quantity,
                prix_unitaire=l.prix_unitaire,
                taux_tva=l.taux_tva,
                received_quantity=l.received_quantity,
                notes=l.notes,
                total_ligne_cts=round(float(l.quantity) * l.prix_unitaire),
            )
            for l in lignes
        ],
    )


@router.get("", response_model=SupplyOrderListResponse)
async def list_commandes(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    vendor_id: Optional[int] = Query(default=None),
    statut: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Liste paginée des commandes fournisseurs."""
    repo = AsyncSupplyOrderRepository(db)
    items, total = await repo.list_paginated(
        tenant_id=current_user.tenant_id,
        page=page,
        per_page=per_page,
        vendor_id=vendor_id,
        statut=statut,
    )
    orders_read = []
    for order in items:
        orders_read.append(await _build_order_read(order, repo))
    return SupplyOrderListResponse(
        items=orders_read, total=total, page=page, per_page=per_page
    )


@router.post("", response_model=SupplyOrderRead, status_code=201)
async def create_commande(
    payload: SupplyOrderCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Crée une commande fournisseur."""
    repo = AsyncSupplyOrderRepository(db)
    order = await creer_commande(db, current_user.tenant_id, payload)
    return await _build_order_read(order, repo)


@router.get("/{order_id}", response_model=SupplyOrderRead)
async def get_commande(
    order_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Détail d'une commande fournisseur."""
    repo = AsyncSupplyOrderRepository(db)
    order = await repo.get_by_id(order_id, current_user.tenant_id)
    if order is None:
        raise NotFound(f"Commande {order_id} introuvable")
    return await _build_order_read(order, repo)


@router.put("/{order_id}", response_model=SupplyOrderRead)
async def update_commande(
    order_id: int,
    payload: SupplyOrderUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """F7 : Met à jour référence, date livraison prévue et notes d'une commande."""
    repo = AsyncSupplyOrderRepository(db)
    order = await repo.get_by_id(order_id, current_user.tenant_id)
    if order is None:
        raise NotFound(f"Commande {order_id} introuvable")
    if order.statut not in _STATUTS_MODIFIABLES:
        raise HTTPException(
            status_code=409,
            detail=f"Commande au statut {order.statut!r} non modifiable",
        )
    if payload.reference is not None:
        order.reference = payload.reference
    if payload.date_livraison_prevue is not None:
        order.date_livraison_prevue = payload.date_livraison_prevue
    if payload.notes is not None:
        order.notes = payload.notes
    await db.flush()
    await db.commit()
    await db.refresh(order)
    return await _build_order_read(order, repo)


@router.post("/{order_id}/confirmer", response_model=SupplyOrderRead)
async def confirmer_commande(
    order_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Confirme une commande (en_attente → confirmee)."""
    repo = AsyncSupplyOrderRepository(db)
    order = await changer_statut(db, current_user.tenant_id, order_id, "confirmee")
    return await _build_order_read(order, repo)


@router.post("/{order_id}/annuler", response_model=SupplyOrderRead)
async def annuler_commande(
    order_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Annule une commande."""
    repo = AsyncSupplyOrderRepository(db)
    order = await changer_statut(db, current_user.tenant_id, order_id, "annulee")
    return await _build_order_read(order, repo)
