"""Schemas Pydantic — VarianteSide (liaison plat ↔ side avec supplément).

supplement_cts : centimes (BigInteger). 0 = inclus, 200 = +2€, etc.
"""
from typing import Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class VarianteSideCreate(BaseSchema):
    """Body POST /variantes-plat/{id}/sides."""
    side_id: int
    supplement_cts: int = Field(default=0, ge=0, description="Supplément en centimes")


class VarianteSideUpdate(BaseSchema):
    """Body PATCH /variantes-plat/{id}/sides/{side_id}."""
    supplement_cts: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class VarianteSideResponse(BaseSchema):
    """Shape retournée par GET /variantes-plat/{id}/sides."""
    id: int
    side_id: int
    side_nom: str = ""
    side_image_url: Optional[str] = None
    supplement_cts: int = 0
    is_active: bool = True
