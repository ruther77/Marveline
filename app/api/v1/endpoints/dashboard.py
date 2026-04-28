"""Endpoint dashboard — KPIs agrégés par tenant."""
import csv
import io
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import joinedload
from sqlalchemy import func, and_, extract, or_, cast, Date as SADate, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope

# Toutes les routes dashboard requièrent REPORTS_READ
ReportsReader = UserCompat
from app.models.reservation import Reservation, ReservationLine
from app.models.invoice import Invoice
from app.models.inventory_movement import InventoryMovement
from app.models.product import Product
from app.models.customer import Customer
from app.schemas.dashboard import (
    DashboardStats, FinancesStats, FinancesMonthly, FinancesTotals,
    UrgentAlertItem, TodayCard, TodayPlanning, ActivityItem, ActivityFeed,
    AnalyticsKpis, TopProductItem, SeasonalityMonthly,
)
from app.constants.business import (
    ReservationStatus,
    InvoiceStatus,
    MovementStatus,
    MovementType,
    LOW_STOCK_THRESHOLD,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: ReportsReader = Depends(require_scope(Scope.REPORTS_READ)),
    db: AsyncSession = Depends(get_async_db),
) -> DashboardStats:
    """Retourne les KPIs agrégés pour le tenant de l'utilisateur."""
    tid = current_user.tenant_id
    today = date.today()

    # ── Reservations ──────────────────────────────────────────────
    active_statuses = [ReservationStatus.CONFIRMED, ReservationStatus.DELIVERED]
    active_reservations = (await db.scalar(
        select(func.count(Reservation.id)).where(
            Reservation.tenant_id == tid, Reservation.status.in_(active_statuses)
        )
    )) or 0

    draft_reservations = (await db.scalar(
        select(func.count(Reservation.id)).where(
            Reservation.tenant_id == tid, Reservation.status == ReservationStatus.DRAFT
        )
    )) or 0

    # CA du mois en cours (réservations confirmed+delivered+returned ce mois)
    revenue_statuses = [
        ReservationStatus.CONFIRMED,
        ReservationStatus.DELIVERED,
        ReservationStatus.RETURNED,
    ]
    monthly_revenue_cents = (await db.scalar(
        select(func.coalesce(func.sum(Reservation.total_amount_cents), 0)).where(
            Reservation.tenant_id == tid,
            Reservation.status.in_(revenue_statuses),
            extract("year", Reservation.created_at) == today.year,
            extract("month", Reservation.created_at) == today.month,
        )
    )) or 0

    # ── Factures ──────────────────────────────────────────────────
    overdue_invoices = (await db.scalar(
        select(func.count(Invoice.id)).where(
            Invoice.tenant_id == tid, Invoice.status == InvoiceStatus.OVERDUE
        )
    )) or 0

    overdue_amount_cents = (await db.scalar(
        select(func.coalesce(func.sum(Invoice.total_amount_cents), 0)).where(
            Invoice.tenant_id == tid, Invoice.status == InvoiceStatus.OVERDUE
        )
    )) or 0

    unpaid_invoices = (await db.scalar(
        select(func.count(Invoice.id)).where(
            Invoice.tenant_id == tid, Invoice.status == InvoiceStatus.SENT
        )
    )) or 0

    # ── Mouvements ────────────────────────────────────────────────
    late_movements = (await db.scalar(
        select(func.count(InventoryMovement.id)).where(
            InventoryMovement.tenant_id == tid,
            InventoryMovement.is_active == True,
            InventoryMovement.status == MovementStatus.LATE,
        )
    )) or 0

    scheduled_departures = (await db.scalar(
        select(func.count(InventoryMovement.id)).where(
            InventoryMovement.tenant_id == tid,
            InventoryMovement.is_active == True,
            InventoryMovement.status == MovementStatus.SCHEDULED,
            InventoryMovement.movement_type == MovementType.DEPARTURE,
        )
    )) or 0

    scheduled_returns = (await db.scalar(
        select(func.count(InventoryMovement.id)).where(
            InventoryMovement.tenant_id == tid,
            InventoryMovement.is_active == True,
            InventoryMovement.status == MovementStatus.SCHEDULED,
            InventoryMovement.movement_type == MovementType.RETURN,
        )
    )) or 0

    # ── Stock ─────────────────────────────────────────────────────
    low_stock_products = (await db.scalar(
        select(func.count(Product.id)).where(
            Product.tenant_id == tid,
            Product.is_active == True,
            Product.available_quantity < LOW_STOCK_THRESHOLD,
        )
    )) or 0

    total_products = (await db.scalar(
        select(func.count(Product.id)).where(
            Product.tenant_id == tid, Product.is_active == True
        )
    )) or 0

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


