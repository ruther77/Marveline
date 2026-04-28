"""Rattrapage des fichiers source ETL manquants.

Problème résolu : les scripts bulk historiques (taiyat/ethan/eurociel/gnanam)
créaient des EtlImport sans persister le fichier source → frontend affiche
"PDF non disponible" (fichier_path IS NULL en base).

Ce script scanne les imports concernés, cherche le fichier source dans les
dossiers fournis, le copie vers `uploads/etl/{id}.ext` et met à jour
`EtlImport.fichier_path`.

Usage :
    docker exec -w /app futurproj_api bash -c '
        PYTHONPATH=/app python scripts/backfill_etl_pdfs.py \\
            --source-dirs /app/docs/TAIYAT/factures_individuelles \\
            --source-dirs /tmp/eurociel_sources \\
            [--commit]'

Arguments :
    --source-dirs  : dossiers où chercher les fichiers source (récursif).
                     Répéter pour plusieurs dossiers.
    --vendor       : filtrer sur un vendor_code (ex: TAIYAT). Défaut : tous.
    --commit       : écrire en base. Sans ce flag : dry-run.
    --limit        : nb max d'imports à traiter (utile pour tester).

Stratégie de recherche :
  - `fichier_source` peut être "foo.pdf" ou "foo.pdf#numero" (multi-factures).
    On extrait la partie avant `#` comme nom de fichier à chercher.
  - Recherche case-insensitive, récursive dans chaque source-dir.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import and_, or_, select

from app.core.database import AsyncSessionLocal
from app.models.catalogue.etl_import import EtlImport
from app.services.catalogue.etl_pdf_storage import persist_etl_source

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill_etl")
logger.setLevel(logging.INFO)


def _source_basename(fichier_source: str) -> str:
    """Extrait le nom de fichier recherchable depuis `fichier_source`.

    Formats observés :
      - "TAIYAT_INCONTOURNABLE_214370_05032024.pdf" → direct
      - "eurociel_batch.pdf#2425" → "eurociel_batch.pdf"
      - "ethan_export.xlsx#INV001" → "ethan_export.xlsx"
    """
    return fichier_source.split("#", 1)[0].strip()


def _build_file_index(source_dirs: list[Path]) -> dict[str, Path]:
    """Indexe tous les fichiers des source_dirs par nom (lowercase).

    Conflits (même nom dans plusieurs dossiers) : le premier gagne,
    warning émis pour les suivants.
    """
    index: dict[str, Path] = {}
    for src_dir in source_dirs:
        if not src_dir.is_dir():
            logger.warning("source_dir absent ou pas un dossier : %s", src_dir)
            continue
        count = 0
        for f in src_dir.rglob("*"):
            if not f.is_file():
                continue
            key = f.name.lower()
            if key in index:
                logger.debug(
                    "Fichier dupliqué ignoré : %s (premier gagne : %s)",
                    f, index[key],
                )
                continue
            index[key] = f
            count += 1
        logger.info("Indexé %d fichier(s) depuis %s", count, src_dir)
    return index


async def _find_candidates(
    vendor_filter: Optional[str],
    limit: Optional[int],
) -> list[EtlImport]:
    """Retourne les EtlImport sans fichier_path mais avec fichier_source."""
    async with AsyncSessionLocal() as db:
        stmt = select(EtlImport).where(
            and_(
                EtlImport.fichier_path.is_(None),
                EtlImport.fichier_source.isnot(None),
            )
        )
        if vendor_filter:
            stmt = stmt.where(EtlImport.vendor_code == vendor_filter)
        stmt = stmt.order_by(EtlImport.id)
        if limit:
            stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())


async def _backfill_one(
    etl_import_id: int,
    source_file: Path,
    commit: bool,
) -> Optional[str]:
    """Persiste le fichier source et met à jour `fichier_path` en base.

    Returns:
        Le `fichier_path` relatif écrit, ou None si échec.
    """
    async with AsyncSessionLocal() as db:
        obj = await db.get(EtlImport, etl_import_id)
        if obj is None:
            logger.warning("EtlImport %d introuvable", etl_import_id)
            return None
        if obj.fichier_path:
            logger.debug("EtlImport %d déjà peuplé (%s), skip", etl_import_id, obj.fichier_path)
            return obj.fichier_path

        fichier_path = persist_etl_source(etl_import_id, source_file)
        if not fichier_path:
            return None

        if commit:
            obj.fichier_path = fichier_path
            await db.commit()
        return fichier_path


async def main(
    source_dirs: list[Path],
    vendor_filter: Optional[str],
    commit: bool,
    limit: Optional[int],
) -> int:
    print(f"→ Backfill ETL PDFs  (dry-run={not commit})")
    print(f"  Source dirs : {[str(d) for d in source_dirs]}")
    print(f"  Vendor      : {vendor_filter or 'ALL'}")
    print(f"  Limit       : {limit or 'none'}")
    print()

    index = _build_file_index(source_dirs)
    if not index:
        print("ERREUR : aucun fichier trouvé dans les source_dirs")
        return 1

    candidates = await _find_candidates(vendor_filter, limit)
    print(f"→ {len(candidates)} import(s) à traiter")
    print()

    stats = {"found": 0, "not_found": 0, "persisted": 0, "skipped_duplicate_source": 0}
    not_found_examples: list[str] = []

    for obj in candidates:
        basename = _source_basename(obj.fichier_source or "")
        key = basename.lower()
        match = index.get(key)

        if match is None:
            stats["not_found"] += 1
            if len(not_found_examples) < 10:
                not_found_examples.append(
                    f"  id={obj.id} vendor={obj.vendor_code} source={obj.fichier_source!r}"
                )
            continue

        stats["found"] += 1
        fichier_path = await _backfill_one(obj.id, match, commit=commit)
        if fichier_path:
            stats["persisted"] += 1
            action = "COMMIT" if commit else "DRY-RUN"
            print(f"  [{action}] id={obj.id:>4}  {obj.vendor_code:<10} "
                  f"{basename[:50]:<50} → {fichier_path}")

    print()
    print("═" * 60)
    print(f"DONE  —  {len(candidates)} imports examinés")
    print(f"  found in source dirs   : {stats['found']}")
    print(f"  persisted to uploads   : {stats['persisted']}")
    print(f"  NOT found              : {stats['not_found']}")

    if not_found_examples:
        print()
        print("─── EXEMPLES NOT FOUND (10 max) ──────────────────────────")
        for line in not_found_examples:
            print(line)

    if not commit and stats["persisted"] > 0:
        print()
        print(">>> DRY-RUN : relancez avec --commit pour écrire les changements en base <<<")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--source-dirs", type=Path, action="append", required=True,
        help="Dossier contenant les fichiers source (répéter pour plusieurs).",
    )
    parser.add_argument(
        "--vendor", default=None,
        help="Filtrer sur un vendor_code (TAIYAT, EUROCIEL, ETHAN, GNANAM).",
    )
    parser.add_argument(
        "--commit", action="store_true",
        help="Écrire les changements en base (par défaut : dry-run).",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Nb max d'imports à traiter.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    rc = asyncio.run(main(
        source_dirs=args.source_dirs,
        vendor_filter=args.vendor,
        commit=args.commit,
        limit=args.limit,
    ))
    sys.exit(rc)
