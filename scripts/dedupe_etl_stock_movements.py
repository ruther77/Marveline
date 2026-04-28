"""Dédoublonnage des mouvements de stock ETL créés par double-validation.

Contexte (incident 2026-04-21) : entre 14h et 15h, plusieurs imports validés
ont vu leurs mouvements rejoués 2 à 6 fois, gonflant le stock actuel de 2×
à 6× sa valeur réelle. Cause : endpoint `validate_import` non-idempotent +
bug UI de double-submission.

Stratégie :
  1. Pour chaque `etl_import_id` avec N vagues de mouvements (séparées de
     >3 secondes), identifier la première vague = celle au plus ancien
     timestamp.
  2. Supprimer tous les mouvements des vagues suivantes.
  3. Recalculer `stock_apres` en chaîne pour chaque produit concerné.
  4. Recalculer `epicerie_stock.quantite` comme somme des mouvements restants.

Usage :
    docker compose exec -T api python -m scripts.dedupe_etl_stock_movements [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal as async_session_factory
from app.models.epicerie.stock import EpicerieStock
from app.models.epicerie.stock_movement import EpicerieStockMovement

# Seuil pour grouper les mouvements en "vagues" : si gap < WAVE_GAP_SECONDS
# avec mouvement précédent, même vague.
WAVE_GAP_SECONDS = 3


async def dedupe(dry_run: bool = False) -> None:
    async with async_session_factory() as db:
        # ── Phase 1 : identifier les imports avec vagues multiples ──────
        stmt = (
            select(EpicerieStockMovement)
            .where(
                EpicerieStockMovement.etl_import_id.is_not(None),
                EpicerieStockMovement.type == "ENTREE",
            )
            .order_by(
                EpicerieStockMovement.etl_import_id.asc(),
                EpicerieStockMovement.date_mouvement.asc(),
                EpicerieStockMovement.id.asc(),
            )
        )
        all_mvt = list((await db.execute(stmt)).scalars())
        print(f"→ {len(all_mvt)} mouvements ENTREE-ETL à analyser")

        # Grouper par etl_import_id
        mvts_by_import: dict[int, list[EpicerieStockMovement]] = {}
        for m in all_mvt:
            mvts_by_import.setdefault(m.etl_import_id, []).append(m)

        to_delete: list[EpicerieStockMovement] = []
        affected_products: set[int] = set()

        for import_id, mvts in mvts_by_import.items():
            if len(mvts) < 2:
                continue

            # Détecter les vagues par gap de timestamp
            mvts.sort(key=lambda m: (m.date_mouvement, m.id))
            first_ts = mvts[0].date_mouvement
            cutoff = first_ts + timedelta(seconds=WAVE_GAP_SECONDS)

            keep = [m for m in mvts if m.date_mouvement <= cutoff]
            drop = [m for m in mvts if m.date_mouvement > cutoff]

            if drop:
                to_delete.extend(drop)
                for m in drop:
                    affected_products.add(m.produit_id)
                # Les produits des mvts gardés aussi (pour recompute stock_apres)
                for m in keep:
                    affected_products.add(m.produit_id)

        print(f"→ {len(to_delete)} mouvements à supprimer (vagues ré-validées)")
        print(f"→ {len(affected_products)} produits à recalculer")

        if not to_delete:
            print("Aucun doublon détecté.")
            return

        # Afficher un aperçu des plus gros cas
        drop_by_product: dict[int, int] = {}
        for m in to_delete:
            drop_by_product[m.produit_id] = drop_by_product.get(m.produit_id, 0) + 1
        top = sorted(drop_by_product.items(), key=lambda x: -x[1])[:10]
        print("\nTop 10 produits les plus affectés (nb mvt à supprimer) :")
        for pid, nb in top:
            print(f"  produit_id={pid} : {nb} mouvements supprimés")

        if dry_run:
            print("\n(DRY-RUN : aucune suppression effectuée)")
            return

        # ── Phase 2 : suppression des mvts dupliqués ────────────────────
        delete_ids = [m.id for m in to_delete]
        # Batch par chunks pour éviter un IN clause trop long
        CHUNK = 500
        for i in range(0, len(delete_ids), CHUNK):
            chunk = delete_ids[i : i + CHUNK]
            await db.execute(
                delete(EpicerieStockMovement).where(
                    EpicerieStockMovement.id.in_(chunk)
                )
            )
        await db.flush()
        print(f"✓ {len(delete_ids)} mouvements supprimés")

        # ── Phase 3 : recalcul stock_apres + epicerie_stock ─────────────
        for produit_id in affected_products:
            # Recharger TOUS les mvts du produit (pas seulement ETL) pour calcul cumul
            stmt = (
                select(EpicerieStockMovement)
                .where(EpicerieStockMovement.produit_id == produit_id)
                .order_by(
                    EpicerieStockMovement.date_mouvement.asc(),
                    EpicerieStockMovement.id.asc(),
                )
            )
            mvts = list((await db.execute(stmt)).scalars())

            cumul = Decimal("0")
            for m in mvts:
                if m.type == "ENTREE":
                    cumul += Decimal(str(m.quantite))
                else:
                    cumul -= Decimal(str(m.quantite))
                m.stock_apres = cumul

            # Mettre à jour epicerie_stock.quantite
            stock_stmt = select(EpicerieStock).where(
                EpicerieStock.produit_id == produit_id
            )
            stock = (await db.execute(stock_stmt)).scalar_one_or_none()
            if stock is not None:
                stock.quantite = cumul

        await db.commit()
        print(f"✓ Stocks recalculés pour {len(affected_products)} produits")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(dedupe(dry_run=args.dry_run))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
