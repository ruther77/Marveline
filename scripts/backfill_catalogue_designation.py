"""Backfill CatalogueProduit.volume_unitaire_ml (et marque/conditionnement
quand vides) depuis la désignation existante, via l'enrichisseur partagé.

Permet au matcher OFF `by_brand_vol` de trouver des candidats pour les
produits catalogue sans volume renseigné à l'origine (cas METRO par exemple).

Usage :
    docker compose exec -T api python -m scripts.backfill_catalogue_designation [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal as async_session_factory
from app.etl_types import LigneParsee
from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.services.catalogue.etl_designation_enrichment import (
    enrich_ligne_from_designation,
)


async def run(dry_run: bool) -> None:
    async with async_session_factory() as db:
        rows = await db.execute(select(CatalogueProduit))
        products = list(rows.scalars())
        print(f"→ {len(products)} produits scannés")

        filled_vol = 0
        filled_marque = 0
        filled_cond = 0

        for prod in products:
            # Skip si tout est déjà rempli
            if (prod.volume_unitaire_ml and prod.marque and prod.conditionnement):
                continue
            stub = LigneParsee(
                designation=prod.designation or "",
                unite_base=prod.unite_base or "piece",
                source_fournisseur=prod.source_fournisseur or "",
                marque=prod.marque,
                conditionnement=prod.conditionnement,
                volume_unitaire_ml=prod.volume_unitaire_ml,
            )
            try:
                enrich_ligne_from_designation(stub)
            except Exception:
                continue
            if not prod.volume_unitaire_ml and stub.volume_unitaire_ml:
                prod.volume_unitaire_ml = stub.volume_unitaire_ml
                filled_vol += 1
            if not prod.marque and stub.marque:
                prod.marque = stub.marque
                filled_marque += 1
            if not prod.conditionnement and stub.conditionnement:
                prod.conditionnement = stub.conditionnement
                filled_cond += 1

        print(f"→ +{filled_vol} volumes, +{filled_marque} marques, +{filled_cond} conditionnements")

        if dry_run:
            await db.rollback()
            print("(DRY-RUN : aucune écriture DB)")
            return
        await db.commit()
        print("✓ Catalogue enrichi")


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
