"""EUROCIEL backfill prix depuis factures → catalogue (bug-eurociel-prix-null-01).

Les 146 produits catalogue EUROCIEL ont prix=NULL car le JSON source n'a pas
de prix. Les prix existent dans etl_imports.lignes_data.prix_unitaire_cts.
Ce script fait un match fuzzy par désignation et remonte le prix le plus
récent vers catalogue_produits.

Usage :
    docker exec -w /app futurproj_api python3 scripts/etl/eurociel_backfill_prix.py [--dry-run] [--min-score=80]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from rapidfuzz import fuzz, process
from sqlalchemy import create_engine, text

from app.services.catalogue.etl_deduplication import designation_signature


def sig_str(d: str) -> str:
    return " ".join(sorted(designation_signature(d or "")))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-score", type=int, default=80)
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        # 1) Factures EUROCIEL VALIDATED (plus récentes d'abord)
        imports = conn.execute(text(
            "SELECT id, lignes_data, created_at FROM etl_imports "
            "WHERE vendor_code = 'EUROCIEL' AND statut = 'VALIDATED' "
            "  AND lignes_data IS NOT NULL "
            "ORDER BY created_at DESC"
        )).fetchall()

        # Dict : sig_str(desig) → (prix_cts, taux_tva)  (premier vu = plus récent)
        latest_prix: dict[str, tuple[int, int]] = {}
        seen_raw = []
        for _, lignes_raw, _ in imports:
            if isinstance(lignes_raw, str):
                lignes = json.loads(lignes_raw)
            else:
                lignes = lignes_raw or []
            for l in lignes:
                if not isinstance(l, dict):
                    continue
                desig = l.get("designation") or ""
                prix = l.get("prix_unitaire_cts")
                tva = l.get("taux_tva_centieme")
                if not desig or not prix:
                    continue
                s = sig_str(desig)
                if s and s not in latest_prix:
                    latest_prix[s] = (int(prix), int(tva) if tva else 550)
                    seen_raw.append((desig, prix, tva))
        print(f"→ {len(latest_prix)} désignations distinctes avec prix dans factures EUROCIEL")

        # 2) Produits catalogue EUROCIEL sans prix
        cat_rows = conn.execute(text(
            "SELECT id, designation FROM catalogue_produits "
            "WHERE source_fournisseur = 'EUROCIEL' AND prix_unitaire_cts IS NULL"
        )).fetchall()
        print(f"→ {len(cat_rows)} produits catalogue EUROCIEL sans prix")

        facture_sigs = list(latest_prix.keys())
        updated = 0
        sample = []

        for cp_id, cp_desig in cat_rows:
            cp_sig = sig_str(cp_desig or "")
            if not cp_sig:
                continue
            # Match fuzzy
            match = process.extractOne(
                cp_sig, facture_sigs,
                scorer=fuzz.token_set_ratio,
                score_cutoff=args.min_score,
            )
            if not match:
                continue
            _, score, idx = match
            factur_sig = facture_sigs[idx]
            prix, tva = latest_prix[factur_sig]

            if len(sample) < 10:
                sample.append((int(score), cp_desig, factur_sig, prix))

            if not args.dry_run:
                conn.execute(
                    text(
                        "UPDATE catalogue_produits "
                        "SET prix_unitaire_cts = :p, "
                        "    taux_tva_centieme = COALESCE(taux_tva_centieme, :t) "
                        "WHERE id = :id"
                    ),
                    {"p": prix, "t": tva, "id": cp_id},
                )
            updated += 1

        if not args.dry_run:
            conn.commit()

            # Propager aussi vers épicerie
            r = conn.execute(text(
                "UPDATE epicerie_produits ep "
                "SET prix_achat_cts = cp.prix_unitaire_cts, "
                "    prix_unitaire_cts = cp.prix_unitaire_cts "  # TTC recalculé par flow marge plus tard
                "FROM catalogue_produits cp "
                "WHERE cp.source_fournisseur = 'EUROCIEL' "
                "  AND cp.prix_unitaire_cts IS NOT NULL "
                "  AND (ep.prix_achat_cts = 0 OR ep.prix_achat_cts IS NULL) "
                "  AND LOWER(TRIM(ep.designation_clean)) = LOWER(TRIM(cp.designation)) "
                "  AND ep.tenant_id = 2"
            ))
            conn.commit()
            print(f"→ Épicerie prix_achat propagés : {r.rowcount}")

        print()
        print("=== Échantillon ===")
        for s, d1, d2, p in sample:
            print(f"  [{s}] catalogue={d1[:35]!r} ~ facture={d2[:35]!r} prix={p / 100:.2f}€")
        print()
        print("=" * 50)
        print(f"  Prix EUROCIEL backfillés : {updated}/{len(cat_rows)}")
        if args.dry_run:
            print("  [DRY-RUN]")
        print("=" * 50)


if __name__ == "__main__":
    main()