@router.get("/finances", response_model=FinancesStats)
async def get_finances_stats(
    current_user: ReportsReader = Depends(require_scope(Scope.REPORTS_READ)),
    db: AsyncSession = Depends(get_async_db),
    year: int = Query(default=None, description="Année à analyser (défaut : année courante)"),
) -> FinancesStats:
    """Statistiques financières annuelles par mois pour le tenant."""
    tid = current_user.tenant_id
    if year is None:
        year = date.today().year

    # ── Revenue mensuel (paid_amount_cents de toutes factures non-annulées) ──
    effective_date = func.coalesce(Invoice.payment_date, Invoice.issue_date)
    paid_rows = (await db.execute(
        select(
            extract("month", effective_date).label("month"),
            func.coalesce(func.sum(Invoice.paid_amount_cents), 0).label("revenue_cents"),
            func.count(Invoice.id).filter(
                Invoice.status == InvoiceStatus.PAID,
            ).label("invoices_paid"),
        )
        .where(
            Invoice.tenant_id == tid,
            Invoice.status != InvoiceStatus.CANCELLED,
            Invoice.paid_amount_cents > 0,
            extract("year", effective_date) == year,
        )
        .group_by(extract("month", effective_date))
    )).all()
    paid_by_month = {int(row.month): row for row in paid_rows}

    # ── Factures passées en retard par mois (due_date dans l'année) ──
    overdue_rows = (await db.execute(
        select(
            extract("month", Invoice.due_date).label("month"),
            func.count(Invoice.id).label("invoices_overdue"),
        )
        .where(
            Invoice.tenant_id == tid,
            Invoice.status == InvoiceStatus.OVERDUE,
            extract("year", Invoice.due_date) == year,
        )
        .group_by(extract("month", Invoice.due_date))
    )).all()
    overdue_by_month = {int(row.month): int(row.invoices_overdue) for row in overdue_rows}

    monthly = [
        FinancesMonthly(
            month=m,
            revenue_cents=int(paid_by_month[m].revenue_cents) if m in paid_by_month else 0,
            invoices_paid=int(paid_by_month[m].invoices_paid) if m in paid_by_month else 0,
            invoices_overdue=overdue_by_month.get(m, 0),
        )
        for m in range(1, 13)
    ]

    # ── Totaux ────────────────────────────────────────────────────
    revenue_ytd_cents = (await db.scalar(
        select(func.coalesce(func.sum(Invoice.paid_amount_cents), 0)).where(
            Invoice.tenant_id == tid,
            Invoice.status != InvoiceStatus.CANCELLED,
            Invoice.paid_amount_cents > 0,
            extract("year", func.coalesce(Invoice.payment_date, Invoice.issue_date)) == year,
        )
    )) or 0

    overdue_amount_cents = (await db.scalar(
        select(func.coalesce(func.sum(Invoice.total_amount_cents), 0)).where(
            Invoice.tenant_id == tid, Invoice.status == InvoiceStatus.OVERDUE
        )
    )) or 0

    active_statuses = [ReservationStatus.CONFIRMED, ReservationStatus.DELIVERED]
    active_reservations = (await db.scalar(
        select(func.count(Reservation.id)).where(
            Reservation.tenant_id == tid, Reservation.status.in_(active_statuses)
        )
    )) or 0

    low_stock_products = (await db.scalar(
        select(func.count(Product.id)).where(
            Product.tenant_id == tid,
            Product.is_active == True,
            Product.available_quantity < LOW_STOCK_THRESHOLD,
        )
    )) or 0

    return FinancesStats(
        year=year,
        monthly=monthly,
        totals=FinancesTotals(
            revenue_ytd_cents=int(revenue_ytd_cents),
            overdue_amount_cents=int(overdue_amount_cents),
            active_reservations=active_reservations,
            low_stock_products=low_stock_products,
        ),
    )


