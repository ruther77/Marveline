"""Schémas Pydantic pour DeliveryZone."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeliveryZoneCreate(BaseModel):
    """Données pour créer une zone de livraison."""

    department_code: str = Field(
        ...,
        min_length=2,
        max_length=3,
        description="Code INSEE du département (ex: '60', '80', '02')",
    )
    department_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nom du département",
    )
    delivery_fee_cents: int = Field(
        default=0,
        ge=0,
        description="Tarif livraison de base en centimes (0 = sur devis)",
    )
    sunday_surcharge_cents: int = Field(
        default=0,
        ge=0,
        description="Supplément reprise dimanche en centimes",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Informations complémentaires",
    )

    @field_validator("department_code")
    @classmethod
    def validate_department_code(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit():
            raise ValueError("Le code département doit être numérique")
        return v


class DeliveryZoneUpdate(BaseModel):
    """Données pour mettre à jour une zone (PATCH partiel)."""

    department_name: Optional[str] = Field(
        default=None, min_length=1, max_length=100
    )
    delivery_fee_cents: Optional[int] = Field(default=None, ge=0)
    sunday_surcharge_cents: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class DeliveryZoneResponse(BaseModel):
    """Réponse API pour une zone de livraison."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    department_code: str
    department_name: str
    delivery_fee_cents: int
    sunday_surcharge_cents: int
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @property
    def delivery_fee_euros(self) -> float:
        return self.delivery_fee_cents / 100

    @property
    def sunday_surcharge_euros(self) -> float:
        return self.sunday_surcharge_cents / 100
