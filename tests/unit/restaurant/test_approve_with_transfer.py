"""Tests approve_with_transfer — résolveur intégré au workflow TransferRequest.

Couverture :
  1. preview_resolution : ligne résolvable → items + couverture complète
  2. preview_resolution : ligne sans ingredient_restaurant_id → unresolvable_line_ids
  3. preview_resolution : déficit partiel → any_deficit = True
  4. approve_with_transfer auto → crée InternalTransfer avec lignes résolues
  5. approve_with_transfer avec overrides → utilise les overrides, ignore résolveur
  6. approve_with_transfer déjà approuvé → BadRequest
  7. approve_with_transfer cross-tenant → NotFound
  8. approve_with_transfer déficit → warnings + transfer créé quand même
"""
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.exceptions import BadRequest, NotFound
from app.models.account import Account
from app.models.epicerie.internal_transfer import InternalTransfer, InternalTransferLine
from app.models.epicerie.produit import EpicerieProduit
from app.models.epicerie.stock import EpicerieStock
from app.models.restaurant.ingredient_epicerie_mapping import IngredientEpicerieMapping
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.schemas.restaurant.ingredient_epicerie_mapping import (
    ApproveOverrideLine,
    ApproveWithTransferRequest,
)
from app.schemas.restaurant.transfer_request import (
    TransferRequestCreate,
    TransferRequestLineCreate,
)
from app.services.epicerie.transfer_request import EpicerieTransferRequestService
from app.services.restaurant.transfer_request import TransferRequestService

from tests.conftest import ASYNC_TEST_DATABASE_URL

_USER = 42  # valeur placeholder pour TransferRequest.created_by (pas de FK)

_TENANT_RESTO = 3
_TENANT_RESTO_OTHER = 99
_TENANT_EPICERIE = 2
_TENANT_EPICERIE_OTHER = 98


async def _seed_account(db: AsyncSession) -> int:
    """Crée un compte test pour renseigner les FK created_by."""
    import uuid
    suffix = uuid.uuid4().hex[:8]
    account = Account(
        email=f"approve-test-{suffix}@carocorp.local",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        first_name="Approve",
        last_name="Test",
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return account.id


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
async def async_db(test_engine):
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _mk_ingredient(
    db: AsyncSession, nom: str = "Huile", tenant_id: int = _TENANT_RESTO,
) -> IngredientRestaurant:
    ingr = IngredientRestaurant(
        tenant_id=tenant_id, nom=nom, unite_stock="L",
        stock_actuel=Decimal("0"), stock_alerte=Decimal("0"),
    )
    db.add(ingr)
    await db.flush()
    return ingr


async def _mk_produit(
    db: AsyncSession, designation: str, stock_qte: Decimal,
    tenant_id: int = _TENANT_EPICERIE,
) -> EpicerieProduit:
    prod = EpicerieProduit(
        tenant_id=tenant_id, designation_clean=designation,
        unite_vente="U", prix_achat_cts=500, prix_unitaire_cts=800,
        taux_tva=2000,
    )
    db.add(prod)
    await db.flush()
    db.add(EpicerieStock(
        tenant_id=tenant_id, produit_id=prod.id,
        quantite=stock_qte, seuil_alerte=Decimal("0"),
    ))
    await db.flush()
    return prod


async def _mk_mapping(
    db: AsyncSession, ingr_id: int, prod_id: int,
    ordre: int = 0, facteur: Decimal = Decimal("1"),
) -> IngredientEpicerieMapping:
    m = IngredientEpicerieMapping(
        tenant_id=_TENANT_RESTO,
        ingredient_id=ingr_id, produit_id=prod_id,
        ordre=ordre, facteur_conv=facteur,
    )
    db.add(m)
    await db.flush()
    return m


async def _mk_request(
    db: AsyncSession, ingredient_id: int, qte: Decimal = Decimal("10"),
    created_by: int = 42,
) -> int:
    service = TransferRequestService(db)
    req = await service.create(
        tenant_id=_TENANT_RESTO, created_by=created_by,
        payload=TransferRequestCreate(
            target_tenant_id=_TENANT_EPICERIE, notes=None,
            lignes=[TransferRequestLineCreate(
                designation="demande ingr",
                quantity=qte, unit="L",
                ingredient_restaurant_id=ingredient_id,
            )],
        ),
    )
    return req.id


# ── preview_resolution ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_preview_resolution_ligne_resolvable(async_db: AsyncSession):
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db, "Bidon 5L", Decimal("10"))
    await _mk_mapping(async_db, ingr.id, prod.id, ordre=0, facteur=Decimal("5"))
    req_id = await _mk_request(async_db, ingr.id, Decimal("20"))

    service = EpicerieTransferRequestService(async_db)
    preview = await service.preview_resolution(req_id, _TENANT_EPICERIE)

    assert preview.request_id == req_id
    assert len(preview.lines) == 1
    line = preview.lines[0]
    assert line.ingredient_restaurant_id == ingr.id
    assert line.qte_besoin == Decimal("20")
    assert line.couverture_complete is True
    assert line.deficit == Decimal("0")
    assert len(line.items) == 1
    assert line.items[0].produit_id == prod.id
    # 20 L / facteur 5 = 4 bidons
    assert line.items[0].qte_prelevee_unites_vente == Decimal("4")
    assert preview.any_deficit is False