@router.get("/urgent-alert", response_model=UrgentAlertItem | None)
async def get_urgent_alert(
    current_user: ReportsReader = Depends(require_scope(Scope.REPORTS_READ)),
    db: AsyncSession = Depends(get_async_db),
) -> UrgentAlertItem | None:
    """Retourne la réservation retournée la plus urgente à contrôler, ou null."""
    tid = current_user.tenant_id
    resa = (await db.execute(
        select(Reservation)
        .options(joinedload(Reservation.customer))
        .where(
            Reservation.tenant_id == tid,
            Reservation.status.in_([
                ReservationStatus.RETURNED,
                ReservationStatus.RETURNED_DISPUTE,
            ]),
        )
        .order_by(Reservation.return_date.asc())
        .limit(1)
    )).unique().scalars().first()
    if not resa:
        return None
    customer_name = resa.customer.display_name if resa.customer else "Client inconnu"
    return UrgentAlertItem(
        reservation_id=resa.id,
        reference=resa.reference,
        customer_name=customer_name,
        return_date=resa.return_date,
    )


@router.get("/today", response_model=TodayPlanning)
async def get_today_planning(
    current_user: ReportsReader = Depends(require_scope(Scope.REPORTS_READ)),
    db: AsyncSession = Depends(get_async_db),
) -> TodayPlanning:
    """Départs et retours programmés aujourd'hui."""
    tid = current_user.tenant_id
    today = date.today()

    movements = (await db.execute(
        select(InventoryMovement)
        .options(joinedload(InventoryMovement.reservation).joinedload(Reservation.customer))
        .where(
            InventoryMovement.tenant_id == tid,
            InventoryMovement.is_active == True,
            InventoryMovement.status.in_([MovementStatus.SCHEDULED, MovementStatus.IN_TRANSIT]),
            cast(InventoryMovement.scheduled_date, SADate) == today,
        )
        .order_by(InventoryMovement.scheduled_date.asc())
    )).unique().scalars().all()

    def _to_card(mv: InventoryMovement, kind: str) -> TodayCard:
        resa = mv.reservation
        customer_name = ""
        deposit_paid = False
        if resa and resa.customer:
            customer_name = resa.customer.display_name
        if resa:
            deposit_paid = resa.deposit_paid
        items_count = len(mv.items) if hasattr(mv, "items") and mv.items else 0
        hour = None
        if mv.scheduled_date:
            try:
                dt = mv.scheduled_date
                if hasattr(dt, "strftime"):
                    hour = dt.strftime("%H:%M")
            except Exception:
                pass
        reference = resa.reference if resa else f"MVT-{mv.id}"
        return TodayCard(
            reservation_id=resa.id if resa else mv.id,
            reference=reference,
            customer_name=customer_name,
            hour=hour,
            articles_count=items_count,
            deposit_paid=deposit_paid,
            kind=kind,
        )

    departures = [
        _to_card(mv, "departure")
        for mv in movements
        if mv.movement_type == MovementType.DEPARTURE
    ]
    returns = [
        _to_card(mv, "return")
        for mv in movements
        if mv.movement_type == MovementType.RETURN
    ]
    return TodayPlanning(departures=departures, returns=returns)


