"""Intégration bulk TAIYAT — upload → preview → validate pour chaque PDF.

Pour chaque facture :
  1. parse_facture → metadata (client, target_tenant, lignes)
  2. Crée EtlImport en PENDING
  3. run_import(preview_mode=True) → hydrate lignes_data + classification
  4. Dispatch selon target_tenant : recevoir_facture_etl (épicerie 2) ou
     recevoir_facture_etl_restaurant (restaurant 3)
  5. Statut VALIDATED + commit

Usage :
    docker exec -w /app futurproj_api bash -c 'PYTHONPATH=/app python scripts/taiyat_bulk_integrate.py /tmp/taiyat_batch [limit]'

Arguments :
    directory : dossier contenant les PDFs
    limit     : optionnel, nb max de factures à traiter (défaut : all)
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
from scripts.etl.parsers.taiyat import parse_facture

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("taiyat_bulk")
logger.setLevel(logging.INFO)

_ETL_UPLOAD_USER_ID = 1  # système


async def process_one(pdf_path: Path) -> dict:
    """Traite un PDF : parse + preview + validation. Retourne stats."""
    stats: dict = {"file": pdf_path.name, "status": "ok"}
    try:
        lignes, metadata = parse_facture(str(pdf_path))
    except Exception as exc:
        return {"file": pdf_path.name, "status": "parse_error", "error": str(exc)[:150]}

    if not metadata.target_tenant_id:
        return {"file": pdf_path.name, "status": "no_tenant", "client": metadata.client_name}

    async with AsyncSessionLocal() as db:
        try:
            # Idempotence : skip si déjà un import avec même numero_facture + vendor_code + target_tenant
            if metadata.numero_facture:
                existing = await db.execute(
                    select(EtlImport).where(
                        EtlImport.numero_facture == metadata.numero_facture,
                        EtlImport.vendor_code == "TAIYAT",
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

            # Persister le PDF source pour affichage frontend
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
                    db=db, etl_import=etl_import, tenant_id=2, user_id=_ETL_UPLOAD_USER_ID,
                )
                stats["produits_synced"] = result.produits_synced
                stats["mouvements"] = result.mouvements_crees
                if result.has_conflicts:
                    stats["status"] = "conflicts"
                    stats["pending_conflicts"] = result.pending_conflicts
                    await db.commit()
                    return stats
            else:  # target_tenant_id == 3
                from app.services.restaurant.reception_etl import recevoir_facture_etl_restaurant
                result = await recevoir_facture_etl_restaurant(
                    db=db, etl_import=etl_import, tenant_id=3, user_id=_ETL_UPLOAD_USER_ID,
                )
                stats["ingredients_crees"] = result.ingredients_crees
                stats["ingredients_updated"] = result.ingredients_updated
                stats["mouvements"] = result.mouvements_crees

            etl_import.statut = "VALIDATED"
            stats["invoice"] = result.invoice.numero if result.invoice else None
            stats["tenant"] = metadata.target_tenant_id
            stats["client"] = metadata.client_name
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
    print(f"→ Intégration de {len(pdfs)} PDFs")

    by_status: dict[str, int] = {}
    t0 = time.perf_counter()
    detail: list[dict] = []

    for i, pdf in enumerate(pdfs, 1):
        stats = await process_one(pdf)
        status = stats.get("status", "?")
        by_status[status] = by_status.get(status, 0) + 1
        detail.append(stats)
        if i % 10 == 0 or stats["status"] != "ok":
            print(f"  [{i}/{len(pdfs)}] {pdf.name:55s} → {status}")

    elapsed = time.perf_counter() - t0
    print()
    print("═" * 60)
    print(f"DONE in {elapsed:.0f}s — {len(pdfs)} PDFs traités")
    for status, n in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f"  {status:25s} : {n}")
    print()

    # Erreurs détaillées
    errors = [d for d in detail if d["status"] not in ("ok", "skipped_duplicate")]
    if errors:
        print("─── ERREURS ─────────────────────────────────────────────────")
        for e in errors[:20]:
            print(f"  {e['file']:50s} {e['status']:20s} {e.get('error', '')[:80]}")


if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else "/tmp/taiyat_batch"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    asyncio.run(main(directory, limit))
