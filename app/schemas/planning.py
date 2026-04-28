"""Schémas Pydantic pour le module Planning."""
from datetime import date
from typing import Optional
from app.schemas.base import BaseSchema


# ---------------------------------------------------------------------------
# Schémas alignés sur les structures réelles retournées par les endpoints
# (correspondance exacte avec les types frontend)
# ---------------------------------------------------------------------------

class PlanningReservationOut(BaseSchema):
    id: int
    reference: str
    event_date: str
    return_date: Optional[str] = None
    status: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    event_type: Optional[str] = None
    event_name: Optional[str] = None
    guest_count: Optional[int] = None
    type: str = "reservation"
    # Logistique
    total_weight_grams: Optional[int] = None
    container_count: int = 0
    delivery_zone_name: Optional[str] = None
    delivery_fee_cents: int = 0
    delivery_method: Optional[str] = None


class PlanningMovementOut(BaseSchema):
    id: int
    scheduled_date: str
    movement_type: str
    reservation_id: Optional[int] = None
    type: str = "movement"


class PlanningDayOut(BaseSchema):
    date: str
    reservations: list[PlanningReservationOut]
    movements: list[PlanningMovementOut]
    total_reservations: int
    total_movements: int


class PlanningDaySlot(BaseSchema):
    reservations: list[PlanningReservationOut]
    movements: list[PlanningMovementOut]


class PlanningWeekOut(BaseSchema):
    week_start: str
    week_end: str
    days: dict[str, PlanningDaySlot]
    total_reservations: int
    total_movements: int


class PlanningMonthOut(BaseSchema):
    month: str
    start: str
    end: str
    reservations: list[PlanningReservationOut]
    movements: list[PlanningMovementOut]
    total_reservations: int
    total_movements: int


class PlanningReservationItem(BaseSchema):
    id: int
    reference: str
    event_date: date
    delivery_date: Optional[date] = None
    return_date: Optional[date] = None
    status: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None


class PlanningMovementItem(BaseSchema):
    id: int
    movement_type: str
    status: str
    reservation_id: Optional[int] = None
    scheduled_date: Optional[date] = None


class PlanningDayResponse(BaseSchema):
    date: date
    reservations: list[PlanningReservationItem]
    movements: list[PlanningMovementItem]
    total_reservations: int
    total_movements: int


class PlanningWeekDay(BaseSchema):
    date: date
    reservations: list[PlanningReservationItem]
    movements: list[PlanningMovementItem]


class PlanningWeekResponse(BaseSchema):
    week_start: date
    week_end: date
    days: list[PlanningWeekDay]


class PlanningMonthDay(BaseSchema):
    date: date
    reservation_count: int
    movement_count: int


class PlanningMonthResponse(BaseSchema):
    year: int
    month: int
    days: list[PlanningMonthDay]


class PlanningActiveReservation(BaseSchema):
    id: int
    reference: str
    event_date: date
    return_date: Optional[date] = None
    status: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None


class PlanningResourcesResponse(BaseSchema):
    date: str
    active_reservations: list[dict]
    total: int


class PlanningTodayReservation(BaseSchema):
    id: int
    reference: str
    event_date: str
    return_date: Optional[str] = None
    status: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    event_name: Optional[str] = None
    event_type: Optional[str] = None
    guest_count: Optional[int] = None
    # Logistique
    total_weight_grams: Optional[int] = None
    container_count: int = 0
    delivery_zone_name: Optional[str] = None
    delivery_fee_cents: int = 0
    delivery_method: Optional[str] = None


class PlanningTodayOut(BaseSchema):
    date: str
    departures: list[PlanningTodayReservation]
    returns_today: list[PlanningTodayReservation]
    active: list[PlanningTodayReservation]
    overdue: list[PlanningTodayReservation]
    total_departures: int
    total_returns: int
    total_active: int
    total_overdue: int


class PlanningTimelineMovement(BaseSchema):
    id: int
    scheduled_date: str
    movement_type: str
    status: str
    reservation_id: Optional[int] = None
    items_count: int = 0


class PlanningTimelineEvent(BaseSchema):
    reservation_id: int
    customer_name: Optional[str] = None
    event_date: str
    rental_start_date: Optional[str] = None
    rental_end_date: Optional[str] = None
    status: str
    departure: Optional[PlanningTimelineMovement] = None
    return_movement: Optional[PlanningTimelineMovement] = None


class PlanningTimelineOut(BaseSchema):
    start_date: str
    end_date: str
    events: list[PlanningTimelineEvent]
    reservations: list[PlanningReservationOut]
    total_departures: int
    total_returns: int
    total_reservations: int


class LoadingContainerItem(BaseSchema):
    """Article dans un contenant pour la vue chargement."""
    movement_item_id: int
    product_name: Optional[str] = None
    variant_label: Optional[str] = None
    image_url: Optional[str] = None
    quantity: int


class LoadingContainer(BaseSchema):
    """Contenant avec ses articles pour la vue chargement."""
    container_id: int
    container_name: str
    container_type: str
    serial_number: Optional[str] = None
    items: list[LoadingContainerItem] = []


class LoadingResponse(BaseSchema):
    """Vue chargement complète d'une réservation."""
    reservation_id: int
    reference: str
    customer_name: Optional[str] = None
    delivery_date: Optional[date] = None
    delivery_zone_name: Optional[str] = None
    delivery_method: Optional[str] = None
    total_weight_grams: Optional[int] = None
    containers: list[LoadingContainer] = []
    unassigned_items_count: int = 0


class PlanningAssignRequest(BaseSchema):
    reservation_id: int
    user_id: Optional[int] = None


class PlanningAssignResponse(BaseSchema):
    reservation_id: int
    assigned_user_id: Optional[int] = None
