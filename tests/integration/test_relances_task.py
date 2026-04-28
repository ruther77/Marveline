"""Tests intégration — Celery task `execute_scheduled_relances` (F1058 FIRE-DRILL).

Couvre la régression RELANCE-FAKE-SENT-01 :
  - Avant fix : status='sent' + log "Relance sent" sans envoyer email.
  - Après fix : envoi réel via notification_service.send_relance_email,
    status='sent' SI gateway 200, sinon status='failed' + email_send_error.

Trois scénarios :
  1. Envoi nominal réussi → status='sent', sent_at=now, gateway appelé 1×.
  2. Gateway lève exception → status='failed', email_send_error capturé, gateway appelé 1×.
  3. Gateway retourne False → status='failed', email_send_error="gateway returned False".

Bonus : skip propres si invoice paid/cancelled, customer sans email, invoice introuvable.
"""
from contextlib import contextmanager
from datetime import date, datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from app.constants import ProductCategory, ReservationStatus
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.product import Product
from app.models.relance import Relance
from app.models.reservation import Reservation, ReservationLine
from app.tasks.relances import execute_scheduled_relances


@pytest.fixture
def patch_db_context(test_db):
    """Patch app.core.database.get_db_context pour pointer sur la test_db.

    Le task Celery `execute_scheduled_relances` importe `get_db_context` depuis
    `app.core.database` et l'appelle pour obtenir une session — sans cette
    patch, il écrirait dans la DB prod (CaroCorp), pas la test DB (CaroCorp_test).
    """
    @contextmanager
    def _ctx():
        yield test_db

    with patch("app.core.database.get_db_context", _ctx):
        yield


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def _setup_relance_due(test_db, test_tenant_record):
    """Crée un set complet customer + reservation + invoice + relance échue.

    Retourne (relance, invoice, customer) — relance.scheduled_at = now-1h, status='scheduled'.
    """
    customer = Customer(
        tenant_id=test_tenant_record.id,
        first_name="Jean",
        last_name="Dupont",
        email="jean.dupont@example.com",
        customer_type="individual",
    )
    test_db.add(customer)
    test_db.flush()

    product = Product(
        tenant_id=test_tenant_record.id,
        name="Chaise pliante",
        sku="CHAISE-001",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=500,
        stock_quantity=10,
        available_quantity=10,
    )
    test_db.add(product)
    test_db.flush()

    reservation = Reservation(
        tenant_id=test_tenant_record.id,
        customer_id=customer.id,
        reference="RES-RELTASK-001",
        event_date=date(2026, 6, 2),
        delivery_date=date(2026, 6, 1),
        return_date=date(2026, 6, 3),
        event_location="Salle test",
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=10000,
        deposit_amount_cents=0,
    )
    test_db.add(reservation)
    test_db.flush()
    test_db.add(ReservationLine(
        tenant_id=test_tenant_record.id,
        reservation_id=reservation.id,
        product_id=product.id,
        quantity=1, unit_price_cents=10000, subtotal_cents=10000,
    ))

    invoice = Invoice(
        tenant_id=test_tenant_record.id,
        reservation_id=reservation.id,
        invoice_number="INV-RELTASK-001",
        issue_date=date.today() - timedelta(days=10),
        due_date=date.today() - timedelta(days=3),
        total_amount_cents=10000,
        total_ttc_cents=12000,
        paid_amount_cents=0,
        status="sent",
    )
    test_db.add(invoice)
    test_db.flush()

    relance = Relance(
        tenant_id=test_tenant_record.id,
        invoice_id=invoice.id,
        scheduled_at=datetime.now(timezone.utc) - timedelta(hours=1),
        status="scheduled",
        channel="email",
        created_at=datetime.now(timezone.utc),
    )
    test_db.add(relance)
    test_db.commit()
    test_db.refresh(relance)
    test_db.refresh(invoice)
    test_db.refresh(customer)
    return relance, invoice, customer


# ── Tests F1058 régression ───────────────────────────────────────────────────


