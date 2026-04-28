"""Schemas Pydantic — TypePreparation + stock requis.

Shapes : V2_API_RESTAURANT.md §GET /restaurant/types-preparation/{id}/stock-requis
`stock_actuel` lu directement DB (ADR-14) — jamais mis en cache.
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class TypePreparationCreate(BaseSchema):
    nom: str = Field(..., min_length=1, max_length=150)
    portions_par_batch: int = Field(..., ge=1)
    temps_cuisson_min: int = Field(default=0, ge=0)
    notes: Optional[str] = None


class TypePreparationUpdate(BaseSchema):
    nom: Optional[str] = Field(None, min_length=1, max_length=150)
    portions_par_batch: Optional[int] = Field(None, ge=1)
    temps_cuisson_min: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class TypePreparationResponse(BaseSchema):
    id: int
    tenant_id: int
    nom: str
    portions_par_batch: int
    temps_cuisson_min: int = 0
    image_url: Optional[str] = None
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RecetteLigneCreate(BaseSchema):
    """Payload POST /restaurant/types-preparation/{id}/recette."""
    ingredient_id: int
    quantite_par_batch: Decimal = Field(..., gt=0)
    notes: Optional[str] = None


class RecetteLigneResponse(BaseSchema):
    """Shape d'une ligne de recette."""
    id: int
    ingredient_id: int
    nom: str
    quantite_par_batch: Decimal
    unite: str
    notes: Optional[str]


class IngredientRequisResponse(BaseSchema):
    """Ligne de stock requis pour un type de préparation."""
    ingredient_id: int
    nom: str
    quantite_par_batch: Decimal
    unite: str
    stock_actuel: Decimal
    suffisant: bool


class StockRequisResponse(BaseSchema):
    """Shape GET /restaurant/types-preparation/{id}/stock-requis."""
    type_preparation_id: int
    nom: str
    portions_par_batch: int
    ingredients_requis: list[IngredientRequisResponse]
