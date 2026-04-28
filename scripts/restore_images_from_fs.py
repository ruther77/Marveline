"""One-shot : restaure epicerie_produits.image_url pour les produits dont le
fichier .jpg existe déjà sur disque (cas de régression DB où la colonne a été
vidée mais les fichiers persistent).

Exécution : docker exec futurproj_api python scripts/restore_images_from_fs.py
"""
import os
from sqlalchemy import create_engine, text
from app.core.config import settings

IMG_DIR = "/app/uploads/products/epicerie"
TENANT_ID = 2


def main() -> int:
    files = [f for f in os.listdir(IMG_DIR) if f.endswith(".jpg")]
    ids = [int(f[:-4]) for f in files if f[:-4].isdigit()]
    print(f"Filesystem: {len(ids)} image files found")
    engine = create_engine(str(settings.DATABASE_URL))
    with engine.begin() as conn:
        res = conn.execute(
            text(
                "UPDATE epicerie_produits "
                "SET image_url = 'products/epicerie/' || id || '.jpg', updated_at=NOW() "
                "WHERE id = ANY(:ids) AND tenant_id = :tid AND image_url IS NULL"
            ),
            {"ids": ids, "tid": TENANT_ID},
        )
        print(f"Restored image_url on {res.rowcount} products")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