class TestRelanceTaskF1058:
    def test_send_ok_marks_sent_and_calls_gateway(
        self, test_db, _setup_relance_due, patch_db_context
    ):
        """F1058 : gateway 200 → status='sent', sent_at peuplé, gateway appelé 1×."""
        relance, invoice, customer = _setup_relance_due

        with patch(
            "app.services.notification.notification_service.send_relance_email",
            return_value=True,
        ) as mock_send:
            result = execute_scheduled_relances()

        assert mock_send.call_count == 1, "F1058 régression : send_relance_email NON appelé"
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["email"] == customer.email
        assert call_kwargs["invoice_number"] == invoice.invoice_number
        assert call_kwargs["invoice_total_cts"] == invoice.total_ttc_cents

        assert result["sent"] == 1
        assert result["failed"] == 0
        assert result["skipped"] == 0

        test_db.refresh(relance)
        assert relance.status == "sent"
        assert relance.sent_at is not None
        assert relance.email_send_error is None

    def test_gateway_exception_marks_failed_with_error(
        self, test_db, _setup_relance_due, patch_db_context
    ):
        """F1058 : gateway lève → status='failed', email_send_error capturé, PAS 'sent'."""
        relance, _, _ = _setup_relance_due

        with patch(
            "app.services.notification.notification_service.send_relance_email",
            side_effect=RuntimeError("SMTP timeout"),
        ) as mock_send:
            result = execute_scheduled_relances()

        assert mock_send.call_count == 1
        assert result["failed"] == 1
        assert result["sent"] == 0

        test_db.refresh(relance)
        assert relance.status == "failed"
        assert relance.sent_at is None
        assert "SMTP timeout" in (relance.email_send_error or "")

    def test_gateway_returns_false_marks_failed(
        self, test_db, _setup_relance_due, patch_db_context
    ):
        """F1058 : gateway False (sans exception) → status='failed', email_send_error informatif."""
        relance, _, _ = _setup_relance_due

        with patch(
            "app.services.notification.notification_service.send_relance_email",
            return_value=False,
        ):
            result = execute_scheduled_relances()

        assert result["failed"] == 1
        test_db.refresh(relance)
        assert relance.status == "failed"
        assert relance.sent_at is None
        assert relance.email_send_error  # message non vide

    def test_invoice_paid_skips_without_calling_gateway(
        self, test_db, _setup_relance_due, patch_db_context
    ):
        """Invoice déjà payée → relance cancelled, gateway PAS appelé."""
        relance, invoice, _ = _setup_relance_due
        invoice.status = "paid"
        test_db.commit()

        with patch(
            "app.services.notification.notification_service.send_relance_email",
            return_value=True,
        ) as mock_send:
            result = execute_scheduled_relances()

        assert mock_send.call_count == 0, "Gateway ne doit PAS être appelé si invoice paid"
        assert result["skipped"] == 1
        test_db.refresh(relance)
        assert relance.status == "cancelled"

    def test_customer_without_email_skips_without_calling_gateway(
        self, test_db, _setup_relance_due, patch_db_context
    ):
        """Customer sans email → relance cancelled, gateway PAS appelé."""
        relance, _, customer = _setup_relance_due
        customer.email = ""  # NOT NULL en DB, mais `not customer.email` matche
        test_db.commit()

        with patch(
            "app.services.notification.notification_service.send_relance_email",
            return_value=True,
        ) as mock_send:
            result = execute_scheduled_relances()

        assert mock_send.call_count == 0
        assert result["skipped"] == 1
        test_db.refresh(relance)
        assert relance.status == "cancelled"

    def test_scheduled_in_future_not_processed(
        self, test_db, _setup_relance_due, patch_db_context
    ):
        """Relance scheduled_at dans le futur → ni sent ni failed ni cancelled."""
        relance, _, _ = _setup_relance_due
        relance.scheduled_at = datetime.now(timezone.utc) + timedelta(hours=2)
        test_db.commit()

        with patch(
            "app.services.notification.notification_service.send_relance_email",
            return_value=True,
        ) as mock_send:
            result = execute_scheduled_relances()

        assert mock_send.call_count == 0
        assert result["total"] == 0
        test_db.refresh(relance)
        assert relance.status == "scheduled"
