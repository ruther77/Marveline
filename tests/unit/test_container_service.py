"""Tests unitaires — schemas Container."""
import pytest
from app.schemas.container import (
    ContainerCreate,
    ContainerUpdate,
    ContainerResponse,
    ContainerAssignCreate,
    ContainerItemCreate,
)


class TestContainerSchemas:
    """Validation Pydantic des schemas Container."""

    def test_container_create_valid(self):
        data = ContainerCreate(
            name="Bac plastique 60L",
            container_type="bac",
            length_cm=60,
            width_cm=40,
            height_cm=30,
            max_weight_grams=25000,
            serial_number="BAC-001",
        )
        assert data.name == "Bac plastique 60L"
        assert data.container_type == "bac"
        assert data.max_weight_grams == 25000

    def test_container_create_minimal(self):
        data = ContainerCreate(name="Carton standard", container_type="carton")
        assert data.length_cm is None
        assert data.serial_number is None

    def test_container_create_rejects_zero_dimensions(self):
        with pytest.raises(Exception):
            ContainerCreate(name="Test", container_type="bac", length_cm=0)

    def test_container_create_rejects_negative_weight(self):
        with pytest.raises(Exception):
            ContainerCreate(name="Test", container_type="bac", max_weight_grams=-1)

    def test_container_update_partial(self):
        data = ContainerUpdate(name="Nouveau nom")
        dump = data.model_dump(exclude_unset=True)
        assert dump == {"name": "Nouveau nom"}

    def test_container_update_availability(self):
        data = ContainerUpdate(is_available=False)
        assert data.is_available is False

    def test_container_assign_create(self):
        data = ContainerAssignCreate(
            container_id=1,
            movement_id=5,
            items=[
                ContainerItemCreate(movement_item_id=10, quantity=20),
                ContainerItemCreate(movement_item_id=11, quantity=50),
            ],
        )
        assert data.container_id == 1
        assert len(data.items) == 2
        assert data.items[0].quantity == 20

    def test_container_assign_rejects_zero_quantity(self):
        with pytest.raises(Exception):
            ContainerItemCreate(movement_item_id=10, quantity=0)

    def test_container_assign_rejects_negative_ids(self):
        with pytest.raises(Exception):
            ContainerAssignCreate(container_id=-1, movement_id=5)

    def test_container_response_from_attributes(self):
        data = ContainerResponse.model_validate({
            "id": 1,
            "tenant_id": 1,
            "name": "Bac 60L",
            "container_type": "bac",
            "length_cm": 60,
            "width_cm": 40,
            "height_cm": 30,
            "max_weight_grams": 25000,
            "serial_number": "BAC-001",
            "is_available": True,
            "is_active": True,
            "notes": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        })
        assert data.id == 1
        assert data.container_type == "bac"
        assert data.is_available is True
