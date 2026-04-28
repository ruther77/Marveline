"""Webhook Boxtal — reception des notifications (creation de documents, suivi, etc.).

Boxtal envoie un POST avec :
- Header `x-bxt-signature` : HMAC-SHA256 du body signe avec la cle de verification
- Body JSON : evenement (creation etiquette, tracking update, etc.)

L'endpoint valide la signature puis traite l'evenement.
"""
import hashlib
import hmac
import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/carrier", tags=["Carrier Webhook"])

BOXTAL_WEBHOOK_SECRET = getattr(settings, "BOXTAL_WEBHOOK_SECRET", "")


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verifie le HMAC-SHA256 du payload contre x-bxt-signature."""
    if not secret:
        logger.warning("BOXTAL_WEBHOOK_SECRET not configured — skipping signature check")
        return True
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook/boxtal", status_code=status.HTTP_200_OK)
async def boxtal_webhook(request: Request):
    """Recoit les notifications Boxtal (creation documents, tracking, etc.).

    - Valide x-bxt-signature (HMAC-SHA256)
    - Log l'evenement pour traitement ulterieur
    - Retourne 200 immediatement (Boxtal attend une reponse rapide)
    """
    body = await request.body()
    signature = request.headers.get("x-bxt-signature", "")

    if BOXTAL_WEBHOOK_SECRET and not _verify_signature(body, signature, BOXTAL_WEBHOOK_SECRET):
        logger.warning("Boxtal webhook: invalid signature")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        logger.error("Boxtal webhook: invalid JSON body")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    event_type = payload.get("event", payload.get("type", "unknown"))
    reference = payload.get("reference", payload.get("shipment_id", ""))

    logger.info(
        "Boxtal webhook received: event=%s reference=%s",
        event_type,
        reference,
    )

    # TODO: traiter les evenements specifiques (tracking update, etiquette prete, etc.)
    # Pour l'instant on log et on ACK.

    return {"status": "ok", "event": event_type}
