"""Restructure les ingrédients protéines + crée placeholders épicerie + mappings.

Actions (idempotent) :
  A. Désactiver variante 1 "Carry Poulet" (user demande suppression)
  B. Désactiver ingrédient 1 "Poulet" générique
  C. Renommer ingrédient 5 "Bœuf" → "Bœuf à mijoter"
  D. Créer produits épicerie placeholder (1kg, prix achat = cout_unitaire ingrédient)
     pour tous les ingrédients protéines achetés hors ETL (frais/boucher/marché local)
  E. Insérer mappings ingredient → produit épicerie avec facteur_conv adapté

Règles prix placeholders (€/kg) :
  Bœuf à mijoter 10 · Porc filet 8.50 · Kilichi 15 · Poulet entier 6.50
  Tripes 6 · Rognon 7 · Gésier 5.50 · Capitaine 12 · Sole 18
  Poisson fumé 12 · Écrevisses séchées 25 · Crevettes 12 · Thon 10

Usage :
    docker exec -w /app futurproj_api python3 \\
        scripts/restaurant/restructure_proteins_and_map.py [--apply]
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

# (nom, prix_achat_cts) — placeholders épicerie à créer (unité kg, colisage 1)
_PLACEHOLDERS = [
    ("Bœuf à mijoter 1kg",    1000, "FRAIS_BOEUF"),
    ("Porc filet 1kg",         850, "FRAIS_PORC"),
    ("Kilichi bœuf séché 1kg", 1500, "FRAIS_BOEUF"),
    ("Poulet entier 1kg",      650, "FRAIS_VOLAILLE"),
    ("Tripes 1kg",             600, "FRAIS_BOEUF"),
    ("Rognon 1kg",             700, "FRAIS_BOEUF"),
    ("Gésier 1kg",             550, "FRAIS_VOLAILLE"),
    ("Capitaine frais 1kg",   1200, "FRAIS_POISSON"),
    ("Sole fraîche 1kg",      1800, "FRAIS_POISSON"),
    ("Poisson fumé 1kg",      1200, "FRAIS_POISSON"),
    ("Écrevisses séchées 1kg",2500, "FRAIS_CRUST"),
    ("Crevettes fraîches 1kg",1200, "FRAIS_CRUST"),
    ("Thon frais 1kg",        1000, "FRAIS_POISSON"),
]

# Après création : mapping ingredient_id → nom placeholder (ou epi_id direct si existant)
# (ingr_id, epi_id_or_placeholder_name, facteur_conv, note)
_MAPPING_PLAN = [
    # Génériques → placeholders
    ( 5, "Bœuf à mijoter 1kg",     1.0, "Bœuf à mijoter → placeholder 1kg"),
    (28, "Porc filet 1kg",         1.0, "Porc filet → placeholder 1kg"),
    (29, "Bœuf à mijoter 1kg",     1.0, "Bœuf brochettes → même viande à mijoter"),
    (30, "Kilichi bœuf séché 1kg", 1.0, "Bœuf séché → Kilichi placeholder"),
    (31, "Poulet entier 1kg",      1.0, "Poulet entier → placeholder"),
    (34, "Tripes 1kg",             1.0, "Tripes → placeholder"),
    (35, "Rognon 1kg",             1.0, "Rognon → placeholder"),
    (36, "Gésier 1kg",             1.0, "Gésier → placeholder"),
    (37, "Capitaine frais 1kg",    1.0, "Capitaine → placeholder"),
    (39, "Sole fraîche 1kg",       1.0, "Sole → placeholder"),
    ( 7, "Poisson fumé 1kg",       1.0, "Poisson fumé → placeholder"),
    ( 8, "Écrevisses séchées 1kg", 1.0, "Écrevisses → placeholder"),
    ( 3, "Crevettes fraîches 1kg", 1.0, "Crevettes → placeholder"),
    ( 2, "Thon frais 1kg",         1.0, "Thon → placeholder"),
    # Mappings vers produits épicerie existants (packs 10kg / 4kg / 20kg)
    (32, 7996, 10.0, "Cuisses poulet → Van o Bel 10kg (1 colis = 10 kg)"),
    (33, 8003, 10.0, "Ailes poulet → Van o Bel 10kg (1 colis = 10 kg)"),
    (38, 8005,  4.0, "Tilapia → Tilapia Ve 800g+ 4kg (1 colis = 4 kg)"),
    ( 6, 8049, 20.0, "Maquereau → Maquereaux 20kg (1 colis = 20 kg)"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
    logs = []

    with engine.begin() as conn:
        # A. Désactiver Carry Poulet (variante 1)
        current = conn.execute(text(
            "SELECT is_active FROM restaurant_variantes_plat WHERE id = 1"
        )).scalar()
        if current is True:
            if args.apply:
                conn.execute(text(
                    "UPDATE restaurant_variantes_plat SET is_active = false WHERE id = 1"
                ))
            logs.append("VAR 1 Carry Poulet désactivée")

        # B. Désactiver ingredient 1 "Poulet" générique
        current = conn.execute(text(
            "SELECT is_active FROM restaurant_ingredients WHERE id = 1"
        )).scalar()
        if current is True:
            if args.apply:
                conn.execute(text(
                    "UPDATE restaurant_ingredients SET is_active = false WHERE id = 1"
                ))
            logs.append("INGR 1 Poulet (générique) désactivé")

        # C. Rename ingredient 5 "Bœuf" → "Bœuf à mijoter"
        current = conn.execute(text(
            "SELECT nom FROM restaurant_ingredients WHERE id = 5"
        )).scalar()
        if current == "Bœuf":
            if args.apply:
                conn.execute(text(
                    "UPDATE restaurant_ingredients SET nom = 'Bœuf à mijoter' WHERE id = 5"
                ))
            logs.append("INGR 5 Bœuf → 'Bœuf à mijoter'")

        # D. Créer placeholders épicerie
        placeholder_ids: dict[str, int] = {}
        for nom, prix_achat, categorie in _PLACEHOLDERS:
            existing = conn.execute(text(
                "SELECT id FROM epicerie_produits "
                "WHERE tenant_id = :t AND LOWER(TRIM(designation_clean)) = LOWER(TRIM(:n))"
            ), {"t": _TENANT_EPICERIE, "n": nom}).scalar()
            if existing:
                placeholder_ids[nom] = existing
                logs.append(f"EPI placeholder '{nom}' existe déjà (id {existing})")
                continue
            if args.apply:
                new_id = conn.execute(text(
                    "INSERT INTO epicerie_produits "
                    "  (tenant_id, designation_clean, volume_unitaire_ml, unite_base, unite_vente, "
                    "   colisage, prix_achat_cts, prix_unitaire_cts, categorie, taux_tva, "
                    "   actif, created_at, updated_at) "
                    "VALUES (:t, :n, 1000, 'kg', 'kg', 1, :pa, :pv, :c, 550, "
                    "        true, now(), now()) "
                    "RETURNING id"
                ), {
                    "t": _TENANT_EPICERIE, "n": nom,
                    "pa": prix_achat, "pv": int(prix_achat * 2.5), "c": categorie,
                }).scalar()
                placeholder_ids[nom] = new_id
                logs.append(f"EPI created '{nom}' id={new_id} ({prix_achat/100:.2f}€/kg)")
            else:
                placeholder_ids[nom] = -1
                logs.append(f"EPI create '{nom}' (DRY-RUN, {prix_achat/100:.2f}€/kg)")

        # E. Insérer mappings
        for ingr_id, target, facteur, note in _MAPPING_PLAN:
            if isinstance(target, str):
                epi_id = placeholder_ids.get(target)
                if not epi_id or epi_id < 0:
                    if args.apply:
                        logs.append(f"SKIP map ingr {ingr_id}: placeholder '{target}' introuvable")
                        continue
                    epi_id = -1  # DRY-RUN, on simule
            else:
                epi_id = target
                # Vérifier qu'il existe
                check = conn.execute(text(
                    "SELECT 1 FROM epicerie_produits WHERE id = :i"
                ), {"i": epi_id}).scalar()
                if not check:
                    logs.append(f"SKIP map ingr {ingr_id}: epi {epi_id} inexistant")
                    continue

            if args.apply:
                existing_map = conn.execute(text(
                    "SELECT id FROM restaurant_ingredient_epicerie_mappings "
                    "WHERE ingredient_id = :i AND produit_id = :p"
                ), {"i": ingr_id, "p": epi_id}).scalar()
                if existing_map:
                    logs.append(f"MAP ingr {ingr_id} → epi {epi_id} déjà existant")
                    continue
                conn.execute(text(
                    "INSERT INTO restaurant_ingredient_epicerie_mappings "
                    "  (tenant_id, ingredient_id, produit_id, ordre, facteur_conv, notes, "
                    "   created_at, updated_at) "
                    "VALUES (:t, :i, :p, 0, :f, :n, now(), now())"
                ), {"t": _TENANT_RESTO, "i": ingr_id, "p": epi_id, "f": facteur, "n": note})
            logs.append(f"MAP ingr {ingr_id} → epi {epi_id} (facteur {facteur}) · {note}")

        if not args.apply:
            conn.rollback()

    print()
    print("=" * 60)
    for log in logs:
        print(f"  • {log}")
    if not args.apply:
        print("\n[DRY-RUN] --apply pour appliquer")


if __name__ == "__main__":
    main()