@pytest.mark.asyncio
async def test_preview_resolution_ligne_sans_ingredient(async_db: AsyncSession):
    """Ligne texte libre (sans ingredient_restaurant_id) → unresolvable."""
    # Création manuelle d'une request avec ligne texte libre
    resto_service = TransferRequestService(async_db)
    req = await resto_service.create(
        tenant_id=_TENANT_RESTO, created_by=_USER,
        payload=TransferRequestCreate(
            target_tenant_id=_TENANT_EPICERIE, notes=None,
            lignes=[TransferRequestLineCreate(
                designation="texte libre sans FK",
                quantity=Decimal("5"), unit="kg",
                ingredient_restaurant_id=None,
            )],
        ),
    )

    service = EpicerieTransferRequestService(async_db)
    preview = await service.preview_resolution(req.id, _TENANT_EPICERIE)

    assert preview.lines == []
    assert len(preview.unresolvable_line_ids) == 1
    assert preview.any_deficit is False


@pytest.mark.asyncio
async def test_preview_resolution_deficit(async_db: AsyncSession):
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db, "Bouteille 1L", Decimal("3"))  # 3L
    await _mk_mapping(async_db, ingr.id, prod.id, ordre=0, facteur=Decimal("1"))
    req_id = await _mk_request(async_db, ingr.id, Decimal("10"))

    service = EpicerieTransferRequestService(async_db)
    preview = await service.preview_resolution(req_id, _TENANT_EPICERIE)

    assert preview.any_deficit is True
    assert preview.lines[0].deficit == Decimal("7")
    assert preview.lines[0].couverture_complete is False


# ── approve_with_transfer ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_with_transfer_auto_cree_lignes_resolues(async_db: AsyncSession):
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db, "Bidon 5L", Decimal("10"))
    await _mk_mapping(async_db, ingr.id, prod.id, ordre=0, facteur=Decimal("5"))
    req_id = await _mk_request(async_db, ingr.id, Decimal("10"))

    account_id = await _seed_account(async_db)
    service = EpicerieTransferRequestService(async_db)
    result = await service.approve_with_transfer(
        request_id=req_id,
        target_tenant_id=_TENANT_EPICERIE,
        user_id=account_id,
        payload=ApproveWithTransferRequest(),
    )

    assert result.transfer_id > 0
    assert result.warnings == []

    # Vérifier que le transfert a bien été créé avec la ligne résolue
    stmt = select(InternalTransfer).where(InternalTransfer.id == result.transfer_id)
    transfer = (await async_db.execute(stmt)).scalar_one()
    assert transfer.tenant_id == _TENANT_EPICERIE
    assert transfer.dest_tenant_id == _TENANT_RESTO
    assert transfer.status == "PENDING"

    lines = await async_db.execute(
        select(InternalTransferLine).where(InternalTransferLine.transfer_id == transfer.id)
    )
    lines_list = list(lines.scalars())
    assert len(lines_list) == 1
    assert lines_list[0].produit_id == prod.id
    assert lines_list[0].ingredient_id == ingr.id
    # 10 L / facteur 5 = 2 bidons
    assert float(lines_list[0].quantite) == 2.0


