"""Tests d'intégration pour les endpoints produits."""
import pytest
from fastapi.testclient import TestClient
from app.models.product import Product
from app.constants import ProductCategory, ProductCondition


@pytest.fixture
def test_product(test_db):
    """Produit de test pour tenant_id=1."""
    product = Product(
        tenant_id=1,
        name="Table ronde 150cm",
        sku="TABLE-RONDE-150",
        category=ProductCategory.NAPPE,
        price_per_day=2000,  # 20€
        deposit_amount=5000,  # 50€
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
    response = client.get("/api/v1/products?category=nappe", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["category"] == "nappe"


def test_list_products_filter_available_only(client: TestClient, test_db, auth_headers_real):
    """Test filtrer produits avec stock disponible uniquement."""
    # Créer produit avec stock 0
    product_out_of_stock = Product(
        tenant_id=1,
        name="Chaise épuisée",
        sku="CHAISE-OUT",
        category=ProductCategory.AUTRE,
        price_per_day=500,
        deposit_amount=1000,
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


def test_create_product_as_admin_success(client: TestClient, auth_headers_admin):
    """Test créer produit en tant qu'admin → 201."""
    product_data = {
        "name": "Chaise Napoléon dorée",
        "sku": "CHAISE-NAP-OR",
        "category": "autre",
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
        "category": "nappe",
        "price_per_day_cents": 1000,
        "deposit_amount_cents": 2000,
        "stock_quantity": 5,
        "available_quantity": 5,
        "condition": "bon"
    }

    response = client.post("/api/v1/products", json=product_data, headers=auth_headers_real)

    assert response.status_code == 403  # Forbidden (RBAC)


def test_create_product_duplicate_sku(client: TestClient, test_product, auth_headers_admin):
    """Test créer produit avec SKU déjà existant → 400."""
    product_data = {
        "name": "Autre table",
        "sku": "TABLE-RONDE-150",  # SKU déjà utilisé par test_product
        "category": "nappe",
        "price_per_day_cents": 1500,
        "deposit_amount_cents": 3000,
        "stock_quantity": 3,
        "available_quantity": 3,
        "condition": "bon"
    }

    response = client.post("/api/v1/products", json=product_data, headers=auth_headers_admin)

    assert response.status_code == 400
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
