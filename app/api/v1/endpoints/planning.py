"""Endpoints planning — vue semaine, mois, ressources.

Agrège réservations + mouvements de stock sans nouvelle table.
"""
import logging
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants.errors import ErrorMessages
from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.exceptions import NotFound
from app.core.permissions import Scope
from app.models.container import ContainerAssignment
from app.models.customer import Customer
from app.models.delivery_zone import DeliveryZone
from app.models.inventory_movement import InventoryMovement, MovementItem
from app.models.reservation import Reservation
from app.models.tenant_membership import TenantMembership
from app.schemas.planning import (
    LoadingContainer,
    LoadingContainerItem,
    LoadingResponse,
    PlanningAssignRequest,
    PlanningAssignResponse,
    PlanningResourcesResponse,
    PlanningDayOut,
    PlanningWeekOut,
    PlanningMonthOut,
    PlanningTodayOut,
    PlanningTimelineOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planning", tags=["Planning"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _reservations_in_range(
    db: AsyncSession, tenant_id: int, date_from: date, date_to: date,
    zone_id: Optional[int] = None,
) -> list:
    from sqlalchemy import func as sa_func

    query = (
        select(Reservation, Customer, DeliveryZone.department_name.label("zone_name"))
        .outerjoin(Customer, Reservation.customer_id == Customer.id)
        .outerjoin(DeliveryZone, Reservation.delivery_zone_id == DeliveryZone.id)
        .where(
            Reservation.tenant_id == tenant_id,
            Reservation.event_date >= date_from,
            Reservation.event_date <= date_to,
        )
    )
    if zone_id is not None:
        query = query.where(Reservation.delivery_zone_id == zone_id)
    query = query.order_by(Reservation.event_date)

    rows = (await db.execute(query)).all()

    # Count containers per reservation (batch)
    res_ids = [row[0].id for row in rows]
    container_counts: dict[int, int] = {}
    if res_ids:
        from app.models.inventory_movement import InventoryMovement as IM
        count_q = (
            select(
                IM.reservation_id,
                sa_func.count(ContainerAssignment.id).label("cnt"),
            )
            .join(ContainerAssignment, ContainerAssignment.movement_id == IM.id)
            .where(
                IM.reservation_id.in_(res_ids),
                IM.tenant_id == tenant_id,
                ContainerAssignment.tenant_id == tenant_id,
            )
            .group_by(IM.reservation_id)
        )
        for rid, cnt in (await db.execute(count_q)).all():
            container_counts[rid] = cnt

    return [
        {
            "id": r.id,
            "reference": r.reference,
            "event_date": str(r.event_date),
            "return_date": str(r.return_date) if r.return_date else None,
            "status": r.status,
            "customer_id": r.customer_id,
            "customer_name": c.display_name if c else None,
            "event_type": getattr(r, "event_type", None),
            "event_name": getattr(r, "event_name", None),
            "guest_count": getattr(r, "guest_count", None),
            "type": "reservation",
            "total_weight_grams": getattr(r, "total_weight_grams", None),
            "container_count": container_counts.get(r.id, 0),
            "delivery_zone_name": zone_name,
            "delivery_fee_cents": getattr(r, "delivery_fee_cents", 0),
            "delivery_method": getattr(r, "delivery_method", None),
        }
        for r, c, zone_name in rows
    ]


async def _movements_in_range(
    db: AsyncSession, tenant_id: int, date_from: date, date_to: date
) -> list:
    rows = (await db.execute(
        select(InventoryMovement).where(
            InventoryMovement.tenant_id == tenant_id,
            InventoryMovement.scheduled_date >= date_from,
            InventoryMovement.scheduled_date <= date_to,
        ).order_by(InventoryMovement.scheduled_date)
    )).scalars().all()
    return [
        {
            "id": m.id,
            "scheduled_date": str(m.scheduled_date),
            "movement_type": m.movement_type,
            "reservation_id": m.reservation_id,
            "type": "movement",
        }
        for m in rows
    ]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/day", response_model=PlanningDayOut)
