"""Schemas Pydantic — Dashboard restaurant.

Shapes : V2_API_RESTAURANT.md §Page: Dashboard
`ca_cts`, `portions_restantes`, `stock_actuel_kg` : lus directement DB (ADR-14).
"""
from datetime import date
from typing import Optional

from app.schemas.base import BaseSchema


class DashboardStatsResponse(BaseSchema):
    """Shape GET /restaurant/dashboard/stats.

    `ca_variation_pct` : variation CA jour/jour-1 en pourcent (None si jour-1 = 0).
    Exemple : +12.5 = +12,5% vs hier ; -3.0 = -3% vs hier.
    """
    date: date
    ca_cts: int
    nb_couverts: int
    ticket_moyen_cts: int
    commandes_ouvertes: int
    marmites_actives: int
    ruptures_count: int
    ca_variation_pct: Optional[float] = None


class InstanceVideResponse(BaseSchema):
    instance_id: int
    type_preparation_nom: str
    portions_restantes: int


class IngredientEpuiseResponse(BaseSchema):
    ingredient_id: int
    nom: str
    stock_actuel_kg: float
    unite_stock: str


class RupturesResponse(BaseSchema):
    """Shape GET /restaurant/dashboard/ruptures."""
    instances_vides: list[InstanceVideResponse]
    ingredients_epuises: list[IngredientEpuiseResponse]
