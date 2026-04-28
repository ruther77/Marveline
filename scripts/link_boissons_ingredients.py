"""Liaison boissons → ingrédients stock + quantite_proteine.

Logique :
  - Bouteille complète (ex: "BLACK LABEL") → 1.0 bouteille
  - 1/2 (ex: "1/2 BLACK LABEL") → 0.5 bouteille
  - 1/4 (ex: "1/4 BLACK LABEL") → 0.25 bouteille
  - CONSO (ex: "COGNAC CONSO") → 0.1 bouteille (1 dose = ~7cl sur 70cl)
  - Bières unités (ex: "1664") → 1.0 bouteille/canette

Matching : normalise le nom variante pour trouver l'ingrédient correspondant.
Mode --dry-run par défaut, --execute pour appliquer.
"""
import asyncio
import re
import sys
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.restaurant.variante_plat import VariantePlat
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant

_TENANT = 3

# Quantités par format
FORMATS = {
    "bouteille": Decimal("1.0"),
    "1/2": Decimal("0.5"),
    "1/4": Decimal("0.25"),
    "conso": Decimal("0.1"),   # ~7cl dose sur 70cl
    "grande": Decimal("1.0"),  # grande bière = 1 bouteille grande
    "petite": Decimal("1.0"),  # petite bière = 1 bouteille petite
}


def _detect_format(nom: str) -> tuple[str, str]:
    """Retourne (format, nom_base_normalise)."""
    lower = nom.strip()
    if re.match(r"^1/2\s+", lower, re.IGNORECASE):
        return "1/2", re.sub(r"^1/2\s+", "", lower, flags=re.IGNORECASE).strip()
    if re.match(r"^1/4\s+", lower, re.IGNORECASE):
        return "1/4", re.sub(r"^1/4\s+", "", lower, flags=re.IGNORECASE).strip()
    if lower.lower().endswith(" conso"):
        return "conso", lower[: -len(" conso")].strip()
    if lower.lower().startswith("conso "):
        return "conso", lower[len("conso ") :].strip()
    if lower.lower().startswith("grande "):
        return "grande", lower[len("grande ") :].strip()
    if lower.lower().startswith("petite "):
        return "petite", lower[len("petite ") :].strip()
    return "bouteille", lower


_TYPO_MAP = {
    "balleys": "baileys",
    "guiness": "guinness",
    "heinekein": "heineken",
    "compari": "campari",
    "veuve clicot": "veuve clicquot",
    "redbull": "red bull",
    "moyen vin": "vin generique",
    "vin 20": "vin generique",
    "vin 25": "vin generique",
    "vin 30": "vin generique",
    "vin 50": "vin generique",
    "coupe moet": "moet",
    "coupe veuve clicot": "veuve clicquot",
    "conso whisky": "whisky generique",
}


def _normalize(s: str) -> str:
    """Normalise pour matching : lowercase, supprime accents courants, ponctuation."""
    s = s.lower().strip()
    s = s.replace("'", "").replace("\u2019", "").replace("-", " ")
    s = re.sub(r"\s*\(.*?\)", "", s)  # retire (70cl), (bouteille) etc.
    s = re.sub(r"\s+", " ", s)
    # Corriger les fautes de frappe connues
    for typo, correct in _TYPO_MAP.items():
        if typo in s:
            s = s.replace(typo, correct)
    return s


def _match_ingredient(
    base_name: str, format_key: str, ingredients: list[IngredientRestaurant]
) -> IngredientRestaurant | None:
    """Trouve l'ingrédient le plus pertinent pour une boisson."""
    norm = _normalize(base_name)
    best = None
    best_score = 0

    for ing in ingredients:
        ing_norm = _normalize(ing.nom)
        # Exact match du nom normalisé dans l'ingrédient
        if norm == ing_norm or norm in ing_norm:
            score = len(norm)
            # Bonus si même type de contenant
            if format_key in ("grande", "petite"):
                if format_key in ing_norm:
                    score += 50
            if score > best_score:
                best_score = score
                best = ing
        # Essai inverse : ingrédient nom dans variante nom
        elif ing_norm in norm and len(ing_norm) > 3:
            score = len(ing_norm) - 1
            if score > best_score:
                best_score = score
                best = ing

    return best


async def run(execute: bool = False):
    db_url = str(settings.DATABASE_ASYNC_URL)
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Charger tous les ingrédients du tenant restaurant
        result = await db.execute(
            select(IngredientRestaurant).where(
                IngredientRestaurant.tenant_id == _TENANT,
                IngredientRestaurant.is_active.is_(True),
            )
        )
        ingredients = list(result.scalars().all())

        # Charger les boissons sans lien ingrédient
        result = await db.execute(
            select(VariantePlat).where(
                VariantePlat.tenant_id == _TENANT,
                VariantePlat.type == "boisson",
                VariantePlat.is_active.is_(True),
            ).order_by(VariantePlat.nom)
        )
        boissons = list(result.scalars().all())

        linked = 0
        skipped = 0
        not_found = []

        for b in boissons:
            format_key, base_name = _detect_format(b.nom)
            qtite = FORMATS.get(format_key, Decimal("1.0"))
            ing = _match_ingredient(base_name, format_key, ingredients)

            if ing is None:
                not_found.append((b.nom, base_name, format_key))
                skipped += 1
                continue

            already = b.ingredient_proteine_id == ing.id and b.quantite_proteine == float(qtite)
            if already:
                print(f"  OK  {b.nom:30s} → {ing.nom:30s} (x{qtite}) [deja lie]")
                skipped += 1
                continue

            print(f"  {'LINK' if execute else 'PLAN':4s} {b.nom:30s} → {ing.nom:30s} (x{qtite})")
            if execute:
                b.ingredient_proteine_id = ing.id
                b.quantite_proteine = float(qtite)
                linked += 1

        if execute:
            await db.commit()

        print(f"\n{'EXECUTE' if execute else 'DRY-RUN'}: {linked} lies, {skipped} ignores")
        if not_found:
            print(f"\nSans correspondance ({len(not_found)}):")
            for nom, base, fmt in not_found:
                print(f"  ? {nom:30s} (base='{base}', format={fmt})")

    await engine.dispose()


if __name__ == "__main__":
    execute = "--execute" in sys.argv
    asyncio.run(run(execute))
