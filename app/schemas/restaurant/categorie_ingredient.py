"""Schemas Pydantic — CategorieIngredient (restaurant)."""
from typing import Optional

from app.schemas.base import BaseSchema


class CategorieIngredientCreate(BaseSchema):
    nom: str
    image_url: Optional[str] = None
    is_proteine: bool = False


class CategorieIngredientUpdate(BaseSchema):
    nom: Optional[str] = None
    image_url: Optional[str] = None
    is_proteine: Optional[bool] = None


class CategorieIngredientResponse(BaseSchema):
    id: int
    tenant_id: int
    nom: str
    image_url: str | None = None
    is_proteine: bool = False
