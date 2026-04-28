"""Schemas Pydantic — IngredientRestaurant.

Shape JSON : V2_API_RESTAURANT.md §Page: Ingrédients & Stock
`statut` : ok | bas | rupture — calculé côté service.
`stock_actuel` : NUMERIC(10,3) lu directement en DB (ADR-14).
"""
from decimal import Decimal
from typing import Optional
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class IngredientCreate(BaseSchema):
    nom: str = Field(..., min_length=1, max_length=150)
    categorie_id: Optional[int] = None
    unite_stock: str = Field(..., max_length=20, description="Ex: kg, L, pièce")
    stock_actuel: Decimal = Field(default=Decimal("0.000"), ge=0)
    stock_alerte: Decimal = Field(default=Decimal("0.000"), ge=0)
    cout_unitaire_cts: int = Field(default=0, ge=0, description="Coût d'achat en centimes")


class IngredientUpdate(BaseSchema):
    nom: Optional[str] = Field(None, min_length=1, max_length=150)
    categorie_id: Optional[int] = None
    unite_stock: Optional[str] = Field(None, max_length=20)
    stock_alerte: Optional[Decimal] = Field(None, ge=0)
    cout_unitaire_cts: Optional[int] = Field(None, ge=0)


class IngredientResponse(BaseSchema):
    """Shape liste (V2_API_RESTAURANT.md §GET /restaurant/ingredients).

    statut : 'rupture' si stock_actuel=0, 'bas' si stock_actuel<=stock_alerte, 'ok' sinon.
    derniere_entree : date du dernier mouvement de type 'entree' (ou None).
    """
    id: int
    nom: str
    unite_stock: str
    stock_actuel: Decimal
    stock_alerte: Decimal
    cout_unitaire_cts: int
    image_url: Optional[str] = None
    statut: str = "ok"
    derniere_entree: Optional[datetime] = None
    categorie_id: Optional[int] = None
    categorie: Optional[str] = None


class IngredientListResponse(BaseSchema):
    items: list[IngredientResponse]
    page: int
    per_page: int
    total: int
    ruptures_count: int = 0
