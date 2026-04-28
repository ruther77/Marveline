"""Schemas Pydantic pour Formula et FormulaItem."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class FormulaItemBase(BaseModel):
    product_id: int
    quantity_per_person: float = Field(..., gt=0, description="Ratio par convive (ex: 3.0 = 3 unités/pers)")


class FormulaItemCreate(FormulaItemBase):
    pass


class FormulaItemResponse(FormulaItemBase):
    id: int
    formula_id: int

    model_config = {"from_attributes": True}


class FormulaBase(BaseModel):
    name: str = Field(..., max_length=200)
    slug: str = Field(..., max_length=100)
    description: Optional[str] = None
    formula_type: Literal["classic", "vin_honneur"] = "classic"
    price_per_person_cents: int = Field(..., gt=0, description="Prix TTC/pers en centimes")
    featured: bool = False
    sort_order: int = 0


class FormulaCreate(FormulaBase):
    items: List[FormulaItemCreate] = Field(default_factory=list)


class FormulaUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    formula_type: Optional[Literal["classic", "vin_honneur"]] = None
    price_per_person_cents: Optional[int] = Field(None, gt=0)
    featured: Optional[bool] = None
    sort_order: Optional[int] = None
    items: Optional[List[FormulaItemCreate]] = None


class FormulaResponse(FormulaBase):
    id: int
    tenant_id: int
    is_active: bool
    items: List[FormulaItemResponse] = []

    model_config = {"from_attributes": True}


class ApplyFormulaRequest(BaseModel):
    formula_id: int
    nb_guests: int = Field(..., gt=0, description="Nombre de convives")
    reservation_id: int


class ApplyFormulaResponse(BaseModel):
    formula_id: int
    nb_guests: int
    lines_created: int
    total_quantity: int
