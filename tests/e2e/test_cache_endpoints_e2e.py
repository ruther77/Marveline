"""Tests E2E cache Redis via endpoints API.

Valide :
- Cache HIT/MISS sur GET endpoints (products, customers, reservations)
- Invalidation cache après PUT/PATCH/DELETE
- Isolation multi-tenant du cache via API
- Métriques cache hit rate exposées via /metrics
"""
import pytest
from app.models.product import Product
from app.models.customer import Customer
from app.services.cache import cache_service
from app.core.metrics import cache_hits_total, cache_misses_total


@pytest.fixture(autouse=True)
def clear_cache_and_metrics():
    """Nettoie le cache Redis et reset métriques avant chaque test."""
    cache_service.flush_all()

    # Reset métriques Prometheus (via _value._value = 0)
    for entity in ["product", "customer", "reservation", "invoice"]:
        try:
            cache_hits_total.labels(entity=entity)._value._value = 0
            cache_misses_total.labels(entity=entity)._value._value = 0
        except Exception:
            pass  # Ignore si labels n'existe pas encore

    yield

    cache_service.flush_all()


def test_product_endpoint_cache_miss_then_hit(client, test_db, test_tenant, auth_headers_real):
    """Test cache MISS puis HIT sur GET /products/{id}."""
    # Créer produit
    product = Product(
        tenant_id=test_tenant.id,
        name="Assiette Cache E2E",
        sku="E2E-CACHE-001",
        category="assiettes",
        price_per_day=300,
        available_quantity=10,
        stock_quantity=10,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)

    # Premier GET → cache MISS (query DB)
    response1 = client.get(
        f"/api/v1/products/{product.id}",
        headers=auth_headers_real
    )
    assert response1.status_code == 200
    assert response1.json()["name"] == "Assiette Cache E2E"

    # Vérifier cache rempli
    cache_key = f"product:{test_tenant.id}:{product.id}"
    cached_data = cache_service.get(cache_key)
    assert cached_data is not None
    assert cached_data["name"] == "Assiette Cache E2E"

    # Deuxième GET → cache HIT (pas de query DB)
    response2 = client.get(
        f"/api/v1/products/{product.id}",
        headers=auth_headers_real
    )
    assert response2.status_code == 200
    assert response2.json()["name"] == "Assiette Cache E2E"
    assert response2.json()["id"] == product.id


def test_product_endpoint_cache_invalidation_on_update(client, test_db, test_tenant, auth_headers_admin):
    """Test invalidation cache après PATCH /products/{id}."""
    # Créer produit
    product = Product(
        tenant_id=test_tenant.id,
        name="Produit Original",
        sku="E2E-UPDATE-001",
        category="verres",
        price_per_day=250,
        available_quantity=5,
        stock_quantity=5,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)

    # GET pour remplir cache
    response1 = client.get(
        f"/api/v1/products/{product.id}",
        headers=auth_headers_admin
    )
    assert response1.status_code == 200

    # Vérifier cache rempli
    cache_key = f"product:{test_tenant.id}:{product.id}"
    assert cache_service.get(cache_key) is not None

    # UPDATE via API (utiliser PATCH)
    response2 = client.patch(
        f"/api/v1/products/{product.id}",
        headers=auth_headers_admin,
        json={
            "name": "Produit Modifié",
        }
    )
    assert response2.status_code == 200
    assert response2.json()["name"] == "Produit Modifié"

    # Cache doit être invalidé
    assert cache_service.get(cache_key) is None

    # Prochain GET re-cache la nouvelle version
    response3 = client.get(
        f"/api/v1/products/{product.id}",
        headers=auth_headers_admin
    )
    assert response3.status_code == 200
    assert response3.json()["name"] == "Produit Modifié"
    assert cache_service.get(cache_key) is not None


def test_customer_endpoint_cache_miss_then_hit(client, test_db, test_tenant, auth_headers_real):
    """Test cache MISS puis HIT sur GET /customers/{id}."""
    # Créer customer
    customer = Customer(
        tenant_id=test_tenant.id,
        customer_type="individual",
        first_name="Jean",
        last_name="Dupont",
        email="jean.dupont.cache@example.com",
        phone="0123456789",
        company_name="Acme Corp Cache",
        address="123 rue Cache",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)

    # Premier GET → cache MISS
    response1 = client.get(
        f"/api/v1/customers/{customer.id}",
        headers=auth_headers_real
    )
    assert response1.status_code == 200
    assert response1.json()["email"] == "jean.dupont.cache@example.com"

    # Vérifier cache rempli
    cache_key = f"customer:{test_tenant.id}:{customer.id}"
    cached_data = cache_service.get(cache_key)
    assert cached_data is not None

    # Deuxième GET → cache HIT
    response2 = client.get(
        f"/api/v1/customers/{customer.id}",
        headers=auth_headers_real
    )
    assert response2.status_code == 200
    assert response2.json()["email"] == "jean.dupont.cache@example.com"


