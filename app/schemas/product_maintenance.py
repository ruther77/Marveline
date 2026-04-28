"""Schémas Pydantic pour ProductMaintenance."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MaintenanceStatus = Literal["scheduled", "in_progress", "completed", "cancelled"]


class MaintenanceCreate(BaseModel):
    """Données pour créer une maintenance produit."""

    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    scheduled_date: Optional[date] = None
    cost_cents: Optional[int] = Field(default=None, ge=0)


class MaintenanceUpdate(BaseModel):
    """Données pour mettre à jour une maintenance (PATCH partiel)."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    scheduled_date: Optional[date] = None
    completed_date: Optional[date] = None
    cost_cents: Optional[int] = Field(default=None, ge=0)
    status: Optional[MaintenanceStatus] = None


class MaintenanceResponse(BaseModel):
    """Réponse API pour une maintenance produit."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    product_id: int
    title: str
    description: Optional[str]
    scheduled_date: Optional[date]
    completed_date: Optional[date]
    cost_cents: Optional[int]
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
