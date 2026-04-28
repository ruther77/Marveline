"""Endpoint offline sync — replay file d'attente ordonnée (FIFO).

Quand une PWA perd la connexion, les mutations sont stockées localement
(BackgroundSync + IndexedDB). Au retour réseau, le client envoie toutes
les mutations en batch, ordonnées par timestamp client.

Le serveur les replay dans l'ordre (FIFO, timestamp serveur fait foi).
En cas de conflit (ex: stock devenu 0 entre-temps), la mutation est
rejetée avec détail, mais les suivantes continuent.

Idempotency : chaque mutation porte un UUID client. Si l'UUID a déjà
été traité (stocké dans Redis TTL 24h), la mutation est skippée avec
status "already_processed".

POST /offline/sync — replay mutations en batch
"""
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import get_current_user, UserCompat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/offline", tags=["Offline Sync"])

IDEMPOTENCY_TTL_SECONDS = 86400  # 24h
IDEMPOTENCY_PREFIX = "offline_sync:"


class OfflineMutation(BaseModel):
    """Une mutation enregistrée offline par le client."""
    id: str
    method: str
    path: str
    body: Optional[dict] = None
    client_timestamp: str


class OfflineSyncRequest(BaseModel):
    mutations: list[OfflineMutation]


class MutationResult(BaseModel):
    id: str
    status: str  # "ok" | "conflict" | "error" | "already_processed" | "unsupported"
    detail: str = ""


class OfflineSyncResponse(BaseModel):
    processed: int
    succeeded: int
    failed: int
    skipped: int
    results: list[MutationResult]


# ── Route patterns pour dispatch ──────────────────────────────────────────────

_EPICERIE_AJUSTEMENT = re.compile(r"^/epicerie/ajustement$")
_EPICERIE_ENCAISSER = re.compile(r"^/epicerie/ventes/encaisser$")
_EPICERIE_COMPTAGE = re.compile(r"^/epicerie/comptage$")
_RESTAURANT_COMMANDES = re.compile(r"^/restaurant/commandes$")
_RESTAURANT_LIGNES = re.compile(r"^/restaurant/commandes/(\d+)/lignes$")
_RESTAURANT_PAYER = re.compile(r"^/restaurant/commandes/(\d+)/payer$")


async def _dispatch_mutation(
    mutation: OfflineMutation,
    user: UserCompat,
    db: AsyncSession,
) -> MutationResult:
    """Route une mutation vers le bon service et retourne le résultat."""
    path = mutation.path
    body = mutation.body or {}

    try:
        # ── Épicerie ──────────────────────────────────────────────
        if _EPICERIE_AJUSTEMENT.match(path):
            from app.services.epicerie.inventaire import ajuster_stock
            from app.schemas.epicerie.stock import AjustementCreate
            payload = AjustementCreate(**body)
            await ajuster_stock(db, user.tenant_id, payload, user.id)
            return MutationResult(id=mutation.id, status="ok")

        if _EPICERIE_ENCAISSER.match(path):
            from app.services.epicerie.vente import encaisser
            from app.schemas.epicerie.vente import VenteCreate
            payload = VenteCreate(**body)
            await encaisser(db, user.tenant_id, payload, user.id)
            return MutationResult(id=mutation.id, status="ok")

        if _EPICERIE_COMPTAGE.match(path):
            from app.services.epicerie.inventaire import comptage_inventaire
            from app.schemas.epicerie.stock import ComptageCreate
            payload = ComptageCreate(**body)
            await comptage_inventaire(db, user.tenant_id, payload, user.id)
            return MutationResult(id=mutation.id, status="ok")

        # ── Restaurant ────────────────────────────────────────────
        if _RESTAURANT_COMMANDES.match(path) and mutation.method == "POST":
            from app.services.restaurant.commande import CommandeService
            from app.schemas.restaurant.commande import CommandeCreate
            service = CommandeService(db)
            payload = CommandeCreate(**body)
            await service.ouvrir(payload, created_by_id=user.id)
            return MutationResult(id=mutation.id, status="ok")

        m = _RESTAURANT_LIGNES.match(path)
        if m and mutation.method == "POST":
            from app.services.restaurant.ligne_commande import LigneCommandeService
            from app.schemas.restaurant.ligne_commande import LigneCommandeCreate
            commande_id = int(m.group(1))
            service = LigneCommandeService(db)
            payload = LigneCommandeCreate(**body)
            await service.create_ligne(commande_id, payload, created_by_id=user.id)
            return MutationResult(id=mutation.id, status="ok")

        m = _RESTAURANT_PAYER.match(path)
        if m and mutation.method == "POST":
            from app.services.restaurant.commande import CommandeService
            from app.schemas.restaurant.commande import PaiementRequest
            commande_id = int(m.group(1))
            service = CommandeService(db)
            payload = PaiementRequest(**body)
            await service.payer(commande_id, payload)
            return MutationResult(id=mutation.id, status="ok")

        # ── Route non supportée ───────────────────────────────────
        return MutationResult(
            id=mutation.id,
            status="unsupported",
            detail=f"Route {mutation.method} {path} non supportée en offline sync.",
        )

    except HTTPException as e:
        return MutationResult(id=mutation.id, status="conflict", detail=str(e.detail))
    except (KeyError, TypeError, ValueError) as e:
        return MutationResult(id=mutation.id, status="error", detail=f"Payload invalide: {e}")
    except Exception as e:
        logger.error("Offline dispatch error mutation=%s path=%s: %s", mutation.id, path, e)
        return MutationResult(id=mutation.id, status="error", detail=str(e))


@router.post("/sync", response_model=OfflineSyncResponse)
async def sync_offline_mutations(
    body: OfflineSyncRequest,
    current_user: UserCompat = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> OfflineSyncResponse:
    """Replay les mutations offline en FIFO (ordre client_timestamp).

    Chaque mutation est rejouée individuellement via le dispatcher.
    Idempotency garantie par UUID client (Redis TTL 24h).
    """
    from app.core.redis import redis_cache

    sorted_mutations = sorted(body.mutations, key=lambda m: m.client_timestamp)

    results: list[MutationResult] = []
    succeeded = 0
    failed = 0
    skipped = 0

    for mutation in sorted_mutations:
        # Idempotency check
        idem_key = f"{IDEMPOTENCY_PREFIX}{mutation.id}"
        already = await redis_cache.client.get(idem_key)
        if already:
            results.append(MutationResult(id=mutation.id, status="already_processed"))
            skipped += 1
            continue

        result = await _dispatch_mutation(mutation, current_user, db)
        results.append(result)

        if result.status == "ok":
            succeeded += 1
            await redis_cache.client.setex(idem_key, IDEMPOTENCY_TTL_SECONDS, "1")
        elif result.status == "unsupported":
            skipped += 1
        else:
            failed += 1

    if succeeded > 0:
        await db.commit()

    return OfflineSyncResponse(
        processed=len(sorted_mutations),
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        results=results,
    )
