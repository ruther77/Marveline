"""Service metier pour les bundles (packs de produits)."""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.bundle import ProductBundle, BundleItem
from app.repositories.bundle import BundleRepository, BundleItemRepository
from app.repositories.product import ProductRepository
from app.schemas.bundle import BundleCreate, BundleUpdate, BundleItemCreate, BundleItemUpdate
from app.constants import ErrorMessages
from app.utils import slugify


class BundleService:
    """Service metier pour gestion des bundles."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = BundleRepository(db)
        self.item_repo = BundleItemRepository(db)
        self.product_repo = ProductRepository(db)

    def create_bundle(self, data: BundleCreate, tenant_id: int) -> ProductBundle:
        """Cree un nouveau bundle.

        Auto-genere le slug depuis le name si pas fourni.
        """
        slug = data.slug if data.slug else slugify(data.name)

        if self.repo.slug_exists(slug, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.BUNDLE_SLUG_EXISTS,
            )

        if self.repo.name_exists(data.name, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.BUNDLE_NAME_EXISTS,
            )

        bundle = ProductBundle(
            tenant_id=tenant_id,
            name=data.name,
            slug=slug,
            description=data.description,
            short_description=data.short_description,
            bundle_price=data.bundle_price_cents,
            cleaning_fee=data.cleaning_fee_cents,
            featured=data.featured,
            display_order=data.display_order,
            image_url=data.image_url,
        )
        return self.repo.create(bundle)

    def update_bundle(
        self, bundle_id: int, data: BundleUpdate, tenant_id: int
    ) -> ProductBundle:
        """Met a jour un bundle (PATCH partiel)."""
        bundle = self.repo.get_by_id(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_NOT_FOUND,
            )

        update_data = data.model_dump(exclude_unset=True)

        # Mapper les noms schema → DB
        field_map = {
            "bundle_price_cents": "bundle_price",
            "cleaning_fee_cents": "cleaning_fee",
        }

        # Verifier unicite slug si change
        if "slug" in update_data and update_data["slug"] != bundle.slug:
            if self.repo.slug_exists(update_data["slug"], tenant_id, exclude_id=bundle_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.BUNDLE_SLUG_EXISTS,
                )

        # Verifier unicite nom si change
        if "name" in update_data and update_data["name"] != bundle.name:
            if self.repo.name_exists(update_data["name"], tenant_id, exclude_id=bundle_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.BUNDLE_NAME_EXISTS,
                )

        for field, value in update_data.items():
            db_field = field_map.get(field, field)
            setattr(bundle, db_field, value)

        return self.repo.update(bundle)

    def delete_bundle(self, bundle_id: int, tenant_id: int) -> bool:
        """Soft delete un bundle."""
        bundle = self.repo.get_by_id(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_NOT_FOUND,
            )
        return self.repo.soft_delete(bundle_id, tenant_id)

    def add_item(
        self, bundle_id: int, data: BundleItemCreate, tenant_id: int
    ) -> BundleItem:
        """Ajoute un produit au bundle."""
        # Verifier bundle existe
        bundle = self.repo.get_by_id(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_NOT_FOUND,
            )

        # Verifier produit existe et meme tenant
        product = self.product_repo.get_by_id(data.product_id, tenant_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.BUNDLE_ITEM_PRODUCT_NOT_FOUND,
            )

        # Verifier pas de doublon
        existing = self.item_repo.get_by_bundle_and_product(bundle_id, data.product_id, tenant_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.BUNDLE_ITEM_DUPLICATE,
            )

        item = BundleItem(
            tenant_id=tenant_id,
            bundle_id=bundle_id,
            product_id=data.product_id,
            quantity=data.quantity,
            display_order=data.display_order,
        )
        return self.item_repo.create(item)

    def update_item(
        self, bundle_id: int, item_id: int, data: BundleItemUpdate, tenant_id: int
    ) -> BundleItem:
        """Met a jour un item du bundle."""
        # Verifier bundle existe
        bundle = self.repo.get_by_id(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_NOT_FOUND,
            )

        # Verifier item existe
        item = self.item_repo.get_by_id(item_id, tenant_id)
        if not item or item.bundle_id != bundle_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_ITEM_NOT_FOUND,
            )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)

        return self.item_repo.update(item)

    def remove_item(
        self, bundle_id: int, item_id: int, tenant_id: int
    ) -> bool:
        """Supprime un item du bundle (suppression physique)."""
        bundle = self.repo.get_by_id(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_NOT_FOUND,
            )

        item = self.item_repo.get_by_id(item_id, tenant_id)
        if not item or item.bundle_id != bundle_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_ITEM_NOT_FOUND,
            )

        self.db.delete(item)
        self.db.flush()
        return True

    def calculate_price(self, bundle_id: int, tenant_id: int) -> dict:
        """Calcule le prix individuel vs bundle."""
        bundle = self.repo.get_with_items(bundle_id, tenant_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.BUNDLE_NOT_FOUND,
            )

        individual_price = 0
        items_detail = []
        for item in bundle.items:
            item_total = item.product.price_per_day * item.quantity
            individual_price += item_total
            items_detail.append({
                "product_id": item.product_id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit_price_cents": item.product.price_per_day,
                "line_total_cents": item_total,
            })

        savings = individual_price - bundle.bundle_price
        savings_percent = (savings / individual_price * 100) if individual_price > 0 else 0.0

        return {
            "bundle_price_cents": bundle.bundle_price,
            "individual_price_cents": individual_price,
            "savings_cents": savings,
            "savings_percent": round(savings_percent, 2),
            "items": items_detail,
        }
