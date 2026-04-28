"""Tests d'intégration — endpoints contenants + anti cross-tenant."""
import pytest
from fastapi.testclient import TestClient
from app.models.container import Container


@pytest.fixture
def test_container(test_db):
    """Contenant de test (tenant_id=1)."""
    c = Container(
        tenant_id=1,
        name="Bac plastique 60L",
        container_type="bac",
        length_cm=60,
        width_cm=40,
        height_cm=30,
        max_weight_grams=25000,
        serial_number="BAC-T1-001",
        is_available=True,
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def container_other_tenant(test_db):
    """Contenant d'un autre tenant (tenant_id=2)."""
    c = Container(
        tenant_id=2,
        name="Palette autre tenant",
        container_type="palette",
        serial_number="PAL-T2-001",
        is_available=True,
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


class TestContainerCRUD:
    """Tests CRUD contenants."""

    def test_create_container(self, client: TestClient, auth_headers_real):
        response = client.post(
            "/api/v1/containers",
            json={
                "name": "Caisse bois 80L",
                "container_type": "caisse",
                "length_cm": 80,
                "width_cm": 50,
                "height_cm": 40,
                "max_weight_grams": 40000,
                "serial_number": "CAISSE-001",
            },
            headers=auth_headers_real,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Caisse bois 80L"
        assert data["container_type"] == "caisse"
        assert data["is_available"] is True
        assert data["serial_number"] == "CAISSE-001"

    def test_create_container_invalid_type(self, client: TestClient, auth_headers_real):
        response = client.post(
            "/api/v1/containers",
            json={"name": "Test", "container_type": "sac"},
            headers=auth_headers_real,
        )
        assert response.status_code == 422

    def test_create_container_duplicate_serial(
        self, client: TestClient, test_container, auth_headers_real
    ):
        response = client.post(
            "/api/v1/containers",
            json={
                "name": "Autre bac",
                "container_type": "bac",
                "serial_number": "BAC-T1-001",
            },
            headers=auth_headers_real,
        )
        assert response.status_code == 409

    def test_get_container(self, client: TestClient, test_container, auth_headers_real):
        response = client.get(
            f"/api/v1/containers/{test_container.id}",
            headers=auth_headers_real,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Bac plastique 60L"
        assert data["length_cm"] == 60

    def test_list_containers(self, client: TestClient, test_container, auth_headers_real):
        response = client.get("/api/v1/containers", headers=auth_headers_real)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(c["id"] == test_container.id for c in data["items"])

    def test_update_container(self, client: TestClient, test_container, auth_headers_real):
        response = client.patch(
            f"/api/v1/containers/{test_container.id}",
            json={"name": "Bac renforcé 60L", "is_available": False},
            headers=auth_headers_real,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Bac renforcé 60L"
        assert data["is_available"] is False

    def test_delete_container(self, client: TestClient, test_container, auth_headers_real):
        response = client.delete(
            f"/api/v1/containers/{test_container.id}",
            headers=auth_headers_real,
        )
        assert response.status_code == 204
        # Vérifier soft delete
        response2 = client.get(
            f"/api/v1/containers/{test_container.id}",
            headers=auth_headers_real,
        )
        assert response2.status_code == 404


class TestContainerCrossTenant:
    """Anti cross-tenant."""

    def test_cannot_access_other_tenant_container(
        self, client: TestClient, container_other_tenant, auth_headers_real
    ):
        response = client.get(
            f"/api/v1/containers/{container_other_tenant.id}",
            headers=auth_headers_real,
        )
        assert response.status_code == 404

    def test_list_excludes_other_tenant(
        self, client: TestClient, container_other_tenant, test_container, auth_headers_real
    ):
        response = client.get("/api/v1/containers", headers=auth_headers_real)
        assert response.status_code == 200
        ids = [c["id"] for c in response.json()["items"]]
        assert container_other_tenant.id not in ids

    def test_cannot_update_other_tenant_container(
        self, client: TestClient, container_other_tenant, auth_headers_real
    ):
        response = client.patch(
            f"/api/v1/containers/{container_other_tenant.id}",
            json={"name": "Hack"},
            headers=auth_headers_real,
        )
        assert response.status_code == 404

    def test_cannot_delete_other_tenant_container(
        self, client: TestClient, container_other_tenant, auth_headers_real
    ):
        response = client.delete(
            f"/api/v1/containers/{container_other_tenant.id}",
            headers=auth_headers_real,
        )
        assert response.status_code == 404
