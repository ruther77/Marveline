"""Backfill TAIYAT : re-parse chaque PDF et PATCH les produits catalogue/épicerie
existants avec les champs désormais mieux extraits (volume, colisage, marque).

Ne touche PAS aux mouvements stock, ni aux EtlImport, ni à la logique de prix.
Objectif : combler les trous vol/col/marque causés par les fixes parser récents
(UNIT_TO_ML étendu aux poids, extraction 'NxM' + unité séparée).

Algorithme :
  1. Pour chaque EtlImport TAIYAT avec fichier_path :
     1a. Re-parse le PDF
     1b. Pour chaque ligne parsée : match produit catalogue existant par
         désignation normalisée stricte (LOWER+TRIM).
     1c. Si trouvé : UPDATE catalogue_produits.volume_unitaire_ml,
         .colisage, .marque (seulement si NULL).
     1d. Record colisage dans catalogue_produit_colisages (idempotent).
     1e. Propage vers epicerie_produits (tenant 2) par même désignation.

Usage :
    docker exec -w /app futurproj_api python3 \\
        scripts/etl/reparse_taiyat_patch_inplace.py [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text

from scripts.etl.parsers.taiyat.core import parse


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Appliquer (défaut dry-run)")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
    base = Path("/app/uploads")

    stats = {
        "pdfs_parsed": 0, "pdfs_missing": 0, "pdfs_error": 0,
        "lignes_parsed": 0, "match_exact": 0, "no_match": 0,
        "cat_updated_vol": 0, "cat_updated_col": 0, "cat_updated_marque": 0,
        "ep_updated_vol": 0, "ep_updated_col": 0,
        "colisages_recorded": 0,
    }

    with engine.begin() as conn:
        imports = conn.execute(text(
            "SELECT id, fichier_path FROM etl_imports "
            "WHERE vendor_code='TAIYAT' AND fichier_path IS NOT NULL "
            "ORDER BY id"
        )).fetchall()

        for imp_id, path in imports:
            full = base / path
            if not full.exists():
                stats["pdfs_missing"] += 1
                continue
            try:
                lignes = parse(str(full))
            except Exception as exc:
                stats["pdfs_error"] += 1
                print(f"  import {imp_id} {path} : ERREUR parse {exc}")
                continue
            stats["pdfs_parsed"] += 1

            for l in lignes:
                stats["lignes_parsed"] += 1
                desig_norm = _norm(l.designation)
                if not desig_norm:
                    continue

                cat = conn.execute(text(
                    "SELECT id, volume_unitaire_ml, colisage, marque FROM catalogue_produits "
                    "WHERE source_fournisseur='TAIYAT' AND merged_into_id IS NULL "
                    "  AND LOWER(TRIM(designation)) = :d LIMIT 1"
                ), {"d": desig_norm}).first()

                if not cat:
                    stats["no_match"] += 1
                    continue
                stats["match_exact"] += 1
                cat_id, cur_vol, cur_col, cur_marque = cat

                updates_cat: dict = {}
                if l.volume_unitaire_ml and not cur_vol:
                    updates_cat["volume_unitaire_ml"] = l.volume_unitaire_ml
                    stats["cat_updated_vol"] += 1
                if l.colisage and l.colisage > 1 and (not cur_col or cur_col <= 1):
                    updates_cat["colisage"] = l.colisage
                    stats["cat_updated_col"] += 1
                if l.marque and not cur_marque:
                    updates_cat["marque"] = l.marque
                    stats["cat_updated_marque"] += 1

                if updates_cat and args.apply:
                    assignments = ", ".join(f"{k} = :{k}" for k in updates_cat)
                    params = {**updates_cat, "id": cat_id}
                    conn.execute(text(
                        f"UPDATE catalogue_produits SET {assignments} WHERE id = :id"
                    ), params)

                # Record colisage dans pivot
                if l.colisage and l.colisage > 1 and args.apply:
                    conn.execute(text(
                        "INSERT INTO catalogue_produit_colisages "
                        "  (catalogue_produit_id, colisage, source_fournisseur) "
                        "VALUES (:c, :co, 'TAIYAT') "
                        "ON CONFLICT (catalogue_produit_id, colisage, source_fournisseur) "
                        "DO UPDATE SET last_seen_at = now()"
                    ), {"c": cat_id, "co": l.colisage})
                    stats["colisages_recorded"] += 1

                # Propager vers epicerie_produits (tenant 2) par désignation
                ep = conn.execute(text(
                    "SELECT id, volume_unitaire_ml, colisage FROM epicerie_produits "
                    "WHERE tenant_id = 2 "
                    "  AND LOWER(TRIM(designation_clean)) = :d LIMIT 1"
                ), {"d": desig_norm}).first()
                if not ep:
                    continue
                ep_id, ep_vol, ep_col = ep
                updates_ep: dict = {}
                if l.volume_unitaire_ml and not ep_vol:
                    updates_ep["volume_unitaire_ml"] = l.volume_unitaire_ml
                    stats["ep_updated_vol"] += 1
                if l.colisage and l.colisage > 1 and (not ep_col or ep_col <= 1):
                    updates_ep["colisage"] = l.colisage
                    stats["ep_updated_col"] += 1
                if updates_ep and args.apply:
                    assignments = ", ".join(f"{k} = :{k}" for k in updates_ep)
                    params = {**updates_ep, "id": ep_id}
                    conn.execute(text(
                        f"UPDATE epicerie_produits SET {assignments} WHERE id = :id"
                    ), params)

        if not args.apply:
            conn.rollback()

    print()
    print("=" * 60)
    print("RESULTATS")
    print("=" * 60)
    for k, v in stats.items():
        print(f"  {k:30s} {v}")
    print()
    if not args.apply:
        print("[DRY-RUN] — relance avec --apply pour appliquer")


if __name__ == "__main__":
    main()
