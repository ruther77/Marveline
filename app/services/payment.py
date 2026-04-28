"""Service Payment — logique métier paiements de factures."""
import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ErrorMessages, InvoiceStatus
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.repositories.payment import AsyncPaymentRepository
from app.schemas.payment import PaymentCreate
from app.services.invoice_payment_rules import apply_invoice_payment

logger = logging.getLogger(__name__)

class PaymentService:
    """Service pour la gestion des paiements de factures."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncPaymentRepository(db)

    async def list_payments(self, invoice_id: int, tenant_id: int) -> list[Payment]:
        """Liste les paiements d'une facture."""
        await self._get_invoice_or_404(invoice_id, tenant_id)
        return await self.repo.list_by_invoice(invoice_id, tenant_id)

    async def add_payment(
        self, invoice_id: int, data: PaymentCreate, tenant_id: int
    ) -> Payment:
        """Ajoute un paiement et recalcule invoice.paid_amount_cents.

        Raises:
            HTTPException 404: Si facture non trouvée.
            HTTPException 400: Si paiement dépasse le solde restant.
            HTTPException 400: Si facture déjà entièrement payée.
        """
        invoice = await self._get_invoice_or_404(invoice_id, tenant_id)

        payment = Payment(
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            amount_cents=data.amount_cents,
            payment_method=data.payment_method,
            payment_date=data.payment_date,
            notes=data.notes,
        )
        self.db.add(payment)
        await self.db.flush()

        status_before = invoice.status
        apply_invoice_payment(
            invoice=invoice,
            amount_cents=data.amount_cents,
            payment_method=data.payment_method,
            payment_date=data.payment_date,
        )

        # Créditer les points fidélité quand la facture passe en PAID
        if invoice.status == InvoiceStatus.PAID and status_before != InvoiceStatus.PAID:
            await self._credit_loyalty_revenue(invoice, tenant_id)

        return payment

    async def _credit_loyalty_revenue(self, invoice: Invoice, tenant_id: int) -> None:
        """Crédite le CA fidélité Marveline quand une facture est payée."""
        try:
            from sqlalchemy import select, and_
            from app.models.reservation import Reservation
            from app.models.loyalty import LoyaltyMember

            if not invoice.reservation_id:
                return

            result = await self.db.execute(
                select(Reservation.customer_id).where(
                    Reservation.id == invoice.reservation_id,
                    Reservation.tenant_id == tenant_id,
                )
            )
            customer_id = result.scalar_one_or_none()
            if not customer_id:
                return

            result = await self.db.execute(
                select(LoyaltyMember).where(
                    and_(
                        LoyaltyMember.customer_id == customer_id,
                        LoyaltyMember.tenant_id == tenant_id,
                        LoyaltyMember.is_active == True,
                    )
                )
            )
            member = result.scalar_one_or_none()
            if not member:
                return

            from app.services.loyalty import LoyaltyService
            loyalty_svc = LoyaltyService(self.db)
            await loyalty_svc.credit_revenue(
                member_id=member.id,
                amount_cents=invoice.total_amount_cents,
                tenant_id=tenant_id,
                reservation_id=invoice.reservation_id,
            )
            logger.info(
                "Loyalty credit_revenue: member=%d amount=%d reservation=%d",
                member.id, invoice.total_amount_cents, invoice.reservation_id,
            )
        except Exception:
            logger.exception("Failed to credit loyalty revenue (non-blocking)")

    async def _get_invoice_or_404(self, invoice_id: int, tenant_id: int) -> Invoice:
        """Récupère la facture ou lève 404."""
        result = await self.db.execute(
            select(Invoice).filter(
                Invoice.id == invoice_id,
                Invoice.tenant_id == tenant_id,
            )
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.INVOICE_NOT_FOUND,
            )
        return invoice
