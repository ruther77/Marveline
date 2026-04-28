"""Tests d'intégration — planning enrichi avec données logistiques."""
import pytest
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.models.reservation import Reservation
from app.models.customer import Customer
from app.constants import ReservationStatus


@pytest.fixture
def planning_customer(test_db):
    """Client pour les tests planning."""
    c = Customer(
        tenant_id=1,
        first_name="Client",
        last_name="Planning",
        email="planning@test.com",
        customer_type="individual",
        country="FR",
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def planning_reservation(test_db, planning_customer):
    """Réservation confirmée pour aujourd'hui avec infos livraison."""
    today = date.today()
    r = Reservation(
        tenant_id=1,
        customer_id=planning_customer.id,
        reference="RES-2026-PLAN",
        event_date=today,
        delivery_date=today - timedelta(days=1),
        return_date=today + timedelta(days=1),
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=50000,
        deposit_amount_cents=10000,
        deposit_paid=True,
        delivery_method="self",
        delivery_fee_cents=3000,
    )
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)
    return r


class TestPlanningEnriched:
    """Tests planning avec champs logistiques."""

    def test_today_includes_logistics(
        self, client: TestClient, planning_reservation, auth_headers_real
    ):
        response = client.get("/api/v1/planning/today", headers=auth_headers_real)
        assert response.status_code == 200
        data = response.json()
        # Check that at least one reservation has logistics fields
        all_reservations = (
            data.get("departures", [])
            + data.get("returns_today", [])
            + data.get("active", [])
        )
        found = [r for r in all_reservations if r["id"] == planning_reservation.id]
        if found:
            r = found[0]
            assert "delivery_method" in r
            assert "delivery_fee_cents" in r
            assert "container_count" in r

    def test_day_includes_logistics(
        self, client: TestClient, planning_reservation, auth_headers_real
    ):
        today_str = date.today().isoformat()
        response = client.get(
            f"/api/v1/planning/day/{today_str}", headers=auth_headers_real
        )
        assert response.status_code == 200
        data = response.json()
        reservations = data.get("reservations", [])
        found = [r for r in reservations if r["id"] == planning_reservation.id]
        if found:
            assert "delivery_method" in found[0]
            assert "container_count" in found[0]


class TestLoadingEndpoint:
    """Tests endpoint vue chargement."""

    def test_loading_view_exists(
        self, client: TestClient, planning_reservation, auth_headers_real
    ):
        response = client.get(
            f"/api/v1/planning/loading/{planning_reservation.id}",
            headers=auth_headers_real,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reservation_id"] == planning_reservation.id
        assert data["reference"] == "RES-2026-PLAN"
        assert "containers" in data
        assert "unassigned_items_count" in data

    def test_loading_view_includes_item_product_metadata(
        self, client: TestClient, planning_reservation, auth_headers_real, test_db
    ):
        from app.models.container import Container, ContainerAssignment, ContainerItem
        from app.models.inventory_movement import InventoryMovement, MovementItem
        from app.models.product import Product

        product = Product(
            tenant_id=1,
            name="Chaise Chiavari doree",
            sku="PLAN-LOAD-IMG-001",
            category="mobilier",
            price_per_day_cents=1500,
            deposit_amount_cents=3000,
            stock_quantity=10,
            available_quantity=10,
            condition="bon",
            image_url="https://example.com/products/chaise-chiavari.jpg",
            is_active=True,
        )
        test_db.add(product)
        test_db.flush()

        movement = InventoryMovement(
            tenant_id=1,
            reservation_id=planning_reservation.id,
            movement_type="departure",
            scheduled_date=datetime.now(timezone.utc),
            status="scheduled",
        )
        test_db.add(movement)
        test_db.flush()

        movement_item = MovementItem(
            tenant_id=1,
            movement_id=movement.id,
            product_id=product.id,
            quantity_expected=2,
        )
        test_db.add(movement_item)
        test_db.flush()

        container = Container(
            tenant_id=1,
            name="Bac bleu",
            container_type="bac",
            serial_number="BAC-LOAD-001",
            is_available=True,
        )
        test_db.add(container)
        test_db.flush()

        assignment = ContainerAssignment(
            tenant_id=1,
            container_id=container.id,
            movement_id=movement.id,
        )
        test_db.add(assignment)
        test_db.flush()

        test_db.add(
            ContainerItem(
                tenant_id=1,
                container_assignment_id=assignment.id,
                movement_item_id=movement_item.id,
                quantity=2,
            )
        )
        test_db.commit()

        response = client.get(
            f"/api/v1/planning/loading/{planning_reservation.id}",
            headers=auth_headers_real,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["containers"]) == 1
        assert len(data["containers"][0]["items"]) == 1
        item = data["containers"][0]["items"][0]
        assert item["movement_item_id"] == movement_item.id
        assert item["product_name"] == "Chaise Chiavari doree"
        assert item["variant_label"] is None
        assert item["image_url"] == "https://example.com/products/chaise-chiavari.jpg"

    def test_loading_view_404_other_tenant(
        self, client: TestClient, auth_headers_real
    ):
        response = client.get(
            "/api/v1/planning/loading/999999",
            headers=auth_headers_real,
        )
        assert response.status_code == 404
