#!/usr/bin/env python3
"""
Script pour recréer les plats depuis le fichier Excel Produits_2025_Par_Profil.

Usage:
    docker exec massacorp_api python scripts/recreate_plats_from_excel.py --tenant-id=1
    docker exec massacorp_api python scripts/recreate_plats_from_excel.py --tenant-id=1 --dry-run
"""
import argparse
import csv
import sys
from decimal import Decimal
from collections import defaultdict

sys.path.insert(0, '/app')

from app.core.database import SessionLocal
from app.models.restaurant.plat import RestaurantPlat, RestaurantPlatCategory
from sqlalchemy import text


# Mapping des familles Excel vers les catégories du modèle
FAMILLE_TO_CATEGORY = {
    'Plat_Ailes': 'GRILLADES',
    'Plat_Porc': 'GRILLADES',
    'Plat_Poisson': 'POISSONS',
    'Accompagnement': 'ACCOMPAGNEMENT',
    'Biere_unitaire': 'BIERES',
}

# Mapping manuel pour les produits "Autre" basé sur le nom
def get_category_from_name(name: str) -> str:
    """Détermine la catégorie basée sur le nom du produit."""
    name_upper = name.upper()

    # Boissons alcoolisées
    bieres = ['HEINEKEIN', 'MUTZIG', '33 EXPORT', 'GUINESS', 'LEFFE', 'DESPERADOS',
              'PELFORT', 'BEAUFORT', 'CASTEL', 'ISENBECK', 'KADJI', '1664', 'BOOSTER',
              'GRANDE GUINESS', 'GRANDE LEFFE', 'GRANDE PELFORT', 'GRANDE DESPERADOS',
              'PETITE GUINESS', 'PETITE LEFFE', 'PETITE DESPERADOS']

    whisky = ['JACK DANIEL', 'CHIVAS', 'BLACK LABEL', 'GLENFIDDICH', 'DG',
              '1/2 BLACK', '1/2 CHIVAS', '1/2 JACK', '1/2 GLENFIDDICH', '1/2 VODKA',
              '1/4 BLACK', '1/4 CHIVAS', '1/4 JACK', 'CONSO WHISKY']

    champagne = ['MOET', 'VEUVE CLICOT', 'COUPE MOET', 'COUPE VEUVE', 'RUINART', 'NICOLA',
                 'FORMULE CHAMPAGNE']

    vins = ['VIN ', 'BORDEAUX', 'ROSE', 'MOELLEUX', 'MOYEN VIN', 'VIN BLANC', 'PETIT CD']

    spiritueux = ['VODKA', 'RHUM', 'COGNAC', 'MARTINI', 'COMPARI', 'BALLEYS', 'BAILEYS']

    softs = ['EAU', 'JUS', 'COCA', 'GINGER', 'MALTA', 'TOP', 'REDBULL', 'RED BULL']

    boissons_chaudes = ['CAFE', 'CAFÉ', 'THE', 'THÉ']

    # Plats
    grillades = ['BROCHETTE', 'MECHOUI', 'ROTI', 'RÔTI', 'GESIER', 'GÉSIER', 'ROGNON',
                 'TRIPPES', 'SOYA']

    plats_sauce = ['NDOLE', 'GOMBO', 'MAFE', 'MAFÉ', 'PISTACHE', 'KONDRE', 'KOKI',
                   'LEGUMES SAUTE', 'LÉGUMES SAUTÉ', 'RAGOUT', 'RAGOÛT', 'TARO', 'HERU',
                   'LEGUMES ROYAL', 'LÉGUMES ROYAL']

    bouillons = ['BOUILLON']

    poissons = ['CAPITAINE', 'MAQUEREAU', 'TILAPIA', 'SOLE', 'POISSON', 'GROS CAPTAINE']

    accompagnements = ['SAUCE JAUNE', 'SAUCE TOMATE', 'SALADE', 'BEIGNET']

    # Check categories
    for b in bieres:
        if b in name_upper:
            return 'BIERES'

    for w in whisky:
        if w in name_upper:
            return 'WHISKY'

    for c in champagne:
        if c in name_upper:
            return 'CHAMPAGNE'

    for v in vins:
        if v in name_upper:
            return 'VINS'

    for s in spiritueux:
        if s in name_upper:
            return 'SPIRITUEUX'

    for s in softs:
        if s in name_upper:
            return 'SOFTS'

    for b in boissons_chaudes:
        if b in name_upper:
            return 'BOISSONS_CHAUDES'

    for g in grillades:
        if g in name_upper:
            return 'GRILLADES'

    for p in plats_sauce:
        if p in name_upper:
            return 'PLATS_EN_SAUCE'

    for b in bouillons:
        if b in name_upper:
            return 'BOUILLONS'

    for p in poissons:
        if p in name_upper:
            return 'POISSONS'

    for a in accompagnements:
        if a in name_upper:
            return 'ACCOMPAGNEMENT'

    # Supplements
    if 'SUPPLEMENT' in name_upper or 'SUPPLÉMENTS' in name_upper:
        return 'AUTRE'

    return 'AUTRE'


