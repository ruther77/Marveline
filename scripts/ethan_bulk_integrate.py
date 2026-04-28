"""Intégration bulk ETHAN — 1 facture xlsx = 1 EtlImport (1b).

Usage :
    docker exec -w /app futurproj_api bash -c 'PYTHONPATH=/app python scripts/ethan_bulk_integrate.py /tmp/ethan.xlsx'
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.catalogue.etl_import import EtlImport
from app.services.catalogue.etl_import_service import run_import
from app.services.catalogue.etl_pdf_storage import persist_etl_source
from scripts.etl.parsers.ethan import list_invoices, parse_facture

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ethan_bulk")
logger.setLevel(logging.INFO)

_USER_ID = 1


async def process_one(xlsx_path: str, numero: str, source_name: str) -> dict:
    stats: dict = {"numero": numero, "status": "ok"}
    try:
        lignes, metadata = parse_facture(xlsx_path, numero)
    except Exception as exc:
        return {"numero": numero, "status": "parse_error", "error": str(exc)[:150]}

    if not metadata.target_tenant_id:
        return {"numero": numero, "status": "no_tenant", "client": metadata.client_name}

    async with AsyncSessionLocal() as db:
        try:
            # Idempotence
            existing = await db.execute(
                select(EtlImport).where(
                    EtlImport.numero_facture == numero,
                    EtlImport.vendor_code == "ETHAN",
                    EtlImport.target_tenant_id == metadata.target_tenant_id,
                    EtlImport.statut.in_(("VALIDATED", "RUNNING")),
                ).limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                return {"numero": numero, "status": "skipped_duplicate"}

            etl_import = EtlImport(
                fournisseur_id=None,
                fichier_source=f"{source_name}#{numero}",
                statut="PENDING",
            )
            db.add(etl_import)
            await db.flush()
            stats["import_id"] = etl_import.id

            # Persister le XLSX source (multi-factures) pour téléchargement frontend
            fichier_path = persist_etl_source(etl_import.id, xlsx_path)
            if fichier_path:
                etl_import.fichier_path = fichier_path
                await db.flush()

            await run_import(db, lignes, etl_import.id, metadata=metadata, preview_mode=True)
            await db.flush()
            await db.refresh(etl_import)

            etl_import.statut = "RUNNING"
            await db.flush()

            if metadata.target_tenant_id == 2:
                from app.services.epicerie.reception_etl import recevoir_facture_etl
                result = await recevoir_facture_etl(
                    db=db, etl_import=etl_import, tenant_id=2, user_id=_USER_ID,
                )
                stats["mouvements"] = result.mouvements_crees
                if result.has_conflicts:
                    stats["status"] = "conflicts"
                    stats["pending"] = result.pending_conflicts
                    await db.commit()
                    return stats
            else:
                from app.services.restaurant.reception_etl import recevoir_facture_etl_restaurant
                result = await recevoir_facture_etl_restaurant(
                    db=db, etl_import=etl_import, tenant_id=3, user_id=_USER_ID,
                )
                stats["mouvements"] = result.mouvements_crees
                stats["ingredients_crees"] = result.ingredients_crees

            etl_import.statut = "VALIDATED"
            stats["invoice"] = result.invoice.numero if result.invoice else None
            stats["client"] = metadata.client_name
            stats["tenant"] = metadata.target_tenant_id
            await db.commit()
        except Exception as exc:
            await db.rollback()
            return {"numero": numero, "status": "error", "error": str(exc)[:200]}

    return stats


async def main(xlsx_path: str) -> None:
    numeros = list_invoices(xlsx_path)
    source_name = xlsx_path.rsplit("/", 1)[-1]
    print(f"→ {len(numeros)} factures dans {source_name}")

    by_status: dict[str, int] = {}
    t0 = time.perf_counter()
    total_mouvements = 0

    for i, num in enumerate(numeros, 1):
        result = await process_one(xlsx_path, num, source_name)
        status = result.get("status", "?")
        by_status[status] = by_status.get(status, 0) + 1
        total_mouvements += result.get("mouvements", 0)
        print(f"  [{i:2}/{len(numeros)}] {num}  {status:15s} "
              f"client={result.get('client', '-'):15s} "
              f"mvts={result.get('mouvements', 0)}")

    elapsed = time.perf_counter() - t0
    print()
    print(f"DONE in {elapsed:.0f}s — {total_mouvements} mouvements créés")
    for status, n in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f"  {status:15s} : {n}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ethan.xlsx"
    asyncio.run(main(path))
