"""One-shot : fetch images pour les produits épicerie sans photo.

Exécution : docker exec futurproj_api python scripts/backfill_epicerie_images.py
"""
import logging
import sys
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.epicerie.produit import EpicerieProduit
from app.services.epicerie.image_fetcher import fetch_product_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill_images")

TENANT_ID = 2
BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 500


def main() -> int:
    raw = str(settings.DATABASE_URL)
    if "+asyncpg" in raw:
        sync_url = raw.replace("+asyncpg", "+psycopg2")
    elif "+psycopg2" in raw:
        sync_url = raw
    elif "+psycopg" in raw:
        sync_url = raw.replace("+psycopg", "+psycopg2")
    else:
        sync_url = raw.replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(sync_url)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        rows = db.execute(
            select(EpicerieProduit.id, EpicerieProduit.ean, EpicerieProduit.designation_clean)
            .where(
                EpicerieProduit.tenant_id == TENANT_ID,
                EpicerieProduit.actif.is_(True),
                EpicerieProduit.image_url.is_(None),
            )
            .limit(BATCH)
        ).all()

        logger.info("Backfill: %d produits à traiter (tenant=%d)", len(rows), TENANT_ID)
        ok = 0
        for i, (pid, ean, designation) in enumerate(rows, 1):
            try:
                path = fetch_product_image(
                    product_id=pid, ean=ean, designation=designation or "", marque=None,
                )
            except Exception as exc:
                logger.warning("pid=%s crash: %s", pid, exc)
                path = None
            if path:
                db.execute(
                    update(EpicerieProduit)
                    .where(EpicerieProduit.id == pid, EpicerieProduit.tenant_id == TENANT_ID)
                    .values(image_url=path)
                )
                ok += 1
            if i % 25 == 0:
                db.commit()
                logger.info("Progress %d/%d — found %d", i, len(rows), ok)
        db.commit()
        logger.info("DONE — %d/%d produits avec nouvelle image (%.1f%%)",
                    ok, len(rows), 100.0 * ok / max(len(rows), 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