def test_cache_multi_tenant_isolation_via_api(
    client,
    test_db,
    test_tenant,
    test_tenant2,
    auth_headers_real,
    auth_headers_tenant2
):
    """Test isolation cache entre tenants via API."""
    # Créer produit pour tenant 1
    product1 = Product(
        tenant_id=test_tenant.id,
        name="Produit Tenant 1",
        sku="TENANT1-CACHE",
        category="assiettes",
        price_per_day=200,
        available_quantity=3,
        stock_quantity=3,
        is_active=True
    )
    test_db.add(product1)
    test_db.commit()
    test_db.refresh(product1)

    # Créer produit pour tenant 2
    product2 = Product(
        tenant_id=test_tenant2.id,
        name="Produit Tenant 2",
        sku="TENANT2-CACHE",
        category="verres",
        price_per_day=300,
        available_quantity=5,
        stock_quantity=5,
        is_active=True
    )
    test_db.add(product2)
    test_db.commit()
    test_db.refresh(product2)

    # Tenant 1 accède à son produit (cache MISS + rempli)
    response1 = client.get(
        f"/api/v1/products/{product1.id}",
        headers=auth_headers_real
    )
    assert response1.status_code == 200
    assert response1.json()["name"] == "Produit Tenant 1"

    # Tenant 2 accède à son produit (cache MISS + rempli)
    response2 = client.get(
        f"/api/v1/products/{product2.id}",
        headers=auth_headers_tenant2
    )
    assert response2.status_code == 200
    assert response2.json()["name"] == "Produit Tenant 2"

    # Vérifier clés cache séparées
    cache_key1 = f"product:{test_tenant.id}:{product1.id}"
    cache_key2 = f"product:{test_tenant2.id}:{product2.id}"

    cached1 = cache_service.get(cache_key1)
    cached2 = cache_service.get(cache_key2)

    assert cached1 is not None
    assert cached2 is not None
    assert cached1["name"] == "Produit Tenant 1"
    assert cached2["name"] == "Produit Tenant 2"

    # Tenant 2 tente d'accéder au produit de Tenant 1 → 404 (pas de fuite cache)
    response3 = client.get(
        f"/api/v1/products/{product1.id}",
        headers=auth_headers_tenant2
    )
    assert response3.status_code == 404


def test_cache_hit_rate_metrics_exposed(client, test_db, test_tenant, auth_headers_real):
    """Test que les métriques cache hit rate sont exposées via /metrics."""
    # Créer produit
    product = Product(
        tenant_id=test_tenant.id,
        name="Produit Metrics",
        sku="METRICS-001",
        category="couverts",
        price_per_day=150,
        available_quantity=2,
        stock_quantity=2,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)

    # Faire 1 MISS + 3 HITs → hit rate = 3/4 = 0.75
    client.get(f"/api/v1/products/{product.id}", headers=auth_headers_real)  # MISS
    client.get(f"/api/v1/products/{product.id}", headers=auth_headers_real)  # HIT
    client.get(f"/api/v1/products/{product.id}", headers=auth_headers_real)  # HIT
    client.get(f"/api/v1/products/{product.id}", headers=auth_headers_real)  # HIT

    # Récupérer métriques Prometheus
    response = client.get("/metrics")
    assert response.status_code == 200

    metrics_text = response.text

    # Vérifier que les métriques cache sont présentes
    assert 'cache_hits_total{entity="product"}' in metrics_text
    assert 'cache_misses_total{entity="product"}' in metrics_text
    assert 'cache_hit_rate{entity="product"}' in metrics_text

    # Vérifier valeurs (1 miss + 3 hits = 4 total)
    assert 'cache_hits_total{entity="product"} 3.0' in metrics_text
    assert 'cache_misses_total{entity="product"} 1.0' in metrics_text

    # Hit rate devrait être ~0.75 (3/4)
    # Note: valeur exacte peut varier légèrement selon timing
    assert 'cache_hit_rate{entity="product"} 0.75' in metrics_text


def test_cache_delete_endpoint_invalidation(client, test_db, test_tenant, auth_headers_admin):
    """Test invalidation cache après DELETE (soft delete) endpoint."""
    # Créer produit
    product = Product(
        tenant_id=test_tenant.id,
        name="Produit à Supprimer",
        sku="DELETE-CACHE-001",
        category="nappes",
        price_per_day=400,
        available_quantity=1,
        stock_quantity=1,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)

    # GET pour remplir cache
    response1 = client.get(
        f"/api/v1/products/{product.id}",
        headers=auth_headers_admin
    )
    assert response1.status_code == 200

    # Vérifier cache rempli
    cache_key = f"product:{test_tenant.id}:{product.id}"
    assert cache_service.get(cache_key) is not None

    # DELETE (soft delete)
    response2 = client.delete(
        f"/api/v1/products/{product.id}",
        headers=auth_headers_admin
    )
    assert response2.status_code == 204  # No Content pour DELETE

    # Cache doit être invalidé
    assert cache_service.get(cache_key) is None

    # GET après delete → 404 (produit inactif)
    response3 = client.get(
        f"/api/v1/products/{product.id}",
        headers=auth_headers_admin
    )
    assert response3.status_code == 404
