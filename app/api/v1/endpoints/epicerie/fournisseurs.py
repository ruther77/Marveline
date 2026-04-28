"""Endpoints Fournisseurs épicerie — liste, stats, factures, commandes."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope
from app.core.permissions import Scope
from app.repositories.epicerie.supply_order import AsyncSupplyOrderRepository
from app.schemas.epicerie.finance import (
    AlertesPrixResponse,
    CaHistoriqueResponse,
    FinanceInvoiceListResponse,
    FinanceInvoiceRead,
    FournisseurListResponse,
    FournisseurRead,
    FournisseurStats,
    QualiteResponse,
    StockMargesResponse,
)
from app.schemas.epicerie.supply_order import (
    SupplyOrderListResponse,
    SupplyOrderLineRead,
    SupplyOrderRead,
)
from app.services.epicerie.fournisseurs import (
    get_alertes_prix,
    get_ca_historique,
    get_fournisseur_stats,
    get_qualite,
    get_stock_marges,
    list_factures_fournisseur,
    list_fournisseurs,
)

router = APIRouter(prefix="/epicerie/fournisseurs", tags=["Épicerie — Fournisseurs"])


@router.get("", response_model=FournisseurListResponse)
async def get_fournisseurs(
    search: Optional[str] = Query(default=None, description="Filtre nom/code fournisseur"),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Liste des fournisseurs avec indicateurs clés (F1 : filtre search)."""
    items = await list_fournisseurs(db, current_user.tenant_id, search=search)
    return FournisseurListResponse(items=items)


@router.get("/{vendor_id}/stats", response_model=FournisseurStats)
async def get_stats(
    vendor_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Statistiques agrégées d'un fournisseur."""
    return await get_fournisseur_stats(db, current_user.tenant_id, vendor_id)


@router.get("/{vendor_id}/invoices", response_model=FinanceInvoiceListResponse)
async def get_invoices(
    vendor_id: int,
    statut: Optional[str] = Query(default=None, description="Filtre statut facture"),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Factures d'un fournisseur (F4 : filtre statut optionnel)."""
    items = await list_factures_fournisseur(db, current_user.tenant_id, vendor_id, statut=statut)
    return FinanceInvoiceListResponse(items=items)


@router.get("/{vendor_id}/commandes", response_model=SupplyOrderListResponse)
async def get_commandes_fournisseur(
    vendor_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    statut: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Commandes fournisseurs d'un fournisseur donné."""
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
        lignes = await repo.list_lines(order.id)
        orders_read.append(SupplyOrderRead(
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
                    **SupplyOrderLineRead.model_validate(l).model_dump(),
                    total_ligne_cts=round(float(l.quantity) * l.prix_unitaire),
                )
                for l in lignes
            ],
        ))
    return SupplyOrderListResponse(items=orders_read, total=total, page=page, per_page=per_page)


@router.get("/{vendor_id}/ca-historique", response_model=CaHistoriqueResponse)
async def get_ca_historique_endpoint(
    vendor_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Sparkline CA mensuel TTC sur 6 mois avec variation M vs M-1."""
    return await get_ca_historique(db, current_user.tenant_id, vendor_id)


@router.get("/{vendor_id}/stock-marges", response_model=StockMargesResponse)
async def get_stock_marges_endpoint(
    vendor_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Marge réelle moyenne du fournisseur vs marge moyenne catalogue."""
    return await get_stock_marges(db, current_user.tenant_id, vendor_id)


@router.get("/{vendor_id}/alertes-prix", response_model=AlertesPrixResponse)
async def get_alertes_prix_endpoint(
    vendor_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Hausses de prix détectées en comparant les 2 dernières factures ETL VALIDATED."""
    return await get_alertes_prix(db, current_user.tenant_id, vendor_id)


@router.get("/{vendor_id}/qualite", response_model=QualiteResponse)
async def get_qualite_endpoint(
    vendor_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Signaux qualité : % livraisons à l'heure + % factures en retard."""
    return await get_qualite(db, current_user.tenant_id, vendor_id)
