"""Finalise le restaurant : désactive plats à prix aberrants, crée type_preparation
Grillade/Bouillon/DG/Oeuf + rattache les variantes qui n'en avaient pas.

Actions :
  1. Désactiver variantes 2 (Vindaye Thon), 3 (Rougail Saucisse), 4 (Carry Crevettes)
  2. Créer type_preparation "Grillade" + recette (huile + sel + salade)
     Rattacher : ailes/cuisses/cotelette/brochettes/tripes/rognon/gesier/poissons
  3. Créer type_preparation "Bouillon" + recette
     Rattacher : Bouillon poisson (58), Bouillon queue bœuf (59)
  4. Créer type_preparation "Poulet DG" + recette
     Rattacher : DG (50)
  5. Créer type_preparation "Oeuf simple" + recette
     Rattacher : Oeuf (62)
  6. Supplements 3/5/10€ : restent sans type_prep (ce sont des add-ons)
"""
from __future__ import annotations

import argparse
import os
import sys

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text


_TENANT_RESTO = 3

# Variantes à désactiver (prix aberrants)
_VAR_DEACTIVATE = [2, 3, 4]

# Nouveaux type_preparation à créer
# (nom, [(ingredient_id, quantite_par_batch, notes)])
_NEW_TYPES: list[tuple[str, list[tuple[int, float, str]]]] = [
    ("Grillade", [
        (22, 0.200, "Huile végétale cuisson"),
        (26, 0.050, "Sel"),
        (41, 0.300, "Laitue (salade)"),
        (15, 0.200, "Tomates (salade)"),
        (42, 0.200, "Concombre (salade)"),
        (16, 0.100, "Oignons (salade)"),
    ]),
    ("Bouillon", [
        (27, 10.000, "Bouillon cube (pièces)"),
        (16, 0.500, "Oignons"),
        (15, 0.300, "Tomates"),
        (22, 0.200, "Huile végétale"),
        (17, 0.100, "Ail"),
        (19, 0.050, "Piment"),
    ]),
    ("Poulet DG", [
        (13, 2.000, "Plantain frit"),
        (43, 0.300, "Poivrons"),
        (16, 0.300, "Oignons"),
        (15, 0.200, "Tomates"),
        (17, 0.100, "Ail"),
        (22, 0.200, "Huile végétale"),
        (19, 0.050, "Piment"),
    ]),
    ("Oeuf simple", [
        (22, 0.050, "Huile végétale"),
        (26, 0.005, "Sel"),
    ]),
]

# Variantes à rattacher (var_id → nom type_prep)
_VAR_ATTACH: dict[int, str] = {
    # Grillade (volaille)
    37: "Grillade", 38: "Grillade", 39: "Grillade", 40: "Grillade",
    # Grillade (porc)
    41: "Grillade", 46: "Grillade", 47: "Grillade",
    # Grillade (brochettes)
    42: "Grillade", 43: "Grillade", 44: "Grillade",
    # Grillade (abats)
    45: "Grillade", 48: "Grillade", 49: "Grillade",
    # Grillade (poissons)
    51: "Grillade", 52: "Grillade", 53: "Grillade", 54: "Grillade",
    55: "Grillade", 56: "Grillade", 57: "Grillade",
    # Bouillon
    58: "Bouillon", 59: "Bouillon",
    # DG (plat camerounais)
    50: "Poulet DG",
    # Oeuf simple
    62: "Oeuf simple",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
    logs = []

    with engine.begin() as conn:
        # 1. Désactiver 3 variantes prix aberrants
        for var_id in _VAR_DEACTIVATE:
            row = conn.execute(text(
                "SELECT nom, is_active, prix_vente_cts FROM restaurant_variantes_plat WHERE id = :i"
            ), {"i": var_id}).first()
            if not row:
                continue
            nom, is_active, prix = row
            if is_active:
                if args.apply:
                    conn.execute(text(
                        "UPDATE restaurant_variantes_plat SET is_active = false WHERE id = :i"
                    ), {"i": var_id})
                logs.append(f"DEACTIVATE var {var_id} {nom} (prix {prix/100:.2f}€ aberrant)")

        # 2. Créer les nouveaux type_preparation + recettes
        created_tp_ids: dict[str, int] = {}
        for nom, recette in _NEW_TYPES:
            existing = conn.execute(text(
                "SELECT id FROM restaurant_types_preparation "
                "WHERE tenant_id = :t AND nom = :n"
            ), {"t": _TENANT_RESTO, "n": nom}).scalar()
            if existing:
                created_tp_ids[nom] = existing
                logs.append(f"TYPE_PREP '{nom}' existe (id {existing}) — skip")
                continue
            if args.apply:
                new_id = conn.execute(text(
                    "INSERT INTO restaurant_types_preparation "
                    "  (tenant_id, nom, portions_par_batch, created_at, updated_at) "
                    "VALUES (:t, :n, 10, now(), now()) RETURNING id"
                ), {"t": _TENANT_RESTO, "n": nom}).scalar()
                created_tp_ids[nom] = new_id
                logs.append(f"TYPE_PREP '{nom}' créé (id {new_id})")
                for ingr_id, qte, note in recette:
                    conn.execute(text(
                        "INSERT INTO restaurant_recettes_type_preparation "
                        "  (tenant_id, type_preparation_id, ingredient_id, quantite_par_batch, "
                        "   notes, created_at, updated_at) "
                        "VALUES (:t, :tp, :i, :q, :n, now(), now())"
                    ), {"t": _TENANT_RESTO, "tp": new_id, "i": ingr_id, "q": qte, "n": note})
                    logs.append(f"  + ingr {ingr_id} × {qte}")

        # 3. Rattacher les variantes
        for var_id, tp_nom in _VAR_ATTACH.items():
            tp_id = created_tp_ids.get(tp_nom)
            if not tp_id:
                if args.apply:
                    logs.append(f"SKIP var {var_id}: type_prep '{tp_nom}' absent")
                continue
            var = conn.execute(text(
                "SELECT nom, type_preparation_id FROM restaurant_variantes_plat WHERE id = :i"
            ), {"i": var_id}).first()
            if not var:
                continue
            nom, current_tp = var
            if current_tp is None:
                if args.apply:
                    conn.execute(text(
                        "UPDATE restaurant_variantes_plat "
                        "SET type_preparation_id = :tp WHERE id = :i"
                    ), {"tp": tp_id, "i": var_id})
                logs.append(f"ATTACH var {var_id} {nom} → type_prep '{tp_nom}'")

        if not args.apply:
            conn.rollback()

    print()
    for log in logs:
        print(f"  • {log}")
    if not args.apply:
        print("\n[DRY-RUN]")


if __name__ == "__main__":
    main()
