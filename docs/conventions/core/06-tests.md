# Conventions — Tests

## Pyramide

- **70% unitaires** : services, validators, logique pure
- **20% intégration** : endpoints FastAPI avec DB réelle
- **10% E2E** : workflows critiques Playwright

Seuils : min **80%** global, critiques (auth, billing, tenant isolation) **95%**

## Structure Tests Intégration

```python
import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

@pytest.mark.asyncio
async def test_create_product(client: AsyncClient, test_tenant, auth_headers):
    response = await client.post(
        "/api/v1/products/",
        json={"name": "Test Product", "price_cents": 1500, "category_id": 1},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Product"
    assert data["price_cents"] == 1500

@pytest.mark.asyncio
async def test_create_product_unauthorized(client: AsyncClient):
    response = await client.post("/api/v1/products/", json={"name": "x"})
    assert response.status_code == 401
```

## Tests Anti-Cross-Tenant (Obligatoire)

```python
@pytest.mark.asyncio
async def test_cannot_access_other_tenant_product(
    client: AsyncClient,
    tenant_a_headers,
    tenant_b_product,
):
    """Tenant A ne peut pas voir les produits de Tenant B"""
    response = await client.get(
        f"/api/v1/products/{tenant_b_product.id}",
        headers=tenant_a_headers,
    )
    assert response.status_code == 404  # pas 403 — ne pas révéler l'existence
```

## db.flush() Obligatoire

```python
# Session test : autoflush=False
def test_something(db: Session):
    product = Product(tenant_id=1, name="test", price_cents=1000)
    db.add(product)
    db.flush()  # OBLIGATOIRE — sans flush, les queries suivantes voient l'état pré-mutation

    # Maintenant on peut requêter
    result = db.query(Product).filter(Product.id == product.id).first()
    assert result is not None
```

## Tests Unitaires Services

```python
from unittest.mock import MagicMock, patch

def test_product_service_create():
    mock_db = MagicMock()
    mock_repo = MagicMock()

    with patch("app.services.product.ProductRepository", return_value=mock_repo):
        service = ProductService(mock_db)
        mock_repo.find_by_name.return_value = None
        mock_repo.create.return_value = Product(id=1, name="Test", price_cents=1000)

        result = service.create(tenant_id=1, data=ProductCreate(name="Test", price_cents=1000))
        assert result.name == "Test"
```

## Tests E2E Playwright

```python
# tests/e2e/products.spec.ts
import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
    // Cleanup obligatoire
    await page.evaluate(() => localStorage.clear());
    // Reset DB + Redis via API de test
});

test('create product', async ({ page }) => {
    await page.goto('/products');
    await page.click('button:has-text("Nouveau produit")');
    await page.fill('input[name="name"]', 'Mon Produit');
    await page.click('button:has-text("Créer")');
    await expect(page.locator('text=Mon Produit')).toBeVisible();
});
```

## Cleanup E2E beforeEach

```typescript
test.beforeEach(async ({ page, request }) => {
    // Reset DB
    await request.post('/api/test/reset-db');
    // Reset Redis
    await request.post('/api/test/flush-redis');
    // Clear auth
    await page.evaluate(() => {
        localStorage.clear();
        // DELETE FROM mfa_devices dans le test setup
    });
    await page.context().clearCookies();
});
```

## TestContainers (Tests DB Isolés)

```python
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16") as pg:
        yield pg

@pytest.fixture
def isolated_db(postgres_container):
    engine = create_engine(postgres_container.get_connection_url())
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
```

## Property-Based Testing (Hypothesis)

```python
from hypothesis import given, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant

@given(st.integers(min_value=0, max_value=1_000_000))
def test_price_cents_roundtrip(price_cents: int):
    schema = ProductResponse(price_cents=price_cents, ...)
    assert int(schema.price_euros * 100) == price_cents
```

## Flaky Tests

```python
# Mettre en quarantaine avec @pytest.mark.flaky (ou skip conditionnel)
@pytest.mark.skip(reason="FLAKY: timing issue with Redis pubsub — tracked in #123")
async def test_realtime_notification():
    ...
```

## Règles

- `@pytest.mark.asyncio` obligatoire sur tous les tests async (mode strict)
- `autoflush=False` sur session test → `db.flush()` après toute mutation ORM
- Rate limit login = 5 req/min → clear `rate_limit:*` Redis dans les tests
- Mocks minimum — préférer implémentations réelles avec TestContainers
- Tests anti-cross-tenant obligatoires sur tout endpoint métier (violation = P0)
- Coverage fail-under=80 → exit 1 (attendu, pas un bug)
