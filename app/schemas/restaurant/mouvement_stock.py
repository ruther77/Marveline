"""Schemas Pydantic — MouvementStockRestaurant.

Shape : V2_API_RESTAURANT.md §POST /restaurant/mouvements-stock
Types valides : entree | consommation | transfert_entrant | inventaire | perte.
`quantite` en body : toujours positive — le backend applique le signe.
`stock_apres` : snapshot enregistré atomiquement dans le mouvement.
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import BaseSchema

TYPES_MOUVEMENT_VALIDES = {"entree", "consommation", "transfert_entrant", "inventaire", "perte"}

_TYPE_PATTERN = "^(entree|consommation|transfert_entrant|inventaire|perte)$"


class MouvementStockCreate(BaseSchema):
    ingredient_id: int
    type_mouvement: str = Field(..., pattern=_TYPE_PATTERN)
    quantite: Decimal = Field(..., gt=0, description="Quantité toujours positive — signe géré backend")
    date_mouvement: datetime
    notes: Optional[str] = Field(None, max_length=500)


class MouvementStockCreateSimple(BaseSchema):
    """Body simplifié pour POST /restaurant/ingredients/{id}/mouvements.

    ingredient_id extrait du path, date_mouvement=now() automatique.
    """
    type_mouvement: str = Field(..., pattern=_TYPE_PATTERN)
    quantite: Decimal = Field(..., gt=0)
    notes: Optional[str] = Field(None, max_length=500)


class MouvementStockResponse(BaseSchema):
    id: int
    tenant_id: int
    ingredient_id: int
    ingredient_nom: str = ""
    ingredient_unite: str = ""
    type_mouvement: str
    quantite: Decimal
    stock_apres: Decimal
    date_mouvement: datetime
    notes: Optional[str]
    created_by_name: Optional[str] = None
    created_at: datetime


class MouvementStockListResponse(BaseSchema):
    items: list[MouvementStockResponse]
    page: int
    per_page: int
    total: int
