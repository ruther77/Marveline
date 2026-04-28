"""Mappings ingrédient → épicerie pour légumes, condiments, huiles, féculents, œufs.

Pour chaque ingrédient restaurant :
  - Si produit épicerie existant reconnu → mapping explicite
  - Sinon → créer placeholder 1kg avec prix d'achat du cout_unitaire ingrédient

Règle facteur_conv :
  - ingr kg + épicerie pack Nkg → facteur = N
  - ingr kg + épicerie 1kg/placeholder → facteur = 1
  - ingr pièce → facteur = 1 (1 unité épi = 1 pièce ingrédient)
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

# Placeholders épicerie à créer (ingrédients absents ou locaux/frais)
# (nom, prix_achat_cts, categorie)
_PLACEHOLDERS = [
    ("Feuilles Ndolé 1kg",       269, "FL_LEGUME"),
    ("Feuilles Eru 1kg",         616, "FL_LEGUME"),
    ("Gombo frais 1kg",         2360, "FL_LEGUME"),
    ("Njansang 1kg",            1200, "COND_EPICE"),
    ("Pistache pilée 1kg",      1000, "COND_EPICE"),
    ("Plantain frais 1kg",       163, "FL_FRUIT"),
    ("Mix légumes sautés 1kg",   500, "FL_LEGUME"),
    ("Maïs doux 1kg",            400, "CONS_LEGUME"),
    ("Tomates fraîches 1kg",     200, "FL_LEGUME"),
    ("Ail frais 1kg",            500, "FL_AROMATE"),
    ("Piment frais 1kg",        1981, "FL_AROMATE"),
    ("Poivron frais 1kg",        300, "FL_LEGUME"),
    ("Concombre frais 1kg",      150, "FL_LEGUME"),
    ("Laitue fraîche 1kg",       200, "FL_SALADE"),
    ("Champignons frais 1kg",    800, "FL_LEGUME"),
    ("Avocat frais 1kg",         350, "FL_FRUIT"),
    ("Épinards frais 1kg",       145, "FL_LEGUME"),
]

# Mapping direct ingrédient → produit épicerie existant (id fixe)
# (ingr_id, epi_id, facteur_conv, note)
_EXISTING_MAPPINGS = [
    # Épices / condiments présents en épicerie
    (27, None,    1.0, "Bouillon cube → chercher fuzzy"),
    # Placeholders seront résolus ci-dessous
]

# Ingrédient → nom de placeholder (pour resolution post-creation)
_PLACEHOLDER_MAP: list[tuple[int, str, float, str]] = [
    (10, "Feuilles Ndolé 1kg",      1.0, "Ndolé → placeholder"),
    (11, "Feuilles Eru 1kg",        1.0, "Eru → placeholder"),
    ( 9, "Gombo frais 1kg",         1.0, "Gombo → placeholder"),
    (25, "Njansang 1kg",            1.0, "Njansang → placeholder"),
    (24, "Pistache pilée 1kg",      1.0, "Pistache pilée → placeholder"),
    (13, "Plantain frais 1kg",      1.0, "Plantain → placeholder"),
    (140, "Mix légumes sautés 1kg", 1.0, "Mix légumes → placeholder"),
    (139, "Maïs doux 1kg",          1.0, "Maïs doux → placeholder"),
    (15, "Tomates fraîches 1kg",    1.0, "Tomates → placeholder"),
    (17, "Ail frais 1kg",           1.0, "Ail → placeholder"),
    (19, "Piment frais 1kg",        1.0, "Piment → placeholder"),
    (43, "Poivron frais 1kg",       1.0, "Poivron → placeholder"),
    (42, "Concombre frais 1kg",     1.0, "Concombre → placeholder"),
    (41, "Laitue fraîche 1kg",      1.0, "Laitue → placeholder"),
    (14, "Champignons frais 1kg",   1.0, "Champignons → placeholder"),
    (40, "Avocat frais 1kg",        1.0, "Avocat → placeholder"),
    (12, "Épinards frais 1kg",      1.0, "Épinards → placeholder"),
]


def find_epicerie(conn, query: str, vol_range: tuple[int, int] = None) -> int | None:
    """Cherche un produit épicerie par fuzzy nom (match strict puis contient)."""
    rows = conn.execute(text(
        "SELECT id, designation_clean, colisage, volume_unitaire_ml FROM epicerie_produits "
        "WHERE tenant_id = :t AND actif AND designation_clean ILIKE :q "
        "ORDER BY id LIMIT 5"
    ), {"t": _TENANT_EPICERIE, "q": f"%{query}%"}).fetchall()
    if vol_range and rows:
        lo, hi = vol_range
        for r in rows:
            if r[3] and lo <= r[3] <= hi:
                return r[0]
    return rows[0][0] if rows else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
    logs = []

    with engine.begin() as conn:
        # 1. Créer placeholders
        placeholder_ids: dict[str, int] = {}
        for nom, prix_achat, categorie in _PLACEHOLDERS:
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
                logs.append(f"EPI create '{nom}' (DRY-RUN)")

        # 2. Résolution ingrédients avec produits épicerie existants
        explicit_mappings = []

        # Oignons (ingr 16) → chercher épicerie
        oignons = find_epicerie(conn, "oignon", vol_range=None)
        if oignons:
            explicit_mappings.append((16, oignons, 1.0, "Oignons → épicerie trouvé"))

        # Gingembre (ingr 18) → chercher
        gingembre = find_epicerie(conn, "gingembre")
        if gingembre:
            explicit_mappings.append((18, gingembre, 1.0, "Gingembre → épicerie trouvé"))
        else:
            # Créer placeholder
            if args.apply:
                gingembre_id = conn.execute(text(
                    "INSERT INTO epicerie_produits "
                    "  (tenant_id, designation_clean, volume_unitaire_ml, unite_base, unite_vente, "
                    "   colisage, prix_achat_cts, prix_unitaire_cts, categorie, taux_tva, actif, "
                    "   created_at, updated_at) "
                    "VALUES (:t, 'Gingembre frais 1kg', 1000, 'kg', 'kg', 1, 2739, 6847, "
                    "        'FL_AROMATE', 550, true, now(), now()) "
                    "RETURNING id"
                ), {"t": _TENANT_EPICERIE}).scalar()
                logs.append(f"EPI created 'Gingembre frais 1kg' id={gingembre_id}")
                explicit_mappings.append((18, gingembre_id, 1.0, "Gingembre → placeholder"))

        # Riz blanc (ingr 20) → chercher "Riz" en épicerie
        riz = find_epicerie(conn, "riz blanc")
        if riz:
            explicit_mappings.append((20, riz, 1.0, "Riz blanc → épicerie"))

        # Haricots blancs (ingr 51)
        haricots = find_epicerie(conn, "haricots blancs")
        if haricots:
            explicit_mappings.append((51, haricots, 1.0, "Haricots blancs → épicerie"))

        # Huile de palme (ingr 21) - unité L
        huile_palme = find_epicerie(conn, "huile de palme")
        if huile_palme:
            explicit_mappings.append((21, huile_palme, 1.0, "Huile palme → épicerie"))

        # Huile végétale (ingr 22) - unité L
        huile_veg = find_epicerie(conn, "huile vegetale")
        if not huile_veg:
            huile_veg = find_epicerie(conn, "huile friture")
        if huile_veg:
            explicit_mappings.append((22, huile_veg, 1.0, "Huile végétale → épicerie"))

        # Pâte d'arachide (ingr 23)
        arachide = find_epicerie(conn, "arachide")
        if arachide:
            explicit_mappings.append((23, arachide, 1.0, "Pâte arachide → épicerie"))

        # Sel (ingr 26)
        sel = find_epicerie(conn, "sel fin")
        if not sel:
            sel = find_epicerie(conn, "sel ")
        if sel:
            explicit_mappings.append((26, sel, 1.0, "Sel → épicerie"))

        # Bouillon cube (ingr 27)
        bouillon = find_epicerie(conn, "bouillon")
        if bouillon:
            explicit_mappings.append((27, bouillon, 1.0, "Bouillon cube → épicerie"))

        # Farine blé (ingr 55)
        farine = find_epicerie(conn, "farine de ble")
        if not farine:
            farine = find_epicerie(conn, "farine")
        if farine:
            explicit_mappings.append((55, farine, 1.0, "Farine → épicerie"))

        # Pommes de terre (ingr 54)
        pdt = find_epicerie(conn, "pomme de terre")
        if pdt:
            explicit_mappings.append((54, pdt, 1.0, "Pommes de terre → épicerie"))

        # Baguette (ingr 58)
        baguette = find_epicerie(conn, "baguette")
        if baguette:
            explicit_mappings.append((58, baguette, 1.0, "Baguette → épicerie"))

        # Œufs (ingr 78) pièce
        oeufs = find_epicerie(conn, "oeuf")
        if oeufs:
            explicit_mappings.append((78, oeufs, 1.0, "Œufs → épicerie (1 pièce = 1 pièce)"))

        # 3. Appliquer tous les mappings
        all_mappings = []
        for ingr_id, nom, facteur, note in _PLACEHOLDER_MAP:
            epi_id = placeholder_ids.get(nom)
            if epi_id and epi_id > 0:
                all_mappings.append((ingr_id, epi_id, facteur, note))
        all_mappings.extend(explicit_mappings)

        for ingr_id, epi_id, facteur, note in all_mappings:
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
    print("=" * 60)
    for log in logs:
        print(f"  • {log}")
    if not args.apply:
        print("\n[DRY-RUN] --apply")


if __name__ == "__main__":
    main()
