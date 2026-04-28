"""Importer le catalogue EUROCIEL depuis le JSON source dans catalogue_produits.

Source : JSON extrait du catalogue PDF EUROCIEL (147 produits poissons/viandes/légumes).
Pas d'EAN dans EUROCIEL (produits référencés par code fournisseur interne).

KNOWN LIMITATION (EUROCIEL-PRIX-NULL-01, audit 2026-04-23) :
    Le JSON source n'a pas de champ prix (simple liste de produits du catalogue
    fournisseur). Résultat : les 146 produits EUROCIEL en base ont
    prix_unitaire_cts=NULL tant qu'aucun rapprochement catalogue↔facture n'est
    implémenté. Les factures EUROCIEL importées via eurociel_bulk_integrate.py
    portent les prix dans etl_imports.lignes_data mais ne remontent pas vers
    catalogue_produits.prix_unitaire_cts (match fuzzy par désignation non
    implémenté — les désignations facture ajoutent poids/tailles/promos et
    ne matchent pas les désignations catalogue courtes).

    Fix structurel à prévoir : dans app/services/epicerie/reception_etl.py,
    ajouter un update de CatalogueProduit.prix_unitaire_cts par match fuzzy
    (Jaro-Winkler >= 0.85) lors de la validation facture EUROCIEL.

Usage :
    docker exec -w /app futurproj_api bash -c 'PYTHONPATH=/app python scripts/import_eurociel_catalog.py /tmp/eurociel_catalogue.json'
"""
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import and_, select

from app.core.database import AsyncSessionLocal
from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.repositories.catalogue.catalogue_produit import AsyncCatalogueProduitRepository
from app.services.catalogue.etl_deduplication import normalize_designation

_CAT_MAP = {
    "POISSONS ENTIERS & GV": "FROID_POIS",
    "DARNES DE POISSON": "FROID_POIS",
    "FUMÉS": "FROID_POIS",
    "VOLAILLES / VIANDES": "FROID_VIAN",
    "CREVETTES / CRUSTACES": "FROID_POIS",
    "LÉGUMES": "SURG_LEGUME",
    "LÉGUMES / RIZ": "SURG_LEGUME",
    "NOURRITURE PREPAREE": "SURG_VIANDE",
    "Emballages / Jetables": "NON_ALI_DROGUERIE",
    "Épicerie sucrée": "ALI_EPICERIE",
}


async def main(json_path: str) -> None:
    data = json.loads(Path(json_path).read_text())
    produits = data.get("produits", [])
    print(f"→ Import de {len(produits)} produits EUROCIEL")

    async with AsyncSessionLocal() as db:
        repo = AsyncCatalogueProduitRepository(db)
        created = 0
        skipped = 0

        for p in produits:
            designation_base = p.get("designation") or ""
            taille = p.get("taille") or ""
            cond = p.get("conditionnement") or ""
            origine = p.get("origine") or ""
            cat_source = p.get("categorie", "")

            if not designation_base:
                continue

            parts = [designation_base]
            if taille:
                parts.append(taille)
            if cond:
                parts.append(cond)
            if origine:
                parts.append(f"({origine})")
            designation = " ".join(parts)
            desig_norm = normalize_designation(designation)

            r = await db.execute(
                select(CatalogueProduit).where(
                    and_(
                        CatalogueProduit.source_fournisseur == "EUROCIEL",
                        CatalogueProduit.designation_norm == desig_norm,
                    )
                ).limit(1)
            )
            if r.scalar_one_or_none() is not None:
                skipped += 1
                continue

            prod = CatalogueProduit(
                designation=designation,
                designation_norm=desig_norm,
                source_fournisseur="EUROCIEL",
                ean=None,
                marque=None,
                unite_base="kg",
                categorie_code=_CAT_MAP.get(cat_source, "AUTRE"),
                conditionnement=cond or None,
            )
            await repo.create(prod)
            created += 1

        await db.commit()
        print(f"  Créés : {created}")
        print(f"  Sautés (existants) : {skipped}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/eurociel_catalogue.json"
    asyncio.run(main(path))
