"""Applique l'auto-fill multi-couches (S1-S4) aux imports PREVIEW existants.

Complément de `reenrich_preview_imports.py` : alors que celui-là enrichit
depuis la désignation (extraction regex/tokenizer), celui-ci fait le matching
catalogue → auto-fill EAN/marque/cat/cond/prix via les 4 couches décrites
dans `app/services/catalogue/etl_auto_fill.py`.

Usage :
    docker compose exec -T api python -m scripts.backfill_autofill_preview_imports [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import AsyncSessionLocal as async_session_factory
from app.models.catalogue.etl_import import EtlImport
from app.repositories.catalogue.catalogue_produit import (
    AsyncCatalogueProduitRepository,
)
from app.services.catalogue.etl_auto_fill import run_auto_fill
from app.services.catalogue.etl_import_service import compute_line_confidence
from app.etl_types import LigneParsee


async def run(dry_run: bool = False) -> None:
    async with async_session_factory() as db:
        stmt = select(EtlImport).where(EtlImport.statut.in_(["PREVIEW", "PARTIEL"]))
        imports = list((await db.execute(stmt)).scalars())
        print(f"→ {len(imports)} imports PREVIEW à backfill")
        if not imports:
            return

        produit_repo = AsyncCatalogueProduitRepository(db)
        preview_candidates = await produit_repo.get_all_candidates()
        print(f"→ {len(preview_candidates)} produits candidats")

        totals = {"s1_norm_exact": 0, "s2_article_four": 0,
                  "s3_history": 0, "s4_tfidf": 0, "total_fields": 0,
                  "imports_touched": 0}
        per_vendor: dict[str, dict[str, int]] = {}

        for i, imp in enumerate(imports, 1):
            lignes_raw = list(imp.lignes_data or [])
            if not lignes_raw:
                continue
            stats = await run_auto_fill(
                db, lignes_raw,
                vendor_code=imp.vendor_code,
                preview_candidates=preview_candidates,
                produit_repo=produit_repo,
            )
            # Recalcul confidence après auto-fill
            for ligne in lignes_raw:
                try:
                    stub = LigneParsee(
                        designation=ligne.get("designation", "") or "",
                        unite_base=ligne.get("unite_base", "U") or "U",
                        source_fournisseur=ligne.get("source_fournisseur", "") or "",
                        ean=ligne.get("ean"),
                        marque=ligne.get("marque"),
                        categorie_code=ligne.get("categorie_code"),
                        quantite=ligne.get("quantite"),
                        prix_unitaire_cts=ligne.get("prix_unitaire_cts"),
                        montant_ht_cts=ligne.get("montant_ht_cts"),
                    )
                    ligne["confidence_score"] = compute_line_confidence(stub)
                except Exception:
                    pass
            imp.lignes_data = list(lignes_raw)
            flag_modified(imp, "lignes_data")

            if stats["total_fields"] > 0:
                totals["imports_touched"] += 1
                for k, v in stats.items():
                    totals[k] = totals.get(k, 0) + v
                bucket = per_vendor.setdefault(
                    imp.vendor_code or "UNKNOWN",
                    {"nb": 0, "fields": 0},
                )
                bucket["nb"] += 1
                bucket["fields"] += stats["total_fields"]

            if i % 20 == 0:
                print(f"  ... {i}/{len(imports)} imports traités")

        print("\n── Synthèse ─────────────────────────────────")
        print(f"  Imports touchés      : {totals['imports_touched']}/{len(imports)}")
        print(f"  Champs auto-fillés   : {totals['total_fields']}")
        print(f"   - S1 norm exact    : {totals['s1_norm_exact']}")
        print(f"   - S2 article four. : {totals['s2_article_four']}")
        print(f"   - S3 history replay: {totals['s3_history']}")
        print(f"   - S4 tfidf graduel : {totals['s4_tfidf']}")
        for v, b in sorted(per_vendor.items(), key=lambda x: -x[1]["fields"]):
            print(f"  {v:10s} : {b['fields']} champs sur {b['nb']} imports")

        if dry_run:
            await db.rollback()
            print("\n(DRY-RUN : aucune écriture DB)")
            return
        await db.commit()
        print("\n✓ Imports PREVIEW mis à jour")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(run(dry_run=args.dry_run))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
