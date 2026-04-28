"""Schemas Pydantic pour l'entité Product (catalogue de vaisselle)."""
from datetime import date, datetime
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

    cleaning_fee_cents: int = Field(
        default=0,
        ge=0,
        description="Frais de nettoyage en centimes (0 = inclus dans le prix)"
    )

    description: Optional[str] = Field(
        default=None,
        description="Description longue du produit"
    )

    short_description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Description courte du produit"
    )

    requires_advance_booking_days: int = Field(
        default=0,
        ge=0,
        description="Délai minimum de réservation en jours (90 pour nappages)"
    )

    weight_grams: Optional[int] = Field(
        default=None,
        ge=0,
        description="Poids unitaire en grammes (NULL = non renseigné)"
    )

    volume_cm3: Optional[int] = Field(
        default=None,
        ge=0,
        description="Volume unitaire en cm³ (NULL = non renseigné)"
    )

    supplier_id: Optional[int] = Field(
        default=None,
        description="ID du fournisseur principal (optionnel)"
    )

    tva_rate: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Taux TVA appliqué (ex: 0.20 = 20%, 0.055 = 5.5%)"
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

    cleaning_fee_cents: Optional[int] = Field(
        default=None,
        ge=0,
        description="Frais de nettoyage en centimes"
    )

    description: Optional[str] = Field(
        default=None,
        description="Description longue du produit"
    )

    short_description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Description courte du produit"
    )

    requires_advance_booking_days: Optional[int] = Field(
        default=None,
        ge=0,
        description="Délai minimum de réservation en jours"
    )

    weight_grams: Optional[int] = Field(
        default=None,
        ge=0,
        description="Poids unitaire en grammes"
    )

    volume_cm3: Optional[int] = Field(
        default=None,
        ge=0,
        description="Volume unitaire en cm³"
    )

    supplier_id: Optional[int] = Field(
        default=None,
        description="ID du fournisseur principal (optionnel)"
    )

    tva_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Taux TVA appliqué (ex: 0.20 = 20%, 0.055 = 5.5%)"
    )


class ProductList(EntityResponseSchema):
    """Schema simplifié pour listes de produits."""

    name: str
    sku: str
    category: str
    price_per_day_cents: int
    stock_quantity: int
    available_quantity: int
    condition: str
    image_url: Optional[str] = None
    supplier_id: Optional[int] = None
    weight_grams: Optional[int] = None
    volume_cm3: Optional[int] = None

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
    price_per_day_cents: int
    deposit_amount_cents: int
    stock_quantity: int
    available_quantity: int
    condition: str
    image_url: Optional[str] = None
    cleaning_fee_cents: int = 0
    description: Optional[str] = None
    short_description: Optional[str] = None
    requires_advance_booking_days: int = 0
    qty_reserved: int = 0
    qty_on_location: int = 0
    qty_damaged: int = 0
    qty_in_repair: int = 0
    supplier_id: Optional[int] = None
    tva_rate: float = 0.20
    weight_grams: Optional[int] = None
    volume_cm3: Optional[int] = None
    images: list["ProductImageResponse"] = []

    @computed_field
    @property
    def price_per_day_euros(self) -> float:
        """Prix location par jour en euros pour affichage."""
        return self.price_per_day_cents / 100

    @computed_field
    @property
    def cleaning_fee_euros(self) -> float:
        """Frais de nettoyage en euros pour affichage."""
        return self.cleaning_fee_cents / 100

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


class ProductImageResponse(EntityResponseSchema):
    """Schéma de réponse pour une image produit."""

    product_id: int
    url: str
    sort_order: int
    is_primary: bool


class ProductImageReorder(BaseSchema):
    """Schéma pour réordonner les images d'un produit."""

    image_ids: list[int]


class StockItemRead(EntityResponseSchema):
    """Schéma de lecture d'une unité physique de stock."""

    product_id: int
    serial_number: Optional[str] = None
    status: str
    current_reservation_id: Optional[int] = None
    notes: Optional[str] = None


class StockDetail(BaseSchema):
    """Détail du stock d'un produit : compteurs + liste des unités."""

    product_id: int
    qty_available: int
    qty_reserved: int
    qty_on_location: int
    qty_damaged: int
    qty_in_repair: int
    qty_retired: int
    total: int
    items: list[StockItemRead]


class StockBatchResponse(BaseSchema):
    """Réponse batch pour le détail stock de plusieurs produits."""

    items: list[StockDetail]


class StockItemHistoryEntry(BaseSchema):
    """Une entrée dans l'historique d'un stock_item : un mouvement le concernant."""

    movement_id: int
    movement_type: str
    scheduled_date: datetime
    actual_date: Optional[datetime] = None
    movement_status: str
    reservation_id: Optional[int] = None
    status_before: Optional[str] = None
    status_after: Optional[str] = None
    condition: Optional[str] = None
    condition_notes: Optional[str] = None


class StockItemHistory(BaseSchema):
    """Historique complet d'une unité physique de stock."""

    stock_item_id: int
    product_id: int
    serial_number: Optional[str] = None
    current_status: str
    entries: list[StockItemHistoryEntry]


class StockItemStatusUpdate(BaseSchema):
    """Mise à jour du statut d'une unité physique de stock."""

    status: str = Field(
        ...,
        description="Nouveau statut : available, reserved, on_location, damaged, in_repair, retired",
    )


class ProductAvailabilitySlot(BaseSchema):
    """Créneau d'indisponibilité d'un produit."""

    date_from: date
    date_to: date
    reserved_quantity: int
    reservation_id: int
    reservation_ref: Optional[str] = None


class ProductAvailabilityResponse(BaseSchema):
    """Réponse disponibilité produit sur une plage de dates."""

    product_id: int
    total_quantity: int
    date_from: date
    date_to: date
    busy_slots: list[ProductAvailabilitySlot]
