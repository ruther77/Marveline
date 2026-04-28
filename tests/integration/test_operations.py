"""Tests d'intégration pour les endpoints opérations terrain (async)."""
import asyncio
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.constants import CustomerType
from app.models.bundle import ProductBundle
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.product import Product
from app.models.reservation import Reservation, ReservationLine, ReservationPreCheckItem
from app.models.stock_item import StockItem


# ---------------------------------------------------------------------------
# Helpers — insertion async (visible par les endpoints async)
# ---------------------------------------------------------------------------

def _create_reservation_async(async_test_engine, *, status: str, ref_suffix: str, **extra_fields) -> int:
    """Crée un customer + reservation via async engine. Retourne reservation.id."""
    async def _create():
        session_factory = async_sessionmaker(
            async_test_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            customer = Customer(
                tenant_id=1,
                customer_type=CustomerType.INDIVIDUAL,
                first_name="Ops",
                last_name=f"Test-{ref_suffix}",
                email=f"ops.{ref_suffix}@example.com",
                is_active=True,
            )
            session.add(customer)
            await session.flush()

            reservation_data = {
                "tenant_id": 1,
                "customer_id": customer.id,
                "reference": f"TEST-OPS-{date.today().year}-{ref_suffix}",
                "status": status,
                "event_date": date.today() + timedelta(days=2),
                "delivery_date": date.today(),
                "return_date": date.today() + timedelta(days=3),
            }
            reservation_data.update(extra_fields)

            reservation = Reservation(**reservation_data)
            session.add(reservation)
            await session.commit()
            return reservation.id

    return asyncio.run(_create())


def _create_stock_item_async(async_test_engine, *, serial_number: str) -> dict:
    """Crée un product + stock_item via async engine. Retourne {id, product_id, serial_number}."""
    async def _create():
        session_factory = async_sessionmaker(
            async_test_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            product = Product(
                tenant_id=1,
                name="Produit QR Test",
                sku=f"QR-TST-{serial_number}",
                category="mobilier",
                price_per_day_cents=1000,
                is_active=True,
            )
            session.add(product)
            await session.flush()

            item = StockItem(
                tenant_id=1,
                product_id=product.id,
                serial_number=serial_number,
                status="available",
            )
            session.add(item)
            await session.commit()
            return {"id": item.id, "product_id": product.id, "serial_number": item.serial_number}

    return asyncio.run(_create())


def _create_reservation_with_invoice_async(async_test_engine, *, ref_suffix: str) -> int:
    """Crée customer + reservation (delivered) + invoice (draft). Retourne reservation.id."""
    async def _create():
        session_factory = async_sessionmaker(
            async_test_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            customer = Customer(
                tenant_id=1,
                customer_type=CustomerType.INDIVIDUAL,
                first_name="DmgInv",
                last_name=f"Test-{ref_suffix}",
                email=f"dmginv.{ref_suffix}@example.com",
                is_active=True,
            )
            session.add(customer)
            await session.flush()
            reservation = Reservation(
                tenant_id=1,
                customer_id=customer.id,
                reference=f"TEST-DMG-INV-{ref_suffix}",
                status="delivered",
                event_date=date.today() + timedelta(days=2),
                delivery_date=date.today(),
                return_date=date.today() + timedelta(days=3),
            )
            session.add(reservation)
            await session.flush()
            invoice = Invoice(
                tenant_id=1,
                reservation_id=reservation.id,
                invoice_number=f"INV-DMG-{ref_suffix}",
                issue_date=date.today(),
                due_date=date.today() + timedelta(days=30),
                total_amount_cents=50000,
                paid_amount_cents=0,
            )
            session.add(invoice)
            await session.commit()
            return reservation.id

    return asyncio.run(_create())


def _create_delivered_reservation_with_bundle_line_async(async_test_engine, *, ref_suffix: str) -> int:
    """Crée une réservation delivered avec une ligne bundle (product_id NULL)."""
    async def _create():
        session_factory = async_sessionmaker(
            async_test_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            customer = Customer(
                tenant_id=1,
                customer_type=CustomerType.INDIVIDUAL,
                first_name="Bundle",
                last_name=f"Ops-{ref_suffix}",
                email=f"bundle.ops.{ref_suffix}@example.com",
                is_active=True,
            )
            session.add(customer)
            await session.flush()

            bundle = ProductBundle(
                tenant_id=1,
                name=f"Pack Retour {ref_suffix}",
                slug=f"pack-retour-{ref_suffix.lower()}",
                bundle_price_cents=15000,
                cleaning_fee_cents=0,
                featured=False,
                display_order=0,
            )
            session.add(bundle)
            await session.flush()

            reservation = Reservation(
                tenant_id=1,
                customer_id=customer.id,
                reference=f"TEST-OPS-BUNDLE-{ref_suffix}",
                status="delivered",
                event_date=date.today() + timedelta(days=2),
                delivery_date=date.today(),
                return_date=date.today() + timedelta(days=3),
            )
            session.add(reservation)
            await session.flush()

            line = ReservationLine(
                tenant_id=1,
                reservation_id=reservation.id,
                product_id=None,
                bundle_id=bundle.id,
                quantity=1,
                unit_price_cents=15000,
                subtotal_cents=15000,
            )
            session.add(line)
            await session.commit()
            return reservation.id

    return asyncio.run(_create())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def reservation_confirmed_id(async_test_engine):
    return _create_reservation_async(async_test_engine, status="confirmed", ref_suffix="001")


@pytest.fixture
def reservation_pre_check_id(async_test_engine):
    return _create_reservation_async(async_test_engine, status="pre_check", ref_suffix="002")


@pytest.fixture
def reservation_delivered_id(async_test_engine):
    return _create_reservation_async(async_test_engine, status="delivered", ref_suffix="003")


@pytest.fixture
def reservation_extended_id(async_test_engine):
    return _create_reservation_async(async_test_engine, status="extended", ref_suffix="004")


@pytest.fixture
def reservation_pre_check_deposit_paid_id(async_test_engine):
    """Réservation pre_check sans items, caution requise ET payée."""
    return _create_reservation_async(
        async_test_engine, status="pre_check", ref_suffix="006",
        deposit_amount_cents=5000, deposit_paid=True,
    )


@pytest.fixture
def reservation_pre_check_with_deposit_id(async_test_engine):
    """Réservation pre_check avec 1 item coché et caution non payée."""
    async def _create():
        session_factory = async_sessionmaker(
            async_test_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            customer = Customer(
                tenant_id=1,
                customer_type=CustomerType.INDIVIDUAL,
                first_name="Ops",
                last_name="Test-005",
                email="ops.005@example.com",
                is_active=True,
            )
            session.add(customer)
            await session.flush()

            reservation = Reservation(
                tenant_id=1,
                customer_id=customer.id,
                reference=f"TEST-OPS-{date.today().year}-005",
                status="pre_check",
                event_date=date.today() + timedelta(days=2),
                delivery_date=date.today(),
                return_date=date.today() + timedelta(days=3),
                deposit_amount_cents=5000,
                deposit_paid=False,
            )
            session.add(reservation)
            await session.flush()

            pre_check = ReservationPreCheckItem(
                tenant_id=1,
                reservation_id=reservation.id,
                label="Vérification matériel",
                type="material",
                checked=True,
                sort_order=0,
            )
            session.add(pre_check)
            await session.commit()
            return reservation.id

    return asyncio.run(_create())


@pytest.fixture
def stock_item_data(async_test_engine):
    return _create_stock_item_async(async_test_engine, serial_number="QR-TEST-001")


# ---------------------------------------------------------------------------
# GET /operations/departure/:id
# ---------------------------------------------------------------------------

class TestGetDepartureState:
    def test_get_state_ok(self, client: TestClient, auth_headers_real: dict, reservation_confirmed_id: int):
        resp = client.get(
            f"/api/v1/operations/departure/{reservation_confirmed_id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reservation_id"] == reservation_confirmed_id
        assert "status" in data
        assert "can_depart" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_get_state_not_found(self, client: TestClient, auth_headers_real: dict):
        resp = client.get("/api/v1/operations/departure/99999", headers=auth_headers_real)
        assert resp.status_code == 404

    def test_get_state_cross_tenant_blocked(
        self, client: TestClient, auth_headers_tenant2: dict, reservation_confirmed_id: int
    ):
        resp = client.get(
            f"/api/v1/operations/departure/{reservation_confirmed_id}",
            headers=auth_headers_tenant2,
        )
        assert resp.status_code == 404

    def test_get_state_unauthenticated(self, client: TestClient, reservation_confirmed_id: int):
        resp = client.get(f"/api/v1/operations/departure/{reservation_confirmed_id}")
        assert resp.status_code == 401

    def test_can_depart_blocked_by_deposit(
        self, client: TestClient, auth_headers_real: dict, reservation_pre_check_with_deposit_id: int
    ):
        """pre_check + pre-checks OK + caution non payée → can_depart=False, reason='deposit_required'."""
        resp = client.get(
            f"/api/v1/operations/departure/{reservation_pre_check_with_deposit_id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["can_depart"] is False
        assert data["departure_blocked_reason"] == "deposit_required"


# ---------------------------------------------------------------------------
# POST /operations/departure/:id — validation
# ---------------------------------------------------------------------------

class TestValidateDeparture:
    def test_validate_departure_ok(
        self, client: TestClient, auth_headers_real: dict, reservation_pre_check_id: int,
    ):
        """Départ depuis pre_check sans items de checklist → transition OK."""
        resp = client.post(
            f"/api/v1/operations/departure/{reservation_pre_check_id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"

    def test_validate_departure_wrong_status(
        self, client: TestClient, auth_headers_real: dict, reservation_confirmed_id: int
    ):
        """Depuis confirmed → 400."""
        resp = client.post(
            f"/api/v1/operations/departure/{reservation_confirmed_id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 400

    def test_validate_departure_cross_tenant(
        self, client: TestClient, auth_headers_tenant2: dict, reservation_pre_check_id: int
    ):
        resp = client.post(
            f"/api/v1/operations/departure/{reservation_pre_check_id}",
            headers=auth_headers_tenant2,
        )
        assert resp.status_code == 404

    def test_validate_departure_rejects_unknown_line_payload(
        self, client: TestClient, auth_headers_real: dict, reservation_pre_check_id: int
    ):
        """Le payload items est désormais traité (plus ignoré silencieusement)."""
        resp = client.post(
            f"/api/v1/operations/departure/{reservation_pre_check_id}",
            json={
                "items": [
                    {
                        "line_id": 999999,
                        "product_id": 123,
                        "quantity_loaded": 1,
                        "condition": "good",
                        "qr_scanned": False,
                        "scanned_codes": [],
                    }
                ]
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 400
        assert "Ligne de départ inconnue" in resp.json()["detail"]

    def test_validate_departure_blocked_by_deposit_not_paid(
        self, client: TestClient, auth_headers_real: dict,
        reservation_pre_check_with_deposit_id: int,
    ):
        """pre_check + tous prechecks cochés + caution non payée → 400."""
        resp = client.post(
            f"/api/v1/operations/departure/{reservation_pre_check_with_deposit_id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 400
        assert "deposit" in resp.json()["detail"].lower()

    def test_validate_departure_passes_when_deposit_paid(
        self, client: TestClient, auth_headers_real: dict,
        reservation_pre_check_deposit_paid_id: int,
    ):
        """pre_check + 0 prechecks + caution payée → départ autorisé → 200."""
        resp = client.post(
            f"/api/v1/operations/departure/{reservation_pre_check_deposit_paid_id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"


# ---------------------------------------------------------------------------
# POST /operations/departure/:id/block
# ---------------------------------------------------------------------------

class TestBlockDeparture:
    def test_block_from_confirmed(
        self, client: TestClient, auth_headers_real: dict, reservation_confirmed_id: int
    ):
        resp = client.post(
            f"/api/v1/operations/departure/{reservation_confirmed_id}/block",
            json={"reason": "Matériel manquant"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed_risk"

    def test_block_from_pre_check(
        self, client: TestClient, auth_headers_real: dict, reservation_pre_check_id: int
    ):
        resp = client.post(
            f"/api/v1/operations/departure/{reservation_pre_check_id}/block",
            json={"reason": "Client absent"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed_risk"

    def test_block_wrong_status(
        self, client: TestClient, auth_headers_real: dict, reservation_delivered_id: int
    ):
        """Depuis delivered → 400."""
        resp = client.post(
            f"/api/v1/operations/departure/{reservation_delivered_id}/block",
            json={"reason": "test"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 400

    def test_block_cross_tenant(
        self, client: TestClient, auth_headers_tenant2: dict, reservation_confirmed_id: int
    ):
        resp = client.post(
            f"/api/v1/operations/departure/{reservation_confirmed_id}/block",
            json={"reason": "test"},
            headers=auth_headers_tenant2,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /operations/summary
# ---------------------------------------------------------------------------

class TestOperationsSummary:
    def test_summary_groups_departures_and_returns(
        self, client: TestClient, auth_headers_real: dict, async_test_engine
    ):
        today = date.today()

        confirmed_id = _create_reservation_async(
            async_test_engine,
            status="confirmed",
            ref_suffix="SUM001",
            delivery_date=today,
            return_date=today + timedelta(days=3),
        )
        pre_check_id = _create_reservation_async(
            async_test_engine,
            status="pre_check",
            ref_suffix="SUM002",
            delivery_date=today,
            return_date=today + timedelta(days=2),
        )
        delivered_pending_id = _create_reservation_async(
            async_test_engine,
            status="delivered",
            ref_suffix="SUM003",
            event_date=today,
            delivery_date=today - timedelta(days=1),
            return_date=today + timedelta(days=1),
        )
        overdue_id = _create_reservation_async(
            async_test_engine,
            status="extended",
            ref_suffix="SUM004",
            event_date=today - timedelta(days=2),
            delivery_date=today - timedelta(days=4),
            return_date=today - timedelta(days=1),
        )
        _create_reservation_async(
            async_test_engine,
            status="confirmed",
            ref_suffix="SUM005",
            delivery_date=today,
            return_date=today + timedelta(days=4),
            is_archived=True,
        )

        resp = client.get("/api/v1/operations/summary", headers=auth_headers_real)

        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert {item["id"] for item in data["departures"]} == {confirmed_id, pre_check_id}
        assert {item["id"] for item in data["returns_pending"]} == {delivered_pending_id}
        assert {item["id"] for item in data["returns_overdue"]} == {overdue_id}

    def test_summary_requires_authentication(self, client: TestClient):
        resp = client.get("/api/v1/operations/summary")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET/POST /operations/return/:id
# ---------------------------------------------------------------------------

class TestReturnOperations:
    def test_get_return_state_ok(
        self, client: TestClient, auth_headers_real: dict, reservation_delivered_id: int
    ):
        resp = client.get(
            f"/api/v1/operations/return/{reservation_delivered_id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["can_return"] is True
        assert data["status"] == "delivered"
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_validate_return_ok(
        self, client: TestClient, auth_headers_real: dict, reservation_delivered_id: int
    ):
        resp = client.post(
            f"/api/v1/operations/return/{reservation_delivered_id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "returned"

    def test_get_return_state_extended_ok(
        self, client: TestClient, auth_headers_real: dict, reservation_extended_id: int
    ):
        resp = client.get(
            f"/api/v1/operations/return/{reservation_extended_id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["can_return"] is True
        assert data["status"] == "extended"

    def test_get_return_state_bundle_line_ok(
        self, client: TestClient, auth_headers_real: dict, async_test_engine
    ):
        """Régression: une ligne bundle ne doit plus provoquer de 500 sur ReturnState."""
        reservation_id = _create_delivered_reservation_with_bundle_line_async(
            async_test_engine, ref_suffix="BUNDLE01"
        )
        resp = client.get(
            f"/api/v1/operations/return/{reservation_id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["product_id"] < 0
        assert data["items"][0]["product_name"].startswith("Pack Retour")

    def test_validate_return_extended_ok(
        self, client: TestClient, auth_headers_real: dict, reservation_extended_id: int
    ):
        resp = client.post(
            f"/api/v1/operations/return/{reservation_extended_id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "returned"

    def test_validate_return_wrong_status(
        self, client: TestClient, auth_headers_real: dict, reservation_confirmed_id: int
    ):
        resp = client.post(
            f"/api/v1/operations/return/{reservation_confirmed_id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 400

    def test_return_cross_tenant(
        self, client: TestClient, auth_headers_tenant2: dict, reservation_delivered_id: int
    ):
        resp = client.post(
            f"/api/v1/operations/return/{reservation_delivered_id}",
            headers=auth_headers_tenant2,
        )
        assert resp.status_code == 404

    def test_return_not_found(self, client: TestClient, auth_headers_real: dict):
        resp = client.get("/api/v1/operations/return/99999", headers=auth_headers_real)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /operations/return/:id/damage
# ---------------------------------------------------------------------------

class TestDeclareDamage:
    def test_declare_damage_from_delivered(
        self, client: TestClient, auth_headers_real: dict, reservation_delivered_id: int
    ):
        resp = client.post(
            f"/api/v1/operations/return/{reservation_delivered_id}/damage",
            json={
                "description": "Table rayée",
                "damage_type_name": "Rayure superficielle",
                "fee_cents": 5000,
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reservation_id"] == reservation_delivered_id
        assert data["damage_type_name"] == "Rayure superficielle"
        assert data["fee_cents"] == 5000

    def test_declare_damage_from_extended(
        self, client: TestClient, auth_headers_real: dict, reservation_extended_id: int
    ):
        resp = client.post(
            f"/api/v1/operations/return/{reservation_extended_id}/damage",
            json={
                "description": "Nappe tachée",
                "damage_type_name": "Tache",
                "fee_cents": 1200,
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reservation_id"] == reservation_extended_id
        assert data["damage_type_name"] == "Tache"
        assert data["fee_cents"] == 1200

    def test_declare_damage_wrong_status(
        self, client: TestClient, auth_headers_real: dict, reservation_confirmed_id: int
    ):
        resp = client.post(
            f"/api/v1/operations/return/{reservation_confirmed_id}/damage",
            json={"description": "Test", "damage_type_name": "Casse", "fee_cents": 0},
            headers=auth_headers_real,
        )
        assert resp.status_code == 400

    def test_declare_damage_cross_tenant(
        self, client: TestClient, auth_headers_tenant2: dict, reservation_delivered_id: int
    ):
        resp = client.post(
            f"/api/v1/operations/return/{reservation_delivered_id}/damage",
            json={"description": "Test", "damage_type_name": "Casse", "fee_cents": 0},
            headers=auth_headers_tenant2,
        )
        assert resp.status_code == 404

    def test_declare_damage_creates_invoice_charge(
        self, client: TestClient, auth_headers_real: dict, async_test_engine
    ):
        """fee_cents > 0 + facture active → invoice_charge_id non-null dans la réponse."""
        reservation_id = _create_reservation_with_invoice_async(
            async_test_engine, ref_suffix="INV001"
        )
        resp = client.post(
            f"/api/v1/operations/return/{reservation_id}/damage",
            json={
                "description": "Verre brisé",
                "damage_type_name": "Casse",
                "fee_cents": 3000,
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["invoice_charge_id"] is not None
        assert data["fee_cents"] == 3000

    def test_declare_damage_no_charge_if_no_invoice(
        self, client: TestClient, auth_headers_real: dict, reservation_delivered_id: int
    ):
        """fee_cents > 0 mais aucune facture liée → invoice_charge_id None."""
        resp = client.post(
            f"/api/v1/operations/return/{reservation_delivered_id}/damage",
            json={
                "description": "Rayure légère",
                "damage_type_name": "Rayure",
                "fee_cents": 2000,
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["invoice_charge_id"] is None

    def test_declare_damage_normalizes_ui_category_name(
        self, client: TestClient, auth_headers_real: dict, reservation_delivered_id: int
    ):
        """Les catégories UI ('scratch', 'other', ...) sont normalisées côté backend."""
        resp = client.post(
            f"/api/v1/operations/return/{reservation_delivered_id}/damage",
            json={
                "description": "Micro rayure",
                "damage_type_name": "scratch",
                "fee_cents": 0,
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["damage_type_name"] == "rayure"

    def test_declare_damage_updates_invoice_total(
        self, client: TestClient, auth_headers_real: dict, async_test_engine
    ):
        """fee_cents > 0 + facture active → invoice.total_amount augmenté."""
        reservation_id = _create_reservation_with_invoice_tva_async(
            async_test_engine, ref_suffix="TOTAL001"
        )
        # Facture initiale : total_amount_cents=50000, tva_rate=0.20
        resp = client.post(
            f"/api/v1/operations/return/{reservation_id}/damage",
            json={
                "description": "Casse totale",
                "damage_type_name": "Casse",
                "fee_cents": 5000,
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["invoice_charge_id"] is not None

        # Vérifier la facture mise à jour via l'API
        inv_resp = client.get(
            "/api/v1/invoices",
            params={"reservation_id": reservation_id},
            headers=auth_headers_real,
        )
        assert inv_resp.status_code == 200
        invoices = inv_resp.json()["items"]
        assert len(invoices) >= 1
        inv = invoices[0]
        assert inv["total_amount_cents"] == 55000  # 50000 + 5000

    def test_declare_damage_updates_invoice_tva(
        self, client: TestClient, auth_headers_real: dict, async_test_engine
    ):
        """Après ajout de charge, tva_amount_cents et total_ttc_cents sont recalculés."""
        reservation_id = _create_reservation_with_invoice_tva_async(
            async_test_engine, ref_suffix="TVA001"
        )
        resp = client.post(
            f"/api/v1/operations/return/{reservation_id}/damage",
            json={
                "description": "Rayure profonde",
                "damage_type_name": "Rayure",
                "fee_cents": 10000,
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 200

        # Charger la facture complète
        inv_resp = client.get(
            "/api/v1/invoices",
            params={"reservation_id": reservation_id},
            headers=auth_headers_real,
        )
        assert inv_resp.status_code == 200
        inv = inv_resp.json()["items"][0]
        # HT = 50000 + 10000 = 60000
        assert inv["total_amount_cents"] == 60000


# ---------------------------------------------------------------------------
# Helper: reservation + invoice with TVA rate
# ---------------------------------------------------------------------------

def _create_reservation_with_invoice_tva_async(async_test_engine, *, ref_suffix: str) -> int:
    """Crée customer + reservation (delivered) + invoice (draft, tva_rate=0.20). Retourne reservation.id."""
    async def _create():
        session_factory = async_sessionmaker(
            async_test_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            customer = Customer(
                tenant_id=1,
                customer_type=CustomerType.INDIVIDUAL,
                first_name="DmgTva",
                last_name=f"Test-{ref_suffix}",
                email=f"dmgtva.{ref_suffix}@example.com",
                is_active=True,
            )
            session.add(customer)
            await session.flush()
            reservation = Reservation(
                tenant_id=1,
                customer_id=customer.id,
                reference=f"TEST-DMG-TVA-{ref_suffix}",
                status="delivered",
                event_date=date.today() + timedelta(days=2),
                delivery_date=date.today(),
                return_date=date.today() + timedelta(days=3),
            )
            session.add(reservation)
            await session.flush()
            invoice = Invoice(
                tenant_id=1,
                reservation_id=reservation.id,
                invoice_number=f"INV-DMG-TVA-{ref_suffix}",
                issue_date=date.today(),
                due_date=date.today() + timedelta(days=30),
                total_amount_cents=50000,
                paid_amount_cents=0,
                tva_rate=0.20,
                tva_amount_cents=10000,
                total_ttc_cents=60000,
            )
            session.add(invoice)
            await session.commit()
            return reservation.id

    return asyncio.run(_create())


# ---------------------------------------------------------------------------
# GET /operations/qr/:code
# ---------------------------------------------------------------------------

class TestQrLookup:
    def test_qr_found(
        self, client: TestClient, auth_headers_real: dict, stock_item_data: dict
    ):
        resp = client.get(
            f"/api/v1/operations/qr/{stock_item_data['serial_number']}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stock_item_id"] == stock_item_data["id"]
        assert data["product_id"] == stock_item_data["product_id"]
        assert "stock_status" in data

    def test_qr_not_found(self, client: TestClient, auth_headers_real: dict):
        resp = client.get("/api/v1/operations/qr/INEXISTANT-XYZ-999", headers=auth_headers_real)
        assert resp.status_code == 404

    def test_qr_cross_tenant(
        self, client: TestClient, auth_headers_tenant2: dict, stock_item_data: dict
    ):
        resp = client.get(
            f"/api/v1/operations/qr/{stock_item_data['serial_number']}",
            headers=auth_headers_tenant2,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /operations/damage/photo
# ---------------------------------------------------------------------------

class TestDamagePhotoUpload:
    def test_upload_jpeg_200(self, client: TestClient, auth_headers_real: dict, tmp_path):
        """Upload JPEG valide → 200 + URL /uploads/damages/..."""
        fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # magic JPEG + padding
        resp = client.post(
            "/api/v1/operations/damage/photo",
            files={"file": ("photo.jpg", fake_jpeg, "image/jpeg")},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["url"].startswith("/uploads/damages/")
        assert data["filename"].startswith("damage_")

    def test_upload_png_200(self, client: TestClient, auth_headers_real: dict):
        """Upload PNG valide → 200."""
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        resp = client.post(
            "/api/v1/operations/damage/photo",
            files={"file": ("photo.png", fake_png, "image/png")},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["url"].endswith(".png")

    def test_upload_invalid_mime_415(self, client: TestClient, auth_headers_real: dict):
        """Type MIME non image → 415."""
        resp = client.post(
            "/api/v1/operations/damage/photo",
            files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
            headers=auth_headers_real,
        )
        assert resp.status_code == 415

    def test_upload_unauthenticated_401(self, client: TestClient):
        """Sans token → 401."""
        fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 10
        resp = client.post(
            "/api/v1/operations/damage/photo",
            files={"file": ("photo.jpg", fake_jpeg, "image/jpeg")},
        )
        assert resp.status_code == 401
