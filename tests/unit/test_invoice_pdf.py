"""Tests unitaires — Service génération PDF factures (Phase 4B)."""
import sys
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock

from app.services.invoice_pdf import (
    _cents_to_eur,
    _format_date,
    generate_invoice_pdf,
)
from app.constants.business import (
    ADVANCE_PAYMENT_PERCENT,
    BALANCE_DUE_DAYS_BEFORE_EVENT,
    TVA_RATE,
)


@pytest.fixture(autouse=True)
def mock_weasyprint(monkeypatch):
    """Mock weasyprint dans sys.modules pour éviter l'import réel (non installé en test)."""
    mock = MagicMock()
    monkeypatch.setitem(sys.modules, "weasyprint", mock)
    return mock


# ═══════════════════════════════════════════════════════════════════════════
# Tests fonctions utilitaires (sans DB, sans WeasyPrint)
# ═══════════════════════════════════════════════════════════════════════════

class TestCentsToEur:
    def test_whole_euros(self):
        assert _cents_to_eur(10000) == "100,00 €"

    def test_with_centimes(self):
        assert _cents_to_eur(12345) == "123,45 €"

    def test_zero(self):
        assert _cents_to_eur(0) == "0,00 €"

    def test_small_amount(self):
        assert _cents_to_eur(78) == "0,78 €"

    def test_large_amount(self):
        # 300 000 centimes = 3 000€
        result = _cents_to_eur(300_000)
        assert "3" in result
        assert "000,00" in result


class TestFormatDate:
    def test_format_standard(self):
        assert _format_date(date(2026, 6, 15)) == "15/06/2026"

    def test_format_single_digit_day_month(self):
        assert _format_date(date(2026, 1, 5)) == "05/01/2026"


# ═══════════════════════════════════════════════════════════════════════════
# Tests calculs métier (via generate_invoice_pdf mocké)
# ═══════════════════════════════════════════════════════════════════════════

def _make_mock_invoice(total_amount_cents=50000, paid_amount_cents=0, deposit_amount_cents=150000):
    """Construit un mock Invoice avec relations imbriquées."""
    # Produit
    product = MagicMock()
    product.name = "Assiette plate 28cm"
    product.sku = "ASS-PLATE-28-BR"

    # Ligne de réservation
    line = MagicMock()
    line.product = product
    line.product_id = 1
    line.quantity = 10
    line.unit_price_cents = 5000      # 50€
    line.subtotal_cents = 50000       # 500€

    # Client
    customer = MagicMock()
    customer.first_name = "Jean"
    customer.last_name = "Dupont"
    customer.company_name = None
    customer.address = "12 rue des Fleurs"
    customer.city = "Paris"
    customer.postal_code = "75001"
    customer.email = "jean.dupont@example.com"
    customer.phone = "+33612345678"

    # Réservation
    reservation = MagicMock()
    reservation.reference = "RES-2026-0001"
    reservation.event_date = date(2026, 9, 15)
    reservation.delivery_date = date(2026, 9, 14)
    reservation.return_date = date(2026, 9, 16)
    reservation.event_location = "Salle des Fêtes, Paris"
    reservation.deposit_amount_cents = deposit_amount_cents
    reservation.customer = customer
    reservation.lines = [line]

    # Facture
    invoice = MagicMock()
    invoice.invoice_number = "INV-2026-0001"
    invoice.issue_date = date(2026, 8, 1)
    invoice.due_date = date(2026, 9, 8)   # event_date - 7j
    invoice.status = "sent"
    invoice.total_amount_cents = total_amount_cents
    invoice.paid_amount_cents = paid_amount_cents
    invoice.remaining_amount_cents = total_amount_cents - paid_amount_cents
    invoice.advance_rate = 0.40
    invoice.reservation = reservation
    # Champs TVA (ajoutés phase TVA — None = calcul automatique dans le service)
    invoice.tva_amount_cents = None
    invoice.total_ttc_cents = None
    invoice.tva_breakdown = None
    invoice.tva_rate = None

    return invoice


def _get_html_string(mock_weasyprint: MagicMock) -> str:
    """Extrait le HTML passé à HTML(string=...) depuis le mock."""
    call_kwargs = mock_weasyprint.HTML.call_args
    assert call_kwargs is not None, "HTML() n'a pas été appelé"
    # Peut être passé comme arg positionnel ou kwarg
    if call_kwargs.kwargs.get("string"):
        return call_kwargs.kwargs["string"]
    if call_kwargs.args:
        return call_kwargs.args[0]
    return ""


