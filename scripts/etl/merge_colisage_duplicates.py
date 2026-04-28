"""Merge des doublons catalogue/épicerie issus d'une dédup colisage trop stricte.

Contexte (2026-04-24) :
    `_same_physical_attrs` refusait historiquement le match si le colisage
    différait. Résultat : "1664 25cL" existait en 3 produits distincts (packs
    18/20/24). Le colisage n'étant qu'un attribut d'emballage, ces 3 doivent
    fusionner en 1 seul, les EANs devenant secondaires et les colisages
    tracés dans le pivot.

Règle de regroupement :
    Produits catalogue partageant (marque, unite_base, volume_unitaire_ml).
    Groupes ≥ 2 produits non encore mergés.

Canonique :
    Le produit ayant le plus grand nombre de références (stock mouvement,
    ligne de vente, mapping resto) gagne ; en cas d'égalité, le plus
    ancien (id ASC).

Usage :
    docker exec -w /app futurproj_api python3 scripts/etl/merge_colisage_duplicates.py --dry-run
    docker exec -w /app futurproj_api python3 scripts/etl/merge_colisage_duplicates.py --apply
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from rapidfuzz import fuzz
from sqlalchemy import create_engine, text


_PACK_TOKEN_RE = re.compile(
    r"\b("
    r"x\s*\d+|\d+\s*x\s*\d+|pack\s*\d+|lot\s*\d+|"
    r"\(\d+\s*x\s*\d+\)|vp|rvp|fardeau|cartouche|colis|pack|caisse"
    r")\b",
    flags=re.IGNORECASE,
)
_SPACE_RE = re.compile(r"\s+")
_FUZZY_THRESHOLD = 92


def _strip_pack_tokens(designation: str | None) -> str:
    if not designation:
        return ""
    s = _PACK_TOKEN_RE.sub(" ", designation)
    s = _SPACE_RE.sub(" ", s).strip().lower()
    return s


def _group_candidates(conn) -> dict[tuple, list[tuple[int, str]]]:
    """Regroupe par (marque, unite_base, volume) puis cluster fuzzy sur designation."""
    rows = conn.execute(text(
        "SELECT id, marque, unite_base, volume_unitaire_ml, designation "
        "FROM catalogue_produits "
        "WHERE merged_into_id IS NULL "
        "  AND marque IS NOT NULL "
        "  AND unite_base IS NOT NULL "
        "  AND volume_unitaire_ml IS NOT NULL "
        "ORDER BY id"
    )).fetchall()
    raw_groups: dict[tuple, list[tuple[int, str]]] = defaultdict(list)
    for cid, marque, unite, vol, desig in rows:
        key = (marque.strip().upper(), unite.strip().lower(), int(vol))
        raw_groups[key].append((cid, _strip_pack_tokens(desig)))

    refined: dict[tuple, list[tuple[int, str]]] = {}
    for key, members in raw_groups.items():
        if len(members) < 2:
            continue
        clusters: list[list[tuple[int, str]]] = []
        for cid, stripped in members:
            placed = False
            for cluster in clusters:
                ref = cluster[0][1]
                # ratio (distance Levenshtein normalisée) — discrimine "RED BULL"
                # vs "RED BULL BLUE" (token_set_ratio les confond car sous-ensemble).
                if fuzz.ratio(stripped, ref) >= _FUZZY_THRESHOLD:
                    cluster.append((cid, stripped))
                    placed = True
                    break
            if not placed:
                clusters.append([(cid, stripped)])
        for idx, cluster in enumerate(clusters):
            if len(cluster) >= 2:
                refined[(*key, idx)] = cluster
    return refined


def _pick_canonical(conn, ids: list[int]) -> int:
    """Renvoie l'id catalogue avec le plus de références en aval (par EAN)."""
    scores: dict[int, int] = {}
    for cid in ids:
        ean_q = conn.execute(text(
            "SELECT ean FROM catalogue_produits WHERE id = :i "
            "UNION SELECT ean FROM catalogue_produit_eans WHERE catalogue_produit_id = :i"
        ), {"i": cid}).fetchall()
        eans = [r[0] for r in ean_q if r[0]]
        if not eans:
            scores[cid] = 0
            continue
        nb = conn.execute(text(
            "SELECT COUNT(*) FROM epicerie_stock_movements m "
            "JOIN epicerie_produits p ON p.id = m.produit_id "
            "WHERE p.ean = ANY(:eans)"
        ), {"eans": eans}).scalar() or 0
        scores[cid] = nb
    max_score = max(scores.values())
    tied = [cid for cid, s in scores.items() if s == max_score]
    return min(tied)


