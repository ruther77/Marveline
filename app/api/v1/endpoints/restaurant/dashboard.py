"""Endpoints — Dashboard restaurant.

4 endpoints :
  GET /restaurant/dashboard/stats     → KPIs du jour (CA, couverts, commandes, ruptures)
  GET /restaurant/dashboard/marmites  → Marmites actives + protéines disponibles
  GET /restaurant/dashboard/ruptures  → Instances vides + ingrédients épuisés
  GET /restaurant/dashboard/activite  → Commandes récentes (vue manageur)
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.restaurant.dashboard import (
    DashboardStatsResponse,
    RupturesResponse,
)
from app.schemas.restaurant.instance_preparation import MarmitesDashboardResponse
from app.services.restaurant.commande import CommandeService
from app.services.restaurant.dashboard import DashboardService

router = APIRouter(prefix="/restaurant/dashboard", tags=["Restaurant — Dashboard"])

_DATE_QUERY = Query(default=None, description="Date de référence (défaut: aujourd'hui)")


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_stats(
    date_ref: Optional[date] = _DATE_QUERY,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> DashboardStatsResponse:
    """KPIs du jour : CA, couverts, ticket moyen, commandes ouvertes, marmites, ruptures."""
    ref = date_ref or date.today()
    return await DashboardService(db).get_stats(ref)


@router.get("/marmites", response_model=MarmitesDashboardResponse)
async def get_marmites(
    date_ref: Optional[date] = _DATE_QUERY,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> MarmitesDashboardResponse:
    """Marmites actives du jour avec protéines disponibles et stock."""
    ref = date_ref or date.today()
    return await DashboardService(db).get_marmites(ref)


@router.get("/ruptures", response_model=RupturesResponse)
async def get_ruptures(
    date_ref: Optional[date] = _DATE_QUERY,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> RupturesResponse:
    """Instances vides (portions=0) + ingrédients épuisés du jour."""
    ref = date_ref or date.today()
    return await DashboardService(db).get_ruptures(ref)


@router.get("/activite")
async def get_activite(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    statut: Optional[str] = Query(default=None),
    date_debut: Optional[datetime] = Query(default=None),
    date_fin: Optional[datetime] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
):
    """Activité récente — liste paginée des commandes (vue manageur)."""
    return await CommandeService(db).list_paginated(
        page=page,
        per_page=per_page,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
    )