class TestGenerateInvoicePdf:
    """Tests génération PDF — WeasyPrint mocké via sys.modules."""

    def test_returns_bytes(self, mock_weasyprint):
        """generate_invoice_pdf retourne des bytes."""
        invoice = _make_mock_invoice()
        fake_pdf = b"%PDF-1.4 fake content"
        mock_weasyprint.HTML.return_value.write_pdf.return_value = fake_pdf

        result = generate_invoice_pdf(invoice)

        assert isinstance(result, bytes)
        assert result == fake_pdf

    def test_html_called_with_string(self, mock_weasyprint):
        """HTML() est bien appelé avec le rendu du template."""
        invoice = _make_mock_invoice()
        mock_weasyprint.HTML.return_value.write_pdf.return_value = b"%PDF"

        generate_invoice_pdf(invoice)

        html_str = _get_html_string(mock_weasyprint)
        assert "INV-2026-0001" in html_str

    def test_template_contains_customer_name(self, mock_weasyprint):
        """Le HTML rendu contient le nom du client."""
        invoice = _make_mock_invoice()
        mock_weasyprint.HTML.return_value.write_pdf.return_value = b"%PDF"

        generate_invoice_pdf(invoice)

        html_str = _get_html_string(mock_weasyprint)
        assert "Jean Dupont" in html_str

    def test_template_contains_reservation_reference(self, mock_weasyprint):
        """Le HTML rendu contient la référence réservation."""
        invoice = _make_mock_invoice()
        mock_weasyprint.HTML.return_value.write_pdf.return_value = b"%PDF"

        generate_invoice_pdf(invoice)

        html_str = _get_html_string(mock_weasyprint)
        assert "RES-2026-0001" in html_str

    def test_template_contains_ttc_amount(self, mock_weasyprint):
        """Le HTML rendu contient le montant TTC formaté."""
        invoice = _make_mock_invoice(total_amount_cents=50000)  # 500€
        mock_weasyprint.HTML.return_value.write_pdf.return_value = b"%PDF"

        generate_invoice_pdf(invoice)

        html_str = _get_html_string(mock_weasyprint)
        assert "500,00" in html_str

    def test_advance_is_40_percent(self, mock_weasyprint):
        """L'acompte calculé est bien 40% du TTC (HT + TVA 20%)."""
        total = 100000  # HT = 1 000€ → TTC = 1 200€ → acompte = 480€
        invoice = _make_mock_invoice(total_amount_cents=total)
        mock_weasyprint.HTML.return_value.write_pdf.return_value = b"%PDF"

        generate_invoice_pdf(invoice)

        html_str = _get_html_string(mock_weasyprint)
        assert "480,00" in html_str  # 40% × TTC(1 200€) = 480€

    def test_balance_due_date_is_7_days_before_event(self, mock_weasyprint):
        """La date d'échéance du solde est event_date - 7 jours."""
        invoice = _make_mock_invoice()
        # event_date = 2026-09-15 → balance_due = 2026-09-08
        mock_weasyprint.HTML.return_value.write_pdf.return_value = b"%PDF"

        generate_invoice_pdf(invoice)

        html_str = _get_html_string(mock_weasyprint)
        assert "08/09/2026" in html_str

    def test_company_customer_name(self, mock_weasyprint):
        """Client entreprise (company_name) → raison sociale utilisée."""
        invoice = _make_mock_invoice()
        invoice.reservation.customer.first_name = None
        invoice.reservation.customer.last_name = None
        invoice.reservation.customer.company_name = "ACME SAS"
        mock_weasyprint.HTML.return_value.write_pdf.return_value = b"%PDF"

        generate_invoice_pdf(invoice)

        html_str = _get_html_string(mock_weasyprint)
        assert "ACME SAS" in html_str

    def test_paid_amount_shown_when_nonzero(self, mock_weasyprint):
        """Le montant payé apparaît dans le template si > 0."""
        invoice = _make_mock_invoice(total_amount_cents=50000, paid_amount_cents=20000)
        invoice.remaining_amount_cents = 30000
        mock_weasyprint.HTML.return_value.write_pdf.return_value = b"%PDF"

        generate_invoice_pdf(invoice)

        html_str = _get_html_string(mock_weasyprint)
        assert "200,00" in html_str  # paid_amount 200€

    def test_tva_calculation(self, mock_weasyprint):
        """TVA = HT × TVA_RATE ; total_amount représente le HT."""
        total_ht = 10000  # HT = 100€ → TVA = 20€ → TTC = 120€
        invoice = _make_mock_invoice(total_amount_cents=total_ht)
        mock_weasyprint.HTML.return_value.write_pdf.return_value = b"%PDF"

        generate_invoice_pdf(invoice)

        html_str = _get_html_string(mock_weasyprint)
        assert "100,00" in html_str  # montant HT = 100€

    def test_no_reservation_raises_value_error(self, mock_weasyprint):
        """Facture sans réservation → ValueError explicite."""
        invoice = _make_mock_invoice()
        invoice.reservation = None
        invoice.id = 42

        with pytest.raises(ValueError, match="pas liée à une réservation"):
            generate_invoice_pdf(invoice)

    def test_no_customer_raises_value_error(self, mock_weasyprint):
        """Réservation sans client → ValueError explicite."""
        invoice = _make_mock_invoice()
        invoice.reservation.customer = None
        invoice.reservation.id = 7

        with pytest.raises(ValueError, match="pas de client associé"):
            generate_invoice_pdf(invoice)
