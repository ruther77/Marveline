"""Schemas Pydantic — TableRestaurant.

Shape : V2_API_RESTAURANT.md §GET /restaurant/tables
`statut` calculé côté service : LIBRE | OUVERTE | SERVIE (R3, ADR-14).
"""
from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class TableCreate(BaseSchema):
    """Body POST /restaurant/tables."""
    numero: str = Field(..., min_length=1, max_length=20)
    capacite: int = Field(default=4, ge=1)


class TableUpdate(BaseSchema):
    """Body PATCH /restaurant/tables/{id}."""
    numero: Optional[str] = Field(None, min_length=1, max_length=20)
    capacite: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class LignePreviewResponse(BaseSchema):
    """Aperçu ligne pour affichage carte table (S6 — GET /restaurant/tables)."""
    ligne_id: int
    variante_nom: str
    quantite: int
    statut_plat: str


class CommandeActiveResponse(BaseSchema):
    """Commande active imbriquée dans la réponse table."""
    commande_id: int
    nb_couverts: int
    nom_client: Optional[str] = None
    date_ouverture: datetime
    nb_plats: int
    nb_plats_servis: int
    total_provisoire_cts: int
    lignes_preview: list[LignePreviewResponse]


class TableResponse(BaseSchema):
    """Item de GET /restaurant/tables."""
    id: int
    numero: str
    capacite: int
    statut: str  # LIBRE | OUVERTE | SERVIE — calculé, non stocké (R3)
    commande_active: Optional[CommandeActiveResponse]


class TableListResponse(BaseSchema):
    items: list[TableResponse]
