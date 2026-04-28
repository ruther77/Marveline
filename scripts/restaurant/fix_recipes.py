"""Corrige les 4 recettes incohérentes + ajoute mappings épicerie pour les
nouveaux ingrédients référencés (Haricots cornilles, Taro, Curry,
Concentré tomate, Ail en poudre).

Recettes corrigées (par marmite, pour ~10 portions) :
  Koki       : 2.0 kg haricots cornilles + 0.3 L huile palme + 0.2 kg oignons
               + 0.1 kg piment + 0.01 kg sel (retire 0.8 arachide erronée)
  Taro       : 3.0 kg Taro tubercule + 0.5 L huile palme + 0.3 kg oignons
               + 0.1 kg njansang + 2 pcs bouillon cube (ajoute le taro qui manquait)
  Sauce      : 1.0 kg tomates + 0.3 kg oignons + 0.2 kg concentré tomate + 0.2 L
  tomate       huile végétale + 0.1 kg ail + 0.1 kg piment (ratio inversé corrigé)
  Sauce      : 0.4 kg pâte arachide + 0.2 L huile palme + 0.15 kg oignons
  jaune      + 0.05 kg curry + 0.05 kg ail en poudre (ajoute épices jaunes)
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

# Nouvelles recettes (type_prep_id → liste (ingredient_id, quantite))
_RECIPES = {
    # Koki (id 12)
    12: [
        (482, 2.000, "Haricots cornilles (niébé) base koki"),
        ( 21, 0.300, "Huile de palme"),
        ( 16, 0.200, "Oignons"),
        ( 19, 0.100, "Piment"),
        ( 26, 0.010, "Sel"),
    ],
    # Taro (id 14)
    14: [
        ( 48, 3.000, "Taro tubercule base plat"),
        ( 21, 0.500, "Huile de palme"),
        ( 16, 0.300, "Oignons"),
        ( 25, 0.100, "Njansang"),
        ( 27, 2.000, "Bouillon cube (pièces)"),
    ],
    # Sauce tomate (id 10)
    10: [
        ( 15, 1.000, "Tomates fraîches (base)"),
        ( 16, 0.300, "Oignons"),
        ( 64, 0.200, "Concentré de tomate"),
        ( 22, 0.200, "Huile végétale"),
        ( 17, 0.100, "Ail frais"),
        ( 19, 0.100, "Piment"),
    ],
    # Sauce jaune (id 9)
    9: [
        ( 23, 0.400, "Pâte d'arachide"),
        ( 21, 0.200, "Huile de palme"),
        ( 16, 0.150, "Oignons"),
        ( 62, 0.050, "Curry (épice jaune)"),
        ( 69, 0.050, "Ail en poudre"),
    ],
}

# Placeholders épicerie à créer pour les ingrédients ajoutés
# (ingredient_id_resto, nom_placeholder, prix_achat_cts, unite_base, categorie)
_NEW_PLACEHOLDERS = [
    (482, "Haricots cornilles 1kg", 250, "kg", "EPIC_LEGUM_SEC"),
    ( 48, "Taro frais 1kg",          250, "kg", "FL_LEGUME"),
    ( 64, "Concentré de tomate 400g", 300, "g", "COND_SAUCE"),
    ( 69, "Ail en poudre 100g",      900, "g", "COND_EPICE"),
    ( 62, "Curry 100g",              800, "g", "COND_EPICE"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
    logs = []

    with engine.begin() as conn:
        # 1. Remplacer toutes les recettes corrigées
        for tp_id, items in _RECIPES.items():
            tp_nom = conn.execute(text(
                "SELECT nom FROM restaurant_types_preparation WHERE id = :i"
            ), {"i": tp_id}).scalar()
            if args.apply:
                conn.execute(text(
                    "DELETE FROM restaurant_recettes_type_preparation "
                    "WHERE type_preparation_id = :i"
                ), {"i": tp_id})
                for ingr_id, qte, note in items:
                    conn.execute(text(
                        "INSERT INTO restaurant_recettes_type_preparation "
                        "  (tenant_id, type_preparation_id, ingredient_id, quantite_par_batch, "
                        "   notes, created_at, updated_at) "
                        "VALUES (:t, :tp, :i, :q, :n, now(), now())"
                    ), {"t": _TENANT_RESTO, "tp": tp_id, "i": ingr_id, "q": qte, "n": note})
            logs.append(f"RECIPE '{tp_nom}' ({tp_id}) : {len(items)} ingrédients")
            for ingr_id, qte, note in items:
                logs.append(f"  + ingr {ingr_id} × {qte}")

        # 2. Créer placeholders pour les nouveaux ingrédients utilisés
        for ingr_id, nom, prix_achat, unite, categ in _NEW_PLACEHOLDERS:
            existing = conn.execute(text(
                "SELECT id FROM epicerie_produits "
                "WHERE tenant_id = :t AND LOWER(TRIM(designation_clean)) = LOWER(TRIM(:n))"
            ), {"t": _TENANT_EPICERIE, "n": nom}).scalar()
            if not existing:
                if args.apply:
                    existing = conn.execute(text(
                        "INSERT INTO epicerie_produits "
                        "  (tenant_id, designation_clean, volume_unitaire_ml, unite_base, unite_vente, "
                        "   colisage, prix_achat_cts, prix_unitaire_cts, categorie, taux_tva, "
                        "   actif, created_at, updated_at) "
                        "VALUES (:t, :n, 1000, :u, :u, 1, :pa, :pv, :c, 550, "
                        "        true, now(), now()) RETURNING id"
                    ), {"t": _TENANT_EPICERIE, "n": nom, "u": unite,
                        "pa": prix_achat, "pv": int(prix_achat * 2.5), "c": categ}).scalar()
                    logs.append(f"EPI '{nom}' id={existing}")
            # 3. Mapping ingrédient → placeholder (si pas déjà mappé)
            if args.apply and existing:
                has_map = conn.execute(text(
                    "SELECT 1 FROM restaurant_ingredient_epicerie_mappings "
                    "WHERE ingredient_id = :i LIMIT 1"
                ), {"i": ingr_id}).scalar()
                if not has_map:
                    conn.execute(text(
                        "INSERT INTO restaurant_ingredient_epicerie_mappings "
                        "  (tenant_id, ingredient_id, produit_id, ordre, facteur_conv, notes, "
                        "   created_at, updated_at) "
                        "VALUES (:t, :i, :p, 0, 1.0, :n, now(), now())"
                    ), {"t": _TENANT_RESTO, "i": ingr_id, "p": existing,
                        "n": f"{nom} → placeholder"})
                    logs.append(f"MAP ingr {ingr_id} → epi {existing}")

        if not args.apply:
            conn.rollback()

    print()
    for log in logs:
        print(f"  • {log}")
    if not args.apply:
        print("\n[DRY-RUN]")


if __name__ == "__main__":
    main()
