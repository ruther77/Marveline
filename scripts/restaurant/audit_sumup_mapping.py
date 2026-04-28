"""Audit fuzzy : pour chaque produit SumUp (top N), trouve la variante
restaurant la plus proche et sort le résultat pour review.

Usage :
    docker exec -w /app futurproj_api python3 \\
        scripts/restaurant/audit_sumup_mapping.py --input /app/uploads/sumup_products.txt \\
        --out /app/uploads/sumup_mapping_audit.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from rapidfuzz import fuzz, process
from sqlalchemy import create_engine, text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Fichier texte : nb_occ nom_produit par ligne")
    ap.add_argument("--out", required=True, help="CSV output audit")
    ap.add_argument("--tenant", type=int, default=3)
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        variants = conn.execute(text(
            "SELECT id, nom, type, prix_vente_cts FROM restaurant_variantes_plat "
            "WHERE tenant_id = :t AND is_active "
            "ORDER BY nom"
        ), {"t": args.tenant}).fetchall()

    variant_names = [v[1] for v in variants]

    with open(args.input, encoding="utf-8") as f:
        lines = [l.rstrip() for l in f if l.strip()]

    results = []
    for line in lines:
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        try:
            count = int(parts[0])
        except ValueError:
            continue
        sumup_nom = parts[1].strip()
        match = process.extractOne(
            sumup_nom, variant_names,
            scorer=fuzz.token_set_ratio,
            score_cutoff=70,
        )
        if match:
            _, score, idx = match
            v = variants[idx]
            results.append({
                "sumup_nom": sumup_nom, "occurrences": count,
                "score": score, "variant_id": v[0], "variant_nom": v[1],
                "variant_type": v[2], "variant_prix_cts": v[3],
                "status": "AUTO" if score >= 90 else ("VERIFIER" if score >= 78 else "INCERTAIN"),
            })
        else:
            results.append({
                "sumup_nom": sumup_nom, "occurrences": count,
                "score": 0, "variant_id": "",
                "variant_nom": "", "variant_type": "", "variant_prix_cts": "",
                "status": "NO_MATCH",
            })

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "status", "sumup_nom", "occurrences", "score",
            "variant_id", "variant_nom", "variant_type", "variant_prix_cts",
        ])
        w.writeheader()
        for r in results:
            w.writerow(r)

    # Stats
    auto = sum(1 for r in results if r["status"] == "AUTO")
    verif = sum(1 for r in results if r["status"] == "VERIFIER")
    incert = sum(1 for r in results if r["status"] == "INCERTAIN")
    nomatch = sum(1 for r in results if r["status"] == "NO_MATCH")
    total_occ = sum(r["occurrences"] for r in results)
    auto_occ = sum(r["occurrences"] for r in results if r["status"] == "AUTO")
    nomatch_occ = sum(r["occurrences"] for r in results if r["status"] == "NO_MATCH")

    print(f"\n{'=' * 60}")
    print(f"Total produits SumUp uniques : {len(results)}")
    print(f"  AUTO (score ≥ 90)      : {auto:3d} ({100*auto/len(results):.0f}%)")
    print(f"  VERIFIER (78-90)       : {verif:3d}")
    print(f"  INCERTAIN (70-78)      : {incert:3d}")
    print(f"  NO_MATCH               : {nomatch:3d}")
    print()
    print(f"Total ventes 3 ans       : {total_occ}")
    print(f"  couvertes par AUTO     : {auto_occ} ({100*auto_occ/total_occ:.0f}%)")
    print(f"  sans match             : {nomatch_occ} ({100*nomatch_occ/total_occ:.0f}%)")
    print(f"\nCSV détaillé : {args.out}")


if __name__ == "__main__":
    main()
