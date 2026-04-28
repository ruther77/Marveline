"""Tâche Celery — Export CSV historique commandes restaurant.

La tâche génère le CSV et le stocke dans Redis-CACHE (TTL 1h).
L'endpoint GET /restaurant/historique/export/{task_id} lit depuis Redis.

Architecture :
    - Celery task synchrone → asyncio.run() → session async → CommandeService
    - Redis sync (redis.from_url) pour stocker le CSV après la boucle async
"""
import asyncio
import csv
import io
import logging
from datetime import datetime
from typing import Optional

import redis

from app.core.config import settings
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_QUEUE_EXPORTS = "exports"
_TASK_NAME = "app.tasks.restaurant_export.export_commandes_csv_task"
_EXPORT_REDIS_KEY_PREFIX = "export:restaurant:commandes:"
_EXPORT_REDIS_TTL = 3600  # 1 heure
_MAX_EXPORT_ROWS = 50_000
_DATE_FMT = "%Y-%m-%d %H:%M:%S"
_CSV_HEADERS = [
    "id", "table", "statut", "date_ouverture", "date_fermeture",
    "nb_couverts", "total_cts", "pourboire_cts",
]


@celery_app.task(
    bind=True,
    queue=_QUEUE_EXPORTS,
    max_retries=1,
    default_retry_delay=60,
    name=_TASK_NAME,
)
def export_commandes_csv_task(
    self,
    statut: Optional[str] = None,
    date_debut: Optional[str] = None,
    date_fin: Optional[str] = None,
) -> dict:
    """Génère le CSV de l'historique commandes et stocke dans Redis-CACHE (TTL 1h).

    Args:
        statut: Filtre statut (PAYEE | ANNULEE | None pour tous).
        date_debut: ISO-8601 ou None.
        date_fin: ISO-8601 ou None.

    Returns:
        {"task_id": str, "total": int}
    """
    try:
        return asyncio.run(
            _generate_and_store_csv(self.request.id, statut, date_debut, date_fin)
        )
    except Exception as exc:
        logger.exception("Export restaurant CSV échoué — task=%s", self.request.id)
        raise self.retry(exc=exc)


async def _generate_and_store_csv(
    task_id: str,
    statut: Optional[str],
    date_debut_iso: Optional[str],
    date_fin_iso: Optional[str],
) -> dict:
    """Récupère les commandes, génère le CSV et le stocke dans Redis."""
    from app.core.database import AsyncSessionLocal
    from app.services.restaurant.commande import CommandeService

    date_debut = datetime.fromisoformat(date_debut_iso) if date_debut_iso else None
    date_fin = datetime.fromisoformat(date_fin_iso) if date_fin_iso else None

    async with AsyncSessionLocal() as db:
        result = await CommandeService(db).list_paginated(
            page=1,
            per_page=_MAX_EXPORT_ROWS,
            statut=statut,
            date_debut=date_debut,
            date_fin=date_fin,
        )

    csv_content = _build_csv(result.items)
    _store_in_redis(task_id, csv_content)
    logger.info(
        "Export restaurant terminé — %d commandes, task=%s",
        len(result.items),
        task_id,
    )
    return {"task_id": task_id, "total": len(result.items)}


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


def _store_in_redis(task_id: str, content: str) -> None:
    """Stocke le CSV dans Redis-CACHE avec TTL (client synchrone)."""
    client = redis.from_url(settings.REDIS_CACHE_URL, decode_responses=True)
    redis_key = f"{_EXPORT_REDIS_KEY_PREFIX}{task_id}"
    client.setex(redis_key, _EXPORT_REDIS_TTL, content)
