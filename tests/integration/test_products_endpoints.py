"""Tests d'intégration pour les endpoints produits."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.product import Product
from app.models.customer import Customer
from app.models.reservation import Reservation, ReservationLine
from app.models.stock_item import StockItem
from app.constants import ProductCategory, ProductCondition, CustomerType


@pytest.fixture
def test_product(test_db):
    """Produit de test pour tenant_id=1."""
    product = Product(
        tenant_id=1,
        name="Table ronde 150cm",
        sku="TABLE-RONDE-150",
        category=ProductCategory.NAPPES,
        price_per_day_cents=2000,  # 20€
        deposit_amount_cents=5000,  # 50€
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.NEUF,
        image_url="https://example.com/table.jpg",
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


def test_list_products_success(client: TestClient, test_product, auth_headers_real):
    """Test liste produits avec pagination."""
    response = client.get("/api/v1/products?skip=0&limit=20", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    assert data["items"][0]["id"] == test_product.id


def test_list_products_filter_by_category(client: TestClient, test_product, auth_headers_real):
    """Test filtrer produits par catégorie."""
    response = client.get("/api/v1/products?category=nappes", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["category"] == "nappes"


def test_list_products_filter_available_only(client: TestClient, test_db, auth_headers_real):
    """Test filtrer produits avec stock disponible uniquement."""
    # Créer produit avec stock 0
    product_out_of_stock = Product(
        tenant_id=1,
        name="Chaise épuisée",
        sku="CHAISE-OUT",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=500,
        deposit_amount_cents=1000,
        stock_quantity=5,
        available_quantity=0,  # Stock épuisé
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product_out_of_stock)
    test_db.commit()

    response = client.get("/api/v1/products?available_only=true", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["available_quantity"] > 0


def test_get_product_success(client: TestClient, test_product, auth_headers_real):
    """Test récupérer détails d'un produit."""
    response = client.get(f"/api/v1/products/{test_product.id}", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_product.id
    assert data["name"] == "Table ronde 150cm"
    assert data["sku"] == "TABLE-RONDE-150"
    assert data["price_per_day_cents"] == 2000
    assert data["price_per_day_euros"] == 20.0  # Computed field
    assert data["stock_quantity"] == 10
    assert data["available_quantity"] == 10


def test_get_product_not_found(client: TestClient, auth_headers_real):
    """Test récupérer produit inexistant → 404."""
    response = client.get("/api/v1/products/999999", headers=auth_headers_real)

    assert response.status_code == 404


def test_get_product_unauthenticated(client: TestClient, test_product):
    """Test récupérer produit sans authentification → 401."""
    response = client.get(f"/api/v1/products/{test_product.id}")

    assert response.status_code == 401


def test_get_products_stock_batch_success(client: TestClient, test_db, auth_headers_real):
    product_with_items = Product(
        tenant_id=1,
        name="Lot batch 1",
        sku="LOT-BATCH-1",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=0,
        stock_quantity=3,
        available_quantity=1,
        condition=ProductCondition.BON,
        is_active=True,
    )
    product_without_items = Product(
        tenant_id=1,
        name="Lot batch 2",
        sku="LOT-BATCH-2",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1200,
        deposit_amount_cents=0,
        stock_quantity=5,
        available_quantity=4,
        condition=ProductCondition.BON,
        is_active=True,
    )
    test_db.add_all([product_with_items, product_without_items])
    test_db.commit()
    test_db.refresh(product_with_items)
    test_db.refresh(product_without_items)

    test_db.add_all([
        StockItem(tenant_id=1, product_id=product_with_items.id, serial_number="B1-001", status="available"),
        StockItem(tenant_id=1, product_id=product_with_items.id, serial_number="B1-002", status="reserved"),
        StockItem(tenant_id=1, product_id=product_with_items.id, serial_number="B1-003", status="on_location"),
    ])
    test_db.commit()

    response = client.get(
        f"/api/v1/products/stock?ids={product_with_items.id}&ids={product_without_items.id}",
        headers=auth_headers_real,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["items"]) == 2

    by_product_id = {item["product_id"]: item for item in data["items"]}

    with_items = by_product_id[product_with_items.id]
    assert with_items["qty_available"] == 1
    assert with_items["qty_reserved"] == 1
    assert with_items["qty_on_location"] == 1
    assert with_items["total"] == 3
    assert len(with_items["items"]) == 3

    without_items = by_product_id[product_without_items.id]
    assert without_items["qty_available"] == 4
    assert without_items["qty_reserved"] == 1
    assert without_items["qty_on_location"] == 0
    assert without_items["total"] == 5
    assert without_items["items"] == []


def test_create_product_as_admin_success(client: TestClient, auth_headers_admin):
    """Test créer produit en tant qu'admin → 201."""
    product_data = {
        "name": "Chaise Napoléon dorée",
        "sku": "CHAISE-NAP-OR",
        "category": "mobilier",
        "price_per_day_cents": 500,
        "deposit_amount_cents": 1000,
        "stock_quantity": 50,
        "available_quantity": 50,
        "condition": "neuf",
        "image_url": "https://example.com/chaise.jpg"
    }

    response = client.post("/api/v1/products", json=product_data, headers=auth_headers_admin)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Chaise Napoléon dorée"
    assert data["sku"] == "CHAISE-NAP-OR"
    assert data["is_active"] is True  # Défaut
    assert "id" in data


def test_create_product_as_staff_forbidden(client: TestClient, auth_headers_real):
    """Test créer produit en tant que staff (non-admin) → 403."""
    product_data = {
        "name": "Table test",
        "sku": "TABLE-TEST",
        "category": "nappes",
        "price_per_day_cents": 1000,
        "deposit_amount_cents": 2000,
        "stock_quantity": 5,
        "available_quantity": 5,
        "condition": "bon"
    }

    response = client.post("/api/v1/products", json=product_data, headers=auth_headers_real)

    assert response.status_code == 403  # Forbidden (RBAC)


def test_create_product_duplicate_sku(client: TestClient, test_product, auth_headers_admin):
    """Test créer produit avec SKU déjà existant → 409."""
    product_data = {
        "name": "Autre table",
        "sku": "TABLE-RONDE-150",  # SKU déjà utilisé par test_product
        "category": "nappes",
        "price_per_day_cents": 1500,
        "deposit_amount_cents": 3000,
        "stock_quantity": 3,
        "available_quantity": 3,
        "condition": "bon"
    }

    response = client.post("/api/v1/products", json=product_data, headers=auth_headers_admin)

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_update_product_as_admin_success(client: TestClient, test_product, auth_headers_admin):
    """Test mettre à jour produit en tant qu'admin (PATCH partiel)."""
    update_data = {
        "price_per_day_cents": 2500,  # Augmentation prix
        "stock_quantity": 15,
        "available_quantity": 15
    }

    response = client.patch(
        f"/api/v1/products/{test_product.id}",
        json=update_data,
        headers=auth_headers_admin
    )

    assert response.status_code == 200
    data = response.json()
    assert data["price_per_day_cents"] == 2500
    assert data["stock_quantity"] == 15
    assert data["name"] == "Table ronde 150cm"  # Inchangé


def test_update_product_available_exceeds_stock(client: TestClient, test_product, auth_headers_admin):
    """Test mettre à jour avec available > stock → 400."""
    update_data = {
        "stock_quantity": 5,
        "available_quantity": 10  # Invalide: available > stock
    }

    response = client.patch(
        f"/api/v1/products/{test_product.id}",
        json=update_data,
        headers=auth_headers_admin
    )

    assert response.status_code == 400
    assert "available_quantity cannot exceed stock_quantity" in response.json()["detail"]


def test_delete_product_soft_delete(client: TestClient, test_product, auth_headers_admin):
    """Test supprimer produit (soft delete par défaut)."""
    response = client.delete(
        f"/api/v1/products/{test_product.id}?hard_delete=false",
        headers=auth_headers_admin
    )

    assert response.status_code == 204

    # Vérifier que produit est is_active=False
    get_response = client.get(f"/api/v1/products/{test_product.id}", headers=auth_headers_admin)
    assert get_response.status_code == 404  # Exclu des listes par défaut


def test_delete_product_as_staff_forbidden(client: TestClient, test_product, auth_headers_real):
    """Test supprimer produit en tant que staff → 403."""
    response = client.delete(
        f"/api/v1/products/{test_product.id}",
        headers=auth_headers_real
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Disponibilité produit
# ---------------------------------------------------------------------------

@pytest.fixture
def test_product_avail(test_db):
    """Produit pour tests de disponibilité."""
    product = Product(
        tenant_id=1,
        name="Chaise Chiavari",
        sku="CHAISE-CHIAVARI-01",
        category=ProductCategory.CHAISES,
        price_per_day_cents=500,
        deposit_amount_cents=1000,
        stock_quantity=20,
        available_quantity=20,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def test_customer_avail(test_db):
    """Client pour tests de disponibilité."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Marc",
        last_name="Dupont",
        email="marc.dupont.avail@example.com",
        is_active=True,
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture
def test_reservation_avail(test_db, test_product_avail, test_customer_avail):
    """Réservation confirmée occupant le produit du 2030-06-10 au 2030-06-15."""
    today = date(2030, 6, 12)  # event_date
    delivery = date(2030, 6, 10)
    return_d = date(2030, 6, 15)

    res = Reservation(
        tenant_id=1,
        customer_id=test_customer_avail.id,
        reference="RES-AVAIL-001",
        event_date=today,
        delivery_date=delivery,
        return_date=return_d,
        status="confirmed",
        total_amount_cents=10000,
    )
    test_db.add(res)
    test_db.flush()

    line = ReservationLine(
        tenant_id=1,
        reservation_id=res.id,
        product_id=test_product_avail.id,
        quantity=5,
        unit_price_cents=500,
        subtotal_cents=2500,
    )
    test_db.add(line)
    test_db.commit()
    test_db.refresh(res)
    return res


def test_get_availability_no_slots(client: TestClient, test_product_avail, auth_headers_real):
    """Aucune réservation → busy_slots vide."""
    response = client.get(
        f"/api/v1/products/{test_product_avail.id}/availability"
        "?date_from=2030-01-01&date_to=2030-01-31",
        headers=auth_headers_real,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == test_product_avail.id
    assert data["total_quantity"] == 20
    assert data["busy_slots"] == []


def test_get_availability_with_overlap(
    client: TestClient, test_product_avail, test_reservation_avail, auth_headers_real
):
    """Réservation chevauche la plage demandée → 1 slot retourné."""
    response = client.get(
        f"/api/v1/products/{test_product_avail.id}/availability"
        "?date_from=2030-06-01&date_to=2030-06-30",
        headers=auth_headers_real,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["busy_slots"]) == 1
    slot = data["busy_slots"][0]
    assert slot["reservation_id"] == test_reservation_avail.id
    assert slot["reserved_quantity"] == 5
    assert slot["reservation_ref"] == "RES-AVAIL-001"


def test_get_availability_no_overlap(
    client: TestClient, test_product_avail, test_reservation_avail, auth_headers_real
):
    """Plage demandée avant la réservation → aucun slot."""
    response = client.get(
        f"/api/v1/products/{test_product_avail.id}/availability"
        "?date_from=2030-05-01&date_to=2030-06-09",
        headers=auth_headers_real,
    )
    assert response.status_code == 200
    assert response.json()["busy_slots"] == []


def test_get_availability_invalid_dates(client: TestClient, test_product_avail, auth_headers_real):
    """date_to < date_from → 400."""
    response = client.get(
        f"/api/v1/products/{test_product_avail.id}/availability"
        "?date_from=2030-06-30&date_to=2030-06-01",
        headers=auth_headers_real,
    )
    assert response.status_code == 400


def test_get_availability_product_not_found(client: TestClient, auth_headers_real):
    """Produit inexistant → 404."""
    response = client.get(
        "/api/v1/products/999999/availability?date_from=2030-01-01&date_to=2030-01-31",
        headers=auth_headers_real,
    )
    assert response.status_code == 404
