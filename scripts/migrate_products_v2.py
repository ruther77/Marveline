"""
Migration v2 : restructurer le catalogue produits.
- Créer les parents manquants
- Convertir les doublons/standalone en variantes des parents
- Migrer stock_items
- Désactiver les anciens produits
- Supprimer les produits test

Usage :
  docker compose exec api python scripts/migrate_products_v2.py --dry-run
  docker compose exec api python scripts/migrate_products_v2.py --apply
"""
import asyncio
import sys
from sqlalchemy import select, func, text, update
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, "/app")
from app.core.database import AsyncSessionLocal
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.stock_item import StockItem

TENANT_ID = 1
DRY_RUN = "--apply" not in sys.argv

# ═══════════════════════════════════════════════════════════════════════════════
# PLAN DE MIGRATION
# Format : (parent_sku, parent_name, category, [(child_id, variant_label)])
# Si child_id est un produit existant, on le convertit en variante du parent.
# Si le parent existe déjà (id connu), on utilise son id.
# ═══════════════════════════════════════════════════════════════════════════════

MIGRATIONS = [
    # ── VERRES (parents existent déjà : 150, 151, 168, 169, 170) ──
    # Doublons à fusionner dans les parents existants
    ("VER-EAU", None, None, [
        (4, "Classique"),   # VER-EAU-CLA
        (8, "Élégance"),    # VER-EAU-ELG
        (12, "Open'Up"),    # VER-EAU-OPN
    ]),
    ("VER-VR", None, None, [
        (5, "Classique"),   # VER-VR-CLA
        (9, "Élégance"),    # VER-VR-ELG
        (13, "Open'Up"),    # VER-VR-OPN
    ]),

    # ── ASSIETTES (parents existent : 152 ASS-RND-CLA) ──
    ("ASS-RND-CLA", None, None, [
        (19, "16cm"),       # ASS-RND-CLA-16
        (20, "21cm"),       # ASS-RND-CLA-21
        (21, "22,5cm"),     # ASS-CRS-CLA-22 → creuse mais même famille
        (22, "26cm"),       # ASS-RND-CLA-26
        (23, "30,5cm"),     # ASS-RND-CLA-30
    ]),

    # ── HOUSSES ──
    ("HOU-CHA", None, None, [
        (92, "Blanche"),    # HOU-CHA-BLC
        (93, "Ivoire"),     # HOU-CHA-IVO
    ]),
    ("HOU-MDB", "Housse mange-debout", "housses", [
        (94, "Standard"),   # HOU-MDB-STD
        (95, "Juponnée"),   # HOU-MDB-JUP
    ]),

    # ── SERVIETTES (parents existent : 148 SER-COT, 149 SER-COT-COL) ──
    ("SER-COT", None, None, [
        (113, "Blanche"),   # SER-COT-BLC
        (114, "Ivoire"),    # SER-COT-IVO
        (115, "Bordeaux"),  # SER-COT-BOR
        (116, "Noire"),     # SER-COT-NOI
        (117, "Rouge"),     # SER-COT-ROU
        (118, "Vert amande"), # SER-COT-VAM
        (119, "Vert sapin"), # SER-COT-VSA
    ]),

    # ── NAPPES ──
    ("NAP-RND-240", None, None, [
        (112, "Ivoire"),    # NAP-RND-240-IVO (doublon)
    ]),
    ("NAP-OVA", "Nappe coton ovale", "nappes", [
        (103, "240x360cm"),
        (104, "240x420cm"),
        (105, "240x480cm"),
        (106, "240x540cm"),
        (107, "240x660cm"),
    ]),
    ("NAP-REC", "Nappe coton rectangulaire", "nappes", [
        (96, "140x240cm"),
        (97, "200x240cm"),
        (98, "300x160cm"),
        (99, "300x190cm"),
        (100, "500x190cm"),
        (111, "300x175cm ivoire"),
    ]),
    ("NAP-RND", "Nappe coton ronde", "nappes", [
        (108, "280cm"),
        (109, "280cm couleur"),
        (110, "300cm"),
    ]),

    # ── COUVERTS ──
    ("COV-COU", "Couteau de table", "couverts", [
        (32, "Élégance"),   # COV-COU-ELG
        (44, "Or"),         # COV-COU-OR
        (43, "Prestige"),   # COV-COU-PRE
    ]),
    ("COV-FOU", "Fourchette de table", "couverts", [
        (33, "Élégance"),
    ]),
    ("COV-CUI", "Cuillère de table", "couverts", [
        (34, "Élégance"),
    ]),
    ("COV-STK", "Couteau à steak", "couverts", [
        (35, "Élégance"),
    ]),
    ("COV-PSN", "Couteau à poisson", "couverts", [
        (36, "Élégance"),
    ]),
    ("COV-FPS", "Fourchette à poisson", "couverts", [
        (37, "Élégance"),
    ]),
    ("COV-CDS", "Couteau à dessert", "couverts", [
        (38, "Élégance"),
    ]),
    ("COV-FDS", "Fourchette à dessert", "couverts", [
        (39, "Élégance"),
    ]),
    ("COV-CUDS", "Cuillère à dessert", "couverts", [
        (40, "Élégance"),
    ]),
    ("COV-CAF", "Cuillère à café", "couverts", [
        (41, "Élégance"),
    ]),
    ("COV-MOK", "Cuillère à moka", "couverts", [
        (42, "Élégance"),
    ]),

    # ── TABLES ──
    ("TAB-OVA", "Table ovale", "tables", [
        (81, "12 personnes"),
        (82, "14 personnes"),
        (83, "16 personnes"),
        (84, "18 personnes"),
        (85, "22 personnes"),
    ]),
    ("TAB-REC", "Table rectangulaire", "tables", [
        (75, "183x76cm"),
        (76, "200x90cm"),
        (80, "Bois 210x100cm"),
    ]),
    ("TAB-RND", "Table ronde", "tables", [
        (77, "150cm"),
        (78, "180cm"),
        (79, "Bois 153cm"),
    ]),

    # ── CHAISES ──
    ("CHA", "Chaise", "chaises", [
        (87, "Napoléon III"),
        (86, "Plastique"),
        (88, "Bois Dos Croisé"),
    ]),

    # ── CANDY BAR ──
    ("CDB", "Candy bar", "candy_bar", [
        (133, "Bois sans toit"),
        (134, "Bois sans toit + bonbonnières"),
        (135, "Premium"),
        (136, "Premium + bonbonnières"),
        (137, "Bois/Métal"),
        (138, "Bois/Métal + bonbonnières"),
    ]),

    # ── DÉCORATIONS ──
    ("DEC-BONB", "Bonbonnière", "decorations", [
        (142, "28cl"),
        (143, "75cl"),
        (144, "1L"),
    ]),

    # ── PORCELAINE ──
    ("POR-MEN-SP", "Ménagère sel/poivre", "porcelaine", [
        (58, "Élégance"),
        (59, "Prestige"),
    ]),
    ("POR-TAS", "Tasse", "porcelaine", [
        (61, "Café"),
        (63, "Thé"),
    ]),
    ("POR-STA", "Sous-tasse", "porcelaine", [
        (62, "Café"),
        (64, "Thé"),
    ]),

    # ── MACHINES ──
    ("MAC-INST", "Instax", "machines", [
        (122, "Mini"),
        (123, "Wide"),
    ]),
    ("MAC-RCH", "Recharge", "machines", [
        (124, "Instax mini"),
        (125, "Instax wide"),
        (127, "40 glaces"),
    ]),

    # ── VAISSELLE SERVICE ──
    ("SRV-COU", "Couteau de service", "vaisselle_service", [
        (52, "Chef"),
        (50, "Fromage"),
        (51, "Gâteau"),
    ]),
    ("SRV-FOU", "Fourchette de service", "vaisselle_service", [
        (47, "Standard"),
        (48, "Viande"),
    ]),

    # ── ACCESSOIRES TRANSPORT ──
    ("TRP-SOC", "Socle rouleur", "accessoires_transport", [
        (145, "Bacs"),
        (146, "Verres"),
    ]),

    # ── VAISSELLE ENFANT ──
    ("ENF", "Vaisselle enfant", "vaisselle_enfants", [
        (71, "Assiette"),
        (70, "Gobelet"),
        (72, "Couteau"),
        (73, "Fourchette"),
        (74, "Cuillère"),
    ]),
]

