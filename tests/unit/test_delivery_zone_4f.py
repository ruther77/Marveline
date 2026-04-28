"""Tests unitaires — Phase 4F DeliveryZone.

Tests couvrant :
- Modèle DeliveryZone (champs, contraintes)
- Schema DeliveryZoneCreate (validation department_code)
- Schema DeliveryZoneResponse (from_attributes)
- Service DeliveryZoneService (CRUD, unicité code, 404, 409)
- Routing endpoints /delivery-zones (enregistrement, 401 sans token)
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ═══════════════════════════════════════════════════════════════════════════════
# Modèle
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeliveryZoneModel:
    def test_model_importable(self):
        from app.models.delivery_zone import DeliveryZone
        assert DeliveryZone.__tablename__ == "delivery_zones"

    def test_model_in_models_init(self):
        from app.models import DeliveryZone
        assert DeliveryZone is not None

    def test_model_has_required_columns(self):
        from app.models.delivery_zone import DeliveryZone
        from sqlalchemy import inspect
        mapper = inspect(DeliveryZone)
        col_names = {c.name for c in mapper.columns}
        expected = {
            "id", "tenant_id", "department_code", "department_name",
            "delivery_fee_cents", "sunday_surcharge_cents", "notes",
            "is_active", "created_at", "updated_at",
        }
        assert expected.issubset(col_names)

    def test_model_unique_constraint_exists(self):
        from app.models.delivery_zone import DeliveryZone
        from sqlalchemy import inspect
        mapper = inspect(DeliveryZone)
        uq_names = [uc.name for uc in mapper.mapper.persist_selectable.constraints
                    if hasattr(uc, "name") and uc.name]
        assert any("uq_delivery_zone_tenant_dept" in (n or "") for n in uq_names)


# ═══════════════════════════════════════════════════════════════════════════════
# Schémas
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeliveryZoneSchema:
    def test_create_valid(self):
        from app.schemas.delivery_zone import DeliveryZoneCreate
        data = DeliveryZoneCreate(
            department_code="60",
            department_name="Oise",
            delivery_fee_cents=5000,
            sunday_surcharge_cents=2000,
        )
        assert data.department_code == "60"
        assert data.delivery_fee_cents == 5000

    def test_create_default_fees_zero(self):
        from app.schemas.delivery_zone import DeliveryZoneCreate
        data = DeliveryZoneCreate(department_code="80", department_name="Somme")
        assert data.delivery_fee_cents == 0
        assert data.sunday_surcharge_cents == 0
        assert data.notes is None

    def test_create_invalid_code_not_numeric(self):
        from pydantic import ValidationError
        from app.schemas.delivery_zone import DeliveryZoneCreate
        with pytest.raises(ValidationError):
            DeliveryZoneCreate(department_code="AB", department_name="Test")

    def test_create_negative_fee_rejected(self):
        from pydantic import ValidationError
        from app.schemas.delivery_zone import DeliveryZoneCreate
        with pytest.raises(ValidationError):
            DeliveryZoneCreate(
                department_code="60",
                department_name="Oise",
                delivery_fee_cents=-1,
            )

    def test_update_partial(self):
        from app.schemas.delivery_zone import DeliveryZoneUpdate
        data = DeliveryZoneUpdate(delivery_fee_cents=8000)
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"delivery_fee_cents": 8000}

    def test_response_from_attributes(self):
        from datetime import datetime, timezone
        from app.schemas.delivery_zone import DeliveryZoneResponse
        mock = MagicMock()
        mock.id = 1
        mock.tenant_id = 1
        mock.department_code = "60"
        mock.department_name = "Oise"
        mock.delivery_fee_cents = 5000
        mock.sunday_surcharge_cents = 2000
        mock.notes = None
        mock.is_active = True
        mock.created_at = datetime.now(timezone.utc)
        mock.updated_at = datetime.now(timezone.utc)

        resp = DeliveryZoneResponse.model_validate(mock)
        assert resp.department_code == "60"
        assert resp.delivery_fee_cents == 5000


# ═══════════════════════════════════════════════════════════════════════════════
# Service
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeliveryZoneService:
    def _make_service(self):
        from app.services.delivery_zone import DeliveryZoneService
        db = MagicMock()
        svc = DeliveryZoneService(db)
        svc.repo = MagicMock()
        return svc

    @pytest.mark.asyncio
    async def test_list_zones_delegates_to_repo(self):
        from unittest.mock import AsyncMock
        svc = self._make_service()
        svc.repo.list_active = AsyncMock(return_value=[])
        svc.repo.count_active = AsyncMock(return_value=0)
        items, total = await svc.list_zones(tenant_id=1, skip=0, limit=100)
        svc.repo.list_active.assert_called_once_with(1, skip=0, limit=100)
        svc.repo.count_active.assert_called_once_with(1)
        assert items == []
        assert total == 0

    async def test_get_zone_found(self):
        from unittest.mock import AsyncMock
        svc = self._make_service()
        zone = MagicMock()
        svc.repo.get_by_id = AsyncMock(return_value=zone)
        result = await svc.get_zone(1, 1)
        assert result is zone

    async def test_get_zone_not_found_raises_404(self):
        from fastapi import HTTPException
        from unittest.mock import AsyncMock
        svc = self._make_service()
        svc.repo.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc:
            await svc.get_zone(99, 1)
        assert exc.value.status_code == 404

    async def test_create_zone_success(self):
        from unittest.mock import AsyncMock
        svc = self._make_service()
        svc.repo.code_exists = AsyncMock(return_value=False)
        from app.schemas.delivery_zone import DeliveryZoneCreate
        data = DeliveryZoneCreate(department_code="60", department_name="Oise")
        zone = await svc.create_zone(data, tenant_id=1)
        svc.db.add.assert_called_once()
        assert zone.department_code == "60"
        assert zone.tenant_id == 1

    async def test_create_zone_duplicate_code_raises_409(self):
        from fastapi import HTTPException
        from unittest.mock import AsyncMock
        svc = self._make_service()
        svc.repo.code_exists = AsyncMock(return_value=True)
        from app.schemas.delivery_zone import DeliveryZoneCreate
        data = DeliveryZoneCreate(department_code="60", department_name="Oise")
        with pytest.raises(HTTPException) as exc:
            await svc.create_zone(data, tenant_id=1)
        assert exc.value.status_code == 409

    async def test_update_zone_patches_fields(self):
        from unittest.mock import AsyncMock
        svc = self._make_service()
        zone = MagicMock()
        svc.repo.get_by_id = AsyncMock(return_value=zone)
        from app.schemas.delivery_zone import DeliveryZoneUpdate
        data = DeliveryZoneUpdate(delivery_fee_cents=9000)
        await svc.update_zone(1, data, tenant_id=1)
        assert zone.delivery_fee_cents == 9000

    async def test_delete_zone_calls_soft_delete(self):
        from unittest.mock import AsyncMock
        svc = self._make_service()
        zone = MagicMock()
        svc.repo.get_by_id = AsyncMock(return_value=zone)
        await svc.delete_zone(1, tenant_id=1)
        zone.soft_delete.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Routing & Auth
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeliveryZoneRouting:
    def test_route_registered(self):
        routes = [r.path for r in app.routes]
        assert any("delivery-zones" in r for r in routes)

    def test_list_requires_auth(self):
        client = TestClient(app)
        resp = client.get("/api/v1/delivery-zones")
        assert resp.status_code == 401

    def test_get_requires_auth(self):
        client = TestClient(app)
        resp = client.get("/api/v1/delivery-zones/1")
        assert resp.status_code == 401

    def test_create_requires_auth(self):
        client = TestClient(app)
        resp = client.post("/api/v1/delivery-zones", json={
            "department_code": "60",
            "department_name": "Oise",
        })
        assert resp.status_code == 401

    def test_update_requires_auth(self):
        client = TestClient(app)
        resp = client.patch("/api/v1/delivery-zones/1", json={})
        assert resp.status_code == 401

    def test_delete_requires_auth(self):
        client = TestClient(app)
        resp = client.delete("/api/v1/delivery-zones/1")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# Repository dans models/__init__.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeliveryZoneRepository:
    def test_repo_importable_from_init(self):
        from app.repositories import DeliveryZoneRepository
        assert DeliveryZoneRepository is not None

    def test_repo_list_active_query(self):
        from unittest.mock import MagicMock, patch
        from app.repositories.delivery_zone import DeliveryZoneRepository

        db = MagicMock()
        db.execute.return_value.scalars.return_value.all.return_value = []
        repo = DeliveryZoneRepository(db)
        result = repo.list_active(tenant_id=1)
        assert result == []

    def test_repo_code_exists_false(self):
        from app.repositories.delivery_zone import DeliveryZoneRepository
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = None
        repo = DeliveryZoneRepository(db)
        assert repo.code_exists("60", tenant_id=1) is False

    def test_repo_code_exists_true(self):
        from app.repositories.delivery_zone import DeliveryZoneRepository
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = MagicMock()
        repo = DeliveryZoneRepository(db)
        assert repo.code_exists("60", tenant_id=1) is True
