"""Tests d'intégration : workflow Reservation -> InventoryMovement.

Couvre :
- Confirmation d'une reservation auto-cree un mouvement DEPARTURE (scheduled)
- Items du mouvement = lignes de la reservation
- Idempotence : confirmer 2x ne cree pas de doublon mouvement
- Completer DEPARTURE -> reservation passe a "delivered"
- Completer RETURN -> reservation passe a "returned"
- Mouvement sans reservation_id -> aucun changement reservation
- Cross-tenant isolation sur les mouvements
- Filtre reservation_id sur GET /inventory-movements
- Workflow complet end-to-end
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.models.customer import Customer
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.constants import CustomerType, ProductCategory, ProductCondition


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def customer_mv(test_db):
    """Client de test pour workflow reservation -> movement."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Sophie",
        last_name="Bernard",
        email="sophie.bernard@mvworkflow.com",
        phone="+33611223344",
        city="Paris",
        postal_code="75001",
        is_active=True,
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture
def product_mv(test_db):
    """Produit de test pour workflow reservation -> movement."""
    product = Product(
        tenant_id=1,
        name="Table ronde 180cm",
        sku="TABLE-MV-001",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=2000,  # 20 EUR/jour
        deposit_amount_cents=5000,  # 50 EUR caution
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def variant_mv(test_db, product_mv):
    """Variante standard pour product_mv."""
    variant = ProductVariant(
        tenant_id=1,
        product_id=product_mv.id,
        label="Standard",
        sku=f"STD-{product_mv.id}",
        price_per_day_cents=product_mv.price_per_day_cents,
        deposit_amount_cents=product_mv.deposit_amount_cents,
        stock_quantity=product_mv.stock_quantity,
        available_quantity=product_mv.available_quantity,
        is_active=True,
    )
    test_db.add(variant)
    test_db.commit()
    test_db.refresh(variant)
    return variant


@pytest.fixture
def product_mv_2(test_db):
    """Second produit pour tester multi-items."""
    product = Product(
        tenant_id=1,
        name="Chaise pliante",
        sku="CHAISE-MV-001",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=500,  # 5 EUR/jour
        deposit_amount_cents=1000,  # 10 EUR caution
        stock_quantity=50,
        available_quantity=50,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def variant_mv_2(test_db, product_mv_2):
    """Variante standard pour product_mv_2."""
    variant = ProductVariant(
        tenant_id=1,
        product_id=product_mv_2.id,
        label="Standard",
        sku=f"STD-{product_mv_2.id}",
        price_per_day_cents=product_mv_2.price_per_day_cents,
        deposit_amount_cents=product_mv_2.deposit_amount_cents,
        stock_quantity=product_mv_2.stock_quantity,
        available_quantity=product_mv_2.available_quantity,
        is_active=True,
    )
    test_db.add(variant)
    test_db.commit()
    test_db.refresh(variant)
    return variant


@pytest.fixture
def customer_mv_t2(test_db):
    """Client tenant 2 pour cross-tenant tests."""
    customer = Customer(
        tenant_id=2,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Pierre",
        last_name="Durand",
        email="pierre.durand@tenant2mv.com",
        phone="+33655443322",
        city="Toulouse",
        postal_code="31000",
        is_active=True,
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture
def product_mv_t2(test_db):
    """Produit tenant 2 pour cross-tenant tests."""
    product = Product(
        tenant_id=2,
        name="Buffet bois",
        sku="BUFFET-T2-001",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=3000,
        deposit_amount_cents=8000,
        stock_quantity=5,
        available_quantity=5,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def variant_mv_t2(test_db, product_mv_t2):
    """Variante standard pour product_mv_t2."""
    variant = ProductVariant(
        tenant_id=2,
        product_id=product_mv_t2.id,
        label="Standard",
        sku=f"STD-{product_mv_t2.id}",
        price_per_day_cents=product_mv_t2.price_per_day_cents,
        deposit_amount_cents=product_mv_t2.deposit_amount_cents,
        stock_quantity=product_mv_t2.stock_quantity,
        available_quantity=product_mv_t2.available_quantity,
        is_active=True,
    )
    test_db.add(variant)
    test_db.commit()
    test_db.refresh(variant)
    return variant


# ============================================================
# Helpers
# ============================================================

def _create_reservation(client, customer_id, product_ids_quantities, headers):
    """Helper : cree une reservation draft via API.

    Args:
        product_ids_quantities: list of (product_id, variant_id, quantity)
    """
    lines = [
        {"product_id": pid, "variant_id": vid, "quantity": qty}
        for pid, vid, qty in product_ids_quantities
    ]
    data = {
        "customer_id": customer_id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Salle des fetes Paris",
        "lines": lines,
    }
    resp = client.post("/api/v1/reservations", json=data, headers=headers)
    assert resp.status_code == 201, f"Create reservation failed: {resp.json()}"
    return resp.json()


def _confirm_reservation(client, reservation_id, headers):
    """Helper : confirme une reservation via API."""
    resp = client.post(
        f"/api/v1/reservations/{reservation_id}/confirm",
        headers=headers,
    )
    return resp


def _get_movements_for_reservation(client, reservation_id, headers):
    """Helper : liste les mouvements lies a une reservation."""
    resp = client.get(
        f"/api/v1/inventory-movements?reservation_id={reservation_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()


def _prepare_departure_ready(test_db, reservation_id: int) -> None:
    """Prépare une réservation pour le départ via Operations."""
    result = test_db.execute(text(
        "UPDATE reservation_pre_check_items SET checked = true "
        "WHERE reservation_id = :rid AND tenant_id = 1"
    ), {"rid": reservation_id})
    assert result.rowcount > 0, "Pre-check items should have been auto-created"
    test_db.execute(text(
        "UPDATE reservations SET deposit_paid = true "
        "WHERE id = :rid AND tenant_id = 1"
    ), {"rid": reservation_id})
    test_db.commit()


# ============================================================
# Test : confirmation auto-cree mouvement DEPARTURE
# ============================================================

class TestConfirmCreatesDepartureMovement:
    """Confirmer une reservation auto-genere un mouvement DEPARTURE."""

    def test_confirm_creates_departure_movement(
        self, client: TestClient, test_db,
        customer_mv, product_mv, variant_mv, auth_headers_real,
    ):
        """POST /reservations/{id}/confirm -> mouvement DEPARTURE auto-cree."""
        res_data = _create_reservation(
            client, customer_mv.id, [(product_mv.id, variant_mv.id, 3)], auth_headers_real,
        )
        reservation_id = res_data["id"]

        # Confirmer
        confirm_resp = _confirm_reservation(client, reservation_id, auth_headers_real)
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["status"] == "pre_check"

        # Verifier mouvement DEPARTURE cree
        mv_data = _get_movements_for_reservation(client, reservation_id, auth_headers_real)
        assert mv_data["total"] == 1

        movement = mv_data["items"][0]
        assert movement["movement_type"] == "departure"
        assert movement["reservation_id"] == reservation_id

    def test_departure_movement_items_match_reservation_lines(
        self, client: TestClient, test_db,
        customer_mv, product_mv, variant_mv, product_mv_2, variant_mv_2, auth_headers_real,
    ):
        """Les items du mouvement correspondent aux lignes de reservation."""
        res_data = _create_reservation(
            client,
            customer_mv.id,
            [(product_mv.id, variant_mv.id, 2), (product_mv_2.id, variant_mv_2.id, 5)],
            auth_headers_real,
        )
        reservation_id = res_data["id"]

        _confirm_reservation(client, reservation_id, auth_headers_real)

        # Recuperer mouvement avec ses items via GET detail
        mv_list = _get_movements_for_reservation(client, reservation_id, auth_headers_real)
        movement_id = mv_list["items"][0]["id"]

        detail_resp = client.get(
            f"/api/v1/inventory-movements/{movement_id}",
            headers=auth_headers_real,
        )
        assert detail_resp.status_code == 200
        detail = detail_resp.json()

        # Verifier items
        items = detail["items"]
        assert len(items) == 2

        items_by_product = {item["product_id"]: item for item in items}
        assert items_by_product[product_mv.id]["quantity_expected"] == 2
        assert items_by_product[product_mv_2.id]["quantity_expected"] == 5

    def test_confirm_idempotent_no_duplicate_movement(
        self, client: TestClient, test_db,
        customer_mv, product_mv, variant_mv, auth_headers_real,
    ):
        """Confirmer 2x ne cree pas de doublon mouvement."""
        res_data = _create_reservation(
            client, customer_mv.id, [(product_mv.id, variant_mv.id, 1)], auth_headers_real,
        )
        reservation_id = res_data["id"]

        # Premiere confirmation -> OK
        resp1 = _confirm_reservation(client, reservation_id, auth_headers_real)
        assert resp1.status_code == 200

        # Deuxieme confirmation -> 400 (status != draft)
        resp2 = _confirm_reservation(client, reservation_id, auth_headers_real)
        assert resp2.status_code == 400

        # Toujours un seul mouvement
        mv_data = _get_movements_for_reservation(client, reservation_id, auth_headers_real)
        assert mv_data["total"] == 1


# ============================================================
# Test : completion mouvement met a jour reservation
# ============================================================

class TestMovementCompletionUpdatesReservation:
    """Completer un mouvement lie via Operations met a jour le statut reservation."""

    def _get_reservation(self, client, reservation_id, headers):
        resp = client.get(f"/api/v1/reservations/{reservation_id}", headers=headers)
        assert resp.status_code == 200
        return resp.json()

    def _check_all_prechecks(self, client, reservation_id, headers):
        """Coche tous les pre-check items via GET departure state."""
        from app.models.reservation import ReservationPreCheckItem
        from tests.conftest import _test_db_session_factory
        # On utilise l'API operations pour obtenir l'etat
        state = client.get(
            f"/api/v1/operations/departure/{reservation_id}",
            headers=headers,
        )
        assert state.status_code == 200
        return state.json()

    def test_direct_complete_linked_movement_returns_409(
        self, client: TestClient, test_db,
        customer_mv, product_mv, variant_mv, auth_headers_real, auth_headers_admin,
    ):
        """complete_movement sur mouvement lie a reservation -> 409."""
        res_data = _create_reservation(
            client, customer_mv.id, [(product_mv.id, variant_mv.id, 2)], auth_headers_real,
        )
        reservation_id = res_data["id"]
        _confirm_reservation(client, reservation_id, auth_headers_real)

        mv_data = _get_movements_for_reservation(client, reservation_id, auth_headers_admin)
        departure_id = mv_data["items"][0]["id"]

        # Passer in_transit
        transit_resp = client.patch(
            f"/api/v1/inventory-movements/{departure_id}",
            json={"status": "in_transit"},
            headers=auth_headers_admin,
        )
        assert transit_resp.status_code == 200

        # Tenter complete_movement directement -> 409
        complete_resp = client.patch(
            f"/api/v1/inventory-movements/{departure_id}/complete",
            headers=auth_headers_admin,
        )
        assert complete_resp.status_code == 409
        assert "reservation" in complete_resp.json()["detail"].lower()

    def test_operations_departure_delivers_reservation(
        self, client: TestClient, test_db,
        customer_mv, product_mv, variant_mv, auth_headers_real, auth_headers_admin,
    ):
        """Operations validate_departure -> reservation 'delivered' + mouvement 'completed'."""
        res_data = _create_reservation(
            client, customer_mv.id, [(product_mv.id, variant_mv.id, 2)], auth_headers_real,
        )
        reservation_id = res_data["id"]
        _confirm_reservation(client, reservation_id, auth_headers_real)

        _prepare_departure_ready(test_db, reservation_id)

        # Valider depart via Operations
        dep_resp = client.post(
            f"/api/v1/operations/departure/{reservation_id}",
            headers=auth_headers_admin,
        )
        assert dep_resp.status_code == 200
        assert dep_resp.json()["status"] == "delivered"

        # Verifier reservation
        res = self._get_reservation(client, reservation_id, auth_headers_real)
        assert res["status"] == "delivered"

        # Verifier mouvement DEPARTURE complete
        mv_data = _get_movements_for_reservation(client, reservation_id, auth_headers_admin)
        departure = mv_data["items"][0]
        assert departure["status"] == "completed"

    def test_operations_return_returns_reservation(
        self, client: TestClient, test_db,
        customer_mv, product_mv, variant_mv, auth_headers_real, auth_headers_admin,
    ):
        """Operations validate_return -> reservation 'returned' + mouvement RETURN 'completed'."""
        from datetime import datetime, timezone

        res_data = _create_reservation(
            client, customer_mv.id, [(product_mv.id, variant_mv.id, 2)], auth_headers_real,
        )
        reservation_id = res_data["id"]
        _confirm_reservation(client, reservation_id, auth_headers_real)

        _prepare_departure_ready(test_db, reservation_id)

        dep_resp = client.post(
            f"/api/v1/operations/departure/{reservation_id}",
            headers=auth_headers_admin,
        )
        assert dep_resp.status_code == 200

        # Creer mouvement RETURN
        return_resp = client.post(
            "/api/v1/inventory-movements",
            json={
                "movement_type": "return",
                "scheduled_date": datetime.now(timezone.utc).isoformat(),
                "reservation_id": reservation_id,
                "items": [
                    {"product_id": product_mv.id, "variant_id": variant_mv.id, "quantity_expected": 2},
                ],
            },
            headers=auth_headers_admin,
        )
        assert return_resp.status_code == 201

        # Valider retour via Operations
        ret_resp = client.post(
            f"/api/v1/operations/return/{reservation_id}",
            headers=auth_headers_admin,
        )
        assert ret_resp.status_code == 200
        assert ret_resp.json()["status"] == "returned"

        # Verifier reservation
        res = self._get_reservation(client, reservation_id, auth_headers_real)
        assert res["status"] == "returned"

    def test_complete_unlinked_movement_no_reservation_change(
        self, client: TestClient, test_db,
        customer_mv, product_mv, variant_mv, auth_headers_admin,
    ):
        """Mouvement sans reservation_id -> completion directe OK."""
        from datetime import datetime, timezone
        mv_resp = client.post(
            "/api/v1/inventory-movements",
            json={
                "movement_type": "departure",
                "scheduled_date": datetime.now(timezone.utc).isoformat(),
                "items": [
                    {"product_id": product_mv.id, "variant_id": variant_mv.id, "quantity_expected": 1},
                ],
            },
            headers=auth_headers_admin,
        )
        assert mv_resp.status_code == 201
        movement_id = mv_resp.json()["id"]
        assert mv_resp.json()["reservation_id"] is None

        transit_resp = client.patch(
            f"/api/v1/inventory-movements/{movement_id}",
            json={"status": "in_transit"},
            headers=auth_headers_admin,
        )
        assert transit_resp.status_code == 200
        complete_resp = client.patch(
            f"/api/v1/inventory-movements/{movement_id}/complete",
            headers=auth_headers_admin,
        )
        assert complete_resp.status_code == 200


# ============================================================
# Test : cross-tenant isolation
# ============================================================

class TestCrossTenantIsolation:
    """Les mouvements auto-generes respectent l'isolation tenant."""

    def test_tenant2_cannot_see_tenant1_movements(
        self, client: TestClient, test_db,
        customer_mv, product_mv, variant_mv,
        customer_mv_t2, product_mv_t2, variant_mv_t2,
        auth_headers_real, auth_headers_tenant2,
    ):
        """Tenant2 ne voit pas les mouvements auto-generes pour tenant1."""
        # Tenant1 : creer et confirmer
        res_data = _create_reservation(
            client, customer_mv.id, [(product_mv.id, variant_mv.id, 1)], auth_headers_real,
        )
        _confirm_reservation(client, res_data["id"], auth_headers_real)

        # Tenant1 voit son mouvement
        mv_t1 = _get_movements_for_reservation(client, res_data["id"], auth_headers_real)
        assert mv_t1["total"] == 1

        # Tenant2 ne voit PAS le mouvement de tenant1
        mv_t2 = _get_movements_for_reservation(client, res_data["id"], auth_headers_tenant2)
        assert mv_t2["total"] == 0

    def test_list_movements_filter_by_reservation_id(
        self, client: TestClient, test_db,
        customer_mv, product_mv, variant_mv, auth_headers_real,
    ):
        """Filtre reservation_id fonctionne correctement."""
        # Creer 2 reservations
        res1 = _create_reservation(
            client, customer_mv.id, [(product_mv.id, variant_mv.id, 1)], auth_headers_real,
        )
        res2 = _create_reservation(
            client, customer_mv.id, [(product_mv.id, variant_mv.id, 1)], auth_headers_real,
        )

        _confirm_reservation(client, res1["id"], auth_headers_real)
        _confirm_reservation(client, res2["id"], auth_headers_real)

        # Filtre par reservation_id=res1
        mv1 = _get_movements_for_reservation(client, res1["id"], auth_headers_real)
        assert mv1["total"] == 1
        assert mv1["items"][0]["reservation_id"] == res1["id"]

        # Filtre par reservation_id=res2
        mv2 = _get_movements_for_reservation(client, res2["id"], auth_headers_real)
        assert mv2["total"] == 1
        assert mv2["items"][0]["reservation_id"] == res2["id"]


# ============================================================
# Test : workflow complet end-to-end
# ============================================================

class TestFullWorkflow:
    """Workflow complet via Operations : reservation -> confirm -> pre_check -> deliver -> return."""

    def test_complete_rental_via_operations(
        self, client: TestClient, test_db,
        customer_mv, product_mv, variant_mv, auth_headers_real, auth_headers_admin,
    ):
        """Workflow complet : create -> confirm (auto-facture + auto-mouvement + pre_check)
        -> validate_departure (delivered) -> create RETURN -> validate_return (returned)."""
        from datetime import datetime, timezone

        # 1. Creer reservation
        res_data = _create_reservation(
            client, customer_mv.id, [(product_mv.id, variant_mv.id, 3)], auth_headers_real,
        )
        reservation_id = res_data["id"]
        assert res_data["status"] == "draft"

        # 2. Confirmer -> auto-facture + auto-mouvement DEPARTURE + auto PRE_CHECK
        confirm_resp = _confirm_reservation(client, reservation_id, auth_headers_real)
        assert confirm_resp.status_code == 200
        # Reservation passe a pre_check (auto-transition apres confirmed)
        assert confirm_resp.json()["status"] == "pre_check"

        # Verifier facture unique (full)
        invoices = client.get(
            f"/api/v1/invoices?reservation_id={reservation_id}",
            headers=auth_headers_real,
        ).json()
        assert invoices["total"] == 1

        # Verifier mouvement DEPARTURE
        mv_data = _get_movements_for_reservation(client, reservation_id, auth_headers_admin)
        assert mv_data["total"] == 1
        assert mv_data["items"][0]["movement_type"] == "departure"

        # Verifier pre-check items auto-crees (raw SQL pour eviter MissingGreenlet)
        from sqlalchemy import text
        count = test_db.execute(text(
            "SELECT count(*) FROM reservation_pre_check_items "
            "WHERE reservation_id = :rid AND tenant_id = 1"
        ), {"rid": reservation_id}).scalar()
        assert count > 0

        # 3. Préparer le départ terrain (pre-checks OK + caution réglée)
        _prepare_departure_ready(test_db, reservation_id)

        # 4. Valider depart via Operations -> reservation "delivered" + mouvement "completed"
        dep_resp = client.post(
            f"/api/v1/operations/departure/{reservation_id}",
            headers=auth_headers_admin,
        )
        assert dep_resp.status_code == 200
        assert dep_resp.json()["status"] == "delivered"

        res_after_departure = client.get(
            f"/api/v1/reservations/{reservation_id}",
            headers=auth_headers_real,
        ).json()
        assert res_after_departure["status"] == "delivered"

        # Mouvement DEPARTURE doit etre completed
        mv_data = _get_movements_for_reservation(client, reservation_id, auth_headers_admin)
        departure = [m for m in mv_data["items"] if m["movement_type"] == "departure"][0]
        assert departure["status"] == "completed"

        # 5. Creer mouvement RETURN
        return_resp = client.post(
            "/api/v1/inventory-movements",
            json={
                "movement_type": "return",
                "scheduled_date": datetime.now(timezone.utc).isoformat(),
                "reservation_id": reservation_id,
                "items": [
                    {"product_id": product_mv.id, "variant_id": variant_mv.id, "quantity_expected": 3},
                ],
            },
            headers=auth_headers_admin,
        )
        assert return_resp.status_code == 201

        # 6. Valider retour via Operations -> reservation "returned"
        ret_resp = client.post(
            f"/api/v1/operations/return/{reservation_id}",
            headers=auth_headers_admin,
        )
        assert ret_resp.status_code == 200
        assert ret_resp.json()["status"] == "returned"

        res_after_return = client.get(
            f"/api/v1/reservations/{reservation_id}",
            headers=auth_headers_real,
        ).json()
        assert res_after_return["status"] == "returned"

        # Verifier total mouvements lies
        all_mv = _get_movements_for_reservation(client, reservation_id, auth_headers_admin)
        assert all_mv["total"] == 2
