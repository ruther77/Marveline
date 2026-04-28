"""Endpoints — Sourcing ingrédients restaurant (mappings vers produits épicerie).

Mapping durable ingrédient ↔ N produits épicerie avec ordre de préférence.
Le résolveur (cascade mixte) propose des prélèvements pour réapprovisionner
un ingrédient donné en puisant dans les stocks épicerie.

Routes :
  GET    /restaurant/ingredients/{id}/produits-epicerie           → liste enrichie
  POST   /restaurant/ingredients/{id}/produits-epicerie           → ajout mapping
  PATCH  /restaurant/ingredients/{id}/produits-epicerie/{prod_id} → update (ordre/facteur)
  DELETE /restaurant/ingredients/{id}/produits-epicerie/{prod_id} → suppression
  POST   /restaurant/ingredients/{id}/produits-epicerie/reorder   → reorder batch
  POST   /restaurant/ingredients/{id}/resolve-preview             → dry-run résolveur
  GET    /restaurant/sourcing/produits-epicerie                   → recherche produits
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.models.epicerie.produit import EpicerieProduit
from app.models.epicerie.stock import EpicerieStock
from app.models.tenant import Tenant
from app.schemas.restaurant.ingredient_epicerie_mapping import (
    MappingCreate,
    MappingListResponse,
    MappingRead,
    MappingReorderRequest,
    MappingUpdate,
    MappingWithProduit,
    ResolveRequest,
    ResolveResponse,
)
from app.services.restaurant.ingredient_sourcing import IngredientSourcingService

router = APIRouter(prefix="/restaurant", tags=["Restaurant — Sourcing ingrédients"])


@router.get(
    "/ingredients/{ingredient_id}/produits-epicerie",
    response_model=MappingListResponse,
)
async def list_mappings(
    ingredient_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> MappingListResponse:
    """Liste des produits épicerie sources d'un ingrédient, triés par ordre."""
    items = await IngredientSourcingService(db).list_mappings(
        ingredient_id, current_user.tenant_id,
    )
    return MappingListResponse(items=items)


@router.post(
    "/ingredients/{ingredient_id}/produits-epicerie",
    response_model=MappingRead,
    status_code=201,
)
async def add_mapping(
    ingredient_id: int,
    payload: MappingCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> MappingRead:
    """Ajoute un produit épicerie comme source d'un ingrédient."""
    mapping = await IngredientSourcingService(db).add_mapping(
        ingredient_id, current_user.tenant_id, payload,
    )
    await db.commit()
    return MappingRead.model_validate(mapping, from_attributes=True)


@router.patch(
    "/ingredients/{ingredient_id}/produits-epicerie/{produit_id}",
    response_model=MappingRead,
)
async def update_mapping(
    ingredient_id: int,
    produit_id: int,
    payload: MappingUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> MappingRead:
    """Modifie ordre, facteur_conv ou notes d'un mapping existant."""
    mapping = await IngredientSourcingService(db).update_mapping(
        ingredient_id, produit_id, current_user.tenant_id, payload,
    )
    await db.commit()
    return MappingRead.model_validate(mapping, from_attributes=True)


@router.delete(
    "/ingredients/{ingredient_id}/produits-epicerie/{produit_id}",
    status_code=204,
)
async def delete_mapping(
    ingredient_id: int,
    produit_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> Response:
    """Supprime un mapping (hard delete, pas de soft delete sur table pivot)."""
    await IngredientSourcingService(db).remove_mapping(
        ingredient_id, produit_id, current_user.tenant_id,
    )
    await db.commit()
    return Response(status_code=204)


@router.post(
    "/ingredients/{ingredient_id}/produits-epicerie/reorder",
    response_model=list[MappingRead],
)
async def reorder_mappings(
    ingredient_id: int,
    payload: MappingReorderRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> list[MappingRead]:
    """Met à jour l'ordre de plusieurs mappings en batch (drag-drop)."""
    mappings = await IngredientSourcingService(db).reorder_mappings(
        ingredient_id, current_user.tenant_id, payload,
    )
    await db.commit()
    return [MappingRead.model_validate(m, from_attributes=True) for m in mappings]


class ProduitEpicerieSearchItem(BaseModel):
    """Résultat de recherche produit épicerie (pour le picker de mapping)."""
    id: int
    tenant_id: int
    designation_clean: str
    ean: Optional[str] = None
    unite_vente: str
    prix_achat_cts: int
    stock_disponible: float = 0


class ProduitEpicerieSearchResponse(BaseModel):
    items: list[ProduitEpicerieSearchItem]


@router.get(
    "/sourcing/produits-epicerie",
    response_model=ProduitEpicerieSearchResponse,
)
async def search_produits_epicerie(
    q: Optional[str] = Query(default=None, min_length=2, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    _: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> ProduitEpicerieSearchResponse:
    """Recherche produits épicerie (tous tenants épicerie actifs).

    Utilisé par le picker de mapping côté fiche ingrédient. Scope
    RESTAURANT_WRITE : réservé aux utilisateurs qui éditent les mappings.
    """
    stmt = (
        select(EpicerieProduit, EpicerieStock.quantite)
        .join(Tenant, Tenant.id == EpicerieProduit.tenant_id)
        .outerjoin(EpicerieStock, EpicerieStock.produit_id == EpicerieProduit.id)
        .where(
            Tenant.app_code == "epicerie",
            EpicerieProduit.actif.is_(True),
        )
        .order_by(EpicerieProduit.designation_clean.asc())
        .limit(limit)
    )
    if q:
        q_like = f"%{q.upper()}%"
        stmt = stmt.where(
            or_(
                EpicerieProduit.designation_clean.ilike(q_like),
                EpicerieProduit.ean == q,
            )
        )

    rows = (await db.execute(stmt)).all()
    items = [
        ProduitEpicerieSearchItem(
            id=prod.id,
            tenant_id=prod.tenant_id,
            designation_clean=prod.designation_clean,
            ean=prod.ean,
            unite_vente=prod.unite_vente,
            prix_achat_cts=prod.prix_achat_cts,
            stock_disponible=float(stock_qte or 0),
        )
        for prod, stock_qte in rows
    ]
    return ProduitEpicerieSearchResponse(items=items)


@router.post(
    "/ingredients/{ingredient_id}/resolve-preview",
    response_model=ResolveResponse,
)
async def resolve_preview(
    ingredient_id: int,
    payload: ResolveRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> ResolveResponse:
    """Dry-run du résolveur cascade mixte — ne modifie rien, retourne la
    proposition de prélèvement avec flag couverture_complete + déficit.
    """
    from app.core.exceptions import NotFound as NotFoundExc

    try:
        return await IngredientSourcingService(db).resolve(
            ingredient_id, payload.qte_besoin, current_user.tenant_id,
        )
    except ValueError as exc:
        raise NotFoundExc("Ingrédient") from exc
