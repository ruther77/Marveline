"""Endpoints — Cuisine restaurant.

6 endpoints :
  POST   /restaurant/instances-preparation                   → créer marmite (consomme recette)
  GET    /restaurant/instances-preparation                   → liste marmites du jour
  GET    /restaurant/instances-preparation/{id}              → détail marmite
  PATCH  /restaurant/instances-preparation/{id}/portions     → ajuster portions (±delta)
  GET    /restaurant/types-preparation                       → liste types (catalogue recettes)
  GET    /restaurant/types-preparation/{id}/stock-requis     → vérifier stock recette

Note: tickets-cuisine et marquer-pret sont dans commandes.py pour garantir
la priorité route statique > route paramétrique dans un même router FastAPI.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.restaurant.instance_preparation import (
    AjustPortionsRequest,
    InstancePreparationCreate,
    InstancePreparationResponse,
)
from app.schemas.restaurant.type_preparation import (
    RecetteLigneCreate,
    RecetteLigneResponse,
    StockRequisResponse,
    TypePreparationCreate,
    TypePreparationResponse,
    TypePreparationUpdate,
)
from app.services.restaurant.instance_preparation import InstancePreparationService
from app.services.restaurant.type_preparation import TypePreparationService

router = APIRouter(prefix="/restaurant", tags=["Restaurant — Cuisine"])


# ── Instances préparation (marmites) ─────────────────────────────────────────

@router.post("/instances-preparation", response_model=InstancePreparationResponse, status_code=201)
async def create_instance(
    payload: InstancePreparationCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> InstancePreparationResponse:
    """Crée une marmite et consomme atomiquement le stock de la recette."""
    result = await InstancePreparationService(db).create(
        payload, created_by_id=current_user.id
    )
    await db.commit()
    return result


@router.get("/instances-preparation", response_model=list[InstancePreparationResponse])
async def list_instances(
    date_cuisine: Optional[date] = Query(default=None, description="Date cuisine (défaut: aujourd'hui)"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> list[InstancePreparationResponse]:
    """Liste les marmites d'un jour (défaut: aujourd'hui)."""
    ref = date_cuisine or date.today()
    items, _ = await InstancePreparationService(db).list_by_date(ref, page, per_page)
    return items


@router.get("/instances-preparation/{instance_id}", response_model=InstancePreparationResponse)
async def get_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> InstancePreparationResponse:
    """Détail d'une marmite avec portions restantes (lu en DB, ADR-14)."""
    return await InstancePreparationService(db).get_by_id(instance_id)


@router.patch("/instances-preparation/{instance_id}/portions", response_model=InstancePreparationResponse)
async def ajuster_portions(
    instance_id: int,
    payload: AjustPortionsRequest,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> InstancePreparationResponse:
    """Ajuste les portions restantes (SELECT FOR UPDATE, ADR-14).
    delta négatif = réduction (portions servies), positif = correction.
    """
    result = await InstancePreparationService(db).ajuster_portions(instance_id, payload)
    await db.commit()
    return result


# ── Types de préparation (recettes) ──────────────────────────────────────────

@router.post("/types-preparation", response_model=TypePreparationResponse, status_code=201)
async def create_type_preparation(
    payload: TypePreparationCreate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> TypePreparationResponse:
    """Crée un nouveau type de préparation (recette / base)."""
    result = await TypePreparationService(db).create(payload)
    await db.commit()
    return result


@router.get("/types-preparation", response_model=list[TypePreparationResponse])
async def list_types_preparation(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> list[TypePreparationResponse]:
    """Catalogue des types de préparation (recettes) actifs."""
    items, _ = await TypePreparationService(db).list_actives(page, per_page)
    return items


@router.patch("/types-preparation/{tp_id}", response_model=TypePreparationResponse)
async def update_type_preparation(
    tp_id: int,
    payload: TypePreparationUpdate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> TypePreparationResponse:
    """Met à jour un type de préparation (nom, portions, notes)."""
    result = await TypePreparationService(db).update(tp_id, payload)
    await db.commit()
    return result


@router.delete("/types-preparation/{tp_id}", status_code=204)
async def delete_type_preparation(
    tp_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> None:
    """Soft-delete un type de préparation."""
    await TypePreparationService(db).soft_delete(tp_id)
    await db.commit()


@router.get("/types-preparation/{tp_id}/stock-requis", response_model=StockRequisResponse)
async def get_stock_requis(
    tp_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> StockRequisResponse:
    """Vérifie si le stock est suffisant pour un type de préparation."""
    return await TypePreparationService(db).get_stock_requis(tp_id)


@router.get("/types-preparation/{tp_id}/recette", response_model=list[RecetteLigneResponse])
async def list_recette(
    tp_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> list[RecetteLigneResponse]:
    """Liste les lignes de recette d'un type de préparation."""
    return await TypePreparationService(db).list_recette(tp_id)


@router.post("/types-preparation/{tp_id}/recette", response_model=RecetteLigneResponse, status_code=201)
async def add_recette_ligne(
    tp_id: int,
    payload: RecetteLigneCreate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> RecetteLigneResponse:
    """Ajoute un ingrédient à la recette d'un type de préparation."""
    result = await TypePreparationService(db).add_recette_ligne(tp_id, payload)
    await db.commit()
    return result


@router.delete("/types-preparation/{tp_id}/recette/{ligne_id}", status_code=204)
async def remove_recette_ligne(
    tp_id: int,
    ligne_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> None:
    """Supprime un ingrédient de la recette."""
    await TypePreparationService(db).remove_recette_ligne(tp_id, ligne_id)
    await db.commit()


# tickets-cuisine et marquer-pret sont dans commandes.py (même router que GET /commandes/{id})
# pour garantir la priorité route statique > route paramétrique dans FastAPI.
