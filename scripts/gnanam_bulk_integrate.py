"""Bulk integration GNANAM — OCR des 145 photos HEIC + preview.

Contrairement aux autres vendors, GNANAM ne commit PAS automatiquement :
chaque facture OCR-ée reste en PREVIEW pour relecture par l'opérateur
(car qualité OCR variable). Un rapport agrégé est produit.

Usage :
    docker exec -w /app futurproj_api bash -c 'PYTHONPATH=/app python scripts/gnanam_bulk_integrate.py /tmp/gnanam_photos'
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
from scripts.etl.parsers.gnanam import parse_facture

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("gnanam_bulk")
logger.setLevel(logging.INFO)


async def process_one(photo: Path) -> dict:
    stats: dict = {"file": photo.name, "status": "preview"}
    try:
        lignes, metadata = parse_facture(str(photo))
    except Exception as exc:
        return {"file": photo.name, "status": "parse_error", "error": str(exc)[:150]}

    stats["numero"] = metadata.numero_facture
    stats["date"] = metadata.date_facture.isoformat() if metadata.date_facture else None
    stats["quality"] = metadata.quality_score
    stats["nb_lignes"] = len(lignes)

    if metadata.quality_score is None or metadata.quality_score < 40:
        stats["status"] = "ocr_too_poor"
        return stats

    async with AsyncSessionLocal() as db:
        try:
            # Idempotence par numero si présent
            if metadata.numero_facture:
                existing = await db.execute(
                    select(EtlImport).where(
                        EtlImport.numero_facture == metadata.numero_facture,
                        EtlImport.vendor_code == "GNANAM",
                        EtlImport.statut.in_(("PREVIEW", "VALIDATED", "RUNNING")),
                    ).limit(1)
                )
                if existing.scalar_one_or_none() is not None:
                    return {**stats, "status": "skipped_duplicate"}

            etl_import = EtlImport(
                fournisseur_id=None,
                fichier_source=photo.name,
                statut="PENDING",
            )
            db.add(etl_import)
            await db.flush()
            stats["import_id"] = etl_import.id

            # Persister la photo HEIC source pour affichage frontend
            fichier_path = persist_etl_source(etl_import.id, photo)
            if fichier_path:
                etl_import.fichier_path = fichier_path
                await db.flush()

            await run_import(db, lignes, etl_import.id, metadata=metadata, preview_mode=True)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            return {**stats, "status": "preview_error", "error": str(exc)[:200]}

    return stats


async def main(directory: str) -> None:
    photos = sorted(Path(directory).glob("*.HEIC"))
    print(f"→ {len(photos)} photos à OCR-iser")

    by_status: dict[str, int] = {}
    quality_buckets = {"0-39 (rejet)": 0, "40-59 (partiel)": 0, "60-79 (ok)": 0, "80-100 (bon)": 0}
    t0 = time.perf_counter()
    total_lignes = 0

    for i, photo in enumerate(photos, 1):
        result = await process_one(photo)
        status = result.get("status", "?")
        by_status[status] = by_status.get(status, 0) + 1
        total_lignes += result.get("nb_lignes", 0)
        q = result.get("quality", 0) or 0
        if q < 40:
            quality_buckets["0-39 (rejet)"] += 1
        elif q < 60:
            quality_buckets["40-59 (partiel)"] += 1
        elif q < 80:
            quality_buckets["60-79 (ok)"] += 1
        else:
            quality_buckets["80-100 (bon)"] += 1
        if i % 20 == 0:
            print(f"  [{i}/{len(photos)}] {photo.name} → {status} q={q} lignes={result.get('nb_lignes', 0)}")

    elapsed = time.perf_counter() - t0
    print()
    print(f"DONE in {elapsed:.0f}s — {len(photos)} photos, {total_lignes} lignes extraites au total")
    for status, n in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f"  {status:20s} : {n}")
    print()
    print("Distribution qualité OCR :")
    for bucket, n in quality_buckets.items():
        print(f"  {bucket:20s} : {n}")


if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else "/tmp/gnanam_photos"
    asyncio.run(main(directory))