# Produits à supprimer (test)
DELETE_IDS = [173, 174]  # SKU-CURL-002, SKU-FIX-GREENLET-001


async def migrate(db: AsyncSession):
    print(f"\n{'='*60}")
    print(f"  {'DRY RUN' if DRY_RUN else 'APPLYING'} — Migration catalogue v2")
    print(f"{'='*60}\n")

    created_parents = 0
    migrated_children = 0
    migrated_stock_items = 0

    # Pré-traitement : renommer les enfants qui vont être migrés pour éviter
    # les conflits de nom unique avec les futurs parents
    if not DRY_RUN:
        all_child_ids = set()
        for _, _, _, children in MIGRATIONS:
            for child_id, _ in children:
                all_child_ids.add(child_id)
        for cid in all_child_ids:
            await db.execute(
                text("UPDATE products SET name = name || ' [migrating]' WHERE id = :id AND tenant_id = :tid AND name NOT LIKE '%[%'"),
                {"id": cid, "tid": TENANT_ID},
            )
        await db.flush()

    for parent_sku, parent_name, parent_category, children in MIGRATIONS:
        # 1. Trouver ou créer le parent
        result = await db.execute(
            select(Product).where(
                Product.sku == parent_sku,
                Product.tenant_id == TENANT_ID,
                Product.is_active == True,
            )
        )
        parent = result.scalars().first()

        if not parent and parent_name:
            # Prendre le premier enfant comme modèle pour les champs manquants
            first_child = await db.get(Product, children[0][0])
            print(f"  [CREATE PARENT] {parent_name} (SKU={parent_sku}, cat={parent_category})")
            if not DRY_RUN:
                parent = Product(
                    tenant_id=TENANT_ID,
                    name=parent_name,
                    sku=parent_sku,
                    category=parent_category,
                    price_per_day_cents=first_child.price_per_day if first_child else 0,
                    deposit_amount_cents=first_child.deposit_amount if first_child else 0,
                    stock_quantity=0,
                    available_quantity=0,
                    is_active=True,
                    condition=first_child.condition if first_child else "new",
                    tva_rate=first_child.tva_rate if first_child else 0.20,
                )
                db.add(parent)
                await db.flush()
            created_parents += 1
        elif not parent:
            print(f"  [SKIP] Parent {parent_sku} non trouvé et pas de nom pour créer")
            continue

        if DRY_RUN and not parent:
            print(f"  [DRY] Parent {parent_sku} → {parent_name} serait créé")
            for child_id, variant_label in children:
                child = await db.get(Product, child_id)
                if child:
                    si_count = await db.scalar(
                        select(func.count(StockItem.id)).where(
                            StockItem.product_id == child_id, StockItem.tenant_id == TENANT_ID
                        )
                    )
                    print(f"    ├── {variant_label} ← {child.name} (id={child_id}, {si_count} stock_items)")
            continue

        parent_id = parent.id if parent else 0

        # 2. Pour chaque enfant, créer la variante et migrer
        for child_id, variant_label in children:
            child = await db.get(Product, child_id)
            if not child:
                print(f"    [WARN] Produit {child_id} non trouvé")
                continue

            # Vérifier si la variante existe déjà sur le parent
            existing_var = await db.execute(
                select(ProductVariant).where(
                    ProductVariant.product_id == parent_id,
                    ProductVariant.label == variant_label,
                    ProductVariant.tenant_id == TENANT_ID,
                    ProductVariant.is_active == True,
                )
            )
            variant = existing_var.scalars().first()

            si_count = await db.scalar(
                select(func.count(StockItem.id)).where(
                    StockItem.product_id == child_id, StockItem.tenant_id == TENANT_ID
                )
            )

            if variant:
                print(f"    [EXIST] {variant_label} (variant={variant.id}) ← merge {child.name} ({si_count} items)")
            else:
                print(f"    [CREATE] {variant_label} ← {child.name} (id={child_id}, {si_count} items)")

            if not DRY_RUN:
                if not variant:
                    variant = ProductVariant(
                        product_id=parent_id,
                        tenant_id=TENANT_ID,
                        label=variant_label,
                        sku=child.sku,
                        price_per_day_cents=child.price_per_day,
                        deposit_amount_cents=child.deposit_amount,
                        stock_quantity=0,
                        available_quantity=0,
                        is_active=True,
                    )
                    db.add(variant)
                    await db.flush()

                # Migrer stock_items
                if si_count > 0:
                    await db.execute(
                        text("""
                            UPDATE stock_items
                            SET product_id = :parent_id, variant_id = :variant_id
                            WHERE product_id = :child_id AND tenant_id = :tid
                        """),
                        {"parent_id": parent_id, "variant_id": variant.id, "child_id": child_id, "tid": TENANT_ID},
                    )
                    migrated_stock_items += si_count

                # Mettre à jour compteurs variante
                new_si_count = await db.scalar(
                    select(func.count(StockItem.id)).where(
                        StockItem.product_id == parent_id,
                        StockItem.variant_id == variant.id,
                        StockItem.tenant_id == TENANT_ID,
                    )
                )
                variant.stock_quantity = new_si_count or 0
                variant.available_quantity = await db.scalar(
                    select(func.count(StockItem.id)).where(
                        StockItem.product_id == parent_id,
                        StockItem.variant_id == variant.id,
                        StockItem.status == "available",
                        StockItem.tenant_id == TENANT_ID,
                    )
                ) or 0

                # Désactiver l'ancien produit enfant
                child.is_active = False

                # Désactiver l'ancienne variante "Standard" de l'enfant
                await db.execute(
                    update(ProductVariant)
                    .where(ProductVariant.product_id == child_id, ProductVariant.tenant_id == TENANT_ID)
                    .values(is_active=False)
                )

            migrated_children += 1

    # Mettre à jour les compteurs des parents
    if not DRY_RUN:
        result = await db.execute(
            select(Product).where(Product.is_active == True, Product.tenant_id == TENANT_ID)
        )
        for parent in result.scalars().all():
            total = await db.scalar(
                select(func.count(StockItem.id)).where(
                    StockItem.product_id == parent.id, StockItem.tenant_id == TENANT_ID
                )
            ) or 0
            avail = await db.scalar(
                select(func.count(StockItem.id)).where(
                    StockItem.product_id == parent.id, StockItem.tenant_id == TENANT_ID,
                    StockItem.status == "available",
                )
            ) or 0
            parent.stock_quantity = total
            parent.available_quantity = avail

    # Supprimer produits test
    for del_id in DELETE_IDS:
        p = await db.get(Product, del_id)
        if p:
            print(f"  [DELETE] {p.name} (id={del_id})")
            if not DRY_RUN:
                p.is_active = False

    if not DRY_RUN:
        await db.commit()

    print(f"\n{'='*60}")
    print(f"  Parents créés    : {created_parents}")
    print(f"  Enfants migrés   : {migrated_children}")
    print(f"  Stock items movés : {migrated_stock_items}")
    print(f"  {'DRY RUN — rien écrit' if DRY_RUN else 'APPLIQUÉ'}")
    print(f"{'='*60}")


