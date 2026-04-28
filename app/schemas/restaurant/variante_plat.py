"""Schemas Pydantic — VariantePlat.

`taux_tva` : INTEGER centièmes de % (ex: 550 = 5,5%). ADR-06-BIS — pas de taux global fixe.
Types : plat | boisson | formule.
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class VariantePlatCreate(BaseSchema):
    nom: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., pattern="^(plat|boisson|formule)$")
    prix_vente_cts: int = Field(..., ge=0, description="Prix TTC en centimes")
    taux_tva: int = Field(..., ge=0, description="Taux TVA en centièmes de % (ex: 550 = 5,5%)")
    categorie: Optional[str] = Field(None, max_length=50)
    image_url: Optional[str] = Field(None, max_length=500)
    type_preparation_id: Optional[int] = None
    ingredient_proteine_id: Optional[int] = None
    quantite_proteine: Optional[Decimal] = Field(None, gt=0)


class VariantePlatUpdate(BaseSchema):
    nom: Optional[str] = Field(None, min_length=1, max_length=200)
    prix_vente_cts: Optional[int] = Field(None, ge=0)
    taux_tva: Optional[int] = Field(None, ge=0)
    categorie: Optional[str] = Field(None, max_length=50)
    image_url: Optional[str] = Field(None, max_length=500)
    type_preparation_id: Optional[int] = None
    ingredient_proteine_id: Optional[int] = None
    quantite_proteine: Optional[Decimal] = Field(None, gt=0)
    is_active: Optional[bool] = None


class VariantePlatResponse(BaseSchema):
    id: int
    tenant_id: int
    nom: str
    type: str
    prix_vente_cts: int
    taux_tva: int
    image_url: Optional[str] = None
    type_preparation_id: Optional[int]
    type_preparation_nom: Optional[str] = None
    ingredient_proteine_id: Optional[int]
    ingredient_proteine_nom: Optional[str] = None
    quantite_proteine: Optional[Decimal]
    categorie: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CatalogueBoisson(BaseSchema):
    """Article boisson dans GET /restaurant/boissons/catalogue."""
    variante_plat_id: int
    nom: str
    categorie: Optional[str]
    prix_vente_cts: int
