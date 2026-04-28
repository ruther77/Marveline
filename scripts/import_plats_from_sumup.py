#!/usr/bin/env python3
"""
Import des plats/produits depuis les rapports Sumup vers restaurant_plats.

Analyse les rapports de commandes Sumup pour extraire tous les produits uniques
avec leurs prix moyens et les importer dans la base de données.

Usage:
    docker exec massacorp_api python /app/scripts/import_plats_from_sumup.py --tenant-id=1
"""

import sys
import csv
import logging
import argparse
from pathlib import Path
from decimal import Decimal
from collections import defaultdict
from typing import Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mapping des catégories basé sur les noms de produits
CATEGORY_MAPPING = {
    # Grillades
    "AILES DE POULET": "GRILLADES",
    "DEMI PLAT AILES": "GRILLADES",
    "AILES DE POULET RIZ": "GRILLADES",
    "COTELETTE DE PORC BRAISE": "GRILLADES",
    "BROCHETTES DE VIANDES": "GRILLADES",
    "BROCHETTES DE CREVETTES": "GRILLADES",
    "CUISSES DE POULET": "GRILLADES",
    "PORC RIZ": "GRILLADES",
    "Rôti porc": "GRILLADES",
    "Rognon sautée": "GRILLADES",
    "TRIPPES SAUTEES": "GRILLADES",
    "SOYA": "GRILLADES",

    # Poissons
    "MAQUEREAU PM": "POISSONS",
    "MAQUEREAU GROS": "POISSONS",
    "CAPITAINE PM": "POISSONS",
    "GROS CAPTAINE": "POISSONS",
    "TILAPIA": "POISSONS",
    "SOLE PM": "POISSONS",
    "SOLE GROS": "POISSONS",
    "BOUILLON DE POISSON": "BOUILLONS",
    "BOUILLON QUEUE DE B": "BOUILLONS",

    # Plats en sauce (déjà existants, mais vérifier)
    "HERU": "PLATS_EN_SAUCE",
    "NDOLE": "PLATS_EN_SAUCE",
    "GOMBO": "PLATS_EN_SAUCE",
    "TARO": "PLATS_EN_SAUCE",
    "KOKI": "PLATS_EN_SAUCE",
    "KONDRE": "PLATS_EN_SAUCE",
    "MAFE": "PLATS_EN_SAUCE",
    "PISTACHE": "PLATS_EN_SAUCE",
    "SAUCE JAUNE": "ACCOMPAGNEMENT",
    "SAUCE TOMATE": "PLATS_EN_SAUCE",
    "LEGUMES SAUTES": "PLATS_EN_SAUCE",

    # Bières
    "HEINEKEIN": "BIERES",
    "GUINESS": "BIERES",
    "PETITE GUINESS": "BIERES",
    "GRANDE GUINESS": "BIERES",
    "LEFFE": "BIERES",
    "GRANDE LEFFE": "BIERES",
    "PETITE LEFFE": "BIERES",
    "1664": "BIERES",
    "DESPERADOS": "BIERES",
    "PETITE DESPERADOS": "BIERES",
    "GRANDE DESPERADOS": "BIERES",
    "MUTZIG": "BIERES",
    "CASTEL": "BIERES",
    "33 EXPORT": "BIERES",
    "Isenbeck": "BIERES",
    "Kadji beer": "BIERES",
    "PELFORT": "BIERES",
    "Pelfort": "BIERES",
    "MALTA": "BIERES",
    "TOP": "BIERES",

    # Whiskies
    "Glenfiddich": "WHISKIES",
    "1/2 Glenfiddich": "WHISKIES",
    "JACK DANIEL": "WHISKIES",
    "1/4 JACK DANIEL": "WHISKIES",
    "1/2 JACK DANIEL": "WHISKIES",
    "CHIVAS": "WHISKIES",
    "1/4 CHIVAS": "WHISKIES",
    "BLACK LABEL": "WHISKIES",
    "1/4 BLACK LABEL": "WHISKIES",
    "Conso whisky": "WHISKIES",

    # Vins
    "Vin": "VINS",
    "VIN BLANC": "VINS",
    "MOYEN VIN": "VINS",
    "BORDEAUX": "VINS",
    "ROSE": "VINS",
    "MOELLEUX": "VINS",

    # Champagnes
    "VEUVE CLICOT": "CHAMPAGNES",
    "MOET": "CHAMPAGNES",

    # Softs
    "Coca": "SOFTS",
    "JUS": "SOFTS",
    "Booster": "SOFTS",
    "Redbull": "SOFTS",
    "Ginger": "SOFTS",
    "EAU": "SOFTS",
    "EAU GAZEUSE": "SOFTS",
    "PETIT CD": "SOFTS",

    # Alcools divers
    "COGNAC CONSO": "DIGESTIFS",
    "COMPARI CONSO": "APERITIFS",
    "BALLEYS CONSO": "DIGESTIFS",
    "RHUM CONSO": "RHUMS",
    "MARTINI CONSO": "APERITIFS",

    # Café
    "café": "CAFES",

    # Suppléments
    "Supplements": "SUPPLEMENT",
}


