"""Enrichissement cross-vendor : METRO = source de vérité.

Stratégie UX (2026-04-24) : le frontend doit afficher les produits TAIYAT,
ETHAN, EUROCIEL avec tous les champs possibles pré-remplis en copiant depuis
un produit METRO équivalent.

Matching par ordre de confiance :
  1. Match par EAN (priorité absolue si EAN valide des deux côtés)
  2. Match par `rapidfuzz.fuzz.token_set_ratio` sur designation_signature ≥ 85
  3. Fallback Jaccard overlap tokens ≥ 0.60

Fields copiés (si NULL/vide côté cible) :
  ean, marque, categorie_code, colisage, volume_unitaire_ml, taux_tva_centieme

Usage :
    docker exec -w /app futurproj_api python3 scripts/etl/cross_vendor_enrich.py [--dry-run] [--min-score=85]
"""
from __future__ import annotations

import argparse
import os
import sys

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from rapidfuzz import fuzz, process
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.catalogue.etl_deduplication import (
    designation_signature,
    is_ean_valid,
)


# Cross-vendor fuzzy match partage marque/catégorie/TVA (niveau famille),
# mais PAS ean/colisage/volume (produit-spécifiques : Coca Cola 6×1.5L et Coca
# Cola 33cL sont deux EANs distincts même si leur désignation match à 100%).
# Seuls les matchs par EAN EXACT ou HAUTE_CONFIDENCE (fuzzy ≥ 92 + volume ±5%
# + unite_base identique) copient aussi l'EAN.
_FIELDS_BY_FUZZ = ("marque", "categorie_code", "taux_tva_centieme")
_FIELDS_BY_EAN = (
    "ean", "marque", "categorie_code", "taux_tva_centieme",
    "colisage", "volume_unitaire_ml",
)
_HIGH_CONF_SCORE = 92
_VOLUME_TOL = 0.05  # ±5%


def _physical_match(row: dict, source: dict) -> bool:
    """Vrai si (unite_base identique ou NULL des 2 côtés) et (volume ±5%)."""
    u_r, u_s = (row.get("unite_base") or ""), (source.get("unite_base") or "")
    if u_r and u_s and u_r.lower() != u_s.lower():
        return False
    v_r, v_s = row.get("volume_unitaire_ml"), source.get("volume_unitaire_ml")
    if v_r and v_s:
        tol = max(v_r, v_s) * _VOLUME_TOL
        if abs(v_r - v_s) > tol:
            return False
    return True


