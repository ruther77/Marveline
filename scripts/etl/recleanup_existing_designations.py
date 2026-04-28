"""One-shot : applique _cleanup_designation_final sur toutes les
epicerie_produits.designation_clean existantes.

Contexte : le sync n'update la désignation que sur upsert par EAN. Les
produits sans EAN (majorité TAIYAT/ETHAN) conservent leur ancienne désignation
même si les règles de nettoyage ont évolué. Ce script rattrape ces cas.

Exécution :
    docker compose exec -T -e PYTHONPATH=/app api \\
        python scripts/etl/recleanup_existing_designations.py [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import settings
from app.models.epicerie.produit import EpicerieProduit
from scripts.etl.sync_catalogue_to_epicerie import _cleanup_designation_final

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("recleanup")

TENANT_ID = 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    engine = create_engine(str(settings.DATABASE_URL))
    Session = sessionmaker(bind=engine)

    with Session() as db:
        rows = db.execute(
            select(EpicerieProduit.id, EpicerieProduit.designation_clean)
            .where(EpicerieProduit.tenant_id == TENANT_ID)
        ).all()

        logger.info("Lecture de %d produits tenant=%d", len(rows), TENANT_ID)
        changed = 0
        samples: list[tuple[int, str, str]] = []
        for pid, orig in rows:
            new = _cleanup_designation_final(orig or "")
            if new and new != orig:
                changed += 1
                if len(samples) < 15:
                    samples.append((pid, orig, new))
                if not args.dry_run:
                    db.execute(
                        update(EpicerieProduit)
                        .where(
                            EpicerieProduit.id == pid,
                            EpicerieProduit.tenant_id == TENANT_ID,
                        )
                        .values(designation_clean=new)
                    )

        if not args.dry_run:
            db.commit()

        logger.info(
            "%s %d/%d produits modifiés",
            "DRY-RUN" if args.dry_run else "COMMIT",
            changed, len(rows),
        )
        for pid, old, new in samples:
            logger.info("  [%d] %r -> %r", pid, old, new)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
