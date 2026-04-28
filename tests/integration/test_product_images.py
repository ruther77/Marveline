"""Tests d'intégration pour les endpoints galerie d'images produits (P2-C3)."""
import io
import pytest
from fastapi.testclient import TestClient
from app.models.product import Product
from app.models.product_image import ProductImage
from app.constants import ProductCategory, ProductCondition


@pytest.fixture
def product_with_images(test_db):
    """Produit avec 2 images existantes."""
    product = Product(
        tenant_id=1,
        name="Produit galerie test",
        sku="GALERIE-TEST-001",
        category=ProductCategory.VERRES,
        price_per_day_cents=100,
        deposit_amount_cents=200,
        stock_quantity=5,
        available_quantity=5,
        condition=ProductCondition.BON,
        is_active=True,
    )
    test_db.add(product)
    test_db.flush()
    img1 = ProductImage(tenant_id=1, product_id=product.id, url="/uploads/products/1/img1.jpg", sort_order=0, is_primary=True)
    img2 = ProductImage(tenant_id=1, product_id=product.id, url="/uploads/products/1/img2.jpg", sort_order=1, is_primary=False)
    test_db.add_all([img1, img2])
    test_db.commit()
    test_db.refresh(product)
    test_db.refresh(img1)
    test_db.refresh(img2)
    return product, img1, img2


def _make_image_file(content: bytes = b"\xff\xd8\xff" + b"\x00" * 100) -> dict:
    """Crée un faux fichier JPEG pour l'upload."""
    return {"file": ("test.jpg", io.BytesIO(content), "image/jpeg")}


class TestListProductImages:
    def test_list_returns_200(self, client: TestClient, product_with_images, auth_headers_real):
        product, img1, img2 = product_with_images
        resp = client.get(f"/api/v1/products/{product.id}/images", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["sort_order"] == 0
        assert data[0]["is_primary"] is True

    def test_list_cross_tenant_isolation(self, client: TestClient, product_with_images, auth_headers_tenant2):
        product, _, _ = product_with_images
        resp = client.get(f"/api/v1/products/{product.id}/images", headers=auth_headers_tenant2)
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert resp.json() == []

    def test_list_unknown_product_returns_404(self, client: TestClient, auth_headers_real):
        resp = client.get("/api/v1/products/999999/images", headers=auth_headers_real)
        assert resp.status_code == 404

    def test_list_unauthenticated_returns_401(self, client: TestClient, product_with_images):
        product, _, _ = product_with_images
        resp = client.get(f"/api/v1/products/{product.id}/images")
        assert resp.status_code == 401


class TestSetPrimaryImage:
    def test_set_primary_returns_200(self, client: TestClient, product_with_images, auth_headers_admin):
        product, img1, img2 = product_with_images
        resp = client.patch(
            f"/api/v1/products/{product.id}/images/{img2.id}/set-primary",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == img2.id
        assert data["is_primary"] is True

    def test_set_primary_unknown_image_returns_404(self, client: TestClient, product_with_images, auth_headers_admin):
        product, _, _ = product_with_images
        resp = client.patch(
            f"/api/v1/products/{product.id}/images/999999/set-primary",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 404


class TestDeleteProductImage:
    def test_delete_returns_204(self, client: TestClient, product_with_images, auth_headers_admin):
        product, img1, img2 = product_with_images
        resp = client.delete(
            f"/api/v1/products/{product.id}/images/{img2.id}",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 204

    def test_delete_unknown_returns_404(self, client: TestClient, product_with_images, auth_headers_admin):
        product, _, _ = product_with_images
        resp = client.delete(
            f"/api/v1/products/{product.id}/images/999999",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 404
