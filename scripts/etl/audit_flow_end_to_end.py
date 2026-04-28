"""Audit end-to-end du flow ETL.

Trace chaque ligne des 10 plus grosses factures à travers les étapes :
  [2-5] etl_imports.lignes_data  (LigneParsee post parse+enrich+auto_fill)
  [6]   catalogue_produits       (INSERT ou MERGE par dédup)
  [7-8] epicerie_produits        (propagation)
  [9]   UI (ce qu'affiche /inventaire)

Pour chaque champ critique, mesure la "perte de signal" entre étapes.

Usage :
    docker exec -w /app futurproj_api python3 scripts/etl/audit_flow_end_to_end.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text


TOP_N_IMPORT_IDS = [8593, 8698, 8636, 8697, 8578, 8694, 8670, 8353, 8436, 8612]

CHAMPS = [
    "ean", "marque", "categorie_code",
    "prix_unitaire_cts", "taux_tva_centieme",
    "volume_unitaire_ml", "colisage",
    "conditionnement",
]


def truthy(v):
    if v is None or v == "" or v == 0:
        return False
    if isinstance(v, str) and v.upper() == "AUTRE":
        return False
    return True


def main() -> None:
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, fichier_source, nb_lignes_ok, lignes_data "
            "FROM etl_imports WHERE id = ANY(:ids)"
        ), {"ids": TOP_N_IMPORT_IDS}).fetchall()

        # Stats
        total_lignes = 0
        field_filled = {s: Counter() for s in ("LIGNE", "CATALOGUE", "EPICERIE")}
        by_vendor_counts: dict[str, int] = defaultdict(int)
        lines_per_catalogue_product: Counter = Counter()
        catalogue_ean_conflicts: Counter = Counter()
        lines_sans_match_catalogue = 0
        lines_sans_match_epicerie = 0
        merge_suspects = []  # (cat_designation, set_eans, nb_lignes)

        for import_id, fichier, nb_ok, lignes_raw in rows:
            lignes = json.loads(lignes_raw) if isinstance(lignes_raw, str) else (lignes_raw or [])
            for l in lignes:
                if not isinstance(l, dict):
                    continue
                total_lignes += 1

                # [2-5] LIGNE — quels champs sont remplis post parse+enrich+auto_fill
                for s in CHAMPS:
                    if truthy(l.get(s)):
                        field_filled["LIGNE"][s] += 1

                # [6] CATALOGUE — match par EAN ou designation_norm
                cp = None
                if l.get("ean"):
                    cp = conn.execute(
                        text(
                            "SELECT id, designation, ean, marque, categorie_code, "
                            "       prix_unitaire_cts, taux_tva_centieme, "
                            "       volume_unitaire_ml, colisage, conditionnement, "
                            "       designation_norm "
                            "FROM catalogue_produits WHERE ean = :e LIMIT 1"
                        ),
                        {"e": l["ean"]},
                    ).mappings().first()
                if cp is None and l.get("designation_norm"):
                    cp = conn.execute(
                        text(
                            "SELECT id, designation, ean, marque, categorie_code, "
                            "       prix_unitaire_cts, taux_tva_centieme, "
                            "       volume_unitaire_ml, colisage, conditionnement, "
                            "       designation_norm "
                            "FROM catalogue_produits WHERE designation_norm = :n LIMIT 1"
                        ),
                        {"n": l["designation_norm"]},
                    ).mappings().first()
                if cp is None:
                    lines_sans_match_catalogue += 1
                    continue

                lines_per_catalogue_product[cp["id"]] += 1
                for s in CHAMPS:
                    if truthy(cp.get(s)):
                        field_filled["CATALOGUE"][s] += 1

                # [7-8] EPICERIE — match par EAN catalogue
                ep = None
                if cp["ean"]:
                    ep = conn.execute(
                        text(
                            "SELECT id, designation_clean, ean, colisage, "
                            "       unite_base, volume_unitaire_ml, "
                            "       prix_achat_cts, prix_unitaire_cts, categorie "
                            "FROM epicerie_produits WHERE ean = :e AND tenant_id=2 LIMIT 1"
                        ),
                        {"e": cp["ean"]},
                    ).mappings().first()
                if ep is None:
                    lines_sans_match_epicerie += 1
                    continue

                # Mapper les champs épicerie sur CHAMPS pour comparaison
                ep_fields = {
                    "ean": ep.get("ean"),
                    "marque": None,  # pas de marque côté épicerie
                    "categorie_code": ep.get("categorie"),
                    "prix_unitaire_cts": ep.get("prix_unitaire_cts"),
                    "taux_tva_centieme": None,
                    "volume_unitaire_ml": ep.get("volume_unitaire_ml"),
                    "colisage": ep.get("colisage") if ep.get("colisage") and ep.get("colisage") > 1 else None,
                    "conditionnement": None,
                }
                for s in CHAMPS:
                    if truthy(ep_fields.get(s)):
                        field_filled["EPICERIE"][s] += 1

        # Sur-merge : catalogue produits avec beaucoup de lignes différentes
        surmergers = [(cp_id, cnt) for cp_id, cnt in lines_per_catalogue_product.items() if cnt >= 5]
        surmergers.sort(key=lambda x: -x[1])
        surmerge_details = []
        for cp_id, cnt in surmergers[:20]:
            cat = conn.execute(
                text("SELECT designation, ean FROM catalogue_produits WHERE id = :i"),
                {"i": cp_id},
            ).first()
            # Combien d'EANs distincts dans lignes_data pointant vers cet id ?
            unique_eans = set()
            for import_id, _, _, lignes_raw in rows:
                lignes = json.loads(lignes_raw) if isinstance(lignes_raw, str) else (lignes_raw or [])
                for l in lignes:
                    if isinstance(l, dict):
                        raw_ean = l.get("ean")
                        raw_desig = l.get("designation_norm")
                        cp_match = None
                        if raw_ean:
                            cp_match = conn.execute(
                                text("SELECT id FROM catalogue_produits WHERE ean = :e LIMIT 1"),
                                {"e": raw_ean},
                            ).scalar()
                        if cp_match != cp_id and raw_desig:
                            cp_match = conn.execute(
                                text("SELECT id FROM catalogue_produits WHERE designation_norm = :n LIMIT 1"),
                                {"n": raw_desig},
                            ).scalar()
                        if cp_match == cp_id and raw_ean:
                            unique_eans.add(raw_ean)
            surmerge_details.append((cat[0], cat[1], cnt, unique_eans))

        # Output
        print("=" * 70)
        print(f"AUDIT 10 PLUS GROSSES FACTURES — {total_lignes} lignes au total")
        print("=" * 70)
        print()
        print(f"Matches :")
        print(f"  Lignes avec match catalogue : {total_lignes - lines_sans_match_catalogue}/{total_lignes}")
        print(f"  Lignes avec match épicerie  : {total_lignes - lines_sans_match_catalogue - lines_sans_match_epicerie}/{total_lignes}")
        print()
        print(f"  {'Champ':25s}  {'LIGNE':>8s}  {'CATALOG':>8s}  {'EPICERIE':>8s}  Perte [LIGNE→CAT]  Perte [CAT→EP]")
        print(f"  {'-' * 25:25s}  {'-' * 8:>8s}  {'-' * 8:>8s}  {'-' * 8:>8s}")
        for s in CHAMPS:
            l = field_filled["LIGNE"][s]
            c = field_filled["CATALOGUE"][s]
            e = field_filled["EPICERIE"][s]
            perte_lc = f"{l - c:+d}" if l else "n/a"
            perte_ce = f"{c - e:+d}" if c else "n/a"
            pct_l = 100 * l / total_lignes if total_lignes else 0
            pct_c = 100 * c / total_lignes if total_lignes else 0
            pct_e = 100 * e / total_lignes if total_lignes else 0
            print(f"  {s:25s}  {l:>4d}({pct_l:>3.0f}%)  {c:>4d}({pct_c:>3.0f}%)  {e:>4d}({pct_e:>3.0f}%)   {perte_lc:>6s}          {perte_ce:>6s}")
        print()
        print(f"SUR-MERGES (produits catalogue avec >=5 lignes factures) :")
        print(f"  Nb produits concernés : {len(surmergers)}")
        print(f"  Top 10 :")
        for desig, ean, cnt, eans in surmerge_details[:10]:
            suspect = " ⚠️ MULTI-EAN" if len(eans) > 1 else ""
            eans_sample = list(eans)[:3]
            print(f"    [{cnt:3d}×] {desig[:40]!r:42s} ean={ean}  distinct_lignes_eans={len(eans)}{suspect}")
            if len(eans) > 1:
                for e in eans_sample:
                    print(f"         → {e}")
        print()


if __name__ == "__main__":
    main()
