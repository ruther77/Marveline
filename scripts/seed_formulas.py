"""Seed des formules Marveline (données réelles scrapées sur marveline.fr).

Usage :
    docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm \
        --entrypoint "" api python scripts/seed_formulas.py [--tenant-id 1]

Données source : marveline.fr — formules classiques et vin d'honneur (relevé 2026-02-23).
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.formula import Formula, FormulaItem

TENANT_ID = 1

# ── Formules classiques (prix TTC/pers) ───────────────────────────────────────
# Source : marveline.fr/formules — 7 formules par tranche de convives
FORMULAS_CLASSIC = [
    {
        "slug": "formule-tout-petits",
        "name": "Formule Tout-Petits",
        "description": "Pour les plus petits convives. 1,20€ TTC par personne.",
        "formula_type": "classic",
        "price_per_person_cents": 120,  # 1,20€
        "sort_order": 1,
    },
    {
        "slug": "formule-enfant-6-pieces",
        "name": "Formule Enfant – 6 pièces",
        "description": "Formule enfant 6 pièces. 1,71€ TTC par personne.",
        "formula_type": "classic",
        "price_per_person_cents": 171,  # 1,71€
        "sort_order": 2,
    },
    {
        "slug": "formule-8-pieces",
        "name": "Formule 8 pièces",
        "description": "Formule standard 8 pièces : 3 verres, 2 assiettes, 3 couverts. 2,26€ TTC par personne.",
        "formula_type": "classic",
        "price_per_person_cents": 226,  # 2,26€
        "featured": True,
        "sort_order": 3,
    },
    {
        "slug": "formule-12-pieces",
        "name": "Formule 12 pièces",
        "description": "Formule complète 12 pièces. 3,29€ TTC par personne.",
        "formula_type": "classic",
        "price_per_person_cents": 329,  # 3,29€
        "sort_order": 4,
    },
    {
        "slug": "formule-15-pieces",
        "name": "Formule 15 pièces",
        "description": "Formule premium 15 pièces. 4,08€ TTC par personne.",
        "formula_type": "classic",
        "price_per_person_cents": 408,  # 4,08€
        "sort_order": 5,
    },
    {
        "slug": "formule-17-pieces",
        "name": "Formule 17 pièces",
        "description": "Formule luxe 17 pièces. 4,59€ TTC par personne.",
        "formula_type": "classic",
        "price_per_person_cents": 459,  # 4,59€
        "sort_order": 6,
    },
    {
        "slug": "formule-20-pieces",
        "name": "Formule 20 pièces",
        "description": "Formule prestige 20 pièces. 5,35€ TTC par personne.",
        "formula_type": "classic",
        "price_per_person_cents": 535,  # 5,35€
        "featured": True,
        "sort_order": 7,
    },
]

# ── Formules vin d'honneur (prix total par tranche de convives) ───────────────
# Source : marveline.fr/formules-vin-honneur
# Prix total : 50conv=39€, 100=78€, 150=117€, 200=140€, 250=180€, 300=216€
# Ramené en prix/pers pour cohérence (arrondi centimes)
FORMULAS_VIN_HONNEUR = [
    {
        "slug": "vin-honneur-50",
        "name": "Vin d'Honneur – 50 convives",
        "description": "Formule vin d'honneur pour 50 personnes. 39€ TTC total (0,78€/pers).",
        "formula_type": "vin_honneur",
        "price_per_person_cents": 78,  # 39€ / 50 = 0,78€
        "sort_order": 10,
    },
    {
        "slug": "vin-honneur-100",
        "name": "Vin d'Honneur – 100 convives",
        "description": "Formule vin d'honneur pour 100 personnes. 78€ TTC total (0,78€/pers).",
        "formula_type": "vin_honneur",
        "price_per_person_cents": 78,  # 78€ / 100
        "sort_order": 11,
    },
    {
        "slug": "vin-honneur-150",
        "name": "Vin d'Honneur – 150 convives",
        "description": "Formule vin d'honneur pour 150 personnes. 117€ TTC total (0,78€/pers).",
        "formula_type": "vin_honneur",
        "price_per_person_cents": 78,  # 117€ / 150
        "sort_order": 12,
    },
    {
        "slug": "vin-honneur-200",
        "name": "Vin d'Honneur – 200 convives",
        "description": "Formule vin d'honneur pour 200 personnes. 140€ TTC total (0,70€/pers).",
        "formula_type": "vin_honneur",
        "price_per_person_cents": 70,  # 140€ / 200
        "sort_order": 13,
    },
    {
        "slug": "vin-honneur-250",
        "name": "Vin d'Honneur – 250 convives",
        "description": "Formule vin d'honneur pour 250 personnes. 180€ TTC total (0,72€/pers).",
        "formula_type": "vin_honneur",
        "price_per_person_cents": 72,  # 180€ / 250
        "sort_order": 14,
    },
    {
        "slug": "vin-honneur-300",
        "name": "Vin d'Honneur – 300 convives",
        "description": "Formule vin d'honneur pour 300 personnes. 216€ TTC total (0,72€/pers).",
        "formula_type": "vin_honneur",
        "price_per_person_cents": 72,  # 216€ / 300
        "sort_order": 15,
    },
]

ALL_FORMULAS = FORMULAS_CLASSIC + FORMULAS_VIN_HONNEUR


def seed_formulas(tenant_id: int, dry_run: bool = False) -> None:
    db = SessionLocal()
    try:
        created = 0
        skipped = 0

        for data in ALL_FORMULAS:
            slug = data["slug"]
            existing = (
                db.query(Formula)
                .filter(Formula.slug == slug, Formula.tenant_id == tenant_id)
                .first()
            )
            if existing:
                print(f"  SKIP  {slug} (existe déjà)")
                skipped += 1
                continue

            formula = Formula(
                tenant_id=tenant_id,
                slug=slug,
                name=data["name"],
                description=data.get("description"),
                formula_type=data["formula_type"],
                price_per_person_cents=data["price_per_person_cents"],
                featured=data.get("featured", False),
                sort_order=data.get("sort_order", 0),
            )
            db.add(formula)
            created += 1
            print(f"  CREATE {slug} — {data['price_per_person_cents']}cts/pers")

        if not dry_run:
            db.commit()
            print(f"\nSeed terminé : {created} formules créées, {skipped} ignorées.")
        else:
            db.rollback()
            print(f"\nDRY RUN : {created} formules seraient créées, {skipped} ignorées.")

    except Exception as exc:
        db.rollback()
        print(f"ERREUR : {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed formules Marveline")
    parser.add_argument("--tenant-id", type=int, default=TENANT_ID)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Seeding formules pour tenant {args.tenant_id}...")
    seed_formulas(args.tenant_id, args.dry_run)
