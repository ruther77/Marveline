"""Tests unitaires pour NotificationService (Phase 1.3 — Notifications métier)."""
import smtplib
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.services.notification import NotificationService


# ── TestFormatAmount ──────────────────────────────────────────────────


class TestFormatAmount:
    """Tests du helper _format_amount (centimes → EUR)."""

    def test_format_amount_normal(self):
        """25000 centimes → '250,00 €'."""
        result = NotificationService._format_amount(25000)
        assert result == "250,00 €"

    def test_format_amount_zero(self):
        """0 centimes → '0,00 €'."""
        result = NotificationService._format_amount(0)
        assert result == "0,00 €"

    def test_format_amount_cents(self):
        """99 centimes → '0,99 €'."""
        result = NotificationService._format_amount(99)
        assert result == "0,99 €"

    def test_format_amount_large(self):
        """125050 centimes → '1\u202f250,50 €' (espace insécable pour milliers)."""
        result = NotificationService._format_amount(125050)
        assert "1" in result
        assert "250,50" in result
        assert "€" in result


# ── TestTemplateRendering ─────────────────────────────────────────────


class TestTemplateRendering:
    """Tests du rendu des templates Jinja2 (sans envoi SMTP)."""

    @pytest.fixture
    def svc(self):
        """NotificationService instance pour tests template."""
        return NotificationService()

    def test_render_reservation_confirmed(self, svc):
        """Template reservation_confirmed.html rend sans erreur."""
        tpl = svc.jinja_env.get_template("reservation_confirmed.html")
        html = tpl.render(
            frontend_url="http://localhost:3002",
            subject="Test",
            customer_name="Alice Dupont",
            reference="RES-2026-0001",
            event_date=date(2026, 6, 15),
            delivery_date=date(2026, 6, 14),
            return_date=date(2026, 6, 16),
            event_location="Salle des Fêtes",
            total_amount_display="250,00 €",
            deposit_amount_display="100,00 €",
        )
        assert "Alice Dupont" in html
        assert "RES-2026-0001" in html
        assert "250,00 €" in html
        assert "Salle des Fêtes" in html

    def test_render_invoice_created(self, svc):
        """Template invoice_created.html rend sans erreur."""
        tpl = svc.jinja_env.get_template("invoice_created.html")
        html = tpl.render(
            frontend_url="http://localhost:3002",
            subject="Test",
            customer_name="Bob Martin",
            invoice_number="INV-2026-0001",
            reservation_reference="RES-2026-0001",
            total_amount_display="500,00 €",
            due_date=date(2026, 6, 15),
            issue_date=date(2026, 6, 1),
        )
        assert "Bob Martin" in html
        assert "INV-2026-0001" in html
        assert "500,00 €" in html

    def test_render_delivery_completed(self, svc):
        """Template delivery_completed.html rend sans erreur."""
        tpl = svc.jinja_env.get_template("delivery_completed.html")
        html = tpl.render(
            frontend_url="http://localhost:3002",
            subject="Test",
            customer_name="Claire Petit",
            reservation_reference="RES-2026-0002",
            delivery_address="12 rue de la Paix, Paris",
            delivery_date=date(2026, 6, 14),
        )
        assert "Claire Petit" in html
        assert "RES-2026-0002" in html
        assert "12 rue de la Paix" in html

    def test_render_return_completed(self, svc):
        """Template return_completed.html rend sans erreur."""
        tpl = svc.jinja_env.get_template("return_completed.html")
        html = tpl.render(
            frontend_url="http://localhost:3002",
            subject="Test",
            customer_name="David Grand",
            reservation_reference="RES-2026-0003",
            return_date=date(2026, 6, 17),
        )
        assert "David Grand" in html
        assert "RES-2026-0003" in html


# ── TestSendNotifications ─────────────────────────────────────────────


