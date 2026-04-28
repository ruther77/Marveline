"""Schémas Pydantic pour ProductVariant."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.constants.business import ProductColor


class ProductVariantCreate(BaseModel):
    """Données pour créer une variante produit multi-dimensions."""

    color: Optional[ProductColor] = Field(
        default=None,
        description="Couleur optionnelle (ex: blanc, ivoire)",
    )
    size: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Taille/format optionnel (ex: 21cm, 240cm)",
    )
    gamme: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Gamme/finition optionnelle (ex: classique, elegance)",
    )
    label: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Label affiché — clé d'unicité par produit",
    )
    price_per_day: Optional[int] = Field(
        default=None,
        ge=0,
        description="Override prix parent en centimes (None = hérite parent)",
    )
    sku: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="SKU unique de la variante (ex: NAP-RND-240-IVO)",
    )
    stock_quantity: int = Field(default=0, ge=0, description="Stock total")
    available_quantity: int = Field(
        default=0, ge=0, description="Quantité disponible"
    )
    deposit_amount: int = Field(
        default=0, ge=0, description="Montant caution par unité en centimes"
    )
    image_url: Optional[str] = Field(
        default=None, max_length=500, description="Override image URL (None = hérite parent)"
    )
    weight_grams: Optional[int] = Field(
        default=None, ge=0, description="Override poids en grammes (None = hérite parent)"
    )
    volume_cm3: Optional[int] = Field(
        default=None, ge=0, description="Override volume en cm³ (None = hérite parent)"
    )

    model_config = ConfigDict(use_enum_values=True)

    @model_validator(mode="after")
    def at_least_one_dimension(self) -> "ProductVariantCreate":
        """Au moins une dimension parmi color, size, gamme doit être renseignée."""
        if not any([self.color, self.size, self.gamme]):
            raise ValueError(
                "Au moins une dimension requise parmi : color, size, gamme"
            )
        return self


class ProductVariantUpdate(BaseModel):
    """Données pour mettre à jour une variante (PATCH partiel)."""

    color: Optional[ProductColor] = None
    size: Optional[str] = Field(default=None, max_length=50)
    gamme: Optional[str] = Field(default=None, max_length=50)
    label: Optional[str] = Field(default=None, min_length=1, max_length=100)
    price_per_day: Optional[int] = Field(default=None, ge=0)
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    available_quantity: Optional[int] = Field(default=None, ge=0)
    deposit_amount: Optional[int] = Field(default=None, ge=0)
    image_url: Optional[str] = Field(default=None, max_length=500)
    weight_grams: Optional[int] = Field(default=None, ge=0)
    volume_cm3: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None

    model_config = ConfigDict(use_enum_values=True)


class ProductVariantNested(BaseModel):
    """Représentation minimale d'une variante pour inclusion dans les réponses nested."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    label: str
    color: Optional[str] = None
    size: Optional[str] = None
    gamme: Optional[str] = None
    sku: str
    price_per_day: Optional[int] = None
    image_url: Optional[str] = None
    weight_grams: Optional[int] = None
    volume_cm3: Optional[int] = None


class ProductVariantResponse(BaseModel):
    """Réponse API pour une variante produit."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    product_id: int
    color: Optional[str]
    size: Optional[str]
    gamme: Optional[str]
    label: str
    price_per_day: Optional[int]
    sku: str
    stock_quantity: int
    available_quantity: int
    deposit_amount: int
    image_url: Optional[str] = None
    weight_grams: Optional[int] = None
    volume_cm3: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
