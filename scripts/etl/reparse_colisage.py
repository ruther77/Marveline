"""Re-tokenise les désignations catalogue_produits pour extraire les colisages
manquants (bug 2026-04-23 : parser _QTY_PREFIXES perdait "150 SUCETTES FRUIT").

Le parser étape 4 a été corrigé (extract_colisage fallback sur NOISE position 0).
Ce script applique la correction aux produits existants sans re-parser les PDF :
  1. Re-tokenize catalogue_produits.designation via fake-words
  2. Call extract_colisage(tokens) [parser corrigé]
  3. UPDATE catalogue_produits.colisage si extrait
  4. Propage vers epicerie_produits.colisage par match EAN

Usage :
    docker exec -w /app futurproj_api python3 scripts/etl/reparse_colisage.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import os

from scripts.etl.parsers._shared.tokenizer import (
    tokenize_designation,
    extract_colisage,
)


def retokenize_text(designation: str) -> list:
    """Construit des fake-words depuis une désignation texte et tokenize."""
    parts = designation.split()
    fake_words = [
        {"text": p, "x0": float(i * 10), "x1": float(i * 10 + 5)}
        for i, p in enumerate(parts)
    ]
    return tokenize_designation(
        fake_words,
        x_min=0.0,
        x_max=1_000_000.0,
        known_brands=None,
        abbrev_dict=None,
        case_fold=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL non défini", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(database_url)
    stats = {"catalogue_scanned": 0, "catalogue_updated": 0, "epicerie_updated": 0}

    with Session(engine) as session:
        rows = session.execute(text(
            "SELECT id, designation, ean "
            "FROM catalogue_produits "
            "WHERE colisage IS NULL "
            "  AND merged_into_id IS NULL"
        )).fetchall()
        stats["catalogue_scanned"] = len(rows)
        print(f"→ {len(rows)} produits catalogue à analyser (colisage NULL)")

        updates_catalogue: list[tuple[int, int]] = []
        for row in rows:
            cp_id, designation, _ean = row
            if not designation:
                continue
            try:
                tokens = retokenize_text(designation)
                colisage = extract_colisage(tokens)
            except Exception:
                continue
            if colisage is not None and 1 < colisage <= 10_000:
                updates_catalogue.append((cp_id, colisage))

        print(f"  {len(updates_catalogue)} colisages extraits")

        if args.dry_run:
            print("DRY-RUN — 10 premiers exemples :")
            for cp_id, colisage in updates_catalogue[:10]:
                row = session.execute(
                    text("SELECT designation FROM catalogue_produits WHERE id = :id"),
                    {"id": cp_id},
                ).fetchone()
                print(f"  id={cp_id} colisage={colisage} designation={row[0]!r}")
            return

        for cp_id, colisage in updates_catalogue:
            session.execute(
                text("UPDATE catalogue_produits SET colisage = :c WHERE id = :id"),
                {"id": cp_id, "c": colisage},
            )
        stats["catalogue_updated"] = len(updates_catalogue)
        session.commit()

        # Propager vers épicerie par match EAN
        result = session.execute(text(
            "UPDATE epicerie_produits ep "
            "SET colisage = cp.colisage "
            "FROM catalogue_produits cp "
            "WHERE ep.ean = cp.ean "
            "  AND ep.ean IS NOT NULL "
            "  AND cp.colisage IS NOT NULL "
            "  AND ep.colisage IS NULL "
            "  AND cp.merged_into_id IS NULL"
        ))
        stats["epicerie_updated"] = result.rowcount or 0
        session.commit()

        # Propager aussi unite_base pour les 579 manquants, même logique
        result2 = session.execute(text(
            "UPDATE epicerie_produits ep "
            "SET unite_base = cp.unite_base "
            "FROM catalogue_produits cp "
            "WHERE ep.ean = cp.ean "
            "  AND ep.ean IS NOT NULL "
            "  AND cp.unite_base IS NOT NULL "
            "  AND ep.unite_base IS NULL "
            "  AND cp.merged_into_id IS NULL"
        ))
        stats["epicerie_unite_base_updated"] = result2.rowcount or 0
        session.commit()

    print()
    print("=" * 50)
    print(f"  Catalogue scannés          : {stats['catalogue_scanned']}")
    print(f"  Catalogue colisage update  : {stats['catalogue_updated']}")
    print(f"  Épicerie colisage update   : {stats['epicerie_updated']}")
    print(f"  Épicerie unite_base update : {stats.get('epicerie_unite_base_updated', 0)}")
    print("=" * 50)


if __name__ == "__main__":
    main()
