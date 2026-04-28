"""Service Treasury — vue unifiee deposits + payments."""
import logging
from datetime import date

from sqlalchemy import func, select, literal_column, union_all, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deposit import Deposit
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.reservation import Reservation
from app.models.customer import Customer
from app.schemas.treasury import TreasuryEntry, TreasurySummary

logger = logging.getLogger(__name__)


class TreasuryService:
    """Service pour la tresorerie unifiee."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_entries(
        self,
        tenant_id: int,
        *,
        entry_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        method: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[TreasuryEntry], int]:
        """Liste unifiee deposits + payments, triee par date desc."""
        entries: list[TreasuryEntry] = []

        # Deposits (exclus si filtre method actif — deposits n'ont pas de method)
        if entry_type in (None, "deposit") and not method:
            dep_entries = await self._get_deposit_entries(
                tenant_id, date_from, date_to, skip=0, limit=500,
            )
            entries.extend(dep_entries)

        # Payments
        if entry_type in (None, "payment"):
            pay_entries = await self._get_payment_entries(
                tenant_id, date_from, date_to, method, skip=0, limit=500,
            )
            entries.extend(pay_entries)

        entries.sort(key=lambda e: e.entry_date, reverse=True)
        total = len(entries)
        return entries[skip:skip + limit], total

    async def get_summary(
        self,
        tenant_id: int,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> TreasurySummary:
        """KPI agreges deposits + payments."""
        dep_summary = await self._deposits_summary(tenant_id, date_from, date_to)
        pay_summary = await self._payments_summary(tenant_id, date_from, date_to)

        return TreasurySummary(
            total_collected_cents=dep_summary["held"] + pay_summary["total"],
            deposits_held_cents=dep_summary["held"],
            deposits_retained_cents=dep_summary["retained"],
            deposits_released_cents=dep_summary["released"],
            payments_total_cents=pay_summary["total"],
            deposits_count=dep_summary["count"],
            payments_count=pay_summary["count"],
            by_method=pay_summary["by_method"],
        )

    async def _get_deposit_entries(
        self,
        tenant_id: int,
        date_from: date | None,
        date_to: date | None,
        skip: int,
        limit: int,
    ) -> list[TreasuryEntry]:
        query = (
            select(
                Deposit,
                Reservation.reference,
                Customer.first_name,
                Customer.last_name,
            )
            .join(Reservation, Deposit.reservation_id == Reservation.id)
            .outerjoin(Customer, Reservation.customer_id == Customer.id)
            .where(
                Deposit.tenant_id == tenant_id,
            )
        )
        if date_from:
            query = query.where(Deposit.created_at >= date_from)
        if date_to:
            query = query.where(Deposit.created_at <= date_to)

        query = query.order_by(Deposit.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        rows = result.all()

        entries = []
        for dep, ref, first, last in rows:
            name = f"{first or ''} {last or ''}".strip() or None
            entries.append(TreasuryEntry(
                entry_type="deposit",
                source_id=dep.reservation_id,
                amount_cents=dep.amount_cents,
                entry_date=(dep.collection_date or dep.created_at.date()),
                method=None,
                status=dep.status,
                reference=ref,
                customer_name=name,
                notes=dep.notes,
            ))
        return entries

    async def _get_payment_entries(
        self,
        tenant_id: int,
        date_from: date | None,
        date_to: date | None,
        method: str | None,
        skip: int,
        limit: int,
    ) -> list[TreasuryEntry]:
        query = (
            select(
                Payment,
                Invoice.reservation_id,
                Invoice.invoice_number,
            )
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .where(
                Payment.tenant_id == tenant_id,
            )
        )
        if date_from:
            query = query.where(Payment.payment_date >= date_from)
        if date_to:
            query = query.where(Payment.payment_date <= date_to)
        if method:
            query = query.where(Payment.payment_method == method)

        query = query.order_by(Payment.payment_date.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        rows = result.all()

        entries = []
        for pay, resa_id, inv_num in rows:
            entries.append(TreasuryEntry(
                entry_type="payment",
                source_id=pay.invoice_id,
                amount_cents=pay.amount_cents,
                entry_date=pay.payment_date,
                method=pay.payment_method,
                status=None,
                reference=inv_num,
                customer_name=None,
                notes=pay.notes,
            ))
        return entries

    async def _deposits_summary(
        self, tenant_id: int, date_from: date | None, date_to: date | None
    ) -> dict:
        query = select(
            Deposit.status,
            func.count().label("cnt"),
            func.coalesce(func.sum(Deposit.amount_cents), 0).label("total"),
        ).where(
            Deposit.tenant_id == tenant_id,
        ).group_by(Deposit.status)

        if date_from:
            query = query.where(Deposit.created_at >= date_from)
        if date_to:
            query = query.where(Deposit.created_at <= date_to)

        result = await self.db.execute(query)
        rows = result.all()

        summary = {"held": 0, "retained": 0, "released": 0, "count": 0}
        for status_val, cnt, total in rows:
            summary[status_val] = int(total)
            summary["count"] += cnt
        return summary

    async def _payments_summary(
        self, tenant_id: int, date_from: date | None, date_to: date | None
    ) -> dict:
        query = select(
            Payment.payment_method,
            func.count().label("cnt"),
            func.coalesce(func.sum(Payment.amount_cents), 0).label("total"),
        ).where(
            Payment.tenant_id == tenant_id,
        ).group_by(Payment.payment_method)

        if date_from:
            query = query.where(Payment.payment_date >= date_from)
        if date_to:
            query = query.where(Payment.payment_date <= date_to)

        result = await self.db.execute(query)
        rows = result.all()

        by_method = {}
        total = 0
        count = 0
        for method_val, cnt, method_total in rows:
            by_method[method_val] = int(method_total)
            total += int(method_total)
            count += cnt

        return {"total": total, "count": count, "by_method": by_method}
