"""Correctifs mapping + complétion des 11 ingrédients restants.

Corrections :
  - Gingembre (18) : mapping sirop → placeholder gingembre frais
  - Œufs (78) : mapping Bouillon Bœuf → placeholder œufs (pièce, prix 25cts)
  - Oignons (16) : facteur_conv 1 → 5 (Oignons 5kg)
  - Sel (26) : facteur_conv 1 → 0.75 (Sel 750g)

Nouveaux placeholders + mappings pour les 11 restants :
  Booster, Eau gazeuse, Eau minérale, Ginger ale, Malta, Petit CD, Top, Café,
  Huile de palme, Pommes de terre, Riz blanc.
"""
from __future__ import annotations

import argparse
import os
import sys

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text


_TENANT_RESTO = 3
_TENANT_EPICERIE = 2

# (nom, volume_ml, unite_base, unite_vente, colisage, prix_achat_cts, categorie)
_PLACEHOLDERS = [
    # Boissons
    ("Booster canette 25cL",    250,  "cL", "canette",  24, 200, "BOIS_ENERG"),
    ("Eau gazeuse 1.5L",       1500,  "L", "bouteille",  6,  80, "BOIS_EAU"),
    ("Eau minérale 1.5L",      1500,  "L", "bouteille",  6,  30, "BOIS_EAU"),
    ("Ginger ale 33cL",         330, "cL", "bouteille", 24, 100, "BOIS_SODA"),
    ("Malta 33cL",              330, "cL", "bouteille", 24, 150, "BOIS_SODA"),
    ("Petit CD 33cL",           330, "cL", "bouteille", 24, 150, "BOIS_SODA"),
    ("Top Ananas 33cL",         330, "cL", "bouteille", 24, 200, "BOIS_SODA"),
    # Cuisine
    ("Gingembre frais 1kg",    1000, "kg", "kg",          1, 2739, "FL_AROMATE"),
    ("Œufs pièce",                1, "piece", "piece",    1,   25, "FRAIS_OEUF"),
    ("Café grain 1kg",         1000, "kg", "kg",          1, 1500, "BOIS_CAFE"),
    ("Huile de palme 1L",      1000, "L", "L",            1,  341, "COND_HUILE"),
    ("Pommes de terre 1kg",    1000, "kg", "kg",          1,  150, "FL_LEGUME"),
    ("Riz blanc 25kg",        25000, "kg", "kg",          1, 5000, "EPIC_RIZ"),
]

