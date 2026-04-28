"""Celery task ETL import catalogue alimentaire (ADR-08).

Enveloppe Celery autour de run_import() (app.services.catalogue.etl_import_service).
La logique métier est entièrement dans le service — cette couche gère uniquement
le cycle de vie Celery (retry, session DB, sérialisation JSON).

Références :
    ADR-08 : pipeline ETL fournisseurs, Celery workers
    ADR-07 : déduplication Jaro-Winkler (implémentée dans le service)
"""
import asyncio
import logging
import threading
from typing import Any

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# ── Nom de la queue ETL (pas de magic string) ─────────────────────────────────

_QUEUE_ETL = "etl"
_TASK_NAME = "app.tasks.etl_tasks.run_etl_import"

# ── Event loop persistant par process worker (évite asyncpg loop-mismatch) ───

_WORKER_LOOP: asyncio.AbstractEventLoop | None = None
_WORKER_LOOP_LOCK = threading.Lock()


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    """Retourne (ou crée) l'event loop dédié à ce process Celery worker.

    asyncpg attache ses connexions à l'event loop de création. En réutilisant
    le même loop pour toutes les tâches du même process, les connexions du pool
    restent valides entre les invocations.
    """
    global _WORKER_LOOP
    with _WORKER_LOOP_LOCK:
        if _WORKER_LOOP is None or _WORKER_LOOP.is_closed():
            _WORKER_LOOP = asyncio.new_event_loop()
            asyncio.set_event_loop(_WORKER_LOOP)
        return _WORKER_LOOP


# ── Cœur async testable (sans AsyncSessionLocal interne) ─────────────────────


async def _execute_import_with_session(
    db: Any,  # AsyncSession — typé Any pour éviter import circulaire
    etl_import_id: int,
    lignes_data: list[dict],
) -> None:
    """Reconstruit les LigneParsee, orchestre run_import() et committe.

    Cette fonction est exposée pour les tests : elle accepte une session
    externe (ne crée pas sa propre AsyncSessionLocal).

    Args:
        db: AsyncSession fournie par l'appelant (Celery task ou test).
        etl_import_id: ID de l'EtlImport PENDING en base.
        lignes_data: Lignes sérialisées en dicts JSON-compatibles.
    """
    from app.services.catalogue.etl_import_service import run_import
    from app.etl_types import LigneParsee
    import dataclasses

    _valid_fields = {f.name for f in dataclasses.fields(LigneParsee)}
    lignes = [
        LigneParsee(**{k: v for k, v in d.items() if k in _valid_fields})
        for d in lignes_data
    ]
    await run_import(db, lignes, etl_import_id)
    await db.commit()


# ── Task Celery ────────────────────────────────────────────────────────────────


@celery_app.task(
    bind=True,
    queue=_QUEUE_ETL,
    max_retries=1,
    default_retry_delay=300,
    name=_TASK_NAME,
)
def run_etl_import(
    self,
    etl_import_id: int,
    lignes_data: list[dict],
) -> dict[str, Any]:
    """Importe une liste de lignes parsées dans le catalogue alimentaire (ADR-08).

    Exécute le pipeline ETL de façon synchrone via asyncio.run() : Celery workers
    sont synchrones, la logique métier (run_import) est async-only.

    Args:
        etl_import_id: ID de l'EtlImport déjà créé en DB (statut PENDING attendu).
        lignes_data: Lignes parsées sérialisées en dicts (depuis LigneParsee).

    Returns:
        Dict {"status": "done", "etl_import_id": <int>}

    Raises:
        ValueError: Propagé sans retry si etl_import_id est introuvable.
    """
    from app.core.database import AsyncSessionLocal

    async def _with_new_session() -> None:
        async with AsyncSessionLocal() as db:
            await _execute_import_with_session(db, etl_import_id, lignes_data)

    try:
        loop = _get_worker_loop()
        loop.run_until_complete(_with_new_session())
        logger.info("ETL import %d terminé avec succès", etl_import_id)
        return {"status": "done", "etl_import_id": etl_import_id}
    except ValueError as exc:
        logger.error("ETL import %d : données invalides — %s", etl_import_id, exc)
        raise
    except Exception as exc:
        logger.exception("ETL import %d : erreur inattendue", etl_import_id)
        raise self.retry(exc=exc)


# ── Task : Fetch product images ──────────────────────────────────────────────

@celery_app.task(
    bind=True,
    queue=_QUEUE_ETL,
    max_retries=0,
    name="etl.fetch_product_images",
)
def fetch_product_images_task(self, products: list[dict]) -> dict:
    """Fetch images pour un batch de produits épicerie.

    Args:
        products: list de dicts avec keys: id, ean, designation, marque
    """
    from app.services.epicerie.image_fetcher import fetch_images_batch
    from app.core.database import AsyncSessionLocal

    results = fetch_images_batch(products, delay=0.5)

    # Persister les image_url en base
    async def _persist():
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            for pid, path in results.items():
                await db.execute(
                    text("UPDATE epicerie_produits SET image_url = :path WHERE id = :id"),
                    {"path": path, "id": pid},
                )
            await db.commit()

    loop = _get_worker_loop()
    loop.run_until_complete(_persist())

    logger.info("Image fetch: %d/%d products got images", len(results), len(products))
    return {"status": "done", "fetched": len(results), "total": len(products)}
