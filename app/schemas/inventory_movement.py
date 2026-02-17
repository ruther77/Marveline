"""Schemas Pydantic pour les mouvements de stock (départs/retours)."""
from datetime import datetime
from typing import Optional

from pydantic import Field, field_validator, computed_field

from app.schemas.base import BaseSchema, EntityResponseSchema, TimestampSchema
from app.constants import (
    MovementType,
    MovementStatus,
    DeliveryMethod,
    InspectionStatus,
    ItemCondition,
)


# ── Movement Item Schemas ─────────────────────────────────────────────


class MovementItemCreate(BaseSchema):
    """Schema pour ajouter un article à un mouvement."""

    event_item_id: Optional[int] = Field(
        default=None,
        description="ID de l'item événement lié",
    )
    product_id: Optional[int] = Field(
        default=None,
        description="ID du produit",
    )
    product_variation_id: Optional[int] = Field(
        default=None,
        description="ID de la variation produit",
    )
    quantity_expected: int = Field(
        ...,
        gt=0,
        description="Quantité prévue",
    )
    condition: Optional[ItemCondition] = Field(
        default=None,
        description="État de l'article",
    )
    condition_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Notes sur l'état",
    )


class MovementItemUpdate(BaseSchema):
    """Schema pour mettre à jour un article de mouvement."""

    quantity_actual: Optional[int] = Field(
        default=None,
        ge=0,
        description="Quantité réellement reçue/envoyée",
    )
    condition: Optional[ItemCondition] = Field(
        default=None,
        description="État de l'article",
    )
    condition_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Notes sur l'état",
    )


class MovementItemResponse(TimestampSchema):
    """Schema de réponse pour un article de mouvement."""

    id: int
    movement_id: int
    event_item_id: Optional[int] = None
    product_id: Optional[int] = None
    product_variation_id: Optional[int] = None
    quantity_expected: int
    quantity_actual: Optional[int] = None
    condition: Optional[str] = None
    condition_notes: Optional[str] = None


# ── Movement Schemas ──────────────────────────────────────────────────


class MovementCreate(BaseSchema):
    """Schema pour créer un mouvement avec ses articles."""

    event_id: Optional[int] = Field(
        default=None,
        description="ID de l'événement lié",
    )
    movement_type: MovementType = Field(
        ...,
        description="Type de mouvement (departure / return)",
    )
    scheduled_date: datetime = Field(
        ...,
        description="Date prévue du mouvement (ISO datetime)",
    )
    delivery_method: Optional[DeliveryMethod] = Field(
        default=None,
        description="Mode de livraison",
    )
    delivery_address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Adresse de livraison",
    )
    delivery_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Notes de livraison",
    )
    reservation_id: Optional[int] = Field(
        default=None,
        description="ID de la réservation liée",
    )
    items: list[MovementItemCreate] = Field(
        ...,
        min_length=1,
        description="Articles du mouvement (min 1)",
    )


class MovementUpdate(BaseSchema):
    """Schema pour mise à jour partielle d'un mouvement (PATCH)."""

    scheduled_date: Optional[datetime] = Field(
        default=None,
        description="Date prévue du mouvement",
    )
    actual_date: Optional[datetime] = Field(
        default=None,
        description="Date effective du mouvement",
    )
    status: Optional[MovementStatus] = Field(
        default=None,
        description="Nouveau statut",
    )
    delivery_method: Optional[DeliveryMethod] = Field(
        default=None,
        description="Mode de livraison",
    )
    delivery_address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Adresse de livraison",
    )
    delivery_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Notes de livraison",
    )
    handled_by_user_id: Optional[int] = Field(
        default=None,
        description="ID du responsable",
    )
    inspection_status: Optional[InspectionStatus] = Field(
        default=None,
        description="Statut d'inspection",
    )
    inspection_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Notes d'inspection",
    )
    damage_fee: Optional[int] = Field(
        default=None,
        ge=0,
        description="Frais de dommages en centimes",
    )


class MovementResponse(EntityResponseSchema):
    """Schema complet pour un mouvement avec ses articles."""

    event_id: Optional[int] = None
    reservation_id: Optional[int] = None
    movement_type: str
    scheduled_date: datetime
    actual_date: Optional[datetime] = None
    status: str
    delivery_method: Optional[str] = None
    delivery_address: Optional[str] = None
    delivery_notes: Optional[str] = None
    handled_by_user_id: Optional[int] = None
    inspection_status: Optional[str] = None
    inspection_notes: Optional[str] = None
    damage_fee: int = 0
    items: list[MovementItemResponse] = Field(default_factory=list)

    @computed_field
    @property
    def damage_fee_euros(self) -> float:
        """Frais de dommages en euros pour affichage."""
        return self.damage_fee / 100


class MovementListItem(EntityResponseSchema):
    """Schema simplifié pour listes de mouvements (sans items)."""

    event_id: Optional[int] = None
    reservation_id: Optional[int] = None
    movement_type: str
    scheduled_date: datetime
    actual_date: Optional[datetime] = None
    status: str
    delivery_method: Optional[str] = None
    items_count: int = 0


class MovementStatistics(BaseSchema):
    """Schema pour les statistiques des mouvements."""

    total_movements: int = 0
    scheduled: int = 0
    in_transit: int = 0
    completed: int = 0
    late: int = 0
    cancelled: int = 0
    total_damage_fees: int = 0

    @computed_field
    @property
    def total_damage_fees_euros(self) -> float:
        """Total frais dommages en euros."""
        return self.total_damage_fees / 100


# ── Agenda Schemas ────────────────────────────────────────────────────


class AgendaItem(BaseSchema):
    """Schema pour un item de l'agenda (événement/réservation avec mouvements)."""

    event_id: Optional[int] = Field(
        None,
        description="ID événement (legacy, peut être null)",
    )
    reservation_id: Optional[int] = Field(
        None,
        description="ID réservation",
    )
    customer_name: str = Field(
        ...,
        description="Nom du client",
    )
    event_type: str = Field(
        default="",
        description="Type d'événement",
    )
    event_date: datetime = Field(
        ...,
        description="Date de l'événement",
    )
    rental_start_date: datetime = Field(
        ...,
        description="Date début location",
    )
    rental_end_date: datetime = Field(
        ...,
        description="Date fin location",
    )
    status: str = Field(
        ...,
        description="Statut de la réservation",
    )
    departure: Optional[MovementListItem] = Field(
        default=None,
        description="Mouvement de départ (si existant)",
    )
    return_movement: Optional[MovementListItem] = Field(
        default=None,
        description="Mouvement de retour (si existant)",
    )


class AgendaView(BaseSchema):
    """Schema pour la vue agenda complète."""

    date_start: str = Field(
        ...,
        description="Date de début de la plage (YYYY-MM-DD)",
    )
    date_end: str = Field(
        ...,
        description="Date de fin de la plage (YYYY-MM-DD)",
    )
    events: list[AgendaItem] = Field(
        default_factory=list,
        description="Liste des événements/réservations avec mouvements",
    )
    total_departures: int = Field(
        default=0,
        description="Nombre total de départs dans la plage",
    )
    total_returns: int = Field(
        default=0,
        description="Nombre total de retours dans la plage",
    )