def parse_price(price_str: str) -> int:
    """Convertit le prix en centimes."""
    if not price_str:
        return 0
    # Remplace la virgule par un point
    price_str = price_str.replace(',', '.').replace('"', '').strip()
    try:
        return int(float(price_str) * 100)
    except ValueError:
        return 0


def extract_products_from_csv(csv_path: str) -> dict:
    """Extrait les produits uniques avec leur prix max et catégorie."""
    products = {}  # name -> {prix_max, famille, count}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('Produit', '').strip()
            if not name:
                continue

            prix = parse_price(row.get('Montant_TTC', '0'))
            famille = row.get('Famille', 'Autre').strip()

            if name not in products:
                products[name] = {
                    'prix_max': prix,
                    'famille': famille,
                    'count': 1
                }
            else:
                products[name]['count'] += 1
                if prix > products[name]['prix_max']:
                    products[name]['prix_max'] = prix

    return products


def recreate_plats(db, tenant_id: int, products: dict, dry_run: bool = False) -> dict:
    """Recrée les plats à partir des produits extraits."""
    stats = {
        'deleted': 0,
        'created': 0,
        'by_category': defaultdict(int),
        'errors': []
    }

    if not dry_run:
        # Supprimer les plats existants
        existing_count = db.execute(
            text("SELECT COUNT(*) FROM restaurant_plats WHERE tenant_id = :tid"),
            {"tid": tenant_id}
        ).scalar()

        # D'abord supprimer les plat_ingredients
        db.execute(
            text("""
                DELETE FROM restaurant_plat_ingredients
                WHERE plat_id IN (SELECT id FROM restaurant_plats WHERE tenant_id = :tid)
            """),
            {"tid": tenant_id}
        )

        # Puis supprimer les plats
        db.execute(
            text("DELETE FROM restaurant_plats WHERE tenant_id = :tid"),
            {"tid": tenant_id}
        )
        stats['deleted'] = existing_count
        print(f"[DELETE] {existing_count} plats existants supprimés")
    else:
        existing_count = db.execute(
            text("SELECT COUNT(*) FROM restaurant_plats WHERE tenant_id = :tid"),
            {"tid": tenant_id}
        ).scalar()
        print(f"[DRY-RUN] Supprimerais {existing_count} plats existants")

    # Créer les nouveaux plats
    for name, data in sorted(products.items()):
        famille = data['famille']
        prix = data['prix_max']

        # Déterminer la catégorie
        if famille in FAMILLE_TO_CATEGORY:
            category = FAMILLE_TO_CATEGORY[famille]
        else:
            category = get_category_from_name(name)

        # Vérifier que la catégorie existe dans l'enum
        try:
            cat_enum = RestaurantPlatCategory(category)
        except ValueError:
            stats['errors'].append(f"{name}: catégorie '{category}' invalide")
            category = 'AUTRE'

        if dry_run:
            print(f"[DRY-RUN] Créerais: {name} | {prix/100:.2f}€ | {category} (ventes: {data['count']})")
        else:
            # Utiliser SQL brut pour éviter les problèmes d'enum
            db.execute(
                text("""
                    INSERT INTO restaurant_plats
                    (tenant_id, name, category, prix_vente, is_active, is_menu,
                     type_plat, est_composable, ajout_sauce_tomate)
                    VALUES
                    (:tenant_id, :name, :category, :prix_vente, true, false,
                     'SIMPLE', false, false)
                """),
                {
                    "tenant_id": tenant_id,
                    "name": name,
                    "category": category,
                    "prix_vente": prix,
                }
            )
            print(f"[CREATED] {name} | {prix/100:.2f}€ | {category}")

        stats['created'] += 1
        stats['by_category'][category] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description='Recréer les plats depuis Excel')
    parser.add_argument('--tenant-id', type=int, required=True, help='ID du tenant')
    parser.add_argument('--dry-run', action='store_true', help='Simulation')
    parser.add_argument('--csv-path', type=str,
                        default='/tmp/Produits_2025_Par_Profil.csv',
                        help='Chemin vers le fichier CSV')

    args = parser.parse_args()

    # Extraire les produits
    print(f"=== Extraction des produits depuis {args.csv_path} ===")
    products = extract_products_from_csv(args.csv_path)
    print(f"Produits uniques trouvés: {len(products)}")
    print()

    db = SessionLocal()

    try:
        print(f"=== Recréation des plats (tenant={args.tenant_id}) ===")
        if args.dry_run:
            print("[MODE DRY-RUN]")
        print()

        stats = recreate_plats(db, args.tenant_id, products, args.dry_run)

        if not args.dry_run:
            db.commit()
            print()
            print("Commit effectué.")

        print()
        print("=== RESUME ===")
        print(f"Plats supprimés: {stats['deleted']}")
        print(f"Plats créés: {stats['created']}")
        print()
        print("Par catégorie:")
        for cat, count in sorted(stats['by_category'].items()):
            print(f"  {cat}: {count}")

        if stats['errors']:
            print()
            print("Erreurs:")
            for err in stats['errors']:
                print(f"  ! {err}")

    except Exception as e:
        print(f"ERREUR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
