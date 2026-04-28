"""Endpoints CRUD Formulas Marveline."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.exceptions import NotFound
from app.core.permissions import Scope
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.formula import (
    ApplyFormulaRequest,
    ApplyFormulaResponse,
    FormulaCreate,
    FormulaResponse,
    FormulaUpdate,
)
from app.services.formula import FormulaService

router = APIRouter(prefix="/formulas", tags=["formulas"])


@router.get("", response_model=PaginatedResponse[FormulaResponse])
async def list_formulas(
    formula_type: Optional[str] = Query(None, description="'classic' | 'vin_honneur'"),
    featured_only: bool = Query(False),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
) -> PaginatedResponse[FormulaResponse]:
    formulas, total = await FormulaService(db).list_formulas(
        current_user.tenant_id, formula_type, featured_only,
        skip=pagination.skip, limit=pagination.limit,
    )
    return PaginatedResponse(
        items=[FormulaResponse.model_validate(f) for f in formulas],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{formula_id}", response_model=FormulaResponse)
async def get_formula(
    formula_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
):
    try:
        return await FormulaService(db).get_formula(formula_id, current_user.tenant_id)
    except NotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("", response_model=FormulaResponse, status_code=status.HTTP_201_CREATED)
async def create_formula(
    payload: FormulaCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(
        require_scope(Scope.PRODUCTS_WRITE)
    ),
):
    data = payload.model_dump()
    return await FormulaService(db).create_formula(current_user.tenant_id, data)


@router.patch("/{formula_id}", response_model=FormulaResponse)
async def update_formula(
    formula_id: int,
    payload: FormulaUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(
        require_scope(Scope.PRODUCTS_WRITE)
    ),
):
    try:
        data = payload.model_dump(exclude_none=True)
        return await FormulaService(db).update_formula(formula_id, current_user.tenant_id, data)
    except NotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{formula_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_formula(
    formula_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(
        require_scope(Scope.PRODUCTS_DELETE)
    ),
):
    try:
        await FormulaService(db).delete_formula(formula_id, current_user.tenant_id)
    except NotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/apply", response_model=ApplyFormulaResponse, status_code=status.HTTP_201_CREATED)
async def apply_formula_to_reservation(
    payload: ApplyFormulaRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(
        require_scope(Scope.RESERVATIONS_WRITE)
    ),
):
    """Applique une formule à une réservation existante.

    Génère automatiquement des ReservationLine depuis formula × nb_guests.
    """
    try:
        result = await FormulaService(db).apply_to_reservation(
            formula_id=payload.formula_id,
            nb_guests=payload.nb_guests,
            reservation_id=payload.reservation_id,
            tenant_id=current_user.tenant_id,
        )
        return result
    except NotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
