"""Endpoints — Historique restaurant.

4 endpoints :
  GET  /restaurant/historique/commandes        → liste paginée commandes fermées
  GET  /restaurant/historique/commandes/{id}   → détail commande fermée
  GET  /restaurant/historique/export           → CSV direct (≤1000) ou tâche async (>1000)
  GET  /restaurant/historique/export/{task_id} → télécharger le CSV généré
"""
import csv
import io
from datetime import datetime
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.restaurant.commande import CommandeDetailHistorique, CommandeListResponse
from app.services.restaurant.commande import CommandeService

router = APIRouter(prefix="/restaurant/historique", tags=["Restaurant — Historique"])

_EXPORT_ASYNC_THRESHOLD = 1000
_EXPORT_REDIS_KEY_PREFIX = "export:restaurant:commandes:"
_EXPORT_REDIS_TTL = 3600  # 1 heure
_DATE_FMT = "%Y-%m-%d %H:%M:%S"
_CSV_HEADERS = [
    "id", "table", "statut", "date_ouverture", "date_fermeture",
    "nb_couverts", "total_cts", "pourboire_cts",
]


def _build_csv(items) -> str:
    """Génère le contenu CSV à partir d'une liste de CommandeResponse."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_HEADERS)
    for r in items:
        writer.writerow([
            r.id,
            r.table_numero or "",
            r.statut,
            r.date_ouverture.strftime(_DATE_FMT) if r.date_ouverture else "",
            r.date_fermeture.strftime(_DATE_FMT) if r.date_fermeture else "",
            r.nb_couverts,
            r.total_cts or 0,
            r.pourboire_cts,
        ])
    return buffer.getvalue()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/commandes", response_model=CommandeListResponse)
async def list_historique(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    statut: Optional[str] = Query(default=None, description="PAYEE | ANNULEE"),
    date_debut: Optional[datetime] = Query(default=None),
    date_fin: Optional[datetime] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> CommandeListResponse:
    """Historique paginé des commandes fermées (PAYEE/ANNULEE)."""
    return await CommandeService(db).list_paginated(
        page=page,
        per_page=per_page,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
    )


@router.get("/commandes/{commande_id}", response_model=CommandeDetailHistorique)
async def get_historique_detail(
    commande_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> CommandeDetailHistorique:
    """Détail complet d'une commande fermée (TVA par ligne, paiement, fractions)."""
    return await CommandeService(db).get_detail_historique(commande_id)


@router.get("/export")
async def export_commandes(
    statut: Optional[str] = Query(default=None),
    date_debut: Optional[datetime] = Query(default=None),
    date_fin: Optional[datetime] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
):
    """Export CSV des commandes fermées.

    ≤ 1000 lignes → CSV immédiat (StreamingResponse).
    > 1000 lignes → tâche Celery lancée, retour 202 avec task_id.
    Le CSV généré est récupérable via GET /export/{task_id} (TTL 1h).
    """
    probe = await CommandeService(db).list_paginated(
        page=1, per_page=1, statut=statut, date_debut=date_debut, date_fin=date_fin
    )
    if probe.total > _EXPORT_ASYNC_THRESHOLD:
        from app.tasks.restaurant_export import export_commandes_csv_task
        task = export_commandes_csv_task.delay(
            statut=statut,
            date_debut=date_debut.isoformat() if date_debut else None,
            date_fin=date_fin.isoformat() if date_fin else None,
        )
        body = f'{{"task_id":"{task.id}","total":{probe.total}}}'
        return Response(content=body, status_code=202, media_type="application/json")

    result = await CommandeService(db).list_paginated(
        page=1, per_page=probe.total or 1,
        statut=statut, date_debut=date_debut, date_fin=date_fin,
    )
    return StreamingResponse(
        iter([_build_csv(result.items)]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=historique_commandes.csv"},
    )


@router.get("/export/{task_id}")
async def get_export_result(
    task_id: str,
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
):
    """Télécharge le CSV produit par une tâche d'export async.

    - 200 + CSV   : export disponible dans Redis (TTL 1h)
    - 404         : export non trouvé ou TTL expiré
    """
    redis_key = f"{_EXPORT_REDIS_KEY_PREFIX}{task_id}"
    client = aioredis.from_url(settings.REDIS_CACHE_URL, decode_responses=True)
    try:
        content = await client.get(redis_key)
    finally:
        await client.aclose()

    if content is None:
        return Response(
            content='{"detail":"Export non disponible ou expiré"}',
            status_code=404,
            media_type="application/json",
        )
    filename = f"historique_commandes_{task_id}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
