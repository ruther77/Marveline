"""Mappings ingrédient → épicerie pour spiritueux, vins, champagnes, sodas.

Mappings explicites (1 ingrédient → 1 produit épicerie principal) basés sur
la correspondance marque + volume standard. Les cas ambigus (Martini en 1L
épicerie vs 70cL ingrédient, Bordeaux générique vs 50 références dispos)
sont mappés sur le candidat le plus cohérent métier.

Usage :
    docker exec -w /app futurproj_api python3 \\
        scripts/restaurant/map_spirits_wines_sodas.py [--apply]
"""
from __future__ import annotations

import argparse
import os
import sys

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text


_TENANT_RESTO = 3

# (ingredient_id, produit_epicerie_id, facteur_conv, note)
# facteur_conv = nb d'unités ingrédient par unité épicerie.
#   - 1.0 : 1 bouteille épi = 1 bouteille ingrédient (volumes équivalents)
#   - 0.7 : 1 bouteille épicerie (1L) couvre 0.7 bouteille ingrédient (70cL) → inverse : 1.4 bout. épi = 1 bout. ingr
#   En pratique : si ingr est en "bouteille" unité, on laisse facteur=1 et on
#   trace juste lequel épicerie décrémente. La quantité servie (en L) via qte_proteine
#   de la variante est ce qui compte pour le coût.
_MAPPINGS = [
    # ═══ Spiritueux (70cL ingrédient → 70cL épicerie sauf mention) ═══
    ( 98,  8690, 1.0, "Jack Daniel's → Jack Daniel's Whisky 70cL"),
    ( 99,  7592, 1.0, "Chivas → Chivas Whisky 12a 70cL"),
    (100,  7593, 1.0, "Black Label → Jwalker Black 12a Whisky 70cL"),
    (101,  7839, 1.0, "Glenfiddich → Glenfiddich Whisky 15a 70cL"),
    (102,  7715, 1.0, "JB → Jb Whisky 70cL"),
    (103,  7595, 1.0, "Baileys → Baileys Irish Creme 70cL"),
    (104,  7716, 1.0, "Vodka (générique) → Poliakov Vodka 70cL"),
    (105,  7697, 1.0, "Cognac (générique) → Hennessy Cognac Vs 70cL"),
    (106,  9039, 1.0, "Rhum (générique) → Saint James Rh 70cL"),
    (107,  7892, 1.0, "Martini (70cl ingr → 1L épi) → Martini Blanc 1L"),
    (108,  7644, 1.0, "Campari (70cl ingr → 1L épi) → Campari 25d 1L"),

    # ═══ Vins ═══
    (113,  8616, 1.0, "Vin blanc → Chardonnay IGP Loir 75cL"),
    (114,  7727, 1.0, "Bordeaux → Bordeaux Rouge Enclos Sadirac 75cL"),
    (115,  7470, 1.0, "Rosé → Cab Anjou Rse Laur 75cL"),
    (116,  8821, 1.0, "Moelleux → Sauternes Mil Sablett 75cL"),

    # ═══ Champagnes ═══
    (109,  7758, 1.0, "Moët → Moët & Chandon Imperial 75cL"),
    (110,  7826, 1.0, "Veuve Clicquot → Veuve Clicquot Brut 75cL"),
    (111,  7848, 1.0, "Ruinart → Ruinart Champagne 75cL"),
    (112,  8581, 1.0, "Nicola → Nicolas Feuillatte Tradition 75cL"),

    # ═══ Sodas/softs (Coca = 33cL selon user) ═══
    (117,  7507, 1.0, "Coca-Cola → Coca Cola 33cL"),
    (123,  7456, 1.0, "Red Bull → Red Bull 25cL"),
    (118,  7647, 1.0, "Jus de fruits → Gilbert Jus Orange 25cL"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])

    inserted = []
    skipped = []
    errors = []

    with engine.begin() as conn:
        for ingr_id, epi_id, facteur, note in _MAPPINGS:
            # Vérifier l'existence
            ingr_name = conn.execute(text(
                "SELECT nom FROM restaurant_ingredients WHERE id = :i"
            ), {"i": ingr_id}).scalar()
            epi_name = conn.execute(text(
                "SELECT designation_clean FROM epicerie_produits WHERE id = :i"
            ), {"i": epi_id}).scalar()
            if not ingr_name:
                errors.append(f"Ingredient {ingr_id} inexistant ({note})")
                continue
            if not epi_name:
                errors.append(f"Produit épicerie {epi_id} inexistant ({note})")
                continue
            existing = conn.execute(text(
                "SELECT id FROM restaurant_ingredient_epicerie_mappings "
                "WHERE ingredient_id = :i AND produit_id = :p"
            ), {"i": ingr_id, "p": epi_id}).scalar()
            if existing:
                skipped.append(f"{ingr_name} → {epi_name} (déjà mappé)")
                continue
            if args.apply:
                conn.execute(text(
                    "INSERT INTO restaurant_ingredient_epicerie_mappings "
                    "  (tenant_id, ingredient_id, produit_id, ordre, facteur_conv, notes, "
                    "   created_at, updated_at) "
                    "VALUES (:t, :i, :p, 0, :f, :n, now(), now())"
                ), {"t": _TENANT_RESTO, "i": ingr_id, "p": epi_id, "f": facteur, "n": note})
            inserted.append(f"{ingr_name} ({ingr_id}) → {epi_name} ({epi_id}) · f={facteur}")

        if not args.apply:
            conn.rollback()

    print()
    print("=" * 60)
    print(f"INSERTED ({len(inserted)}) :")
    for i in inserted:
        print(f"  ✓ {i}")
    print(f"\nSKIPPED ({len(skipped)}) :")
    for s in skipped:
        print(f"  - {s}")
    if errors:
        print(f"\nERRORS ({len(errors)}) :")
        for e in errors:
            print(f"  ⚠ {e}")
    if not args.apply:
        print("\n[DRY-RUN] --apply pour appliquer")


if __name__ == "__main__":
    main()
