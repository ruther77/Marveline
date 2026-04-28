"""Pré-remplissage des mappings ingrédient restaurant → produits épicerie.

Stratégie conservative par matching nom :
  1. Normalise chaque ingrédient et chaque produit (lowercase, sans accents,
     sans parenthèses, sans "de/la/le" etc.)
  2. Score Jaccard pondéré entre tokens significatifs de l'ingrédient et
     chaque produit épicerie
  3. Conserve jusqu'à 3 meilleurs produits au-dessus du seuil 0.35
  4. Facteur_conv = 1.0 par défaut (l'utilisateur ajuste ensuite)
  5. Skip silencieusement si mapping déjà présent (UNIQUE ingredient_id, produit_id)

Usage :
    docker compose exec -T api python -m scripts.seed_ingredient_mappings [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import unicodedata
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal as async_session_factory
from app.models.epicerie.produit import EpicerieProduit
from app.models.restaurant.ingredient_epicerie_mapping import IngredientEpicerieMapping
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.models.tenant import Tenant

# Tokens ignorés (stop-words FR + unités qui polluent le matching)
STOP_WORDS = {
    "de", "du", "des", "la", "le", "les", "et", "en", "a", "au", "aux",
    "l", "d", "un", "une", "sur", "pour", "par", "avec", "ou", "u",
    "kg", "g", "l", "cl", "ml", "cts", "pc", "pcs", "u",
    "bouteille", "canette", "sachet", "boite", "pack", "pot", "paquet",
    "piece", "pieces", "unite", "unites", "botte", "bottes",
}

# Seuil minimum de score pour accepter un match
SCORE_MIN = 0.35
# Nombre max de mappings créés par ingrédient
TOP_N = 3


def normalize(text: str) -> str:
    """Supprime accents, parenthèses, passe en minuscules."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    return text.lower().strip()


def tokenize(text: str) -> set[str]:
    """Tokens significatifs : >2 lettres, hors stop-words."""
    tokens = normalize(text).split()
    return {t for t in tokens if len(t) > 2 and t not in STOP_WORDS}


def score_match(ing_tokens: set[str], prod_tokens: set[str]) -> float:
    """Score Jaccard pondéré : intersection / union des tokens ingrédient."""
    if not ing_tokens:
        return 0.0
    inter = ing_tokens & prod_tokens
    if not inter:
        return 0.0
    # Bonus si tous les tokens ingrédient sont dans le produit
    coverage = len(inter) / len(ing_tokens)
    # Pénalité si beaucoup de tokens produit n'ont rien à voir
    precision = len(inter) / len(prod_tokens) if prod_tokens else 1.0
    return 0.7 * coverage + 0.3 * precision


def facteur_default(ing_unite: str, prod_unite: str) -> Decimal:
    """Facteur de conversion par défaut. 1.0 si unités compatibles."""
    ing = ing_unite.strip().lower()
    prod = prod_unite.strip().upper()
    # Correspondances directes
    if ing in {"kg", "g"} and prod == "KG":
        return Decimal("1.0")
    if ing in {"l", "cl", "ml"} and prod == "L":
        return Decimal("1.0")
    # Pièces, bouteilles, etc. = 1 vente → 1 unité stock
    if prod == "U":
        return Decimal("1.0")
    return Decimal("1.0")


async def fetch_all_produits_epicerie(
    db: AsyncSession,
) -> list[EpicerieProduit]:
    """Charge tous les produits épicerie actifs (tous tenants app_code=epicerie)."""
    stmt = (
        select(EpicerieProduit)
        .join(Tenant, Tenant.id == EpicerieProduit.tenant_id)
        .where(Tenant.app_code == "epicerie", EpicerieProduit.actif.is_(True))
    )
    return list((await db.execute(stmt)).scalars())