class TestSendNotifications:
    """Tests d'envoi avec mock SMTP."""

    @pytest.fixture
    def svc(self):
        return NotificationService()

    @patch("app.services.notification.smtplib.SMTP")
    def test_send_reservation_confirmed_success(self, mock_smtp_cls, svc):
        """send_reservation_confirmed appelle SMTP et retourne True."""
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = svc.send_reservation_confirmed(
            email="client@example.com",
            customer_name="Alice",
            reference="RES-2026-0001",
            event_date=date(2026, 6, 15),
            delivery_date=date(2026, 6, 14),
            return_date=date(2026, 6, 16),
            event_location="Salle",
            total_cents=25000,
            deposit_cents=10000,
        )
        assert result is True
        mock_server.sendmail.assert_called_once()
        args = mock_server.sendmail.call_args
        assert args[0][1] == "client@example.com"

    @patch("app.services.notification.smtplib.SMTP")
    def test_send_invoice_created_success(self, mock_smtp_cls, svc):
        """send_invoice_created appelle SMTP et retourne True."""
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = svc.send_invoice_created(
            email="client@example.com",
            customer_name="Bob",
            invoice_number="INV-2026-0001",
            reservation_reference="RES-2026-0001",
            total_cents=50000,
            due_date=date(2026, 6, 15),
            issue_date=date(2026, 6, 1),
        )
        assert result is True
        mock_server.sendmail.assert_called_once()

    @patch("app.services.notification.smtplib.SMTP")
    def test_send_delivery_completed_success(self, mock_smtp_cls, svc):
        """send_delivery_completed appelle SMTP et retourne True."""
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = svc.send_delivery_completed(
            email="client@example.com",
            customer_name="Claire",
            reservation_reference="RES-2026-0002",
            delivery_address="12 rue de la Paix",
            delivery_date=date(2026, 6, 14),
        )
        assert result is True
        mock_server.sendmail.assert_called_once()

    @patch("app.services.notification.smtplib.SMTP")
    def test_send_return_completed_success(self, mock_smtp_cls, svc):
        """send_return_completed appelle SMTP et retourne True."""
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = svc.send_return_completed(
            email="client@example.com",
            customer_name="David",
            reservation_reference="RES-2026-0003",
            return_date=date(2026, 6, 17),
        )
        assert result is True
        mock_server.sendmail.assert_called_once()

    @patch("app.services.notification.smtplib.SMTP")
    def test_send_failure_returns_false(self, mock_smtp_cls, svc):
        """SMTP exception → retourne False."""
        mock_smtp_cls.side_effect = smtplib.SMTPException("Connection refused")

        result = svc.send_reservation_confirmed(
            email="client@example.com",
            customer_name="Alice",
            reference="RES-2026-0001",
            event_date=date(2026, 6, 15),
            delivery_date=date(2026, 6, 14),
            return_date=date(2026, 6, 16),
            event_location="Salle",
            total_cents=25000,
            deposit_cents=10000,
        )
        assert result is False


# ── TestBestEffortHooks ───────────────────────────────────────────────


class TestBestEffortHooks:
    """Tests des hooks best-effort (async via Celery .delay())."""

    def _make_mock_reservation(self):
        """Crée un mock reservation avec customer."""
        customer = MagicMock()
        customer.email = "client@example.com"
        customer.display_name = "Alice Dupont"

        reservation = MagicMock()
        reservation.reference = "RES-2026-0001"
        reservation.customer = customer
        reservation.event_date = date(2026, 6, 15)
        reservation.delivery_date = date(2026, 6, 14)
        reservation.return_date = date(2026, 6, 16)
        reservation.event_location = "Salle des Fêtes"
        reservation.total_amount = 25000
        reservation.deposit_amount = 10000
        return reservation

    @patch("app.tasks.notifications.send_reservation_confirmed_email")
    def test_reservation_confirm_calls_delay(self, mock_task):
        """confirm_reservation → send_reservation_confirmed_email.delay() appelée."""
        from app.services.reservation import ReservationService

        reservation = self._make_mock_reservation()
        svc = MagicMock(spec=ReservationService)
        svc.db = MagicMock()

        ReservationService._notify_reservation_confirmed(svc, reservation)

        mock_task.delay.assert_called_once_with(
            email="client@example.com",
            customer_name="Alice Dupont",
            reference="RES-2026-0001",
            event_date_iso="2026-06-15",
            delivery_date_iso="2026-06-14",
            return_date_iso="2026-06-16",
            event_location="Salle des Fêtes",
            total_cents=25000,
            deposit_cents=10000,
        )

    @patch("app.tasks.notifications.send_reservation_confirmed_email")
    def test_reservation_confirm_ok_if_queue_fails(self, mock_task):
        """Celery queue exception → confirm_reservation ne casse pas."""
        from app.services.reservation import ReservationService

        mock_task.delay.side_effect = Exception("Redis down")

        reservation = self._make_mock_reservation()
        svc = MagicMock(spec=ReservationService)
        svc.db = MagicMock()

        # Ne doit pas lever d'exception
        ReservationService._notify_reservation_confirmed(svc, reservation)

    @patch("app.tasks.notifications.send_delivery_completed_email")
    def test_complete_movement_calls_delivery_delay(self, mock_task):
        """complete departure movement → send_delivery_completed_email.delay()."""
        from app.services.inventory_movement import MovementService

        reservation = self._make_mock_reservation()
        reservation.id = 1
        reservation.tenant_id = 1

        movement = MagicMock()
        movement.id = 10
        movement.delivery_address = "12 rue de la Paix"
        movement.actual_date = date(2026, 6, 14)

        mock_full_res = self._make_mock_reservation()
        mock_full_res.id = 1
        mock_full_res.tenant_id = 1

        svc = MagicMock(spec=MovementService)
        svc.db = MagicMock()

        with patch("app.services.reservation.ReservationService") as MockResSvc:
            mock_res_instance = MagicMock()
            mock_res_instance.repo.get_by_id_with_relations.return_value = mock_full_res
            MockResSvc.return_value = mock_res_instance

            MovementService._notify_delivery_completed(svc, reservation, movement)

        mock_task.delay.assert_called_once_with(
            email="client@example.com",
            customer_name="Alice Dupont",
            reservation_reference="RES-2026-0001",
            delivery_address="12 rue de la Paix",
            delivery_date_iso="2026-06-14",
        )