# Mapping ingredient → placeholder
_PLACEHOLDER_MAPPINGS = [
    (122, "Booster canette 25cL",     1.0, "Booster → placeholder"),
    (120, "Eau gazeuse 1.5L",         1.0, "Eau gazeuse → placeholder"),
    (119, "Eau minérale 1.5L",        1.0, "Eau minérale → placeholder"),
    (121, "Ginger ale 33cL",          1.0, "Ginger ale → placeholder"),
    ( 96, "Malta 33cL",               1.0, "Malta → placeholder"),
    (124, "Petit CD 33cL",            1.0, "Petit CD → placeholder"),
    ( 97, "Top Ananas 33cL",          1.0, "Top → placeholder"),
    (125, "Café grain 1kg",           1.0, "Café → placeholder"),
    ( 21, "Huile de palme 1L",        1.0, "Huile palme → placeholder"),
    ( 54, "Pommes de terre 1kg",      1.0, "Pommes de terre → placeholder"),
    ( 20, "Riz blanc 25kg",          25.0, "Riz blanc → placeholder 25kg (f=25)"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
    logs = []

    with engine.begin() as conn:
        # Corrections
        # Gingembre (18) : supprimer mapping sirop
        if args.apply:
            res = conn.execute(text(
                "DELETE FROM restaurant_ingredient_epicerie_mappings "
                "WHERE ingredient_id = 18 AND produit_id = 7794"
            ))
            if res.rowcount > 0:
                logs.append("DEL mapping erroné Gingembre → Sirop (7794)")

        # Œufs (78) : supprimer mapping bouillon
        if args.apply:
            res = conn.execute(text(
                "DELETE FROM restaurant_ingredient_epicerie_mappings "
                "WHERE ingredient_id = 78 AND produit_id = 8098"
            ))
            if res.rowcount > 0:
                logs.append("DEL mapping erroné Œufs → Bouillon Bœuf (8098)")

        # Oignons (16) : facteur 1 → 5 (pack 5kg)
        if args.apply:
            res = conn.execute(text(
                "UPDATE restaurant_ingredient_epicerie_mappings "
                "SET facteur_conv = 5.0, notes = 'Oignons 5kg : 1 sac = 5 kg' "
                "WHERE ingredient_id = 16 AND produit_id = 7561 AND facteur_conv = 1.0"
            ))
            if res.rowcount > 0:
                logs.append("UPD Oignons facteur 1 → 5")

        # Sel (26) : facteur 1 → 0.75 (sachet 750g)
        if args.apply:
            res = conn.execute(text(
                "UPDATE restaurant_ingredient_epicerie_mappings "
                "SET facteur_conv = 0.75, notes = 'Sel 750g : 1 sachet = 0.75 kg' "
                "WHERE ingredient_id = 26 AND produit_id = 7731 AND facteur_conv = 1.0"
            ))
            if res.rowcount > 0:
                logs.append("UPD Sel facteur 1 → 0.75")

        # Créer placeholders
        placeholder_ids: dict[str, int] = {}
        for nom, vol, unite_base, unite_vente, col, prix_achat, categ in _PLACEHOLDERS:
            existing = conn.execute(text(
                "SELECT id FROM epicerie_produits "
                "WHERE tenant_id = :t AND LOWER(TRIM(designation_clean)) = LOWER(TRIM(:n))"
            ), {"t": _TENANT_EPICERIE, "n": nom}).scalar()
            if existing:
                placeholder_ids[nom] = existing
                continue
            if args.apply:
                new_id = conn.execute(text(
                    "INSERT INTO epicerie_produits "
                    "  (tenant_id, designation_clean, volume_unitaire_ml, unite_base, unite_vente, "
                    "   colisage, prix_achat_cts, prix_unitaire_cts, categorie, taux_tva, "
                    "   actif, created_at, updated_at) "
                    "VALUES (:t, :n, :v, :ub, :uv, :c, :pa, :pv, :cat, 550, "
                    "        true, now(), now()) "
                    "RETURNING id"
                ), {
                    "t": _TENANT_EPICERIE, "n": nom, "v": vol,
                    "ub": unite_base, "uv": unite_vente, "c": col,
                    "pa": prix_achat, "pv": int(prix_achat * 2.5), "cat": categ,
                }).scalar()
                placeholder_ids[nom] = new_id
                logs.append(f"EPI '{nom}' id={new_id} ({prix_achat/100:.2f}€)")
            else:
                placeholder_ids[nom] = -1

        # Appliquer mappings
        for ingr_id, nom, facteur, note in _PLACEHOLDER_MAPPINGS:
            epi_id = placeholder_ids.get(nom)
            if not epi_id or epi_id < 0:
                if not args.apply:
                    logs.append(f"MAP ingr {ingr_id} → '{nom}' (DRY-RUN)")
                continue
            if args.apply:
                existing_map = conn.execute(text(
                    "SELECT id FROM restaurant_ingredient_epicerie_mappings "
                    "WHERE ingredient_id = :i AND produit_id = :p"
                ), {"i": ingr_id, "p": epi_id}).scalar()
                if existing_map:
                    continue
                conn.execute(text(
                    "INSERT INTO restaurant_ingredient_epicerie_mappings "
                    "  (tenant_id, ingredient_id, produit_id, ordre, facteur_conv, notes, "
                    "   created_at, updated_at) "
                    "VALUES (:t, :i, :p, 0, :f, :n, now(), now())"
                ), {"t": _TENANT_RESTO, "i": ingr_id, "p": epi_id, "f": facteur, "n": note})
            logs.append(f"MAP ingr {ingr_id} → epi {epi_id} (f={facteur}) · {note}")

        if not args.apply:
            conn.rollback()

    print()
    for log in logs:
        print(f"  • {log}")
    if not args.apply:
        print("\n[DRY-RUN]")


if __name__ == "__main__":
    main()
