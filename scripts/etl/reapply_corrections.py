"""Re-applique les corrections manuelles historiques sur les produits catalogue
existants. Bug 2026-04-24 : etl_correction_history.designation_norm contient du
legacy UPPERCASE (ligne.designation stockée telle quelle), alors que
normalize_designation produit du lowercase — le lookup in-place ratait.

Ce script :
  1. Charge toutes les corrections (_AUTOFILL_FIELDS : ean, marque, categorie_code)
  2. Normalise les clés history via normalize_designation
  3. Pour chaque catalogue_produits, normalise sa designation et match
  4. UPDATE catalogue_produits.{ean, marque, categorie_code} si les valeurs
     sont NULL/vides ET qu'une correction existe
  5. Propage ean + marque vers epicerie_produits par match EAN ou designation

Usage :
    docker exec -w /app futurproj_api python3 scripts/etl/reapply_corrections.py
"""
from __future__ import annotations

import os
import sys

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.catalogue.etl_deduplication import normalize_designation


_AUTOFILL_FIELDS = ("ean", "marque", "categorie_code")


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL non défini", file=sys.stderr)
        sys.exit(1)
    engine = create_engine(database_url)

    with Session(engine) as session:
        # 1) Charger les corrections, les dédupliquer par (norm, field) DESC
        rows = session.execute(text(
            "SELECT designation_norm, field_corrected, new_value "
            "FROM etl_correction_history "
            "WHERE field_corrected IN ('ean', 'marque', 'categorie_code') "
            "  AND new_value IS NOT NULL "
            "ORDER BY id DESC"
        )).fetchall()

        history: dict[str, dict[str, str]] = {}
        for raw_norm, field, new_val in rows:
            key = normalize_designation(raw_norm or "")
            if not key:
                continue
            entry = history.setdefault(key, {})
            if field not in entry:
                entry[field] = new_val
        print(f"→ {len(history)} désignations avec corrections historiques")

        # 2) Scanner catalogue_produits
        cat_rows = session.execute(text(
            "SELECT id, designation, ean, marque, categorie_code "
            "FROM catalogue_produits"
        )).fetchall()

        stats = {"cat_updated": 0, "by_field": {"ean": 0, "marque": 0, "categorie_code": 0}}
        for cp_id, designation, ean, marque, cat in cat_rows:
            norm = normalize_designation(designation or "")
            if not norm or norm not in history:
                continue
            corrections = history[norm]
            sets = []
            params: dict = {"id": cp_id}
            current = {"ean": ean, "marque": marque, "categorie_code": cat}
            for field in _AUTOFILL_FIELDS:
                if field not in corrections or not corrections[field]:
                    continue
                # categorie_code='AUTRE' est considéré comme vide (classif par défaut)
                cur_val = current.get(field)
                is_empty = not cur_val or (field == "categorie_code" and cur_val == "AUTRE")
                if is_empty:
                    sets.append(f"{field} = :{field}")
                    params[field] = corrections[field]
                    stats["by_field"][field] += 1
            if sets:
                session.execute(
                    text(f"UPDATE catalogue_produits SET {', '.join(sets)} WHERE id = :id"),
                    params,
                )
                stats["cat_updated"] += 1

        session.commit()

        # 3) Propager ean + marque vers epicerie_produits
        #    - Si ep.ean manque ET cp.ean existe : copier via match designation
        #    - (marque n'existe pas sur epicerie_produits, skip)
        result = session.execute(text(
            "UPDATE epicerie_produits ep "
            "SET ean = cp.ean "
            "FROM catalogue_produits cp "
            "WHERE ep.ean IS NULL "
            "  AND cp.ean IS NOT NULL "
            "  AND cp.merged_into_id IS NULL "
            "  AND LOWER(TRIM(ep.designation_clean)) = LOWER(TRIM(cp.designation)) "
            "  AND ep.tenant_id = 2"
        ))
        stats["epicerie_ean_filled"] = result.rowcount or 0
        session.commit()

        print()
        print("=" * 50)
        print(f"  Catalogue produits corrigés  : {stats['cat_updated']}")
        print(f"    ean        : {stats['by_field']['ean']}")
        print(f"    marque     : {stats['by_field']['marque']}")
        print(f"    categorie  : {stats['by_field']['categorie_code']}")
        print(f"  Épicerie EAN propagés        : {stats['epicerie_ean_filled']}")
        print("=" * 50)


if __name__ == "__main__":
    main()
