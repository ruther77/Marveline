"""Endpoint public recu numerique — accessible via QR code ticket.

GET /receipt/{token} — retourne le recu en HTML (pas d'auth requise).
Le token est un identifiant unique court genere a l'impression du ticket.

Stocke en Redis avec TTL 90 jours (suffisant pour garantie).
P1-20 : rate limiting 10 req/min par IP pour eviter enumeration.
"""
import logging
import re
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.core.redis import redis_cache, redis_sec

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Receipt"])

RECEIPT_TTL_SECONDS = 90 * 24 * 3600  # 90 jours
RECEIPT_KEY_PREFIX = "receipt:"
RECEIPT_RATE_LIMIT = 10  # max req/min par IP
RECEIPT_RATE_WINDOW = 60  # 1 minute

# Format attendu : UUID hex (32 chars) ou UUID standard (36 chars avec tirets)
_TOKEN_PATTERN = re.compile(r'^[a-f0-9\-]{32,36}$')


async def store_receipt(token: str, html_content: str) -> None:
    """Stocke un recu HTML dans Redis avec TTL 90 jours."""
    key = f"{RECEIPT_KEY_PREFIX}{token}"
    await redis_cache.client.setex(key, RECEIPT_TTL_SECONDS, html_content)


@router.get("/receipt/{token}", response_class=HTMLResponse)
async def get_receipt(token: str, request: Request) -> HTMLResponse:
    """Affiche un recu numerique (accessible sans auth — lien QR code)."""
    # P1-20 : valider format token (anti-enumeration)
    if not _TOKEN_PATTERN.match(token):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # P1-20 : rate limit par IP
    client_ip = request.client.host if request.client else "unknown"
    rl_key = f"rate:receipt:{client_ip}"
    try:
        count = await redis_sec.client.incr(rl_key)
        if count == 1:
            await redis_sec.client.expire(rl_key, RECEIPT_RATE_WINDOW)
        if count > RECEIPT_RATE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"retry_after": RECEIPT_RATE_WINDOW},
            )
    except HTTPException:
        raise
    except Exception:
        pass  # FAIL-OPEN pour receipt (non critique)

    key = f"{RECEIPT_KEY_PREFIX}{token}"
    try:
        content = await redis_cache.client.get(key)
    except Exception:
        logger.error("Redis error fetching receipt %s", token)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recu introuvable ou expire.",
        )

    return HTMLResponse(content=content.decode("utf-8"), status_code=200)
