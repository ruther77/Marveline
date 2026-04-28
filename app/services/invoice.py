"""Service métier pour les factures."""
import logging
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    HOURLY_RATE_WEEKDAY_CENTS,
    HOURLY_RATE_WEEKEND_CENTS,
    ErrorMessages,
    InvoiceStatus,
    Limits,
    PaymentMethod,
    ReservationStatus,
)
from app.models.invoice import Invoice
from app.models.invoice_charge import InvoiceCharge
from app.models.tenant_settings import TenantSettings
from app.repositories.invoice import AsyncInvoiceRepository
from app.repositories.reservation import AsyncReservationRepository
from app.schemas.invoice import (
    AddPaymentRequest,
    InvoiceChargeCreate,
    InvoiceCreate,
    InvoiceUpdate,
)
from app.services.invoice_payment_rules import apply_invoice_payment

logger = logging.getLogger(__name__)


async def update_invoice_after_charge(
    invoice: Invoice,
    charge_amount_cents: int,
    db: AsyncSession,
) -> None:
    """Met à jour total_amount_cents + TVA après ajout d'une InvoiceCharge.

    Les charges (dommages, main d'oeuvre) sont HT. La TVA est appliquée
    au même taux que la facture.
    """
    invoice.total_amount_cents += charge_amount_cents
    if invoice.tva_rate is not None:
        invoice.tva_amount_cents = round(invoice.total_amount_cents * invoice.tva_rate)
        invoice.total_ttc_cents = invoice.total_amount_cents + invoice.tva_amount_cents
    await db.flush()


