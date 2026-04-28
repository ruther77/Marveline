"""Celery task pour impression tickets ESC/POS.

L'impression est asynchrone pour ne pas bloquer les requêtes API.
En cas d'échec réseau (imprimante off), la task retry 3× avec backoff.
"""
import logging
from typing import Optional

from app.tasks.celery_app import celery_app
from app.services.printer import (
    TicketData,
    TicketLine,
    TvaBreakdown,
    print_ticket,
)

logger = logging.getLogger(__name__)

# Retry : 3 tentatives, backoff 5s → 15s → 45s
MAX_RETRIES = 3
RETRY_BACKOFF = 5


@celery_app.task(
    bind=True,
    max_retries=MAX_RETRIES,
    default_retry_delay=RETRY_BACKOFF,
    autoretry_for=(ConnectionError, OSError),
    retry_backoff=True,
)
def print_ticket_task(
    self,
    tenant_id: int,
    ticket_type: str,
    lignes: list[dict],
    sous_total_ht_cts: int,
    tva_breakdown: list[dict],
    total_ttc_cts: int,
    numero_ticket: str,
    operateur: str,
    mention_legale: str,
    qr_url: Optional[str],
    ouvrir_tiroir: bool,
    printer_host: str,
    printer_port: int = 9100,
) -> dict:
    """Formate et envoie un ticket vers l'imprimante réseau."""
    # Charger config commerce depuis DB (sync, car Celery worker)
    nom_commerce, adresse, siret, telephone = _load_commerce_info(tenant_id)

    data = TicketData(
        nom_commerce=nom_commerce,
        adresse=adresse,
        siret=siret,
        telephone=telephone,
        lignes=[TicketLine(**l) for l in lignes],
        sous_total_ht_cts=sous_total_ht_cts,
        tva_breakdown=[TvaBreakdown(**t) for t in tva_breakdown],
        total_ttc_cts=total_ttc_cts,
        numero_ticket=numero_ticket,
        operateur=operateur,
        mention_legale=mention_legale,
        qr_url=qr_url,
        ouvrir_tiroir=ouvrir_tiroir,
        ticket_type=ticket_type,
    )

    success = print_ticket(data, host=printer_host, port=printer_port)

    if not success:
        logger.warning(
            "Print failed tenant=%d host=%s retry=%d/%d",
            tenant_id, printer_host, self.request.retries, MAX_RETRIES,
        )
        raise ConnectionError(f"Cannot reach printer at {printer_host}:{printer_port}")

    logger.info("Ticket printed tenant=%d type=%s ticket=%s", tenant_id, ticket_type, numero_ticket)
    return {"status": "printed", "ticket": numero_ticket}


def _load_commerce_info(tenant_id: int) -> tuple[str, str, str, str]:
    """Charge les infos commerce depuis tenant_settings (sync DB)."""
    from app.core.database import SessionLocal
    from app.models.tenant_settings import TenantSettings
    from sqlalchemy import select

    try:
        with SessionLocal() as db:
            result = db.execute(
                select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
            )
            settings = result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to load commerce info for tenant %d: %s", tenant_id, e)
        return ("", "", "", "")

    if not settings:
        return ("", "", "", "")

    return (
        getattr(settings, "nom_commerce", "") or "",
        getattr(settings, "adresse", "") or "",
        getattr(settings, "siret", "") or "",
        getattr(settings, "telephone", "") or "",
    )
