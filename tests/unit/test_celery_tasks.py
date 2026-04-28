"""Tests unitaires pour les tâches Celery (Phase 1.4).

Tests des modules :
- app.tasks.notifications (4 tâches email async)
- app.tasks.invoicing (check_overdue_invoices)
- app.tasks.monitoring (check_late_movements, check_low_stock)
"""
import logging
from datetime import date
from unittest.mock import MagicMock, patch, call

import pytest


# ── TestNotificationTasks ─────────────────────────────────────────────


class TestNotificationTasks:
    """Tests des 4 tâches de notification email."""

    @patch("app.services.notification.notification_service")
    def test_send_reservation_confirmed_calls_service(self, mock_notif):
        """Task appelle notification_service.send_reservation_confirmed."""
        from app.tasks.notifications import send_reservation_confirmed_email

        # Appel direct de la fonction (pas via .delay())
        send_reservation_confirmed_email(
            email="client@test.com",
            customer_name="Alice",
            reference="RES-2026-0001",
            event_date_iso="2026-06-15",
            delivery_date_iso="2026-06-14",
            return_date_iso="2026-06-16",
            event_location="Salle",
            total_cents=25000,
            deposit_cents=10000,
        )

        mock_notif.send_reservation_confirmed.assert_called_once_with(
            email="client@test.com",
            customer_name="Alice",
            reference="RES-2026-0001",
            event_date=date(2026, 6, 15),
            delivery_date=date(2026, 6, 14),
            return_date=date(2026, 6, 16),
            event_location="Salle",
            total_cents=25000,
            deposit_cents=10000,
        )

    @patch("app.services.notification.notification_service")
    def test_send_invoice_created_calls_service(self, mock_notif):
        """Task appelle notification_service.send_invoice_created."""
        from app.tasks.notifications import send_invoice_created_email

        send_invoice_created_email(
            email="client@test.com",
            customer_name="Bob",
            invoice_number="INV-2026-0001",
            reservation_reference="RES-2026-0001",
            total_cents=50000,
            due_date_iso="2026-06-15",
            issue_date_iso="2026-06-01",
        )

        mock_notif.send_invoice_created.assert_called_once_with(
            email="client@test.com",
            customer_name="Bob",
            invoice_number="INV-2026-0001",
            reservation_reference="RES-2026-0001",
            total_cents=50000,
            due_date=date(2026, 6, 15),
            issue_date=date(2026, 6, 1),
        )

    @patch("app.services.notification.notification_service")
    def test_send_delivery_completed_calls_service(self, mock_notif):
        """Task appelle notification_service.send_delivery_completed."""
        from app.tasks.notifications import send_delivery_completed_email

        send_delivery_completed_email(
            email="client@test.com",
            customer_name="Claire",
            reservation_reference="RES-2026-0002",
            delivery_address="12 rue de la Paix",
            delivery_date_iso="2026-06-14",
        )

        mock_notif.send_delivery_completed.assert_called_once_with(
            email="client@test.com",
            customer_name="Claire",
            reservation_reference="RES-2026-0002",
            delivery_address="12 rue de la Paix",
            delivery_date=date(2026, 6, 14),
        )

    @patch("app.services.notification.notification_service")
    def test_send_return_completed_calls_service(self, mock_notif):
        """Task appelle notification_service.send_return_completed."""
        from app.tasks.notifications import send_return_completed_email

        send_return_completed_email(
            email="client@test.com",
            customer_name="David",
            reservation_reference="RES-2026-0003",
            return_date_iso="2026-06-17",
        )

        mock_notif.send_return_completed.assert_called_once_with(
            email="client@test.com",
            customer_name="David",
            reservation_reference="RES-2026-0003",
            return_date=date(2026, 6, 17),
        )

    def test_date_iso_conversion(self):
        """Dates ISO string → date reconversion correcte."""
        assert date.fromisoformat("2026-06-15") == date(2026, 6, 15)
        assert date.fromisoformat("2026-01-01") == date(2026, 1, 1)
        assert str(date(2026, 6, 15)) == "2026-06-15"

    @patch("app.services.notification.notification_service")
    def test_retry_on_smtp_failure(self, mock_notif):
        """Exception SMTP → exception propagée (triggers Celery retry)."""
        from app.tasks.notifications import send_reservation_confirmed_email

        mock_notif.send_reservation_confirmed.side_effect = Exception("SMTP error")

        # Quand appelé directement (pas via worker), le retry lève MaxRetriesExceeded
        # ou l'exception originale. Vérifions que l'exception n'est pas avalée.
        with pytest.raises(Exception):
            send_reservation_confirmed_email(
                email="client@test.com",
                customer_name="Alice",
                reference="RES-2026-0001",
                event_date_iso="2026-06-15",
                delivery_date_iso="2026-06-14",
                return_date_iso="2026-06-16",
                event_location="Salle",
                total_cents=25000,
                deposit_cents=10000,
            )

    def test_task_registered_on_notifications_queue(self):
        """Tâches notifications sont enregistrées sur queue 'notifications'."""
        from app.tasks.notifications import (
            send_reservation_confirmed_email,
            send_invoice_created_email,
            send_delivery_completed_email,
            send_return_completed_email,
        )

        for task in [
            send_reservation_confirmed_email,
            send_invoice_created_email,
            send_delivery_completed_email,
            send_return_completed_email,
        ]:
            assert task.queue == "notifications"

    def test_max_retries_config(self):
        """Tâches notifications ont max_retries=3."""
        from app.tasks.notifications import (
            send_reservation_confirmed_email,
            send_invoice_created_email,
            send_delivery_completed_email,
            send_return_completed_email,
        )

        for task in [
            send_reservation_confirmed_email,
            send_invoice_created_email,
            send_delivery_completed_email,
            send_return_completed_email,
        ]:
            assert task.max_retries == 3


