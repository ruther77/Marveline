"""Schemas Pydantic pour Reservation et ReservationLine."""
from datetime import date
from typing import Optional, Literal, TYPE_CHECKING
from pydantic import Field, field_validator, computed_field, model_validator
from app.schemas.base import BaseSchema, EntityResponseSchema

# Import pour type hints seulement (évite circular imports)
if TYPE_CHECKING:
    from app.schemas.customer import CustomerList
    from app.schemas.product import ProductList


class ReservationLineBase(BaseSchema):
    """Schema de base pour une ligne de réservation."""

    product_id: int = Field(
        ...,
        gt=0,
        description="ID du produit réservé"
    )

    quantity: int = Field(
        ...,
        gt=0,
        description="Quantité réservée"
    )

    unit_price_cents: int = Field(
        ...,
        ge=0,
        description="Prix unitaire par jour en centimes (snapshot)"
    )

    @computed_field
    @property
    def subtotal_cents(self) -> int:
        """Sous-total en centimes (quantity × unit_price)."""
        return self.quantity * self.unit_price_cents


class ReservationLineCreate(BaseSchema):
    """Schema pour création d'une ligne de réservation.

    Note: unit_price_cents sera automatiquement récupéré depuis le produit.

    Example:
        {
            "product_id": 1,
            "quantity": 50
        }
    """

    product_id: int = Field(
        ...,
        gt=0,
        description="ID du produit à réserver"
    )

    quantity: int = Field(
        ...,
        gt=0,
        description="Quantité à réserver"
    )


class ReservationLineResponse(EntityResponseSchema):
    """Schema complet pour réponse d'une ligne de réservation."""

    reservation_id: int
    product_id: int
    quantity: int
    unit_price_cents: int = Field(alias="unit_price")
    subtotal_cents: int = Field(alias="subtotal")

    # Relation nested optionnelle (product info)
    product: Optional["ProductList"] = None

    @computed_field
    @property
    def unit_price_euros(self) -> float:
        """Prix unitaire en euros pour affichage."""
        return self.unit_price_cents / 100

    @computed_field
    @property
    def subtotal_euros(self) -> float:
        """Sous-total en euros pour affichage."""
        return self.subtotal_cents / 100


class ReservationBase(BaseSchema):
    """Schema de base partagé entre Create et Update."""

    customer_id: int = Field(
        ...,
        gt=0,
        description="ID du client"
    )

    event_date: date = Field(
        ...,
        description="Date de l'événement"
    )

    delivery_date: date = Field(
        ...,
        description="Date de livraison"
    )

    return_date: date = Field(
        ...,
        description="Date de retour"
    )

    event_location: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Lieu de l'événement"
    )

    @model_validator(mode='after')
    def validate_dates_coherence(self):
        """Validation cohérence des dates.

        Rules:
            - delivery_date <= event_date
            - return_date >= event_date
            - return_date >= delivery_date
        """
        if self.delivery_date > self.event_date:
            raise ValueError("delivery_date must be before or equal to event_date")
        if self.return_date < self.event_date:
            raise ValueError("return_date must be after or equal to event_date")
        if self.return_date < self.delivery_date:
            raise ValueError("return_date must be after or equal to delivery_date")
        return self


class ReservationCreate(ReservationBase):
    """Schema pour création d'une réservation.

    Le reference sera généré automatiquement côté service (Redis INCR).
    Le status sera initialisé à 'draft'.
    Les montants seront calculés depuis les lignes.

    Example:
        {
            "customer_id": 1,
            "event_date": "2026-06-15",
            "delivery_date": "2026-06-14",
            "return_date": "2026-06-16",
            "event_location": "Château de Versailles",
            "lines": [
                {"product_id": 1, "quantity": 50},
                {"product_id": 2, "quantity": 100}
            ]
        }
    """

    lines: list[ReservationLineCreate] = Field(
        ...,
        min_length=1,
        description="Lignes de réservation (au moins une)"
    )

    @field_validator('lines')
    @classmethod
    def lines_not_empty(cls, v: list) -> list:
        """Validation qu'il y a au moins une ligne."""
        if not v:
            raise ValueError("At least one reservation line is required")
        return v


class ReservationUpdate(BaseSchema):
    """Schema pour mise à jour d'une réservation.

    Tous les champs sont optionnels (PATCH partiel).
    customer_id et reference sont immutables.
    Les lignes ne peuvent pas être modifiées via update (utiliser endpoints dédiés).

    Example:
        {
            "event_date": "2026-06-20",
            "delivery_date": "2026-06-19",
            "event_location": "Palais de Tokyo"
        }
    """

    event_date: Optional[date] = Field(
        default=None,
        description="Date de l'événement"
    )

    delivery_date: Optional[date] = Field(
        default=None,
        description="Date de livraison"
    )

    return_date: Optional[date] = Field(
        default=None,
        description="Date de retour"
    )

    event_location: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Lieu de l'événement"
    )

    deposit_paid: Optional[bool] = Field(
        default=None,
        description="Caution payée"
    )


class ReservationList(EntityResponseSchema):
    """Schema simplifié pour listes de réservations."""

    customer_id: int
    reference: str
    event_date: date
    status: str
    total_amount_cents: int = Field(alias="total_amount")

    @computed_field
    @property
    def total_amount_euros(self) -> float:
        """Montant total en euros pour affichage."""
        return self.total_amount_cents / 100


class ReservationResponse(EntityResponseSchema):
    """Schema complet pour réponse détaillée d'une réservation."""

    customer_id: int
    reference: str
    event_date: date
    delivery_date: date
    return_date: date
    event_location: Optional[str] = None
    status: Literal["draft", "confirmed", "in_progress", "completed", "cancelled"]
    total_amount_cents: int = Field(alias="total_amount")
    deposit_amount_cents: int = Field(alias="deposit_amount")
    deposit_paid: bool

    # Relations nested
    customer: Optional["CustomerList"] = None
    lines: list[ReservationLineResponse] = Field(default_factory=list)

    @computed_field
    @property
    def total_amount_euros(self) -> float:
        """Montant total en euros pour affichage."""
        return self.total_amount_cents / 100

    @computed_field
    @property
    def deposit_amount_euros(self) -> float:
        """Montant caution en euros pour affichage."""
        return self.deposit_amount_cents / 100

    @computed_field
    @property
    def rental_days(self) -> int:
        """Nombre de jours de location (return_date - delivery_date + 1)."""
        return (self.return_date - self.delivery_date).days + 1

    @computed_field
    @property
    def is_confirmed(self) -> bool:
        """Indique si la réservation est confirmée."""
        return self.status == "confirmed"

    @computed_field
    @property
    def is_cancelled(self) -> bool:
        """Indique si la réservation est annulée."""
        return self.status == "cancelled"

    model_config = EntityResponseSchema.model_config.copy()
    model_config["json_schema_extra"] = {
        "examples": [
            {
                "id": 1,
                "tenant_id": 1,
                "customer_id": 1,
                "reference": "RES-2026-0001",
                "event_date": "2026-06-15",
                "delivery_date": "2026-06-14",
                "return_date": "2026-06-16",
                "event_location": "Château de Versailles",
                "status": "confirmed",
                "total_amount_cents": 50000,
                "deposit_amount_cents": 10000,
                "deposit_paid": True,
                "is_active": True,
                "created_at": "2026-01-15T10:00:00Z",
                "updated_at": "2026-01-15T10:00:00Z"
            }
        ]
    }


# Résolution des forward references
from app.schemas.customer import CustomerList
from app.schemas.product import ProductList
ReservationLineResponse.model_rebuild()
ReservationResponse.model_rebuild()
