"""Tests d'intégration — poids/volume sur produits et variantes + anti cross-tenant."""
import pytest
from fastapi.testclient import TestClient
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.constants import ProductCategory, ProductCondition


@pytest.fixture
def product_with_weight(test_db):
    """Produit avec poids et volume renseignés (tenant_id=1)."""
    product = Product(
        tenant_id=1,
        name="Table lourde 200cm",
        sku="TABLE-LOURDE-200",
        category=ProductCategory.TABLES,
        price_per_day_cents=3000,
        deposit_amount_cents=8000,
        stock_quantity=5,
        available_quantity=5,
        condition=ProductCondition.BON,
        weight_grams=25000,
        volume_cm3=120000,
        is_active=True,
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def product_without_weight(test_db):
    """Produit sans poids/volume (tenant_id=1)."""
    product = Product(
        tenant_id=1,
        name="Serviette simple",
        sku="SERV-SIMPLE",
        category=ProductCategory.SERVIETTES,
        price_per_day_cents=50,
        deposit_amount_cents=0,
        stock_quantity=200,
        available_quantity=200,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def variant_with_weight(test_db, product_with_weight):
    """Variante avec override poids/volume."""
    variant = ProductVariant(
        tenant_id=1,
        product_id=product_with_weight.id,
        label="Blanc mat",
        sku="TABLE-LOURDE-200-WHI",
        color="blanc",
        stock_quantity=3,
        available_quantity=3,
        weight_grams=26000,
        volume_cm3=125000,
    )
    test_db.add(variant)
    test_db.commit()
    test_db.refresh(variant)
    return variant


@pytest.fixture
def product_other_tenant(test_db):
    """Produit d'un autre tenant (tenant_id=2)."""
    product = Product(
        tenant_id=2,
        name="Chaise autre tenant",
        sku="CHAISE-OTHER",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
        stock_quantity=20,
        available_quantity=20,
        condition=ProductCondition.BON,
        weight_grams=5000,
        volume_cm3=30000,
        is_active=True,
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


class TestProductWeightVolumeEndpoints:
    """Tests CRUD poids/volume via API."""

    def test_create_product_with_weight_volume(self, client: TestClient, auth_headers_real):
        response = client.post(
            "/api/v1/products",
            json={
                "name": "Banc test poids",
                "sku": "BANC-POIDS-01",
                "category": "bancs",
                "price_per_day_cents": 1500,
                "stock_quantity": 8,
                "available_quantity": 8,
                "weight_grams": 18000,
                "volume_cm3": 95000,
            },
            headers=auth_headers_real,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["weight_grams"] == 18000
        assert data["volume_cm3"] == 95000

    def test_create_product_without_weight_volume(self, client: TestClient, auth_headers_real):
        response = client.post(
            "/api/v1/products",
            json={
                "name": "Assiette sans poids",
                "sku": "ASS-NO-POIDS",
                "category": "assiettes",
                "price_per_day_cents": 100,
                "stock_quantity": 100,
                "available_quantity": 100,
            },
            headers=auth_headers_real,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["weight_grams"] is None
        assert data["volume_cm3"] is None

    def test_get_product_returns_weight_volume(
        self, client: TestClient, product_with_weight, auth_headers_real
    ):
        response = client.get(
            f"/api/v1/products/{product_with_weight.id}",
            headers=auth_headers_real,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["weight_grams"] == 25000
        assert data["volume_cm3"] == 120000

    def test_update_product_weight_volume(
        self, client: TestClient, product_without_weight, auth_headers_real
    ):
        response = client.patch(
            f"/api/v1/products/{product_without_weight.id}",
            json={"weight_grams": 50, "volume_cm3": 200},
            headers=auth_headers_real,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["weight_grams"] == 50
        assert data["volume_cm3"] == 200

    def test_list_products_includes_weight_volume(
        self, client: TestClient, product_with_weight, auth_headers_real
    ):
        response = client.get("/api/v1/products", headers=auth_headers_real)
        assert response.status_code == 200
        items = response.json()["items"]
        found = [i for i in items if i["id"] == product_with_weight.id]
        assert len(found) == 1
        assert found[0]["weight_grams"] == 25000
        assert found[0]["volume_cm3"] == 120000


class TestProductWeightVolumeCrossTenant:
    """Anti cross-tenant : le produit d'un autre tenant ne doit pas apparaître."""

    def test_cannot_access_other_tenant_product(
        self, client: TestClient, product_other_tenant, auth_headers_real
    ):
        response = client.get(
            f"/api/v1/products/{product_other_tenant.id}",
            headers=auth_headers_real,
        )
        assert response.status_code == 404

    def test_list_excludes_other_tenant(
        self, client: TestClient, product_other_tenant, product_with_weight, auth_headers_real
    ):
        response = client.get("/api/v1/products", headers=auth_headers_real)
        assert response.status_code == 200
        ids = [i["id"] for i in response.json()["items"]]
        assert product_other_tenant.id not in ids


class TestVariantWeightVolumeEndpoints:
    """Tests poids/volume sur variantes via API."""

    def test_create_variant_with_weight_volume(
        self, client: TestClient, product_with_weight, auth_headers_real
    ):
        response = client.post(
            f"/api/v1/products/{product_with_weight.id}/variants",
            json={
                "label": "Noir laqué",
                "sku": "TABLE-LOURDE-200-BLK",
                "color": "noir",
                "stock_quantity": 2,
                "available_quantity": 2,
                "weight_grams": 27000,
                "volume_cm3": 130000,
            },
            headers=auth_headers_real,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["weight_grams"] == 27000
        assert data["volume_cm3"] == 130000

    def test_get_variant_returns_weight_volume(
        self, client: TestClient, product_with_weight, variant_with_weight, auth_headers_real
    ):
        response = client.get(
            f"/api/v1/products/{product_with_weight.id}/variants/{variant_with_weight.id}",
            headers=auth_headers_real,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["weight_grams"] == 26000
        assert data["volume_cm3"] == 125000