# ── TestPeriodicTasks ─────────────────────────────────────────────────


class TestPeriodicTasks:
    """Tests des tâches périodiques (invoicing + monitoring)."""

    @patch("app.services.invoice.InvoiceService")
    @patch("app.core.database.get_db_context")
    def test_check_overdue_queries_all_tenants(self, mock_ctx, mock_invoice_cls):
        """check_overdue_invoices itère sur tous les tenant_ids actifs."""
        from app.tasks.invoicing import check_overdue_invoices

        mock_db = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.all.return_value = [
            (1,), (2,),
        ]

        mock_svc = MagicMock()
        mock_svc.check_overdue_invoices.return_value = []
        mock_invoice_cls.return_value = mock_svc

        check_overdue_invoices()

        assert mock_invoice_cls.call_count == 2
        assert mock_svc.check_overdue_invoices.call_count == 2
        mock_svc.check_overdue_invoices.assert_any_call(1)
        mock_svc.check_overdue_invoices.assert_any_call(2)

    @patch("app.services.invoice.InvoiceService")
    @patch("app.core.database.get_db_context")
    def test_check_overdue_commits_changes(self, mock_ctx, mock_invoice_cls):
        """db.commit() appelé si des factures ont été mises à jour."""
        from app.tasks.invoicing import check_overdue_invoices

        mock_db = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.all.return_value = [(1,)]

        mock_svc = MagicMock()
        mock_svc.check_overdue_invoices.return_value = [MagicMock()]
        mock_invoice_cls.return_value = mock_svc

        check_overdue_invoices()

        mock_db.commit.assert_called_once()

    @patch("app.services.invoice.InvoiceService")
    @patch("app.core.database.get_db_context")
    def test_check_overdue_no_commit_if_no_updates(self, mock_ctx, mock_invoice_cls):
        """db.commit() pas appelé si aucune facture mise à jour."""
        from app.tasks.invoicing import check_overdue_invoices

        mock_db = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.all.return_value = [(1,)]

        mock_svc = MagicMock()
        mock_svc.check_overdue_invoices.return_value = []
        mock_invoice_cls.return_value = mock_svc

        check_overdue_invoices()

        mock_db.commit.assert_not_called()

    @patch("app.repositories.inventory_movement.MovementRepository")
    @patch("app.core.database.get_db_context")
    def test_check_late_movements_logs_results(self, mock_ctx, mock_repo_cls, caplog):
        """Warning loggé si mouvements en retard."""
        from app.tasks.monitoring import check_late_movements

        mock_db = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.all.return_value = [(1,)]

        mock_repo = MagicMock()
        mock_repo.list_late.return_value = ([MagicMock(), MagicMock()], 2)
        mock_repo_cls.return_value = mock_repo

        with caplog.at_level(logging.WARNING):
            check_late_movements()

        assert "2 late movements" in caplog.text

    @patch("app.core.database.get_db_context")
    def test_check_low_stock_detects_below_threshold(self, mock_ctx, caplog):
        """Warning loggé si produits avec stock bas."""
        from app.tasks.monitoring import check_low_stock

        mock_db = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [(1,)],
            [MagicMock(), MagicMock(), MagicMock()],
        ]

        with caplog.at_level(logging.WARNING):
            check_low_stock()

        assert "3 products with low stock" in caplog.text

    @patch("app.core.database.get_db_context")
    def test_check_low_stock_custom_threshold(self, mock_ctx):
        """Seuil configurable via paramètre."""
        from app.tasks.monitoring import check_low_stock

        mock_db = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [(1,)],
            [],
        ]

        check_low_stock(threshold=10)


# ── TestAsyncHooks ────────────────────────────────────────────────────


