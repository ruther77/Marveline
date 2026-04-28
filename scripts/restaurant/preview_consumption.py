"""Preview de la consommation reconstituée à partir des ventes SumUp + recettes.

Pour chaque variante vendue, on additionne :
  - Protéine : variante.quantite_proteine × qte_vendue
  - Base : pour chaque recette de son type_preparation,
           (recette.quantite_par_batch / type_prep.portions_par_batch) × qte_vendue

Sortie :
  - Total par ingrédient sur la période
  - Variantes sans recette (ni proteine ni type_prep) → conso non comptabilisée
  - Total transferts hebdo théoriques (par mapping facteur_conv vers épicerie)

Usage :
    docker exec -w /app futurproj_api python3 \\
        scripts/restaurant/preview_consumption.py
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from decimal import Decimal

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text


_TENANT_RESTO = 3


def main() -> None:
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        # 1. Recettes par type_preparation (qte par portion = qte_par_batch / portions_par_batch)
        recettes_rows = conn.execute(text(
            "SELECT r.type_preparation_id, r.ingredient_id, r.quantite_par_batch, "
            "       tp.portions_par_batch "
            "FROM restaurant_recettes_type_preparation r "
            "JOIN restaurant_types_preparation tp ON tp.id = r.type_preparation_id "
            "WHERE r.tenant_id = :t"
        ), {"t": _TENANT_RESTO}).fetchall()
        # type_prep_id → list[(ingredient_id, qte_par_portion)]
        recettes: dict[int, list[tuple[int, Decimal]]] = defaultdict(list)
        for tp_id, ingr_id, qte_batch, portions in recettes_rows:
            qte_portion = Decimal(qte_batch) / Decimal(portions)
            recettes[tp_id].append((ingr_id, qte_portion))

        # 2. Variantes (proteine + type_prep)
        variants = {
            v[0]: (v[1], v[2], v[3], v[4])
            for v in conn.execute(text(
                "SELECT id, nom, type_preparation_id, ingredient_proteine_id, "
                "       quantite_proteine "
                "FROM restaurant_variantes_plat WHERE tenant_id = :t"
            ), {"t": _TENANT_RESTO}).fetchall()
        }

        # 3. Lignes vendues + dates
        lignes = conn.execute(text(
            "SELECT lc.variante_id, lc.quantite, c.date_ouverture::date AS d "
            "FROM restaurant_lignes_commande lc "
            "JOIN restaurant_commandes c ON c.id = lc.commande_id "
            "WHERE c.sumup_order_id IS NOT NULL "
            "ORDER BY c.date_ouverture"
        )).fetchall()

        # 4. Ingrédients (nom + unité)
        ingr_meta = {
            r[0]: (r[1], r[2])
            for r in conn.execute(text(
                "SELECT id, nom, unite_stock FROM restaurant_ingredients "
                "WHERE tenant_id = :t"
            ), {"t": _TENANT_RESTO}).fetchall()
        }

        # 5. Mappings ingr → epicerie (ordre 0 = principal)
        mappings = {}
        for r in conn.execute(text(
            "SELECT DISTINCT ON (ingredient_id) ingredient_id, produit_id, facteur_conv "
            "FROM restaurant_ingredient_epicerie_mappings "
            "WHERE tenant_id = :t "
            "ORDER BY ingredient_id, ordre, id"
        ), {"t": _TENANT_RESTO}).fetchall():
            mappings[r[0]] = (r[1], Decimal(r[2]))

    # 6. Aggregate
    conso_total: dict[int, Decimal] = defaultdict(lambda: Decimal(0))
    conso_par_jour: dict[tuple[int, str], Decimal] = defaultdict(lambda: Decimal(0))
    sans_recette_qte = 0
    sans_recette_variants: dict[str, int] = defaultdict(int)
    lignes_total = 0
    min_d = max_d = None

    for variante_id, qte, d in lignes:
        lignes_total += 1
        if min_d is None or d < min_d:
            min_d = d
        if max_d is None or d > max_d:
            max_d = d
        v = variants.get(variante_id)
        if not v:
            continue
        nom, tp_id, prot_id, qte_prot = v

        a_recette = False
        # Proteine
        if prot_id and qte_prot:
            consume = Decimal(qte_prot) * Decimal(qte)
            conso_total[prot_id] += consume
            conso_par_jour[(prot_id, str(d))] += consume
            a_recette = True
        # Type prep recette
        if tp_id and tp_id in recettes:
            for ingr_id, qte_portion in recettes[tp_id]:
                consume = qte_portion * Decimal(qte)
                conso_total[ingr_id] += consume
                conso_par_jour[(ingr_id, str(d))] += consume
                a_recette = True
        if not a_recette:
            sans_recette_qte += qte
            sans_recette_variants[nom] += qte

    # 7. Output
    print(f"\nPériode : {min_d} → {max_d}")
    print(f"Lignes commande : {lignes_total}")
    print(f"Lignes sans recette : {sans_recette_qte} (top variantes ci-dessous)")
    print()
    print("=" * 80)
    print(f"  CONSO PAR INGREDIENT (top 30 par volume)")
    print("=" * 80)
    print(f"  {'Ingrédient':40s} {'Unité':10s} {'Total':>15s}  {'Mapping':>10s}")
    print("-" * 80)
    sorted_conso = sorted(conso_total.items(), key=lambda x: -x[1])
    for ingr_id, total in sorted_conso[:30]:
        nom, unite = ingr_meta.get(ingr_id, ("?", "?"))
        mapped = "OK" if ingr_id in mappings else "AUCUN"
        print(f"  {nom[:40]:40s} {unite[:10]:10s} {float(total):>15.2f}  {mapped:>10s}")

    print()
    print(f"Total ingrédients consommés     : {len(conso_total)}")
    print(f"  dont mappés vers épicerie    : {sum(1 for i in conso_total if i in mappings)}")
    print(f"  dont sans mapping            : {sum(1 for i in conso_total if i not in mappings)}")

    print()
    print("=" * 80)
    print(f"  TOP 15 VARIANTES VENDUES SANS RECETTE")
    print("=" * 80)
    for nom, qte in sorted(sans_recette_variants.items(), key=lambda x: -x[1])[:15]:
        print(f"  {nom[:50]:50s} {qte:>6d} ventes")

    # 8. Stats mouvements à générer
    nb_mvts_resto = len({(i, d) for (i, d) in conso_par_jour.keys()})
    nb_semaines = (max_d - min_d).days // 7 + 1 if min_d else 0
    nb_ingr_uniques = len(conso_total)
    nb_transferts_estim = nb_semaines * sum(1 for i in conso_total if i in mappings)
    print()
    print("=" * 80)
    print(f"  ESTIMATION VOLUME ÉCRITURE")
    print("=" * 80)
    print(f"  Mouvements conso quotidiens resto : {nb_mvts_resto}")
    print(f"  Semaines couvertes                : {nb_semaines}")
    print(f"  Transferts hebdo épicerie→resto   : {nb_transferts_estim} (max théorique)")
    print(f"  Mouvements épicerie               : ~{nb_transferts_estim} sorties")


if __name__ == "__main__":
    main()
