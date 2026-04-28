"""Importe les ventes SumUp vers restaurant_commandes + restaurant_lignes_commande.

Format attendu (rapport-de-commandes-produits-*.csv) :
  "Etablissement";"ID Etablissement";"Date ouverture";"Date fermeture";
  "ID commande";"Devise";"Produit";"SKU";"Quantité";...;
  "Prix ​​unitaire TTC";"Remises";"CA TTC";"CA HT";"Montant TVA"

Idempotent : si `sumup_order_id` existe déjà, skip la commande entière.

Matching nom produit SumUp → variante :
  1. Alias explicites (override manuel)
  2. LOWER+TRIM exact
  3. Fuzzy rapidfuzz token_set_ratio ≥ 85

Usage :
    docker exec -w /app futurproj_api python3 \\
        scripts/restaurant/import_sumup_sales.py \\
        --file /app/uploads/sumup_2025.csv \\
        [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime
from decimal import Decimal

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from rapidfuzz import fuzz, process
from sqlalchemy import create_engine, text


_TENANT_RESTO = 3

# Alias explicites : nom SumUp → nom variante exact (pour les cas ambigus)
_NAME_ALIASES = {
    "pelfort": "PELFORT",
    "salade": "SALADE MAISON",
    "ndole poisson frit": "NDOLE POISSON FRIT",
    "1/2 plat ailes": "DEMI PLAT AILES",
    "sauce jaune p fume": "SAUCE JAUNE POISSON FUMÉ",
    "petit vin": "Vin 20€",  # approximation ; à confirmer
    "mechoui chevre": "Méchoui chèvre",
}


def _parse_fr_number(s: str) -> Decimal:
    """Convertit '6,00' ou '5.68' → Decimal."""
    s = s.strip().replace(" ", "")
    if not s:
        return Decimal(0)
    return Decimal(s.replace(",", "."))


def _parse_date(s: str) -> datetime | None:
    s = s.strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def load_variants(conn) -> tuple[dict[str, int], dict[str, int]]:
    """Charge (exact_map, variants_names_to_id) pour lookup."""
    rows = conn.execute(text(
        "SELECT id, nom FROM restaurant_variantes_plat "
        "WHERE tenant_id = :t AND is_active"
    ), {"t": _TENANT_RESTO}).fetchall()
    exact = {r[1].strip().lower(): r[0] for r in rows}
    names_list = [r[1] for r in rows]
    return exact, names_list


def match_variant(sumup_name: str, exact: dict, names_list: list[str]) -> tuple[int | None, str, int]:
    """Retourne (variant_id, match_method, score)."""
    normalized = sumup_name.strip().lower()
    # 1. Alias explicite
    if normalized in _NAME_ALIASES:
        aliased = _NAME_ALIASES[normalized].strip().lower()
        if aliased in exact:
            return exact[aliased], "alias", 100
    # 2. Exact
    if normalized in exact:
        return exact[normalized], "exact", 100
    # 3. Fuzzy
    match = process.extractOne(
        sumup_name, names_list, scorer=fuzz.token_set_ratio, score_cutoff=85,
    )
    if match:
        _, score, idx = match
        from_dict = list(exact.items())[idx]  # on recharge mais on ne peut pas mapper idx ; plutôt refaire
        # Mieux : chercher l'id par nom
        matched_name = names_list[idx].strip().lower()
        return exact.get(matched_name), "fuzzy", int(score)
    return None, "no_match", 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="Chemin CSV rapport-de-commandes-produits")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])

    stats = {
        "lines_read": 0, "orders_new": 0, "orders_skipped_existing": 0,
        "lines_inserted": 0, "lines_no_match": 0, "lines_fuzzy": 0,
        "errors": 0,
    }
    unmatched: dict[str, int] = {}

    with engine.begin() as conn:
        exact, names_list = load_variants(conn)
        print(f"→ {len(names_list)} variantes actives chargées")

        # Grouper par ID commande
        orders: dict[str, dict] = {}
        with open(args.file, encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";", quotechar='"')
            header = next(reader)
            # Détecter les colonnes
            col_idx = {name: i for i, name in enumerate(header)}

            def col(row, name):
                return row[col_idx[name]] if name in col_idx else ""

            for row in reader:
                if not row or not any(row):
                    continue
                stats["lines_read"] += 1
                order_id = col(row, "ID commande").strip()
                if not order_id:
                    continue
                produit = col(row, "Produit").strip()
                qte_raw = col(row, "Quantité").strip()
                prix_u_raw = col(row, "Prix ​​unitaire TTC").strip() \
                    or col(row, "Prix unitaire TTC").strip()
                ca_ttc_raw = col(row, "CA TTC").strip()
                ca_ht_raw = col(row, "CA HT").strip()
                tva_raw = col(row, "Montant TVA").strip()

                if order_id not in orders:
                    orders[order_id] = {
                        "date_ouverture": _parse_date(col(row, "Date ouverture")),
                        "date_fermeture": _parse_date(col(row, "Date fermeture")),
                        "lignes": [],
                        "sous_total": Decimal(0),
                        "tva": Decimal(0),
                        "total": Decimal(0),
                    }
                try:
                    qte = int(qte_raw) if qte_raw else 1
                except ValueError:
                    qte = 1
                orders[order_id]["lignes"].append({
                    "produit": produit,
                    "qte": qte,
                    "prix_u_cts": int(_parse_fr_number(prix_u_raw) * 100),
                    "ca_ttc": _parse_fr_number(ca_ttc_raw),
                    "ca_ht": _parse_fr_number(ca_ht_raw),
                    "tva": _parse_fr_number(tva_raw),
                })
                orders[order_id]["total"] += _parse_fr_number(ca_ttc_raw)
                orders[order_id]["sous_total"] += _parse_fr_number(ca_ht_raw)
                orders[order_id]["tva"] += _parse_fr_number(tva_raw)

        print(f"→ {len(orders)} commandes distinctes extraites")

        for order_id, data in orders.items():
            # Idempotence : skip si UUID existe déjà
            existing = conn.execute(text(
                "SELECT id FROM restaurant_commandes WHERE sumup_order_id = :s"
            ), {"s": order_id}).scalar()
            if existing:
                stats["orders_skipped_existing"] += 1
                continue

            stats["orders_new"] += 1

            cmd_id = None
            if args.apply:
                cmd_id = conn.execute(text(
                    "INSERT INTO restaurant_commandes "
                    "  (tenant_id, sumup_order_id, date_ouverture, date_fermeture, "
                    "   statut, nb_couverts, sous_total_cts, tva_cts, total_cts, "
                    "   created_at, updated_at) "
                    "VALUES (:t, :sumup, :do, :df, 'PAYEE', 1, :st, :tva, :tot, "
                    "        now(), now()) RETURNING id"
                ), {
                    "t": _TENANT_RESTO, "sumup": order_id,
                    "do": data["date_ouverture"], "df": data["date_fermeture"],
                    "st": int(data["sous_total"] * 100),
                    "tva": int(data["tva"] * 100),
                    "tot": int(data["total"] * 100),
                }).scalar()

            # Matching + stats (toujours) + insert lignes (si apply)
            for ligne in data["lignes"]:
                variant_id, method, score = match_variant(ligne["produit"], exact, names_list)
                if variant_id is None:
                    stats["lines_no_match"] += 1
                    unmatched[ligne["produit"]] = unmatched.get(ligne["produit"], 0) + 1
                    continue
                if method == "fuzzy":
                    stats["lines_fuzzy"] += 1
                stats["lines_inserted"] += 1
                if args.apply:
                    conn.execute(text(
                        "INSERT INTO restaurant_lignes_commande "
                        "  (tenant_id, commande_id, variante_id, quantite, prix_unitaire_cts, "
                        "   statut_plat, created_at, updated_at) "
                        "VALUES (:t, :c, :v, :q, :pu, 'SERVIE', now(), now())"
                    ), {
                        "t": _TENANT_RESTO, "c": cmd_id, "v": variant_id,
                        "q": ligne["qte"], "pu": ligne["prix_u_cts"],
                    })

        if not args.apply:
            conn.rollback()

    print()
    print("=" * 60)
    for k, v in stats.items():
        print(f"  {k:30s} {v}")
    if unmatched:
        print(f"\n  Produits sans match (top 10) :")
        for nom, count in sorted(unmatched.items(), key=lambda x: -x[1])[:10]:
            print(f"    {nom:40s} {count}")
    if not args.apply:
        print("\n[DRY-RUN]")


if __name__ == "__main__":
    main()
