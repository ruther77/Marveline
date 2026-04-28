"""Service métier pour les produits."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.models.product import Product
from app.repositories.product import AsyncProductRepository
from app.repositories.product_variant import AsyncProductVariantRepository
from app.schemas.product import ProductCreate, ProductUpdate
from app.constants import ErrorMessages


class ProductService:
    """Version async du service produit — expand/contract (sync conservé pour Celery).

    Utilise AsyncProductRepository + AsyncSession pour les endpoints FastAPI.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncProductRepository(db)
        self.variant_repo = AsyncProductVariantRepository(db)

    async def list_products(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        condition: Optional[str] = None,
        supplier_id: Optional[int] = None,
        available_only: bool = False,
        include_inactive: bool = False,
        search: Optional[str] = None,
    ) -> tuple[list[Product], int]:
        if search:
            return await self.repo.list_with_search(
                tenant_id=tenant_id,
                search_term=search,
                skip=skip,
                limit=limit,
                condition=condition,
                supplier_id=supplier_id,
            )

        filters = {}
        if category:
            filters["category"] = category
        if condition:
            filters["condition"] = condition
        if supplier_id is not None:
            filters["supplier_id"] = supplier_id
        if available_only:
            filters["available_quantity__gt"] = 0
        if include_inactive:
            filters["include_inactive"] = True

        return await self.repo.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters=filters if filters else None,
        )

    async def get_product(self, product_id: int, tenant_id: int) -> Product:
        product = await self.repo.get_by_id_with_images(product_id, tenant_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.PRODUCT_NOT_FOUND,
            )
        return product

    async def create_product(
        self,
        product_data: ProductCreate,
        tenant_id: int,
    ) -> Product:
        if await self.repo.sku_exists(product_data.sku, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Product with SKU '{product_data.sku}' already exists",
            )

        product = Product(
            tenant_id=tenant_id,
            name=product_data.name,
            sku=product_data.sku,
            category=product_data.category,
            price_per_day_cents=product_data.price_per_day_cents,
            deposit_amount_cents=product_data.deposit_amount_cents,
            stock_quantity=product_data.stock_quantity,
            available_quantity=product_data.available_quantity,
            condition=product_data.condition,
            image_url=product_data.image_url,
            is_active=True,
        )

        if product.available_quantity > product.stock_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.AVAILABLE_EXCEEDS_STOCK,
            )

        try:
            return await self.repo.create(product)
        except IntegrityError as e:
            if "unique constraint" in str(e).lower() or "sku" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Product with SKU '{product.sku}' already exists",
                )
            raise

    async def update_product(
        self,
        product_id: int,
        product_data: ProductUpdate,
        tenant_id: int,
    ) -> Product:
        product = await self.repo.get_by_id(product_id, tenant_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.PRODUCT_NOT_FOUND,
            )

        update_data = product_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "price_per_day_cents":
                setattr(product, "price_per_day_cents", value)
            elif field == "deposit_amount_cents":
                setattr(product, "deposit_amount_cents", value)
            else:
                setattr(product, field, value)

        if product.available_quantity > product.stock_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.AVAILABLE_EXCEEDS_STOCK,
            )

        return await self.repo.update(product)

    async def reserve_stock(
        self,
        product_id: int,
        quantity: int,
        tenant_id: int,
        variant_id: Optional[int] = None,
    ) -> bool:
        if variant_id is not None:
            success = await self.variant_repo.reserve_stock(variant_id, quantity, tenant_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Stock insuffisant pour la variante #{variant_id}",
                )
            await self.repo.sync_available_from_variants(product_id, tenant_id)
            return True

        if not await self.repo.check_availability(product_id, quantity, tenant_id):
            product = await self.repo.get_by_id(product_id, tenant_id)
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ErrorMessages.PRODUCT_NOT_FOUND,
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock. Available: {product.available_quantity}, Requested: {quantity}",
            )

        success = await self.repo.reserve_stock(product_id, quantity, tenant_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.STOCK_RESERVATION_FAILED,
            )
        return True

    async def release_stock(
        self,
        product_id: int,
        quantity: int,
        tenant_id: int,
        variant_id: Optional[int] = None,
    ) -> bool:
        if variant_id is not None:
            await self.variant_repo.release_stock(variant_id, quantity, tenant_id)
            await self.repo.sync_available_from_variants(product_id, tenant_id)
            return True

        success = await self.repo.release_stock(product_id, quantity, tenant_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.PRODUCT_NOT_FOUND,
            )
        return True

    async def delete_product(
        self,
        product_id: int,
        tenant_id: int,
        hard_delete: bool = False,
    ) -> bool:
        if hard_delete:
            success = await self.repo.hard_delete(product_id, tenant_id)
        else:
            success = await self.repo.soft_delete(product_id, tenant_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.PRODUCT_NOT_FOUND,
            )
        return True


# Backward-compat alias
AsyncProductService = ProductService
