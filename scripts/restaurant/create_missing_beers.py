"""Crée les produits épicerie manquants pour le bar restaurant + normalise les
volumes existants incomplets (ex: Guiness Irlande sans volume).

Actions :
  1. UPDATE `Guiness Irlande` (id 8096) → volume_unitaire_ml=330
  2. INSERT bières africaines placeholder :
     - Castel 33cL, Mutzig 33cL, Kadji Beer 33cL, Isenbeck 33cL, 33 Export 33cL
     - Tous : volume=330ml, unite_base='cL', colisage=12, prix_achat=250 cts (2.50€)
  3. INSERT `Pelforth Brun 75cL` (placeholder pour grande Pelforth)

Tenant épicerie = 2.

Usage :
    docker exec -w /app futurproj_api python3 \\
        scripts/restaurant/create_missing_beers.py [--apply]
"""
from __future__ import annotations

import argparse
import os
import sys

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text


_TENANT_ID = 2

# Bières à créer (prix_achat = 2.50€ pour 30€/12, pack 12)
_AFRICAN_BEERS = [
    ("Castel 33cL",     330, "cL", 12, 250),
    ("Mutzig 33cL",     330, "cL", 12, 250),
    ("Kadji Beer 33cL", 330, "cL", 12, 250),
    ("Isenbeck 33cL",   330, "cL", 12, 250),
    ("33 Export 33cL",  330, "cL", 12, 250),
]

# Pelforth grande (75cL pack 12, prix achat à confirmer — 3€/bouteille estimé)
_PELFORTH_GRAND = ("Pelforth Brun 75cL", 750, "cL", 12, 300)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])

    created = []
    updated = []
    skipped = []

    with engine.begin() as conn:
        # 1. Normaliser Guiness Irlande
        res = conn.execute(text(
            "SELECT volume_unitaire_ml FROM epicerie_produits WHERE id = 8096"
        )).scalar()
        if res is None:
            if args.apply:
                conn.execute(text(
                    "UPDATE epicerie_produits SET volume_unitaire_ml = 330, unite_base = 'cL' "
                    "WHERE id = 8096"
                ))
            updated.append("Guiness Irlande (id 8096) → 330ml / cL")
        else:
            skipped.append(f"Guiness Irlande (id 8096) déjà volume={res}")

        # 2. Créer bières africaines + Pelforth
        for nom, vol_ml, unite, col, prix_achat in _AFRICAN_BEERS + [_PELFORTH_GRAND]:
            existing = conn.execute(text(
                "SELECT id FROM epicerie_produits "
                "WHERE tenant_id = :t AND LOWER(TRIM(designation_clean)) = LOWER(TRIM(:n))"
            ), {"t": _TENANT_ID, "n": nom}).scalar()
            if existing:
                skipped.append(f"{nom} existe déjà (id {existing})")
                continue

            if args.apply:
                # Prix vente estimé à partir du prix d'achat × 2.5 (marge bar)
                prix_vente = int(prix_achat * 2.5)
                new_id = conn.execute(text(
                    "INSERT INTO epicerie_produits "
                    "  (tenant_id, designation_clean, volume_unitaire_ml, unite_base, unite_vente, "
                    "   colisage, prix_achat_cts, prix_unitaire_cts, categorie, taux_tva, "
                    "   actif, created_at, updated_at) "
                    "VALUES (:t, :n, :v, :u, 'bouteille', :c, :pa, :pv, 'ALC_BIERE', 2000, "
                    "        true, now(), now()) "
                    "RETURNING id"
                ), {
                    "t": _TENANT_ID, "n": nom, "v": vol_ml, "u": unite,
                    "c": col, "pa": prix_achat, "pv": prix_vente,
                }).scalar()
                created.append(f"{nom} (id {new_id}, pack {col}, {prix_achat/100:.2f}€/bouteille)")
            else:
                created.append(f"{nom} (DRY-RUN, pack {col}, {prix_achat/100:.2f}€/bouteille)")

        if not args.apply:
            conn.rollback()

    print()
    print("=" * 60)
    print(f"CREATED ({len(created)}) :")
    for c in created:
        print(f"  • {c}")
    print(f"UPDATED ({len(updated)}) :")
    for u in updated:
        print(f"  • {u}")
    print(f"SKIPPED ({len(skipped)}) :")
    for s in skipped:
        print(f"  • {s}")
    if not args.apply:
        print("\n[DRY-RUN] --apply pour appliquer")


if __name__ == "__main__":
    main()