class TestAsyncHooks:
    """Tests que les hooks appellent .delay() au lieu d'appels synchrones."""

    def _make_mock_reservation(self):
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
        reservation.total_amount_cents = 25000
        reservation.deposit_amount_cents = 10000
        return reservation

    @patch("app.tasks.notifications.send_reservation_confirmed_email")
    def test_reservation_confirm_calls_delay(self, mock_task):
        """.delay() appelé (pas appel sync direct)."""
        from app.services.reservation import ReservationService

        reservation = self._make_mock_reservation()
        svc = MagicMock(spec=ReservationService)

        ReservationService._notify_reservation_confirmed(svc, reservation)

        mock_task.delay.assert_called_once()
        kwargs = mock_task.delay.call_args.kwargs
        assert kwargs["email"] == "client@example.com"
        assert kwargs["event_date_iso"] == "2026-06-15"

    @patch("app.tasks.notifications.send_reservation_confirmed_email")
    def test_reservation_confirm_ok_if_queue_fails(self, mock_task):
        """Exception broker → confirm OK (best-effort)."""
        from app.services.reservation import ReservationService

        mock_task.delay.side_effect = Exception("Redis down")

        reservation = self._make_mock_reservation()
        svc = MagicMock(spec=ReservationService)

        # Ne doit pas lever d'exception
        ReservationService._notify_reservation_confirmed(svc, reservation)

    @patch("app.tasks.notifications.send_invoice_created_email")
    def test_invoice_created_calls_delay(self, mock_task):
        """_notify_invoice_created → send_invoice_created_email.delay()."""
        from app.services.reservation import ReservationService

        reservation = self._make_mock_reservation()
        invoice = MagicMock()
        invoice.invoice_number = "INV-2026-0001"
        invoice.total_amount_cents = 50000
        invoice.due_date = date(2026, 6, 15)
        invoice.issue_date = date(2026, 6, 1)

        svc = MagicMock(spec=ReservationService)

        ReservationService._notify_invoice_created(svc, invoice, reservation)

        mock_task.delay.assert_called_once()
        kwargs = mock_task.delay.call_args.kwargs
        assert kwargs["invoice_number"] == "INV-2026-0001"
        assert kwargs["due_date_iso"] == "2026-06-15"

    @pytest.mark.skip(reason="MovementService._notify_delivery_completed supprime ; Celery task send_delivery_completed_email sans appelant actuel (dead code, cf. bug DEAD-NOTIF-01)")
    def test_delivery_completed_calls_delay(self):
        pass

    @patch("app.tasks.notifications.send_return_completed_email")
    def test_return_completed_calls_delay(self, mock_task):
        """_notify_return_completed → send_return_completed_email.delay()."""
        from app.services.inventory_movement import MovementService

        reservation = self._make_mock_reservation()
        reservation.id = 1
        reservation.tenant_id = 1

        movement = MagicMock()
        movement.id = 11
        movement.actual_date = date(2026, 6, 17)

        mock_full_res = self._make_mock_reservation()
        mock_full_res.id = 1
        mock_full_res.tenant_id = 1

        svc = MagicMock(spec=MovementService)
        svc.db = MagicMock()

        with patch("app.services.reservation.ReservationService") as MockResSvc:
            mock_res_instance = MagicMock()
            mock_res_instance.repo.get_by_id_with_relations.return_value = mock_full_res
            MockResSvc.return_value = mock_res_instance

            MovementService._notify_return_completed(svc, reservation, movement)

        mock_task.delay.assert_called_once()
        kwargs = mock_task.delay.call_args.kwargs
        assert kwargs["return_date_iso"] == "2026-06-17"

    @patch("app.tasks.notifications.send_reservation_confirmed_email")
    def test_dates_passed_as_iso_strings(self, mock_task):
        """Dates passées comme str ISO (pas comme date objects)."""
        from app.services.reservation import ReservationService

        reservation = self._make_mock_reservation()
        svc = MagicMock(spec=ReservationService)

        ReservationService._notify_reservation_confirmed(svc, reservation)

        kwargs = mock_task.delay.call_args.kwargs
        # Toutes les dates doivent être des strings ISO
        assert isinstance(kwargs["event_date_iso"], str)
        assert isinstance(kwargs["delivery_date_iso"], str)
        assert isinstance(kwargs["return_date_iso"], str)


# ── TestBeatSchedule ──────────────────────────────────────────────────


class TestBeatSchedule:
    """Tests de la configuration beat_schedule."""

    def test_beat_schedule_has_three_entries(self):
        """3 tâches périodiques configurées."""
        from app.tasks.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        assert len(schedule) == 3
        assert "check-overdue-invoices-daily" in schedule
        assert "check-late-movements-hourly" in schedule
        assert "check-low-stock-daily" in schedule

    def test_autodiscover_modules(self):
        """Les modules de tâches sont enregistrés."""
        from app.tasks.celery_app import celery_app

        # Les tâches doivent être découvertes
        task_names = list(celery_app.tasks.keys())
        assert any("notifications" in t for t in task_names)
        assert any("invoicing" in t for t in task_names)
        assert any("monitoring" in t for t in task_names)
