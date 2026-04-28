"""Endpoints — Ingrédients & Stock restaurant.

5 endpoints ingrédients :
  GET    /restaurant/ingredients           → liste paginée avec filtre search
  POST   /restaurant/ingredients           → créer ingrédient
  PUT    /restaurant/ingredients/{id}      → modifier ingrédient
  GET    /restaurant/ingredients/epuises   → liste ingrédients épuisés

2 endpoints mouvements-stock :
  GET    /restaurant/mouvements-stock      → historique paginé (filtres type, date, ingredient)
  POST   /restaurant/mouvements-stock      → enregistrer mouvement (entrée, perte, inventaire)
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.restaurant.ingredient import (
    IngredientCreate,
    IngredientListResponse,
    IngredientResponse,
    IngredientUpdate,
)
from app.schemas.restaurant.mouvement_stock import (
    MouvementStockCreate,
    MouvementStockCreateSimple,
    MouvementStockListResponse,
    MouvementStockResponse,
)
from app.schemas.restaurant.categorie_ingredient import (
    CategorieIngredientCreate,
    CategorieIngredientResponse,
    CategorieIngredientUpdate,
)
from app.services.restaurant.categorie_ingredient import CategorieIngredientService
from app.services.restaurant.ingredient import IngredientService
from app.services.restaurant.mouvement_stock import MouvementStockService

router = APIRouter(prefix="/restaurant", tags=["Restaurant — Ingrédients & Stock"])


# ── Ingrédients ──────────────────────────────────────────────────────────────

@router.get("/ingredients/epuises", response_model=list[IngredientResponse])
async def list_ingredients_epuises(
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> list[IngredientResponse]:
    """Liste les ingrédients avec stock_actuel ≤ 0 (rupture totale)."""
    return await IngredientService(db).list_epuises()


@router.get("/categories-ingredient", response_model=list[CategorieIngredientResponse])
async def list_categories_ingredient(
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> list[CategorieIngredientResponse]:
    """Liste toutes les catégories d'ingrédients du tenant."""
    return await CategorieIngredientService(db).list_all()


@router.get("/ingredients", response_model=IngredientListResponse)
async def list_ingredients(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None, description="Recherche par nom"),
    categorie_id: Optional[int] = Query(default=None, description="Filtre par catégorie"),
    statut: Optional[str] = Query(default=None, description="Filtre par statut : ok | bas | rupture"),
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> IngredientListResponse:
    """Liste paginée des ingrédients avec niveau de stock."""
    return await IngredientService(db).list_paginated(page, per_page, search, categorie_id, statut)


@router.post("/ingredients", response_model=IngredientResponse, status_code=201)
async def create_ingredient(
    payload: IngredientCreate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> IngredientResponse:
    """Crée un nouvel ingrédient avec stock initial."""
    result = await IngredientService(db).create(payload)
    await db.commit()
    return result


@router.get("/ingredients/{ingredient_id}", response_model=IngredientResponse)
async def get_ingredient(
    ingredient_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> IngredientResponse:
    """Détail d'un ingrédient avec stock actuel (ADR-14)."""
    return await IngredientService(db).get_by_id(ingredient_id)


@router.put("/ingredients/{ingredient_id}", response_model=IngredientResponse)
async def update_ingredient(
    ingredient_id: int,
    payload: IngredientUpdate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> IngredientResponse:
    """Modifie un ingrédient (nom, seuil alerte, coût unitaire)."""
    result = await IngredientService(db).update(ingredient_id, payload)
    await db.commit()
    return result


@router.delete("/ingredients/{ingredient_id}", status_code=204)
async def delete_ingredient(
    ingredient_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> Response:
    """Soft-delete d'un ingrédient (is_active = False)."""
    await IngredientService(db).delete(ingredient_id)
    await db.commit()
    return Response(status_code=204)


@router.post("/categories-ingredient", response_model=CategorieIngredientResponse, status_code=201)
async def create_categorie_ingredient(
    payload: CategorieIngredientCreate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> CategorieIngredientResponse:
    """Crée une nouvelle catégorie d'ingrédients."""
    result = await CategorieIngredientService(db).create(payload)
    await db.commit()
    return result


@router.get("/categories-ingredient/{cat_id}/usages")
async def get_categorie_usages(
    cat_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> dict:
    """Nombre d'ingrédients actifs utilisant cette catégorie."""
    count = await CategorieIngredientService(db).count_usages(cat_id)
    return {"count": count}


@router.patch("/categories-ingredient/{cat_id}", response_model=CategorieIngredientResponse)
async def update_categorie_ingredient(
    cat_id: int,
    payload: CategorieIngredientUpdate,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> CategorieIngredientResponse:
    """Modifie une catégorie d'ingrédients (PATCH partiel)."""
    result = await CategorieIngredientService(db).update(cat_id, payload)
    await db.commit()
    return result


@router.delete("/categories-ingredient/{cat_id}", status_code=204)
async def delete_categorie_ingredient(
    cat_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> Response:
    """Supprime une catégorie (hard delete — FK SET NULL sur ingrédients)."""
    await CategorieIngredientService(db).delete(cat_id)
    await db.commit()
    return Response(status_code=204)


@router.post("/ingredients/{ingredient_id}/mouvements", status_code=201)
async def create_mouvement_for_ingredient(
    ingredient_id: int,
    payload: MouvementStockCreateSimple,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
):
    """Enregistre un mouvement de stock simplifié (date=now, ingredient du path).

    Retourne 204 si type=inventaire et delta=0 (stock inchangé).
    """
    result = await MouvementStockService(db).create_for_ingredient(
        ingredient_id, payload, created_by_id=current_user.id,
    )
    await db.commit()
    if result is None:
        return Response(status_code=204)
    return result


# ── Mouvements de stock ───────────────────────────────────────────────────────

@router.get("/mouvements-stock", response_model=MouvementStockListResponse)
async def list_mouvements(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    ingredient_id: Optional[int] = Query(default=None),
    type_mouvement: Optional[str] = Query(default=None),
    date_debut: Optional[datetime] = Query(default=None),
    date_fin: Optional[datetime] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> MouvementStockListResponse:
    """Historique paginé des mouvements de stock."""
    return await MouvementStockService(db).list_paginated(
        page, per_page, ingredient_id, type_mouvement, date_debut, date_fin
    )


@router.post("/mouvements-stock", status_code=201)
async def create_mouvement(
    payload: MouvementStockCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
):
    """Enregistre un mouvement de stock.

    Retourne 204 si type=inventaire et delta=0 (stock inchangé).
    """
    result = await MouvementStockService(db).create(payload, created_by_id=current_user.id)
    await db.commit()
    if result is None:
        return Response(status_code=204)
    return result
