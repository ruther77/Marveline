"""Propose un mapping ingrédient restaurant → produit épicerie.

Pour chaque ingrédient utilisé (protéine variante / recette / side), sort les
top-3 candidats épicerie (fuzzy rapidfuzz + heuristiques format) avec un
facteur_conv suggéré. Output CSV pour review manuelle.

Règles heuristiques :
  - Nettoyage nom ingrédient : retire parenthèses '(bouteille)', '(70cl)', etc.
  - Filtrage format :
      * 'petite' → volume épicerie ≤ 33cL (330ml)
      * 'grande' → volume épicerie ≥ 50cL (500ml)
      * '(70cl)' → volume épicerie ~= 700ml
      * '(75cl)' → volume épicerie ~= 750ml
  - facteur_conv suggéré :
      * unité ingr = 'bouteille' + volume connu → 1 (1 bouteille = 1 bouteille)
      * unité ingr = 'kg' + volume épicerie connu → volume_ml / 1000
      * unité ingr = 'pièce' + colisage épicerie → colisage

Usage :
    docker exec -w /app futurproj_api python3 \\
        scripts/restaurant/propose_ingredient_epicerie_mappings.py \\
        --out /app/uploads/mappings_proposals.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from typing import Optional

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from rapidfuzz import fuzz, process
from sqlalchemy import create_engine, text


_CONTENANT_RE = re.compile(r"\s*\([^)]+\)\s*", re.IGNORECASE)
_VOLUME_IN_NAME = re.compile(r"\((\d+)\s*cl\)", re.IGNORECASE)


def clean_ingredient_name(nom: str) -> str:
    """Retire les précisions de contenant entre parenthèses pour le matching."""
    return _CONTENANT_RE.sub(" ", nom).strip().lower()


def extract_volume_from_name(nom: str) -> Optional[int]:
    """Extrait un volume cL explicite du nom de l'ingrédient (ex: '(70cl)' → 70)."""
    m = _VOLUME_IN_NAME.search(nom)
    return int(m.group(1)) if m else None


def is_format_petite(nom: str) -> bool:
    return "petite" in nom.lower()


def is_format_grande(nom: str) -> bool:
    return "grande" in nom.lower()


def suggest_facteur_conv(
    ingr_unite: str,
    ingr_name: str,
    epi_volume_ml: Optional[int],
    epi_unite: Optional[str],
    epi_colisage: Optional[int],
) -> float:
    """Suggère un facteur_conv : combien d'unités ingrédient dans 1 unité épicerie."""
    u = (ingr_unite or "").lower()
    # Bouteille → 1 bouteille épicerie = 1 bouteille ingrédient (volume équivalent)
    if u in ("bouteille", "canette", "pièce", "piece"):
        return 1.0
    # kg → volume_ml / 1000 (convention 1g ≈ 1ml)
    if u == "kg" and epi_volume_ml:
        return round(epi_volume_ml / 1000.0, 4)
    # L → volume_ml / 1000 (même échelle)
    if u == "l" and epi_volume_ml:
        return round(epi_volume_ml / 1000.0, 4)
    return 1.0