@router.get("/activity", response_model=ActivityFeed)
async def get_activity_feed(
    current_user: ReportsReader = Depends(require_scope(Scope.REPORTS_READ)),
    db: AsyncSession = Depends(get_async_db),
) -> ActivityFeed:
    """Feed des 5 dernières activités cross-domaines du tenant."""
    tid = current_user.tenant_id
    items: list[ActivityItem] = []

    # Retours récents (5 derniers)
    returned_resas = (await db.execute(
        select(Reservation)
        .options(joinedload(Reservation.customer))
        .where(
            Reservation.tenant_id == tid,
            Reservation.status.in_([
                ReservationStatus.RETURNED,
                ReservationStatus.RETURNED_DISPUTE,
            ]),
        )
        .order_by(Reservation.updated_at.desc())
        .limit(3)
    )).unique().scalars().all()
    for r in returned_resas:
        customer = r.customer.display_name if r.customer else ""
        items.append(ActivityItem(
            kind="return_checked",
            label=f"Retour — {r.reference}",
            sub_label=customer,
            link=f"/reservations/{r.id}",
            created_at=r.updated_at.isoformat() if r.updated_at else "",
        ))

    # Factures payées récemment
    paid_invoices = (await db.execute(
        select(Invoice)
        .where(Invoice.tenant_id == tid, Invoice.status == InvoiceStatus.PAID)
        .order_by(Invoice.updated_at.desc())
        .limit(3)
    )).scalars().all()
    for inv in paid_invoices:
        amount_str = f"{inv.total_amount_cents / 100:.2f} €" if inv.total_amount_cents else ""
        items.append(ActivityItem(
            kind="invoice_paid",
            label=f"Facture payée — {inv.invoice_number}",
            sub_label=amount_str,
            link=f"/finance/invoices/{inv.id}",
            created_at=inv.updated_at.isoformat() if inv.updated_at else "",
        ))

    # Stock faible
    low_stock = (await db.execute(
        select(Product)
        .where(Product.tenant_id == tid, Product.is_active == True, Product.available_quantity < LOW_STOCK_THRESHOLD)  # noqa: E712
        .order_by(Product.updated_at.desc())
        .limit(2)
    )).scalars().all()
    for p in low_stock:
        items.append(ActivityItem(
            kind="low_stock",
            label=f"Stock faible — {p.name}",
            sub_label=f"{p.available_quantity} disponible(s)",
            link="/stock/items",
            created_at=p.updated_at.isoformat() if p.updated_at else "",
        ))

    # Trier par date desc, garder les 5 plus récents
    def _ts(it: ActivityItem) -> str:
        return it.created_at or ""

    items.sort(key=_ts, reverse=True)
    return ActivityFeed(items=items[:5])


@router.get("/analytics", response_model=AnalyticsKpis)
async def get_analytics_kpis(
    current_user: ReportsReader = Depends(require_scope(Scope.REPORTS_READ)),
    db: AsyncSession = Depends(get_async_db),
    period_days: int = Query(default=365, ge=30, le=1095, description="Période en jours (30-1095)"),
) -> AnalyticsKpis:
    """KPIs analytiques : panier moyen, taux utilisation, top produits, saisonnalité."""
    tid = current_user.tenant_id
    today = date.today()
    from datetime import timedelta
    period_start = today - timedelta(days=period_days)

    # ── Panier moyen ───────────────────────────────────────────────
    revenue_statuses = [
        ReservationStatus.CONFIRMED,
        ReservationStatus.DELIVERED,
        ReservationStatus.RETURNED,
        ReservationStatus.COMPLETED,
    ]
    basket_row = (await db.execute(
        select(
            func.coalesce(func.avg(Reservation.total_amount_cents), 0).label("avg_cents"),
            func.count(Reservation.id).label("count"),
            func.coalesce(func.sum(Reservation.total_amount_cents), 0).label("total_cents"),
        ).where(
            Reservation.tenant_id == tid,
            Reservation.status.in_(revenue_statuses),
            Reservation.created_at >= period_start,
        )
    )).one()
    avg_basket_cents = int(basket_row.avg_cents)
    total_reservations = int(basket_row.count)
    total_revenue_cents = int(basket_row.total_cents)

    # ── Taux d'utilisation (snapshot serveur) ──────────────────────
    stock_row = (await db.execute(
        select(
            func.coalesce(func.sum(Product.stock_quantity), 0).label("total"),
            func.coalesce(func.sum(Product.available_quantity), 0).label("available"),
        ).where(
            Product.tenant_id == tid,
            Product.is_active == True,  # noqa: E712
        )
    )).one()
    total_stock = int(stock_row.total)
    total_available = int(stock_row.available)
    total_rented = total_stock - total_available
    utilization_rate = round((total_rented / total_stock * 100) if total_stock > 0 else 0, 1)

    # ── Top 10 produits par fréquence de location ──────────────────
    top_rows = (await db.execute(
        select(
            ReservationLine.product_id,
            Product.name.label("product_name"),
            Product.category.label("category"),
            func.count(ReservationLine.id).label("rental_count"),
            func.sum(ReservationLine.quantity).label("total_quantity"),
            func.coalesce(func.sum(ReservationLine.subtotal_cents), 0).label("revenue_cents"),
        )
        .join(Reservation, Reservation.id == ReservationLine.reservation_id)
        .join(Product, Product.id == ReservationLine.product_id)
        .where(
            ReservationLine.tenant_id == tid,
            Reservation.status.in_(revenue_statuses),
            Reservation.created_at >= period_start,
            ReservationLine.product_id.isnot(None),
        )
        .group_by(ReservationLine.product_id, Product.name, Product.category)
        .order_by(func.count(ReservationLine.id).desc())
        .limit(10)
    )).all()
    top_products = [
        TopProductItem(
            product_id=row.product_id,
            product_name=row.product_name,
            category=row.category,
            rental_count=int(row.rental_count),
            total_quantity=int(row.total_quantity),
            revenue_cents=int(row.revenue_cents),
        )
        for row in top_rows
    ]

    # ── Saisonnalité (N, N-1, N-2) ────────────────────────────────
    current_year = today.year
    years = [current_year - 2, current_year - 1, current_year]
    season_rows = (await db.execute(
        select(
            extract("year", Reservation.created_at).label("year"),
            extract("month", Reservation.created_at).label("month"),
            func.coalesce(func.sum(Reservation.total_amount_cents), 0).label("revenue_cents"),
            func.count(Reservation.id).label("reservation_count"),
        ).where(
            Reservation.tenant_id == tid,
            Reservation.status.in_(revenue_statuses),
            extract("year", Reservation.created_at).in_(years),
        )
        .group_by(
            extract("year", Reservation.created_at),
            extract("month", Reservation.created_at),
        )
        .order_by(
            extract("year", Reservation.created_at),
            extract("month", Reservation.created_at),
        )
    )).all()
    monthly_revenue = [
        SeasonalityMonthly(
            year=int(row.year),
            month=int(row.month),
            revenue_cents=int(row.revenue_cents),
            reservation_count=int(row.reservation_count),
        )
        for row in season_rows
    ]

    return AnalyticsKpis(
        avg_basket_cents=avg_basket_cents,
        total_reservations=total_reservations,
        total_revenue_cents=total_revenue_cents,
        utilization_rate=utilization_rate,
        total_stock=total_stock,
        total_rented=total_rented,
        top_products=top_products,
        monthly_revenue=monthly_revenue,
        seasonality_years=years,
    )