def sig_str(designation: str) -> str:
    """Retourne la signature token-set comme string pour rapidfuzz."""
    tokens = designation_signature(designation or "")
    return " ".join(sorted(tokens))


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-score", type=int, default=85,
                    help="Seuil rapidfuzz token_set_ratio (défaut 85)")
    ap.add_argument("--min-jaccard", type=float, default=0.60)
    args = ap.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL non défini", file=sys.stderr)
        sys.exit(1)
    engine = create_engine(database_url)

    with Session(engine) as session:
        # 1) Charger METRO
        metro_rows = session.execute(text(
            "SELECT id, designation, ean, marque, categorie_code, colisage, "
            "       volume_unitaire_ml, unite_base, taux_tva_centieme "
            "FROM catalogue_produits "
            "WHERE source_fournisseur = 'METRO' AND merged_into_id IS NULL "
            "  AND ean IS NOT NULL AND ean <> ''"
        )).mappings().all()
        metro = [dict(m) for m in metro_rows]
        print(f"→ {len(metro)} produits METRO chargés (source de vérité)")

        by_ean = {m["ean"]: m for m in metro if m["ean"] and is_ean_valid(m["ean"])}
        metro_sigs = [sig_str(m["designation"] or "") for m in metro]
        metro_token_sets = [set(designation_signature(m["designation"] or "")) for m in metro]

        # 2) Charger les non-METRO
        other_rows = session.execute(text(
            "SELECT id, designation, source_fournisseur, ean, marque, categorie_code, "
            "       colisage, volume_unitaire_ml, unite_base, taux_tva_centieme "
            "FROM catalogue_produits "
            "WHERE source_fournisseur <> 'METRO' AND merged_into_id IS NULL"
        )).mappings().all()
        others = [dict(o) for o in other_rows]
        print(f"→ {len(others)} produits non-METRO à enrichir")

        stats = {"by_ean": 0, "by_fuzz": 0, "by_jaccard": 0, "no_match": 0, "updated": 0}
        by_field: dict[str, int] = {}

        for row in others:
            source = None
            match_type = None

            # B1 : EAN exact
            if row["ean"] and row["ean"] in by_ean:
                source = by_ean[row["ean"]]
                match_type = "ean"

            # B1b : marque + attributs physiques identiques → same product
            # Utile quand les désignations TAIYAT/METRO divergent mais que
            # marque + volume + unite_base + degré collent (ex: VIMTO 500ml).
            if source is None and row.get("marque"):
                marque_norm = row["marque"].strip().upper()
                candidates_by_brand = [
                    m for m in metro
                    if m.get("marque") and m["marque"].strip().upper() == marque_norm
                    and _physical_match(row, m)
                ]
                if len(candidates_by_brand) == 1:
                    source = candidates_by_brand[0]
                    match_type = "ean"

            # B2 : rapidfuzz token_set_ratio
            if source is None:
                sig_other = sig_str(row["designation"] or "")
                if sig_other:
                    match = process.extractOne(
                        sig_other, metro_sigs,
                        scorer=fuzz.token_set_ratio,
                        score_cutoff=args.min_score,
                    )
                    if match:
                        _, score, idx = match
                        candidate = metro[idx]
                        # B2a : haute conf + physique identique → EAN aussi
                        if score >= _HIGH_CONF_SCORE and _physical_match(row, candidate):
                            source = candidate
                            match_type = "ean"  # traite comme EAN (copie tous champs)
                        else:
                            source = candidate
                            match_type = "fuzz"

            # B3 : Jaccard fallback
            if source is None:
                tokens_other = set(designation_signature(row["designation"] or ""))
                if tokens_other:
                    best_score = 0.0
                    best_idx = -1
                    for idx, tset in enumerate(metro_token_sets):
                        if not tset:
                            continue
                        sc = jaccard(tokens_other, tset)
                        if sc > best_score:
                            best_score = sc
                            best_idx = idx
                    if best_score >= args.min_jaccard:
                        source = metro[best_idx]
                        match_type = "jaccard"

            if source is None:
                stats["no_match"] += 1
                continue

            stats[f"by_{match_type}"] += 1

            # Sélectionner les champs selon le type de match
            fields = _FIELDS_BY_EAN if match_type == "ean" else _FIELDS_BY_FUZZ

            # Sécurité : ne pas écraser un EAN existant par celui de METRO si différent
            if match_type == "ean" and row.get("ean") and row["ean"] != source.get("ean"):
                fields = tuple(f for f in fields if f != "ean")

            sets = []
            params: dict = {"id": row["id"]}
            for field in fields:
                src_val = source.get(field)
                if src_val is None or src_val == "":
                    continue
                if field == "categorie_code" and src_val == "AUTRE":
                    continue
                current = row.get(field)
                if field == "categorie_code":
                    is_empty = not current or current == "AUTRE"
                else:
                    is_empty = not current
                if not is_empty:
                    continue
                sets.append(f"{field} = :{field}")
                params[field] = src_val
                by_field.setdefault(field, 0)
                by_field[field] += 1

            if sets and not args.dry_run:
                # Si l'EAN cible existe déjà sur un autre produit, ne pas l'écraser :
                # le stocker comme EAN secondaire du produit courant.
                if "ean" in params:
                    conflict = session.execute(
                        text("SELECT id FROM catalogue_produits WHERE ean = :e AND id != :i"),
                        {"e": params["ean"], "i": row["id"]},
                    ).scalar()
                    if conflict is None:
                        conflict = session.execute(
                            text("SELECT catalogue_produit_id FROM catalogue_produit_eans "
                                 "WHERE ean = :e AND catalogue_produit_id != :i"),
                            {"e": params["ean"], "i": row["id"]},
                        ).scalar()
                    if conflict is not None:
                        session.execute(
                            text(
                                "INSERT INTO catalogue_produit_eans "
                                "  (catalogue_produit_id, ean, source_fournisseur) "
                                "VALUES (:c, :e, :src) ON CONFLICT DO NOTHING"
                            ),
                            {"c": row["id"], "e": params["ean"], "src": f"cross:{row['source_fournisseur']}"},
                        )
                        # Retire ean du UPDATE principal
                        sets = [s for s in sets if not s.startswith("ean ")]
                        params.pop("ean", None)
                        by_field["ean"] = by_field.get("ean", 0)  # reste compté comme trouvé
                if sets:
                    session.execute(
                        text(f"UPDATE catalogue_produits SET {', '.join(sets)} WHERE id = :id"),
                        params,
                    )
                    stats["updated"] += 1

        if not args.dry_run:
            session.commit()

            # Propager vers épicerie
            session.execute(text(
                "UPDATE epicerie_produits ep SET ean = cp.ean "
                "FROM catalogue_produits cp "
                "WHERE ep.ean IS NULL AND cp.ean IS NOT NULL "
                "  AND cp.merged_into_id IS NULL "
                "  AND LOWER(TRIM(ep.designation_clean)) = LOWER(TRIM(cp.designation)) "
                "  AND ep.tenant_id = 2"
            ))
            session.execute(text(
                "UPDATE epicerie_produits ep "
                "SET colisage = COALESCE(NULLIF(ep.colisage, 1), cp.colisage), "
                "    unite_base = COALESCE(ep.unite_base, cp.unite_base) "
                "FROM catalogue_produits cp "
                "WHERE ep.ean = cp.ean AND ep.ean IS NOT NULL "
                "  AND cp.merged_into_id IS NULL "
                "  AND cp.colisage > 1 "
                "  AND ep.tenant_id = 2"
            ))
            session.commit()

        print()
        print("=" * 50)
        print(f"  Non-METRO scannés   : {len(others)}")
        print(f"    match par EAN     : {stats['by_ean']}")
        print(f"    match fuzz >= {args.min_score}   : {stats['by_fuzz']}")
        print(f"    match Jaccard >= {args.min_jaccard} : {stats['by_jaccard']}")
        print(f"    pas de match      : {stats['no_match']}")
        print(f"    UPDATE catalogue  : {stats['updated']}")
        print(f"  Champs copiés :")
        for f, n in by_field.items():
            print(f"    {f:25s} : {n}")
        if args.dry_run:
            print("  [DRY-RUN]")
        print("=" * 50)


if __name__ == "__main__":
    main()
