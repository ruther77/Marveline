"""Service ProductVariant — logique métier variantes multi-dimensions."""
import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_variant import ProductVariant
from app.repositories.product import AsyncProductRepository
from app.repositories.product_variant import AsyncProductVariantRepository
from app.constants.errors import ErrorMessages
from app.schemas.product_variant import ProductVariantCreate, ProductVariantUpdate

logger = logging.getLogger(__name__)


class ProductVariantService:
    """Service pour la gestion des variantes multi-dimensions d'un produit."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncProductVariantRepository(db)
        self.product_repo = AsyncProductRepository(db)

    async def _sync_product_stock(self, product_id: int, tenant_id: int) -> None:
        """Recalcule le stock du produit parent depuis la somme de ses variantes actives.

        Délègue à AsyncProductRepository.sync_available_from_variants qui est
        la source de vérité unique (SUM stock_quantity + available_quantity des variantes).
        """
        await self.product_repo.sync_available_from_variants(product_id, tenant_id)

    async def _get_product_or_404(self, product_id: int, tenant_id: int) -> None:
        """Vérifie que le produit parent existe et appartient au tenant."""
        product = await self.product_repo.get_by_id(product_id, tenant_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.PRODUCT_NOT_FOUND,
            )

    async def list_variants(
        self, product_id: int, tenant_id: int
    ) -> list[ProductVariant]:
        """Liste toutes les variantes actives d'un produit, triées par label."""
        await self._get_product_or_404(product_id, tenant_id)
        return await self.repo.list_by_product(product_id, tenant_id)

    async def get_variant(
        self, product_id: int, variant_id: int, tenant_id: int
    ) -> ProductVariant:
        """Récupère une variante par son ID.

        Raises:
            HTTPException 404: Si produit ou variante non trouvé(e).
        """
        await self._get_product_or_404(product_id, tenant_id)
        variant = await self.repo.get_by_id(variant_id, tenant_id)
        if not variant or variant.product_id != product_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.VARIANT_NOT_FOUND,
            )
        return variant

    async def create_variant(
        self, product_id: int, data: ProductVariantCreate, tenant_id: int
    ) -> ProductVariant:
        """Crée une nouvelle variante pour un produit.

        Raises:
            HTTPException 404: Si produit non trouvé.
            HTTPException 409: Si label déjà existant pour ce produit,
                               ou SKU dupliqué dans le tenant.
        """
        await self._get_product_or_404(product_id, tenant_id)

        if await self.repo.label_exists_for_product(product_id, data.label, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorMessages.VARIANT_LABEL_EXISTS,
            )

        if await self.repo.sku_exists(data.sku, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorMessages.SKU_ALREADY_EXISTS,
            )

        variant = ProductVariant(
            tenant_id=tenant_id,
            product_id=product_id,
            color=data.color,
            size=data.size,
            gamme=data.gamme,
            label=data.label,
            price_per_day_cents=data.price_per_day,
            image_url=data.image_url,
            sku=data.sku,
            stock_quantity=data.stock_quantity,
            available_quantity=data.available_quantity,
        )
        self.db.add(variant)
        await self.db.flush()
        await self._sync_product_stock(product_id, tenant_id)
        return variant

    async def update_variant(
        self,
        product_id: int,
        variant_id: int,
        data: ProductVariantUpdate,
        tenant_id: int,
    ) -> ProductVariant:
        """Met à jour une variante (PATCH partiel).

        Raises:
            HTTPException 404: Si produit ou variante non trouvé(e).
            HTTPException 409: Si le nouveau label est déjà pris.
        """
        variant = await self.get_variant(product_id, variant_id, tenant_id)

        update_data = data.model_dump(exclude_unset=True)

        if "label" in update_data:
            new_label = update_data["label"]
            if await self.repo.label_exists_for_product(
                product_id, new_label, tenant_id, exclude_id=variant_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=ErrorMessages.VARIANT_LABEL_EXISTS,
                )

        # Mapper noms schema → colonnes ORM
        field_map = {"price_per_day": "price_per_day_cents"}
        for field, value in update_data.items():
            orm_field = field_map.get(field, field)
            setattr(variant, orm_field, value)

        await self.db.flush()
        await self._sync_product_stock(product_id, tenant_id)
        return variant

    async def delete_variant(
        self, product_id: int, variant_id: int, tenant_id: int
    ) -> None:
        """Soft delete d'une variante.

        Raises:
            HTTPException 404: Si produit ou variante non trouvé(e).
        """
        variant = await self.get_variant(product_id, variant_id, tenant_id)
        variant.soft_delete()
        await self.db.flush()
        await self._sync_product_stock(product_id, tenant_id)
