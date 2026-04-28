"""Seed script — Peuple la base de données avec les données réelles Marveline.

Usage (Docker) :
    docker compose exec api python scripts/seed_data.py

Usage (local) :
    python3 scripts/seed_data.py

Données : catégories hiérarchiques, ~100 produits, 13 formules (bundles),
          5 clients de démonstration.
"""

import sys
import os

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db_context
from app.models.product import Product
from app.models.category import Category
from app.models.bundle import ProductBundle, BundleItem
from app.models.customer import Customer
from app.models.product_variant import ProductVariant

TENANT_ID = 1


def _eur_to_cents(eur: float) -> int:
    """Convertit un prix en euros vers centimes BigInteger."""
    return int(round(eur * 100))


def _fix_category_hierarchy(db):
    """Corrige la hiérarchie parent_id si les catégories existent mais sont plates."""
    hierarchy = {
        "vaisselle": ["verres", "assiettes", "couverts", "vaisselle_service", "vaisselle_enfants"],
        "mobilier": ["tables", "chaises", "bancs", "mange_debout", "candy_bar", "accessoires_transport"],
        "nappages": ["housses", "nappes", "serviettes"],
    }
    cats = {c.slug: c for c in db.query(Category).filter(Category.tenant_id == TENANT_ID).all()}
    fixed = 0
    for parent_slug, children_slugs in hierarchy.items():
        parent = cats.get(parent_slug)
        if not parent:
            continue
        for child_slug in children_slugs:
            child = cats.get(child_slug)
            if child and child.parent_id is None:
                child.parent_id = parent.id
                fixed += 1
    if fixed:
        db.commit()
        print(f"  -> Hiérarchie corrigée : {fixed} sous-catégories rattachées.")
    return cats


def seed_categories(db):
    """Crée les catégories hiérarchiques Marveline."""
    existing = db.query(Category).filter(Category.tenant_id == TENANT_ID).count()
    if existing > 0:
        print(f"  -> {existing} catégories existent déjà, vérification hiérarchie...")
        return _fix_category_hierarchy(db)

    # Catégories racines
    roots = [
        {"name": "Vaisselle", "slug": "vaisselle", "description": "Verres, assiettes, couverts et accessoires de service", "display_order": 1},
        {"name": "Mobilier", "slug": "mobilier", "description": "Tables, chaises, bancs et mange-debout", "display_order": 2},
        {"name": "Nappages", "slug": "nappages", "description": "Housses, nappes et serviettes", "display_order": 3},
        {"name": "Machines", "slug": "machines", "description": "Bornes photo, machines à glaces, percolateurs", "display_order": 4},
        {"name": "Décorations & Accessoires", "slug": "decorations-accessoires", "description": "Candy bars, bonbonnières et décorations", "display_order": 5},
        {"name": "Porcelaine", "slug": "porcelaine", "description": "Tasses, bols, ménagères et accessoires", "display_order": 6},
    ]

    root_map = {}
    for r in roots:
        cat = Category(tenant_id=TENANT_ID, **r)
        db.add(cat)
        db.flush()
        root_map[r["slug"]] = cat

    # Sous-catégories Vaisselle
    vaisselle_children = [
        {"name": "Verres", "slug": "verres", "description": "Verres à eau, vin, flûtes à champagne", "display_order": 1},
        {"name": "Assiettes", "slug": "assiettes", "description": "Assiettes rondes, carrées, creuses", "display_order": 2},
        {"name": "Couverts", "slug": "couverts", "description": "Couteaux, fourchettes, cuillères", "display_order": 3},
        {"name": "Vaisselle de service", "slug": "vaisselle-de-service", "description": "Plats, seaux, louches", "display_order": 4},
        {"name": "Vaisselle enfants", "slug": "vaisselle-enfants", "description": "Gobelets, assiettes et couverts enfant", "display_order": 5},
    ]
    for c in vaisselle_children:
        cat = Category(tenant_id=TENANT_ID, parent_id=root_map["vaisselle"].id, **c)
        db.add(cat)
        db.flush()
        root_map[c["slug"]] = cat

    # Sous-catégories Mobilier
    mobilier_children = [
        {"name": "Tables", "slug": "tables", "description": "Tables rectangulaires, rondes, ovales", "display_order": 1},
        {"name": "Chaises", "slug": "chaises", "description": "Chaises plastique, Napoléon III, bois", "display_order": 2},
        {"name": "Bancs", "slug": "bancs", "description": "Bancs bois", "display_order": 3},
        {"name": "Mange-debout", "slug": "mange-debout", "description": "Tables hautes cocktail", "display_order": 4},
        {"name": "Candy Bar", "slug": "candy-bar", "description": "Meubles et accessoires candy bar", "display_order": 5},
        {"name": "Accessoires de transport", "slug": "accessoires-transport", "description": "Socles rouleurs pour bacs et verres", "display_order": 6},
    ]
    for c in mobilier_children:
        cat = Category(tenant_id=TENANT_ID, parent_id=root_map["mobilier"].id, **c)
        db.add(cat)
        db.flush()
        root_map[c["slug"]] = cat

    # Sous-catégories Nappages
    nappages_children = [
        {"name": "Housses", "slug": "housses", "description": "Housses de chaise et mange-debout", "display_order": 1},
        {"name": "Nappes", "slug": "nappes", "description": "Nappes coton rectangulaires, rondes, ovales", "display_order": 2},
        {"name": "Serviettes", "slug": "serviettes", "description": "Serviettes de table coton, couleurs variées", "display_order": 3},
    ]
    for c in nappages_children:
        cat = Category(tenant_id=TENANT_ID, parent_id=root_map["nappages"].id, **c)
        db.add(cat)
        db.flush()
        root_map[c["slug"]] = cat

    db.commit()
    total = db.query(Category).filter(Category.tenant_id == TENANT_ID).count()
    print(f"  -> {total} catégories créées ({len(roots)} racines + sous-catégories)")
    return root_map


