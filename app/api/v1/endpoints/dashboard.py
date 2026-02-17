"""Endpoint dashboard — KPIs agrégés par tenant."""
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.reservation import Reservation
from app.models.invoice import Invoice
from app.models.inventory_movement import InventoryMovement
from app.models.product import Product
from app.schemas.dashboard import DashboardStats
from app.constants.business import (
    ReservationStatus,
    InvoiceStatus,
    MovementStatus,
    MovementType,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

LOW_STOCK_THRESHOLD = 5


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> DashboardStats:
    """Retourne les KPIs agrégés pour le tenant de l'utilisateur."""
    tid = current_user.tenant_id
    today = date.today()

    # ── Reservations ──────────────────────────────────────────────
    active_statuses = [ReservationStatus.CONFIRMED, ReservationStatus.DELIVERED]
    active_reservations = (
        db.query(func.count(Reservation.id))
        .filter(Reservation.tenant_id == tid, Reservation.status.in_(active_statuses))
        .scalar()
    ) or 0

    draft_reservations = (
        db.query(func.count(Reservation.id))
        .filter(Reservation.tenant_id == tid, Reservation.status == ReservationStatus.DRAFT)
        .scalar()
    ) or 0

    # CA du mois en cours (réservations confirmed+delivered+returned ce mois)
    revenue_statuses = [
        ReservationStatus.CONFIRMED,
        ReservationStatus.DELIVERED,
        ReservationStatus.RETURNED,
    ]
    monthly_revenue_cents = (
        db.query(func.coalesce(func.sum(Reservation.total_amount), 0))
        .filter(
            Reservation.tenant_id == tid,
            Reservation.status.in_(revenue_statuses),
            extract("year", Reservation.created_at) == today.year,
            extract("month", Reservation.created_at) == today.month,
        )
        .scalar()
    ) or 0

    # ── Factures ──────────────────────────────────────────────────
    overdue_invoices = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.tenant_id == tid, Invoice.status == InvoiceStatus.OVERDUE)
        .scalar()
    ) or 0

    overdue_amount_cents = (
        db.query(func.coalesce(func.sum(Invoice.total_amount), 0))
        .filter(Invoice.tenant_id == tid, Invoice.status == InvoiceStatus.OVERDUE)
        .scalar()
    ) or 0

    unpaid_invoices = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.tenant_id == tid, Invoice.status == InvoiceStatus.SENT)
        .scalar()
    ) or 0

    # ── Mouvements ────────────────────────────────────────────────
    late_movements = (
        db.query(func.count(InventoryMovement.id))
        .filter(InventoryMovement.tenant_id == tid, InventoryMovement.is_active == True, InventoryMovement.status == MovementStatus.LATE)
        .scalar()
    ) or 0

    scheduled_departures = (
        db.query(func.count(InventoryMovement.id))
        .filter(
            InventoryMovement.tenant_id == tid,
            InventoryMovement.is_active == True,
            InventoryMovement.status == MovementStatus.SCHEDULED,
            InventoryMovement.movement_type == MovementType.DEPARTURE,
        )
        .scalar()
    ) or 0

    scheduled_returns = (
        db.query(func.count(InventoryMovement.id))
        .filter(
            InventoryMovement.tenant_id == tid,
            InventoryMovement.is_active == True,
            InventoryMovement.status == MovementStatus.SCHEDULED,
            InventoryMovement.movement_type == MovementType.RETURN,
        )
        .scalar()
    ) or 0

    # ── Stock ─────────────────────────────────────────────────────
    low_stock_products = (
        db.query(func.count(Product.id))
        .filter(
            Product.tenant_id == tid,
            Product.is_active == True,
            Product.available_quantity < LOW_STOCK_THRESHOLD,
        )
        .scalar()
    ) or 0

    total_products = (
        db.query(func.count(Product.id))
        .filter(Product.tenant_id == tid, Product.is_active == True)
        .scalar()
    ) or 0

    return DashboardStats(
        active_reservations=active_reservations,
        draft_reservations=draft_reservations,
        monthly_revenue_cents=monthly_revenue_cents,
        overdue_invoices=overdue_invoices,
        overdue_amount_cents=overdue_amount_cents,
        unpaid_invoices=unpaid_invoices,
        late_movements=late_movements,
        scheduled_departures=scheduled_departures,
        scheduled_returns=scheduled_returns,
        low_stock_products=low_stock_products,
        total_products=total_products,
    )