async def fetch_restaurant_tenants(db: AsyncSession) -> list[int]:
    """Liste des tenant_ids restaurant actifs."""
    stmt = select(Tenant.id).where(Tenant.app_code == "restaurant", Tenant.is_active.is_(True))
    return [t for t, in (await db.execute(stmt)).all()]


async def fetch_ingredients(db: AsyncSession, tenant_id: int) -> list[IngredientRestaurant]:
    stmt = select(IngredientRestaurant).where(
        IngredientRestaurant.tenant_id == tenant_id,
        IngredientRestaurant.is_active.is_(True),
    )
    return list((await db.execute(stmt)).scalars())


async def fetch_existing_mappings(
    db: AsyncSession, tenant_id: int,
) -> set[tuple[int, int]]:
    stmt = select(
        IngredientEpicerieMapping.ingredient_id,
        IngredientEpicerieMapping.produit_id,
    ).where(IngredientEpicerieMapping.tenant_id == tenant_id)
    return {(ing, prod) for ing, prod in (await db.execute(stmt)).all()}


async def seed(dry_run: bool = False) -> None:
    async with async_session_factory() as db:
        produits = await fetch_all_produits_epicerie(db)
        print(f"→ {len(produits)} produits épicerie actifs chargés")

        prod_index: list[tuple[EpicerieProduit, set[str]]] = [
            (p, tokenize(p.designation_clean)) for p in produits
        ]

        restaurants = await fetch_restaurant_tenants(db)
        print(f"→ {len(restaurants)} tenant(s) restaurant")

        total_created = 0
        total_skipped_existing = 0
        total_ingredients_with_match = 0
        total_ingredients_without_match = 0

        for tenant_id in restaurants:
            ingredients = await fetch_ingredients(db, tenant_id)
            existing = await fetch_existing_mappings(db, tenant_id)
            print(
                f"\n── Tenant {tenant_id} : {len(ingredients)} ingrédients, "
                f"{len(existing)} mappings existants"
            )

            for ing in ingredients:
                ing_tokens = tokenize(ing.nom)
                if not ing_tokens:
                    continue

                scored: list[tuple[float, EpicerieProduit]] = []
                for prod, prod_tokens in prod_index:
                    s = score_match(ing_tokens, prod_tokens)
                    if s >= SCORE_MIN:
                        scored.append((s, prod))
                scored.sort(key=lambda x: x[0], reverse=True)
                top = scored[:TOP_N]

                if not top:
                    total_ingredients_without_match += 1
                    continue

                total_ingredients_with_match += 1
                print(f"  {ing.nom!r} ({ing.unite_stock}) →")
                ordre = 0
                for score, prod in top:
                    if (ing.id, prod.id) in existing:
                        total_skipped_existing += 1
                        continue
                    facteur = facteur_default(ing.unite_stock, prod.unite_vente)
                    print(
                        f"     [#{ordre}] {prod.designation_clean!r} "
                        f"({prod.unite_vente}) score={score:.2f} facteur={facteur}"
                    )
                    if not dry_run:
                        mapping = IngredientEpicerieMapping(
                            tenant_id=tenant_id,
                            ingredient_id=ing.id,
                            produit_id=prod.id,
                            ordre=ordre,
                            facteur_conv=facteur,
                            notes="auto-seed par similarité nom — à réviser",
                        )
                        db.add(mapping)
                        total_created += 1
                    ordre += 1

            if not dry_run:
                await db.commit()

        print("\n" + "=" * 60)
        print(f"Ingrédients avec au moins 1 match     : {total_ingredients_with_match}")
        print(f"Ingrédients sans match                : {total_ingredients_without_match}")
        print(f"Mappings créés                        : {total_created}")
        print(f"Mappings existants ignorés            : {total_skipped_existing}")
        if dry_run:
            print("(DRY-RUN : aucune écriture effectuée)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="N'écrit rien")
    args = parser.parse_args()
    try:
        asyncio.run(seed(dry_run=args.dry_run))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
