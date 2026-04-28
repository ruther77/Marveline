"""Schémas Pydantic pour DamageType."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DamageTypeCreate(BaseModel):
    """Données pour créer un type de dommage."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Libellé du type de dommage"
    )
    default_fee_cents: int = Field(
        default=0,
        ge=0,
        description="Tarif par défaut en centimes (0 = montant à saisir)"
    )


class DamageTypeUpdate(BaseModel):
    """Données pour mettre à jour un type de dommage (PATCH partiel)."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    default_fee_cents: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class DamageTypeRead(BaseModel):
    """Réponse API pour un type de dommage."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: str
    default_fee_cents: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @property
    def default_fee_euros(self) -> float:
        return self.default_fee_cents / 100
