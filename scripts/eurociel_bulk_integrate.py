"""Bulk integration EUROCIEL — pour chaque PDF multi-factures, itère sur les factures.

Usage :
    docker exec -w /app futurproj_api bash -c 'PYTHONPATH=/app python scripts/eurociel_bulk_integrate.py /tmp/eurociel_sample.pdf /tmp/eurociel_2425.pdf ...'
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
from scripts.etl.parsers.eurociel import list_invoices, parse_facture

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("eurociel_bulk")
logger.setLevel(logging.INFO)

_USER_ID = 1


async def process_one(pdf_path: str, numero: str, source_name: str) -> dict:
    stats: dict = {"numero": numero, "status": "ok"}
    try:
        lignes, metadata = parse_facture(pdf_path, numero)
    except Exception as exc:
        return {"numero": numero, "status": "parse_error", "error": str(exc)[:150]}

    if not metadata.target_tenant_id:
        return {"numero": numero, "status": "no_tenant", "client": metadata.client_name}
    if not lignes:
        return {"numero": numero, "status": "no_lines"}

    async with AsyncSessionLocal() as db:
        try:
            existing = await db.execute(
                select(EtlImport).where(
                    EtlImport.numero_facture == numero,
                    EtlImport.vendor_code == "EUROCIEL",
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

            # Persister le PDF source (multi-factures) pour affichage frontend
            fichier_path = persist_etl_source(etl_import.id, pdf_path)
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
            stats["client"] = metadata.client_name
            stats["tenant"] = metadata.target_tenant_id
            await db.commit()
        except Exception as exc:
            await db.rollback()
            return {"numero": numero, "status": "error", "error": str(exc)[:200]}

    return stats


async def main(pdf_paths: list[str]) -> None:
    total_invoices = 0
    by_status: dict[str, int] = {}
    t0 = time.perf_counter()

    for pdf_path in pdf_paths:
        source = pdf_path.split("/")[-1]
        try:
            numeros = list_invoices(pdf_path)
        except Exception as exc:
            print(f"  SKIP {source} : {exc}")
            continue
        print(f"→ {source} : {len(numeros)} factures")
        total_invoices += len(numeros)
        for num in numeros:
            result = await process_one(pdf_path, num, source)
            status = result.get("status", "?")
            by_status[status] = by_status.get(status, 0) + 1

    elapsed = time.perf_counter() - t0
    print()
    print(f"DONE in {elapsed:.0f}s — {total_invoices} factures traitées")
    for status, n in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f"  {status:20s} : {n}")


if __name__ == "__main__":
    paths = sys.argv[1:] if len(sys.argv) > 1 else []
    if not paths:
        print("Usage: script.py <pdf1> [pdf2] ...")
        sys.exit(1)
    asyncio.run(main(paths))
