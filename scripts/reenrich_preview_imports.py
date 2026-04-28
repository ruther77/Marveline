"""Pré-enrichissement en masse de tous les imports PREVIEW existants.

Raison d'être : après déploiement de l'enrichisseur universel (marque,
conditionnement, volume…) et du nouveau format de `similar_products`, les
imports PREVIEW créés avant le fix n'en profitent pas automatiquement. Plutôt
que de forcer l'opérateur à cliquer "Re-classer" sur chacun (UX : alléger
l'user), ce script applique la mise à jour en masse.

Logique (identique à l'endpoint `/reclassify` enrichi) :
  1. enrich_ligne_from_designation → marque, cond, volume, contenant, degré
  2. classify_categorie_code / classify_by_knn → catégorie si AUTRE
  3. compute_line_confidence → score mis à jour
  4. Régénère similar_products avec categorie_code, marque, cond, volume, prix

Idempotent : peut être rerun sans risque.

Usage :
    docker compose exec -T api python -m scripts.reenrich_preview_imports [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import AsyncSessionLocal as async_session_factory
from app.etl_types import LigneParsee
from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.models.catalogue.etl_import import EtlImport
from app.repositories.catalogue.catalogue_produit import (
    AsyncCatalogueProduitRepository,
)
from app.services.catalogue.etl_classification import (
    classify_by_knn, classify_categorie_code,
)
from app.services.catalogue.etl_deduplication import (
    build_idf_from_candidates, classify_designation_top_n,
    normalize_designation,
)
from app.services.catalogue.etl_designation_enrichment import (
    enrich_ligne_from_designation,
)
from app.services.catalogue.etl_import_service import compute_line_confidence


_ENRICH_FIELDS = ("marque", "conditionnement", "volume_unitaire_ml",
                  "contenant", "degre_alcool", "unite_base")


async def _reenrich_one(db, import_obj: EtlImport, produit_repo, labelled,
                         preview_candidates) -> dict[str, int]:
    lignes: list[dict[str, Any]] = list(import_obj.lignes_data or [])
    if not lignes:
        return {"lignes": 0, "enriched_fields": 0, "reclassified": 0, "similar_regen": 0}

    stats = {"lignes": len(lignes), "enriched_fields": 0, "reclassified": 0, "similar_regen": 0}

    for ligne in lignes:
        # 1. Enrichissement depuis désignation
        stub = LigneParsee(
            designation=ligne.get("designation", "") or "",
            unite_base=ligne.get("unite_base", "U") or "U",
            source_fournisseur=ligne.get("source_fournisseur", "") or "",
            ean=ligne.get("ean"),
            marque=ligne.get("marque"),
            conditionnement=ligne.get("conditionnement"),
            volume_unitaire_ml=ligne.get("volume_unitaire_ml"),
            contenant=ligne.get("contenant"),
            degre_alcool=ligne.get("degre_alcool"),
            categorie_code=ligne.get("categorie_code"),
        )
        try:
            enrich_ligne_from_designation(stub)
        except Exception:
            pass
        for field in _ENRICH_FIELDS:
            new = getattr(stub, field, None)
            if new and not ligne.get(field):
                ligne[field] = new
                stats["enriched_fields"] += 1

        # 2. Reclassification catégorie si AUTRE ou nulle
        cat = ligne.get("categorie_code")
        if not cat or cat == "AUTRE":
            desig = ligne.get("designation") or ligne.get("designation_raw") or ""
            if desig.strip():
                norm = normalize_designation(desig)
                new_cat = classify_categorie_code(norm)
                if new_cat == "AUTRE" and labelled:
                    knn_cat = classify_by_knn(norm, labelled, seuil=0.70)
                    if knn_cat != "AUTRE":
                        new_cat = knn_cat
                if new_cat and new_cat != "AUTRE" and new_cat != cat:
                    ligne["categorie_code"] = new_cat
                    stats["reclassified"] += 1

        # 3. Confidence recalc
        try:
            conf_stub = LigneParsee(
                designation=ligne.get("designation", "") or "",
                unite_base=ligne.get("unite_base", "U") or "U",
                source_fournisseur=ligne.get("source_fournisseur", "") or "",
                ean=ligne.get("ean"),
                marque=ligne.get("marque"),
                categorie_code=ligne.get("categorie_code"),
                quantite=ligne.get("quantite"),
                prix_unitaire_cts=ligne.get("prix_unitaire_cts"),
                montant_ht_cts=ligne.get("montant_ht_cts"),
            )
            ligne["confidence_score"] = compute_line_confidence(conf_stub)
        except Exception:
            pass

        # 4. Similar products enrichis
        if not ligne.get("ean") and preview_candidates:
            desig = ligne.get("designation") or ligne.get("designation_raw") or ""
            if desig.strip():
                top = classify_designation_top_n(
                    desig, preview_candidates, seuil=0.70, n=3,
                )
                if top:
                    enriched_similar = []
                    for t in top:
                        prod = await produit_repo.get_by_id(t["candidate_id"])
                        enriched_similar.append({
                            "candidate_id": t["candidate_id"],
                            "designation": prod.designation if prod else t["designation_norm"],
                            "ean": prod.ean if prod else None,
                            "categorie_code": prod.categorie_code if prod else None,
                            "marque": prod.marque if prod else None,
                            "conditionnement": prod.conditionnement if prod else None,
                            "volume_unitaire_ml": getattr(prod, "volume_unitaire_ml", None) if prod else None,
                            "prix_unitaire_cts": prod.prix_unitaire_cts if prod else None,
                            "taux_tva_centieme": getattr(prod, "taux_tva_centieme", None) if prod else None,
                            "score": t["score"],
                        })
                    ligne["similar_products"] = enriched_similar
                    stats["similar_regen"] += 1

    # SQLAlchemy ne détecte pas les mutations in-place sur JSONB. Réassigner
    # une nouvelle liste + flag_modified pour forcer le UPDATE.
    import_obj.lignes_data = list(lignes)
    flag_modified(import_obj, "lignes_data")
    return stats


async def run(dry_run: bool = False) -> None:
    async with async_session_factory() as db:
        stmt = select(EtlImport).where(EtlImport.statut.in_(["PREVIEW", "PARTIEL"]))
        imports = list((await db.execute(stmt)).scalars())
        print(f"→ {len(imports)} imports PREVIEW à ré-enrichir")

        if not imports:
            return

        produit_repo = AsyncCatalogueProduitRepository(db)

        # Corpus labellisé (pour classify_by_knn)
        labelled_q = await db.execute(
            select(CatalogueProduit.designation_norm, CatalogueProduit.categorie_code).where(
                and_(
                    CatalogueProduit.categorie_code.isnot(None),
                    CatalogueProduit.categorie_code != "AUTRE",
                    CatalogueProduit.designation_norm.isnot(None),
                )
            )
        )
        labelled = [(r[0], r[1]) for r in labelled_q.all()]
        print(f"→ {len(labelled)} produits labellisés dans le corpus KNN")

        # Candidats pour similar_products
        preview_candidates = await produit_repo.get_all_candidates()
        if preview_candidates:
            build_idf_from_candidates(preview_candidates)
        print(f"→ {len(preview_candidates)} produits candidats pour similar_products")

        totals = {"lignes": 0, "enriched_fields": 0, "reclassified": 0, "similar_regen": 0}
        for i, imp in enumerate(imports, 1):
            stats = await _reenrich_one(db, imp, produit_repo, labelled, preview_candidates)
            for k, v in stats.items():
                totals[k] += v
            if i % 20 == 0:
                print(f"  ... {i}/{len(imports)} imports traités")

        print(
            f"→ Total : {totals['lignes']} lignes | "
            f"+{totals['enriched_fields']} champs enrichis | "
            f"{totals['reclassified']} reclassifiées | "
            f"{totals['similar_regen']} similar_products régénérés"
        )

        if dry_run:
            await db.rollback()
            print("(DRY-RUN : aucune écriture DB)")
            return

        await db.commit()
        print("✓ Imports PREVIEW mis à jour")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(run(dry_run=args.dry_run))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