def score_candidate(
    ingr_name_clean: str, ingr_name_raw: str,
    epi_designation: str, epi_volume_ml: Optional[int],
) -> int:
    """Score rapidfuzz + bonus/malus format."""
    base = fuzz.token_set_ratio(ingr_name_clean, epi_designation.lower())
    # Bonus format si volume attendu du nom ingrédient match
    vol_expected = extract_volume_from_name(ingr_name_raw)  # en cL
    if vol_expected and epi_volume_ml:
        expected_ml = vol_expected * 10
        if abs(epi_volume_ml - expected_ml) <= expected_ml * 0.10:
            base = min(100, base + 8)
    # Malus pour format incohérent si nom précise "petite" ou "grande"
    if is_format_petite(ingr_name_raw) and epi_volume_ml and epi_volume_ml > 400:
        base = max(0, base - 15)
    if is_format_grande(ingr_name_raw) and epi_volume_ml and epi_volume_ml < 500:
        base = max(0, base - 15)
    return int(base)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Chemin CSV de sortie")
    ap.add_argument("--tenant-resto", type=int, default=3)
    ap.add_argument("--tenant-epicerie", type=int, default=2)
    ap.add_argument("--min-score", type=int, default=55,
                    help="Score minimum pour inclure une proposition (défaut 55)")
    ap.add_argument("--top-n", type=int, default=3, help="Top N candidats par ingrédient")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])

    with engine.connect() as conn:
        # Ingrédients utilisés (protéines + recettes + sides)
        rows = conn.execute(text(
            "WITH used AS ( "
            "  SELECT DISTINCT ingredient_proteine_id AS id "
            "  FROM restaurant_variantes_plat "
            "  WHERE ingredient_proteine_id IS NOT NULL AND is_active = true "
            "  UNION "
            "  SELECT DISTINCT ingredient_id FROM restaurant_recettes_type_preparation "
            "  UNION "
            "  SELECT DISTINCT ingredient_id FROM restaurant_sides WHERE ingredient_id IS NOT NULL "
            ") "
            "SELECT i.id, i.nom, i.unite_stock, i.cout_unitaire_cts, c.nom AS categ "
            "FROM restaurant_ingredients i "
            "JOIN used u ON u.id = i.id "
            "LEFT JOIN restaurant_categories_ingredient c ON c.id = i.categorie_id "
            "WHERE i.is_active = true AND i.tenant_id = :tid "
            "ORDER BY c.nom, i.nom"
        ), {"tid": args.tenant_resto}).fetchall()
        ingredients = [
            {
                "id": r[0], "nom": r[1], "unite_stock": r[2],
                "cout_unitaire_cts": r[3], "categ": r[4] or "",
            }
            for r in rows
        ]

        # Produits épicerie (tenant 2)
        rows = conn.execute(text(
            "SELECT id, designation_clean, ean, volume_unitaire_ml, unite_base, "
            "       colisage, categorie, prix_achat_cts "
            "FROM epicerie_produits "
            "WHERE tenant_id = :tid AND actif = true "
            "ORDER BY designation_clean"
        ), {"tid": args.tenant_epicerie}).fetchall()
        produits = [
            {
                "id": r[0], "designation": r[1], "ean": r[2],
                "volume_unitaire_ml": r[3], "unite_base": r[4],
                "colisage": r[5], "categorie": r[6],
                "prix_achat_cts": r[7],
            }
            for r in rows
        ]

    print(f"→ {len(ingredients)} ingrédients utilisés à mapper")
    print(f"→ {len(produits)} produits épicerie candidats")

    epi_names_lower = [p["designation"].lower() for p in produits]

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "keep", "ordre", "ingredient_id", "ingredient_nom", "ingredient_unite",
            "ingredient_categ", "ingredient_cout_cts",
            "epicerie_produit_id", "epicerie_designation", "epicerie_volume_ml",
            "epicerie_unite_base", "epicerie_colisage",
            "score", "facteur_conv_suggere", "notes",
        ])

        for ingr in ingredients:
            name_clean = clean_ingredient_name(ingr["nom"])
            # Top 10 candidates rapidfuzz puis re-scoring avec heuristiques
            prelim = process.extract(
                name_clean, epi_names_lower,
                scorer=fuzz.token_set_ratio,
                limit=10,
            )
            scored: list[tuple[int, int]] = []  # (score, index)
            for _match_text, prelim_score, idx in prelim:
                p = produits[idx]
                fine_score = score_candidate(
                    name_clean, ingr["nom"], p["designation"], p["volume_unitaire_ml"],
                )
                if fine_score >= args.min_score:
                    scored.append((fine_score, idx))
            scored.sort(key=lambda x: -x[0])
            scored = scored[:args.top_n]

            if not scored:
                w.writerow([
                    "NON", "", ingr["id"], ingr["nom"], ingr["unite_stock"],
                    ingr["categ"], ingr["cout_unitaire_cts"],
                    "", "", "", "", "", "", "", "pas de match ≥ min_score",
                ])
                continue

            for ordre, (score, idx) in enumerate(scored):
                p = produits[idx]
                facteur = suggest_facteur_conv(
                    ingr["unite_stock"], ingr["nom"],
                    p["volume_unitaire_ml"], p["unite_base"], p["colisage"],
                )
                notes = []
                if score >= 92:
                    notes.append("AUTO")
                elif score >= 75:
                    notes.append("VERIFIER")
                else:
                    notes.append("INCERTAIN")
                w.writerow([
                    "OUI" if ordre == 0 and score >= 92 else "?",
                    ordre, ingr["id"], ingr["nom"], ingr["unite_stock"],
                    ingr["categ"], ingr["cout_unitaire_cts"],
                    p["id"], p["designation"], p["volume_unitaire_ml"],
                    p["unite_base"], p["colisage"],
                    score, facteur, " ".join(notes),
                ])

    print(f"✓ CSV généré : {args.out}")
    print("\nColonnes :")
    print("  keep : mettre OUI pour appliquer, NON pour ignorer (défaut : OUI si AUTO, ? sinon)")
    print("  ordre : 0 = principal, 1+ = secondaires")
    print("  facteur_conv_suggere : N unités ingrédient par unité épicerie (ajuste si besoin)")


if __name__ == "__main__":
    main()
