"""Endpoints pour les événements avancés."""
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.evenements import (
    EvenementCreate, EvenementUpdate, EvenementList, EvenementResponse,
    EventIncidentCreate, EventIncidentResponse,
    IncidentActionCreate, IncidentActionResponse,
    FlagRiskRequest, CloseRequest, MarkReturnedRequest,
    RescheduleRequest, RescheduleResponse, EvenementReport,
)
import app.services.evenements as ev_svc


router = APIRouter(prefix="/evenements", tags=["Evenements"])

_404 = {"description": "Événement ou incident introuvable"}


# ---------------------------------------------------------------------------
# CRUD Événements
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedResponse[EvenementList])
async def list_evenements(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None, description="Filtre date min (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(default=None, description="Filtre date max (YYYY-MM-DD)"),
    search: Optional[str] = Query(default=None, description="Recherche par nom, reference ou lieu"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_READ)),
):
    items, total = await ev_svc.list_evenements(
        db, current_user.tenant_id,
        skip=pagination.skip, limit=pagination.limit, status=status,
        date_from=date_from, date_to=date_to, search=search,
    )
    return PaginatedResponse[EvenementList](
        items=items,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.post("", response_model=EvenementResponse, status_code=201)
async def create_evenement(
    data: EvenementCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_WRITE)),
):
    return await ev_svc.create_evenement(db, current_user.tenant_id, data)


@router.get("/{event_id}", response_model=EvenementResponse, responses={404: _404})
async def get_evenement(
    event_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_READ)),
):
    return await ev_svc.get_evenement(db, current_user.tenant_id, event_id)


@router.patch("/{event_id}", response_model=EvenementResponse, responses={404: _404})
async def update_evenement(
    event_id: int,
    data: EvenementUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_WRITE)),
):
    return await ev_svc.update_evenement(db, current_user.tenant_id, event_id, data)


# ---------------------------------------------------------------------------
# Transitions d'état
# ---------------------------------------------------------------------------

@router.post("/{event_id}/mark-returned", response_model=EvenementResponse)
async def mark_returned(
    event_id: int,
    data: MarkReturnedRequest = MarkReturnedRequest(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_WRITE)),
):
    return await ev_svc.mark_returned(db, current_user.tenant_id, event_id, notes=data.notes)


@router.post("/{event_id}/close", response_model=EvenementResponse)
async def close_evenement(
    event_id: int,
    data: CloseRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_WRITE)),
):
    return await ev_svc.close_evenement(db, current_user.tenant_id, event_id, notes=data.notes)


@router.post("/{event_id}/reschedule", response_model=RescheduleResponse)
async def reschedule_evenement(
    event_id: int,
    data: RescheduleRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_WRITE)),
):
    ev, conflicts = await ev_svc.reschedule_evenement(
        db, current_user.tenant_id, event_id, data.new_date, data.force
    )
    return RescheduleResponse(evenement=ev, conflicts=conflicts)


@router.get("/{event_id}/report", response_model=EvenementReport)
async def get_event_report(
    event_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_READ)),
):
    return await ev_svc.get_event_report(db, current_user.tenant_id, event_id)


@router.post("/{event_id}/flag-risk", response_model=EvenementResponse)
async def flag_risk(
    event_id: int,
    data: FlagRiskRequest = FlagRiskRequest(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_WRITE)),
):
    return await ev_svc.flag_risk(db, current_user.tenant_id, event_id)


@router.post("/{event_id}/start", response_model=EvenementResponse)
async def start_evenement(
    event_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_WRITE)),
):
    return await ev_svc.start_evenement(db, current_user.tenant_id, event_id)


@router.post("/{event_id}/cancel", response_model=EvenementResponse)
async def cancel_evenement(
    event_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_WRITE)),
):
    return await ev_svc.cancel_evenement(db, current_user.tenant_id, event_id)


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

@router.post("/{event_id}/incidents", response_model=EventIncidentResponse, status_code=201)
async def create_incident(
    event_id: int,
    data: EventIncidentCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_WRITE)),
):
    return await ev_svc.create_incident(db, current_user.tenant_id, event_id, current_user.id, data)


@router.get("/{event_id}/incidents", response_model=List[EventIncidentResponse])
async def list_incidents(
    event_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_READ)),
):
    return await ev_svc.list_incidents(db, current_user.tenant_id, event_id)


@router.patch("/{event_id}/incidents/{incident_id}/actions/{action_id}/close", response_model=IncidentActionResponse)
async def close_action(
    event_id: int,
    incident_id: int,
    action_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_WRITE)),
):
    return await ev_svc.close_action(db, current_user.tenant_id, event_id, incident_id, action_id)


@router.post("/{event_id}/incidents/{incident_id}/action-plan", response_model=List[IncidentActionResponse], status_code=201)
async def create_action_plan(
    event_id: int,
    incident_id: int,
    actions: List[IncidentActionCreate],
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.EVENEMENTS_WRITE)),
):
    return await ev_svc.create_action_plan(db, current_user.tenant_id, event_id, incident_id, actions)
