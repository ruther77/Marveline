"""Intégration bulk METRO — upload → preview → validate pour chaque PDF.

Calqué sur taiyat_bulk_integrate.py. METRO ne remplit pas metadata.target_tenant_id,
on force donc tenant=2 (épicerie) par défaut.

Usage :
    docker exec -w /app futurproj_api bash -c 'PYTHONPATH=/app python scripts/metro_bulk_integrate.py /tmp/metro_batch [limit]'
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.catalogue.etl_import import EtlImport
from app.services.catalogue.etl_import_service import run_import
from app.services.catalogue.etl_pdf_storage import persist_etl_source
from scripts.etl.parsers.metro.core import parse_facture

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("metro_bulk")
logger.setLevel(logging.INFO)

_ETL_UPLOAD_USER_ID = 1  # système
_DEFAULT_TENANT = 2  # épicerie (METRO n'a pas de routing multi-tenant)


async def process_one(pdf_path: Path) -> dict:
    stats: dict = {"file": pdf_path.name, "status": "ok"}
    try:
        lignes, metadata = parse_facture(str(pdf_path))
    except Exception as exc:
        return {"file": pdf_path.name, "status": "parse_error", "error": str(exc)[:150]}

    # Forcer tenant=2 (épicerie) si non renseigné
    if not metadata.target_tenant_id:
        metadata.target_tenant_id = _DEFAULT_TENANT

    async with AsyncSessionLocal() as db:
        try:
            if metadata.numero_facture:
                existing = await db.execute(
                    select(EtlImport).where(
                        EtlImport.numero_facture == metadata.numero_facture,
                        EtlImport.vendor_code == "METRO",
                        EtlImport.target_tenant_id == metadata.target_tenant_id,
                        EtlImport.statut.in_(("VALIDATED", "RUNNING")),
                    ).limit(1)
                )
                if existing.scalar_one_or_none() is not None:
                    return {"file": pdf_path.name, "status": "skipped_duplicate",
                            "numero": metadata.numero_facture}

            etl_import = EtlImport(
                fournisseur_id=None, fichier_source=pdf_path.name, statut="PENDING",
            )
            db.add(etl_import)
            await db.flush()
            stats["import_id"] = etl_import.id

            fichier_path = persist_etl_source(etl_import.id, pdf_path)
            if fichier_path:
                etl_import.fichier_path = fichier_path
                await db.flush()

            await run_import(db, lignes, etl_import.id, metadata=metadata, preview_mode=True)
            await db.flush()
            await db.refresh(etl_import)

            etl_import.statut = "RUNNING"
            await db.flush()

            from app.services.epicerie.reception_etl import recevoir_facture_etl
            result = await recevoir_facture_etl(
                db=db, etl_import=etl_import, tenant_id=2, user_id=_ETL_UPLOAD_USER_ID,
            )
            stats["produits_synced"] = result.produits_synced
            stats["mouvements"] = result.mouvements_crees
            if result.has_conflicts:
                stats["status"] = "conflicts"
                stats["pending_conflicts"] = result.pending_conflicts
                await db.commit()
                return stats

            etl_import.statut = "VALIDATED"
            stats["invoice"] = result.invoice.numero if result.invoice else None
            stats["numero"] = metadata.numero_facture
            await db.commit()
        except Exception as exc:
            await db.rollback()
            return {"file": pdf_path.name, "status": "integration_error",
                    "error": str(exc)[:200], "import_id": stats.get("import_id")}

    return stats


async def main(directory: str, limit: int | None = None) -> None:
    pdf_dir = Path(directory)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if limit:
        pdfs = pdfs[:limit]
    print(f"→ Intégration de {len(pdfs)} PDFs METRO")

    by_status: dict[str, int] = {}
    t0 = time.perf_counter()
    detail: list[dict] = []

    for i, pdf in enumerate(pdfs, 1):
        stats = await process_one(pdf)
        status = stats.get("status", "?")
        by_status[status] = by_status.get(status, 0) + 1
        detail.append(stats)
        if i % 25 == 0 or stats["status"] not in ("ok", "skipped_duplicate"):
            elapsed = time.perf_counter() - t0
            rate = i / elapsed if elapsed > 0 else 0
            print(f"  [{i}/{len(pdfs)}] ({rate:.1f}/s) {pdf.name:30s} → {status}")

    elapsed = time.perf_counter() - t0
    print()
    print("═" * 60)
    print(f"DONE in {elapsed:.0f}s — {len(pdfs)} PDFs METRO traités")
    for status, n in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f"  {status:25s} : {n}")
    print()

    errors = [d for d in detail if d["status"] not in ("ok", "skipped_duplicate")]
    if errors:
        print("─── ERREURS ─────────────────────────────────────────────────")
        for e in errors[:20]:
            print(f"  {e['file']:30s} {e['status']:20s} {e.get('error', '')[:80]}")


if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else "/tmp/metro_batch"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    asyncio.run(main(directory, limit))
