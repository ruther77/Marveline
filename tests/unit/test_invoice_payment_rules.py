"""Tests unitaires des règles partagées d'encaissement facture."""
from datetime import date

import pytest
from fastapi import HTTPException

from app.constants import InvoiceStatus
from app.models.invoice import Invoice
from app.services.invoice_payment_rules import apply_invoice_payment


def _make_invoice(
    *,
    status: str = InvoiceStatus.DRAFT,
    total_amount_cents: int = 10_000,
    paid_amount_cents: int = 0,
) -> Invoice:
    return Invoice(
        tenant_id=1,
        reservation_id=1,
        invoice_number="INV-RULES-0001",
        issue_date=date.today(),
        due_date=date.today(),
        total_amount_cents=total_amount_cents,
        paid_amount_cents=paid_amount_cents,
        status=status,
    )


def test_apply_invoice_payment_rejects_cancelled_invoice():
    invoice = _make_invoice(status=InvoiceStatus.CANCELLED)

    with pytest.raises(HTTPException) as exc:
        apply_invoice_payment(invoice, 1000, "card", date.today())

    assert exc.value.status_code == 400
    assert "cancelled" in str(exc.value.detail).lower()


def test_apply_invoice_payment_rejects_already_paid_invoice():
    invoice = _make_invoice(status=InvoiceStatus.PAID, total_amount_cents=5000, paid_amount_cents=5000)

    with pytest.raises(HTTPException) as exc:
        apply_invoice_payment(invoice, 100, "cash", date.today())

    assert exc.value.status_code == 400
    assert "already paid" in str(exc.value.detail).lower()


def test_apply_invoice_payment_rejects_overpayment():
    invoice = _make_invoice(total_amount_cents=5000, paid_amount_cents=4000)

    with pytest.raises(HTTPException) as exc:
        apply_invoice_payment(invoice, 2000, "transfer", date.today())

    assert exc.value.status_code == 400
    assert "exceeds remaining balance" in str(exc.value.detail).lower()


def test_apply_invoice_payment_marks_invoice_paid_when_balance_reaches_zero():
    invoice = _make_invoice(total_amount_cents=5000, paid_amount_cents=4000)

    apply_invoice_payment(invoice, 1000, "check", date.today())

    assert invoice.paid_amount_cents == 5000
    assert invoice.status == InvoiceStatus.PAID
