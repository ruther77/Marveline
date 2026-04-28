"""Tests d'intégration : transitions stock_item pendant le cycle de réservation.

Couvre :
- Confirmation réservation : StockItems 'available' → 'reserved'
- Complétion DEPARTURE : StockItems 'reserved' → 'on_location'
- Complétion RETURN : StockItems 'on_location' → 'available'
- Vérification des compteurs via GET /api/v1/products/{product_id}/stock
- O1-a : RETURN avec tous les articles endommagés → StockItems 'damaged' + MovementItemUnit créés
- O1-b : RETURN partiel (2 produits) → transition individuelle par produit
- O1-c : Calcul automatique damage_fee lors du RETURN
"""
import pytest
from datetime import date, timedelta, datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models.customer import Customer
from app.models.product import Product
from app.models.stock_item import StockItem
from app.models.movement_item_unit import MovementItemUnit
from app.models.product_variant import ProductVariant
from app.constants import CustomerType, ProductCategory, ProductCondition

TENANT_ID = 1
QTY = 3  # Nombre d'unités physiques créées


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def customer_stock(test_db):
    """Client de test pour workflow stock."""
    customer = Customer(
        tenant_id=TENANT_ID,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Alice",
        last_name="Martin",
        email="alice.martin@stockworkflow.com",
        phone="+33612345678",
        city="Lyon",
        postal_code="69001",
        is_active=True,
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture
def product_stock(test_db):
    """Produit avec 3 unités physiques disponibles (StockItems)."""
    product = Product(
        tenant_id=TENANT_ID,
        name="Nappe blanche 180cm",
        sku="NAPPE-STOCK-001",
        category=ProductCategory.NAPPES,
        price_per_day_cents=300,   # 3 EUR/jour
        deposit_amount_cents=500,  # 5 EUR caution
        stock_quantity=QTY,
        available_quantity=QTY,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)

    # Créer les unités physiques — obligatoire pour reserve_n
    for i in range(QTY):
        item = StockItem(
            tenant_id=TENANT_ID,
            product_id=product.id,
            serial_number=f"NAPPE-STOCK-{i + 1:03d}",
            status="available",
        )
        test_db.add(item)
    test_db.commit()

    test_db.refresh(product)
    return product


@pytest.fixture
def variant_stock(test_db, product_stock):
    """Variante Standard associée à product_stock."""
    variant = ProductVariant(
        tenant_id=TENANT_ID,
        product_id=product_stock.id,
        label="Standard",
        sku=f"STD-{product_stock.id}",
        price_per_day_cents=product_stock.price_per_day_cents,
        deposit_amount_cents=product_stock.deposit_amount_cents,
        stock_quantity=product_stock.stock_quantity,
        available_quantity=product_stock.available_quantity,
        is_active=True,
    )
    test_db.add(variant)
    test_db.commit()
    test_db.refresh(variant)
    return variant


# ============================================================
# Helpers
# ============================================================

def _get_stock(client: TestClient, product_id: int, headers: dict) -> dict:
    """GET /api/v1/products/{product_id}/stock → StockDetail."""
    resp = client.get(f"/api/v1/products/{product_id}/stock", headers=headers)
    assert resp.status_code == 200, f"GET stock failed: {resp.json()}"
    return resp.json()


def _create_reservation(client: TestClient, customer_id: int, product_id: int, qty: int, headers: dict, variant_id: int | None = None) -> dict:
    line = {"product_id": product_id, "quantity": qty}
    if variant_id is not None:
        line["variant_id"] = variant_id
    resp = client.post(
        "/api/v1/reservations",
        json={
            "customer_id": customer_id,
            "event_date": str(date.today() + timedelta(days=14)),
            "delivery_date": str(date.today() + timedelta(days=13)),
            "return_date": str(date.today() + timedelta(days=15)),
            "event_location": "Salle du Peuple Lyon",
            "lines": [line],
        },
        headers=headers,
    )
    assert resp.status_code == 201, f"Create reservation failed: {resp.json()}"
    return resp.json()


def _confirm_reservation(client: TestClient, reservation_id: int, headers: dict) -> dict:
    resp = client.post(
        f"/api/v1/reservations/{reservation_id}/confirm",
        headers=headers,
    )
    assert resp.status_code == 200, f"Confirm reservation failed: {resp.json()}"
    return resp.json()


def _get_departure_id(client: TestClient, reservation_id: int, headers: dict) -> int:
    resp = client.get(
        f"/api/v1/inventory-movements?reservation_id={reservation_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    departures = [m for m in items if m["movement_type"] == "departure"]
    assert len(departures) == 1, "DEPARTURE auto-créé introuvable"
    return departures[0]["id"]


def _set_all_prechecks_checked(test_db, reservation_id: int) -> None:
    """Prépare une réservation pour le départ terrain.

    Cette suite vérifie les transitions de stock, pas les prérequis métier
    du départ. On coche donc tous les pre-checks et on marque la caution comme
    payée pour exercer le flow Operations nominal.
    """
    result = test_db.execute(
        text(
            "UPDATE reservation_pre_check_items "
            "SET checked = true "
            "WHERE reservation_id = :rid AND tenant_id = :tenant_id"
        ),
        {"rid": reservation_id, "tenant_id": TENANT_ID},
    )
    assert result.rowcount > 0, "Pre-check items should have been auto-created"
    test_db.execute(
        text(
            "UPDATE reservations "
            "SET deposit_paid = true "
            "WHERE id = :rid AND tenant_id = :tenant_id"
        ),
        {"rid": reservation_id, "tenant_id": TENANT_ID},
    )
    test_db.commit()


def _validate_departure(client: TestClient, reservation_id: int, headers: dict) -> dict:
    """Complète le départ via le flow Operations supporté."""
    resp = client.post(
        f"/api/v1/operations/departure/{reservation_id}",
        headers=headers,
    )
    assert resp.status_code == 200, f"Validate departure failed: {resp.json()}"
    return resp.json()


def _validate_return(client: TestClient, reservation_id: int, headers: dict) -> dict:
    """Complète le retour via le flow Operations supporté."""
    resp = client.post(
        f"/api/v1/operations/return/{reservation_id}",
        headers=headers,
    )
    assert resp.status_code == 200, f"Validate return failed: {resp.json()}"
    return resp.json()


# ============================================================
# Tests
# ============================================================

class TestStockItemStatusTransitions:
    """Vérifie les transitions de status StockItem à chaque étape du workflow."""

    def test_confirm_moves_stock_items_to_reserved(
        self,
        client: TestClient,
        test_db,
        customer_stock,
        product_stock,
        variant_stock,
        auth_headers_real,
    ):
        """Après confirmation, les StockItems passent de 'available' à 'reserved'."""
        # Vérifier état initial
        stock_before = _get_stock(client, product_stock.id, auth_headers_real)
        assert stock_before["qty_available"] == QTY
        assert stock_before["qty_reserved"] == 0

        # Créer et confirmer la réservation
        res = _create_reservation(client, customer_stock.id, product_stock.id, QTY, auth_headers_real, variant_id=variant_stock.id)
        _confirm_reservation(client, res["id"], auth_headers_real)

        # Vérifier transition available → reserved
        stock_after = _get_stock(client, product_stock.id, auth_headers_real)
        assert stock_after["qty_available"] == 0
        assert stock_after["qty_reserved"] == QTY
        assert stock_after["qty_on_location"] == 0

    def test_departure_complete_moves_stock_items_to_on_location(
        self,
        client: TestClient,
        test_db,
        customer_stock,
        product_stock,
        variant_stock,
        auth_headers_real,
        auth_headers_admin,
    ):
        """Après DEPARTURE completed, les StockItems passent de 'reserved' à 'on_location'."""
        res = _create_reservation(client, customer_stock.id, product_stock.id, QTY, auth_headers_real, variant_id=variant_stock.id)
        _confirm_reservation(client, res["id"], auth_headers_real)

        # Compléter DEPARTURE
        departure_id = _get_departure_id(client, res["id"], auth_headers_admin)
        _set_all_prechecks_checked(test_db, res["id"])
        _validate_departure(client, res["id"], auth_headers_admin)

        # Vérifier transition reserved → on_location
        stock = _get_stock(client, product_stock.id, auth_headers_real)
        assert stock["qty_available"] == 0
        assert stock["qty_reserved"] == 0
        assert stock["qty_on_location"] == QTY

    def test_return_complete_moves_stock_items_back_to_available(
        self,
        client: TestClient,
        test_db,
        customer_stock,
        product_stock,
        variant_stock,
        auth_headers_real,
        auth_headers_admin,
    ):
        """Après RETURN completed, les StockItems reviennent à 'available'."""
        res = _create_reservation(client, customer_stock.id, product_stock.id, QTY, auth_headers_real, variant_id=variant_stock.id)
        _confirm_reservation(client, res["id"], auth_headers_real)

        # Compléter DEPARTURE
        departure_id = _get_departure_id(client, res["id"], auth_headers_admin)
        _set_all_prechecks_checked(test_db, res["id"])
        _validate_departure(client, res["id"], auth_headers_admin)

        # Créer et compléter RETURN
        return_resp = client.post(
            "/api/v1/inventory-movements",
            json={
                "movement_type": "return",
                "scheduled_date": datetime.now(timezone.utc).isoformat(),
                "reservation_id": res["id"],
                "items": [{"product_id": product_stock.id, "quantity_expected": QTY}],
            },
            headers=auth_headers_admin,
        )
        assert return_resp.status_code == 201, f"Create return failed: {return_resp.json()}"
        _validate_return(client, res["id"], auth_headers_admin)

        # Vérifier retour à available
        stock = _get_stock(client, product_stock.id, auth_headers_real)
        assert stock["qty_available"] == QTY
        assert stock["qty_reserved"] == 0
        assert stock["qty_on_location"] == 0

    def test_full_cycle_stock_transitions(
        self,
        client: TestClient,
        test_db,
        customer_stock,
        product_stock,
        variant_stock,
        auth_headers_real,
        auth_headers_admin,
    ):
        """Workflow complet : vérifie les compteurs stock à chaque étape.

        Étapes :
            1. Initial        : available=3, reserved=0, on_location=0
            2. Après confirm  : available=0, reserved=3, on_location=0
            3. Après DEPARTURE: available=0, reserved=0, on_location=3
            4. Après RETURN   : available=3, reserved=0, on_location=0
        """
        # 1. Initial
        s0 = _get_stock(client, product_stock.id, auth_headers_real)
        assert s0["qty_available"] == QTY
        assert s0["qty_reserved"] == 0
        assert s0["qty_on_location"] == 0

        # 2. Après confirmation
        res = _create_reservation(client, customer_stock.id, product_stock.id, QTY, auth_headers_real, variant_id=variant_stock.id)
        _confirm_reservation(client, res["id"], auth_headers_real)

        s1 = _get_stock(client, product_stock.id, auth_headers_real)
        assert s1["qty_available"] == 0
        assert s1["qty_reserved"] == QTY
        assert s1["qty_on_location"] == 0

        # 3. Après DEPARTURE completed
        departure_id = _get_departure_id(client, res["id"], auth_headers_admin)
        _set_all_prechecks_checked(test_db, res["id"])
        _validate_departure(client, res["id"], auth_headers_admin)

        s2 = _get_stock(client, product_stock.id, auth_headers_real)
        assert s2["qty_available"] == 0
        assert s2["qty_reserved"] == 0
        assert s2["qty_on_location"] == QTY

        # 4. Après RETURN completed
        return_resp = client.post(
            "/api/v1/inventory-movements",
            json={
                "movement_type": "return",
                "scheduled_date": datetime.now(timezone.utc).isoformat(),
                "reservation_id": res["id"],
                "items": [{"product_id": product_stock.id, "quantity_expected": QTY}],
            },
            headers=auth_headers_admin,
        )
        assert return_resp.status_code == 201
        _validate_return(client, res["id"], auth_headers_admin)

        s3 = _get_stock(client, product_stock.id, auth_headers_real)
        assert s3["qty_available"] == QTY
        assert s3["qty_reserved"] == 0
        assert s3["qty_on_location"] == 0

    def test_confirm_without_stock_items_uses_aggregate_stock(
        self,
        client: TestClient,
        test_db,
        customer_stock,
        auth_headers_real,
    ):
        """Confirmer sans StockItems physiques utilise le stock agrégé du produit."""
        # Produit sans StockItems créés
        product_no_stock = Product(
            tenant_id=TENANT_ID,
            name="Produit sans stock physique",
            sku="NO-STOCK-001",
            category=ProductCategory.NAPPES,
            price_per_day_cents=100,
            deposit_amount_cents=200,
            stock_quantity=5,
            available_quantity=5,
            condition=ProductCondition.NEUF,
            is_active=True,
        )
        test_db.add(product_no_stock)
        test_db.commit()
        test_db.refresh(product_no_stock)

        variant_no_stock = ProductVariant(
            tenant_id=TENANT_ID,
            product_id=product_no_stock.id,
            label="Standard",
            sku=f"STD-{product_no_stock.id}",
            price_per_day_cents=product_no_stock.price_per_day_cents,
            deposit_amount_cents=product_no_stock.deposit_amount_cents,
            stock_quantity=product_no_stock.stock_quantity,
            available_quantity=product_no_stock.available_quantity,
            is_active=True,
        )
        test_db.add(variant_no_stock)
        test_db.commit()
        test_db.refresh(variant_no_stock)

        # Créer une réservation (draft)
        res = _create_reservation(
            client, customer_stock.id, product_no_stock.id, 2, auth_headers_real,
            variant_id=variant_no_stock.id,
        )

        # La confirmation doit utiliser le stock agrégé du produit
        resp = client.post(
            f"/api/v1/reservations/{res['id']}/confirm",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"


# ============================================================
# Tests O1 — Tracking individuel MovementItemUnit
# ============================================================


@pytest.fixture
def product_damaged_test(test_db):
    """Produit avec 3 unités physiques pour tests O1 (SKU différent pour isoler)."""
    product = Product(
        tenant_id=TENANT_ID,
        name="Nappe rouge 120cm",
        sku="NAPPE-DAMAGED-001",
        category=ProductCategory.NAPPES,
        price_per_day_cents=300,   # 3 EUR/jour
        deposit_amount_cents=500,
        stock_quantity=QTY,
        available_quantity=QTY,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)

    for i in range(QTY):
        test_db.add(StockItem(
            tenant_id=TENANT_ID,
            product_id=product.id,
            serial_number=f"NAPPE-DAM-{i + 1:03d}",
            status="available",
        ))
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def variant_damaged_test(test_db, product_damaged_test):
    """Variante Standard associée à product_damaged_test."""
    variant = ProductVariant(
        tenant_id=TENANT_ID,
        product_id=product_damaged_test.id,
        label="Standard",
        sku=f"STD-{product_damaged_test.id}",
        price_per_day_cents=product_damaged_test.price_per_day_cents,
        deposit_amount_cents=product_damaged_test.deposit_amount_cents,
        stock_quantity=product_damaged_test.stock_quantity,
        available_quantity=product_damaged_test.available_quantity,
        is_active=True,
    )
    test_db.add(variant)
    test_db.commit()
    test_db.refresh(variant)
    return variant


def _run_departure_cycle(client, test_db, customer_id, product_id, qty, headers_user, headers_admin, variant_id=None):
    """Crée + confirme une réservation, puis complète le DEPARTURE.

    Retourne (reservation_id, departure_id).
    """
    res = _create_reservation(client, customer_id, product_id, qty, headers_user, variant_id=variant_id)
    _confirm_reservation(client, res["id"], headers_user)
    departure_id = _get_departure_id(client, res["id"], headers_admin)
    _set_all_prechecks_checked(test_db, res["id"])
    _validate_departure(client, res["id"], headers_admin)
    return res["id"], departure_id


class TestMovementItemUnitTracking:
    """Tests O1 — Vérification du tracking individuel MovementItemUnit."""

    def test_o1a_departure_creates_movement_item_units(
        self,
        client: TestClient,
        test_db,
        customer_stock,
        product_damaged_test,
        variant_damaged_test,
        auth_headers_real,
        auth_headers_admin,
    ):
        """O1-a — DEPARTURE completed crée un MovementItemUnit par StockItem physique."""
        reservation_id, departure_id = _run_departure_cycle(
            client, test_db,
            customer_stock.id, product_damaged_test.id, QTY,
            auth_headers_real, auth_headers_admin,
            variant_id=variant_damaged_test.id,
        )

        # Vérifier les MovementItemUnit créés en DB
        # On passe par le GET movement pour récupérer les item ids
        movement_resp = client.get(
            f"/api/v1/inventory-movements/{departure_id}",
            headers=auth_headers_admin,
        )
        assert movement_resp.status_code == 200
        items = movement_resp.json()["items"]
        assert len(items) == 1
        item = items[0]

        # Vérifier les units dans la réponse
        assert "units" in item
        assert len(item["units"]) == QTY, (
            f"Attendu {QTY} MovementItemUnit, obtenu {len(item['units'])}"
        )
        # Chaque unit pointe vers un stock_item_id distinct
        unit_stock_ids = {u["stock_item_id"] for u in item["units"]}
        assert len(unit_stock_ids) == QTY

    def test_o1a_return_damaged_moves_stock_items_to_damaged(
        self,
        client: TestClient,
        test_db,
        customer_stock,
        product_damaged_test,
        variant_damaged_test,
        auth_headers_real,
        auth_headers_admin,
    ):
        """O1-a — RETURN avec tous les articles endommagés → StockItems passent à 'damaged'."""
        reservation_id, _ = _run_departure_cycle(
            client, test_db,
            customer_stock.id, product_damaged_test.id, QTY,
            auth_headers_real, auth_headers_admin,
            variant_id=variant_damaged_test.id,
        )

        # Créer le RETURN avec condition=damaged
        return_resp = client.post(
            "/api/v1/inventory-movements",
            json={
                "movement_type": "return",
                "scheduled_date": datetime.now(timezone.utc).isoformat(),
                "reservation_id": reservation_id,
                "items": [{
                    "product_id": product_damaged_test.id,
                    "quantity_expected": QTY,
                    "quantity_actual": QTY,
                    "condition": "damaged",
                    "condition_notes": "Articles abîmés au retour",
                }],
            },
            headers=auth_headers_admin,
        )
        assert return_resp.status_code == 201, return_resp.json()
        return_id = return_resp.json()["id"]

        # Compléter le RETURN
        _validate_return(client, reservation_id, auth_headers_admin)

        # Vérifier les StockItems : tous doivent être 'damaged'
        damaged_items = (
            test_db.query(StockItem)
            .filter(
                StockItem.product_id == product_damaged_test.id,
                StockItem.tenant_id == TENANT_ID,
            )
            .all()
        )
        assert len(damaged_items) == QTY
        statuses = [item.status for item in damaged_items]
        assert all(s == "damaged" for s in statuses), (
            f"StockItems attendus 'damaged', obtenus: {statuses}"
        )

        # Vérifier le compteur stock via API
        stock = _get_stock(client, product_damaged_test.id, auth_headers_real)
        assert stock["qty_available"] == 0
        assert stock["qty_on_location"] == 0
        assert stock["qty_damaged"] == QTY

    def test_o1b_return_partial_two_products(
        self,
        client: TestClient,
        test_db,
        customer_stock,
        product_damaged_test,
        variant_damaged_test,
        auth_headers_real,
        auth_headers_admin,
    ):
        """O1-b — RETURN partiel avec 2 produits : un retour OK, un retour endommagé."""
        # Créer un deuxième produit avec 1 StockItem
        product_b = Product(
            tenant_id=TENANT_ID,
            name="Chaise dorée",
            sku="CHAISE-B-001",
            category=ProductCategory.CHAISES,
            price_per_day_cents=200,
            deposit_amount_cents=300,
            stock_quantity=1,
            available_quantity=1,
            condition=ProductCondition.NEUF,
            is_active=True,
        )
        test_db.add(product_b)
        test_db.commit()
        test_db.refresh(product_b)
        test_db.add(StockItem(
            tenant_id=TENANT_ID,
            product_id=product_b.id,
            serial_number="CHAISE-B-001",
            status="available",
        ))
        test_db.commit()

        # Variante pour product_b
        variant_b = ProductVariant(
            tenant_id=TENANT_ID,
            product_id=product_b.id,
            label="Standard",
            sku=f"STD-{product_b.id}",
            price_per_day_cents=product_b.price_per_day_cents,
            deposit_amount_cents=product_b.deposit_amount_cents,
            stock_quantity=product_b.stock_quantity,
            available_quantity=product_b.available_quantity,
            is_active=True,
        )
        test_db.add(variant_b)
        test_db.commit()
        test_db.refresh(variant_b)

        # Réservation avec product_damaged_test×2 + product_b×1
        resp = client.post(
            "/api/v1/reservations",
            json={
                "customer_id": customer_stock.id,
                "event_date": str(date.today() + timedelta(days=14)),
                "delivery_date": str(date.today() + timedelta(days=13)),
                "return_date": str(date.today() + timedelta(days=15)),
                "event_location": "Salle de test Lyon",
                "lines": [
                    {"product_id": product_damaged_test.id, "variant_id": variant_damaged_test.id, "quantity": 2},
                    {"product_id": product_b.id, "variant_id": variant_b.id, "quantity": 1},
                ],
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 201, resp.json()
        reservation_id = resp.json()["id"]
        _confirm_reservation(client, reservation_id, auth_headers_real)

        # Compléter DEPARTURE
        departure_id = _get_departure_id(client, reservation_id, auth_headers_admin)
        _set_all_prechecks_checked(test_db, reservation_id)
        _validate_departure(client, reservation_id, auth_headers_admin)

        # Vérifier: 3 MovementItemUnit créés (2 pour product_damaged_test + 1 pour product_b)
        movement_resp = client.get(
            f"/api/v1/inventory-movements/{departure_id}",
            headers=auth_headers_admin,
        )
        items = movement_resp.json()["items"]
        total_units = sum(len(item["units"]) for item in items)
        assert total_units == 3, f"Attendu 3 MovementItemUnit, obtenu {total_units}"

        # RETURN : product_damaged_test OK, product_b endommagé
        return_resp = client.post(
            "/api/v1/inventory-movements",
            json={
                "movement_type": "return",
                "scheduled_date": datetime.now(timezone.utc).isoformat(),
                "reservation_id": reservation_id,
                "items": [
                    {
                        "product_id": product_damaged_test.id,
                        "quantity_expected": 2,
                        "quantity_actual": 2,
                        # Pas de condition → retour normal
                    },
                    {
                        "product_id": product_b.id,
                        "quantity_expected": 1,
                        "quantity_actual": 1,
                        "condition": "damaged",
                    },
                ],
            },
            headers=auth_headers_admin,
        )
        assert return_resp.status_code == 201, return_resp.json()
        _validate_return(client, reservation_id, auth_headers_admin)

        # product_damaged_test : QTY=3 StockItems au total, 2 réservés puis retournés → 3 available
        stock_a = _get_stock(client, product_damaged_test.id, auth_headers_real)
        assert stock_a["qty_available"] == 3, f"product A: {stock_a}"
        assert stock_a["qty_damaged"] == 0

        # product_b : 1 StockItem → damaged
        stock_b = _get_stock(client, product_b.id, auth_headers_real)
        assert stock_b["qty_damaged"] == 1, f"product B: {stock_b}"
        assert stock_b["qty_available"] == 0

    def test_o1c_return_damaged_auto_calculates_damage_fee(
        self,
        client: TestClient,
        test_db,
        customer_stock,
        product_damaged_test,
        variant_damaged_test,
        auth_headers_real,
        auth_headers_admin,
    ):
        """O1-c — RETURN avec articles endommagés → damage_fee calculé automatiquement.

        Règle : damage_fee = price_per_day * qty_damaged
        product_damaged_test.price_per_day_cents = 300, qty = QTY (3) → 900 centimes
        """
        reservation_id, _ = _run_departure_cycle(
            client, test_db,
            customer_stock.id, product_damaged_test.id, QTY,
            auth_headers_real, auth_headers_admin,
            variant_id=variant_damaged_test.id,
        )

        # RETURN avec tous articles endommagés
        return_resp = client.post(
            "/api/v1/inventory-movements",
            json={
                "movement_type": "return",
                "scheduled_date": datetime.now(timezone.utc).isoformat(),
                "reservation_id": reservation_id,
                "items": [{
                    "product_id": product_damaged_test.id,
                    "variant_id": variant_damaged_test.id,
                    "quantity_expected": QTY,
                    "quantity_actual": QTY,
                    "condition": "damaged",
                }],
            },
            headers=auth_headers_admin,
        )
        assert return_resp.status_code == 201, return_resp.json()
        return_id = return_resp.json()["id"]

        # Compléter RETURN via Operations puis relire le mouvement complété
        _validate_return(client, reservation_id, auth_headers_admin)
        r = client.get(
            f"/api/v1/inventory-movements/{return_id}",
            headers=auth_headers_admin,
        )
        assert r.status_code == 200, r.json()
        completed = r.json()

        # Vérifier damage_fee auto-calculé : 300 × 3 = 900 centimes
        expected_fee = product_damaged_test.price_per_day_cents * QTY  # 900
        assert completed["damage_fee"] == expected_fee, (
            f"damage_fee attendu={expected_fee}, obtenu={completed['damage_fee']}"
        )
        assert completed["damage_fee_euros"] == pytest.approx(expected_fee / 100)
