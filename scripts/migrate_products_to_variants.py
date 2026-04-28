"""
Migration : fusionner les produits doublons (variante Standard) dans les produits parents.

Pour chaque produit doublon :
1. Identifier le parent existant (via SKU prefix) OU créer un parent
2. Créer/mapper la variante correspondante
3. Migrer les stock_items vers parent + variante
4. Désactiver le produit doublon

Usage :
  docker compose exec api python scripts/migrate_products_to_variants.py --dry-run
  docker compose exec api python scripts/migrate_products_to_variants.py --apply
"""
import asyncio
import sys
import re
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

# ── Bootstrap app ─────────────────────────────────────────────────────────────
sys.path.insert(0, "/app")
from app.core.database import async_engine, AsyncSessionLocal
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.stock_item import StockItem

TENANT_ID = 1
DRY_RUN = "--apply" not in sys.argv


async def get_doublons(db: AsyncSession):
    """Produits avec exactement 1 variante 'Standard'."""
    result = await db.execute(
        select(Product, ProductVariant)
        .join(ProductVariant, ProductVariant.product_id == Product.id)
        .where(
            Product.is_active == True,
            Product.tenant_id == TENANT_ID,
            ProductVariant.is_active == True,
            ProductVariant.label == "Standard",
        )
    )
    rows = result.all()
    # Garder seulement ceux qui n'ont QUE "Standard"
    doublons = []
    for product, variant in rows:
        count = await db.scalar(
            select(func.count(ProductVariant.id))
            .where(ProductVariant.product_id == product.id, ProductVariant.is_active == True)
        )
        if count == 1:
            doublons.append((product, variant))
    return doublons


async def get_parents(db: AsyncSession):
    """Produits avec >1 variante ou variante != Standard."""
    result = await db.execute(
        select(Product)
        .where(Product.is_active == True, Product.tenant_id == TENANT_ID)
    )
    all_products = result.scalars().all()
    parents = {}
    for p in all_products:
        variants = (await db.execute(
            select(ProductVariant)
            .where(ProductVariant.product_id == p.id, ProductVariant.is_active == True)
        )).scalars().all()
        has_real = any(v.label != "Standard" for v in variants)
        if has_real or len(variants) > 1:
            parents[p.sku] = (p, variants)
    return parents


def extract_variant_label(doublon_name: str, parent_name: str) -> str:
    """Dérive le nom de variante depuis le nom du doublon."""
    # Ex: "Verre à eau classique" - parent "Verre à eau" → "Classique"
    label = doublon_name.replace(parent_name, "").strip()
    if not label:
        label = doublon_name.split()[-1]  # Dernier mot
    return label.capitalize()


def find_matching_variant(variants, label: str, price: int):
    """Trouve la variante qui correspond (par label ou prix)."""
    # Match exact par label
    for v in variants:
        if v.label.lower() == label.lower():
            return v
    # Match par prix
    for v in variants:
        if v.price_per_day == price:
            return v
    return None


async def migrate(db: AsyncSession):
    doublons = await get_doublons(db)
    parents = await get_parents(db)

    print(f"\n{'=' * 60}")
    print(f"  {'DRY RUN' if DRY_RUN else 'APPLYING'} — Migration produits → variantes")
    print(f"  {len(doublons)} doublons, {len(parents)} parents existants")
    print(f"{'=' * 60}\n")

    migrated = 0
    created_parents = 0
    orphans = []

    for product, old_variant in doublons:
        # Trouver le parent via SKU prefix
        sku_parts = product.sku.rsplit("-", 1)
        parent_sku = sku_parts[0] if len(sku_parts) > 1 else None
        parent_match = parents.get(parent_sku)

        if not parent_match:
            # Essayer avec un niveau de moins
            sku_parts2 = parent_sku.rsplit("-", 1) if parent_sku else (None,)
            parent_sku2 = sku_parts2[0] if len(sku_parts2) > 1 else None
            parent_match = parents.get(parent_sku2) if parent_sku2 else None

        if not parent_match:
            orphans.append(product)
            continue

        parent_product, parent_variants = parent_match
        variant_label = extract_variant_label(product.name, parent_product.name)
        matched_variant = find_matching_variant(parent_variants, variant_label, product.price_per_day)

        if not matched_variant:
            # Créer la variante manquante sur le parent
            print(f"  [CREATE VARIANT] {parent_product.name} → '{variant_label}' ({product.price_per_day} cts/j)")
            if not DRY_RUN:
                new_variant = ProductVariant(
                    product_id=parent_product.id,
                    tenant_id=TENANT_ID,
                    label=variant_label,
                    sku=product.sku,
                    price_per_day_cents=product.price_per_day,
                    deposit_amount_cents=product.deposit_amount,
                    stock_quantity=product.stock_quantity,
                    available_quantity=product.available_quantity,
                    is_active=True,
                )
                db.add(new_variant)
                await db.flush()
                matched_variant = new_variant

        if matched_variant:
            # Migrer les stock_items
            si_count = await db.scalar(
                select(func.count(StockItem.id))
                .where(StockItem.product_id == product.id, StockItem.tenant_id == TENANT_ID)
            )

            print(f"  [MIGRATE] {product.name} (id={product.id}) → {parent_product.name} / {matched_variant.label} (variant={matched_variant.id}) — {si_count} stock_items")

            if not DRY_RUN:
                # Déplacer stock_items vers parent + variante
                await db.execute(
                    text("""
                        UPDATE stock_items
                        SET product_id = :parent_id, variant_id = :variant_id
                        WHERE product_id = :old_id AND tenant_id = :tid
                    """),
                    {"parent_id": parent_product.id, "variant_id": matched_variant.id, "old_id": product.id, "tid": TENANT_ID},
                )

                # Mettre à jour les compteurs variante
                matched_variant.stock_quantity = (matched_variant.stock_quantity or 0) + (product.stock_quantity or 0)
                matched_variant.available_quantity = (matched_variant.available_quantity or 0) + (product.available_quantity or 0)

                # Désactiver le doublon
                product.is_active = False

                # Désactiver l'ancienne variante Standard
                old_variant.is_active = False

            migrated += 1

    # Mettre à jour les compteurs des parents
    if not DRY_RUN:
        for parent_sku, (parent_product, _) in parents.items():
            total = await db.scalar(
                select(func.count(StockItem.id))
                .where(StockItem.product_id == parent_product.id, StockItem.tenant_id == TENANT_ID)
            )
            available = await db.scalar(
                select(func.count(StockItem.id))
                .where(StockItem.product_id == parent_product.id, StockItem.tenant_id == TENANT_ID, StockItem.status == "available")
            )
            parent_product.stock_quantity = total or 0
            parent_product.available_quantity = available or 0

        await db.commit()

    print(f"\n{'=' * 60}")
    print(f"  Migrated: {migrated}")
    print(f"  Orphans (no parent found): {len(orphans)}")
    if orphans:
        print(f"  Orphan products:")
        for o in orphans:
            print(f"    - {o.name} (SKU={o.sku}, id={o.id})")
    print(f"{'=' * 60}")


async def main():
    async with AsyncSessionLocal() as db:
        await migrate(db)


if __name__ == "__main__":
    asyncio.run(main())
