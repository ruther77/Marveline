"""Tests workflow approbation côté épicerie pour TransferRequest.

Couverture :
  1. list_inbound retourne les demandes ciblant le tenant épicerie courant
  2. list_inbound n'expose PAS les demandes destinées à un autre épicerie
  3. approve PENDING → APPROVED
  4. reject PENDING → REJECTED + raison stockée
  5. approve cross-tenant (mauvaise épicerie cible) → NotFound
  6. approve déjà APPROVED → NotFound (pas double-approve)
"""
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.exceptions import NotFound
from app.schemas.restaurant.transfer_request import (
    TransferRequestCreate,
    TransferRequestLineCreate,
)
from app.services.epicerie.transfer_request import EpicerieTransferRequestService
from app.services.restaurant.transfer_request import TransferRequestService

from tests.conftest import ASYNC_TEST_DATABASE_URL

_TENANT_RESTO = 3
_TENANT_RESTO_OTHER = 99
_TENANT_EPICERIE = 2
_TENANT_EPICERIE_OTHER = 98
_USER = 42


@pytest.fixture
async def async_db(test_engine):
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def _payload(target: int = _TENANT_EPICERIE) -> TransferRequestCreate:
    return TransferRequestCreate(
        target_tenant_id=target,
        notes=None,
        lignes=[
            TransferRequestLineCreate(
                designation="Tomates",
                quantity=Decimal("3.000"),
                unit="kg",
            )
        ],
    )


@pytest.mark.asyncio
async def test_list_inbound_only_returns_targeted(async_db: AsyncSession):
    """Épicerie A voit ses demandes entrantes, pas celles d'épicerie B."""
    resto_service = TransferRequestService(async_db)
    await resto_service.create(
        tenant_id=_TENANT_RESTO, created_by=_USER,
        payload=_payload(target=_TENANT_EPICERIE),
    )
    await resto_service.create(
        tenant_id=_TENANT_RESTO, created_by=_USER,
        payload=_payload(target=_TENANT_EPICERIE_OTHER),
    )

    epicerie_service = EpicerieTransferRequestService(async_db)
    items_a, total_a = await epicerie_service.list_inbound(_TENANT_EPICERIE)
    items_b, total_b = await epicerie_service.list_inbound(_TENANT_EPICERIE_OTHER)

    assert total_a == 1
    assert total_b == 1
    assert all(r.target_tenant_id == _TENANT_EPICERIE for r in items_a)
    assert all(r.target_tenant_id == _TENANT_EPICERIE_OTHER for r in items_b)


@pytest.mark.asyncio
async def test_approve_pending_to_approved(async_db: AsyncSession):
    resto_service = TransferRequestService(async_db)
    request = await resto_service.create(
        tenant_id=_TENANT_RESTO, created_by=_USER, payload=_payload(),
    )

    epicerie_service = EpicerieTransferRequestService(async_db)
    approved = await epicerie_service.approve(request.id, _TENANT_EPICERIE)
    assert approved.status == "APPROVED"


@pytest.mark.asyncio
async def test_reject_pending_with_reason(async_db: AsyncSession):
    resto_service = TransferRequestService(async_db)
    request = await resto_service.create(
        tenant_id=_TENANT_RESTO, created_by=_USER, payload=_payload(),
    )

    epicerie_service = EpicerieTransferRequestService(async_db)
    rejected = await epicerie_service.reject(
        request.id, _TENANT_EPICERIE, raison="Stock épuisé"
    )
    assert rejected.status == "REJECTED"
    assert rejected.rejection_reason == "Stock épuisé"


@pytest.mark.asyncio
async def test_approve_cross_tenant_raises_not_found(async_db: AsyncSession):
    """Épicerie B ne peut pas approuver une demande ciblant épicerie A."""
    resto_service = TransferRequestService(async_db)
    request = await resto_service.create(
        tenant_id=_TENANT_RESTO, created_by=_USER,
        payload=_payload(target=_TENANT_EPICERIE),
    )

    epicerie_service = EpicerieTransferRequestService(async_db)
    with pytest.raises(NotFound):
        await epicerie_service.approve(request.id, _TENANT_EPICERIE_OTHER)


@pytest.mark.asyncio
async def test_double_approve_raises_not_found(async_db: AsyncSession):
    resto_service = TransferRequestService(async_db)
    request = await resto_service.create(
        tenant_id=_TENANT_RESTO, created_by=_USER, payload=_payload(),
    )

    epicerie_service = EpicerieTransferRequestService(async_db)
    await epicerie_service.approve(request.id, _TENANT_EPICERIE)

    with pytest.raises(NotFound):
        await epicerie_service.approve(request.id, _TENANT_EPICERIE)


@pytest.mark.asyncio
async def test_reject_cross_tenant_raises_not_found(async_db: AsyncSession):
    resto_service = TransferRequestService(async_db)
    request = await resto_service.create(
        tenant_id=_TENANT_RESTO, created_by=_USER,
        payload=_payload(target=_TENANT_EPICERIE),
    )

    epicerie_service = EpicerieTransferRequestService(async_db)
    with pytest.raises(NotFound):
        await epicerie_service.reject(request.id, _TENANT_EPICERIE_OTHER, raison="abus")