def _find_epicerie_canonical(conn, catalogue_ids: list[int]) -> tuple[int | None, list[int]]:
    """Trouve le epicerie_produit canonique + secondaires pour un groupe catalogue."""
    eans_rows = conn.execute(text(
        "SELECT ean FROM catalogue_produits WHERE id = ANY(:ids) "
        "UNION SELECT ean FROM catalogue_produit_eans WHERE catalogue_produit_id = ANY(:ids)"
    ), {"ids": catalogue_ids}).fetchall()
    eans = [r[0] for r in eans_rows if r[0]]
    if not eans:
        return None, []
    ep_rows = conn.execute(text(
        "SELECT ep.id, COALESCE(cnt.n, 0) AS mvt_cnt FROM epicerie_produits ep "
        "LEFT JOIN (SELECT produit_id, COUNT(*) AS n FROM epicerie_stock_movements GROUP BY produit_id) cnt "
        "  ON cnt.produit_id = ep.id "
        "WHERE ep.ean = ANY(:eans) "
        "ORDER BY mvt_cnt DESC, ep.id ASC"
    ), {"eans": eans}).fetchall()
    if not ep_rows:
        return None, []
    canonical_id = ep_rows[0][0]
    secondary_ids = [r[0] for r in ep_rows[1:]]
    return canonical_id, secondary_ids


def merge_catalogue_group(conn, canonical_id: int, secondary_ids: list[int], apply: bool) -> None:
    """Fusionne les secondaires dans le canonique côté catalogue."""
    for sid in secondary_ids:
        # EAN principal secondaire → devient EAN secondaire du canonique
        sec_ean = conn.execute(text(
            "SELECT ean FROM catalogue_produits WHERE id = :i"
        ), {"i": sid}).scalar()
        source = conn.execute(text(
            "SELECT source_fournisseur FROM catalogue_produits WHERE id = :i"
        ), {"i": sid}).scalar()

        if apply:
            # Reparenter EANs secondaires existants du doublon vers le canonique
            conn.execute(text(
                "UPDATE catalogue_produit_eans SET catalogue_produit_id = :c "
                "WHERE catalogue_produit_id = :s "
                "  AND ean NOT IN (SELECT ean FROM catalogue_produit_eans WHERE catalogue_produit_id = :c) "
                "  AND ean != COALESCE((SELECT ean FROM catalogue_produits WHERE id = :c), '')"
            ), {"c": canonical_id, "s": sid})
            # Supprimer les conflits restants (EAN déjà présent)
            conn.execute(text(
                "DELETE FROM catalogue_produit_eans WHERE catalogue_produit_id = :s"
            ), {"s": sid})
            # Ajouter l'EAN principal du doublon comme secondaire du canonique
            if sec_ean:
                conn.execute(text(
                    "INSERT INTO catalogue_produit_eans (catalogue_produit_id, ean, source_fournisseur) "
                    "VALUES (:c, :e, :src) ON CONFLICT DO NOTHING"
                ), {"c": canonical_id, "e": sec_ean, "src": source})
            # Reparenter colisages observés
            conn.execute(text(
                "INSERT INTO catalogue_produit_colisages "
                "  (catalogue_produit_id, colisage, source_fournisseur, first_seen_at, last_seen_at) "
                "SELECT :c, colisage, source_fournisseur, first_seen_at, last_seen_at "
                "FROM catalogue_produit_colisages WHERE catalogue_produit_id = :s "
                "ON CONFLICT (catalogue_produit_id, colisage, source_fournisseur) "
                "DO UPDATE SET last_seen_at = EXCLUDED.last_seen_at"
            ), {"c": canonical_id, "s": sid})
            conn.execute(text(
                "DELETE FROM catalogue_produit_colisages WHERE catalogue_produit_id = :s"
            ), {"s": sid})
            # Enregistrer le colisage originel du doublon (depuis la colonne)
            orig_colisage = conn.execute(text(
                "SELECT colisage FROM catalogue_produits WHERE id = :i"
            ), {"i": sid}).scalar()
            if orig_colisage and orig_colisage > 1:
                conn.execute(text(
                    "INSERT INTO catalogue_produit_colisages "
                    "  (catalogue_produit_id, colisage, source_fournisseur) "
                    "VALUES (:c, :co, :src) "
                    "ON CONFLICT (catalogue_produit_id, colisage, source_fournisseur) "
                    "DO UPDATE SET last_seen_at = now()"
                ), {"c": canonical_id, "co": int(orig_colisage), "src": source})
            # Reparenter conflits ETL
            conn.execute(text(
                "UPDATE etl_conflicts SET catalogue_produit_id = :c WHERE catalogue_produit_id = :s"
            ), {"c": canonical_id, "s": sid})
            # Marquer le doublon comme mergé
            conn.execute(text(
                "UPDATE catalogue_produits SET merged_into_id = :c, ean = NULL "
                "WHERE id = :s"
            ), {"c": canonical_id, "s": sid})


