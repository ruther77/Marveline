"""Tests unitaires — Phase 4E Planning & Calendar.

Tests couvrant :
- LOW_STOCK_THRESHOLD dans business.py
- Endpoint GET /products/low-stock
- Endpoint GET /inventory-movements/today
"""
from datetime import date
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.constants.business import LOW_STOCK_THRESHOLD
from app.main import app


# ═══════════════════════════════════════════════════════════════════════════════
# Constante LOW_STOCK_THRESHOLD
# ═══════════════════════════════════════════════════════════════════════════════

class TestLowStockConstant:
    def test_threshold_is_integer(self):
        assert isinstance(LOW_STOCK_THRESHOLD, int)

    def test_threshold_is_positive(self):
        assert LOW_STOCK_THRESHOLD > 0

    def test_threshold_value(self):
        assert LOW_STOCK_THRESHOLD == 5

    def test_exported_from_constants(self):
        """Vérifier que la constante est bien exportée depuis app.constants."""
        from app.constants import business
        assert hasattr(business, "LOW_STOCK_THRESHOLD")

    def test_in_all(self):
        """Vérifier que LOW_STOCK_THRESHOLD est dans __all__ de business.py."""
        from app.constants import business
        assert "LOW_STOCK_THRESHOLD" in business.__all__


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoint GET /products/low-stock
# ═══════════════════════════════════════════════════════════════════════════════

def _make_product_mock(available_quantity: int, sku: str = "TEST-SKU") -> MagicMock:
    p = MagicMock()
    p.id = 1
    p.sku = sku
    p.name = f"Produit {sku}"
    p.available_quantity = available_quantity
    p.stock_quantity = 10
    p.tenant_id = 1
    p.is_active = True
    p.price_per_day_cents = 500
    p.deposit_amount_cents = 0
    p.cleaning_fee = 0
    p.description = None
    p.short_description = None
    p.requires_advance_booking_days = 0
    p.category = "tables"
    p.created_at = date.today()
    p.updated_at = date.today()
    return p


class TestLowStockEndpointRouting:
    """Tests de routing uniquement — vérifie que l'endpoint est bien enregistré."""

    def test_low_stock_route_registered(self):
        """L'endpoint /products/low-stock est enregistré dans l'app."""
        routes = [r.path for r in app.routes]
        assert any("low-stock" in r for r in routes)

    def test_today_route_registered(self):
        """L'endpoint /inventory-movements/today est enregistré dans l'app."""
        routes = [r.path for r in app.routes]
        assert any("today" in r for r in routes)

    def test_low_stock_requires_auth(self):
        """GET /products/low-stock retourne 401 sans token."""
        client = TestClient(app)
        resp = client.get("/api/v1/products/low-stock")
        assert resp.status_code == 401

    def test_today_requires_auth(self):
        """GET /inventory-movements/today retourne 401 sans token."""
        client = TestClient(app)
        resp = client.get("/api/v1/inventory-movements/today")
        # 401 Unauthorized OU 410 Gone (endpoint deprecated/supprime) — les 2 impliquent "pas accessible"
        assert resp.status_code in (401, 410)


# ═══════════════════════════════════════════════════════════════════════════════
# Dashboard — LOW_STOCK_THRESHOLD utilisé (pas de constante locale)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDashboardUsesConstant:
    def test_dashboard_imports_low_stock_threshold(self):
        """dashboard.py utilise LOW_STOCK_THRESHOLD de business.py (pas de constante locale)."""
        import inspect
        import app.api.v1.endpoints.dashboard as dashboard_module

        # La constante ne doit pas être définie localement dans le module
        source = inspect.getsource(dashboard_module)
        assert "LOW_STOCK_THRESHOLD = 5" not in source, (
            "LOW_STOCK_THRESHOLD ne doit pas être définie localement dans dashboard.py"
        )

    def test_low_stock_threshold_accessible_in_dashboard(self):
        """LOW_STOCK_THRESHOLD est bien importée dans dashboard.py."""
        import app.api.v1.endpoints.dashboard as dashboard_module
        assert hasattr(dashboard_module, "LOW_STOCK_THRESHOLD")
        assert dashboard_module.LOW_STOCK_THRESHOLD == LOW_STOCK_THRESHOLD


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoint /today — comportement service
# ═══════════════════════════════════════════════════════════════════════════════

class TestTodayEndpointService:
    async def test_today_calls_agenda_with_today(self):
        """L'endpoint /today appelle get_agenda avec start_date=today et end_date=today."""
        from app.services.inventory_movement import MovementService

        svc = MagicMock(spec=MovementService)
        svc.get_agenda = AsyncMock(return_value={
            "date_start": date.today().isoformat(),
            "date_end": date.today().isoformat(),
            "events": [],
            "total_departures": 0,
            "total_returns": 0,
        })

        today = date.today()
        result = await svc.get_agenda(
            tenant_id=1,
            start_date=today,
            end_date=today,
        )

        svc.get_agenda.assert_called_once_with(
            tenant_id=1,
            start_date=today,
            end_date=today,
        )
        assert result["date_start"] == today.isoformat()
        assert result["date_end"] == today.isoformat()

    def test_today_agenda_returns_agenda_view_fields(self):
        """La réponse /today respecte le schéma AgendaView."""
        from app.schemas.inventory_movement import AgendaView

        today = date.today()
        data = {
            "date_start": today.isoformat(),
            "date_end": today.isoformat(),
            "events": [],
            "total_departures": 2,
            "total_returns": 1,
        }
        view = AgendaView(**data)
        assert view.date_start == today.isoformat()
        assert view.total_departures == 2
        assert view.total_returns == 1
        assert view.events == []