def detect_category(product_name: str) -> str:
    """
    Détecte la catégorie d'un produit basé sur son nom.
    Catégories valides: ENTREE, PLAT, DESSERT, BOISSON, MENU, ACCOMPAGNEMENT, AUTRE
    """
    name_upper = product_name.upper()

    # Détection des boissons
    if any(x in name_upper for x in [
        "HEINEKEIN", "GUINESS", "LEFFE", "1664", "DESPERADOS", "MUTZIG", "CASTEL",
        "MALTA", "TOP", "PELFORT", "ISENBECK", "KADJI", "33 EXPORT", "BIERE", "BEER"
    ]):
        return "BOISSON"

    if any(x in name_upper for x in [
        "GLENFIDDICH", "JACK DANIEL", "CHIVAS", "BLACK LABEL", "WHISKY", "WHISKEY",
        "COGNAC", "RHUM", "VODKA", "MARTINI", "COMPARI", "BALLEYS", "CONSO"
    ]):
        return "BOISSON"

    if any(x in name_upper for x in ["VIN", "BORDEAUX", "ROSE", "MOELLEUX", "BLANC"]):
        return "BOISSON"

    if any(x in name_upper for x in ["VEUVE CLICOT", "MOET", "CHAMPAGNE", "RUINART"]):
        return "BOISSON"

    if any(x in name_upper for x in ["COCA", "JUS", "EAU", "BOOSTER", "REDBULL", "GINGER", "PETIT CD", "SOFT"]):
        return "BOISSON"

    if any(x in name_upper for x in ["CAFÉ", "CAFE"]):
        return "BOISSON"

    # Détection des plats
    if any(x in name_upper for x in [
        "AILES", "COTELETTE", "BROCHETTE", "POULET", "PORC", "VIANDE", "BOEUF",
        "SOYA", "TRIPPES", "ROTI", "ROGNON", "CUISSES", "GESIER"
    ]):
        return "PLAT"

    if any(x in name_upper for x in [
        "MAQUEREAU", "CAPITAINE", "TILAPIA", "SOLE", "POISSON"
    ]):
        return "PLAT"

    if any(x in name_upper for x in [
        "BOUILLON"
    ]):
        return "ENTREE"

    if any(x in name_upper for x in [
        "HERU", "NDOLE", "GOMBO", "TARO", "KOKI", "KONDRE", "MAFE", "PISTACHE",
        "SAUCE JAUNE", "SAUCE TOMATE", "LEGUMES"
    ]):
        return "PLAT"

    if any(x in name_upper for x in ["SALADE"]):
        return "ENTREE"

    if any(x in name_upper for x in ["SUPPLEMENT", "SUPPL"]):
        return "ACCOMPAGNEMENT"

    if any(x in name_upper for x in ["BEIGNET", "OEUF"]):
        return "ACCOMPAGNEMENT"

    return "AUTRE"


def parse_sumup_csv(csv_path: Path) -> Dict[str, Dict]:
    """
    Parse le CSV Sumup et retourne un dict de produits avec leurs stats.

    Returns:
        Dict[nom_produit] = {
            'count': nombre de ventes,
            'prices': liste des prix observés,
            'avg_price': prix moyen
        }
    """
    products = defaultdict(lambda: {'count': 0, 'prices': []})

    with open(csv_path, 'r', encoding='utf-8') as f:
        # Le CSV utilise ; comme séparateur
        reader = csv.DictReader(f, delimiter=';')

        for row in reader:
            product_name = row.get('Produit', '').strip().strip('"')
            if not product_name:
                continue

            # Extraire le prix
            price_str = row.get('Prix ​​unitaire TTC', '0').replace(',', '.').strip().strip('"')
            try:
                price = float(price_str)
            except ValueError:
                price = 0.0

            # Extraire la quantité
            qty_str = row.get('Quantité', '1').strip().strip('"')
            try:
                qty = int(qty_str)
            except ValueError:
                qty = 1

            products[product_name]['count'] += qty
            if price > 0:
                products[product_name]['prices'].append(price)

    # Calculer les prix moyens et max
    for name, data in products.items():
        if data['prices']:
            data['avg_price'] = sum(data['prices']) / len(data['prices'])
            data['max_price'] = max(data['prices'])
        else:
            data['avg_price'] = 0
            data['max_price'] = 0

    return products


