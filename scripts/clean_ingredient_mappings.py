"""Nettoyage des faux positifs + ajustement des facteur_conv pour les mappings
auto-seedés (étapes 2+3 du POC ingredient-sourcing).

Nettoyage (étape 2) — supprime les mappings où un pattern de faux positif
connu apparaît dans la désignation produit, en fonction du type d'ingrédient
(fruit frais vs jus, viande fraîche vs transformé, etc.).

Ajustement (étape 3) — extrait le poids/volume réel depuis la désignation
produit (ex: "25kg", "70cL", "500g") et ajuste `facteur_conv` en fonction de
l'unité stock ingrédient.

Usage :
    docker compose exec -T api python -m scripts.clean_ingredient_mappings [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal as async_session_factory
from app.models.epicerie.produit import EpicerieProduit
from app.models.restaurant.ingredient_epicerie_mapping import IngredientEpicerieMapping
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant

# ── Patterns de faux positifs ────────────────────────────────────────────────

# Mots-clés qui indiquent un type de produit incompatible selon l'ingrédient.
# Si la désignation produit contient ces mots (case-insensitive), le mapping
# est supprimé pour tout ingrédient dont le nom matche le côté gauche.
FALSE_POSITIVE_PATTERNS: list[tuple[re.Pattern[str], re.Pattern[str], str]] = [
    # Fruits frais (poids unitaire) ≠ jus en bouteille/canette
    (
        re.compile(r"\b(ananas|mangue|citron|banane|pomme|orange)\b", re.I),
        re.compile(
            r"\b(mogu|maaza|caraibos|pulco|sirop|solijavel|bs\s*ti|"
            r"\d+\s*cl)\b",
            re.I,
        ),
        "fruit frais ≠ jus/sirop/nettoyant",
    ),
    # Viande fraîche ≠ produits transformés/surgelés
    (
        re.compile(r"\b(poulet|boeuf|ailes|cuisses|brochettes|gesier)\b", re.I),
        re.compile(r"\b(nem|nuggets|halal|surgeles|surgele)\b", re.I),
        "viande fraîche ≠ transformé/surgelé",
    ),
    # Produits gras/sucrants ≠ snacks
    (
        re.compile(r"\b(vinaigre|sucre|lait|sel)\b", re.I),
        re.compile(r"\b(lay'?s|chips|toblerone|dessert)\b", re.I),
        "ingrédient base ≠ snack/dessert",
    ),
    # Pâte à cuisiner ≠ pâtes à tartiner/sablée
    (
        re.compile(r"\b(pate|pâte)\b", re.I),
        re.compile(r"\b(speculoos|tartin|sablee)\b", re.I),
        "pâte cuisine ≠ tartine/sablée",
    ),
    # Crèmes fraîches ≠ sirop
    (
        re.compile(r"\bsucre\b", re.I),
        re.compile(r"\bsirop|canne\s*1l\b", re.I),
        "sucre ≠ sirop de canne",
    ),
    # Alcools en bouteille vs version miniature ou canette
    (
        re.compile(r"\bbaileys\s*\(70cl\)", re.I),
        re.compile(r"\bdistribut|plo|mini\b", re.I),
        "bouteille 70cl ≠ distributeur/mini",
    ),
]

# ── Extraction poids/volume depuis la désignation produit ────────────────────

WEIGHT_VOLUME_PATTERN = re.compile(
    r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*(kg|g|cl|ml|l)\b",
    re.I,
)


def extract_weight_volume(designation: str) -> tuple[float, str] | None:
    """Extrait la première quantité+unité significative.

    Retourne (valeur_en_unite_canonique, unite_canonique 'kg' ou 'L')
    ou None si rien de trouvé.
    """
    matches = WEIGHT_VOLUME_PATTERN.findall(designation)
    for raw_value, raw_unit in matches:
        unit = raw_unit.lower()
        try:
            value = float(raw_value.replace(",", "."))
        except ValueError:
            continue
        if value <= 0:
            continue
        if unit == "kg":
            return value, "kg"
        if unit == "g":
            # Ignorer les valeurs trop petites (<50g) = condiments, pas source
            if value < 50:
                continue
            return value / 1000.0, "kg"
        if unit == "l":
            return value, "L"
        if unit == "cl":
            return value / 100.0, "L"
        if unit == "ml":
            if value < 50:
                continue
            return value / 1000.0, "L"
    return None


def compute_facteur(
    ing_unite: str, produit_designation: str, produit_unite_vente: str,
) -> tuple[Decimal, str] | None:
    """Détermine le facteur_conv idéal si on peut l'extraire.

    Retourne (facteur, reason) ou None si pas d'info exploitable.
    """
    ing = ing_unite.strip().lower()

    # Ingrédient en kg : on cherche un poids dans la désignation produit
    if ing == "kg":
        extracted = extract_weight_volume(produit_designation)
        if extracted and extracted[1] == "kg":
            return Decimal(str(round(extracted[0], 4))), f"poids extrait: {extracted[0]}kg"
        return None

    # Ingrédient en L : on cherche un volume
    if ing == "l":
        extracted = extract_weight_volume(produit_designation)
        if extracted and extracted[1] == "L":
            return Decimal(str(round(extracted[0], 4))), f"volume extrait: {extracted[0]}L"
        return None

    # Bouteille / canette / pièce / unité : 1 produit U = 1 ingrédient
    # (facteur déjà à 1.0, rien à ajuster)
    return None


# ── Main ─────────────────────────────────────────────────────────────────────


async def clean(dry_run: bool = False) -> None:
    async with async_session_factory() as db:
        stmt = (
            select(IngredientEpicerieMapping, IngredientRestaurant, EpicerieProduit)
            .join(IngredientRestaurant, IngredientRestaurant.id == IngredientEpicerieMapping.ingredient_id)
            .join(EpicerieProduit, EpicerieProduit.id == IngredientEpicerieMapping.produit_id)
            .where(IngredientEpicerieMapping.notes.like("auto-seed%"))
        )
        rows: list[tuple[IngredientEpicerieMapping, IngredientRestaurant, EpicerieProduit]] = list(
            (await db.execute(stmt)).all()
        )
        print(f"→ {len(rows)} mappings auto-seedés à examiner")

        nb_deleted = 0
        nb_facteur_updated = 0
        nb_unchanged = 0
        delete_reasons: dict[str, int] = {}

        for mapping, ing, prod in rows:
            # ─── Étape 2 : détection faux positif ───
            is_false_positive = False
            fp_reason = ""
            for ing_pat, prod_pat, reason in FALSE_POSITIVE_PATTERNS:
                if ing_pat.search(ing.nom) and prod_pat.search(prod.designation_clean):
                    is_false_positive = True
                    fp_reason = reason
                    break

            if is_false_positive:
                print(
                    f"  ✗ DELETE  {ing.nom!r} ← {prod.designation_clean!r} "
                    f"({fp_reason})"
                )
                delete_reasons[fp_reason] = delete_reasons.get(fp_reason, 0) + 1
                if not dry_run:
                    await db.delete(mapping)
                nb_deleted += 1
                continue

            # ─── Étape 3 : ajustement facteur_conv ───
            result = compute_facteur(ing.unite_stock, prod.designation_clean, prod.unite_vente)
            if result is None:
                nb_unchanged += 1
                continue

            new_facteur, reason = result
            if abs(float(mapping.facteur_conv) - float(new_facteur)) < 1e-6:
                nb_unchanged += 1
                continue

            print(
                f"  ✎ ADJUST  {ing.nom!r} ({ing.unite_stock}) ← "
                f"{prod.designation_clean!r} : facteur {mapping.facteur_conv} → "
                f"{new_facteur} ({reason})"
            )
            if not dry_run:
                mapping.facteur_conv = new_facteur
                mapping.notes = f"auto-seed + facteur ajusté : {reason}"
            nb_facteur_updated += 1

        if not dry_run:
            await db.commit()

        print("\n" + "=" * 60)
        print(f"Mappings supprimés (faux positifs) : {nb_deleted}")
        for reason, count in delete_reasons.items():
            print(f"   • {reason}: {count}")
        print(f"Facteurs ajustés                   : {nb_facteur_updated}")
        print(f"Mappings inchangés                 : {nb_unchanged}")
        if dry_run:
            print("(DRY-RUN : aucune écriture effectuée)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(clean(dry_run=args.dry_run))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