@pytest.mark.asyncio
async def test_approve_with_transfer_overrides(async_db: AsyncSession):
    """Overrides manuels → ignore le résolveur."""
    ingr = await _mk_ingredient(async_db)
    prod_auto = await _mk_produit(async_db, "Auto", Decimal("50"))
    prod_override = await _mk_produit(async_db, "Manuel", Decimal("50"))
    await _mk_mapping(async_db, ingr.id, prod_auto.id, ordre=0, facteur=Decimal("1"))
    req_id = await _mk_request(async_db, ingr.id, Decimal("5"))

    account_id = await _seed_account(async_db)
    service = EpicerieTransferRequestService(async_db)
    result = await service.approve_with_transfer(
        request_id=req_id,
        target_tenant_id=_TENANT_EPICERIE,
        user_id=account_id,
        payload=ApproveWithTransferRequest(
            overrides=[ApproveOverrideLine(
                produit_id=prod_override.id,
                ingredient_id=ingr.id,
                quantite=Decimal("3"),
                unite="U",
                prix_unitaire=1000,
                tva_pct=2000,
            )],
        ),
    )

    stmt = select(InternalTransferLine).where(
        InternalTransferLine.transfer_id == result.transfer_id
    )
    lines_list = list((await async_db.execute(stmt)).scalars())
    assert len(lines_list) == 1
    assert lines_list[0].produit_id == prod_override.id
    assert lines_list[0].prix_unitaire == 1000
    assert float(lines_list[0].quantite) == 3.0


@pytest.mark.asyncio
async def test_approve_with_transfer_deja_approuve(async_db: AsyncSession):
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db, "P", Decimal("10"))
    await _mk_mapping(async_db, ingr.id, prod.id, ordre=0, facteur=Decimal("1"))
    req_id = await _mk_request(async_db, ingr.id, Decimal("5"))

    account_id = await _seed_account(async_db)
    service = EpicerieTransferRequestService(async_db)
    await service.approve_with_transfer(
        request_id=req_id, target_tenant_id=_TENANT_EPICERIE,
        user_id=account_id, payload=ApproveWithTransferRequest(),
    )
    await async_db.commit()

    with pytest.raises(BadRequest):
        await service.approve_with_transfer(
            request_id=req_id, target_tenant_id=_TENANT_EPICERIE,
            user_id=account_id, payload=ApproveWithTransferRequest(),
        )


@pytest.mark.asyncio
async def test_approve_with_transfer_cross_tenant(async_db: AsyncSession):
    """Autre tenant épicerie → NotFound silencieux."""
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db, "P", Decimal("10"))
    await _mk_mapping(async_db, ingr.id, prod.id, ordre=0, facteur=Decimal("1"))
    req_id = await _mk_request(async_db, ingr.id, Decimal("5"))

    account_id = await _seed_account(async_db)
    service = EpicerieTransferRequestService(async_db)
    with pytest.raises(NotFound):
        await service.approve_with_transfer(
            request_id=req_id,
            target_tenant_id=_TENANT_EPICERIE_OTHER,
            user_id=account_id, payload=ApproveWithTransferRequest(),
        )


@pytest.mark.asyncio
async def test_approve_with_transfer_deficit_signale(async_db: AsyncSession):
    """Couverture partielle → warning + transfer créé avec les lignes résolues."""
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db, "Petit stock", Decimal("2"))  # 2L seulement
    await _mk_mapping(async_db, ingr.id, prod.id, ordre=0, facteur=Decimal("1"))
    req_id = await _mk_request(async_db, ingr.id, Decimal("10"))  # besoin 10L

    account_id = await _seed_account(async_db)
    service = EpicerieTransferRequestService(async_db)
    result = await service.approve_with_transfer(
        request_id=req_id,
        target_tenant_id=_TENANT_EPICERIE,
        user_id=account_id,
        payload=ApproveWithTransferRequest(),
    )

    assert result.transfer_id > 0
    assert len(result.warnings) >= 1
    assert any("déficit" in w.lower() for w in result.warnings)

    stmt = select(InternalTransferLine).where(
        InternalTransferLine.transfer_id == result.transfer_id
    )
    lines = list((await async_db.execute(stmt)).scalars())
    assert len(lines) == 1
    assert float(lines[0].quantite) == 2.0  # tout le stock prélevé
