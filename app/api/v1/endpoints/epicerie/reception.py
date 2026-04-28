"""Endpoint Réception commandes épicerie — POST /epicerie/commandes/{id}/recevoir."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope
from app.core.permissions import Scope
from app.repositories.epicerie.supply_order import AsyncSupplyOrderRepository
from app.schemas.epicerie.supply_order import ReceiveOrderRequest, SupplyOrderLineRead, SupplyOrderRead
from app.services.epicerie.supply_order import recevoir_commande

router = APIRouter(prefix="/epicerie/commandes", tags=["Épicerie — Réception"])


@router.post("/{order_id}/recevoir", response_model=SupplyOrderRead)
async def recevoir(
    order_id: int,
    payload: ReceiveOrderRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Réception atomique d'une commande fournisseur."""
    order = await recevoir_commande(
        db, current_user.tenant_id, order_id, payload, current_user.id
    )
    repo = AsyncSupplyOrderRepository(db)
    lignes = await repo.list_lines(order.id)
    return SupplyOrderRead(
        id=order.id,
        vendor_id=order.vendor_id,
        reference=order.reference,
        date_commande=order.date_commande,
        date_livraison_prevue=order.date_livraison_prevue,
        date_livraison_reelle=order.date_livraison_reelle,
        statut=order.statut,
        montant_ht=order.montant_ht,
        montant_tva=order.montant_tva,
        montant_ttc=order.montant_ttc,
        notes=order.notes,
        invoice_id=order.invoice_id,
        lignes=[SupplyOrderLineRead.model_validate(l) for l in lignes],
    )
