"""Normalise les variantes bière + crée les mappings ingredient → produit épicerie.

Actions (toutes idempotentes) :
  A. Corriger les quantités protéine sur les variantes trio (3 bouteilles) :
       - HEINEKEIN grande (var 67) → qte=3
       - GUINESS base (var 68) → qte=3, GRANDE GUINESS (69) → qte=3
       - GRANDE DESPERADOS (78) → qte=3, DESPERADOS (77) → qte=3
  B. Splitter ingrédient 93 "Pelfort (bouteille)" en 2 :
       - Rename id 93 → "Pelforth 50cL"
       - Créer nouvel ingrédient "Pelforth 75cL"
       - Variante GRANDE PELFORT (var 82) → pointe vers nouvel ingrédient
  C. Insérer mappings bières → épicerie selon règles user validées.

Usage :
    docker exec -w /app futurproj_api python3 \\
        scripts/restaurant/fix_beer_variantes_and_mappings.py [--apply]
"""
from __future__ import annotations

import argparse
import os
import sys

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text


_TENANT_RESTO = 3

# (variante_id, nouvelle_qte_proteine, commentaire)
_VARIANTES_TRIO = [
    (67, 3.0, "HEINEKEIN 1200 = 3×65cL"),
    (68, 3.0, "GUINESS 1200 = 3×33cL"),
    (69, 3.0, "GRANDE GUINESS 1000 = 3×33cL"),
    (77, 3.0, "DESPERADOS 1000 = 3×33cL"),
    (78, 3.0, "GRANDE DESPERADOS 800 = 3×33cL"),
]

