"""Re-passe `run_auto_fill` (S1-S5) sur tous les imports PREVIEW.

Utilise le pipeline v2 complet :
  - S1 : norm_exact (match catalogue strict)
  - S2 : article_fournisseur
  - S3 : correction_history
  - S4 : Soft TF-IDF smart (avec marque_entrante + candidates_marques)
  - S5 : OpenFoodFacts (EAN pour produits grand public)

Usage :
    docker exec -w /app futurproj_api bash -c 'PYTHONPATH=/app python scripts/bulk_reclassify_imports.py'
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import AsyncSessionLocal
from app.models.catalogue.etl_import import EtlImport
from app.services.catalogue.etl_auto_fill import run_auto_fill


async def main(vendor_filter: str | None = None, dry_run: bool = False) -> None:
    async with AsyncSessionLocal() as db:
        stmt = select(EtlImport).where(EtlImport.statut == "PREVIEW")
        if vendor_filter:
            stmt = stmt.where(EtlImport.vendor_code == vendor_filter)
        imports = list((await db.execute(stmt)).scalars())
        print(f"→ {len(imports)} imports PREVIEW à reclassifier")
        print(f"  vendor : {vendor_filter or 'ALL'}  dry_run : {dry_run}")
        print()

        totals = {"s1_norm_exact": 0, "s2_article_four": 0,
                  "s3_history": 0, "s4_tfidf": 0, "s5_off": 0, "total_fields": 0}

        for i, imp in enumerate(imports, 1):
            lignes = list(imp.lignes_data or [])
            if not lignes:
                continue
            stats = await run_auto_fill(db, lignes, vendor_code=imp.vendor_code)
            for k, v in stats.items():
                if k in totals:
                    totals[k] += v

            # Forcer JSONB update
            imp.lignes_data = list(lignes)
            flag_modified(imp, "lignes_data")

            if i % 20 == 0 or i == len(imports):
                print(f"  ... {i}/{len(imports)} imports traités "
                      f"(s1={totals['s1_norm_exact']} s4={totals['s4_tfidf']} s5={totals['s5_off']})")

        print()
        print("═" * 60)
        print("TOTALS:")
        for k, v in totals.items():
            print(f"  {k:<20} {v:>6}")

        if dry_run:
            await db.rollback()
            print("\n(DRY-RUN : aucune écriture DB)")
            return

        await db.commit()
        print("\n✓ Imports reclassifiés + sauvés")


def cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendor", default=None,
                        help="Filtrer (TAIYAT, EUROCIEL, ETHAN, GNANAM, METRO)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(main(vendor_filter=args.vendor, dry_run=args.dry_run))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    cli()
