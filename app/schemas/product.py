"""Schemas Pydantic pour l'entité Product (catalogue de vaisselle)."""
from typing import Optional
from pydantic import Field, field_validator, computed_field
from app.schemas.base import BaseSchema, EntityResponseSchema
from app.constants import ProductCategory, ProductCondition


class ProductBase(BaseSchema):
    """Schema de base partagé entre Create et Update."""

    name: str = Field(
        ...,
        max_length=200,
        description="Nom du produit"
    )

    sku: str = Field(
        ...,
        max_length=50,
        description="Code produit unique (Stock Keeping Unit)"
    )

    category: ProductCategory = Field(
        ...,
        description="Catégorie du produit"
    )

    price_per_day_cents: int = Field(
        ...,
        ge=0,
        description="Prix location par jour en centimes (250 = 2.50€)"
    )

    deposit_amount_cents: int = Field(
        default=0,
        ge=0,
        description="Montant caution par unité en centimes (500 = 5€)"
    )

    stock_quantity: int = Field(
        default=0,
        ge=0,
        description="Quantité totale en stock"
    )

    available_quantity: int = Field(
        default=0,
        ge=0,
        description="Quantité disponible à la location"
    )

    condition: ProductCondition = Field(
        default=ProductCondition.BON,
        description="État du produit"
    )

    image_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL de l'image du produit"
    )

    @field_validator('sku')
    @classmethod
    def sku_uppercase(cls, v: str) -> str:
        """Normaliser SKU en majuscules."""
        return v.upper().strip()

    @field_validator('available_quantity')
    @classmethod
    def available_lte_stock(cls, v: int, info) -> int:
        """Validation: available_quantity <= stock_quantity."""
        stock_quantity = info.data.get('stock_quantity', 0)
        if v > stock_quantity:
            raise ValueError(
                f"available_quantity ({v}) cannot exceed stock_quantity ({stock_quantity})"
            )
        return v


class ProductCreate(ProductBase):
    """Schema pour création d'un nouveau produit.

    Le tenant_id sera automatiquement ajouté depuis le JWT du user connecté.

    Example:
        {
            "name": "Assiette plate blanche 28cm",
            "sku": "ASS-PLATE-28-WHI",
            "category": "assiette",
            "price_per_day_cents": 250,
            "deposit_amount_cents": 500,
            "stock_quantity": 100,
            "available_quantity": 100,
            "condition": "neuf",
            "image_url": "https://cdn.carocorp.com/products/assiette-plate-28.jpg"
        }
    """
    pass


class ProductUpdate(BaseSchema):
    """Schema pour mise à jour d'un produit existant.

    Tous les champs sont optionnels (PATCH partiel).
    SKU est immutable (ne peut pas être changé après création).

    Example:
        {
            "price_per_day_cents": 300,
            "stock_quantity": 150,
            "available_quantity": 120,
            "condition": "bon"
        }
    """

    name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Nom du produit"
    )

    category: Optional[ProductCategory] = Field(
        default=None,
        description="Catégorie du produit"
    )

    price_per_day_cents: Optional[int] = Field(
        default=None,
        ge=0,
        description="Prix location par jour en centimes"
    )

    deposit_amount_cents: Optional[int] = Field(
        default=None,
        ge=0,
        description="Montant caution par unité en centimes"
    )

    stock_quantity: Optional[int] = Field(
        default=None,
        ge=0,
        description="Quantité totale en stock"
    )

    available_quantity: Optional[int] = Field(
        default=None,
        ge=0,
        description="Quantité disponible à la location"
    )

    condition: Optional[ProductCondition] = Field(
        default=None,
        description="État du produit"
    )

    image_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL de l'image du produit"
    )


class ProductList(EntityResponseSchema):
    """Schema simplifié pour listes de produits."""

    name: str
    sku: str
    category: str
    price_per_day_cents: int = Field(validation_alias="price_per_day")
    stock_quantity: int
    available_quantity: int
    condition: str

    @computed_field
    @property
    def price_per_day_euros(self) -> float:
        """Prix en euros pour affichage (computed field)."""
        return self.price_per_day_cents / 100

    @computed_field
    @property
    def is_available(self) -> bool:
        """Indique si le produit est disponible (stock > 0 et actif)."""
        return self.is_active and self.available_quantity > 0


class ProductResponse(EntityResponseSchema):
    """Schema complet pour réponse détaillée d'un produit."""

    name: str
    sku: str
    category: str
    price_per_day_cents: int = Field(validation_alias="price_per_day")
    deposit_amount_cents: int = Field(validation_alias="deposit_amount")
    stock_quantity: int
    available_quantity: int
    condition: str
    image_url: Optional[str] = None

    @computed_field
    @property
    def price_per_day_euros(self) -> float:
        """Prix location par jour en euros pour affichage."""
        return self.price_per_day_cents / 100

    @computed_field
    @property
    def deposit_amount_euros(self) -> float:
        """Montant caution en euros pour affichage."""
        return self.deposit_amount_cents / 100

    @computed_field
    @property
    def is_available(self) -> bool:
        """Indique si le produit est disponible."""
        return self.is_active and self.available_quantity > 0

    @computed_field
    @property
    def is_out_of_stock(self) -> bool:
        """Indique si le produit est en rupture de stock."""
        return self.available_quantity == 0

    model_config = EntityResponseSchema.model_config.copy()
    model_config["json_schema_extra"] = {
        "examples": [
            {
                "id": 1,
                "tenant_id": 1,
                "name": "Assiette plate blanche 28cm",
                "sku": "ASS-PLATE-28-WHI",
                "category": "assiette",
                "price_per_day_cents": 250,
                "deposit_amount_cents": 500,
                "stock_quantity": 100,
                "available_quantity": 85,
                "condition": "bon",
                "image_url": "https://cdn.carocorp.com/products/assiette-plate-28.jpg",
                "is_active": True,
                "created_at": "2026-01-15T10:00:00Z",
                "updated_at": "2026-01-15T10:00:00Z"
            }
        ]
    }
