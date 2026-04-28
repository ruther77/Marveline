"""Schemas Pydantic pour les bundles (packs de produits)."""
from typing import Optional
from pydantic import Field, computed_field
from app.schemas.base import BaseSchema, EntityResponseSchema
from app.schemas.product import ProductList


class BundleCreate(BaseSchema):
    """Schema pour creation d'un nouveau bundle."""

    name: str = Field(
        ...,
        max_length=200,
        description="Nom du bundle"
    )
    slug: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Slug URL-safe (auto-genere si absent)"
    )
    description: Optional[str] = Field(
        default=None,
        description="Description longue"
    )
    short_description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Description courte pour les listes"
    )
    bundle_price_cents: int = Field(
        ...,
        ge=0,
        description="Prix du bundle en centimes"
    )
    cleaning_fee_cents: int = Field(
        default=0,
        ge=0,
        description="Frais de nettoyage en centimes"
    )
    featured: bool = Field(
        default=False,
        description="Mis en avant sur le site"
    )
    display_order: int = Field(
        default=0,
        ge=0,
        description="Ordre d'affichage"
    )
    image_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL de l'image"
    )


class BundleUpdate(BaseSchema):
    """Schema pour mise a jour d'un bundle (PATCH partiel)."""

    name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Nom du bundle"
    )
    slug: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Slug URL-safe"
    )
    description: Optional[str] = Field(
        default=None,
        description="Description longue"
    )
    short_description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Description courte"
    )
    bundle_price_cents: Optional[int] = Field(
        default=None,
        ge=0,
        description="Prix du bundle en centimes"
    )
    cleaning_fee_cents: Optional[int] = Field(
        default=None,
        ge=0,
        description="Frais de nettoyage en centimes"
    )
    featured: Optional[bool] = Field(
        default=None,
        description="Mis en avant"
    )
    display_order: Optional[int] = Field(
        default=None,
        ge=0,
        description="Ordre d'affichage"
    )
    image_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL de l'image"
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Actif"
    )


class BundleItemCreate(BaseSchema):
    """Schema pour ajouter un item au bundle."""

    product_id: int = Field(
        ...,
        gt=0,
        description="ID du produit"
    )
    variant_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID de la variante (optionnel — preciser la variante dans le bundle)"
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="Quantite dans le bundle"
    )
    display_order: int = Field(
        default=0,
        ge=0,
        description="Ordre d'affichage"
    )


class BundleItemUpdate(BaseSchema):
    """Schema pour mise a jour d'un item du bundle."""

    variant_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID de la variante"
    )
    quantity: Optional[int] = Field(
        default=None,
        ge=1,
        description="Quantite dans le bundle"
    )
    display_order: Optional[int] = Field(
        default=None,
        ge=0,
        description="Ordre d'affichage"
    )


class BundleItemResponse(BaseSchema):
    """Schema de reponse pour un item de bundle."""

    id: int
    bundle_id: int
    product_id: int
    variant_id: Optional[int] = None
    quantity: int
    display_order: int
    product: ProductList


class BundleResponse(EntityResponseSchema):
    """Schema de reponse pour un bundle (sans items)."""

    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    bundle_price_cents: int
    cleaning_fee_cents: int
    featured: bool
    display_order: int
    image_url: Optional[str] = None

    @computed_field
    @property
    def bundle_price_euros(self) -> float:
        """Prix du bundle en euros."""
        return self.bundle_price_cents / 100

    @computed_field
    @property
    def cleaning_fee_euros(self) -> float:
        """Frais de nettoyage en euros."""
        return self.cleaning_fee_cents / 100


class BundleWithItems(BundleResponse):
    """Schema de reponse pour un bundle avec ses items."""

    items: list[BundleItemResponse] = []

    @computed_field
    @property
    def total_items(self) -> int:
        """Nombre d'items dans le bundle."""
        return len(self.items)

    @computed_field
    @property
    def individual_price_cents(self) -> int:
        """Prix individuel total (somme des prix unitaires * quantite)."""
        return sum(
            item.product.price_per_day_cents * item.quantity
            for item in self.items
        )

    @computed_field
    @property
    def savings_cents(self) -> int:
        """Economie en centimes (prix individuel - prix bundle)."""
        return self.individual_price_cents - self.bundle_price_cents

    @computed_field
    @property
    def individual_price_euros(self) -> float:
        """Prix individuel en euros."""
        return self.individual_price_cents / 100

    @computed_field
    @property
    def savings_euros(self) -> float:
        """Economie en euros."""
        return self.savings_cents / 100


class BundlePriceResponse(BaseSchema):
    """Schema de reponse pour le calcul de prix."""

    bundle_price_cents: int
    individual_price_cents: int
    savings_cents: int
    savings_percent: float
    items: list[dict]
