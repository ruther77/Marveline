"""Schemas Pydantic — SideRestaurant (accompagnements)."""
from decimal import Decimal
from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema


class SideCreate(BaseSchema):
    nom: str = Field(..., min_length=1, max_length=150)
    image_url: Optional[str] = Field(None, max_length=500)
    ingredient_id: Optional[int] = None
    quantite_par_portion: Optional[Decimal] = Field(None, gt=0)

    @model_validator(mode="after")
    def check_ingredient_quantite_couplees(self) -> "SideCreate":
        ing = self.ingredient_id
        qty = self.quantite_par_portion
        if (ing is None) != (qty is None):
            raise ValueError("ingredient_id et quantite_par_portion doivent être renseignés ensemble")
        return self


class SideUpdate(BaseSchema):
    nom: Optional[str] = Field(None, min_length=1, max_length=150)
    image_url: Optional[str] = Field(None, max_length=500)
    ingredient_id: Optional[int] = None
    quantite_par_portion: Optional[Decimal] = Field(None, gt=0)
    is_active: Optional[bool] = None


class SideResponse(BaseSchema):
    id: int
    tenant_id: int
    nom: str
    image_url: Optional[str] = None
    ingredient_id: Optional[int]
    ingredient_nom: Optional[str] = None
    quantite_par_portion: Optional[Decimal]
    is_active: bool
    nb_plats_lies: int = 0
    created_at: datetime
    updated_at: datetime
