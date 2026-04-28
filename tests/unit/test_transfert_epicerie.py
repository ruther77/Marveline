"""Tests refonte transferts internes epicerie -> restaurant.

6 cas :
  1. Nominal : creer + valider → stock epicerie --, mouvements, invoice
  2. Stock insuffisant → BadRequest
  3. Double validation → BadRequest
  4. Annulation → CANCELLED
  5. Cross-tenant → NotFound
  6. Produit inexistant → NotFound
"""
import pytest
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.models.account import Account
from app.models.epicerie.internal_transfer import InternalTransfer, InternalTransferLine
from app.models.epicerie.produit import EpicerieProduit
from app.models.epicerie.stock import EpicerieStock
from app.models.epicerie.stock_movement import EpicerieStockMovement
from app.models.finance.invoice import FinanceInvoice
from app.core.exceptions import BadRequest, NotFound
from app.schemas.epicerie.transfert import InternalTransferCreate, TransferLineCreate
from app.services.epicerie.transfert import (
    creer_transfert,
    valider_transfert,
    annuler_transfert,
)

from tests.conftest import ASYNC_TEST_DATABASE_URL

_EPICERIE_TENANT = 2
_RESTAURANT_TENANT = 3


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _seed_account(db: AsyncSession) -> int:
    account = Account(
        email="transfer-test@carocorp.local",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        first_name="Transfer",
        last_name="Test",
        is_active=True,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return account.id


async def _seed_produit(
    db: AsyncSession, designation: str = "PRODUIT TEST", prix_cts: int = 500,
) -> EpicerieProduit:
    produit = EpicerieProduit(
        tenant_id=_EPICERIE_TENANT,
        designation_clean=designation,
        prix_unitaire_cts=prix_cts,
        unite_vente="U",
        actif=True,
    )
    db.add(produit)
    await db.flush()
    await db.refresh(produit)
    return produit


async def _seed_stock(
    db: AsyncSession, produit_id: int, quantite: float = 100.0,
) -> EpicerieStock:
    stock = EpicerieStock(
        tenant_id=_EPICERIE_TENANT,
        produit_id=produit_id,
        quantite=quantite,
        seuil_alerte=5,
    )
    db.add(stock)
    await db.flush()
    await db.refresh(stock)
    return stock


def _mk_payload(
    produit_id: int,
    quantite: float = 10.0,
    prix: int = 500,
    ingredient_id: int = None,
) -> InternalTransferCreate:
    return InternalTransferCreate(
        dest_tenant_id=_RESTAURANT_TENANT,
        reference="TRF-TEST",
        lignes=[
            TransferLineCreate(
                produit_id=produit_id,
                ingredient_id=ingredient_id,
                quantite=quantite,
                prix_unitaire=prix,
            ),
        ],
    )


# ── Fixture ────────────────────────────────────────────────────────────────────


@pytest.fixture
async def async_db(test_engine):
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transfert_nominal(async_db):
    """Creer + valider : stock decremente, mouvement cree, invoice creee."""
    db = async_db
    user_id = await _seed_account(db)
    produit = await _seed_produit(db, "HUILE OLIVE")
    await _seed_stock(db, produit.id, 50.0)

    payload = _mk_payload(produit.id, quantite=10.0, prix=599)

    # Creer
    transfer = await creer_transfert(db, _EPICERIE_TENANT, payload, user_id)
    assert transfer.status == "PENDING"
    assert transfer.tenant_id == _EPICERIE_TENANT
    assert transfer.dest_tenant_id == _RESTAURANT_TENANT

    # Valider
    transfer = await valider_transfert(db, _EPICERIE_TENANT, transfer.id, user_id)
    await db.commit()

    assert transfer.status == "VALIDATED"
    assert transfer.invoice_id is not None
    assert transfer.montant_ht > 0

    # Verif stock epicerie decremente
    stock_result = await db.execute(
        select(EpicerieStock).where(
            EpicerieStock.produit_id == produit.id,
            EpicerieStock.tenant_id == _EPICERIE_TENANT,
        )
    )
    stock = stock_result.scalar_one()
    assert float(stock.quantite) == 40.0

    # Verif mouvement TRANSFERT_RESTAURANT cree
    mvt_result = await db.execute(
        select(EpicerieStockMovement).where(
            EpicerieStockMovement.produit_id == produit.id,
            EpicerieStockMovement.type == "TRANSFERT_RESTAURANT",
        )
    )
    mvt = mvt_result.scalar_one()
    assert float(mvt.quantite) == -10.0
    assert float(mvt.stock_apres) == 40.0

    # Verif invoice INTERNE
    inv_result = await db.execute(
        select(FinanceInvoice).where(FinanceInvoice.id == transfer.invoice_id)
    )
    inv = inv_result.scalar_one()
    assert inv.type == "INTERNE"
    assert inv.statut == "PAYEE"


@pytest.mark.asyncio
async def test_transfert_stock_insuffisant(async_db):
    """Valider avec stock < quantite → BadRequest."""
    db = async_db
    user_id = await _seed_account(db)
    produit = await _seed_produit(db, "RIZ BASMATI")
    await _seed_stock(db, produit.id, 5.0)

    payload = _mk_payload(produit.id, quantite=20.0)
    transfer = await creer_transfert(db, _EPICERIE_TENANT, payload, user_id)

    with pytest.raises(BadRequest, match="Stock insuffisant"):
        await valider_transfert(db, _EPICERIE_TENANT, transfer.id, user_id)


@pytest.mark.asyncio
async def test_transfert_double_validation(async_db):
    """Valider 2x → BadRequest (status != PENDING)."""
    db = async_db
    user_id = await _seed_account(db)
    produit = await _seed_produit(db, "FARINE T55")
    await _seed_stock(db, produit.id, 100.0)

    payload = _mk_payload(produit.id, quantite=5.0)
    transfer = await creer_transfert(db, _EPICERIE_TENANT, payload, user_id)
    await valider_transfert(db, _EPICERIE_TENANT, transfer.id, user_id)

    with pytest.raises(BadRequest, match="non validable"):
        await valider_transfert(db, _EPICERIE_TENANT, transfer.id, user_id)


@pytest.mark.asyncio
async def test_transfert_annulation(async_db):
    """Creer → annuler → CANCELLED."""
    db = async_db
    user_id = await _seed_account(db)
    produit = await _seed_produit(db, "SUCRE ROUX")
    await _seed_stock(db, produit.id, 50.0)

    payload = _mk_payload(produit.id, quantite=10.0)
    transfer = await creer_transfert(db, _EPICERIE_TENANT, payload, user_id)

    transfer = await annuler_transfert(
        db, _EPICERIE_TENANT, transfer.id, "Test annulation",
    )
    assert transfer.status == "CANCELLED"
    assert transfer.raison_annulation == "Test annulation"


@pytest.mark.asyncio
async def test_transfert_cross_tenant_isolation(async_db):
    """Chercher un transfert avec le mauvais tenant → NotFound."""
    db = async_db
    user_id = await _seed_account(db)
    produit = await _seed_produit(db, "SEL FIN")
    await _seed_stock(db, produit.id, 50.0)

    payload = _mk_payload(produit.id, quantite=5.0)
    transfer = await creer_transfert(db, _EPICERIE_TENANT, payload, user_id)

    # Essayer de valider avec tenant_id=1 (pas le bon)
    with pytest.raises(NotFound):
        await valider_transfert(db, 1, transfer.id, user_id)


@pytest.mark.asyncio
async def test_transfert_produit_inexistant(async_db):
    """Ligne avec produit_id fantome → NotFound."""
    db = async_db
    user_id = await _seed_account(db)

    payload = _mk_payload(produit_id=999999, quantite=5.0)

    with pytest.raises(NotFound, match="Produit 999999"):
        await creer_transfert(db, _EPICERIE_TENANT, payload, user_id)
