"""Met à jour les descriptions des produits sans description (Marveline).

Usage :
    docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm \
        --entrypoint "" api python scripts/update_product_descriptions.py [--tenant-id 1] [--dry-run]

Génère une description courte basée sur le nom + la catégorie du produit.
N'écrase jamais une description existante.
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.product import Product

TENANT_ID = 1

# Textes d'introduction par catégorie (location vaisselle / matériel événementiel)
CATEGORY_INTRO = {
    "verres": "Verre à louer pour vos événements.",
    "assiettes": "Assiette à louer pour vos repas et réceptions.",
    "couverts": "Couvert à louer pour vos tables de réception.",
    "vaisselle_service": "Ustensile de service à louer pour vos buffets et réceptions.",
    "porcelaine": "Pièce en porcelaine à louer pour un dressage élégant.",
    "vaisselle_enfants": "Vaisselle adaptée aux enfants, disponible à la location.",
    "nappes": "Nappe à louer pour habiller vos tables de réception.",
    "serviettes": "Serviette de table à louer pour compléter votre décoration.",
    "housses": "Housse à louer pour habiller vos chaises et sièges.",
    "tables": "Table à louer pour vos événements et réceptions.",
    "chaises": "Chaise à louer pour vos événements et réceptions.",
    "bancs": "Banc à louer pour vos événements en plein air ou en salle.",
    "mange_debout": "Mange-debout à louer pour vos cocktails et réceptions debout.",
    "machines": "Équipement à louer pour vos événements et prestations traiteur.",
    "decorations": "Élément de décoration à louer pour personnaliser vos événements.",
    "candy_bar": "Accessoire candy bar à louer pour vos fêtes et célébrations.",
    "accessoires_transport": "Accessoire de transport à louer pour faciliter la logistique de votre événement.",
}

DEFAULT_INTRO = "Article à louer pour vos événements et réceptions."


def build_description(product: Product) -> str:
    """Construit une description courte à partir du nom et de la catégorie."""
    intro = CATEGORY_INTRO.get(product.category or "", DEFAULT_INTRO)
    name = product.name.strip()
    # Format : "<Intro> Modèle : <Nom du produit>."
    return f"{intro} Modèle\u00a0: {name}."


def update_descriptions(tenant_id: int, dry_run: bool = False) -> None:
    db = SessionLocal()
    try:
        products = (
            db.query(Product)
            .filter(Product.tenant_id == tenant_id, Product.description == None)
            .order_by(Product.id)
            .all()
        )
        print(f"Produits sans description : {len(products)}")

        updated = 0
        for product in products:
            desc = build_description(product)
            if not dry_run:
                product.description = desc
            updated += 1
            print(f"  UPDATE [{product.id}] {product.name!r} → {desc[:60]}…")

        if not dry_run:
            db.commit()
            print(f"\nMise à jour terminée : {updated} produits mis à jour.")
        else:
            db.rollback()
            print(f"\nDRY RUN : {updated} produits seraient mis à jour.")

    except Exception as exc:
        db.rollback()
        print(f"ERREUR : {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Met à jour les descriptions produits Marveline")
    parser.add_argument("--tenant-id", type=int, default=TENANT_ID)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Mise à jour descriptions produits pour tenant {args.tenant_id}...")
    update_descriptions(args.tenant_id, args.dry_run)
