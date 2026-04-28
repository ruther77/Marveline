"""Endpoints POS épicerie — encaissement et historique des ventes."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope
from app.core.exceptions import NotFound
from app.core.permissions import Scope
from app.repositories.epicerie.stock import AsyncEpicerieStockRepository
from app.repositories.epicerie.vente import AsyncEpicerieVenteRepository
from app.schemas.epicerie.produit import ProduitCatalogueListResponse, ProduitCatalogueRead
from app.schemas.epicerie.vente import (
    EncaissementRequest,
    EncaissementResponse,
    EpicerieVenteListItem,
    EpicerieVenteListResponse,
    EpicerieVenteRead,
    VenteLigneRead,
)
from app.services.epicerie.vente import annuler_vente, encaisser

router = APIRouter(prefix="/epicerie", tags=["Épicerie — POS"])

_BADGE_SEUIL = 1.0  # quantite <= seuil_alerte → 'bas'


def _to_catalogue_read(produit, stock) -> ProduitCatalogueRead:
    """Construit ProduitCatalogueRead depuis (EpicerieProduit, EpicerieStock | None)."""
    quantite = float(stock.quantite) if stock else 0.0
    seuil = float(stock.seuil_alerte) if stock else 0.0
    if quantite <= 0:
        badge = 'rupture'
    elif quantite <= seuil:
        badge = 'bas'
    else:
        badge = 'ok'
    return ProduitCatalogueRead(
        id=produit.id,
        ean=produit.ean,
        designation_clean=produit.designation_clean,
        nom_court=produit.nom_court,
        categorie=produit.categorie,
        unite_vente=produit.unite_vente,
        prix_unitaire_cts=produit.prix_unitaire_cts,
        taux_tva=produit.taux_tva,
        image_url=produit.image_url,
        actif=produit.actif,
        quantite=quantite,
        seuil_alerte=seuil,
        statut_badge=badge,
    )


@router.get("/pos/catalogue", response_model=ProduitCatalogueListResponse)
async def catalogue_pos(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=500),
    search: Optional[str] = Query(default=None),
    categorie: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Catalogue POS : produits actifs + stock courant (LEFT JOIN, 1 requête)."""
    repo = AsyncEpicerieStockRepository(db)
    items, total = await repo.list_with_produit(
        tenant_id=current_user.tenant_id,
        page=page,
        per_page=per_page,
        search=search,
        categorie=categorie,
    )
    return ProduitCatalogueListResponse(
        items=[_to_catalogue_read(p, s) for p, s in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/ventes/encaisser", response_model=EncaissementResponse, status_code=201)
async def endpoint_encaisser(
    payload: EncaissementRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Encaissement POS atomique."""
    return await encaisser(db, current_user.tenant_id, payload, vendeur_id=current_user.id)


@router.get("/ventes", response_model=EpicerieVenteListResponse)
async def list_ventes(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    statut: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Historique paginé des ventes épicerie."""
    repo = AsyncEpicerieVenteRepository(db)
    rows, total = await repo.list_paginated(
        tenant_id=current_user.tenant_id,
        limit=limit,
        offset=offset,
        statut=statut,
        search=search,
    )
    counts = await repo.counts_by_statut(current_user.tenant_id)
    items = [
        EpicerieVenteListItem(
            id=vente.id,
            numero_ticket=vente.numero_ticket,
            date_vente=vente.date_vente,
            statut=vente.statut,
            mode_paiement=vente.mode_paiement,
            total_ht=vente.total_ht,
            total_tva=vente.total_tva,
            total_ttc=vente.total_ttc,
            remise_pct=float(vente.remise_pct),
            remise_montant=vente.remise_montant,
            montant_especes=vente.montant_especes,
            montant_cb=vente.montant_cb,
            montant_rendu=vente.montant_rendu,
            client_nom=vente.client_nom,
            vendeur_id=vente.vendeur_id,
            nb_articles=nb_articles,
        )
        for vente, nb_articles in rows
    ]
    return EpicerieVenteListResponse(
        items=items, total=total, limit=limit, offset=offset, counts=counts
    )


@router.get("/ventes/{vente_id}", response_model=EpicerieVenteRead)
async def get_vente(
    vente_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Détail d'une vente épicerie."""
    repo = AsyncEpicerieVenteRepository(db)
    vente = await repo.get_by_id(vente_id, current_user.tenant_id)
    if vente is None:
        raise NotFound(f"Vente {vente_id} introuvable")
    lignes = await repo.list_lignes(vente.id)
    return EpicerieVenteRead(
        id=vente.id,
        numero_ticket=vente.numero_ticket,
        date_vente=vente.date_vente,
        statut=vente.statut,
        mode_paiement=vente.mode_paiement,
        total_ht=vente.total_ht,
        total_tva=vente.total_tva,
        total_ttc=vente.total_ttc,
        remise_pct=float(vente.remise_pct),
        remise_montant=vente.remise_montant,
        montant_especes=vente.montant_especes,
        montant_cb=vente.montant_cb,
        montant_rendu=vente.montant_rendu,
        client_nom=vente.client_nom,
        client_email=vente.client_email,
        vendeur_id=vente.vendeur_id,
        notes=vente.notes,
        invoice_id=vente.invoice_id,
        lignes=[VenteLigneRead.model_validate(l) for l in lignes],
    )


@router.post("/ventes/{vente_id}/annuler", status_code=200)
async def endpoint_annuler_vente(
    vente_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Annule une vente."""
    await annuler_vente(db, current_user.tenant_id, vente_id)
    return {"message": "Vente annulée"}
