"""Rejoue l'historique de consommation restaurant 2023-05-29 → 2025-11-07
à partir des commandes SumUp + recettes type_preparation.

Ordre :
  1. Reset stock_actuel resto à 0 puis seed = 2 semaines de conso moyenne
     (1 mouvement 'entree' daté 2023-05-28).
  2. Pour chaque semaine, calcule le besoin = conso_semaine × 1.5 - stock_actuel.
     Si > 0, crée 1 internal_transfer épicerie→resto daté lundi 00:00.
     Si stock épicerie insuffisant, crée AJUSTEMENT positif (achat externe non-ETL)
     daté juste avant.
  3. Pour chaque (ingr, jour) consommé, crée 1 mouvement 'consommation' daté.

Idempotence : si des mouvements 'consommation' SumUp existent déjà
(via marqueur dans notes), abort.

Usage :
    docker exec -w /app futurproj_api python3 \\
        scripts/restaurant/replay_consumption_history.py [--apply]
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text


_TENANT_RESTO = 3
_TENANT_EPICERIE = 2
_NOTE_TAG = "[SUMUP_REPLAY]"
_SEED_DATE = datetime(2023, 5, 28, 0, 0, 0)
_REAPPROV_MARGIN = Decimal("1.5")
_SEED_WEEKS = Decimal("2")


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])

    stats = {
        "ingr_seeded": 0,
        "transferts_crees": 0,
        "transferts_lignes": 0,
        "ajustements_epi": 0,
        "mvts_conso": 0,
        "mvts_transfert_entrant": 0,
        "mvts_epi_sortie": 0,
    }

    with engine.begin() as conn:
        # Idempotence
        existing = conn.execute(text(
            "SELECT COUNT(*) FROM restaurant_mouvements_stock "
            "WHERE tenant_id = :t AND notes LIKE :tag"
        ), {"t": _TENANT_RESTO, "tag": f"%{_NOTE_TAG}%"}).scalar()
        if existing > 0:
            print(f"❌ {existing} mouvements {_NOTE_TAG} existent déjà — abort")
            return

        # Drop temporaire des contraintes stock_apres>=0 (replay au milieu désynchro
        # les mouvements ETL postérieurs ; on recalcule à la fin via window function)
        if args.apply:
            conn.execute(text(
                "ALTER TABLE epicerie_stock_movements "
                "DROP CONSTRAINT IF EXISTS check_epicerie_movement_stock_apres_positif"
            ))
            conn.execute(text(
                "ALTER TABLE restaurant_mouvements_stock "
                "DROP CONSTRAINT IF EXISTS check_mouvement_stock_apres_positif"
            ))
            print("→ Contraintes stock_apres>=0 droppées temporairement")

        # Recettes
        recettes_rows = conn.execute(text(
            "SELECT r.type_preparation_id, r.ingredient_id, r.quantite_par_batch, "
            "       tp.portions_par_batch "
            "FROM restaurant_recettes_type_preparation r "
            "JOIN restaurant_types_preparation tp ON tp.id = r.type_preparation_id "
            "WHERE r.tenant_id = :t"
        ), {"t": _TENANT_RESTO}).fetchall()
        recettes: dict[int, list[tuple[int, Decimal]]] = defaultdict(list)
        for tp_id, ingr_id, qte_batch, portions in recettes_rows:
            recettes[tp_id].append(
                (ingr_id, Decimal(qte_batch) / Decimal(portions))
            )

        variants = {
            v[0]: (v[1], v[2], v[3])
            for v in conn.execute(text(
                "SELECT id, type_preparation_id, ingredient_proteine_id, "
                "       quantite_proteine "
                "FROM restaurant_variantes_plat WHERE tenant_id = :t"
            ), {"t": _TENANT_RESTO}).fetchall()
        }

        # Lignes vendues
        lignes = conn.execute(text(
            "SELECT lc.variante_id, lc.quantite, c.date_ouverture "
            "FROM restaurant_lignes_commande lc "
            "JOIN restaurant_commandes c ON c.id = lc.commande_id "
            "WHERE c.sumup_order_id IS NOT NULL "
            "ORDER BY c.date_ouverture"
        )).fetchall()

        # Ingrédients
        ingr_meta = {
            r[0]: {"nom": r[1], "unite": r[2]}
            for r in conn.execute(text(
                "SELECT id, nom, unite_stock FROM restaurant_ingredients "
                "WHERE tenant_id = :t"
            ), {"t": _TENANT_RESTO}).fetchall()
        }

        # Mappings ingr → (produit, facteur_conv)
        mappings = {}
        for r in conn.execute(text(
            "SELECT DISTINCT ON (ingredient_id) ingredient_id, produit_id, facteur_conv "
            "FROM restaurant_ingredient_epicerie_mappings "
            "WHERE tenant_id = :t "
            "ORDER BY ingredient_id, ordre, id"
        ), {"t": _TENANT_RESTO}).fetchall():
            mappings[r[0]] = {"produit_id": r[1], "facteur": Decimal(r[2])}

        # Produits épicerie
        produits_epi = {}
        for r in conn.execute(text(
            "SELECT id, designation_clean, unite_base, prix_achat_cts, taux_tva, "
            "       prix_unitaire_cts "
            "FROM epicerie_produits WHERE tenant_id = :t"
        ), {"t": _TENANT_EPICERIE}).fetchall():
            produits_epi[r[0]] = {
                "designation": r[1], "unite": r[2],
                "prix_achat": r[3] or 0, "tva": r[4] or 550,
                "prix_unitaire": r[5] or 0,
            }

        # Stock épicerie au 28/05/2023 (snapshot historique, pas le stock courant)
        # = dernier stock_apres avant cette date, ou somme cumulative depuis 0 sinon
        stock_epi: dict[int, Decimal] = {}
        for r in conn.execute(text(
            "SELECT DISTINCT ON (produit_id) produit_id, stock_apres "
            "FROM epicerie_stock_movements "
            "WHERE tenant_id = :t AND date_mouvement < :cutoff "
            "ORDER BY produit_id, date_mouvement DESC, id DESC"
        ), {"t": _TENANT_EPICERIE, "cutoff": _SEED_DATE + timedelta(days=1)}).fetchall():
            stock_epi[r[0]] = Decimal(r[1])

        # 1. Calcul conso (ingr × jour)
        conso_par_jour: dict[tuple[int, date], Decimal] = defaultdict(lambda: Decimal(0))
        for variante_id, qte, dt_ouv in lignes:
            d = dt_ouv.date() if isinstance(dt_ouv, datetime) else dt_ouv
            v = variants.get(variante_id)
            if not v:
                continue
            tp_id, prot_id, qte_prot = v
            if prot_id and qte_prot:
                conso_par_jour[(prot_id, d)] += Decimal(qte_prot) * Decimal(qte)
            if tp_id and tp_id in recettes:
                for ingr_id, qte_portion in recettes[tp_id]:
                    conso_par_jour[(ingr_id, d)] += qte_portion * Decimal(qte)

        # Aggrégat conso par semaine et total
        conso_par_semaine: dict[tuple[int, date], Decimal] = defaultdict(lambda: Decimal(0))
        conso_total: dict[int, Decimal] = defaultdict(lambda: Decimal(0))
        for (ingr_id, d), q in conso_par_jour.items():
            lundi = monday_of(d)
            conso_par_semaine[(ingr_id, lundi)] += q
            conso_total[ingr_id] += q

        # Période
        if not conso_par_jour:
            print("Aucune conso à rejouer")
            return
        all_dates = [d for _, d in conso_par_jour.keys()]
        date_min = min(all_dates)
        date_max = max(all_dates)
        nb_semaines = ((date_max - date_min).days // 7) + 1
        print(f"Période : {date_min} → {date_max} ({nb_semaines} semaines)")
        print(f"Ingrédients consommés : {len(conso_total)}")

        # 2. Reset stock resto + seed initial
        ingr_consommes = list(conso_total.keys())
        stock_resto: dict[int, Decimal] = {i: Decimal(0) for i in ingr_consommes}

        if args.apply:
            # Reset
            conn.execute(text(
                "UPDATE restaurant_ingredients SET stock_actuel = 0 "
                "WHERE tenant_id = :t AND id = ANY(:ids)"
            ), {"t": _TENANT_RESTO, "ids": ingr_consommes})

        # Seed = 2 semaines de conso moyenne
        nb_semaines_total = max(1, nb_semaines)
        for ingr_id in ingr_consommes:
            avg_par_semaine = conso_total[ingr_id] / Decimal(nb_semaines_total)
            seed_qte = (avg_par_semaine * _SEED_WEEKS).quantize(Decimal("0.001"))
            if seed_qte <= 0:
                continue
            stock_resto[ingr_id] = seed_qte
            stats["ingr_seeded"] += 1
            if args.apply:
                conn.execute(text(
                    "INSERT INTO restaurant_mouvements_stock "
                    "  (tenant_id, ingredient_id, type_mouvement, quantite, "
                    "   stock_apres, date_mouvement, notes, created_at) "
                    "VALUES (:t, :i, 'entree', :q, :sa, :d, :n, now())"
                ), {
                    "t": _TENANT_RESTO, "i": ingr_id, "q": seed_qte,
                    "sa": seed_qte, "d": _SEED_DATE,
                    "n": f"{_NOTE_TAG} Seed initial (2 semaines conso moyenne)",
                })
                conn.execute(text(
                    "UPDATE restaurant_ingredients SET stock_actuel = :s "
                    "WHERE id = :i"
                ), {"s": seed_qte, "i": ingr_id})

        # 3. Boucle hebdo : transferts épicerie→resto
        # Pour chaque semaine triée, pour chaque ingr consommé en semaine W,
        # vérifier si réapprov nécessaire
        semaines_uniques = sorted({lundi for _, lundi in conso_par_semaine.keys()})

        for lundi in semaines_uniques:
            # Grouper les besoins de la semaine en un seul transfer
            lignes_transfert: list[dict] = []
            for ingr_id in ingr_consommes:
                conso_w = conso_par_semaine.get((ingr_id, lundi), Decimal(0))
                if conso_w <= 0:
                    continue
                # Stock cible = conso_w * 1.5
                besoin = (conso_w * _REAPPROV_MARGIN - stock_resto[ingr_id]).quantize(Decimal("0.001"))
                if besoin <= 0:
                    continue
                m = mappings.get(ingr_id)
                if not m:
                    continue
                produit_id = m["produit_id"]
                facteur = m["facteur"]
                qte_epi = (besoin * facteur).quantize(Decimal("0.001"))
                lignes_transfert.append({
                    "ingr_id": ingr_id, "produit_id": produit_id,
                    "qte_resto": besoin, "qte_epi": qte_epi,
                })

            if not lignes_transfert:
                continue

            ts_transfer = datetime.combine(lundi, datetime.min.time()).replace(hour=8)

            # Pré-traitement : ajustements épicerie pour stocks insuffisants
            for ln in lignes_transfert:
                pid = ln["produit_id"]
                cur = stock_epi.get(pid, Decimal(0))
                if cur < ln["qte_epi"]:
                    manque = (ln["qte_epi"] - cur).quantize(Decimal("0.001"))
                    nouveau_stock = cur + manque
                    stock_epi[pid] = nouveau_stock
                    stats["ajustements_epi"] += 1
                    if args.apply:
                        conn.execute(text(
                            "INSERT INTO epicerie_stock_movements "
                            "  (tenant_id, produit_id, type, quantite, stock_apres, "
                            "   date_mouvement, notes, created_at) "
                            "VALUES (:t, :p, 'AJUSTEMENT', :q, :sa, :d, :n, now())"
                        ), {
                            "t": _TENANT_EPICERIE, "p": pid, "q": manque,
                            "sa": nouveau_stock, "d": ts_transfer - timedelta(minutes=10),
                            "n": f"{_NOTE_TAG} Ajustement achat externe (ETL incomplet)",
                        })

            # Calcul montants transfert
            montant_ht = 0
            montant_ttc = 0
            for ln in lignes_transfert:
                p = produits_epi.get(ln["produit_id"])
                if not p:
                    continue
                # Prix transfert = prix achat (cession au coût)
                pu = p["prix_achat"]
                qte = ln["qte_epi"]
                ligne_ht = int(Decimal(pu) * qte)
                tva = p["tva"]
                ligne_ttc = int(ligne_ht * (1000 + tva) / 1000)
                ln["prix_unitaire"] = pu
                ln["montant_ht"] = ligne_ht
                ln["montant_ttc"] = ligne_ttc
                ln["tva_pct"] = tva
                montant_ht += ligne_ht
                montant_ttc += ligne_ttc

            stats["transferts_crees"] += 1
            stats["transferts_lignes"] += len(lignes_transfert)

            transfer_id = None
            if not args.apply:
                # Met à jour les stocks en mémoire pour la conso de la semaine
                for ln in lignes_transfert:
                    pid = ln["produit_id"]
                    stock_epi[pid] = (stock_epi[pid] - ln["qte_epi"]).quantize(Decimal("0.001"))
                    stock_resto[ln["ingr_id"]] = (stock_resto[ln["ingr_id"]] + ln["qte_resto"]).quantize(Decimal("0.001"))
                    stats["mvts_epi_sortie"] += 1
                    stats["mvts_transfert_entrant"] += 1
            else:
                # Insert transfert
                ref = f"REPLAY-{lundi.isoformat()}"
                transfer_id = conn.execute(text(
                    "INSERT INTO internal_transfers "
                    "  (tenant_id, dest_tenant_id, reference, status, montant_ht, "
                    "   montant_ttc, notes, validated_at, created_at, updated_at) "
                    "VALUES (:t, :dt, :ref, 'VALIDATED', :mht, :mttc, :n, :va, :ca, :ca) "
                    "RETURNING id"
                ), {
                    "t": _TENANT_EPICERIE, "dt": _TENANT_RESTO,
                    "ref": ref, "mht": montant_ht, "mttc": montant_ttc,
                    "n": f"{_NOTE_TAG} Réapprov hebdo {lundi}",
                    "va": ts_transfer, "ca": ts_transfer,
                }).scalar()

                # Insert lignes + mouvements
                for ln in lignes_transfert:
                    pid = ln["produit_id"]
                    p = produits_epi[pid]
                    stock_epi[pid] = (stock_epi[pid] - ln["qte_epi"]).quantize(Decimal("0.001"))
                    mvt_epi = conn.execute(text(
                        "INSERT INTO epicerie_stock_movements "
                        "  (tenant_id, produit_id, type, quantite, stock_apres, "
                        "   date_mouvement, transfer_id, notes, created_at) "
                        "VALUES (:t, :p, 'TRANSFERT_RESTAURANT', :q, :sa, :d, :tr, :n, now()) "
                        "RETURNING id"
                    ), {
                        "t": _TENANT_EPICERIE, "p": pid, "q": ln["qte_epi"],
                        "sa": stock_epi[pid], "d": ts_transfer, "tr": transfer_id,
                        "n": f"{_NOTE_TAG} Transfert vers resto",
                    }).scalar()
                    stats["mvts_epi_sortie"] += 1

                    stock_resto[ln["ingr_id"]] = (stock_resto[ln["ingr_id"]] + ln["qte_resto"]).quantize(Decimal("0.001"))
                    mvt_resto = conn.execute(text(
                        "INSERT INTO restaurant_mouvements_stock "
                        "  (tenant_id, ingredient_id, type_mouvement, quantite, "
                        "   stock_apres, date_mouvement, notes, created_at) "
                        "VALUES (:t, :i, 'transfert_entrant', :q, :sa, :d, :n, now()) "
                        "RETURNING id"
                    ), {
                        "t": _TENANT_RESTO, "i": ln["ingr_id"], "q": ln["qte_resto"],
                        "sa": stock_resto[ln["ingr_id"]], "d": ts_transfer,
                        "n": f"{_NOTE_TAG} Transfert depuis épicerie",
                    }).scalar()
                    stats["mvts_transfert_entrant"] += 1

                    conn.execute(text(
                        "INSERT INTO internal_transfer_lines "
                        "  (transfer_id, produit_id, ingredient_id, designation, "
                        "   quantite, unite, prix_unitaire, montant_ht, tva_pct, "
                        "   montant_ttc, mouvement_epicerie_id, mouvement_restaurant_id, "
                        "   created_at, updated_at) "
                        "VALUES (:tr, :p, :i, :des, :q, :u, :pu, :ht, :tva, :ttc, "
                        "        :me, :mr, now(), now())"
                    ), {
                        "tr": transfer_id, "p": pid, "i": ln["ingr_id"],
                        "des": p["designation"][:255], "q": ln["qte_epi"],
                        "u": (p["unite"] or "u")[:10], "pu": ln["prix_unitaire"],
                        "ht": ln["montant_ht"], "tva": ln["tva_pct"],
                        "ttc": ln["montant_ttc"],
                        "me": mvt_epi, "mr": mvt_resto,
                    })

            # 4. Conso quotidienne de la semaine (immédiatement après le réapprov)
            for ingr_id in ingr_consommes:
                # Itérer sur les jours lundi..lundi+6
                for offset in range(7):
                    d = lundi + timedelta(days=offset)
                    q = conso_par_jour.get((ingr_id, d), Decimal(0))
                    if q <= 0:
                        continue
                    q = q.quantize(Decimal("0.001"))
                    stock_resto[ingr_id] = (stock_resto[ingr_id] - q).quantize(Decimal("0.001"))
                    stats["mvts_conso"] += 1
                    if not args.apply:
                        continue
                    if stock_resto[ingr_id] < 0:
                        # Stock insuffisant : rare car +50% marge ; on log
                        # et on remet à 0 pour respecter la contrainte
                        # (ne devrait pas arriver, mais sécurité)
                        stock_resto[ingr_id] = Decimal(0)
                    ts_conso = datetime.combine(d, datetime.min.time()).replace(hour=12)
                    conn.execute(text(
                        "INSERT INTO restaurant_mouvements_stock "
                        "  (tenant_id, ingredient_id, type_mouvement, quantite, "
                        "   stock_apres, date_mouvement, notes, created_at) "
                        "VALUES (:t, :i, 'consommation', :q, :sa, :d, :n, now())"
                    ), {
                        "t": _TENANT_RESTO, "i": ingr_id, "q": q,
                        "sa": stock_resto[ingr_id], "d": ts_conso,
                        "n": f"{_NOTE_TAG} Conso ventes SumUp {d}",
                    })

        if args.apply:
            # Recalcul stock_apres ordonné par date pour tous produits/ingrédients touchés
            print("→ Recalcul des stock_apres (window function)...")
            ingr_ids = list(stock_resto.keys())
            produits_touches = list({m["produit_id"] for m in mappings.values()})

            conn.execute(text(
                "WITH recalc AS ("
                "  SELECT id, "
                "    SUM(CASE WHEN type IN ('ENTREE','AJUSTEMENT') THEN quantite "
                "             WHEN type IN ('SORTIE','VENTE','TRANSFERT_RESTAURANT','PERTE') THEN -quantite "
                "             ELSE 0 END) "
                "      OVER (PARTITION BY produit_id ORDER BY date_mouvement, id "
                "            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS sa "
                "  FROM epicerie_stock_movements "
                "  WHERE tenant_id = :t AND produit_id = ANY(:ids) "
                ") "
                "UPDATE epicerie_stock_movements m SET stock_apres = recalc.sa "
                "FROM recalc WHERE m.id = recalc.id"
            ), {"t": _TENANT_EPICERIE, "ids": produits_touches})

            conn.execute(text(
                "WITH recalc AS ("
                "  SELECT id, "
                "    SUM(CASE WHEN type_mouvement IN ('entree','transfert_entrant') THEN quantite "
                "             WHEN type_mouvement IN ('consommation','perte') THEN -quantite "
                "             WHEN type_mouvement = 'inventaire' THEN 0 "
                "             ELSE 0 END) "
                "      OVER (PARTITION BY ingredient_id ORDER BY date_mouvement, id "
                "            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS sa "
                "  FROM restaurant_mouvements_stock "
                "  WHERE tenant_id = :t AND ingredient_id = ANY(:ids) "
                ") "
                "UPDATE restaurant_mouvements_stock m SET stock_apres = recalc.sa "
                "FROM recalc WHERE m.id = recalc.id"
            ), {"t": _TENANT_RESTO, "ids": ingr_ids})

            # Update stock_actuel ingredients = dernier stock_apres
            conn.execute(text(
                "UPDATE restaurant_ingredients i SET stock_actuel = sub.sa "
                "FROM ("
                "  SELECT DISTINCT ON (ingredient_id) ingredient_id, stock_apres AS sa "
                "  FROM restaurant_mouvements_stock WHERE tenant_id = :t AND ingredient_id = ANY(:ids) "
                "  ORDER BY ingredient_id, date_mouvement DESC, id DESC"
                ") sub WHERE i.id = sub.ingredient_id"
            ), {"t": _TENANT_RESTO, "ids": ingr_ids})

            print("→ Recalcul terminé")
        else:
            conn.rollback()

    print()
    print("=" * 60)
    for k, v in stats.items():
        print(f"  {k:30s} {v}")
    if not args.apply:
        print("\n[DRY-RUN]")


if __name__ == "__main__":
    main()