def import_products_to_db(products: Dict[str, Dict], tenant_id: int, dry_run: bool = False) -> Dict[str, int]:
    """Import les produits dans restaurant_plats."""
    try:
        sys.path.insert(0, '/app')
        from sqlalchemy import text
        from app.core.database import SessionLocal
    except ImportError:
        logger.error("Script disponible uniquement depuis le container API")
        sys.exit(1)

    db = SessionLocal()
    stats = {
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0,
    }

    try:
        # Récupérer les plats existants
        existing = db.execute(
            text("SELECT id, name, prix_vente FROM restaurant_plats WHERE tenant_id = :tid"),
            {"tid": tenant_id}
        ).fetchall()

        existing_names = {row[1].upper(): (row[0], row[2]) for row in existing}
        logger.info(f"Plats existants: {len(existing_names)}")

        for product_name, data in sorted(products.items(), key=lambda x: -x[1]['count']):
            # Ignorer les produits avec peu de ventes
            if data['count'] < 5:
                continue

            category = detect_category(product_name)
            price_cents = int(data['max_price'] * 100)  # Utiliser le prix max comme prix de vente

            # Vérifier si existe déjà
            name_upper = product_name.upper()

            if name_upper in existing_names:
                existing_id, existing_price = existing_names[name_upper]

                # Mettre à jour si le prix est différent
                if price_cents != existing_price and price_cents > 0:
                    if not dry_run:
                        db.execute(
                            text("""
                                UPDATE restaurant_plats
                                SET prix_vente = :prix, category = :cat, updated_at = NOW()
                                WHERE id = :id
                            """),
                            {"prix": price_cents, "cat": category, "id": existing_id}
                        )
                    stats['updated'] += 1
                    logger.debug(f"Mis à jour: {product_name} ({price_cents/100:.2f}€, {category})")
                else:
                    stats['skipped'] += 1
            else:
                # Créer le plat
                if price_cents == 0:
                    logger.warning(f"Ignoré (prix 0): {product_name}")
                    stats['skipped'] += 1
                    continue

                if not dry_run:
                    try:
                        db.execute(
                            text("""
                                INSERT INTO restaurant_plats (
                                    tenant_id, name, category, prix_vente,
                                    is_active, is_menu, type_plat,
                                    created_at, updated_at
                                ) VALUES (
                                    :tid, :name, :cat, :prix,
                                    true, false, :type_plat,
                                    NOW(), NOW()
                                )
                            """),
                            {
                                "tid": tenant_id,
                                "name": product_name,
                                "cat": category,
                                "prix": price_cents,
                                "type_plat": "BOISSON" if category == "BOISSON" else "SIMPLE",
                            }
                        )
                        stats['created'] += 1
                        logger.info(f"Créé: {product_name} ({price_cents/100:.2f}€, {category}) - {data['count']} ventes")
                    except Exception as e:
                        logger.error(f"Erreur création {product_name}: {e}")
                        stats['errors'] += 1
                else:
                    stats['created'] += 1
                    logger.info(f"[DRY-RUN] Créerait: {product_name} ({price_cents/100:.2f}€, {category}) - {data['count']} ventes")

        if not dry_run:
            db.commit()

    except Exception as e:
        logger.error(f"Erreur import: {e}")
        db.rollback()
        raise
    finally:
        db.close()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Import plats depuis Sumup")
    parser.add_argument("--csv-path", help="Chemin vers le CSV Sumup",
                       default="/app/docs/releve/Sumup/rapport-de-commandes-2023-11-08_2025-11-08/rapport-de-commandes-produits-2023-11-08_2025-11-08.csv")
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true", help="Mode simulation")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        logger.error(f"Fichier non trouvé: {csv_path}")
        sys.exit(1)

    logger.info(f"Parsing {csv_path}...")
    products = parse_sumup_csv(csv_path)
    logger.info(f"Produits uniques trouvés: {len(products)}")

    # Afficher les tops
    print("\n=== TOP 20 PRODUITS PAR VENTES ===")
    for name, data in sorted(products.items(), key=lambda x: -x[1]['count'])[:20]:
        cat = detect_category(name)
        print(f"  {data['count']:5d}x {name:40s} ({data['max_price']:6.2f}€) [{cat}]")

    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Import dans la base...")
    stats = import_products_to_db(products, args.tenant_id, args.dry_run)

    print(f"\n=== RÉSULTAT ===")
    print(f"Créés: {stats['created']}")
    print(f"Mis à jour: {stats['updated']}")
    print(f"Ignorés: {stats['skipped']}")
    print(f"Erreurs: {stats['errors']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
