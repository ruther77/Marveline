"""Ré-ordonnance les mappings ingrédient → produits épicerie pour privilégier
les gros formats (vrac) pour les ingrédients en kg/L.

Règle métier (2026-04-21) : le restaurant reconditionne les produits depuis
les gros formats (1kg, 5kg, 10kg, 25kg…). Il faut donc consommer en priorité
les produits à `facteur_conv` élevé avant de descendre vers les petits
conditionnements type 68g ou 250g.

Stratégie :
  - Ingrédients en 'kg' ou 'L' : trier mappings par facteur_conv DESC
    (gros format en tête)
  - Ingrédients en 'pièce', 'bouteille', 'canette', 'unité', 'botte',
    'sachet', 'boîte' : ordre conservé (facteur_conv = 1.0 partout,
    pas de notion de vrac)
  - Mise à jour de l'ordre (0 = préféré, N-1 = dernier fallback)

Usage :
    docker compose exec -T api python -m scripts.reprioritize_ingredient_mappings [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal as async_session_factory
from app.models.epicerie.produit import EpicerieProduit
from app.models.restaurant.ingredient_epicerie_mapping import IngredientEpicerieMapping
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant

# Unités pour lesquelles on trie par facteur_conv DESC (vrac prioritaire)
BULK_UNITES = {"kg", "g", "l", "cl", "ml"}


async def reprioritize(dry_run: bool = False) -> None:
    async with async_session_factory() as db:
        # Charger tous les ingrédients qui ont au moins un mapping
        ingr_stmt = (
            select(IngredientRestaurant)
            .where(IngredientRestaurant.is_active.is_(True))
            .join(
                IngredientEpicerieMapping,
                IngredientEpicerieMapping.ingredient_id == IngredientRestaurant.id,
            )
            .distinct()
        )
        ingredients = list((await db.execute(ingr_stmt)).scalars())
        print(f"→ {len(ingredients)} ingrédients avec mappings à examiner")

        nb_reorders = 0
        nb_inchanges = 0

        for ing in ingredients:
            # Charger mappings + produit joint pour affichage
            stmt = (
                select(IngredientEpicerieMapping, EpicerieProduit)
                .join(EpicerieProduit, EpicerieProduit.id == IngredientEpicerieMapping.produit_id)
                .where(
                    IngredientEpicerieMapping.ingredient_id == ing.id,
                    IngredientEpicerieMapping.tenant_id == ing.tenant_id,
                )
                .order_by(
                    IngredientEpicerieMapping.ordre.asc(),
                    IngredientEpicerieMapping.id.asc(),
                )
            )
            rows = list((await db.execute(stmt)).all())
            if not rows:
                continue

            unite = ing.unite_stock.strip().lower()
            is_bulk = unite in BULK_UNITES
            if is_bulk:
                # Trier par facteur_conv DESC (gros format d'abord).
                sorted_rows = sorted(
                    rows,
                    key=lambda r: (
                        -float(r[0].facteur_conv),
                        r[0].ordre,
                        r[0].id,
                    ),
                )
            else:
                # Conserver l'ordre actuel mais compacter la séquence (0,1,2…).
                sorted_rows = sorted(rows, key=lambda r: (r[0].ordre, r[0].id))

            # Changement nécessaire ? (soit identité différente, soit gap d'ordre)
            needs_update = any(
                rows[i][0].id != sorted_rows[i][0].id
                or sorted_rows[i][0].ordre != i
                for i in range(len(rows))
            )
            if not needs_update:
                nb_inchanges += len(rows)
                continue

            print(f"\n  {ing.nom!r} ({unite}) — réordonnancement :")
            for new_ordre, (mapping, produit) in enumerate(sorted_rows):
                old_ordre = mapping.ordre
                marker = "  " if old_ordre == new_ordre else "★ "
                print(
                    f"    {marker}#{new_ordre} (ex #{old_ordre}) "
                    f"facteur={mapping.facteur_conv} "
                    f"{produit.designation_clean!r}"
                )
                if not dry_run and old_ordre != new_ordre:
                    mapping.ordre = new_ordre
                    mapping.notes = (
                        (mapping.notes or "") + " | priorisation gros formats"
                    )[:500]
            nb_reorders += 1

        if not dry_run:
            await db.commit()

        print("\n" + "=" * 60)
        print(f"Ingrédients réordonnés : {nb_reorders}")
        print(f"Mappings inchangés     : {nb_inchanges}")
        if dry_run:
            print("(DRY-RUN : aucune écriture effectuée)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(reprioritize(dry_run=args.dry_run))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
