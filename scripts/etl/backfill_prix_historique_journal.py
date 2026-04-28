"""Backfill rétroactif epicerie_prix_historique en mode journal d'événements.

Contexte : avant le fix 2026-04-24 (reception_etl.py), prix_historique ne
recevait une entrée QUE si le prix changeait vs. le dernier point. Résultat :
la modale produit affiche 1 seule ligne (ex: "1664 75cL · 09/01/2020 · 1,45€")
au lieu des N factures réelles.

Ce script reconstitue l'historique factuelement en repartant des mouvements
ENTREE rattachés à un etl_import_id : chaque ENTREE = 1 réception = 1 entrée
prix_historique. Il ne touche pas aux entrées existantes (INSERT IF NOT EXISTS
par couple produit_id + etl_import_id).

Valeurs reconstituées :
  - prix_achat_cts : depuis etl_imports.lignes_data (ligne matching par produit)
  - prix_vente_cts : recalculé via marges_categories + tva du produit actuel
  - source_fournisseur : etl_imports.vendor_code
  - etl_import_id : mouvement.etl_import_id
  - effective_date : etl_imports.date_facture (fallback: mouvement.date_mouvement)

Usage :
    docker exec -w /app futurproj_api python3 \\
        scripts/etl/backfill_prix_historique_journal.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from rapidfuzz import fuzz
from sqlalchemy import create_engine, text


_DEFAULT_MARGE_CENTIEME = 3000  # 30% si catégorie inconnue
_DEFAULT_TVA_CENTIEME = 550     # 5.5%


def _match_ligne(lignes: list[dict], produit: dict) -> dict | None:
    """Trouve la ligne ETL correspondant au produit épicerie.

    Ordre de priorité :
      1. Match par EAN (principal OU secondaire — EANs cross-pays du produit)
      2. Match désignation stricte (LOWER+TRIM)
      3. Fallback : mouvement lié à ce produit dans la facture = seule ligne
    """
    all_eans = set(produit.get("all_eans") or [])
    if produit.get("ean"):
        all_eans.add(produit["ean"])
    if all_eans:
        for l in lignes:
            if isinstance(l, dict) and l.get("ean") in all_eans:
                return l
    pdesig = (produit.get("designation_clean") or "").strip().lower()
    if pdesig:
        # Passe 1 : match strict
        for l in lignes:
            if not isinstance(l, dict):
                continue
            ldesig = (l.get("designation") or "").strip().lower()
            if ldesig == pdesig:
                return l
        # Passe 2 : fallback fuzzy (tolère ordre mots, accents, variations mineures)
        best = None
        best_score = 0
        for l in lignes:
            if not isinstance(l, dict):
                continue
            ldesig = (l.get("designation") or "").strip().lower()
            if not ldesig:
                continue
            score = fuzz.token_set_ratio(pdesig, ldesig)
            if score > best_score:
                best_score = score
                best = l
        if best is not None and best_score >= 88:
            return best
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])

    stats = {
        "entrees_scanned": 0, "entrees_without_ligne": 0,
        "entrees_without_date": 0, "already_present": 0,
        "inserted": 0, "tenant_missing_vendor": 0,
    }

    with engine.begin() as conn:
        # Charger les marges par tenant (pour calcul prix vente historique)
        marges_by_tenant: dict[int, dict[str, int]] = defaultdict(dict)
        for t_id, cat, taux in conn.execute(text(
            "SELECT tenant_id, categorie, taux_marge_centieme FROM epicerie_marges_categories"
        )).fetchall():
            marges_by_tenant[t_id][cat] = taux

        # Pré-charger tous les EtlImport avec vendor_code + date_facture
        imports = {
            r[0]: {"vendor_code": r[1], "date_facture": r[2], "numero_facture": r[3], "lignes_data": r[4]}
            for r in conn.execute(text(
                "SELECT id, vendor_code, date_facture, numero_facture, lignes_data "
                "FROM etl_imports WHERE lignes_data IS NOT NULL"
            )).fetchall()
        }
        print(f"→ {len(imports)} EtlImport avec lignes_data chargés")

        # Pré-charger les produits épicerie (pour match ligne + tva + catégorie)
        produits = {
            r[0]: {
                "tenant_id": r[1], "ean": r[2], "designation_clean": r[3],
                "categorie": r[4], "taux_tva": r[5], "prix_achat_cts": r[6],
                "all_eans": [],
            }
            for r in conn.execute(text(
                "SELECT id, tenant_id, ean, designation_clean, categorie, taux_tva, prix_achat_cts "
                "FROM epicerie_produits"
            )).fetchall()
        }
        # Ajouter EANs secondaires (cross-pays) depuis le pivot épicerie
        for pid, ean in conn.execute(text(
            "SELECT produit_id, ean FROM epicerie_produit_eans"
        )).fetchall():
            if pid in produits:
                produits[pid]["all_eans"].append(ean)
        # Ajouter EANs secondaires côté catalogue, propagés via ean principal ↔ catalogue
        for ep_id, ep_ean, cat_id in conn.execute(text(
            "SELECT ep.id, ep.ean, cp.id FROM epicerie_produits ep "
            "JOIN catalogue_produits cp ON cp.ean = ep.ean "
            "WHERE cp.merged_into_id IS NULL"
        )).fetchall():
            for alt_ean, _ in conn.execute(text(
                "SELECT ean, id FROM catalogue_produit_eans WHERE catalogue_produit_id = :c"
            ), {"c": cat_id}).fetchall():
                if ep_id in produits and alt_ean not in produits[ep_id]["all_eans"]:
                    produits[ep_id]["all_eans"].append(alt_ean)
        print(f"→ {len(produits)} produits épicerie chargés (+EANs secondaires)")

        # Tous les mouvements ENTREE liés à un etl_import
        rows = conn.execute(text(
            "SELECT m.id, m.tenant_id, m.produit_id, m.etl_import_id, m.date_mouvement "
            "FROM epicerie_stock_movements m "
            "WHERE m.type = 'ENTREE' AND m.etl_import_id IS NOT NULL "
            "ORDER BY m.etl_import_id, m.produit_id"
        )).fetchall()
        print(f"→ {len(rows)} mouvements ENTREE avec etl_import_id à backfiller")

        for mid, tid, pid, eid, mvt_date in rows:
            stats["entrees_scanned"] += 1
            imp = imports.get(eid)
            if imp is None:
                continue
            produit = produits.get(pid)
            if produit is None:
                continue

            # Match ligne dans JSON
            lignes_raw = imp["lignes_data"]
            lignes_list = json.loads(lignes_raw) if isinstance(lignes_raw, str) else (lignes_raw or [])
            ligne = _match_ligne(lignes_list, produit)
            if ligne is None:
                stats["entrees_without_ligne"] += 1
                continue

            prix_achat_cts = ligne.get("prix_unitaire_cts")
            if prix_achat_cts is None:
                prix_achat_cts = produit.get("prix_achat_cts")
            if not prix_achat_cts or prix_achat_cts <= 0:
                continue

            # Date effective : date_facture > date_mouvement
            eff_date = imp["date_facture"] or (mvt_date.date() if mvt_date else None)
            if eff_date is None:
                stats["entrees_without_date"] += 1
                continue

            # Calcul prix_vente via marge + TVA
            cat = produit["categorie"] or "AUTRE"
            marge_taux = marges_by_tenant[tid].get(cat) \
                or marges_by_tenant[tid].get("AUTRE") \
                or _DEFAULT_MARGE_CENTIEME
            tva_centieme = produit["taux_tva"] or _DEFAULT_TVA_CENTIEME
            prix_ht = int(prix_achat_cts * (1 + marge_taux / 10000))
            prix_vente_cts = int(prix_ht * (1 + tva_centieme / 10000))

            # Check existance (dedup par produit_id + etl_import_id)
            existing = conn.execute(text(
                "SELECT 1 FROM epicerie_prix_historique "
                "WHERE tenant_id = :tid AND produit_id = :pid AND etl_import_id = :eid LIMIT 1"
            ), {"tid": tid, "pid": pid, "eid": eid}).first()
            if existing:
                stats["already_present"] += 1
                continue

            if args.apply:
                conn.execute(text(
                    "INSERT INTO epicerie_prix_historique "
                    "  (tenant_id, produit_id, prix_achat_cts, prix_vente_cts, "
                    "   taux_marge_centieme, source, source_fournisseur, etl_import_id, "
                    "   reference, effective_date) "
                    "VALUES (:tid, :pid, :achat, :vente, :marge, 'etl', :vendor, :eid, :ref, :eff)"
                ), {
                    "tid": tid, "pid": pid, "achat": prix_achat_cts, "vente": prix_vente_cts,
                    "marge": marge_taux, "vendor": imp["vendor_code"], "eid": eid,
                    "ref": imp["numero_facture"] or f"ETL #{eid}",
                    "eff": eff_date,
                })
            stats["inserted"] += 1

        if not args.apply:
            conn.rollback()

    print()
    print("=" * 60)
    print("RESULTATS")
    print("=" * 60)
    for k, v in stats.items():
        print(f"  {k:30s} {v}")
    if not args.apply:
        print("\n[DRY-RUN] — relance avec --apply")


if __name__ == "__main__":
    main()
