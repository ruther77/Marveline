"""Tests unitaires — service printer ESC/POS (formatage ticket)."""
import pytest

from app.services.printer import (
    TicketData,
    TicketLine,
    TvaBreakdown,
    build_ticket_bytes,
    _fmt_cts,
    _line_two_cols,
    CMD_INIT,
    CMD_CUT,
    CMD_KICK_DRAWER,
    CMD_BOLD_ON,
    PAPER_WIDTH_CHARS,
)


class TestFmtCts:
    """Formatage centimes → euros."""

    def test_zero(self):
        assert _fmt_cts(0) == "0,00"

    def test_round(self):
        assert _fmt_cts(1250) == "12,50"

    def test_large(self):
        result = _fmt_cts(123456)
        assert "1" in result
        assert ",56" in result


class TestLineTwoCols:
    """Alignement deux colonnes."""

    def test_basic(self):
        line = _line_two_cols("Assiette", "12,50")
        assert len(line) == PAPER_WIDTH_CHARS
        assert line.startswith("Assiette")
        assert line.endswith("12,50")

    def test_truncate_long_left(self):
        line = _line_two_cols("A" * 50, "5,00")
        assert line.endswith("5,00")
        assert len(line) == PAPER_WIDTH_CHARS


class TestBuildTicketBytes:
    """Construction bytes ESC/POS."""

    def test_init_command_present(self):
        data = TicketData(
            nom_commerce="Test",
            lignes=[TicketLine("Cafe", 1, 250, 250)],
            total_ttc_cts=250,
        )
        raw = build_ticket_bytes(data)
        assert raw.startswith(CMD_INIT)

    def test_cut_at_end(self):
        data = TicketData(
            lignes=[TicketLine("Item", 1, 100, 100)],
            total_ttc_cts=100,
        )
        raw = build_ticket_bytes(data)
        assert CMD_CUT in raw

    def test_bold_for_commerce_name(self):
        data = TicketData(
            nom_commerce="Chez Marcel",
            lignes=[],
            total_ttc_cts=0,
        )
        raw = build_ticket_bytes(data)
        assert CMD_BOLD_ON in raw

    def test_tiroir_when_ouvrir_true(self):
        data = TicketData(
            lignes=[TicketLine("Item", 1, 100, 100)],
            total_ttc_cts=100,
            ouvrir_tiroir=True,
        )
        raw = build_ticket_bytes(data)
        assert CMD_KICK_DRAWER in raw

    def test_no_tiroir_when_false(self):
        data = TicketData(
            lignes=[TicketLine("Item", 1, 100, 100)],
            total_ttc_cts=100,
            ouvrir_tiroir=False,
        )
        raw = build_ticket_bytes(data)
        assert CMD_KICK_DRAWER not in raw

    def test_tva_breakdown(self):
        data = TicketData(
            lignes=[TicketLine("Plat", 1, 1000, 1000)],
            sous_total_ht_cts=833,
            tva_breakdown=[TvaBreakdown("10%", 833, 83)],
            total_ttc_cts=1000,
        )
        raw = build_ticket_bytes(data)
        decoded = raw.decode("cp858", errors="replace")
        assert "10%" in decoded

    def test_multiple_lignes(self):
        data = TicketData(
            lignes=[
                TicketLine("Entree", 2, 500, 1000),
                TicketLine("Plat", 1, 1500, 1500),
                TicketLine("Dessert", 1, 700, 700),
            ],
            total_ttc_cts=3200,
        )
        raw = build_ticket_bytes(data)
        decoded = raw.decode("cp858", errors="replace")
        assert "Entree" in decoded
        assert "Plat" in decoded
        assert "Dessert" in decoded
        assert "2 x" in decoded  # quantite > 1

    def test_qr_code_section(self):
        data = TicketData(
            lignes=[TicketLine("Item", 1, 100, 100)],
            total_ttc_cts=100,
            qr_url="https://example.com/receipt/123",
        )
        raw = build_ticket_bytes(data)
        # QR code uses GS ( k command
        assert b'\x1d\x28\x6b' in raw or b'example.com' in raw

    def test_numero_ticket_in_output(self):
        data = TicketData(
            lignes=[TicketLine("Item", 1, 100, 100)],
            total_ttc_cts=100,
            numero_ticket="CMD-42",
        )
        raw = build_ticket_bytes(data)
        decoded = raw.decode("cp858", errors="replace")
        assert "CMD-42" in decoded
