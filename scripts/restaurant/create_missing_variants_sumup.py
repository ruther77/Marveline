"""Crée les 6 variantes manquantes détectées par l'audit SumUp + leurs
ingrédients + placeholders épicerie + mappings.

Variantes à créer :
  - Prunes 5€ (2 safous braisés, plat)
  - Prunes 10€ (4 safous braisés, plat)
  - BEAUFORT (bière camerounaise grand format 75cL)
  - Ragoût viande (plat en sauce avec bœuf à mijoter)
  - Méchoui chèvre (plat avec viande de chèvre)
  - Formule champagne (3 bouteilles du champagne le moins cher = Nicola)
  - BROCHETTES DE GESIER (brochette 7-8 gésiers ≈ 200g)

Ingrédients + placeholders créés :
  - Safou (pièce, 0.50€/pièce)
  - Bière Beaufort (bouteille 75cL, 2€/bouteille achat)
  - Viande chèvre (kg, 12€/kg)
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

# IDs connus
_TYPE_PREP_GRILLADE = 27    # créé précédemment
_TYPE_PREP_SAUCE_TOMATE = 10
_INGR_BOEUF_MIJOTER = 5
_INGR_GESIER = 36
_INGR_NICOLA = 112  # Nicola (75cl) = champagne le moins cher


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
    logs = []

    with engine.begin() as conn:
        # Récupérer les IDs de catégories resto (Protéine/Viandes/etc.)
        categ_ids = dict(conn.execute(text(
            "SELECT nom, id FROM restaurant_categories_ingredient"
        )).fetchall())

        # 1. Créer ingrédients + placeholders épicerie
        def create_ingredient(nom: str, unite: str, cout_cts: int, categ_nom: str) -> int | None:
            existing = conn.execute(text(
                "SELECT id FROM restaurant_ingredients "
                "WHERE tenant_id = :t AND nom = :n"
            ), {"t": _TENANT_RESTO, "n": nom}).scalar()
            if existing:
                logs.append(f"INGR '{nom}' existe (id {existing})")
                return existing
            if not args.apply:
                logs.append(f"INGR create '{nom}' (DRY-RUN)")
                return None
            categ_id = categ_ids.get(categ_nom)
            new_id = conn.execute(text(
                "INSERT INTO restaurant_ingredients "
                "  (tenant_id, nom, unite_stock, categorie_id, cout_unitaire_cts, "
                "   is_active, stock_actuel, stock_alerte, created_at, updated_at) "
                "VALUES (:t, :n, :u, :c, :cost, true, 0, 0, now(), now()) "
                "RETURNING id"
            ), {"t": _TENANT_RESTO, "n": nom, "u": unite, "c": categ_id, "cost": cout_cts}).scalar()
            logs.append(f"INGR '{nom}' id={new_id}")
            return new_id

        def create_epi_placeholder(nom: str, vol_ml: int, unite: str, col: int,
                                    prix_achat: int, categ: str) -> int | None:
            existing = conn.execute(text(
                "SELECT id FROM epicerie_produits "
                "WHERE tenant_id = :t AND LOWER(TRIM(designation_clean)) = LOWER(TRIM(:n))"
            ), {"t": _TENANT_EPICERIE, "n": nom}).scalar()
            if existing:
                logs.append(f"EPI '{nom}' existe (id {existing})")
                return existing
            if not args.apply:
                logs.append(f"EPI create '{nom}' (DRY-RUN)")
                return None
            unite_vente = "bouteille" if unite == "cL" else "kg" if unite == "kg" else "piece"
            new_id = conn.execute(text(
                "INSERT INTO epicerie_produits "
                "  (tenant_id, designation_clean, volume_unitaire_ml, unite_base, unite_vente, "
                "   colisage, prix_achat_cts, prix_unitaire_cts, categorie, taux_tva, "
                "   actif, created_at, updated_at) "
                "VALUES (:t, :n, :v, :u, :uv, :c, :pa, :pv, :cat, 550, "
                "        true, now(), now()) RETURNING id"
            ), {
                "t": _TENANT_EPICERIE, "n": nom, "v": vol_ml, "u": unite, "uv": unite_vente,
                "c": col, "pa": prix_achat, "pv": int(prix_achat * 2.5), "cat": categ,
            }).scalar()
            logs.append(f"EPI '{nom}' id={new_id}")
            return new_id

        def create_mapping(ingr_id: int | None, epi_id: int | None, facteur: float, note: str):
            if not args.apply or not ingr_id or not epi_id:
                if ingr_id and epi_id:
                    logs.append(f"MAP {ingr_id}→{epi_id} (f={facteur}) {note}")
                return
            exists = conn.execute(text(
                "SELECT 1 FROM restaurant_ingredient_epicerie_mappings "
                "WHERE ingredient_id = :i AND produit_id = :p LIMIT 1"
            ), {"i": ingr_id, "p": epi_id}).scalar()
            if not exists:
                conn.execute(text(
                    "INSERT INTO restaurant_ingredient_epicerie_mappings "
                    "  (tenant_id, ingredient_id, produit_id, ordre, facteur_conv, notes, "
                    "   created_at, updated_at) "
                    "VALUES (:t, :i, :p, 0, :f, :n, now(), now())"
                ), {"t": _TENANT_RESTO, "i": ingr_id, "p": epi_id, "f": facteur, "n": note})
                logs.append(f"MAP {ingr_id}→{epi_id} · {note}")

        # Safou
        ingr_safou = create_ingredient("Safou (prune)", "pièce", 50, "Fruits")
        epi_safou = create_epi_placeholder("Safou frais pièce", 100, "g", 1, 50, "FL_FRUIT")
        create_mapping(ingr_safou, epi_safou, 1.0, "Safou pièce → placeholder")

        # Beaufort bière grand format 75cL
        ingr_beaufort = create_ingredient("Beaufort (bouteille)", "bouteille", 200, "Boissons stock")
        epi_beaufort = create_epi_placeholder("Beaufort 75cL", 750, "cL", 12, 200, "ALC_BIERE")
        create_mapping(ingr_beaufort, epi_beaufort, 1.0, "Beaufort grande → placeholder 75cL")

        # Viande chèvre
        ingr_chevre = create_ingredient("Viande chèvre", "kg", 1200, "Viandes")
        epi_chevre = create_epi_placeholder("Viande chèvre 1kg", 1000, "kg", 1, 1200, "FRAIS_AGNEAU")
        create_mapping(ingr_chevre, epi_chevre, 1.0, "Chèvre → placeholder 1kg")

        # 2. Créer les variantes plat
        variants_to_create = [
            # (nom, type, ingredient_id, quantite, prix_vente_cts, type_prep_id, description)
            ("Prunes 5€",  "plat",    ingr_safou, 2.0,  500, _TYPE_PREP_GRILLADE, "Safou braisé × 2"),
            ("Prunes 10€", "plat",    ingr_safou, 4.0, 1000, _TYPE_PREP_GRILLADE, "Safou braisé × 4"),
            ("BEAUFORT",   "boisson", ingr_beaufort, 1.0, 1000, None, "Bière Beaufort 75cL grande"),
            ("Ragoût viande", "plat", _INGR_BOEUF_MIJOTER, 0.25, 1500, _TYPE_PREP_SAUCE_TOMATE, "Ragoût bœuf mijoté"),
            ("Méchoui chèvre", "plat", ingr_chevre, 0.30, 1500, _TYPE_PREP_GRILLADE, "Méchoui chèvre grillé"),
            ("Formule champagne", "formule", _INGR_NICOLA, 3.0, 12000, None, "3 bouteilles Nicola"),
            ("BROCHETTES DE GESIER", "plat", _INGR_GESIER, 0.2, 1000, _TYPE_PREP_GRILLADE, "7-8 gésiers brochette"),
        ]

        for nom, vtype, ingr_id, qte, prix, tp_id, desc in variants_to_create:
            existing = conn.execute(text(
                "SELECT id FROM restaurant_variantes_plat "
                "WHERE tenant_id = :t AND nom = :n"
            ), {"t": _TENANT_RESTO, "n": nom}).scalar()
            if existing:
                logs.append(f"VAR '{nom}' existe (id {existing})")
                continue
            if not args.apply or (ingr_id is None):
                logs.append(f"VAR create '{nom}' (DRY-RUN)")
                continue
            new_id = conn.execute(text(
                "INSERT INTO restaurant_variantes_plat "
                "  (tenant_id, nom, type, prix_vente_cts, taux_tva, description, "
                "   type_preparation_id, ingredient_proteine_id, quantite_proteine, "
                "   is_active, created_at, updated_at) "
                "VALUES (:t, :n, :ty, :pv, 550, :d, :tp, :ip, :qp, true, now(), now()) "
                "RETURNING id"
            ), {
                "t": _TENANT_RESTO, "n": nom, "ty": vtype, "pv": prix, "d": desc,
                "tp": tp_id, "ip": ingr_id, "qp": qte,
            }).scalar()
            logs.append(f"VAR '{nom}' id={new_id} type={vtype} prix={prix/100:.2f}€")

        if not args.apply:
            conn.rollback()

    print()
    for log in logs:
        print(f"  • {log}")
    if not args.apply:
        print("\n[DRY-RUN]")


if __name__ == "__main__":
    main()