# Mappings ingredient → produit épicerie (ingr_id, epi_id, ordre, facteur_conv, notes)
_MAPPINGS = [
    # 1664 à 5€ = 75cL
    (86,  7540, 0, 1.0, "1664 → 1664 75cL"),
    # Heineken (ingredient unique pour 500 et 1200) → 65cL
    (79,  7539, 0, 1.0, "Heineken → Heineken 5d 65cL"),
    # Guinness : petite/grande/base tous → Guinness 33cL
    (82,  7864, 0, 1.0, "Guinness petite → Guinness 33cL"),
    (81,  7864, 0, 1.0, "Guinness grande → Guinness 33cL (×3 via qte)"),
    (80,  7864, 0, 1.0, "Guinness base → Guinness 33cL (×3 via qte)"),
    # Desperados : petite/grande/base tous → Desperad 33cL (7641)
    (89,  7641, 0, 1.0, "Desperados petite → Desperad 33cL"),
    (88,  7641, 0, 1.0, "Desperados grande → Desperad 33cL (×3 via qte)"),
    (87,  7641, 0, 1.0, "Desperados base → Desperad 33cL (×3 via qte)"),
    # Leffe : petite → 33cL, grande/base → 75cL
    (85,  7471, 0, 1.0, "Leffe petite → Leffe Blonde 33cL"),
    (84,  7472, 0, 1.0, "Leffe grande → Leffe Blonde 75cL"),
    (83,  7472, 0, 1.0, "Leffe base → Leffe Blonde 75cL"),
    # Bières africaines (produits créés dans create_missing_beers.py)
    (91,  9128, 0, 1.0, "Castel → Castel 33cL"),
    (90,  9129, 0, 1.0, "Mutzig → Mutzig 33cL"),
    (95,  9130, 0, 1.0, "Kadji → Kadji Beer 33cL"),
    (94,  9131, 0, 1.0, "Isenbeck → Isenbeck 33cL"),
    (92,  9132, 0, 1.0, "33 Export → 33 Export 33cL"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])

    stats = {"trio_updated": 0, "ingr_split": 0, "ingr_created": 0,
             "mappings_inserted": 0, "mappings_skipped": 0}
    logs = []

    with engine.begin() as conn:
        # A. Corriger qte_proteine sur variantes trio
        for var_id, new_qte, comment in _VARIANTES_TRIO:
            existing = conn.execute(text(
                "SELECT quantite_proteine FROM restaurant_variantes_plat WHERE id = :i"
            ), {"i": var_id}).scalar()
            if existing is None:
                logs.append(f"SKIP var {var_id} (non trouvée)")
                continue
            if float(existing) != new_qte:
                if args.apply:
                    conn.execute(text(
                        "UPDATE restaurant_variantes_plat "
                        "SET quantite_proteine = :q WHERE id = :i"
                    ), {"q": new_qte, "i": var_id})
                stats["trio_updated"] += 1
                logs.append(f"TRIO var {var_id} qte {existing} → {new_qte} · {comment}")

        # B. Splitter Pelfort (ingredient 93)
        existing_93 = conn.execute(text(
            "SELECT nom FROM restaurant_ingredients WHERE id = 93"
        )).scalar()
        if existing_93 == "Pelfort (bouteille)":
            if args.apply:
                conn.execute(text(
                    "UPDATE restaurant_ingredients SET nom = 'Pelforth 50cL' WHERE id = 93"
                ))
            logs.append("INGR 93 rename → 'Pelforth 50cL'")
            stats["ingr_split"] += 1

        # Créer Pelforth 75cL si absent
        existing_75 = conn.execute(text(
            "SELECT id FROM restaurant_ingredients "
            "WHERE tenant_id = :t AND nom = 'Pelforth 75cL'"
        ), {"t": _TENANT_RESTO}).scalar()
        new_ingr_id = existing_75
        if not existing_75 and args.apply:
            new_ingr_id = conn.execute(text(
                "INSERT INTO restaurant_ingredients "
                "  (tenant_id, nom, unite_stock, categorie_id, is_active, stock_actuel, stock_alerte, "
                "   cout_unitaire_cts, created_at, updated_at) "
                "SELECT tenant_id, 'Pelforth 75cL', 'bouteille', categorie_id, true, 0, 0, "
                "       300, now(), now() "
                "FROM restaurant_ingredients WHERE id = 93 "
                "RETURNING id"
            )).scalar()
            logs.append(f"INGR created 'Pelforth 75cL' id={new_ingr_id}")
            stats["ingr_created"] += 1
        elif not existing_75:
            new_ingr_id = -1  # placeholder dry-run
            logs.append("INGR create 'Pelforth 75cL' (DRY-RUN, id à allouer)")
            stats["ingr_created"] += 1

        # Pointer variante 82 GRANDE PELFORT → Pelforth 75cL
        if new_ingr_id and new_ingr_id > 0 and args.apply:
            conn.execute(text(
                "UPDATE restaurant_variantes_plat "
                "SET ingredient_proteine_id = :new_id WHERE id = 82"
            ), {"new_id": new_ingr_id})
            logs.append(f"VAR 82 GRANDE PELFORT → ingredient {new_ingr_id}")

        # C. Insérer mappings
        full_mappings = list(_MAPPINGS)
        # Ajouter Pelforth 50cL (id 93) → epicerie 7831 + Pelforth 75cL (new_id) → epi 9133
        full_mappings.append((93,  7831, 0, 1.0, "Pelforth 50cL → Pelforth Bt Brun 50cL"))
        if new_ingr_id and new_ingr_id > 0:
            full_mappings.append((new_ingr_id, 9133, 0, 1.0, "Pelforth 75cL → Pelforth Brun 75cL (créé)"))

        for ingr_id, epi_id, ordre, facteur, note in full_mappings:
            existing_map = conn.execute(text(
                "SELECT id FROM restaurant_ingredient_epicerie_mappings "
                "WHERE ingredient_id = :i AND produit_id = :p"
            ), {"i": ingr_id, "p": epi_id}).scalar()
            if existing_map:
                stats["mappings_skipped"] += 1
                continue
            if args.apply:
                conn.execute(text(
                    "INSERT INTO restaurant_ingredient_epicerie_mappings "
                    "  (tenant_id, ingredient_id, produit_id, ordre, facteur_conv, notes, "
                    "   created_at, updated_at) "
                    "VALUES (:t, :i, :p, :o, :f, :n, now(), now())"
                ), {"t": _TENANT_RESTO, "i": ingr_id, "p": epi_id,
                    "o": ordre, "f": facteur, "n": note})
            stats["mappings_inserted"] += 1
            logs.append(f"MAP ingr {ingr_id} → epi {epi_id} (facteur {facteur}) · {note}")

        if not args.apply:
            conn.rollback()

    print()
    print("=" * 60)
    print("ACTIONS :")
    for log in logs:
        print(f"  • {log}")
    print()
    print("STATS :")
    for k, v in stats.items():
        print(f"  {k:20s} {v}")
    if not args.apply:
        print("\n[DRY-RUN] --apply pour appliquer")


if __name__ == "__main__":
    main()