def merge_epicerie_group(conn, canonical_id: int, secondary_ids: list[int], apply: bool) -> None:
    """Fusionne les secondaires dans le canonique côté épicerie (stock, mvts, etc.)."""
    for sid in secondary_ids:
        if apply:
            # Consolider stock : additionner quantite, garder seuil max
            conn.execute(text(
                "INSERT INTO epicerie_stock "
                "  (tenant_id, produit_id, quantite, seuil_alerte, created_at, updated_at) "
                "SELECT tenant_id, :c, quantite, seuil_alerte, created_at, now() "
                "FROM epicerie_stock WHERE produit_id = :s "
                "ON CONFLICT (tenant_id, produit_id) DO UPDATE "
                "  SET quantite = epicerie_stock.quantite + EXCLUDED.quantite, "
                "      seuil_alerte = GREATEST(epicerie_stock.seuil_alerte, EXCLUDED.seuil_alerte), "
                "      updated_at = now()"
            ), {"c": canonical_id, "s": sid})
            conn.execute(text("DELETE FROM epicerie_stock WHERE produit_id = :s"), {"s": sid})
            # Reparenter mouvements, prix_historique, mappings resto, lignes vente/transfert/supply
            for tbl in (
                "epicerie_stock_movements",
                "epicerie_prix_historique",
                "restaurant_ingredient_epicerie_mappings",
                "epicerie_vente_lignes",
                "internal_transfer_lines",
                "epicerie_supply_order_lines",
            ):
                conn.execute(text(
                    f"UPDATE {tbl} SET produit_id = :c WHERE produit_id = :s"
                ), {"c": canonical_id, "s": sid})
            # EANs secondaires côté épicerie
            sec_ean = conn.execute(text(
                "SELECT ean FROM epicerie_produits WHERE id = :i"
            ), {"i": sid}).scalar()
            conn.execute(text(
                "DELETE FROM epicerie_produit_eans WHERE produit_id = :s"
            ), {"s": sid})
            if sec_ean:
                tenant_id = conn.execute(text(
                    "SELECT tenant_id FROM epicerie_produits WHERE id = :i"
                ), {"i": canonical_id}).scalar()
                conn.execute(text(
                    "INSERT INTO epicerie_produit_eans (tenant_id, produit_id, ean) "
                    "VALUES (:t, :c, :e) ON CONFLICT DO NOTHING"
                ), {"t": tenant_id, "c": canonical_id, "e": sec_ean})
            # Désactiver le doublon (ean NULL pour libérer la contrainte)
            conn.execute(text(
                "UPDATE epicerie_produits SET actif = false, ean = NULL WHERE id = :s"
            ), {"s": sid})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Appliquer réellement (par défaut dry-run)")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        groups = _group_candidates(conn)
        if not groups:
            print("Aucun groupe doublon détecté (marque, unite_base, volume_unitaire_ml).")
            return

        print(f"{'=' * 70}")
        print(f"GROUPES DOUBLONS DÉTECTÉS : {len(groups)}")
        print(f"Mode : {'APPLY' if args.apply else 'DRY-RUN (pas de modif)'}")
        print(f"{'=' * 70}")
        total_merged_cat = 0
        total_merged_ep = 0

        for key, members in sorted(groups.items(), key=lambda x: -len(x[1])):
            marque, unite, vol, _cluster_idx = key
            cat_ids = [cid for cid, _ in members]
            sample_desig = members[0][1]
            cat_canonical = _pick_canonical(conn, cat_ids)
            cat_secondaries = [i for i in cat_ids if i != cat_canonical]
            print(f"\n{marque} — {vol}ml ({unite})  [{sample_desig!r}]")
            print(f"  catalogue canonical id={cat_canonical}, secondaires={cat_secondaries}")

            ep_canonical, ep_secondaries = _find_epicerie_canonical(conn, cat_ids)
            if ep_canonical:
                print(f"  épicerie  canonical id={ep_canonical}, secondaires={ep_secondaries}")

            merge_catalogue_group(conn, cat_canonical, cat_secondaries, apply=args.apply)
            total_merged_cat += len(cat_secondaries)
            if ep_canonical and ep_secondaries:
                merge_epicerie_group(conn, ep_canonical, ep_secondaries, apply=args.apply)
                total_merged_ep += len(ep_secondaries)

        print(f"\n{'=' * 70}")
        print(f"Merged catalogue : {total_merged_cat}, épicerie : {total_merged_ep}")
        if not args.apply:
            print("(dry-run : rien n'a été modifié, relance avec --apply)")
        else:
            print("APPLIED.")


if __name__ == "__main__":
    main()