async def verify(db: AsyncSession):
    print(f"\n--- Vérification post-migration ---")
    active = await db.scalar(
        select(func.count(Product.id)).where(Product.is_active == True, Product.tenant_id == TENANT_ID)
    )
    inactive = await db.scalar(
        select(func.count(Product.id)).where(Product.is_active == False, Product.tenant_id == TENANT_ID)
    )
    variants = await db.scalar(
        select(func.count(ProductVariant.id)).where(ProductVariant.is_active == True, ProductVariant.tenant_id == TENANT_ID)
    )
    stock = await db.scalar(
        select(func.count(StockItem.id)).where(StockItem.tenant_id == TENANT_ID)
    )
    orphan_stock = await db.scalar(
        text("""
            SELECT count(*) FROM stock_items si
            JOIN products p ON si.product_id = p.id
            WHERE p.is_active = false AND si.tenant_id = :tid
        """),
        {"tid": TENANT_ID},
    )
    print(f"  Produits actifs   : {active}")
    print(f"  Produits inactifs : {inactive}")
    print(f"  Variantes actives : {variants}")
    print(f"  Stock items total : {stock}")
    print(f"  Stock orphelins   : {orphan_stock} (liés à produits inactifs)")


async def main():
    async with AsyncSessionLocal() as db:
        await migrate(db)
        if not DRY_RUN:
            await verify(db)


if __name__ == "__main__":
    asyncio.run(main())