def seed_products(db):
    """Crée les produits du catalogue Marveline avec prix réels."""
    existing = db.query(Product).filter(Product.tenant_id == TENANT_ID).count()
    if existing > 0:
        print(f"  -> {existing} produits existent déjà, skip.")
        return

    products = [
        # ── VERRES ──────────────────────────────────────────────────────
        # Gamme Classique
        {"name": "Verre à eau classique", "sku": "VER-EAU-CLA", "category": "verres", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 500, "available_quantity": 500, "image_url": "/images/produits/verres/marveline-produits-verre-classique.jpeg", "short_description": "Verre à eau robuste, gamme classique"},
        {"name": "Verre à vin rouge classique", "sku": "VER-VR-CLA", "category": "verres", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 500, "available_quantity": 500, "image_url": "/images/produits/verres/marveline-produits-verre-classique.jpeg", "short_description": "Verre à vin rouge, gamme classique"},
        {"name": "Verre à vin blanc classique", "sku": "VER-VB-CLA", "category": "verres", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 500, "available_quantity": 500, "image_url": "/images/produits/verres/marveline-produits-verre-classique.jpeg", "short_description": "Verre à vin blanc, gamme classique"},
        {"name": "Flûte à champagne classique", "sku": "VER-FLU-CLA", "category": "verres", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 600, "available_quantity": 600, "image_url": "/images/produits/verres/marveline-produits-flute-classique.jpeg", "short_description": "Flûte à champagne, gamme classique"},
        # Gamme Élégance
        {"name": "Verre à eau élégance", "sku": "VER-EAU-ELG", "category": "verres", "price_per_day_cents": _eur_to_cents(0.35), "stock_quantity": 300, "available_quantity": 300, "image_url": "/images/produits/verres/marveline-produits-verre-a-eau-elegance.jpeg", "short_description": "Verre à eau design élégant"},
        {"name": "Verre à vin rouge élégance", "sku": "VER-VR-ELG", "category": "verres", "price_per_day_cents": _eur_to_cents(0.35), "stock_quantity": 300, "available_quantity": 300, "image_url": "/images/produits/verres/marveline-produits-verre-a-vin-rouge-elegance.jpeg", "short_description": "Verre à vin rouge, gamme élégance"},
        {"name": "Verre à vin blanc élégance", "sku": "VER-VB-ELG", "category": "verres", "price_per_day_cents": _eur_to_cents(0.35), "stock_quantity": 300, "available_quantity": 300, "image_url": "/images/produits/verres/marveline-produits-verre-a-vin-blanc-elegance.jpeg", "short_description": "Verre à vin blanc, gamme élégance"},
        {"name": "Flûte à champagne élégance", "sku": "VER-FLU-ELG", "category": "verres", "price_per_day_cents": _eur_to_cents(0.35), "stock_quantity": 300, "available_quantity": 300, "image_url": "/images/produits/verres/marveline-produits-flute-elegance.jpeg", "short_description": "Flûte à champagne, gamme élégance"},
        # Gamme Open'Up
        {"name": "Verre à eau Open'Up", "sku": "VER-EAU-OPN", "category": "verres", "price_per_day_cents": _eur_to_cents(0.90), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/verres/marveline-produits-verre-eau-open-up.jpeg", "short_description": "Verre eau haut de gamme Open'Up"},
        {"name": "Verre à vin rouge Open'Up", "sku": "VER-VR-OPN", "category": "verres", "price_per_day_cents": _eur_to_cents(0.90), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/verres/marveline-produits-verre-vin-rouge-open-up.jpeg", "short_description": "Verre vin rouge haut de gamme Open'Up"},
        {"name": "Verre à vin blanc Open'Up", "sku": "VER-VB-OPN", "category": "verres", "price_per_day_cents": _eur_to_cents(0.90), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/verres/marveline-produits-verre-vin-blanc-open-up.jpeg", "short_description": "Verre vin blanc haut de gamme Open'Up"},
        {"name": "Flûte à champagne Open'Up", "sku": "VER-FLU-OPN", "category": "verres", "price_per_day_cents": _eur_to_cents(0.90), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/verres/marveline-produits-flute-open-up.jpeg", "short_description": "Flûte champagne haut de gamme Open'Up"},
        # Gamme Vintage
        {"name": "Verre Vintage", "sku": "VER-VINT", "category": "verres", "price_per_day_cents": _eur_to_cents(0.78), "stock_quantity": 150, "available_quantity": 150, "image_url": "/images/produits/verres/marveline-produits-verre-eau-vintage.jpeg", "short_description": "Verre vintage au style rétro"},
        {"name": "Verre ballon", "sku": "VER-BALL", "category": "verres", "price_per_day_cents": _eur_to_cents(0.90), "stock_quantity": 100, "available_quantity": 100, "image_url": "/images/produits/verres/marveline-produits-verre-ballon.jpeg", "short_description": "Grand verre ballon pour vin rouge"},
        {"name": "Verre à soft élégance", "sku": "VER-SOFT-ELG", "category": "verres", "price_per_day_cents": _eur_to_cents(0.35), "stock_quantity": 300, "available_quantity": 300, "image_url": "/images/produits/verres/marveline-produits-verre-a-soft-elegance.jpeg", "short_description": "Verre à soft, gamme élégance"},

        # ── ASSIETTES ──────────────────────────────────────────────────
        {"name": "Assiette ronde classique 16cm", "sku": "ASS-RND-CLA-16", "category": "assiettes", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 400, "available_quantity": 400, "image_url": "/images/produits/assiettes/marveline-produits-assiette-pain.jpeg", "short_description": "Assiette à pain ronde classique 16cm"},
        {"name": "Assiette ronde classique 21cm", "sku": "ASS-RND-CLA-21", "category": "assiettes", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 400, "available_quantity": 400, "image_url": "/images/produits/assiettes/marveline-produits-assiette-cocktail.jpg", "short_description": "Assiette ronde classique 21cm"},
        {"name": "Assiette ronde creuse classique 22,5cm", "sku": "ASS-CRS-CLA-22", "category": "assiettes", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 400, "available_quantity": 400, "image_url": "/images/produits/assiettes/marveline-produits-assiette-creuse-classique.jpeg", "short_description": "Assiette creuse classique 22,5cm"},
        {"name": "Assiette ronde classique 26cm", "sku": "ASS-RND-CLA-26", "category": "assiettes", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 400, "available_quantity": 400, "image_url": "/images/produits/assiettes/marveline-produits-assiette-cocktail.jpg", "short_description": "Assiette ronde classique 26cm"},
        {"name": "Assiette ronde classique 30,5cm", "sku": "ASS-RND-CLA-30", "category": "assiettes", "price_per_day_cents": _eur_to_cents(0.42), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/assiettes/marveline-produits-assiette-vintage.jpg", "short_description": "Grande assiette ronde classique 30,5cm"},
        {"name": "Assiette ronde extra creuse blanche 27cm", "sku": "ASS-XCRS-BLC-27", "category": "assiettes", "price_per_day_cents": _eur_to_cents(0.54), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/assiettes/marveline-produits-assiette-extra-creuse-blanche.jpeg", "short_description": "Assiette extra creuse blanche 27cm"},
        {"name": "Assiette à couscous / paella 26cm", "sku": "ASS-COUSC-26", "category": "assiettes", "price_per_day_cents": _eur_to_cents(0.54), "stock_quantity": 100, "available_quantity": 100, "image_url": "/images/produits/assiettes/marveline-produits-assiette-couscous.jpeg", "short_description": "Assiette creuse couscous / paella 26cm"},
        {"name": "Assiette carrée creuse élégance 23cm", "sku": "ASS-CAR-CRS-ELG-23", "category": "assiettes", "price_per_day_cents": _eur_to_cents(0.36), "stock_quantity": 300, "available_quantity": 300, "image_url": "/images/produits/assiettes/marveline-produits-assiettes-carrees-creuses-elegance.jpeg", "short_description": "Assiette carrée creuse élégance 23cm"},
        {"name": "Assiette carrée élégance 23cm", "sku": "ASS-CAR-ELG-23", "category": "assiettes", "price_per_day_cents": _eur_to_cents(0.36), "stock_quantity": 300, "available_quantity": 300, "image_url": "/images/produits/assiettes/marveline-produits-assiettes-carrees-elegance.jpeg", "short_description": "Assiette carrée plate élégance 23cm"},
        {"name": "Assiette carrée élégance 27cm", "sku": "ASS-CAR-ELG-27", "category": "assiettes", "price_per_day_cents": _eur_to_cents(0.36), "stock_quantity": 300, "available_quantity": 300, "image_url": "/images/produits/assiettes/marveline-produits-assiettes-carrees-elegance.jpeg", "short_description": "Grande assiette carrée élégance 27cm"},
        {"name": "Assiette ronde Vintage 16cm", "sku": "ASS-RND-VIN-16", "category": "assiettes", "price_per_day_cents": _eur_to_cents(0.60), "stock_quantity": 150, "available_quantity": 150, "image_url": "/images/produits/assiettes/marveline-produits-assiette-vintage.jpg", "short_description": "Assiette vintage ronde 16cm"},
        {"name": "Assiette ronde creuse Vintage 22cm", "sku": "ASS-CRS-VIN-22", "category": "assiettes", "price_per_day_cents": _eur_to_cents(0.60), "stock_quantity": 150, "available_quantity": 150, "image_url": "/images/produits/assiettes/marveline-produits-assiette-creuse-vintage.jpeg", "short_description": "Assiette creuse vintage 22cm"},
        {"name": "Assiette ronde Vintage 27cm", "sku": "ASS-RND-VIN-27", "category": "assiettes", "price_per_day_cents": _eur_to_cents(0.78), "stock_quantity": 150, "available_quantity": 150, "image_url": "/images/produits/assiettes/marveline-produits-assiette-vintage.jpg", "short_description": "Grande assiette vintage ronde 27cm"},

        # ── COUVERTS ───────────────────────────────────────────────────
        {"name": "Couteau de table élégance", "sku": "COV-COU-ELG", "category": "couverts", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 500, "available_quantity": 500, "image_url": "/images/produits/couverts/marveline-produits-couteau-elegance.jpeg", "short_description": "Couteau de table gamme élégance"},
        {"name": "Fourchette de table élégance", "sku": "COV-FOU-ELG", "category": "couverts", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 500, "available_quantity": 500, "image_url": "/images/produits/couverts/marveline-produits-fourchette-elegance.jpeg", "short_description": "Fourchette de table gamme élégance"},
        {"name": "Cuillère de table élégance", "sku": "COV-CUI-ELG", "category": "couverts", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 500, "available_quantity": 500, "image_url": "/images/produits/couverts/marveline-produits-cuillere-de-table-elegance.jpeg", "short_description": "Cuillère de table gamme élégance"},
        {"name": "Couteau à steak élégance", "sku": "COV-STK-ELG", "category": "couverts", "price_per_day_cents": _eur_to_cents(0.36), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/couverts/marveline-produits-couteau-steak-elegance.jpeg", "short_description": "Couteau à steak gamme élégance"},
        {"name": "Couteau à poisson élégance", "sku": "COV-PSN-ELG", "category": "couverts", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/couverts/marveline-produits-couteau-poisson-elegance.jpeg", "short_description": "Couteau à poisson gamme élégance"},
        {"name": "Fourchette à poisson élégance", "sku": "COV-FPS-ELG", "category": "couverts", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/couverts/marveline-produits-fourchette-poisson-elegance.jpeg", "short_description": "Fourchette à poisson gamme élégance"},
        {"name": "Couteau à dessert élégance", "sku": "COV-CDS-ELG", "category": "couverts", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 400, "available_quantity": 400, "image_url": "/images/produits/couverts/marveline-produits-couteau-elegance.jpeg", "short_description": "Couteau à dessert gamme élégance"},
        {"name": "Fourchette à dessert élégance", "sku": "COV-FDS-ELG", "category": "couverts", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 400, "available_quantity": 400, "image_url": "/images/produits/couverts/marveline-produits-fourchette-elegance.jpeg", "short_description": "Fourchette à dessert gamme élégance"},
        {"name": "Cuillère à dessert élégance", "sku": "COV-CUDS-ELG", "category": "couverts", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 400, "available_quantity": 400, "image_url": "/images/produits/couverts/marveline-produits-cuillere-a-cafe-elegance.jpeg", "short_description": "Cuillère à dessert gamme élégance"},
        {"name": "Cuillère à café élégance", "sku": "COV-CAF-ELG", "category": "couverts", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 400, "available_quantity": 400, "image_url": "/images/produits/couverts/marveline-produits-cuillere-a-cafe-elegance.jpeg", "short_description": "Cuillère à café gamme élégance"},
        {"name": "Cuillère à moka élégance", "sku": "COV-MOK-ELG", "category": "couverts", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/couverts/marveline-produits-cuillere-a-cafe-elegance.jpeg", "short_description": "Cuillère à moka gamme élégance"},
        {"name": "Couteau de table prestige", "sku": "COV-COU-PRE", "category": "couverts", "price_per_day_cents": _eur_to_cents(0.32), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/couverts/marveline-produits-couteau-prestige.jpg", "short_description": "Couteau de table gamme prestige"},
        {"name": "Couteau de table Or", "sku": "COV-COU-OR", "category": "couverts", "price_per_day_cents": _eur_to_cents(0.54), "stock_quantity": 100, "available_quantity": 100, "image_url": "/images/produits/couverts/marveline-produits-couteau-table-or.png", "short_description": "Couteau de table finition dorée"},

        # ── VAISSELLE DE SERVICE ───────────────────────────────────────
        {"name": "Coupe à dessert", "sku": "SRV-COP-DES", "category": "vaisselle_service", "price_per_day_cents": _eur_to_cents(0.42), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/vaisselle-service/marveline-produits-coupe-dessert.jpeg", "short_description": "Coupe à dessert en verre"},
        {"name": "Pelle à tarte", "sku": "SRV-PEL-TAR", "category": "vaisselle_service", "price_per_day_cents": _eur_to_cents(1.20), "stock_quantity": 30, "available_quantity": 30, "image_url": "/images/produits/vaisselle-service/marveline-produits-pelle-a-tarte.jpg", "short_description": "Pelle à tarte inox"},
        {"name": "Fourchette de service", "sku": "SRV-FOU-SRV", "category": "vaisselle_service", "price_per_day_cents": _eur_to_cents(1.20), "stock_quantity": 30, "available_quantity": 30, "image_url": "/images/produits/vaisselle-service/marveline-produits-fourchette-service.png", "short_description": "Fourchette de service inox"},
        {"name": "Fourchette de service viande", "sku": "SRV-FOU-VIA", "category": "vaisselle_service", "price_per_day_cents": _eur_to_cents(1.20), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/vaisselle-service/marveline-produits-fourchette-service.png", "short_description": "Fourchette de service à viande inox"},
        {"name": "Cuillère de service", "sku": "SRV-CUI-SRV", "category": "vaisselle_service", "price_per_day_cents": _eur_to_cents(1.20), "stock_quantity": 30, "available_quantity": 30, "image_url": "/images/produits/vaisselle-service/marveline-produits-cuillere-service.png", "short_description": "Cuillère de service inox"},
        {"name": "Couteau à fromage", "sku": "SRV-COU-FRO", "category": "vaisselle_service", "price_per_day_cents": _eur_to_cents(0.90), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/vaisselle-service/marveline-produits-couteau-fromage.jpg", "short_description": "Couteau à fromage inox"},
        {"name": "Couteau à gâteau", "sku": "SRV-COU-GAT", "category": "vaisselle_service", "price_per_day_cents": _eur_to_cents(3.00), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/vaisselle-service/marveline-produits-couteau-a-gateau.jpeg", "short_description": "Couteau à gâteau/wedding cake"},
        {"name": "Couteau de chef", "sku": "SRV-COU-CHF", "category": "vaisselle_service", "price_per_day_cents": _eur_to_cents(4.50), "stock_quantity": 5, "available_quantity": 5, "image_url": "/images/produits/vaisselle-service/marveline-produits-couteau-chef-1.jpeg", "short_description": "Couteau de chef professionnel"},
        {"name": "Louche", "sku": "SRV-LOUCHE", "category": "vaisselle_service", "price_per_day_cents": _eur_to_cents(0.90), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/vaisselle-service/marveline-produits-louche.jpg", "short_description": "Louche de service inox"},
        {"name": "Seau à champagne", "sku": "SRV-SEAU-CHP", "category": "vaisselle_service", "price_per_day_cents": _eur_to_cents(3.00), "stock_quantity": 30, "available_quantity": 30, "image_url": "/images/produits/vaisselle-service/marveline-produits-seau-a-champagne.jpeg", "short_description": "Seau à champagne inox"},
        {"name": "Vasque à champagne", "sku": "SRV-VASQ-CHP", "category": "vaisselle_service", "price_per_day_cents": _eur_to_cents(10.00), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/vaisselle-service/marveline-produits-vasque-champagne.png", "short_description": "Grande vasque à champagne pour buffet"},
        {"name": "Distributeur à jus", "sku": "SRV-DIST-JUS", "category": "vaisselle_service", "price_per_day_cents": _eur_to_cents(6.00), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/vaisselle-service/marveline-produits-distributeur-jus.jpeg", "short_description": "Distributeur à jus transparent avec robinet"},
        {"name": "Plateau de service inox", "sku": "SRV-PLAT-INX", "category": "vaisselle_service", "price_per_day_cents": _eur_to_cents(4.00), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/vaisselle-service/marveline-produits-plat-ovale-inox.jpg", "short_description": "Plateau de service ovale en inox"},

        # ── PORCELAINE ─────────────────────────────────────────────────
        {"name": "Ménagère sel/poivre élégance", "sku": "POR-MEN-SP-ELG", "category": "porcelaine", "price_per_day_cents": _eur_to_cents(0.72), "stock_quantity": 100, "available_quantity": 100, "image_url": "/images/produits/porcelaine/marveline-produits-menagere-sel-poivre-classique.jpeg", "short_description": "Ménagère sel et poivre porcelaine élégance"},
        {"name": "Ménagère sel/poivre prestige", "sku": "POR-MEN-SP-PRE", "category": "porcelaine", "price_per_day_cents": _eur_to_cents(0.85), "stock_quantity": 50, "available_quantity": 50, "image_url": "/images/produits/porcelaine/marveline-produits-menagere-sel-poivre-prestige.jpeg", "short_description": "Ménagère sel et poivre porcelaine prestige"},
        {"name": "Ménagère sel/poivre/moutarde prestige", "sku": "POR-MEN-SPM-PRE", "category": "porcelaine", "price_per_day_cents": _eur_to_cents(1.00), "stock_quantity": 30, "available_quantity": 30, "image_url": "/images/produits/porcelaine/marveline-produits-menagere-sel-poivre-moutarde.jpeg", "short_description": "Ménagère trio sel, poivre et moutarde prestige"},
        {"name": "Tasse à café", "sku": "POR-TAS-CAF", "category": "porcelaine", "price_per_day_cents": _eur_to_cents(0.24), "stock_quantity": 300, "available_quantity": 300, "image_url": "/images/produits/porcelaine/marveline-produits-tasse.jpg", "short_description": "Tasse à café en porcelaine blanche"},
        {"name": "Sous-tasse à café", "sku": "POR-STA-CAF", "category": "porcelaine", "price_per_day_cents": _eur_to_cents(0.18), "stock_quantity": 300, "available_quantity": 300, "image_url": "/images/produits/porcelaine/marveline-produits-sous-tasse-expresso.jpeg", "short_description": "Sous-tasse à café / expresso en porcelaine"},
        {"name": "Tasse à thé", "sku": "POR-TAS-THE", "category": "porcelaine", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 100, "available_quantity": 100, "image_url": "/images/produits/porcelaine/marveline-produits-tasse.jpg", "short_description": "Tasse à thé en porcelaine blanche"},
        {"name": "Sous-tasse à thé", "sku": "POR-STA-THE", "category": "porcelaine", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 100, "available_quantity": 100, "image_url": "/images/produits/porcelaine/marveline-produits-sous-tasse-the.jpeg", "short_description": "Sous-tasse à thé en porcelaine"},
        {"name": "Bol", "sku": "POR-BOL", "category": "porcelaine", "price_per_day_cents": _eur_to_cents(0.36), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/porcelaine/marveline-produit-bol.jpeg", "short_description": "Bol en porcelaine blanche"},
        {"name": "Ramequin", "sku": "POR-RAM", "category": "porcelaine", "price_per_day_cents": _eur_to_cents(0.36), "stock_quantity": 150, "available_quantity": 150, "image_url": "/images/produits/porcelaine/marveline-produits-ramequin-19cl.jpg", "short_description": "Ramequin individuel 19cl en porcelaine"},
        {"name": "Saucier", "sku": "POR-SAUC", "category": "porcelaine", "price_per_day_cents": _eur_to_cents(2.40), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/porcelaine/marveline-produits-saucier-34cl.jpg", "short_description": "Saucier 34cl en porcelaine blanche"},
        {"name": "Mug", "sku": "POR-MUG", "category": "porcelaine", "price_per_day_cents": _eur_to_cents(0.36), "stock_quantity": 100, "available_quantity": 100, "image_url": "/images/produits/porcelaine/marveline-produit-mug.jpeg", "short_description": "Mug en porcelaine blanche"},
        {"name": "Sucrier prestige", "sku": "POR-SUC-PRE", "category": "porcelaine", "price_per_day_cents": _eur_to_cents(1.50), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/porcelaine/marveline-produits-sucrier-prestige.jpeg", "short_description": "Sucrier prestige en porcelaine"},

        # ── VAISSELLE ENFANTS ──────────────────────────────────────────
        {"name": "Gobelet enfant", "sku": "ENF-GOB", "category": "vaisselle_enfants", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 100, "available_quantity": 100, "image_url": "/images/produits/vaisselle-enfants/marveline-produits-gobelet-enfant.jpeg", "short_description": "Gobelet enfant coloré et résistant"},
        {"name": "Assiette enfant", "sku": "ENF-ASS", "category": "vaisselle_enfants", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 100, "available_quantity": 100, "image_url": "/images/produits/vaisselle-enfants/marveline-produits-assiette-enfant.jpeg", "short_description": "Assiette enfant colorée et résistante"},
        {"name": "Couteau enfant", "sku": "ENF-COU", "category": "vaisselle_enfants", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 100, "available_quantity": 100, "image_url": "/images/produits/vaisselle-enfants/marveline-produits-couteau-enfant.jpeg", "short_description": "Couteau enfant inox à lame arrondie"},
        {"name": "Fourchette enfant", "sku": "ENF-FOU", "category": "vaisselle_enfants", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 100, "available_quantity": 100, "image_url": "/images/produits/vaisselle-enfants/marveline-produits-fourchette-enfant.jpeg", "short_description": "Fourchette enfant inox de taille adaptée"},
        {"name": "Cuillère enfant", "sku": "ENF-CUI", "category": "vaisselle_enfants", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 100, "available_quantity": 100, "image_url": "/images/produits/vaisselle-enfants/marveline-produits-cuillere-enfant.jpeg", "short_description": "Cuillère enfant inox de taille adaptée"},

        # ── TABLES ─────────────────────────────────────────────────────
        {"name": "Table rectangulaire 183x76cm", "sku": "TAB-REC-183", "category": "tables", "price_per_day_cents": _eur_to_cents(10.00), "stock_quantity": 30, "available_quantity": 30, "image_url": "/images/produits/mobilier/marveline-produits-table-rectangulaire.png", "short_description": "Table pliante rectangulaire 183x76cm"},
        {"name": "Table rectangulaire 200x90cm", "sku": "TAB-REC-200", "category": "tables", "price_per_day_cents": _eur_to_cents(11.00), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/mobilier/marveline-produits-table-rectangulaire.png", "short_description": "Table pliante rectangulaire 200x90cm"},
        {"name": "Table ronde diamètre 150cm", "sku": "TAB-RND-150", "category": "tables", "price_per_day_cents": _eur_to_cents(10.00), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/mobilier/marveline-produits-table-ronde.png", "short_description": "Table ronde diamètre 150cm"},
        {"name": "Table ronde diamètre 180cm", "sku": "TAB-RND-180", "category": "tables", "price_per_day_cents": _eur_to_cents(16.50), "stock_quantity": 15, "available_quantity": 15, "image_url": "/images/produits/mobilier/marveline-produits-table-ronde.png", "short_description": "Grande table ronde diamètre 180cm"},
        {"name": "Table ronde bois diamètre 153cm", "sku": "TAB-RND-BOIS-153", "category": "tables", "price_per_day_cents": _eur_to_cents(54.00), "stock_quantity": 5, "available_quantity": 5, "image_url": "/images/produits/mobilier/marveline-produits-table-bois-ronde.jpg", "short_description": "Table ronde bois massif diamètre 153cm"},
        {"name": "Table rectangulaire bois 210x100cm", "sku": "TAB-REC-BOIS-210", "category": "tables", "price_per_day_cents": _eur_to_cents(48.00), "stock_quantity": 5, "available_quantity": 5, "image_url": "/images/produits/mobilier/marveline-produits-table-bois-rectangulaire.jpg", "short_description": "Table rectangulaire bois massif 210x100cm"},
        {"name": "Table ovale 12 personnes", "sku": "TAB-OVA-12", "category": "tables", "price_per_day_cents": _eur_to_cents(18.00), "stock_quantity": 5, "available_quantity": 5, "image_url": "/images/produits/mobilier/marveline-produits-table-ovale.jpg", "short_description": "Table ovale pour 12 personnes"},
        {"name": "Table ovale 14 personnes", "sku": "TAB-OVA-14", "category": "tables", "price_per_day_cents": _eur_to_cents(24.00), "stock_quantity": 4, "available_quantity": 4, "image_url": "/images/produits/mobilier/marveline-produits-table-ovale.jpg", "short_description": "Table ovale pour 14 personnes"},
        {"name": "Table ovale 16 personnes", "sku": "TAB-OVA-16", "category": "tables", "price_per_day_cents": _eur_to_cents(30.00), "stock_quantity": 3, "available_quantity": 3, "image_url": "/images/produits/mobilier/marveline-produits-table-ovale.jpg", "short_description": "Table ovale pour 16 personnes"},
        {"name": "Table ovale 18 personnes", "sku": "TAB-OVA-18", "category": "tables", "price_per_day_cents": _eur_to_cents(36.00), "stock_quantity": 3, "available_quantity": 3, "image_url": "/images/produits/mobilier/marveline-produits-table-ovale.jpg", "short_description": "Grande table ovale pour 18 personnes"},
        {"name": "Table ovale 22 personnes", "sku": "TAB-OVA-22", "category": "tables", "price_per_day_cents": _eur_to_cents(42.00), "stock_quantity": 2, "available_quantity": 2, "image_url": "/images/produits/mobilier/marveline-produits-table-ovale.jpg", "short_description": "Grande table ovale pour 22 personnes"},

        # ── CHAISES ────────────────────────────────────────────────────
        {"name": "Chaise plastique", "sku": "CHA-PLAST", "category": "chaises", "price_per_day_cents": _eur_to_cents(2.00), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/mobilier/marveline-produits-chaise.jpeg", "short_description": "Chaise plastique empilable"},
        {"name": "Chaise Napoléon III", "sku": "CHA-NAP3", "category": "chaises", "price_per_day_cents": _eur_to_cents(6.90), "stock_quantity": 100, "available_quantity": 100, "image_url": "/images/produits/mobilier/marveline-produits-chaise-napoleon.jpg", "short_description": "Chaise Napoléon III élégante"},
        {"name": "Chaise Bois Dos Croisé", "sku": "CHA-BOIS-DC", "category": "chaises", "price_per_day_cents": _eur_to_cents(7.80), "stock_quantity": 80, "available_quantity": 80, "image_url": "/images/produits/mobilier/marveline-produits-chaise-bois.jpg", "short_description": "Chaise bois dos croisé style champêtre"},
        {"name": "Tabouret de bar", "sku": "CHA-TAB-BAR", "category": "chaises", "price_per_day_cents": _eur_to_cents(3.00), "stock_quantity": 30, "available_quantity": 30, "image_url": "/images/produits/mobilier/marveline-produit-tabouret.jpg", "short_description": "Tabouret de bar pour mange-debout"},

        # ── BANCS ──────────────────────────────────────────────────────
        {"name": "Banc bois", "sku": "BAN-BOIS", "category": "bancs", "price_per_day_cents": _eur_to_cents(7.80), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/mobilier/marveline-produits-banc-bois-blanc.png", "short_description": "Banc en bois laqué blanc"},

        # ── MANGE-DEBOUT ───────────────────────────────────────────────
        {"name": "Mange-debout", "sku": "MDB-STD", "category": "mange_debout", "price_per_day_cents": _eur_to_cents(12.00), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/mobilier/marveline-produits-mange-debout.jpeg", "short_description": "Mange-debout pliable en métal"},

        # ── HOUSSES ────────────────────────────────────────────────────
        {"name": "Housse de chaise blanche", "sku": "HOU-CHA-BLC", "category": "housses", "price_per_day_cents": _eur_to_cents(2.40), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/nappages/marveline-produits-housse-chaise.jpeg", "short_description": "Housse de chaise blanche avec noeud"},
        {"name": "Housse de chaise ivoire", "sku": "HOU-CHA-IVO", "category": "housses", "price_per_day_cents": _eur_to_cents(2.40), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/nappages/marveline-produits-housse-chaise-ivoire.jpeg", "short_description": "Housse de chaise ivoire avec noeud"},
        {"name": "Housse de mange-debout", "sku": "HOU-MDB-STD", "category": "housses", "price_per_day_cents": _eur_to_cents(6.00), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/nappages/marveline-produits-mange-debout-housse-blanche.jpg", "short_description": "Housse blanche pour mange-debout"},
        {"name": "Housse de mange-debout juponnée", "sku": "HOU-MDB-JUP", "category": "housses", "price_per_day_cents": _eur_to_cents(9.00), "stock_quantity": 15, "available_quantity": 15, "image_url": "/images/produits/nappages/marveline-produits-housse-MD-juponnee.png", "short_description": "Housse juponnée élégante pour mange-debout"},

        # ── NAPPES ─────────────────────────────────────────────────────
        {"name": "Nappe coton rectangulaire 140x240cm", "sku": "NAP-REC-140x240", "category": "nappes", "price_per_day_cents": _eur_to_cents(11.00), "stock_quantity": 50, "available_quantity": 50, "image_url": "/images/produits/nappages/marveline-produits-nappe-rectangulaire.jpg", "short_description": "Nappe coton blanche rectangulaire 140x240cm", "requires_advance_booking_days": 90},
        {"name": "Nappe coton rectangulaire 200x240cm", "sku": "NAP-REC-200x240", "category": "nappes", "price_per_day_cents": _eur_to_cents(12.00), "stock_quantity": 40, "available_quantity": 40, "image_url": "/images/produits/nappages/marveline-produits-nappe-rectangulaire.jpg", "short_description": "Nappe coton blanche rectangulaire 200x240cm", "requires_advance_booking_days": 90},
        {"name": "Nappe coton rectangulaire 300x160cm", "sku": "NAP-REC-300x160", "category": "nappes", "price_per_day_cents": _eur_to_cents(13.50), "stock_quantity": 30, "available_quantity": 30, "image_url": "/images/produits/nappages/marveline-produits-nappe-rectangulaire.jpg", "short_description": "Nappe coton blanche rectangulaire 300x160cm", "requires_advance_booking_days": 90},
        {"name": "Nappe coton rectangulaire 300x190cm", "sku": "NAP-REC-300x190", "category": "nappes", "price_per_day_cents": _eur_to_cents(17.00), "stock_quantity": 30, "available_quantity": 30, "image_url": "/images/produits/nappages/marveline-produits-nappe-rectangulaire.jpg", "short_description": "Nappe coton blanche rectangulaire 300x190cm", "requires_advance_booking_days": 90},
        {"name": "Nappe coton rectangulaire 500x190cm", "sku": "NAP-REC-500x190", "category": "nappes", "price_per_day_cents": _eur_to_cents(24.00), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/nappages/marveline-produits-nappe-rectangulaire.jpg", "short_description": "Grande nappe coton rectangulaire 500x190cm", "requires_advance_booking_days": 90},
        {"name": "Nappe coton carrée 250x250cm", "sku": "NAP-CAR-250", "category": "nappes", "price_per_day_cents": _eur_to_cents(15.00), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/nappages/marveline-produits-nappe-carree.jpg", "short_description": "Nappe coton blanche carrée 250x250cm", "requires_advance_booking_days": 90},
        {"name": "Nappe coton ronde 240cm", "sku": "NAP-RND-240", "category": "nappes", "price_per_day_cents": _eur_to_cents(15.00), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/nappages/marveline-produits-nappe-ronde.jpg", "short_description": "Nappe coton blanche ronde diamètre 240cm", "requires_advance_booking_days": 90},
        {"name": "Nappe coton ovale 240x360cm", "sku": "NAP-OVA-240x360", "category": "nappes", "price_per_day_cents": _eur_to_cents(20.00), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/nappages/marveline-produits-nappe-ovale.jpg", "short_description": "Nappe coton blanche ovale 240x360cm", "requires_advance_booking_days": 90},
        {"name": "Nappe coton ovale 240x420cm", "sku": "NAP-OVA-240x420", "category": "nappes", "price_per_day_cents": _eur_to_cents(24.00), "stock_quantity": 8, "available_quantity": 8, "image_url": "/images/produits/nappages/marveline-produits-nappe-ovale.jpg", "short_description": "Nappe coton blanche ovale 240x420cm", "requires_advance_booking_days": 90},
        {"name": "Nappe coton ovale 240x480cm", "sku": "NAP-OVA-240x480", "category": "nappes", "price_per_day_cents": _eur_to_cents(27.60), "stock_quantity": 6, "available_quantity": 6, "image_url": "/images/produits/nappages/marveline-produits-nappe-ovale.jpg", "short_description": "Nappe coton blanche ovale 240x480cm", "requires_advance_booking_days": 90},
        {"name": "Nappe coton ovale 240x540cm", "sku": "NAP-OVA-240x540", "category": "nappes", "price_per_day_cents": _eur_to_cents(30.00), "stock_quantity": 4, "available_quantity": 4, "image_url": "/images/produits/nappages/marveline-produits-nappe-ovale.jpg", "short_description": "Grande nappe coton blanche ovale 240x540cm", "requires_advance_booking_days": 90},
        {"name": "Nappe coton ovale 240x660cm", "sku": "NAP-OVA-240x660", "category": "nappes", "price_per_day_cents": _eur_to_cents(36.00), "stock_quantity": 3, "available_quantity": 3, "image_url": "/images/produits/nappages/marveline-produits-nappe-ovale.jpg", "short_description": "Très grande nappe coton blanche ovale 240x660cm", "requires_advance_booking_days": 90},
        {"name": "Nappe ronde coton 280cm", "sku": "NAP-RND-280", "category": "nappes", "price_per_day_cents": _eur_to_cents(17.00), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/nappages/marveline-produits-nappe-ronde.jpg", "short_description": "Nappe coton blanche ronde diamètre 280cm", "requires_advance_booking_days": 90},
        {"name": "Nappe ronde coton 280cm couleur", "sku": "NAP-RND-280-COL", "category": "nappes", "price_per_day_cents": _eur_to_cents(24.00), "stock_quantity": 8, "available_quantity": 8, "image_url": "/images/produits/nappages/marveline-produits-nappe-ronde.jpg", "short_description": "Nappe coton couleur ronde diamètre 280cm", "requires_advance_booking_days": 90},
        {"name": "Nappe ronde coton 300cm", "sku": "NAP-RND-300", "category": "nappes", "price_per_day_cents": _eur_to_cents(18.00), "stock_quantity": 8, "available_quantity": 8, "image_url": "/images/produits/nappages/marveline-produits-nappe-ronde.jpg", "short_description": "Nappe coton blanche ronde diamètre 300cm", "requires_advance_booking_days": 90},
        {"name": "Nappe rect. coton 300x175cm ivoire", "sku": "NAP-REC-300x175-IVO", "category": "nappes", "price_per_day_cents": _eur_to_cents(15.00), "stock_quantity": 15, "available_quantity": 15, "image_url": "/images/produits/nappages/marveline-produits-nappe-rectangulaire.jpg", "short_description": "Nappe coton ivoire rectangulaire 300x175cm", "requires_advance_booking_days": 90},
        {"name": "Nappe ronde coton 240cm ivoire", "sku": "NAP-RND-240-IVO", "category": "nappes", "price_per_day_cents": _eur_to_cents(16.00), "stock_quantity": 15, "available_quantity": 15, "image_url": "/images/produits/nappages/marveline-produits-nappe-ronde.jpg", "short_description": "Nappe coton ivoire ronde diamètre 240cm", "requires_advance_booking_days": 90},

        # ── SERVIETTES ─────────────────────────────────────────────────
        {"name": "Serviette de table coton blanche", "sku": "SER-COT-BLC", "category": "serviettes", "price_per_day_cents": _eur_to_cents(0.90), "stock_quantity": 500, "available_quantity": 500, "image_url": "/images/produits/nappages/marveline-produits-serviette.jpg", "short_description": "Serviette de table coton blanche 40x40cm"},
        {"name": "Serviette de table coton ivoire", "sku": "SER-COT-IVO", "category": "serviettes", "price_per_day_cents": _eur_to_cents(0.90), "stock_quantity": 500, "available_quantity": 500, "image_url": "/images/produits/nappages/marveline-produits-serviette.jpg", "short_description": "Serviette de table coton ivoire 40x40cm"},
        {"name": "Serviette de table coton bordeaux", "sku": "SER-COT-BOR", "category": "serviettes", "price_per_day_cents": _eur_to_cents(1.80), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/nappages/marveline-produits-serviette.jpg", "short_description": "Serviette de table coton bordeaux 40x40cm"},
        {"name": "Serviette de table coton noire", "sku": "SER-COT-NOI", "category": "serviettes", "price_per_day_cents": _eur_to_cents(1.80), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/nappages/marveline-produits-serviette.jpg", "short_description": "Serviette de table coton noire 40x40cm"},
        {"name": "Serviette de table coton rouge", "sku": "SER-COT-ROU", "category": "serviettes", "price_per_day_cents": _eur_to_cents(1.80), "stock_quantity": 200, "available_quantity": 200, "image_url": "/images/produits/nappages/marveline-produits-serviette.jpg", "short_description": "Serviette de table coton rouge 40x40cm"},
        {"name": "Serviette de table coton vert amande", "sku": "SER-COT-VAM", "category": "serviettes", "price_per_day_cents": _eur_to_cents(1.80), "stock_quantity": 150, "available_quantity": 150, "image_url": "/images/produits/nappages/marveline-produits-serviette.jpg", "short_description": "Serviette de table coton vert amande 40x40cm"},
        {"name": "Serviette de table coton vert sapin", "sku": "SER-COT-VSA", "category": "serviettes", "price_per_day_cents": _eur_to_cents(1.80), "stock_quantity": 150, "available_quantity": 150, "image_url": "/images/produits/nappages/marveline-produits-serviette.jpg", "short_description": "Serviette de table coton vert sapin 40x40cm"},

        # ── MACHINES ───────────────────────────────────────────────────
        {"name": "Borne à selfie", "sku": "MAC-BORN-SEL", "category": "machines", "price_per_day_cents": _eur_to_cents(200.00), "deposit_amount_cents": _eur_to_cents(3000.00), "stock_quantity": 2, "available_quantity": 2, "image_url": "/images/produits/machines/borneselfie_marveline.png", "short_description": "Borne à selfie tactile avec imprimante intégrée"},
        {"name": "Caisse d'accessoires borne à selfie", "sku": "MAC-ACC-BORN", "category": "machines", "price_per_day_cents": _eur_to_cents(30.00), "stock_quantity": 3, "available_quantity": 3, "image_url": "/images/produits/candy-bar/marveline-produits-caisse-borne-selfie.jpg", "short_description": "Caisse d'accessoires et props pour borne à selfie"},
        {"name": "Instax mini", "sku": "MAC-INST-MIN", "category": "machines", "price_per_day_cents": _eur_to_cents(30.00), "stock_quantity": 5, "available_quantity": 5, "image_url": "/images/produits/machines/instax_mini_film_cartridge.png", "short_description": "Appareil photo instantané Instax mini"},
        {"name": "Instax wide", "sku": "MAC-INST-WID", "category": "machines", "price_per_day_cents": _eur_to_cents(50.00), "stock_quantity": 3, "available_quantity": 3, "image_url": "/images/produits/machines/instax_wide_film_cartridge_1.png", "short_description": "Appareil photo instantané Instax wide format panoramique"},
        {"name": "Recharge papier photo Instax mini", "sku": "MAC-RCH-MIN", "category": "machines", "price_per_day_cents": _eur_to_cents(10.00), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/machines/instax_mini_film_cartridge.png", "short_description": "Recharge papier photo format Instax mini (10 photos)"},
        {"name": "Recharge papier photo Instax wide", "sku": "MAC-RCH-WID", "category": "machines", "price_per_day_cents": _eur_to_cents(10.00), "stock_quantity": 15, "available_quantity": 15, "image_url": "/images/produits/machines/instax_wide_film_cartridge_1.png", "short_description": "Recharge papier photo format Instax wide (10 photos)"},
        {"name": "Machine à glaces", "sku": "MAC-GLACE", "category": "machines", "price_per_day_cents": _eur_to_cents(150.00), "deposit_amount_cents": _eur_to_cents(200.00), "stock_quantity": 2, "available_quantity": 2, "image_url": "/images/produits/machines/marveline-produits-machine-a-glaces.jpeg", "short_description": "Machine à glaces italienne professionnelle"},
        {"name": "Recharge 40 glaces", "sku": "MAC-RCH-GLAC", "category": "machines", "price_per_day_cents": _eur_to_cents(25.00), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/machines/ramequin-a-glaces.png", "short_description": "Kit recharge pour 40 glaces (cornets + mix)"},
        {"name": "Coulis chocolat 500ml", "sku": "MAC-COUL-CHO", "category": "machines", "price_per_day_cents": _eur_to_cents(12.00), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/machines/Sauce-au-Chocolat-Noir-Monin-France-67423469371727.png", "short_description": "Coulis chocolat noir Monin 500ml pour machine à glaces"},
        {"name": "Toppings brisures", "sku": "MAC-TOPP-BRI", "category": "machines", "price_per_day_cents": _eur_to_cents(8.00), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/machines/billes-de-crunch-120g.png", "short_description": "Toppings brisures crunch 120g pour glaces"},
        {"name": "Cornet gaufré pour glace", "sku": "MAC-CORN-GAU", "category": "machines", "price_per_day_cents": _eur_to_cents(18.00), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/machines/cornet-gaufre.png", "short_description": "Cornets gaufrés pour machine à glaces (sachet de 50)"},
        {"name": "Chafing dish électrique", "sku": "MAC-CHAF-ELE", "category": "machines", "price_per_day_cents": _eur_to_cents(30.00), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/vaisselle-service/marveline-produits-chafing-dish.jpeg", "short_description": "Chafing dish électrique maintien au chaud buffet"},
        {"name": "Percolateur 100 tasses", "sku": "MAC-PERC-100", "category": "machines", "price_per_day_cents": _eur_to_cents(30.00), "stock_quantity": 3, "available_quantity": 3, "image_url": "/images/produits/vaisselle-service/marveline-produits-percolateur.jpeg", "short_description": "Percolateur professionnel 100 tasses"},

        # ── CANDY BAR ──────────────────────────────────────────────────
        {"name": "Candy bar bois (sans toit)", "sku": "CDB-STD", "category": "candy_bar", "price_per_day_cents": _eur_to_cents(42.00), "stock_quantity": 3, "available_quantity": 3, "image_url": "/images/produits/candy-bar/marveline-produit-candybar-2.jpeg", "short_description": "Candy bar en bois naturel sans toit"},
        {"name": "Candy bar bois (sans toit) avec bonbonnières", "sku": "CDB-STD-BON", "category": "candy_bar", "price_per_day_cents": _eur_to_cents(54.00), "stock_quantity": 3, "available_quantity": 3, "image_url": "/images/produits/candy-bar/marveline-produit-candybar-2.jpeg", "short_description": "Candy bar bois naturel avec set de bonbonnières"},
        {"name": "Candy bar", "sku": "CDB-PREM", "category": "candy_bar", "price_per_day_cents": _eur_to_cents(60.00), "stock_quantity": 2, "available_quantity": 2, "image_url": "/images/produits/candy-bar/marveline-produit-candybar-1.jpeg", "short_description": "Candy bar avec toit et éclairage LED"},
        {"name": "Candy bar avec bonbonnières", "sku": "CDB-PREM-BON", "category": "candy_bar", "price_per_day_cents": _eur_to_cents(75.00), "stock_quantity": 2, "available_quantity": 2, "image_url": "/images/produits/candy-bar/marveline-produit-candybar-1.jpeg", "short_description": "Candy bar avec toit, LED et set de bonbonnières"},
        {"name": "Candy bar Bois/Métal", "sku": "CDB-BOIS-MET", "category": "candy_bar", "price_per_day_cents": _eur_to_cents(75.00), "stock_quantity": 2, "available_quantity": 2, "image_url": "/images/produits/candy-bar/marveline-produits-candy-bar-bois-ceruse.png", "short_description": "Candy bar bois cérusé et métal style industriel"},
        {"name": "Candy bar Bois/Métal avec bonbonnières", "sku": "CDB-BOIS-BON", "category": "candy_bar", "price_per_day_cents": _eur_to_cents(90.00), "stock_quantity": 2, "available_quantity": 2, "image_url": "/images/produits/candy-bar/marveline-produits-candy-bar-bois-ceruse.png", "short_description": "Candy bar bois/métal avec set de bonbonnières"},

        # ── DÉCORATIONS ────────────────────────────────────────────────
        {"name": "Petite étagère en bois", "sku": "DEC-ETG-BOIS", "category": "decorations", "price_per_day_cents": _eur_to_cents(3.60), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/candy-bar/marveline-produits-etagere-bois-2.png", "short_description": "Petite étagère en bois pour candy bar ou décoration"},
        {"name": "Pince à bonbons", "sku": "DEC-PINC-BON", "category": "decorations", "price_per_day_cents": _eur_to_cents(0.36), "stock_quantity": 30, "available_quantity": 30, "image_url": "/images/produits/candy-bar/marveline-produits-pince-bonbons.jpg", "short_description": "Pince à bonbons inox pour candy bar"},
        {"name": "Pelle à bonbons", "sku": "DEC-PELL-BON", "category": "decorations", "price_per_day_cents": _eur_to_cents(0.36), "stock_quantity": 30, "available_quantity": 30, "image_url": "/images/produits/candy-bar/marveline-produits-pelle-bonbons.jpg", "short_description": "Pelle à bonbons inox pour candy bar"},
        {"name": "Bonbonnière 28cl", "sku": "DEC-BONB-28", "category": "decorations", "price_per_day_cents": _eur_to_cents(0.60), "stock_quantity": 20, "available_quantity": 20, "image_url": "/images/produits/candy-bar/marveline-produits-bonbonniere-28cl-1.jpeg", "short_description": "Bonbonnière en verre 28cl avec couvercle"},
        {"name": "Bonbonnière 75cl", "sku": "DEC-BONB-75", "category": "decorations", "price_per_day_cents": _eur_to_cents(1.20), "stock_quantity": 15, "available_quantity": 15, "image_url": "/images/produits/candy-bar/marveline-produits-bonbonniere-75cl-1.jpeg", "short_description": "Bonbonnière en verre 75cl avec couvercle"},
        {"name": "Bonbonnière 1L", "sku": "DEC-BONB-100", "category": "decorations", "price_per_day_cents": _eur_to_cents(1.80), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/candy-bar/marveline-produits-bonbonniere-1L.jpeg", "short_description": "Grande bonbonnière en verre 1L avec couvercle"},

        # ── ACCESSOIRES TRANSPORT ──────────────────────────────────────
        {"name": "Socle rouleur bacs", "sku": "TRP-SOC-BAC", "category": "accessoires_transport", "price_per_day_cents": _eur_to_cents(5.00), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/vaisselle-service/marveline-produits-baquet-60L.jpg", "short_description": "Socle à roulettes pour bacs de transport vaisselle"},
        {"name": "Socle rouleur verres", "sku": "TRP-SOC-VER", "category": "accessoires_transport", "price_per_day_cents": _eur_to_cents(5.00), "stock_quantity": 10, "available_quantity": 10, "image_url": "/images/produits/vaisselle-service/marveline-produits-baquet-60L.jpg", "short_description": "Socle à roulettes pour bacs de transport verres"},
    ]

    for p_data in products:
        if "deposit_amount" not in p_data:
            p_data["deposit_amount"] = 0
        p = Product(tenant_id=TENANT_ID, condition="bon", **p_data)
        db.add(p)

    db.commit()
    total = db.query(Product).filter(Product.tenant_id == TENANT_ID).count()
    print(f"  -> {total} produits créés")


def seed_bundles(db):
    """Crée les formules (bundles) Marveline."""
    existing = db.query(ProductBundle).filter(ProductBundle.tenant_id == TENANT_ID).count()
    if existing > 0:
        print(f"  -> {existing} formules existent déjà, skip.")
        return

    def get_product(sku):
        p = db.query(Product).filter(Product.tenant_id == TENANT_ID, Product.sku == sku).first()
        if not p:
            print(f"    WARN: Produit SKU={sku} non trouvé")
        return p

    # ── FORMULES CLASSIQUES (prix par personne en TTC) ─────────────
    classic_formulas = [
        {
            "name": "Formule Tout Petits",
            "slug": "formule-tout-petits",
            "description": "Formule enfants en bas âge : 1 assiette, 1 gobelet, 3 couverts plastique. Idéal pour les tout-petits lors de mariages et baptêmes.",
            "short_description": "1 assiette + 1 gobelet + 3 couverts (enfants)",
            "bundle_price_cents": _eur_to_cents(1.20),
            "display_order": 1,
            "featured": False,
            "items": [("ENF-ASS", 1), ("ENF-GOB", 1), ("ENF-COU", 1), ("ENF-FOU", 1), ("ENF-CUI", 1)],
        },
        {
            "name": "Formule Enfant 6 pièces",
            "slug": "formule-enfant-6-pieces",
            "description": "Formule enfant complète : 1 verre, 2 assiettes, 3 couverts. Vaisselle gamme classique.",
            "short_description": "1 verre + 2 assiettes + 3 couverts",
            "bundle_price_cents": _eur_to_cents(1.71),
            "display_order": 2,
            "featured": False,
            "items": [("VER-EAU-CLA", 1), ("ASS-RND-CLA-26", 1), ("ASS-RND-CLA-21", 1), ("COV-COU-ELG", 1), ("COV-FOU-ELG", 1), ("COV-CUI-ELG", 1)],
        },
        {
            "name": "Formule 8 pièces",
            "slug": "formule-8-pieces",
            "description": "Formule standard : 3 verres, 2 assiettes, 3 couverts. Verres et assiettes rondes gamme classique, couverts gamme élégance.",
            "short_description": "3 verres + 2 assiettes + 3 couverts",
            "bundle_price_cents": _eur_to_cents(2.26),
            "display_order": 3,
            "featured": True,
            "items": [("VER-EAU-CLA", 1), ("VER-VR-CLA", 1), ("VER-VB-CLA", 1), ("ASS-RND-CLA-26", 1), ("ASS-RND-CLA-21", 1), ("COV-COU-ELG", 1), ("COV-FOU-ELG", 1), ("COV-CUI-ELG", 1)],
        },
        {
            "name": "Formule 12 pièces",
            "slug": "formule-12-pieces",
            "description": "Formule complète : 4 verres, 3 assiettes, 4 couverts, 1 tasse à café. Gamme classique + élégance.",
            "short_description": "4 verres + 3 assiettes + 4 couverts + 1 tasse",
            "bundle_price_cents": _eur_to_cents(3.29),
            "display_order": 4,
            "featured": True,
            "items": [
                ("VER-EAU-CLA", 1), ("VER-VR-CLA", 1), ("VER-VB-CLA", 1), ("VER-FLU-CLA", 1),
                ("ASS-RND-CLA-26", 1), ("ASS-RND-CLA-21", 1), ("ASS-CRS-CLA-22", 1),
                ("COV-COU-ELG", 1), ("COV-FOU-ELG", 1), ("COV-CUI-ELG", 1), ("COV-CAF-ELG", 1),
                ("POR-TAS-CAF", 1),
            ],
        },
        {
            "name": "Formule 15 pièces",
            "slug": "formule-15-pieces",
            "description": "Formule premium : 4 verres, 4 assiettes, 6 couverts, 1 tasse. Service complet avec couvert à dessert.",
            "short_description": "4 verres + 4 assiettes + 6 couverts + 1 tasse",
            "bundle_price_cents": _eur_to_cents(4.08),
            "display_order": 5,
            "featured": False,
            "items": [
                ("VER-EAU-CLA", 1), ("VER-VR-CLA", 1), ("VER-VB-CLA", 1), ("VER-FLU-CLA", 1),
                ("ASS-RND-CLA-26", 1), ("ASS-RND-CLA-21", 1), ("ASS-CRS-CLA-22", 1), ("ASS-RND-CLA-16", 1),
                ("COV-COU-ELG", 1), ("COV-FOU-ELG", 1), ("COV-CUI-ELG", 1),
                ("COV-CDS-ELG", 1), ("COV-FDS-ELG", 1), ("COV-CAF-ELG", 1),
                ("POR-TAS-CAF", 1),
            ],
        },
        {
            "name": "Formule 17 pièces",
            "slug": "formule-17-pieces",
            "description": "Formule grand repas : 5 verres, 4 assiettes, 7 couverts, 1 tasse. Inclut cuillère à dessert.",
            "short_description": "5 verres + 4 assiettes + 7 couverts + 1 tasse",
            "bundle_price_cents": _eur_to_cents(4.59),
            "display_order": 6,
            "featured": False,
            "items": [
                ("VER-EAU-CLA", 1), ("VER-VR-CLA", 1), ("VER-VB-CLA", 1), ("VER-FLU-CLA", 1), ("VER-SOFT-ELG", 1),
                ("ASS-RND-CLA-26", 1), ("ASS-RND-CLA-21", 1), ("ASS-CRS-CLA-22", 1), ("ASS-RND-CLA-16", 1),
                ("COV-COU-ELG", 1), ("COV-FOU-ELG", 1), ("COV-CUI-ELG", 1),
                ("COV-CDS-ELG", 1), ("COV-FDS-ELG", 1), ("COV-CUDS-ELG", 1), ("COV-CAF-ELG", 1),
                ("POR-TAS-CAF", 1),
            ],
        },
        {
            "name": "Formule 20 pièces",
            "slug": "formule-20-pieces",
            "description": "Formule gastronomique : 5 verres, 5 assiettes, 9 couverts, 1 tasse. Le service le plus complet pour les grandes occasions.",
            "short_description": "5 verres + 5 assiettes + 9 couverts + 1 tasse",
            "bundle_price_cents": _eur_to_cents(5.35),
            "display_order": 7,
            "featured": True,
            "items": [
                ("VER-EAU-CLA", 1), ("VER-VR-CLA", 1), ("VER-VB-CLA", 1), ("VER-FLU-CLA", 1), ("VER-SOFT-ELG", 1),
                ("ASS-RND-CLA-26", 1), ("ASS-RND-CLA-21", 1), ("ASS-CRS-CLA-22", 1), ("ASS-RND-CLA-16", 1), ("ASS-RND-CLA-30", 1),
                ("COV-COU-ELG", 1), ("COV-FOU-ELG", 1), ("COV-CUI-ELG", 1),
                ("COV-CDS-ELG", 1), ("COV-FDS-ELG", 1), ("COV-CUDS-ELG", 1),
                ("COV-PSN-ELG", 1), ("COV-FPS-ELG", 1), ("COV-CAF-ELG", 1),
                ("POR-TAS-CAF", 1),
            ],
        },
    ]

    # ── FORMULES VIN D'HONNEUR (prix par lot) ──────────────────────
    vh_formulas = [
        {
            "name": "Vin d'Honneur 50 personnes",
            "slug": "vin-honneur-50",
            "description": "Pack vin d'honneur pour 50 personnes : 98 flûtes à champagne classique et 36 verres à soft. Gobelets enfants inclus.",
            "short_description": "98 flûtes + 36 verres soft (50 pers.)",
            "bundle_price_cents": _eur_to_cents(39.00),
            "display_order": 10,
            "featured": False,
            "items": [("VER-FLU-CLA", 98), ("VER-SOFT-ELG", 36)],
        },
        {
            "name": "Vin d'Honneur 100 personnes",
            "slug": "vin-honneur-100",
            "description": "Pack vin d'honneur pour 100 personnes : 196 flûtes et 72 verres à soft.",
            "short_description": "196 flûtes + 72 verres soft (100 pers.)",
            "bundle_price_cents": _eur_to_cents(78.00),
            "display_order": 11,
            "featured": True,
            "items": [("VER-FLU-CLA", 196), ("VER-SOFT-ELG", 72)],
        },
        {
            "name": "Vin d'Honneur 150 personnes",
            "slug": "vin-honneur-150",
            "description": "Pack vin d'honneur pour 150 personnes : 294 flûtes et 108 verres à soft.",
            "short_description": "294 flûtes + 108 verres soft (150 pers.)",
            "bundle_price_cents": _eur_to_cents(117.00),
            "display_order": 12,
            "featured": False,
            "items": [("VER-FLU-CLA", 294), ("VER-SOFT-ELG", 108)],
        },
        {
            "name": "Vin d'Honneur 200 personnes",
            "slug": "vin-honneur-200",
            "description": "Pack vin d'honneur pour 200 personnes : 343 flûtes et 144 verres à soft.",
            "short_description": "343 flûtes + 144 verres soft (200 pers.)",
            "bundle_price_cents": _eur_to_cents(140.00),
            "display_order": 13,
            "featured": False,
            "items": [("VER-FLU-CLA", 343), ("VER-SOFT-ELG", 144)],
        },
        {
            "name": "Vin d'Honneur 250 personnes",
            "slug": "vin-honneur-250",
            "description": "Pack vin d'honneur pour 250 personnes : 441 flûtes et 180 verres à soft.",
            "short_description": "441 flûtes + 180 verres soft (250 pers.)",
            "bundle_price_cents": _eur_to_cents(180.00),
            "display_order": 14,
            "featured": False,
            "items": [("VER-FLU-CLA", 441), ("VER-SOFT-ELG", 180)],
        },
        {
            "name": "Vin d'Honneur 300 personnes",
            "slug": "vin-honneur-300",
            "description": "Pack vin d'honneur pour 300 personnes : 539 flûtes et 216 verres à soft.",
            "short_description": "539 flûtes + 216 verres soft (300 pers.)",
            "bundle_price_cents": _eur_to_cents(216.00),
            "display_order": 15,
            "featured": False,
            "items": [("VER-FLU-CLA", 539), ("VER-SOFT-ELG", 216)],
        },
    ]

    all_formulas = classic_formulas + vh_formulas

    for f_data in all_formulas:
        items_data = f_data.pop("items")
        featured = f_data.pop("featured", False)
        bundle = ProductBundle(tenant_id=TENANT_ID, featured=featured, **f_data)
        db.add(bundle)
        db.flush()

        order = 0
        for sku, qty in items_data:
            product = get_product(sku)
            if product:
                item = BundleItem(
                    bundle_id=bundle.id,
                    product_id=product.id,
                    quantity=qty,
                    display_order=order,
                    tenant_id=TENANT_ID,
                )
                db.add(item)
                order += 1

    db.commit()
    total = db.query(ProductBundle).filter(ProductBundle.tenant_id == TENANT_ID).count()
    print(f"  -> {total} formules (bundles) créées")


def seed_customers(db):
    """Crée des clients de démonstration."""
    existing = db.query(Customer).filter(Customer.tenant_id == TENANT_ID).count()
    if existing > 0:
        print(f"  -> {existing} clients existent déjà, skip.")
        return

    customers = [
        {
            "customer_type": "individual",
            "first_name": "Marie",
            "last_name": "Dupont",
            "email": "marie.dupont@email.fr",
            "phone": "06 12 34 56 78",
            "address": "15 rue des Fleurs",
            "city": "Beauvais",
            "postal_code": "60000",
        },
        {
            "customer_type": "individual",
            "first_name": "Jean",
            "last_name": "Martin",
            "email": "jean.martin@email.fr",
            "phone": "06 98 76 54 32",
            "address": "42 avenue de la Paix",
            "city": "Compiègne",
            "postal_code": "60200",
        },
        {
            "customer_type": "company",
            "company_name": "Traiteur Picard SARL",
            "email": "contact@traiteur-picard.fr",
            "phone": "03 44 55 66 77",
            "address": "8 zone industrielle Nord",
            "city": "Senlis",
            "postal_code": "60300",
        },
        {
            "customer_type": "company",
            "company_name": "Château de Chantilly Events",
            "email": "events@chateau-chantilly.fr",
            "phone": "03 44 27 31 80",
            "address": "Rue du Connétable",
            "city": "Chantilly",
            "postal_code": "60500",
        },
        {
            "customer_type": "individual",
            "first_name": "Sophie",
            "last_name": "Leroy",
            "email": "sophie.leroy@email.fr",
            "phone": "07 11 22 33 44",
            "address": "23 rue du Château",
            "city": "Clermont",
            "postal_code": "60600",
        },
    ]

    for c_data in customers:
        c = Customer(tenant_id=TENANT_ID, **c_data)
        db.add(c)

    db.commit()
    total = db.query(Customer).filter(Customer.tenant_id == TENANT_ID).count()
    print(f"  -> {total} clients créés")


def _get_product_by_sku(db, sku: str):
    """Récupère un produit par SKU pour le tenant courant."""
    return db.query(Product).filter(
        Product.sku == sku,
        Product.tenant_id == TENANT_ID,
    ).first()



def _ensure_parent_product(db, sku: str, name: str, category_slug: str, price_per_day: int) -> Product:
    """Crée le produit parent si absent ; le retourne dans tous les cas."""
    existing = _get_product_by_sku(db, sku)
    if existing:
        return existing
    parent = Product(
        tenant_id=TENANT_ID,
        sku=sku,
        name=name,
        category=category_slug,
        price_per_day_cents=price_per_day_cents,
        deposit_amount_cents=0,
        stock_quantity=0,
        available_quantity=0,
        condition="bon",
        cleaning_fee_cents=0,
        short_description=f"{name} (géré par variantes)",
    )
    db.add(parent)
    db.flush()
    return parent


def _ensure_variant(db, product_id: int, variant_data: dict) -> bool:
    """Crée une variante si elle n'existe pas (idempotent). Retourne True si créée."""
    exists = db.query(ProductVariant).filter(
        ProductVariant.product_id == product_id,
        ProductVariant.tenant_id == TENANT_ID,
        ProductVariant.label == variant_data["label"],
    ).first()
    if exists:
        return False
    variant = ProductVariant(tenant_id=TENANT_ID, product_id=product_id, **variant_data)
    db.add(variant)
    return True


def seed_variants(db) -> None:
    """Crée les variantes multi-dimensions pour les familles de produits Marveline.

    Familles couvertes :
        - Housses de chaise (couleur)
        - Nappes rondes (couleur)
        - Serviettes coton (couleur)
        - Verres (gamme, via produits parents communs type/gamme)
        - Assiettes rondes classiques (taille)
    """
    existing = db.query(ProductVariant).filter(
        ProductVariant.tenant_id == TENANT_ID
    ).count()
    if existing > 0:
        print(f"  -> {existing} variantes existent déjà, skip.")
        return

    created = 0

    # ── Housses de chaise — couleur ──────────────────────────────────────────
    parent_hou = _ensure_parent_product(db, "HOU-CHA", "Housse de chaise", "housses", _eur_to_cents(2.40))
    for vd in [
        {"label": "Blanche", "color": "blanc", "sku": "HOU-CHA-BLC", "stock_quantity": 200, "available_quantity": 200},
        {"label": "Ivoire",  "color": "ivoire", "sku": "HOU-CHA-IVO", "stock_quantity": 200, "available_quantity": 200},
    ]:
        if _ensure_variant(db, parent_hou.id, vd):
            created += 1

    # ── Nappe ronde 240cm — couleur ──────────────────────────────────────────
    parent_nap240 = _get_product_by_sku(db, "NAP-RND-240") or _ensure_parent_product(
        db, "NAP-RND-240", "Nappe ronde 240cm", "nappes", _eur_to_cents(15.00)
    )
    for vd in [
        {"label": "Blanc", "color": "blanc", "sku": "NAP-RND-240-BLC", "stock_quantity": 20, "available_quantity": 20},
        {"label": "Ivoire", "color": "ivoire", "sku": "NAP-RND-240-IVO-V", "stock_quantity": 15, "available_quantity": 15},
    ]:
        if _ensure_variant(db, parent_nap240.id, vd):
            created += 1

    # ── Serviettes coton blanc/ivoire — couleur ──────────────────────────────
    parent_ser = _ensure_parent_product(db, "SER-COT", "Serviette coton", "serviettes", _eur_to_cents(0.90))
    for vd in [
        {"label": "Blanche", "color": "blanc", "sku": "SER-V-BLC", "stock_quantity": 500, "available_quantity": 500},
        {"label": "Ivoire",  "color": "ivoire", "sku": "SER-V-IVO", "stock_quantity": 500, "available_quantity": 500},
    ]:
        if _ensure_variant(db, parent_ser.id, vd):
            created += 1

    # ── Serviettes couleur — couleur ─────────────────────────────────────────
    parent_ser_col = _ensure_parent_product(db, "SER-COT-COL", "Serviette coton couleur", "serviettes", _eur_to_cents(1.80))
    for vd in [
        {"label": "Bordeaux",   "color": "bordeaux",   "sku": "SER-V-BOR", "stock_quantity": 200, "available_quantity": 200},
        {"label": "Noire",      "color": "noir",        "sku": "SER-V-NOI", "stock_quantity": 200, "available_quantity": 200},
        {"label": "Rouge",      "color": "rouge",       "sku": "SER-V-ROU", "stock_quantity": 200, "available_quantity": 200},
        {"label": "Vert amande","color": "vert_amande", "sku": "SER-V-VAM", "stock_quantity": 150, "available_quantity": 150},
        {"label": "Vert sapin", "color": "vert_sapin",  "sku": "SER-V-VSA", "stock_quantity": 150, "available_quantity": 150},
    ]:
        if _ensure_variant(db, parent_ser_col.id, vd):
            created += 1

    # ── Verre à eau — gamme ──────────────────────────────────────────────────
    parent_ver_eau = _ensure_parent_product(db, "VER-EAU", "Verre à eau", "verres", _eur_to_cents(0.30))
    for vd in [
        {"label": "Classique", "gamme": "classique", "sku": "VER-V-EAU-CLA", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 500, "available_quantity": 500},
        {"label": "Élégance",  "gamme": "elegance",  "sku": "VER-V-EAU-ELG", "price_per_day_cents": _eur_to_cents(0.35), "stock_quantity": 300, "available_quantity": 300},
        {"label": "Open'Up",   "gamme": "open_up",   "sku": "VER-V-EAU-OPN", "price_per_day_cents": _eur_to_cents(0.90), "stock_quantity": 200, "available_quantity": 200},
    ]:
        if _ensure_variant(db, parent_ver_eau.id, vd):
            created += 1

    # ── Verre à vin rouge — gamme ────────────────────────────────────────────
    parent_ver_vr = _ensure_parent_product(db, "VER-VR", "Verre à vin rouge", "verres", _eur_to_cents(0.30))
    for vd in [
        {"label": "Classique", "gamme": "classique", "sku": "VER-V-VR-CLA", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 500, "available_quantity": 500},
        {"label": "Élégance",  "gamme": "elegance",  "sku": "VER-V-VR-ELG", "price_per_day_cents": _eur_to_cents(0.35), "stock_quantity": 300, "available_quantity": 300},
        {"label": "Open'Up",   "gamme": "open_up",   "sku": "VER-V-VR-OPN", "price_per_day_cents": _eur_to_cents(0.90), "stock_quantity": 200, "available_quantity": 200},
    ]:
        if _ensure_variant(db, parent_ver_vr.id, vd):
            created += 1

    # ── Assiette ronde classique — taille ────────────────────────────────────
    parent_ass = _ensure_parent_product(db, "ASS-RND-CLA", "Assiette ronde classique", "assiettes", _eur_to_cents(0.30))
    for vd in [
        {"label": "16cm",   "size": "16cm",   "sku": "ASS-V-RND-CLA-16", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 400, "available_quantity": 400},
        {"label": "21cm",   "size": "21cm",   "sku": "ASS-V-RND-CLA-21", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 400, "available_quantity": 400},
        {"label": "22,5cm", "size": "22.5cm", "sku": "ASS-V-CRS-CLA-22", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 400, "available_quantity": 400},
        {"label": "26cm",   "size": "26cm",   "sku": "ASS-V-RND-CLA-26", "price_per_day_cents": _eur_to_cents(0.30), "stock_quantity": 400, "available_quantity": 400},
        {"label": "30,5cm", "size": "30.5cm", "sku": "ASS-V-RND-CLA-30", "price_per_day_cents": _eur_to_cents(0.42), "stock_quantity": 200, "available_quantity": 200},
    ]:
        if _ensure_variant(db, parent_ass.id, vd):
            created += 1

    db.commit()
    total = db.query(ProductVariant).filter(ProductVariant.tenant_id == TENANT_ID).count()
    print(f"  -> {created} variantes créées ({total} total)")


def main():
    print("=" * 60)
    print("  SEED DATA — Marveline / CaroCorp")
    print("=" * 60)

    with get_db_context() as db:
        print("\n1. Catégories...")
        seed_categories(db)

        print("\n2. Produits...")
        seed_products(db)

        print("\n3. Variantes produit...")
        seed_variants(db)

        print("\n4. Formules (bundles)...")
        seed_bundles(db)

        print("\n5. Clients de démonstration...")
        seed_customers(db)

    print("\n" + "=" * 60)
    print("  SEED TERMINÉ")
    print("=" * 60)


if __name__ == "__main__":
    main()
