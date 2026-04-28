"""Seed le brand_dictionary depuis le CatalogueProduit existant.

Objectif : les marques déjà saisies manuellement par l'opérateur lors de la
validation d'imports précédents doivent alimenter le dictionnaire vivant, pour
qu'elles soient reconnues automatiquement sur les prochains imports (ETHAN,
EUROCIEL, GNANAM — parsers sans extraction de marque intégrée).

Stratégie :
  1. Scan tous les CatalogueProduit avec (marque non vide, categorie_code non AUTRE)
  2. Normaliser marque → majuscules, trim
  3. Pour chaque (marque, categorie_code), `bd.add(..., source="catalogue_seed")`
  4. `bd.save()` en fin

Idempotent : add() ne duplique pas. Peut être rerun sans risque.

Usage :
    docker compose exec -T api python -m scripts.seed_brand_dictionary_from_catalogue [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal as async_session_factory
from app.models.catalogue.catalogue_produit import CatalogueProduit


# Marques "fantômes" à ne jamais seed — tokens parasites vus en base
_BLACKLIST = frozenset({
    "AUTRE", "DIVERS", "N/A", "NONE", "NULL", "_", "-", "?",
    "MARQUE", "SANS MARQUE", "SANS", "INCONNU",
})


def _normalize_brand(raw: str) -> str | None:
    s = (raw or "").strip().upper()
    if not s or s in _BLACKLIST:
        return None
    if len(s) < 2:  # 1 lettre = bruit
        return None
    if s.isdigit() and len(s) < 2:
        return None
    return s


async def seed(dry_run: bool = False) -> None:
    from scripts.etl.parsers.brand_dictionary import get_brand_dictionary

    bd = get_brand_dictionary()
    seed_size_before = bd.size

    async with async_session_factory() as db:
        stmt = select(
            CatalogueProduit.marque,
            CatalogueProduit.categorie_code,
        ).where(
            CatalogueProduit.marque.isnot(None),
            CatalogueProduit.categorie_code.isnot(None),
            CatalogueProduit.categorie_code != "AUTRE",
        )
        rows = (await db.execute(stmt)).all()

    # Agrégation : marque → set[cat] (éviter de compter chaque occurrence
    # comme un call `add()`, on consolide d'abord)
    by_brand: dict[str, set[str]] = {}
    skipped = 0
    for marque_raw, cat in rows:
        norm = _normalize_brand(marque_raw)
        if not norm or not cat:
            skipped += 1
            continue
        by_brand.setdefault(norm, set()).add(cat)

    print(f"→ {len(rows)} produits avec marque scannés")
    print(f"→ {len(by_brand)} marques distinctes extraites ({skipped} écartés)")

    added_new = 0
    extended_cat = 0
    for brand, cats in by_brand.items():
        existed = bd.contains(brand)
        changed = bd.add(brand, list(cats), source="catalogue_seed")
        if not existed:
            added_new += 1
        elif changed:
            extended_cat += 1

    print(f"→ {added_new} nouvelles marques ajoutées")
    print(f"→ {extended_cat} marques existantes étendues (nouvelle catégorie)")
    print(f"→ size brand_dict : {seed_size_before} → {bd.size}")

    if dry_run:
        print("(DRY-RUN : aucune écriture fichier)")
        return

    bd.save()
    print(f"✓ brand_dictionary.json écrit ({bd.size} entrées)")


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
