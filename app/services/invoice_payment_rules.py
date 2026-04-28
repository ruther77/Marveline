"""Règles métier partagées pour l'encaissement des factures."""
from datetime import date

from fastapi import HTTPException, status

from app.constants import ErrorMessages, InvoiceStatus
from app.models.invoice import Invoice


def apply_invoice_payment(
    invoice: Invoice,
    amount_cents: int,
    payment_method: str,
    payment_date: date,
) -> None:
    """Valide et applique un paiement sur une facture.

    Cette fonction est la source de vérité commune pour:
    - POST /invoices/{id}/add-payment (legacy)
    - POST /invoices/{id}/payments (endpoint canonique)
    """
    if amount_cents <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.PAYMENT_AMOUNT_INVALID,
        )

    if invoice.status == InvoiceStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.INVOICE_CANCELLED_NO_PAYMENT,
        )

    if invoice.status == InvoiceStatus.PAID or invoice.paid_amount_cents >= invoice.total_amount_cents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.INVOICE_ALREADY_PAID,
        )

    remaining = invoice.total_amount_cents - invoice.paid_amount_cents
    if amount_cents > remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Payment amount ({amount_cents} cents) exceeds remaining balance "
                f"({remaining} cents)"
            ),
        )

    invoice.paid_amount_cents += amount_cents
    # payment_method et payment_date vivent dans la table payments (source de verite).
    # On garde les champs Invoice a jour comme cache du dernier paiement.
    if payment_method:
        invoice.payment_method = payment_method
    if payment_date:
        invoice.payment_date = payment_date

    if invoice.paid_amount_cents >= invoice.total_amount_cents:
        invoice.status = InvoiceStatus.PAID
    elif invoice.status == InvoiceStatus.DRAFT:
        invoice.status = InvoiceStatus.SENT
