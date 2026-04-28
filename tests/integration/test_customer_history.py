"""Tests pour GET /customers/{id}/history."""
import pytest
from fastapi.testclient import TestClient
from app.models.customer import Customer
from app.constants import CustomerType


@pytest.fixture
def test_customer_hist(test_db):
    """Client de test pour history."""
    c = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Histor",
        last_name="Test",
        email="histor.test@example.com",
        phone="+33600000001",
        city="Lyon",
        postal_code="69001",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


def test_get_history_structure(client: TestClient, auth_headers_real, test_customer_hist):
    """GET /customers/{id}/history retourne la structure attendue."""
    response = client.get(
        f"/api/v1/customers/{test_customer_hist.id}/history",
        headers=auth_headers_real,
    )
    assert response.status_code == 200
    data = response.json()
    assert "customer" in data
    assert "reservations" in data
    assert "invoices" in data
    assert "stats" in data
    assert isinstance(data["reservations"], list)
    assert isinstance(data["invoices"], list)


def test_get_history_stats_fields(client: TestClient, auth_headers_real, test_customer_hist):
    """Les stats contiennent les champs attendus."""
    response = client.get(
        f"/api/v1/customers/{test_customer_hist.id}/history",
        headers=auth_headers_real,
    )
    assert response.status_code == 200
    stats = response.json()["stats"]
    assert "total_reservations" in stats
    assert "total_revenue_cents" in stats
    assert "last_event_date" in stats
    assert stats["total_reservations"] == 0
    assert stats["total_revenue_cents"] == 0


def test_get_history_customer_data(client: TestClient, auth_headers_real, test_customer_hist):
    """Les données du client sont correctes."""
    response = client.get(
        f"/api/v1/customers/{test_customer_hist.id}/history",
        headers=auth_headers_real,
    )
    assert response.status_code == 200
    customer = response.json()["customer"]
    assert customer["id"] == test_customer_hist.id
    assert customer["first_name"] == "Histor"
    assert customer["last_name"] == "Test"


def test_get_history_not_found(client: TestClient, auth_headers_real):
    """404 si le client n'existe pas."""
    response = client.get(
        "/api/v1/customers/999999/history",
        headers=auth_headers_real,
    )
    assert response.status_code == 404


def test_get_history_requires_auth(client: TestClient, test_customer_hist):
    """401 sans authentification."""
    response = client.get(f"/api/v1/customers/{test_customer_hist.id}/history")
    assert response.status_code == 401


def test_get_history_tenant_isolation(
    client: TestClient, auth_headers_tenant2, test_customer_hist
):
    """404 depuis un autre tenant (isolation)."""
    response = client.get(
        f"/api/v1/customers/{test_customer_hist.id}/history",
        headers=auth_headers_tenant2,
    )
    assert response.status_code == 404
