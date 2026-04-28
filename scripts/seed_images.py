"""Script d'assignation des images réelles Marveline aux produits, formules et catégories.

Usage (Docker) :
    docker compose exec api python scripts/seed_images.py

Usage (local) :
    python3 scripts/seed_images.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db_context
from app.models.product import Product
from app.models.bundle import ProductBundle
from app.models.category import Category

TENANT_ID = 1
P = "/images/produits"
F = "/images/formules"
C = "/images/categories"

# ---------------------------------------------------------------------------
# SKU → image URL (chemin relatif servi depuis frontend/public/)
# ---------------------------------------------------------------------------
PRODUCT_IMAGES = {
    # ── Assiettes ───────────────────────────────────────────────────────────
    "ASS-CAR-CRS-ELG-23": f"{P}/assiettes/marveline-produits-assiettes-carrees-creuses-elegance.jpeg",
    "ASS-CAR-ELG-23":     f"{P}/assiettes/marveline-produits-assiettes-carrees-elegance.jpeg",
    "ASS-CAR-ELG-27":     f"{P}/assiettes/marveline-produits-assiettes-carrees-elegance.jpeg",
    "ASS-COUSC-26":       f"{P}/assiettes/marveline-produits-assiette-couscous.jpeg",
    "ASS-CRS-CLA-22":     f"{P}/assiettes/marveline-produits-assiette-creuse-classique.jpeg",
    "ASS-CRS-VIN-22":     f"{P}/assiettes/marveline-produits-assiette-creuse-vintage.jpeg",
    "ASS-RND-CLA-16":     f"{P}/assiettes/marveline-produits-assiette-pain.jpeg",
    "ASS-RND-CLA-21":     f"{P}/assiettes/marveline-produits-assiette-cocktail.jpg",
    "ASS-RND-CLA-26":     f"{P}/assiettes/marveline-produits-assiette-creuse-classique.jpeg",
    "ASS-RND-CLA-30":     f"{P}/assiettes/marveline-produits-assiette-creuse-classique.jpeg",
    "ASS-RND-VIN-16":     f"{P}/assiettes/marveline-produits-assiette-vintage.jpg",
    "ASS-RND-VIN-27":     f"{P}/assiettes/marveline-produits-assiette-vintage.jpg",
    "ASS-XCRS-BLC-27":    f"{P}/assiettes/marveline-produits-assiette-extra-creuse-blanche.jpeg",
    # ── Accessoires transport ────────────────────────────────────────────────
    # (pas d'images disponibles – image_url reste None)
    # ── Bancs ───────────────────────────────────────────────────────────────
    "BAN-BOIS":    f"{P}/mobilier/marveline-produits-banc-bois-blanc.png",
    # ── Candy bar ───────────────────────────────────────────────────────────
    "CDB-BOIS-BON": f"{P}/candy-bar/marveline-produits-candy-bar-bois-ceruse.png",
    "CDB-BOIS-MET": f"{P}/candy-bar/marveline-produits-candy-bar-bois-ceruse.png",
    "CDB-PREM":     f"{P}/candy-bar/marveline-produit-candybar-2.jpeg",
    "CDB-PREM-BON": f"{P}/candy-bar/marveline-produit-candybar-2.jpeg",
    "CDB-STD":      f"{P}/candy-bar/marveline-produit-candybar-1.jpeg",
    "CDB-STD-BON":  f"{P}/candy-bar/marveline-produit-candybar-1.jpeg",
    # ── Chaises ─────────────────────────────────────────────────────────────
    "CHA-BOIS-DC": f"{P}/mobilier/marveline-produits-chaise-bois.jpg",
    "CHA-NAP3":    f"{P}/mobilier/marveline-produits-chaise-napoleon.jpg",
    "CHA-PLAST":   f"{P}/mobilier/marveline-produits-chaise.jpeg",
    "CHA-TAB-BAR": f"{P}/mobilier/marveline-produit-tabouret.jpg",
    # ── Couverts ────────────────────────────────────────────────────────────
    "COV-CAF-ELG":  f"{P}/couverts/marveline-produits-cuillere-a-cafe-elegance.jpeg",
    "COV-CDS-ELG":  f"{P}/couverts/marveline-produits-couteau-elegance.jpeg",
    "COV-COU-ELG":  f"{P}/couverts/marveline-produits-couteau-elegance.jpeg",
    "COV-COU-OR":   f"{P}/couverts/marveline-produits-couteau-table-or.png",
    "COV-COU-PRE":  f"{P}/couverts/marveline-produits-couteau-prestige.jpg",
    "COV-CUDS-ELG": f"{P}/couverts/marveline-produits-cuillere-de-table-elegance.jpeg",
    "COV-CUI-ELG":  f"{P}/couverts/marveline-produits-cuillere-de-table-elegance.jpeg",
    "COV-FDS-ELG":  f"{P}/couverts/marveline-produits-fourchette-elegance.jpeg",
    "COV-FOU-ELG":  f"{P}/couverts/marveline-produits-fourchette-elegance.jpeg",
    "COV-FPS-ELG":  f"{P}/couverts/marveline-produits-fourchette-poisson-elegance.jpeg",
    "COV-MOK-ELG":  f"{P}/couverts/marveline-produits-cuillere-a-cafe-elegance.jpeg",
    "COV-PSN-ELG":  f"{P}/couverts/marveline-produits-couteau-poisson-elegance.jpeg",
    "COV-STK-ELG":  f"{P}/couverts/marveline-produits-couteau-steak-elegance.jpeg",
    # ── Décorations ─────────────────────────────────────────────────────────
    "DEC-BONB-100": f"{P}/candy-bar/marveline-produits-bonbonniere-1L.jpeg",
    "DEC-BONB-28":  f"{P}/candy-bar/marveline-produits-bonbonniere-28cl-1.jpeg",
    "DEC-BONB-75":  f"{P}/candy-bar/marveline-produits-bonbonniere-75cl-1.jpeg",
    "DEC-ETG-BOIS": f"{P}/candy-bar/marveline-produits-etagere-bois-2.png",
    "DEC-PELL-BON": f"{P}/candy-bar/marveline-produits-pelle-bonbons.jpg",
    "DEC-PINC-BON": f"{P}/candy-bar/marveline-produits-pince-bonbons.jpg",
    # ── Housses ─────────────────────────────────────────────────────────────
    "HOU-CHA-BLC": f"{P}/nappages/marveline-produits-housse-chaise.jpeg",
    "HOU-CHA-IVO": f"{P}/nappages/marveline-produits-housse-chaise-ivoire.jpeg",
    "HOU-MDB-JUP": f"{P}/nappages/marveline-produits-housse-MD-juponnee.png",
    "HOU-MDB-STD": f"{P}/nappages/marveline-produits-mange-debout-housse-blanche.jpg",
    # ── Machines ────────────────────────────────────────────────────────────
    "MAC-ACC-BORN": f"{P}/machines/marveline-produits-caisse-borne-selfie.jpg",
    "MAC-BORN-SEL": f"{P}/machines/borneselfie_marveline.png",
    "MAC-CHAF-ELE": f"{P}/vaisselle-service/marveline-produits-chafing-dish.jpeg",
    "MAC-CORN-GAU": f"{P}/machines/cornet-gaufre.png",
    "MAC-COUL-CHO": f"{P}/machines/Sauce-au-Chocolat-Noir-Monin-France-67423469371727.png",
    "MAC-GLACE":    f"{P}/machines/marveline-produits-machine-a-glaces.jpeg",
    "MAC-INST-MIN": f"{P}/machines/4547410489071_1.png",
    "MAC-INST-WID": f"{P}/machines/4547410529982_2.png",
    "MAC-PERC-100": f"{P}/vaisselle-service/marveline-produits-percolateur.jpeg",
    "MAC-RCH-GLAC": f"{P}/machines/ramequin-a-glaces.png",
    "MAC-RCH-MIN":  f"{P}/machines/instax_mini_film_cartridge.png",
    "MAC-RCH-WID":  f"{P}/machines/instax_wide_film_cartridge_1.png",
    "MAC-TOPP-BRI": f"{P}/machines/billes-de-crunch-120g.png",
    # ── Mange-debout ────────────────────────────────────────────────────────
    "MDB-STD": f"{P}/mobilier/marveline-produits-mange-debout.jpeg",
    # ── Nappes ──────────────────────────────────────────────────────────────
    "NAP-CAR-250":    f"{P}/nappages/marveline-produits-nappe-carree.jpg",
    "NAP-OVA-240x360": f"{P}/nappages/marveline-produits-nappe-ovale.jpg",
    "NAP-OVA-240x420": f"{P}/nappages/marveline-produits-nappe-ovale.jpg",
    "NAP-OVA-240x480": f"{P}/nappages/marveline-produits-nappe-ovale.jpg",
    "NAP-OVA-240x540": f"{P}/nappages/marveline-produits-nappe-ovale.jpg",
    "NAP-OVA-240x660": f"{P}/nappages/marveline-produits-nappe-ovale.jpg",
    "NAP-REC-140x240": f"{P}/nappages/marveline-produits-nappe-rectangulaire.jpg",
    "NAP-REC-200x240": f"{P}/nappages/marveline-produits-nappe-rectangulaire.jpg",
    "NAP-REC-300x160": f"{P}/nappages/marveline-produits-nappe-rectangulaire.jpg",
    "NAP-REC-300x190": f"{P}/nappages/marveline-produits-nappe-rectangulaire.jpg",
    "NAP-REC-500x190": f"{P}/nappages/marveline-produits-nappe-rectangulaire.jpg",
    "NAP-RND-240":    f"{P}/nappages/marveline-produits-nappe-ronde.jpg",
    # ── Porcelaine ──────────────────────────────────────────────────────────
    "POR-BOL":       f"{P}/porcelaine/marveline-produit-bol.jpeg",
    "POR-MEN-SP-ELG":  f"{P}/porcelaine/marveline-produits-sel-poivre_elegance.jpeg",
    "POR-MEN-SPM-PRE": f"{P}/porcelaine/marveline-produits-menagere-sel-poivre-moutarde.jpeg",
    "POR-MEN-SP-PRE":  f"{P}/porcelaine/marveline-produits-menagere-sel-poivre-prestige.jpeg",
    "POR-MUG":       f"{P}/porcelaine/marveline-produit-mug.jpeg",
    "POR-RAM":       f"{P}/porcelaine/marveline-produits-ramequin-19cl.jpg",
    "POR-SAUC":      f"{P}/porcelaine/marveline-produits-saucier-34cl.jpg",
    "POR-STA-CAF":   f"{P}/porcelaine/marveline-produits-sous-tasse-expresso.jpeg",
    "POR-STA-THE":   f"{P}/porcelaine/marveline-produits-sous-tasse-the.jpeg",
    "POR-SUC-PRE":   f"{P}/porcelaine/marveline-produits-sucrier-prestige.jpeg",
    "POR-TAS-CAF":   f"{P}/porcelaine/marveline-produits-tasse.jpg",
    "POR-TAS-THE":   f"{P}/porcelaine/marveline-produits-tasse.jpg",
    # ── Serviettes ──────────────────────────────────────────────────────────
    "SER-COT-BLC": f"{P}/nappages/marveline-produits-serviette.jpg",
    "SER-COT-BOR": f"{P}/nappages/marveline-produits-serviette.jpg",
    "SER-COT-IVO": f"{P}/nappages/marveline-produits-serviette.jpg",
    "SER-COT-NOI": f"{P}/nappages/marveline-produits-serviette.jpg",
    "SER-COT-ROU": f"{P}/nappages/marveline-produits-serviette.jpg",
    "SER-COT-VAM": f"{P}/nappages/marveline-produits-serviette.jpg",
    "SER-COT-VSA": f"{P}/nappages/marveline-produits-serviette.jpg",
    # ── Tables ──────────────────────────────────────────────────────────────
    "TAB-OVA-12":      f"{P}/mobilier/marveline-produits-table-ovale.jpg",
    "TAB-OVA-14":      f"{P}/mobilier/marveline-produits-table-ovale.jpg",
    "TAB-OVA-16":      f"{P}/mobilier/marveline-produits-table-ovale.jpg",
    "TAB-OVA-18":      f"{P}/mobilier/marveline-produits-table-ovale.jpg",
    "TAB-OVA-22":      f"{P}/mobilier/marveline-produits-table-ovale.jpg",
    "TAB-REC-183":     f"{P}/mobilier/marveline-produits-table-rectangulaire.png",
    "TAB-REC-200":     f"{P}/mobilier/marveline-produits-table-rectangulaire.png",
    "TAB-REC-BOIS-210": f"{P}/mobilier/marveline-produits-table-bois-rectangulaire.jpg",
    "TAB-RND-150":     f"{P}/mobilier/marveline-produits-table-ronde.png",
    "TAB-RND-180":     f"{P}/mobilier/marveline-produits-table-ronde.png",
    "TAB-RND-BOIS-153": f"{P}/mobilier/marveline-produits-table-bois-ronde.jpg",
    # ── Vaisselle enfants ───────────────────────────────────────────────────
    "ENF-ASS": f"{P}/vaisselle-enfants/marveline-produits-assiette-enfant.jpeg",
    "ENF-COU": f"{P}/vaisselle-enfants/marveline-produits-couteau-enfant.jpeg",
    "ENF-CUI": f"{P}/vaisselle-enfants/marveline-produits-cuillere-enfant.jpeg",
    "ENF-FOU": f"{P}/vaisselle-enfants/marveline-produits-fourchette-enfant.jpeg",
    "ENF-GOB": f"{P}/vaisselle-enfants/marveline-produits-gobelet-enfant.jpeg",
    # ── Vaisselle service ───────────────────────────────────────────────────
    "SRV-COP-DES":  f"{P}/vaisselle-service/marveline-produits-coupe-dessert.jpeg",
    "SRV-COU-CHF":  f"{P}/vaisselle-service/marveline-produits-couteau-chef-1.jpeg",
    "SRV-COU-FRO":  f"{P}/vaisselle-service/marveline-produits-couteau-fromage.jpg",
    "SRV-COU-GAT":  f"{P}/vaisselle-service/marveline-produits-couteau-a-gateau.jpeg",
    "SRV-CUI-SRV":  f"{P}/vaisselle-service/marveline-produits-cuillere-service.png",
    "SRV-DIST-JUS": f"{P}/vaisselle-service/marveline-produits-distributeur-jus.jpeg",
    "SRV-FOU-SRV":  f"{P}/vaisselle-service/marveline-produits-fourchette-service.png",
    "SRV-FOU-VIA":  f"{P}/vaisselle-service/marveline-produits-fourchette-service.png",
    "SRV-LOUCHE":   f"{P}/vaisselle-service/marveline-produits-louche.jpg",
    "SRV-PEL-TAR":  f"{P}/vaisselle-service/marveline-produits-pelle-a-tarte.jpg",
    "SRV-PLAT-INX": f"{P}/vaisselle-service/marveline-produits-plateau-de-service-45cm.jpeg",
    "SRV-SEAU-CHP": f"{P}/vaisselle-service/marveline-produits-seau-a-champagne.jpeg",
    "SRV-VASQ-CHP": f"{P}/vaisselle-service/marveline-produits-vasque-champagne.png",
    # ── Verres ──────────────────────────────────────────────────────────────
    "VER-BALL":     f"{P}/verres/marveline-produits-verre-ballon.jpeg",
    "VER-EAU-CLA":  f"{P}/verres/marveline-produits-verre-classique.jpeg",
    "VER-EAU-ELG":  f"{P}/verres/marveline-produits-verre-a-eau-elegance.jpeg",
    "VER-EAU-OPN":  f"{P}/verres/marveline-produits-verre-eau-open-up.jpeg",
    "VER-FLU-CLA":  f"{P}/verres/marveline-produits-flute-classique.jpeg",
    "VER-FLU-ELG":  f"{P}/verres/marveline-produits-flute-elegance.jpeg",
    "VER-FLU-OPN":  f"{P}/verres/marveline-produits-flute-open-up.jpeg",
    "VER-SOFT-ELG": f"{P}/verres/marveline-produits-verre-a-soft-elegance.jpeg",
    "VER-VB-CLA":   f"{P}/verres/marveline-produits-verre-classique.jpeg",
    "VER-VB-ELG":   f"{P}/verres/marveline-produits-verre-a-vin-blanc-elegance.jpeg",
    "VER-VB-OPN":   f"{P}/verres/marveline-produits-verre-vin-blanc-open-up.jpeg",
    "VER-VINT":     f"{P}/verres/marveline-produits-flute-vintage.jpeg",
    "VER-VR-CLA":   f"{P}/verres/marveline-produits-verre-classique.jpeg",
    "VER-VR-ELG":   f"{P}/verres/marveline-produits-verre-a-vin-rouge-elegance.jpeg",
    "VER-VR-OPN":   f"{P}/verres/marveline-produits-verre-vin-rouge-open-up.jpeg",
}

# ---------------------------------------------------------------------------
# Slug formule → image URL
# ---------------------------------------------------------------------------
BUNDLE_IMAGES = {
    "formule-enfant-6-pieces": f"{F}/marveline-formule-enfant.jpg",
    "formule-8-pieces":        f"{F}/marveline-formule-classique-8-pieces.jpg",
    "formule-12-pieces":       f"{F}/marveline-formule-classique-12-pieces.jpg",
    "formule-15-pieces":       f"{F}/marveline-formule-classique-15-pieces.jpg",
    "formule-17-pieces":       f"{F}/marveline-formule-classique-17-pieces.jpg",
    "formule-20-pieces":       f"{F}/marveline-formule-classique-21-pieces.jpg",
    "vin-honneur-50":          f"{F}/marveline-formule-vin-d-honneur.jpg",
    "vin-honneur-100":         f"{F}/marveline-formule-vin-d-honneur.jpg",
    "vin-honneur-150":         f"{F}/marveline-formule-vin-d-honneur.jpg",
    "vin-honneur-200":         f"{F}/marveline-formule-vin-d-honneur.jpg",
    "vin-honneur-250":         f"{F}/marveline-formule-vin-d-honneur.jpg",
    "vin-honneur-300":         f"{F}/marveline-formule-vin-d-honneur.jpg",
    "formule-tout-petits":     f"{F}/marveline-formule-tout-petit.jpg",
}

# ---------------------------------------------------------------------------
# Slug catégorie → image URL
# ---------------------------------------------------------------------------
CATEGORY_IMAGES = {
    "assiettes":       f"{C}/marveline-categorie-assiettes.png",
    "candy_bar":       f"{C}/marveline-categorie-candy-bar.png",
    "chaises":         f"{C}/marveline-categorie-chaises.png",
    "couverts":        f"{C}/marveline-categorie-couverts.png",
    "housses":         f"{C}/marveline-categorie-housses.png",
    "mange_debout":    f"{C}/marveline-categorie-mange-debout.png",
    "nappes":          f"{C}/marveline-categorie-nappes.png",
    "porcelaine":      f"{C}/marveline-categorie-porcelaine.png",
    "serviettes":      f"{C}/marveline-categorie-serviettes.png",
    "tables":          f"{C}/marveline-categorie-tables.png",
    "vaisselle_service": f"{C}/marveline-categorie-vaisselle-de-service.png",
    "vaisselle_enfants": f"{C}/marveline-categorie-vaisselle-enfants.png",
    "verres":          f"{C}/marveline-categorie-verres.png",
}


# SKU courts (produits fusionnes sans variante) -> image par defaut de la gamme
PRODUCT_IMAGES_SHORT = {
    # Assiettes
    "ASS-CAR-ELG":  f"{P}/assiettes/marveline-produits-assiettes-carrees-elegance.jpeg",
    "ASS-RND-CLA":  f"{P}/assiettes/marveline-produits-assiette-creuse-classique.jpeg",
    "ASS-RND-VIN":  f"{P}/assiettes/marveline-produits-assiette-vintage.jpg",
    # Candy bar
    "CDB":          f"{P}/candy-bar/marveline-produit-candybar-1.jpeg",
    # Chaises
    "CHA":          f"{P}/mobilier/marveline-produits-chaise.jpeg",
    # Couverts
    "COV-COU":      f"{P}/couverts/marveline-produits-couteau-elegance.jpeg",
    "COV-CDS":      f"{P}/couverts/marveline-produits-couteau-dessert-or.png",
    "COV-PSN":      f"{P}/couverts/marveline-produits-couteau-poisson-elegance.jpeg",
    "COV-STK":      f"{P}/couverts/marveline-produits-couteau-steak-elegance.jpeg",
    "COV-CAF":      f"{P}/couverts/marveline-produits-cuillere-a-cafe-elegance.jpeg",
    "COV-CUDS":     f"{P}/couverts/marveline-produits-cuillere-dessert-or.png",
    "COV-MOK":      f"{P}/couverts/marveline-produits-cuillere-a-cafe-prestige.jpeg",
    "COV-CUI":      f"{P}/couverts/marveline-produits-cuillere-de-table-elegance.jpeg",
    "COV-FDS":      f"{P}/couverts/marveline-produits-fourchette-dessert-or.png",
    "COV-FPS":      f"{P}/couverts/marveline-produits-fourchette-poisson-elegance.jpeg",
    "COV-FOU":      f"{P}/couverts/marveline-produits-fourchette-elegance.jpeg",
    # Decorations
    "DEC-BONB":     f"{P}/candy-bar/marveline-produits-bonbonniere-1L.jpeg",
    # Housses
    "HOU-CHA":      f"{P}/nappages/marveline-produits-housse-chaise.jpeg",
    "HOU-MDB":      f"{P}/nappages/marveline-produits-housse-MD-juponnee.png",
    # Machines
    "MAC-INST":     f"{P}/machines/4547410489071_1.png",
    "MAC-RCH":      f"{P}/machines/instax_mini_film_cartridge.png",
    # Nappes
    "NAP-OVA":      f"{P}/nappages/marveline-produits-nappe-ovale.jpg",
    "NAP-REC":      f"{P}/nappages/marveline-produits-nappe-rectangulaire.jpg",
    "NAP-RND":      f"{P}/nappages/marveline-produits-nappe-ronde.jpg",
    # Porcelaine
    "POR-MEN-SP":   f"{P}/porcelaine/marveline-produits-menagere-sel-poivre-classique.jpeg",
    "POR-STA":      f"{P}/porcelaine/marveline-produits-sous-tasse-expresso.jpeg",
    "POR-TAS":      f"{P}/porcelaine/marveline-produits-tasse.jpg",
    # Serviettes
    "SER-COT":      f"{P}/nappages/marveline-produits-serviette.jpg",
    "SER-COT-COL":  f"{P}/nappages/marveline-produits-serviette.jpg",
    # Tables
    "TAB-OVA":      f"{P}/mobilier/marveline-produits-table-ovale.jpg",
    "TAB-REC":      f"{P}/mobilier/marveline-produits-table-rectangulaire.png",
    "TAB-RND":      f"{P}/mobilier/marveline-produits-table-ronde.png",
    # Vaisselle enfants
    "ENF":          f"{P}/vaisselle-enfants/marveline-produits-assiette-enfant.jpeg",
    # Vaisselle service
    "SRV-COU":      f"{P}/vaisselle-service/marveline-produits-couteau-chef-1.jpeg",
    "SRV-FOU":      f"{P}/vaisselle-service/marveline-produits-fourchette-service.png",
    # Verres
    "VER-FLU":      f"{P}/verres/marveline-produits-flute-classique.jpeg",
    "VER-EAU":      f"{P}/verres/marveline-produits-verre-a-eau-elegance.jpeg",
    "VER-SOFT":     f"{P}/verres/marveline-produits-verre-a-soft-elegance.jpeg",
    "VER-VB":       f"{P}/verres/marveline-produits-verre-a-vin-blanc-elegance.jpeg",
    "VER-VR":       f"{P}/verres/marveline-produits-verre-a-vin-rouge-elegance.jpeg",
    # Accessoires transport (pas d'image dispo)
    # "TRP-SOC": None,
}


def seed_product_images(db):
    products = db.query(Product).filter(Product.tenant_id == TENANT_ID).all()
    updated = 0
    skipped = 0
    for p in products:
        url = PRODUCT_IMAGES.get(p.sku) or PRODUCT_IMAGES_SHORT.get(p.sku)
        if url:
            p.image_url = url
            updated += 1
        else:
            skipped += 1
    db.commit()
    print(f"  -> {updated} produits mis a jour, {skipped} sans image (SKU non mappe)")


def seed_bundle_images(db):
    bundles = db.query(ProductBundle).filter(ProductBundle.tenant_id == TENANT_ID).all()
    updated = 0
    skipped = 0
    for b in bundles:
        url = BUNDLE_IMAGES.get(b.slug)
        if url:
            b.image_url = url
            updated += 1
        else:
            skipped += 1
    db.commit()
    print(f"  -> {updated} formules mises à jour, {skipped} sans image (slug non mappé)")


def seed_category_images(db):
    cats = db.query(Category).filter(Category.tenant_id == TENANT_ID).all()
    updated = 0
    skipped = 0
    for c in cats:
        url = CATEGORY_IMAGES.get(c.slug)
        if url:
            c.image_url = url
            updated += 1
        else:
            skipped += 1
    db.commit()
    print(f"  -> {updated} catégories mises à jour, {skipped} sans image (slug non mappé)")


def main():
    print("=== Marveline — Assignation des images réelles ===\n")
    with get_db_context() as db:
        print("1. Produits...")
        seed_product_images(db)
        print("2. Formules (bundles)...")
        seed_bundle_images(db)
        print("3. Catégories...")
        seed_category_images(db)
    print("\n=== Terminé ===")


if __name__ == "__main__":
    main()