_MONTH_NAMES = [
    "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]


@router.get("/finances/export")
async def export_finances_csv(
    current_user: ReportsReader = Depends(require_scope(Scope.REPORTS_READ)),
    db: AsyncSession = Depends(get_async_db),
    year: int = Query(default=None, description="Année à exporter (défaut : année courante)"),
) -> StreamingResponse:
    """Exporte le rapport financier mensuel en CSV (téléchargement direct)."""
    if year is None:
        year = date.today().year

    tid = current_user.tenant_id

    paid_rows = (await db.execute(
        select(
            extract("month", Invoice.payment_date).label("month"),
            func.coalesce(func.sum(Invoice.paid_amount_cents), 0).label("revenue_cents"),
            func.count(Invoice.id).label("invoices_paid"),
        )
        .where(
            Invoice.tenant_id == tid,
            Invoice.status == InvoiceStatus.PAID,
            extract("year", Invoice.payment_date) == year,
        )
        .group_by(extract("month", Invoice.payment_date))
    )).all()
    paid_by_month = {int(row.month): row for row in paid_rows}

    overdue_rows = (await db.execute(
        select(
            extract("month", Invoice.due_date).label("month"),
            func.count(Invoice.id).label("invoices_overdue"),
        )
        .where(
            Invoice.tenant_id == tid,
            Invoice.status == InvoiceStatus.OVERDUE,
            extract("year", Invoice.due_date) == year,
        )
        .group_by(extract("month", Invoice.due_date))
    )).all()
    overdue_by_month = {int(row.month): int(row.invoices_overdue) for row in overdue_rows}

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Mois", "Revenu (€)", "Factures payées", "Factures en retard"])
    for m in range(1, 13):
        revenue_cents = int(paid_by_month[m].revenue_cents) if m in paid_by_month else 0
        writer.writerow([
            _MONTH_NAMES[m],
            f"{revenue_cents / 100:.2f}",
            int(paid_by_month[m].invoices_paid) if m in paid_by_month else 0,
            overdue_by_month.get(m, 0),
        ])

    output.seek(0)
    filename = f"rapport-financier-{year}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