async def get_planning_day(
    date_param: Optional[date] = Query(None, alias="date"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> PlanningDayOut:
    """Vue jour : réservations + mouvements pour un jour précis."""
    ref_date = date_param or date.today()

    reservations = await _reservations_in_range(db, current_user.tenant_id, ref_date, ref_date)
    movements = await _movements_in_range(db, current_user.tenant_id, ref_date, ref_date)

    return {
        "date": str(ref_date),
        "reservations": reservations,
        "movements": movements,
        "total_reservations": len(reservations),
        "total_movements": len(movements),
    }


@router.get("/week", response_model=PlanningWeekOut)
async def get_planning_week(
    date_param: Optional[date] = Query(None, alias="date"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> PlanningWeekOut:
    """Vue semaine : réservations + mouvements sur 7 jours à partir de la date donnée."""
    ref_date = date_param or date.today()
    # Commencer au lundi de la semaine
    start = ref_date - timedelta(days=ref_date.weekday())
    end = start + timedelta(days=6)

    reservations = await _reservations_in_range(db, current_user.tenant_id, start, end)
    movements = await _movements_in_range(db, current_user.tenant_id, start, end)

    # Grouper par jour
    days = {}
    for offset in range(7):
        d = str(start + timedelta(days=offset))
        days[d] = {"reservations": [], "movements": []}

    for r in reservations:
        d = r["event_date"]
        if d in days:
            days[d]["reservations"].append(r)

    for m in movements:
        d = m["scheduled_date"]
        if d in days:
            days[d]["movements"].append(m)

    return {
        "week_start": str(start),
        "week_end": str(end),
        "days": days,
        "total_reservations": len(reservations),
        "total_movements": len(movements),
    }


@router.get("/month", response_model=PlanningMonthOut)
async def get_planning_month(
    date_param: Optional[date] = Query(None, alias="date"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> PlanningMonthOut:
    """Vue mois : réservations + mouvements sur le mois calendaire."""
    ref_date = date_param or date.today()
    start = date(ref_date.year, ref_date.month, 1)
    # Dernier jour du mois
    if ref_date.month == 12:
        end = date(ref_date.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(ref_date.year, ref_date.month + 1, 1) - timedelta(days=1)

    reservations = await _reservations_in_range(db, current_user.tenant_id, start, end)
    movements = await _movements_in_range(db, current_user.tenant_id, start, end)

    return {
        "month": f"{ref_date.year}-{ref_date.month:02d}",
        "start": str(start),
        "end": str(end),
        "reservations": reservations,
        "movements": movements,
        "total_reservations": len(reservations),
        "total_movements": len(movements),
    }


@router.get("/resources", response_model=PlanningResourcesResponse)
async def get_planning_resources(
    date_param: Optional[date] = Query(None, alias="date"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> PlanningResourcesResponse:
    """Vue ressources : réservations actives à la date donnée (vue 'qui est dehors')."""
    ref_date = date_param or date.today()

    # Réservations dont event_date <= ref_date <= return_date (ou event_date == ref_date)
    rows = (await db.execute(
        select(Reservation, Customer)
        .outerjoin(Customer, Reservation.customer_id == Customer.id)
        .where(
            Reservation.tenant_id == current_user.tenant_id,
            Reservation.event_date <= ref_date,
            Reservation.status.in_(["confirmed", "confirmed_risk", "pre_check", "delivered", "extended"]),
        ).order_by(Reservation.event_date)
    )).all()

    active = []
    for r, c in rows:
        return_date = getattr(r, "return_date", None)
        if return_date is None or return_date >= ref_date:
            active.append({
                "id": r.id,
                "reference": r.reference,
                "event_date": str(r.event_date),
                "return_date": str(return_date) if return_date else None,
                "status": r.status,
                "customer_id": r.customer_id,
                "customer_name": c.display_name if c else None,
            })

    return {
        "date": str(ref_date),
        "active_reservations": active,
        "total": len(active),
    }


# ---------------------------------------------------------------------------
# Vue opérationnelle Jour J
# ---------------------------------------------------------------------------

@router.get("/today", response_model=PlanningTodayOut)
async def get_planning_today(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> PlanningTodayOut:
    """Vue opérationnelle Jour J : départs, retours attendus, actifs, retards."""
    today = date.today()
    tid = current_user.tenant_id

    ACTIVE_STATUSES = ["confirmed", "delivered", "in_progress"]

    rows = (await db.execute(
        select(Reservation, Customer)
        .outerjoin(Customer, Reservation.customer_id == Customer.id)
        .where(
            Reservation.tenant_id == tid,
            Reservation.status.in_(ACTIVE_STATUSES),
        )
    )).all()

    def _to_dict(r: Reservation, c) -> dict:
        return {
            "id": r.id,
            "reference": r.reference,
            "event_date": str(r.event_date),
            "return_date": str(r.return_date) if r.return_date else None,
            "status": r.status,
            "customer_id": r.customer_id,
            "customer_name": c.display_name if c else None,
            "event_name": getattr(r, "event_name", None),
            "event_type": getattr(r, "event_type", None),
            "guest_count": getattr(r, "guest_count", None),
            "delivery_method": getattr(r, "delivery_method", None),
            "delivery_fee_cents": getattr(r, "delivery_fee_cents", 0),
        }

    departures, returns_today, active, overdue = [], [], [], []

    for r, c in rows:
        event_date = r.event_date
        return_date = getattr(r, "return_date", None)

        if return_date and return_date < today:
            overdue.append(_to_dict(r, c))
        elif event_date == today:
            departures.append(_to_dict(r, c))
            if return_date and return_date == today:
                returns_today.append(_to_dict(r, c))
        elif return_date and return_date == today:
            returns_today.append(_to_dict(r, c))
        elif event_date < today and (return_date is None or return_date > today):
            active.append(_to_dict(r, c))

    return {
        "date": str(today),
        "departures": departures,
        "returns_today": returns_today,
        "active": active,
        "overdue": overdue,
        "total_departures": len(departures),
        "total_returns": len(returns_today),
        "total_active": len(active),
        "total_overdue": len(overdue),
    }


# ---------------------------------------------------------------------------
# Timeline — vue calendrier unifiée (remplace /inventory-movements/agenda)
# ---------------------------------------------------------------------------

@router.get("/timeline", response_model=PlanningTimelineOut)
async def get_planning_timeline(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> PlanningTimelineOut:
    """Vue calendrier unifiée : réservations + mouvements sur une plage."""
    ref_start = start_date or date.today()
    ref_end = end_date or (ref_start + timedelta(days=30))
    tid = current_user.tenant_id

    # Réservations avec mouvements eager-loaded
    rows = (await db.execute(
        select(Reservation)
        .options(
            selectinload(Reservation.movements)
            .selectinload(InventoryMovement.items),
            selectinload(Reservation.customer),
        )
        .where(
            Reservation.tenant_id == tid,
            or_(
                (Reservation.delivery_date >= ref_start)
                & (Reservation.delivery_date <= ref_end),
                (Reservation.return_date >= ref_start)
                & (Reservation.return_date <= ref_end),
                (Reservation.event_date >= ref_start)
                & (Reservation.event_date <= ref_end),
            ),
        )
    )).scalars().all()

    events = []
    total_dep = 0
    total_ret = 0
    reservations_out = []

    for r in rows:
        customer_name = None
        if r.customer:
            customer_name = (
                f"{r.customer.first_name} {r.customer.last_name}".strip()
            )

        reservations_out.append({
            "id": r.id,
            "reference": r.reference,
            "event_date": str(r.event_date),
            "return_date": str(r.return_date) if r.return_date else None,
            "status": r.status,
            "customer_id": r.customer_id,
            "customer_name": customer_name,
            "event_type": getattr(r, "event_type", None),
            "event_name": getattr(r, "event_name", None),
            "guest_count": getattr(r, "guest_count", None),
            "type": "reservation",
        })

        dep = None
        ret = None
        for m in r.movements:
            if not m.is_active:
                continue
            sd = m.scheduled_date
            if hasattr(sd, "date"):
                sd = sd.date()
            if sd < ref_start or sd > ref_end:
                continue
            entry = {
                "id": m.id,
                "scheduled_date": m.scheduled_date.isoformat(),
                "movement_type": m.movement_type,
                "status": m.status,
                "reservation_id": m.reservation_id,
                "items_count": len(m.items) if m.items else 0,
            }
            if m.movement_type == "departure":
                dep = entry
                total_dep += 1
            elif m.movement_type == "return":
                ret = entry
                total_ret += 1

        events.append({
            "reservation_id": r.id,
            "customer_name": customer_name,
            "event_date": r.event_date.isoformat(),
            "rental_start_date": (
                r.delivery_date.isoformat() if r.delivery_date else None
            ),
            "rental_end_date": (
                r.return_date.isoformat() if r.return_date else None
            ),
            "status": r.status,
            "departure": dep,
            "return_movement": ret,
        })

    return {
        "start_date": ref_start.isoformat(),
        "end_date": ref_end.isoformat(),
        "events": events,
        "reservations": reservations_out,
        "total_departures": total_dep,
        "total_returns": total_ret,
        "total_reservations": len(rows),
    }


# ---------------------------------------------------------------------------
# Affectation équipe
# ---------------------------------------------------------------------------

@router.post("/assign", response_model=PlanningAssignResponse)
async def assign_user_to_reservation(
    data: PlanningAssignRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> PlanningAssignResponse:
    """Affecte (ou désaffecte) un utilisateur à une réservation."""
    res = (await db.execute(
        select(Reservation).where(
            Reservation.id == data.reservation_id,
            Reservation.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not res:
        raise NotFound(ErrorMessages.RESERVATION_NOT_FOUND)

    if data.user_id is not None:
        membership = (await db.execute(
            select(TenantMembership).where(
                TenantMembership.account_id == data.user_id,
                TenantMembership.tenant_id == current_user.tenant_id,
                TenantMembership.status == "active",
            )
        )).scalar_one_or_none()
        if not membership:
            raise NotFound(ErrorMessages.USER_NOT_FOUND)

    res.assigned_user_id = data.user_id
    await db.commit()

    return PlanningAssignResponse(
        reservation_id=res.id,
        assigned_user_id=res.assigned_user_id,
    )


# ---------------------------------------------------------------------------
# Loading view — vue chargement par réservation
# ---------------------------------------------------------------------------


@router.get("/loading/{reservation_id}", response_model=LoadingResponse)
async def get_loading_view(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> LoadingResponse:
    """Vue chargement : contenants + articles par contenant pour une réservation."""
    from sqlalchemy.orm import selectinload as sload
    from app.models.container import ContainerAssignment, ContainerItem

    res = (await db.execute(
        select(Reservation)
        .outerjoin(Customer, Reservation.customer_id == Customer.id)
        .outerjoin(DeliveryZone, Reservation.delivery_zone_id == DeliveryZone.id)
        .where(
            Reservation.id == reservation_id,
            Reservation.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()

    if not res:
        raise NotFound(ErrorMessages.RESERVATION_NOT_FOUND)

    customer = (await db.execute(
        select(Customer).where(Customer.id == res.customer_id)
    )).scalar_one_or_none()

    zone = None
    if res.delivery_zone_id:
        zone = (await db.execute(
            select(DeliveryZone).where(DeliveryZone.id == res.delivery_zone_id)
        )).scalar_one_or_none()

    # Get movements for this reservation
    movements = (await db.execute(
        select(InventoryMovement).where(
            InventoryMovement.reservation_id == reservation_id,
            InventoryMovement.tenant_id == current_user.tenant_id,
        )
    )).scalars().all()

    movement_ids = [m.id for m in movements]

    containers_out = []
    total_assigned = 0
    if movement_ids:
        assignments = (await db.execute(
            select(ContainerAssignment)
            .options(
                sload(ContainerAssignment.container),
                sload(ContainerAssignment.items),
            )
            .where(
                ContainerAssignment.movement_id.in_(movement_ids),
                ContainerAssignment.tenant_id == current_user.tenant_id,
            )
        )).scalars().unique().all()

        movement_item_ids = [
            item.movement_item_id
            for assignment in assignments
            for item in assignment.items
        ]
        movement_items_by_id: dict[int, MovementItem] = {}
        if movement_item_ids:
            movement_items = (await db.execute(
                select(MovementItem)
                .options(
                    sload(MovementItem.product),
                    sload(MovementItem.variant),
                )
                .where(
                    MovementItem.id.in_(movement_item_ids),
                    MovementItem.tenant_id == current_user.tenant_id,
                )
            )).scalars().all()
            movement_items_by_id = {item.id: item for item in movement_items}

        for a in assignments:
            items_out = [
                LoadingContainerItem(
                    movement_item_id=item.movement_item_id,
                    product_name=(
                        movement_items_by_id[item.movement_item_id].product.name
                        if movement_items_by_id.get(item.movement_item_id)
                        and movement_items_by_id[item.movement_item_id].product
                        else None
                    ),
                    variant_label=(
                        movement_items_by_id[item.movement_item_id].variant.label
                        if movement_items_by_id.get(item.movement_item_id)
                        and movement_items_by_id[item.movement_item_id].variant
                        else None
                    ),
                    image_url=(
                        movement_items_by_id[item.movement_item_id].variant.image_url
                        if movement_items_by_id.get(item.movement_item_id)
                        and movement_items_by_id[item.movement_item_id].variant
                        and movement_items_by_id[item.movement_item_id].variant.image_url
                        else (
                            movement_items_by_id[item.movement_item_id].product.image_url
                            if movement_items_by_id.get(item.movement_item_id)
                            and movement_items_by_id[item.movement_item_id].product
                            else None
                        )
                    ),
                    quantity=item.quantity,
                )
                for item in a.items
            ]
            total_assigned += len(items_out)
            containers_out.append(LoadingContainer(
                container_id=a.container_id,
                container_name=a.container.name if a.container else "?",
                container_type=a.container.container_type if a.container else "?",
                serial_number=a.container.serial_number if a.container else None,
                items=items_out,
            ))

    # Count total movement items for unassigned calc
    total_items_count = 0
    if movement_ids:
        total_items_result = await db.execute(
            select(MovementItem.id).where(
                MovementItem.movement_id.in_(movement_ids),
                MovementItem.tenant_id == current_user.tenant_id,
            )
        )
        total_items_count = len(total_items_result.all())

    return LoadingResponse(
        reservation_id=res.id,
        reference=res.reference,
        customer_name=customer.display_name if customer else None,
        delivery_date=res.delivery_date,
        delivery_zone_name=zone.department_name if zone else None,
        delivery_method=res.delivery_method,
        total_weight_grams=None,  # Calculated on demand if needed
        containers=containers_out,
        unassigned_items_count=max(0, total_items_count - total_assigned),
    )
