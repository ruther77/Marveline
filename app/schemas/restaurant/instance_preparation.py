"""Schemas Pydantic — InstancePreparation (marmites).

Shapes :
  POST body   : V2_API_RESTAURANT.md §Body POST /restaurant/instances-preparation
  GET liste   : V2_API_RESTAURANT.md §Shape GET /restaurant/instances-preparation
  GET dashboard: V2_API_RESTAURANT.md §Shape GET /restaurant/dashboard/marmites
  PATCH portions: V2_API_RESTAURANT.md §PATCH /restaurant/instances-preparation/{id}/portions

`portions_restantes` : lu directement DB à chaque appel (ADR-14).
"""
from datetime import date, datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class InstancePreparationCreate(BaseSchema):
    """Body POST /restaurant/instances-preparation."""
    type_preparation_id: int
    portions_initiales: int = Field(..., ge=1)
    date_cuisine: date
    notes: Optional[str] = None


class AjustPortionsRequest(BaseSchema):
    """Body PATCH /restaurant/instances-preparation/{id}/portions — R6."""
    ajustement: int = Field(..., description="Signé : négatif = réduction, positif = correction")
    motif: str = Field(..., min_length=5, max_length=255)


class InstancePreparationResponse(BaseSchema):
    """Shape liste instances-preparation (cuisine page) — R1."""
    instance_id: int
    type_preparation_id: Optional[int] = None
    type_preparation_nom: str
    date_cuisine: date
    heure_lancement: Optional[datetime] = None  # R1 : heure de création
    created_by_nom: Optional[str] = None  # R1 : nom du cuisinier
    portions_initiales: int
    portions_restantes: int
    pourcentage_restant: int
    statut_badge: str = "dispo"  # R1 : dispo | faible | epuise
    est_fraiche: bool = True  # R1 : date_cuisine = today
    proteines_disponibles: list["ProteineDisponibleResponse"] = []  # R1


class ProteineDisponibleResponse(BaseSchema):
    """Protéine disponible par marmite (shape dashboard/marmites + liste cuisine)."""
    ingredient_id: int
    nom: str
    stock_actuel_kg: float
    stock_badge: Optional[str] = None  # R1 : full | low | out
    unite_stock: str = ""
    variante_plat_id: Optional[int] = None
    variante_nom: Optional[str] = None
    prix_vente_cts: Optional[int] = None


class MarmiteDetailResponse(BaseSchema):
    """Item de GET /restaurant/dashboard/marmites."""
    instance_id: int
    type_preparation_nom: str
    date_cuisine: date
    portions_initiales: int
    portions_restantes: int
    proteines_disponibles: list[ProteineDisponibleResponse]


class MarmitesDashboardResponse(BaseSchema):
    items: list[MarmiteDetailResponse]
