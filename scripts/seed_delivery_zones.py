"""Seed des zones de livraison Marveline (données scrapées sur marveline.fr).

Usage :
    docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm \
        --entrypoint "" api python scripts/seed_delivery_zones.py [--tenant-id 1]

Données source : marveline.fr/livraison — 7 départements (relevé 2026-02-23).
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.delivery_zone import DeliveryZone

TENANT_ID = 1

# Source : marveline.fr — zones de livraison confirmées
DELIVERY_ZONES = [
    {"name": "Oise (60)", "department_code": "60", "is_active": True},
    {"name": "Somme (80)", "department_code": "80", "is_active": True},
    {"name": "Aisne (02)", "department_code": "02", "is_active": True},
    {"name": "Val-d'Oise (95)", "department_code": "95", "is_active": True},
    {"name": "Seine-Maritime (76)", "department_code": "76", "is_active": True},
    {"name": "Eure (27)", "department_code": "27", "is_active": True},
    {"name": "Pas-de-Calais (62)", "department_code": "62", "is_active": True},
]


def seed_delivery_zones(tenant_id: int, dry_run: bool = False) -> None:
    db = SessionLocal()
    try:
        created = 0
        skipped = 0

        for data in DELIVERY_ZONES:
            dept = data["department_code"]
            existing = (
                db.query(DeliveryZone)
                .filter(
                    DeliveryZone.tenant_id == tenant_id,
                    DeliveryZone.department_code == dept,
                )
                .first()
            )
            if existing:
                print(f"  SKIP  {data['name']} (existe déjà)")
                skipped += 1
                continue

            zone = DeliveryZone(
                tenant_id=tenant_id,
                department_name=data["name"],
                department_code=dept,
                is_active=data["is_active"],
            )
            db.add(zone)
            created += 1
            print(f"  CREATE {data['name']}")

        if not dry_run:
            db.commit()
            print(f"\nSeed terminé : {created} zones créées, {skipped} ignorées.")
        else:
            db.rollback()
            print(f"\nDRY RUN : {created} zones seraient créées, {skipped} ignorées.")

    except Exception as exc:
        db.rollback()
        print(f"ERREUR : {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed zones de livraison Marveline")
    parser.add_argument("--tenant-id", type=int, default=TENANT_ID)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Seeding zones de livraison pour tenant {args.tenant_id}...")
    seed_delivery_zones(args.tenant_id, args.dry_run)
