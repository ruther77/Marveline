"""Revalide les imports TAIYAT VALIDATED côté épicerie (tenant 2) avec le
nouveau matching par désignation (fix mouvements sans EAN).

Pour chaque EtlImport VALIDATED avec vendor_code=TAIYAT et target_tenant_id=2:
  1. revert_import        → REVERTED + mouvements AJUSTEMENT négatifs
  2. reopen_import        → PREVIEW
  3. recevoir_facture_etl → VALIDATED (avec nouveau match désignation)

Usage :
    docker exec -w /app futurproj_api bash -c 'PYTHONPATH=/app python scripts/taiyat_revalidate_epicerie.py'
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.catalogue.etl_import import EtlImport
from app.services.epicerie.reception_etl import (
    recevoir_facture_etl, reopen_import, revert_import,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("taiyat_revalidate")
logger.setLevel(logging.INFO)

_TENANT = 2
_USER_ID = 1


async def process_one(import_id: int) -> dict:
    async with AsyncSessionLocal() as db:
        obj = (await db.execute(
            select(EtlImport).where(EtlImport.id == import_id).with_for_update()
        )).scalar_one_or_none()
        if obj is None:
            return {"import_id": import_id, "status": "missing"}

        try:
            await revert_import(db=db, etl_import=obj, tenant_id=_TENANT, user_id=_USER_ID)
            await db.flush()
            await reopen_import(db=db, etl_import=obj, tenant_id=_TENANT, user_id=_USER_ID)
            await db.flush()
            obj.statut = "RUNNING"
            await db.flush()
            result = await recevoir_facture_etl(
                db=db, etl_import=obj, tenant_id=_TENANT, user_id=_USER_ID,
            )
            if result.has_conflicts:
                await db.commit()
                return {"import_id": import_id, "status": "conflicts",
                        "pending": result.pending_conflicts}
            obj.statut = "VALIDATED"
            await db.commit()
            return {"import_id": import_id, "status": "ok",
                    "mouvements": result.mouvements_crees}
        except Exception as exc:
            await db.rollback()
            return {"import_id": import_id, "status": "error", "error": str(exc)[:200]}


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(EtlImport.id)
            .where(
                EtlImport.vendor_code == "TAIYAT",
                EtlImport.target_tenant_id == _TENANT,
                EtlImport.statut == "VALIDATED",
            )
            .order_by(EtlImport.id)
        )).scalars().all()

    print(f"→ {len(rows)} imports TAIYAT épicerie à revalider")

    by_status: dict[str, int] = {}
    total_mouvements = 0
    t0 = time.perf_counter()

    for i, import_id in enumerate(rows, 1):
        result = await process_one(import_id)
        status = result.get("status", "?")
        by_status[status] = by_status.get(status, 0) + 1
        if status == "ok":
            total_mouvements += result.get("mouvements", 0)
        if i % 10 == 0 or status != "ok":
            print(f"  [{i}/{len(rows)}] import={import_id} → {status} "
                  f"{result.get('mouvements', '')}")

    elapsed = time.perf_counter() - t0
    print()
    print(f"DONE in {elapsed:.0f}s — {len(rows)} imports, {total_mouvements} mouvements créés")
    for status, n in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f"  {status:15s} : {n}")


if __name__ == "__main__":
    asyncio.run(main())