class InvoiceService:
    """Service async pour la gestion des factures."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncInvoiceRepository(db)
        self.reservation_repo = AsyncReservationRepository(db)

    async def list_invoices(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None,
        reservation_id: Optional[int] = None,
    ) -> tuple[list[Invoice], int]:
        filters = {}
        if status_filter:
            filters["status"] = status_filter
        if reservation_id:
            filters["reservation_id"] = reservation_id
        return await self.repo.list_with_customer(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters=filters if filters else None,
        )

    async def get_invoice(self, invoice_id: int, tenant_id: int) -> Invoice:
        invoice = await self.repo.get_by_id_with_relations(invoice_id, tenant_id)
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.INVOICE_NOT_FOUND,
            )
        return invoice

    async def generate_invoice_number(self, tenant_id: int) -> str:
        from sqlalchemy import func, select, text

        year = datetime.now().year
        prefix = f"INV-{year}-"

        lock_key = 0x494E56 ^ (year & 0xFFFF) ^ (tenant_id & 0xFFFF)
        await self.db.execute(text(f"SELECT pg_advisory_xact_lock({lock_key})"))

        last = await self.db.scalar(
            select(func.max(Invoice.invoice_number)).filter(
                Invoice.invoice_number.like(f"{prefix}%"),
                Invoice.tenant_id == tenant_id,
            )
        )

        if last:
            try:
                last_counter = int(last.rsplit("-", 1)[-1])
            except (ValueError, IndexError):
                last_counter = 0
        else:
            last_counter = 0

        counter = last_counter + 1
        if counter > 9999:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ErrorMessages.INVOICE_NUMBER_OVERFLOW,
            )
        return f"{prefix}{counter:0{Limits.INVOICE_NUMBER_PADDING}d}"

    async def generate_from_reservation(
        self,
        invoice_data: InvoiceCreate,
        tenant_id: int,
        invoice_type: str = "full",
        amount_override_cents: Optional[int] = None,
    ) -> Invoice:
        from sqlalchemy import select

        reservation = await self.reservation_repo.get_by_id_with_relations(
            invoice_data.reservation_id, tenant_id
        )
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND,
            )

        existing_invoice = await self.repo.get_by_reservation_and_type(
            invoice_data.reservation_id, invoice_type, tenant_id
        )
        if existing_invoice:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invoice already exists for this reservation (ID: {existing_invoice.id})",
            )

        invoice_number = await self.generate_invoice_number(tenant_id)

        tenant_settings = await self.db.scalar(
            select(TenantSettings).filter(TenantSettings.tenant_id == tenant_id)
        )
        if tenant_settings:
            default_tva_rate = tenant_settings.vat_rate
        else:
            default_tva_rate = 0.20
            logger.warning(
                "tenant_settings introuvable pour tenant_id=%s — taux TVA fallback 20%% appliqué",
                tenant_id,
            )

        total_ht = (
            amount_override_cents
            if amount_override_cents is not None
            else reservation.total_amount_cents
        )

        tva_breakdown, tva_rate, tva_amount_cents, total_ttc_cents = (
            self._compute_tva_breakdown(reservation, total_ht, default_tva_rate)
        )

        invoice = Invoice(
            tenant_id=tenant_id,
            reservation_id=invoice_data.reservation_id,
            invoice_number=invoice_number,
            issue_date=invoice_data.issue_date,
            due_date=invoice_data.due_date,
            total_amount_cents=total_ht,
            paid_amount_cents=0,
            status=InvoiceStatus.DRAFT,
            payment_method=None,
            payment_date=None,
            tva_rate=tva_rate,
            tva_amount_cents=tva_amount_cents,
            total_ttc_cents=total_ttc_cents,
            tva_breakdown=tva_breakdown,
            invoice_type=invoice_type,
        )

        created = await self.repo.create(invoice)
        return await self.repo.get_by_id_with_relations(created.id, tenant_id)

    async def add_payment(
        self,
        invoice_id: int,
        payment_data: AddPaymentRequest,
        tenant_id: int,
    ) -> Invoice:
        invoice = await self.repo.get_by_id(invoice_id, tenant_id)
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.INVOICE_NOT_FOUND,
            )

        apply_invoice_payment(
            invoice=invoice,
            amount_cents=payment_data.amount_cents,
            payment_method=payment_data.payment_method,
            payment_date=payment_data.payment_date,
        )

        await self.repo.update(invoice)
        return await self.repo.get_by_id_with_relations(invoice_id, tenant_id)

    async def update_invoice(
        self,
        invoice_id: int,
        invoice_data: InvoiceUpdate,
        tenant_id: int,
    ) -> Invoice:
        invoice = await self.repo.get_by_id(invoice_id, tenant_id)
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.INVOICE_NOT_FOUND,
            )
        if invoice.status == InvoiceStatus.PAID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.INVOICE_PAID_NO_MODIFY,
            )
        update_data = invoice_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(invoice, field, value)
        await self.repo.update(invoice)
        return await self.repo.get_by_id_with_relations(invoice_id, tenant_id)

    async def check_overdue_invoices(
        self,
        tenant_id: int,
        as_of_date: Optional[date] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[Invoice]:
        overdue_invoices = await self.repo.list_overdue(
            tenant_id=tenant_id,
            as_of_date=as_of_date,
            limit=limit,
            skip=skip,
        )
        for invoice in overdue_invoices:
            if invoice.status not in (InvoiceStatus.OVERDUE, InvoiceStatus.CANCELLED):
                invoice.status = InvoiceStatus.OVERDUE
                await self.repo.update(invoice)
        return overdue_invoices

    async def cancel_invoice(self, invoice_id: int, tenant_id: int) -> Invoice:
        invoice = await self.repo.get_by_id(invoice_id, tenant_id)
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.INVOICE_NOT_FOUND,
            )
        if invoice.status == InvoiceStatus.PAID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.INVOICE_PAID_NO_CANCEL,
            )
        if invoice.paid_amount_cents > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Impossible d'annuler : {invoice.paid_amount_cents} centimes déjà encaissés. "
                    "Créez un avoir (credit-note) avant d'annuler."
                ),
            )
        invoice.status = InvoiceStatus.CANCELLED
        if invoice.cancelled_at is None:
            invoice.cancelled_at = datetime.now()
        await self.repo.update(invoice)
        return await self.repo.get_by_id_with_relations(invoice_id, tenant_id)

    async def list_overdue(self, tenant_id: int) -> list[Invoice]:
        return await self.repo.list_overdue(tenant_id=tenant_id)

    async def add_charge(
        self,
        invoice_id: int,
        tenant_id: int,
        charge_data: InvoiceChargeCreate,
    ) -> InvoiceCharge:
        invoice = await self.repo.get_by_id(invoice_id, tenant_id)
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.INVOICE_NOT_FOUND,
            )
        if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot add charge to invoice with status '{invoice.status}'",
            )

        if charge_data.charge_type == "DAMAGE":
            amount_cents = charge_data.amount_cents
            if amount_cents is None and charge_data.damage_type_id:
                from app.models.damage_type import DamageType
                dt_result = await self.db.execute(
                    select(DamageType).where(
                        DamageType.id == charge_data.damage_type_id,
                        DamageType.tenant_id == tenant_id,
                    )
                )
                damage_type = dt_result.scalars().first()
                if damage_type and damage_type.default_fee_cents > 0:
                    amount_cents = damage_type.default_fee_cents
            if amount_cents is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="amount_cents is required for DAMAGE charges (or select a DamageType with default_fee_cents)",
                )
        else:
            if charge_data.hours is None or charge_data.day_type is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="hours and day_type are required for LABOR charges",
                )
            rate = (
                HOURLY_RATE_WEEKDAY_CENTS
                if charge_data.day_type == "weekday"
                else HOURLY_RATE_WEEKEND_CENTS
            )
            amount_cents = math.ceil(float(charge_data.hours) * rate)

        charge = InvoiceCharge(
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            charge_type=charge_data.charge_type,
            amount_cents=amount_cents,
            description=charge_data.description,
            hours=charge_data.hours,
            day_type=charge_data.day_type,
            damage_type_id=charge_data.damage_type_id,
        )

        persisted = await self.repo.add_charge(charge)
        await update_invoice_after_charge(invoice, amount_cents, self.db)
        await self.repo.update(invoice)
        return persisted

    async def generate_tva_report(self, tenant_id: int, month: str) -> dict:
        import calendar as cal_mod
        from datetime import date as date_type
        from sqlalchemy import select

        try:
            year, mon = map(int, month.split("-"))
            _, last_day = cal_mod.monthrange(year, mon)
            start_date = date_type(year, mon, 1)
            end_date = date_type(year, mon, last_day)
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid month format. Expected YYYY-MM (ex: 2026-02)",
            )

        invoices = (
            await self.db.scalars(
                select(Invoice).filter(
                    Invoice.tenant_id == tenant_id,
                    Invoice.status == InvoiceStatus.PAID,
                    Invoice.issue_date >= start_date,
                    Invoice.issue_date <= end_date,
                )
            )
        ).all()

        groups: dict[float, dict] = {}
        total_base_ht = 0
        total_tva = 0

        for inv in invoices:
            if inv.tva_breakdown:
                for item in inv.tva_breakdown:
                    rate = item["rate"]
                    if rate not in groups:
                        groups[rate] = {"base_ht_cents": 0, "tva_cents": 0, "ttc_cents": 0}
                    groups[rate]["base_ht_cents"] += item["base_ht_cents"]
                    groups[rate]["tva_cents"] += item["tva_cents"]
                    groups[rate]["ttc_cents"] += item["ttc_cents"]
                    total_base_ht += item["base_ht_cents"]
                    total_tva += item["tva_cents"]
            elif inv.tva_rate is not None and inv.tva_amount_cents is not None:
                rate = inv.tva_rate
                base_ht = inv.total_amount_cents
                tva = inv.tva_amount_cents
                ttc = base_ht + tva
                if rate not in groups:
                    groups[rate] = {"base_ht_cents": 0, "tva_cents": 0, "ttc_cents": 0}
                groups[rate]["base_ht_cents"] += base_ht
                groups[rate]["tva_cents"] += tva
                groups[rate]["ttc_cents"] += ttc
                total_base_ht += base_ht
                total_tva += tva

        breakdown_by_rate = [
            {
                "rate": rate,
                "base_ht_cents": data["base_ht_cents"],
                "tva_cents": data["tva_cents"],
                "ttc_cents": data["ttc_cents"],
            }
            for rate, data in sorted(groups.items())
        ]

        return {
            "month": month,
            "invoice_count": len(invoices),
            "total_base_ht_cents": total_base_ht,
            "total_tva_cents": total_tva,
            "total_ttc_cents": total_base_ht + total_tva,
            "breakdown_by_rate": breakdown_by_rate,
        }

    def _compute_tva_breakdown(
        self,
        reservation,
        total_ht: int,
        default_tva_rate: float,
    ) -> tuple[list | None, float, int, int]:
        """Calcule le breakdown TVA multi-taux depuis les lignes de réservation.

        Returns:
            Tuple (tva_breakdown, tva_rate_global, tva_amount_cents, total_ttc_cents)
            - tva_breakdown: liste de dicts par taux, ou None si taux unique
            - tva_rate_global: taux représentatif (premier taux ou taux tenant)
            - tva_amount_cents: total TVA en centimes
            - total_ttc_cents: total TTC en centimes
        """
        lines = reservation.lines if reservation.lines else []

        if not lines:
            tva_amount_cents = round(total_ht * default_tva_rate)
            return None, default_tva_rate, tva_amount_cents, total_ht + tva_amount_cents

        groups: dict[float, int] = {}
        total_lines_ht = sum(line.subtotal_cents for line in lines)

        for line in lines:
            rate = line.tva_rate
            groups[rate] = groups.get(rate, 0) + line.subtotal_cents

        if total_lines_ht > 0 and total_ht != total_lines_ht:
            ratio = Decimal(total_ht) / Decimal(total_lines_ht)
            groups = {rate: round(int(base) * ratio) for rate, base in groups.items()}

        breakdown = []
        total_tva = 0
        for rate, base_ht in sorted(groups.items()):
            tva = round(base_ht * rate)
            total_tva += tva
            breakdown.append({
                "rate": rate,
                "base_ht_cents": base_ht,
                "tva_cents": tva,
                "ttc_cents": base_ht + tva,
            })

        total_ttc_cents = total_ht + total_tva

        rates = list(groups.keys())
        if len(rates) == 1:
            return None, rates[0], total_tva, total_ttc_cents

        return breakdown, rates[0], total_tva, total_ttc_cents


# Backward-compat alias
AsyncInvoiceService = InvoiceService
