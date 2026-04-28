"""Tests isolation cross-tenant TransferRequest (BACK-TRANSFER-RESTO-01).

Multi-tenant strict (A1) : un tenant restaurant ne peut JAMAIS lire ou
modifier les demandes de transfert d'un autre tenant.

Couverture :
  1. create scope tenant_id correct + ligne attachée
  2. self-target rejeté (CHECK SQL ou pre-validation)
  3. get cross-tenant → None
  4. list cross-tenant → ne retourne pas les demandes d'autrui
  5. cancel cross-tenant → None (refus silencieux)
  6. cancel d'une demande déjà CANCELLED → None (état invalide)
"""
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.repositories.restaurant.transfer_request import AsyncTransferRequestRepo
from app.schemas.restaurant.transfer_request import (
    TransferRequestCreate,
    TransferRequestLineCreate,
)
from app.services.restaurant.transfer_request import TransferRequestService

from tests.conftest import ASYNC_TEST_DATABASE_URL

_TENANT_RESTO_A = 3
_TENANT_RESTO_B = 99
_TENANT_EPICERIE = 2
_USER_ID = 42


# ── Fixture ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def async_db(test_engine):
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _payload(target_tenant_id: int = _TENANT_EPICERIE, n_lignes: int = 1) -> TransferRequestCreate:
    return TransferRequestCreate(
        target_tenant_id=target_tenant_id,
        notes=None,
        lignes=[
            TransferRequestLineCreate(
                designation=f"Ingrédient {i}",
                quantity=Decimal("2.500"),
                unit="kg",
            )
            for i in range(n_lignes)
        ],
    )


# ── Tests service ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_scopes_tenant_and_attaches_lines(async_db: AsyncSession):
    """create() : tenant_id correct, status PENDING, lignes attachées."""
    service = TransferRequestService(async_db)
    request = await service.create(
        tenant_id=_TENANT_RESTO_A,
        created_by=_USER_ID,
        payload=_payload(n_lignes=2),
    )
    assert request.tenant_id == _TENANT_RESTO_A
    assert request.target_tenant_id == _TENANT_EPICERIE
    assert request.status == "PENDING"
    assert request.created_by == _USER_ID
    assert len(request.lignes) == 2


@pytest.mark.asyncio
async def test_create_self_target_rejected(async_db: AsyncSession):
    """create() avec target_tenant_id == tenant_id → ValueError."""
    service = TransferRequestService(async_db)
    with pytest.raises(ValueError, match="différent"):
        await service.create(
            tenant_id=_TENANT_RESTO_A,
            created_by=_USER_ID,
            payload=_payload(target_tenant_id=_TENANT_RESTO_A),
        )


@pytest.mark.asyncio
async def test_get_cross_tenant_returns_none(async_db: AsyncSession):
    """repo.get() avec mauvais tenant_id → None."""
    service = TransferRequestService(async_db)
    request = await service.create(
        tenant_id=_TENANT_RESTO_A,
        created_by=_USER_ID,
        payload=_payload(),
    )

    repo = AsyncTransferRequestRepo(async_db)
    found_a = await repo.get(request.id, _TENANT_RESTO_A)
    found_b = await repo.get(request.id, _TENANT_RESTO_B)

    assert found_a is not None
    assert found_b is None


@pytest.mark.asyncio
async def test_list_isolates_tenants(async_db: AsyncSession):
    """list_for_tenant(A) ne retourne pas les demandes du tenant B."""
    service = TransferRequestService(async_db)
    await service.create(
        tenant_id=_TENANT_RESTO_A, created_by=_USER_ID, payload=_payload(),
    )
    await service.create(
        tenant_id=_TENANT_RESTO_B, created_by=_USER_ID, payload=_payload(),
    )

    items_a, total_a = await service.list_for_tenant(_TENANT_RESTO_A)
    items_b, total_b = await service.list_for_tenant(_TENANT_RESTO_B)

    assert total_a == 1
    assert total_b == 1
    assert all(r.tenant_id == _TENANT_RESTO_A for r in items_a)
    assert all(r.tenant_id == _TENANT_RESTO_B for r in items_b)


@pytest.mark.asyncio
async def test_cancel_cross_tenant_raises_not_found(async_db: AsyncSession):
    """cancel(B) sur demande de A → NotFound, demande NON modifiée."""
    from app.core.exceptions import NotFound

    service = TransferRequestService(async_db)
    request = await service.create(
        tenant_id=_TENANT_RESTO_A, created_by=_USER_ID, payload=_payload(),
    )

    with pytest.raises(NotFound):
        await service.cancel(request.id, _TENANT_RESTO_B, raison="test")

    # La demande est toujours PENDING côté tenant A
    repo = AsyncTransferRequestRepo(async_db)
    still = await repo.get(request.id, _TENANT_RESTO_A)
    assert still is not None
    assert still.status == "PENDING"


@pytest.mark.asyncio
async def test_cancel_already_cancelled_raises_not_found(async_db: AsyncSession):
    """cancel d'une demande CANCELLED → NotFound (état invalide)."""
    from app.core.exceptions import NotFound

    service = TransferRequestService(async_db)
    request = await service.create(
        tenant_id=_TENANT_RESTO_A, created_by=_USER_ID, payload=_payload(),
    )
    await service.cancel(request.id, _TENANT_RESTO_A, raison="première annulation")

    with pytest.raises(NotFound):
        await service.cancel(request.id, _TENANT_RESTO_A, raison="seconde tentative")
