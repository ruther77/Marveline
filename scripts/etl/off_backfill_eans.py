"""Backfill EAN via OpenFoodFacts sur tous les produits catalogue sans EAN.

Pour chaque catalogue_produit sans EAN mais avec marque+désignation, interroge
OFF (cache Redis 30j). Si un EAN est trouvé avec marque matchante et popularité,
l'attribue au produit catalogue et le propage sur les epicerie_produits
correspondants (par désignation normalisée, tenant 2).

Usage :
    docker exec -w /app futurproj_api python3 scripts/etl/off_backfill_eans.py \\
        [--limit N] [--apply] [--vendor TAIYAT,ETHAN]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.services.catalogue.off_enrichment import find_ean_by_brand_and_designation


async def main_async(args) -> None:
    db_url = os.environ["DATABASE_URL"]
    if db_url.startswith("postgresql+psycopg2://"):
        db_url = db_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url)

    vendor_filter = [v.strip().upper() for v in args.vendor.split(",")] if args.vendor else None

    stats = {
        "scanned": 0, "no_marque": 0, "no_desig": 0,
        "off_found": 0, "off_miss": 0, "off_errors": 0,
        "cat_updated": 0, "ep_updated": 0,
        "ean_conflict": 0,
    }

    async with engine.begin() as conn:
        where_vendor = "AND source_fournisseur = ANY(:vendors)" if vendor_filter else ""
        limit_clause = f"LIMIT {args.limit}" if args.limit else ""
        rows = await conn.execute(text(
            f"SELECT id, designation, marque, source_fournisseur "
            f"FROM catalogue_produits "
            f"WHERE (ean IS NULL OR ean = '') "
            f"  AND merged_into_id IS NULL "
            f"  AND marque IS NOT NULL AND marque <> '' "
            f"  AND designation IS NOT NULL AND designation <> '' "
            f"  {where_vendor} "
            f"ORDER BY id {limit_clause}"
        ), {"vendors": vendor_filter} if vendor_filter else {})
        targets = rows.fetchall()

    print(f"→ {len(targets)} produits sans EAN à interroger (filtre vendor={vendor_filter})")

    for i, (cat_id, desig, marque, vendor) in enumerate(targets, 1):
        stats["scanned"] += 1
        if not marque:
            stats["no_marque"] += 1
            continue
        if not desig:
            stats["no_desig"] += 1
            continue

        try:
            result = await find_ean_by_brand_and_designation(marque, desig)
        except Exception as exc:
            stats["off_errors"] += 1
            print(f"  [{i}] ERREUR OFF {marque!r} / {desig!r}: {exc}")
            continue

        if result is None:
            stats["off_miss"] += 1
            if i % 20 == 0:
                print(f"  [{i}/{len(targets)}] avancement — found={stats['off_found']} miss={stats['off_miss']}")
            continue

        stats["off_found"] += 1
        new_ean = result["ean"]

        if args.apply:
            # Vérifier conflit EAN (UNIQUE constraint sur catalogue_produits.ean)
            async with engine.begin() as conn:
                existing = await conn.execute(text(
                    "SELECT id FROM catalogue_produits WHERE ean = :e AND id != :i"
                ), {"e": new_ean, "i": cat_id})
                if existing.first():
                    # Conflit : ajouter comme EAN secondaire
                    stats["ean_conflict"] += 1
                    await conn.execute(text(
                        "INSERT INTO catalogue_produit_eans "
                        "  (catalogue_produit_id, ean, source_fournisseur) "
                        "VALUES (:c, :e, :src) "
                        "ON CONFLICT DO NOTHING"
                    ), {"c": cat_id, "e": new_ean, "src": f"off:{vendor}"})
                else:
                    await conn.execute(text(
                        "UPDATE catalogue_produits SET ean = :e WHERE id = :i"
                    ), {"e": new_ean, "i": cat_id})
                    stats["cat_updated"] += 1

                # Propage vers epicerie_produits (tenant 2) par désignation
                ep_rows = await conn.execute(text(
                    "SELECT id FROM epicerie_produits "
                    "WHERE tenant_id = 2 AND (ean IS NULL OR ean = '') "
                    "  AND LOWER(TRIM(designation_clean)) = LOWER(TRIM(:d))"
                ), {"d": desig})
                ep_ids = [r[0] for r in ep_rows.fetchall()]
                for ep_id in ep_ids:
                    # Vérifier conflit EAN côté épicerie aussi
                    ep_exists = await conn.execute(text(
                        "SELECT id FROM epicerie_produits "
                        "WHERE tenant_id = 2 AND ean = :e AND id != :i"
                    ), {"e": new_ean, "i": ep_id})
                    if not ep_exists.first():
                        await conn.execute(text(
                            "UPDATE epicerie_produits SET ean = :e WHERE id = :i"
                        ), {"e": new_ean, "i": ep_id})
                        stats["ep_updated"] += 1

        if i % 20 == 0:
            print(f"  [{i}/{len(targets)}] avancement — found={stats['off_found']} miss={stats['off_miss']} updated={stats['cat_updated']}")

    print()
    print("=" * 60)
    print("RESULTATS")
    print("=" * 60)
    for k, v in stats.items():
        print(f"  {k:20s} {v}")
    print()
    if not args.apply:
        print("[DRY-RUN] --apply pour appliquer")

    await engine.dispose()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--vendor", type=str, default=None,
                    help="Filtre vendor (ex: TAIYAT,ETHAN). Défaut: tous non-METRO.")
    args = ap.parse_args()
    if args.vendor is None:
        args.vendor = "TAIYAT,ETHAN,EUROCIEL"
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
