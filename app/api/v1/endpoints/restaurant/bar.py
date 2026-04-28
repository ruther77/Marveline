"""Endpoints — Bar restaurant.

3 endpoints :
  GET  /restaurant/boissons/catalogue                        → catalogue boissons actives
  GET  /restaurant/commandes/tickets-bar                     → boissons en attente (groupées par table)
  POST /restaurant/commandes/{id}/appliquer-formule          → appliquer formule boissons

Scope : RESTAURANT_READ (lecture) / RESTAURANT_WRITE (appliquer-formule).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope
from app.core.permissions import Scope
from app.schemas.restaurant.commande import CommandeDetail
from app.schemas.restaurant.ligne_commande import AppliquerFormuleRequest, BoissonsTicketResponse
from app.schemas.restaurant.variante_plat import CatalogueBoisson
from app.services.restaurant.ligne_commande import LigneCommandeService
from app.services.restaurant.variante_plat import VariantePlatService

router = APIRouter(prefix="/restaurant", tags=["Restaurant — Bar"])


@router.get("/boissons/catalogue", response_model=list[CatalogueBoisson])
async def get_catalogue_boissons(
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.RESTAURANT_READ)),
) -> list[CatalogueBoisson]:
    """Liste des boissons actives du menu (pour encaissement bar)."""
    boissons = await VariantePlatService(db).list_actives("boisson")
    return [
        CatalogueBoisson(
            variante_plat_id=b.id,
            nom=b.nom,
            categorie=b.categorie,
            prix_vente_cts=b.prix_vente_cts,
        )
        for b in boissons
    ]


@router.get("/commandes/tickets-bar", response_model=BoissonsTicketResponse)
async def get_tickets_bar(
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.RESTAURANT_READ)),
) -> BoissonsTicketResponse:
    """Ticket bar : boissons ENVOYEE / LANCEE regroupées par commande."""
    return await LigneCommandeService(db).get_ticket_bar()


@router.post("/commandes/{commande_id}/appliquer-formule", response_model=CommandeDetail)
async def appliquer_formule(
    commande_id: int,
    payload: AppliquerFormuleRequest,
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> CommandeDetail:
    """Applique une formule boissons à la commande (ajoute une ligne formule)."""
    result = await LigneCommandeService(db).appliquer_formule(
        commande_id, payload.variante_formule_id
    )
    await db.commit()
    return result
