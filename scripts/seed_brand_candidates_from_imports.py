"""Bootstrap du brand_candidates tracker depuis les imports VALIDATED passés.

E4 apprend passivement à partir de chaque import futur, mais on a potentiellement
des centaines d'imports déjà validés qui portent le même signal. Ce script replay
l'apprentissage sur l'historique pour accélérer la détection des marques
récurrentes (MOGU, VIMTO, HAWAI, etc.).

À exécuter une fois après la mise en place d'E4, puis éventuellement sur demande
pour rattraper un backlog.

Usage :
    docker compose exec -T api python -m scripts.seed_brand_candidates_from_imports [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal as async_session_factory
from app.models.catalogue.etl_import import EtlImport


async def seed(dry_run: bool = False) -> None:
    from scripts.etl.parsers.brand_candidates import (
        get_brand_candidates, run_promotion_cycle,
    )
    cands = get_brand_candidates()
    before = cands.stats()

    async with async_session_factory() as db:
        stmt = (
            select(EtlImport.id, EtlImport.lignes_data)
            .where(
                EtlImport.statut.in_(["VALIDATED", "SUCCES", "PARTIEL"]),
                EtlImport.lignes_data.isnot(None),
            )
            .order_by(EtlImport.id.asc())
        )
        rows = (await db.execute(stmt)).all()

    print(f"→ {len(rows)} imports validés à rejouer")
    for import_id, lignes_data in rows:
        if not lignes_data:
            continue
        cands.record_batch(lignes_data, import_id)

    ready = cands.promote_ready()
    print(f"→ {cands.size} candidats trackés ({len(ready)} prêts à promouvoir)")
    for token, cat in ready[:20]:
        print(f"  {token!r} → {cat}")
    if len(ready) > 20:
        print(f"  ... et {len(ready) - 20} autres")

    if dry_run:
        print("(DRY-RUN : aucune écriture fichier, aucune promotion)")
        return

    cands.save()
    # PAS de promotion automatique lors du bootstrap — risque de polluer le
    # brand_dict avec des faux positifs accumulés. La promotion live n'agit
    # que sur les nouvelles validations (validate_import endpoint), ou via
    # l'endpoint admin explicite /admin/etl/brand-candidates/promote.
    print(f"✓ brand_candidates.json écrit ({cands.size} entrées)")
    print(f"→ {len(ready)} candidats prêts à promouvoir (validation manuelle requise)")
    print("   Endpoint admin : POST /admin/etl/brand-candidates/promote")
    after = cands.stats()
    print(f"Stats : {before} → {after}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(seed(dry_run=args.dry_run))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
