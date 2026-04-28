"""Tests unitaires — auto-scheduling relances factures OVERDUE."""
import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.tasks.invoicing import _maybe_schedule_relance


class FakeInvoice:
    def __init__(self, id, invoice_number, due_date, status="overdue"):
        self.id = id
        self.invoice_number = invoice_number
        self.due_date = due_date
        self.status = status


class FakeRelance:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def mock_db():
    """Simule une session SQLAlchemy avec query chainable."""
    db = MagicMock()
    return db


def _setup_db_queries(db, scheduled_exists=False, sent_count=0):
    """Configure les retours du mock db.query pour Relance."""
    query_mock = MagicMock()
    filter_mock = MagicMock()

    query_mock.filter.return_value = filter_mock
    filter_mock.filter.return_value = filter_mock
    filter_mock.first.return_value = MagicMock() if scheduled_exists else None
    filter_mock.count.return_value = sent_count

    db.query.return_value = query_mock
    return db


class TestMaybeScheduleRelance:
    """Tests pour _maybe_schedule_relance."""

    def test_creates_relance_at_7_days(self, mock_db):
        """Facture overdue 7j → relance creee."""
        _setup_db_queries(mock_db, scheduled_exists=False, sent_count=0)
        invoice = FakeInvoice(1, "INV-001", date.today() - timedelta(days=7))
        now = datetime.now(timezone.utc)

        result = _maybe_schedule_relance(mock_db, 1, invoice, 7, now)
        assert result is True
        mock_db.add.assert_called_once()

    def test_no_relance_before_threshold(self, mock_db):
        """Facture overdue 3j → pas de relance (seuil = 7j min)."""
        _setup_db_queries(mock_db, scheduled_exists=False, sent_count=0)
        invoice = FakeInvoice(1, "INV-001", date.today() - timedelta(days=3))
        now = datetime.now(timezone.utc)

        result = _maybe_schedule_relance(mock_db, 1, invoice, 3, now)
        assert result is False

    def test_no_duplicate_if_scheduled_exists(self, mock_db):
        """Si une relance scheduled existe deja → pas de doublon."""
        _setup_db_queries(mock_db, scheduled_exists=True, sent_count=0)
        invoice = FakeInvoice(1, "INV-001", date.today() - timedelta(days=30))
        now = datetime.now(timezone.utc)

        result = _maybe_schedule_relance(mock_db, 1, invoice, 30, now)
        assert result is False
        mock_db.add.assert_not_called()

    def test_creates_relance_at_30_days(self, mock_db):
        """Facture overdue 30j avec 1 relance deja envoyee → nouvelle relance."""
        _setup_db_queries(mock_db, scheduled_exists=False, sent_count=1)
        invoice = FakeInvoice(1, "INV-001", date.today() - timedelta(days=30))
        now = datetime.now(timezone.utc)

        result = _maybe_schedule_relance(mock_db, 1, invoice, 30, now)
        assert result is True
