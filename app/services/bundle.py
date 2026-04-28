"""Service metier pour les bundles (packs de produits)."""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.bundle import ProductBundle, BundleItem
from app.models.product import Product
from app.repositories.bundle import AsyncBundleRepository, AsyncBundleItemRepository
from app.repositories.product_variant import AsyncProductVariantRepository
from app.schemas.bundle import BundleCreate, BundleUpdate, BundleItemCreate, BundleItemUpdate
from app.constants import ErrorMessages
from app.utils import slugify


class BundleService:
    """Service metier pour gestion des bundles."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncBundleRepository(db)
        self.item_repo = AsyncBundleItemRepository(db)
        self.variant_repo = AsyncProductVariantRepository(db)

    async def list_bundles(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        featured: Optional[bool] = None,
        include_inactive: bool = False,  # noqa: ARG002 — async repo filtre is_active par défaut
    ) -> tuple[list[ProductBundle], int]:
        """Liste les bundles avec filtres et pagination."""
        filters: dict = {}
        if featured is not None:
            filters["featured"] = featured
        return await self.repo.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters=filters if filters else None,
        )

    async def get_bundle(self, bundle_id: int, tenant_id: int) -> ProductBundle:
        """Récupère un bundle par ID avec ses items et produits.

        Raises:
            HTTPException 404: Si bundle non trouvé.
        """
        bundle = await self.repo.get_with_items(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_NOT_FOUND,
            )
        return bundle

    async def create_bundle(self, data: BundleCreate, tenant_id: int) -> ProductBundle:
        """Cree un nouveau bundle. Auto-genere le slug depuis le name si pas fourni."""
        slug = data.slug if data.slug else slugify(data.name)

        if await self.repo.slug_exists(slug, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.BUNDLE_SLUG_EXISTS,
            )

        if await self.repo.name_exists(data.name, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.BUNDLE_NAME_EXISTS,
            )

        return await self.repo.create({
            "tenant_id": tenant_id,
            "name": data.name,
            "slug": slug,
            "description": data.description,
            "short_description": data.short_description,
            "bundle_price_cents": data.bundle_price_cents,
            "cleaning_fee_cents": data.cleaning_fee_cents,
            "featured": data.featured,
            "display_order": data.display_order,
            "image_url": data.image_url,
        })

    async def update_bundle(
        self, bundle_id: int, data: BundleUpdate, tenant_id: int
    ) -> ProductBundle:
        """Met a jour un bundle (PATCH partiel)."""
        bundle = await self.repo.get_by_id(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_NOT_FOUND,
            )

        update_data = data.model_dump(exclude_unset=True)

        # Mapper noms schema → colonnes DB
        field_map = {"bundle_price_cents": "bundle_price_cents", "cleaning_fee_cents": "cleaning_fee_cents"}

        if "slug" in update_data and update_data["slug"] != bundle.slug:
            if await self.repo.slug_exists(update_data["slug"], tenant_id, exclude_id=bundle_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.BUNDLE_SLUG_EXISTS,
                )

        if "name" in update_data and update_data["name"] != bundle.name:
            if await self.repo.name_exists(update_data["name"], tenant_id, exclude_id=bundle_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.BUNDLE_NAME_EXISTS,
                )

        mapped_data = {field_map.get(k, k): v for k, v in update_data.items()}
        return await self.repo.update(bundle, mapped_data)

    async def delete_bundle(self, bundle_id: int, tenant_id: int) -> bool:
        """Soft delete un bundle."""
        bundle = await self.repo.get_by_id(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_NOT_FOUND,
            )
        await self.repo.soft_delete(bundle)
        return True

    async def add_item(
        self, bundle_id: int, data: BundleItemCreate, tenant_id: int
    ) -> BundleItem:
        """Ajoute un produit au bundle."""
        bundle = await self.repo.get_by_id(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_NOT_FOUND,
            )

        product = (await self.db.execute(
            select(Product).filter(
                Product.id == data.product_id,
                Product.tenant_id == tenant_id,
                Product.is_active == True,  # noqa: E712
            )
        )).scalar_one_or_none()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.BUNDLE_ITEM_PRODUCT_NOT_FOUND,
            )

        existing = await self.item_repo.get_by_bundle_and_product(bundle_id, data.product_id, tenant_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.BUNDLE_ITEM_DUPLICATE,
            )

        active_variants = await self.variant_repo.list_by_product(data.product_id, tenant_id)
        if active_variants and data.variant_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=ErrorMessages.BUNDLE_ITEM_VARIANT_REQUIRED,
            )
        if data.variant_id is not None:
            variant = await self.variant_repo.get_by_id(data.variant_id, tenant_id)
            if not variant or variant.product_id != data.product_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.BUNDLE_ITEM_VARIANT_MISMATCH,
                )

        return await self.item_repo.create({
            "tenant_id": tenant_id,
            "bundle_id": bundle_id,
            "product_id": data.product_id,
            "variant_id": data.variant_id,
            "quantity": data.quantity,
            "display_order": data.display_order,
        })

    async def update_item(
        self, bundle_id: int, item_id: int, data: BundleItemUpdate, tenant_id: int
    ) -> BundleItem:
        """Met a jour un item du bundle."""
        bundle = await self.repo.get_by_id(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_NOT_FOUND,
            )

        item = (await self.db.execute(
            select(BundleItem).filter(
                BundleItem.id == item_id,
                BundleItem.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if not item or item.bundle_id != bundle_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_ITEM_NOT_FOUND,
            )

        update_data = data.model_dump(exclude_unset=True)

        if "variant_id" in update_data and update_data["variant_id"] is not None:
            variant = await self.variant_repo.get_by_id(update_data["variant_id"], tenant_id)
            if not variant or variant.product_id != item.product_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.BUNDLE_ITEM_VARIANT_MISMATCH,
                )

        for field, value in update_data.items():
            setattr(item, field, value)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def remove_item(self, bundle_id: int, item_id: int, tenant_id: int) -> bool:
        """Supprime un item du bundle (suppression physique)."""
        bundle = await self.repo.get_by_id(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_NOT_FOUND,
            )

        item = (await self.db.execute(
            select(BundleItem).filter(
                BundleItem.id == item_id,
                BundleItem.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if not item or item.bundle_id != bundle_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_ITEM_NOT_FOUND,
            )

        await self.db.delete(item)
        await self.db.flush()
        return True

    async def calculate_price(self, bundle_id: int, tenant_id: int) -> dict:
        """Calcule le prix individuel vs bundle (eager-loaded via get_with_items)."""
        bundle = await self.repo.get_with_items(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_NOT_FOUND,
            )

        individual_price = 0
        items_detail = []
        for item in bundle.items:
            item_total = item.product.price_per_day_cents * item.quantity
            individual_price += item_total
            items_detail.append({
                "product_id": item.product_id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit_price_cents": item.product.price_per_day_cents,
                "line_total_cents": item_total,
            })

        savings = individual_price - bundle.bundle_price_cents
        savings_percent = (savings / individual_price * 100) if individual_price > 0 else 0.0

        return {
            "bundle_price_cents": bundle.bundle_price_cents,
            "individual_price_cents": individual_price,
            "savings_cents": savings,
            "savings_percent": round(savings_percent, 2),
            "items": items_detail,
        }
