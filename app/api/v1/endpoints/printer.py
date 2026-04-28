"""Endpoints impression tickets ESC/POS.

POST /print/ticket — envoie un ticket vers l'imprimante réseau du tenant.
L'impression est asynchrone (Celery task) pour ne pas bloquer la requête.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/print", tags=["Printer"])


class TicketLineRequest(BaseModel):
    designation: str
    quantite: int = 1
    prix_unitaire_cts: int = 0
    total_cts: int = 0


class TvaBreakdownRequest(BaseModel):
    taux_label: str
    base_ht_cts: int = 0
    montant_tva_cts: int = 0


class PrintTicketRequest(BaseModel):
    ticket_type: str  # vente_epicerie | commande_cuisine | recu_restaurant
    lignes: list[TicketLineRequest]
    sous_total_ht_cts: int = 0
    tva_breakdown: list[TvaBreakdownRequest] = []
    total_ttc_cts: int = 0
    numero_ticket: str = ""
    mention_legale: str = "Merci de votre visite"
    qr_url: Optional[str] = None
    ouvrir_tiroir: bool = False


@router.post("/ticket", status_code=status.HTTP_202_ACCEPTED)
async def print_ticket(
    body: PrintTicketRequest,
    current_user: UserCompat = Depends(get_current_user),  # Auth requise, scope vérifié par app-level
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Enqueue une impression ticket vers l'imprimante réseau du tenant.

    L'impression est asynchrone — retourne 202 immédiatement.
    La config imprimante (IP, port) est lue depuis tenant_settings.
    """
    from app.tasks.printing import print_ticket_task

    tenant_id = current_user.tenant_id

    # Lire config imprimante depuis tenant_settings
    from sqlalchemy import select
    from app.models.tenant_settings import TenantSettings
    result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    settings = result.scalar_one_or_none()

    printer_host = getattr(settings, "printer_host", None) if settings else None
    printer_port = getattr(settings, "printer_port", 9100) if settings else 9100

    if not printer_host:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aucune imprimante configurée pour ce tenant. Configurez printer_host dans les paramètres.",
        )

    # Enqueue Celery task
    print_ticket_task.delay(
        tenant_id=tenant_id,
        ticket_type=body.ticket_type,
        lignes=[l.model_dump() for l in body.lignes],
        sous_total_ht_cts=body.sous_total_ht_cts,
        tva_breakdown=[t.model_dump() for t in body.tva_breakdown],
        total_ttc_cts=body.total_ttc_cts,
        numero_ticket=body.numero_ticket,
        operateur=f"{current_user.first_name} {current_user.last_name}",
        mention_legale=body.mention_legale,
        qr_url=body.qr_url,
        ouvrir_tiroir=body.ouvrir_tiroir,
        printer_host=printer_host,
        printer_port=printer_port,
    )

    logger.info("Print ticket enqueued tenant=%d type=%s", tenant_id, body.ticket_type)
    return {"status": "queued", "message": "Impression en cours..."}
