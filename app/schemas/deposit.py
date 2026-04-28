"""Schémas Pydantic pour les cautions (deposits)."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.constants import DepositStatus


class DepositCreate(BaseModel):
    """Données pour créer une caution."""
    amount_cents: int = Field(..., gt=0, description="Montant en centimes (> 0)")
    collection_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)


class DepositUpdate(BaseModel):
    """Mise à jour du statut d'une caution."""
    status: DepositStatus
    retained_amount_cents: int | None = Field(default=None, gt=0)
    release_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_status_fields(self) -> "DepositUpdate":
        if self.status == "released" and self.release_date is None:
            raise ValueError("release_date is required when status is 'released'")
        if self.status == "retained" and self.retained_amount_cents is None:
            raise ValueError(
                "retained_amount_cents is required when status is 'retained'"
            )
        return self


class DepositRead(BaseModel):
    """Représentation complète d'une caution."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    reservation_id: int
    amount_cents: int
    status: str
    retained_amount_cents: int | None
    collection_date: date | None
    release_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class DepositWithReservation(DepositRead):
    """Deposit enrichi avec infos réservation pour la vue globale admin."""
    reservation_reference: str
    customer_name: str | None = None
    event_date: date | None = None


class DepositSummary(BaseModel):
    """KPI agrégés des cautions du tenant."""
    count_held: int = 0
    count_retained: int = 0
    count_released: int = 0
    total_held_cents: int = 0
    total_retained_cents: int = 0
    total_released_cents: int = 0
