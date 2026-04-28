"""Tests reception_etl — chaine ETL -> catalogue -> epicerie -> stock.

Spec : ADR-08 (pipeline ETL), ADR-25 (workflow facture preview/validation).
Strategie : AsyncSession DB reelle — pas de mocks sur la couche SQL.

Tests :
  1. Nominal : 3 lignes -> catalogue + epicerie_produits + 2 ENTREE + FinanceInvoice
  2. Non-regression : lignes_data vide -> ValueError
  3. Isolation tenant : tout en tenant_id=2
  4. Doublon produit : meme EAN sur 2 lignes -> stock cumule
"""
import dataclasses
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.models.base import Base
from app.models.account import Account
from app.models.catalogue.etl_import import EtlImport
from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.models.epicerie.produit import EpicerieProduit
from app.models.epicerie.stock import EpicerieStock
from app.models.epicerie.stock_movement import EpicerieStockMovement
from app.models.finance.invoice import FinanceInvoice
from app.etl_types import LigneParsee
from app.services.epicerie.reception_etl import recevoir_facture_etl

from tests.conftest import ASYNC_TEST_DATABASE_URL

_EPICERIE_TENANT = 2


# ── Helpers ────────────────────────────────────────────────────────────────────


def _mk_ligne(**kwargs) -> LigneParsee:
    defaults = dict(
        designation="Produit test",
        unite_base="U",
        source_fournisseur="METRO",
    )
    defaults.update(kwargs)
    return LigneParsee(**defaults)


def _mk_lignes_data(lignes: list[LigneParsee]) -> list[dict]:
    return [dataclasses.asdict(l) for l in lignes]


async def _seed_etl_import(
    db: AsyncSession,
    lignes: list[LigneParsee],
    vendor_code: str = "METRO",
    numero_facture: str = "FAC-TEST-001",
) -> EtlImport:
    """Cree un EtlImport PREVIEW avec lignes_data."""
    obj = EtlImport(
        statut="PREVIEW",
        nb_lignes_total=len(lignes),
        nb_lignes_ok=len(lignes),
        vendor_code=vendor_code,
        numero_facture=numero_facture,
        montant_ht_total=10000,
        montant_tva_total=2000,
        montant_ttc_total=12000,
        lignes_data=_mk_lignes_data(lignes),
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return obj


# ── Fixture session async ──────────────────────────────────────────────────────


async def _seed_test_account(db: AsyncSession) -> int:
    """Cree un compte de test et retourne son id."""
    account = Account(
        email="etl-test@carocorp.local",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        first_name="ETL",
        last_name="Test",
        is_active=True,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return account.id


@pytest.fixture
async def async_db(test_engine):
    """Session async pour chaque test."""
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reception_etl_nominal(async_db):
    """3 lignes : 2 avec quantite (ENTREE), 1 sans quantite (skip)."""
    db = async_db
    user_id = await _seed_test_account(db)

    lignes = [
        _mk_ligne(
            designation="HUILE OLIVE VIERGE EXTRA",
            ean="3012345678901",
            quantite=10.0,
            prix_unitaire_cts=599,
            taux_tva_centieme=2000,
        ),
        _mk_ligne(
            designation="RIZ BASMATI",
            ean="3012345678902",
            quantite=5.0,
            prix_unitaire_cts=299,
            taux_tva_centieme=550,
        ),
        _mk_ligne(
            designation="PRODUIT SANS QUANTITE",
            ean="3012345678903",
            # quantite=None -> pas de mouvement ENTREE
        ),
    ]
    etl_import = await _seed_etl_import(db, lignes)

    result = await recevoir_facture_etl(
        db=db,
        etl_import=etl_import,
        tenant_id=_EPICERIE_TENANT,
        user_id=user_id,
    )
    await db.commit()

    # Verif : 2 mouvements ENTREE, 1 ligne sans quantite
    assert result.mouvements_crees == 2
    assert result.lignes_sans_quantite == 1

    # Verif : FinanceInvoice creee
    assert result.invoice is not None
    assert result.invoice.type == "FOURNISSEUR"
    assert result.invoice.tenant_id == _EPICERIE_TENANT
    assert result.invoice.etl_import_id == etl_import.id
    assert result.invoice.montant_ht == 10000
    assert result.invoice.montant_ttc == 12000

    # Verif : produits epicerie crees avec bon tenant
    produits_count = await db.execute(
        select(func.count()).select_from(
            select(EpicerieProduit).where(
                EpicerieProduit.tenant_id == _EPICERIE_TENANT,
                EpicerieProduit.actif.is_(True),
            ).subquery()
        )
    )
    assert produits_count.scalar_one() >= 2

    # Verif : mouvements avec etl_import_id
    mvts = await db.execute(
        select(EpicerieStockMovement).where(
            EpicerieStockMovement.etl_import_id == etl_import.id,
        )
    )
    mouvements = mvts.scalars().all()
    assert len(mouvements) == 2
    assert all(m.type == "ENTREE" for m in mouvements)
    assert all(m.tenant_id == _EPICERIE_TENANT for m in mouvements)
    assert all(m.quantite > 0 for m in mouvements)


@pytest.mark.asyncio
async def test_reception_etl_lignes_data_vide(async_db):
    """lignes_data vide -> ValueError."""
    db = async_db

    obj = EtlImport(statut="PREVIEW", lignes_data=None)
    db.add(obj)
    await db.flush()
    await db.refresh(obj)

    with pytest.raises(ValueError, match="lignes_data vide"):
        await recevoir_facture_etl(
            db=db, etl_import=obj, tenant_id=_EPICERIE_TENANT, user_id=0,
        )


@pytest.mark.asyncio
async def test_reception_etl_tenant_isolation(async_db):
    """Verifie que tous les objets crees ont tenant_id=2, pas 1."""
    db = async_db
    user_id = await _seed_test_account(db)

    lignes = [
        _mk_ligne(
            designation="CAFE MOULU",
            ean="3099999999901",
            quantite=3.0,
            prix_unitaire_cts=450,
        ),
    ]
    etl_import = await _seed_etl_import(db, lignes)

    result = await recevoir_facture_etl(
        db=db, etl_import=etl_import, tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()

    # FinanceInvoice
    assert result.invoice.tenant_id == _EPICERIE_TENANT

    # Stock movements
    mvts = await db.execute(
        select(EpicerieStockMovement).where(
            EpicerieStockMovement.etl_import_id == etl_import.id,
        )
    )
    for m in mvts.scalars().all():
        assert m.tenant_id == _EPICERIE_TENANT

    # Epicerie produits — aucun en tenant 1
    t1_count = await db.execute(
        select(func.count()).select_from(
            select(EpicerieProduit).where(
                EpicerieProduit.tenant_id == 1,
            ).subquery()
        )
    )
    assert t1_count.scalar_one() == 0


@pytest.mark.asyncio
async def test_reception_etl_doublon_ean(async_db):
    """Meme EAN sur 2 lignes -> stock cumule correctement."""
    db = async_db
    user_id = await _seed_test_account(db)

    lignes = [
        _mk_ligne(
            designation="FARINE BLE T55",
            ean="3088888888801",
            quantite=10.0,
            prix_unitaire_cts=150,
        ),
        _mk_ligne(
            designation="FARINE BLE T55",
            ean="3088888888801",
            quantite=5.0,
            prix_unitaire_cts=150,
        ),
    ]
    etl_import = await _seed_etl_import(db, lignes)

    result = await recevoir_facture_etl(
        db=db, etl_import=etl_import, tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()

    assert result.mouvements_crees == 2

    # Verif stock cumule = 15
    produit = await db.execute(
        select(EpicerieProduit).where(
            EpicerieProduit.ean == "3088888888801",
            EpicerieProduit.tenant_id == _EPICERIE_TENANT,
        )
    )
    p = produit.scalar_one()
    stock = await db.execute(
        select(EpicerieStock).where(
            EpicerieStock.produit_id == p.id,
            EpicerieStock.tenant_id == _EPICERIE_TENANT,
        )
    )
    s = stock.scalar_one()
    assert float(s.quantite) == 15.0


# ── Édition post-validation (Option B — P1) ────────────────────────────────


async def _seed_validated_import(
    db: AsyncSession,
    lignes: list[LigneParsee],
    invoice_statut: str = "EN_ATTENTE",
    invoice_tenant_id: int = _EPICERIE_TENANT,
) -> tuple[EtlImport, FinanceInvoice, list[int]]:
    """Seed EtlImport VALIDATED + FinanceInvoice liée + produits epicerie + stocks.

    Retourne (import, invoice, produit_ids dans l'ordre des lignes).
    """
    from datetime import date as _date

    produit_ids: list[int] = []
    for lg in lignes:
        ht = int((lg.quantite or 0) * (lg.prix_unitaire_cts or 0))
        prod = EpicerieProduit(
            tenant_id=_EPICERIE_TENANT,
            ean=lg.ean,
            designation_clean=lg.designation.upper(),
            prix_achat_cts=lg.prix_unitaire_cts or 0,
            prix_unitaire_cts=int((lg.prix_unitaire_cts or 0) * 1.3),
            taux_tva=lg.taux_tva_centieme or 2000,
            categorie=lg.categorie_code or "AUTRE",
            unite_vente="U",
            actif=True,
        )
        db.add(prod)
        await db.flush()
        produit_ids.append(prod.id)
        if lg.quantite:
            stock = EpicerieStock(
                tenant_id=_EPICERIE_TENANT,
                produit_id=prod.id,
                quantite=float(lg.quantite),
                seuil_alerte=0,
            )
            db.add(stock)
    await db.flush()

    total_ht = sum(
        int((lg.quantite or 0) * (lg.prix_unitaire_cts or 0)) for lg in lignes
    )
    total_ttc = sum(
        int(
            (lg.quantite or 0)
            * (lg.prix_unitaire_cts or 0)
            * (1 + (lg.taux_tva_centieme or 0) / 10000)
        )
        for lg in lignes
    )
    etl_import = EtlImport(
        statut="VALIDATED",
        nb_lignes_total=len(lignes),
        nb_lignes_ok=len(lignes),
        vendor_code="METRO",
        numero_facture="FAC-EDIT-TEST",
        montant_ht_total=total_ht,
        montant_tva_total=total_ttc - total_ht,
        montant_ttc_total=total_ttc,
        lignes_data=_mk_lignes_data(lignes),
    )
    db.add(etl_import)
    await db.flush()

    invoice = FinanceInvoice(
        tenant_id=invoice_tenant_id,
        type="FOURNISSEUR",
        numero=f"FAC-EDIT-{etl_import.id}",
        date_facture=_date.today(),
        montant_ht=total_ht,
        montant_tva=total_ttc - total_ht,
        montant_ttc=total_ttc,
        statut=invoice_statut,
        etl_import_id=etl_import.id,
    )
    db.add(invoice)
    await db.flush()
    await db.refresh(etl_import)
    await db.refresh(invoice)
    return etl_import, invoice, produit_ids


def _count_ajustements(db: AsyncSession, etl_import_id: int):
    """Helper pour compter les mouvements AJUSTEMENT d'un import."""
    return db.execute(
        select(func.count()).select_from(
            select(EpicerieStockMovement).where(
                EpicerieStockMovement.etl_import_id == etl_import_id,
                EpicerieStockMovement.type == "AJUSTEMENT",
            ).subquery()
        )
    )


@pytest.mark.asyncio
async def test_edit_validated_ligne_nominal_qte_plus(async_db):
    """Qte 10 → 15 : stock +5, AJUSTEMENT créé, facture recalculée."""
    from app.services.epicerie.reception_etl import edit_validated_lignes

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [
        _mk_ligne(
            designation="HUILE OLIVE EDIT", ean="3011111110001",
            quantite=10.0, prix_unitaire_cts=500, taux_tva_centieme=2000,
        ),
    ]
    etl_import, invoice, prod_ids = await _seed_validated_import(db, lignes)
    old_ht, old_ttc = invoice.montant_ht, invoice.montant_ttc

    await edit_validated_lignes(
        db=db, etl_import=etl_import,
        updates=[{"idx": 0, "quantite": 15.0}],
        tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()
    await db.refresh(invoice)

    stock = await db.execute(
        select(EpicerieStock).where(EpicerieStock.produit_id == prod_ids[0])
    )
    assert float(stock.scalar_one().quantite) == 15.0

    mvts = await db.execute(
        select(EpicerieStockMovement).where(
            EpicerieStockMovement.etl_import_id == etl_import.id,
            EpicerieStockMovement.type == "AJUSTEMENT",
        )
    )
    ajustements = mvts.scalars().all()
    assert len(ajustements) == 1
    assert float(ajustements[0].quantite) == 5.0
    assert float(ajustements[0].stock_apres) == 15.0

    # Facture recalculée : HT = 15 * 500 = 7500, TTC = 7500 * 1.20 = 9000
    assert invoice.montant_ht == 7500
    assert invoice.montant_ttc == 9000
    assert invoice.montant_ht != old_ht
    assert invoice.montant_ttc != old_ttc


@pytest.mark.asyncio
async def test_edit_validated_ligne_delta_negatif(async_db):
    """Qte 10 → 3 : AJUSTEMENT -7, stock = 3."""
    from app.services.epicerie.reception_etl import edit_validated_lignes

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [
        _mk_ligne(
            designation="RIZ EDIT", ean="3011111110002",
            quantite=10.0, prix_unitaire_cts=300, taux_tva_centieme=550,
        ),
    ]
    etl_import, invoice, prod_ids = await _seed_validated_import(db, lignes)

    await edit_validated_lignes(
        db=db, etl_import=etl_import,
        updates=[{"idx": 0, "quantite": 3.0}],
        tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()

    stock = await db.execute(
        select(EpicerieStock).where(EpicerieStock.produit_id == prod_ids[0])
    )
    assert float(stock.scalar_one().quantite) == 3.0

    mvts = await db.execute(
        select(EpicerieStockMovement).where(
            EpicerieStockMovement.etl_import_id == etl_import.id,
            EpicerieStockMovement.type == "AJUSTEMENT",
        )
    )
    ajustements = mvts.scalars().all()
    assert len(ajustements) == 1
    assert float(ajustements[0].quantite) == -7.0


@pytest.mark.asyncio
async def test_edit_validated_ligne_not_validated(async_db):
    """Import en PREVIEW → EtlValidationEditError(NOT_VALIDATED)."""
    from app.services.epicerie.reception_etl import (
        edit_validated_lignes, EtlValidationEditError,
    )

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [_mk_ligne(designation="TEST", ean="3011111110003", quantite=1.0, prix_unitaire_cts=100)]
    etl_import = await _seed_etl_import(db, lignes)  # statut=PREVIEW

    with pytest.raises(EtlValidationEditError) as exc_info:
        await edit_validated_lignes(
            db=db, etl_import=etl_import,
            updates=[{"idx": 0, "quantite": 2.0}],
            tenant_id=_EPICERIE_TENANT, user_id=user_id,
        )
    assert exc_info.value.code == "NOT_VALIDATED"


@pytest.mark.asyncio
async def test_edit_validated_ligne_cross_tenant(async_db):
    """Facture tenant 99 ≠ caller tenant 2 → WRONG_TENANT."""
    from app.services.epicerie.reception_etl import (
        edit_validated_lignes, EtlValidationEditError,
    )

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [_mk_ligne(designation="TEST XT", ean="3011111110004", quantite=1.0, prix_unitaire_cts=100)]
    etl_import, _, _ = await _seed_validated_import(db, lignes, invoice_tenant_id=99)

    with pytest.raises(EtlValidationEditError) as exc_info:
        await edit_validated_lignes(
            db=db, etl_import=etl_import,
            updates=[{"idx": 0, "quantite": 2.0}],
            tenant_id=_EPICERIE_TENANT, user_id=user_id,
        )
    assert exc_info.value.code == "WRONG_TENANT"


@pytest.mark.asyncio
async def test_edit_validated_ligne_invoice_locked(async_db):
    """Facture PAYEE → INVOICE_LOCKED sur modif financière."""
    from app.services.epicerie.reception_etl import (
        edit_validated_lignes, EtlValidationEditError,
    )

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [_mk_ligne(designation="PAID", ean="3011111110005", quantite=1.0, prix_unitaire_cts=100)]
    etl_import, _, _ = await _seed_validated_import(db, lignes, invoice_statut="PAYEE")

    with pytest.raises(EtlValidationEditError) as exc_info:
        await edit_validated_lignes(
            db=db, etl_import=etl_import,
            updates=[{"idx": 0, "quantite": 2.0}],
            tenant_id=_EPICERIE_TENANT, user_id=user_id,
        )
    assert exc_info.value.code == "INVOICE_LOCKED"


@pytest.mark.asyncio
async def test_edit_validated_ligne_out_of_range(async_db):
    """idx=99 sur import 1 ligne → LIGNE_OUT_OF_RANGE."""
    from app.services.epicerie.reception_etl import (
        edit_validated_lignes, EtlValidationEditError,
    )

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [_mk_ligne(designation="RANGE", ean="3011111110006", quantite=1.0, prix_unitaire_cts=100)]
    etl_import, _, _ = await _seed_validated_import(db, lignes)

    with pytest.raises(EtlValidationEditError) as exc_info:
        await edit_validated_lignes(
            db=db, etl_import=etl_import,
            updates=[{"idx": 99, "quantite": 2.0}],
            tenant_id=_EPICERIE_TENANT, user_id=user_id,
        )
    assert exc_info.value.code == "LIGNE_OUT_OF_RANGE"


def test_if_match_header_helper():
    """Helper _parse_if_match_header : match, stale, manquant."""
    from datetime import datetime, timezone
    from fastapi import HTTPException
    from app.api.v1.endpoints.admin.etl_imports import _parse_if_match_header

    dt = datetime(2026, 4, 11, 17, 35, 50, 181844, tzinfo=timezone.utc)

    # Match exact → pas d'exception
    _parse_if_match_header(dt.isoformat(), dt)

    # Match avec guillemets (format HTTP standard)
    _parse_if_match_header(f'"{dt.isoformat()}"', dt)

    # Missing → 428
    with pytest.raises(HTTPException) as exc:
        _parse_if_match_header(None, dt)
    assert exc.value.status_code == 428
    assert exc.value.detail["code"] == "IF_MATCH_REQUIRED"

    # Stale → 409
    with pytest.raises(HTTPException) as exc:
        _parse_if_match_header("2020-01-01T00:00:00+00:00", dt)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "STALE"


# ── P2 : cascades non-financières + invoice meta ────────────────────────────


async def _seed_marge_cat(db: AsyncSession, categorie: str, taux: int) -> None:
    """Seed une marge de catégorie pour le tenant épicerie."""
    from app.models.epicerie.marge import EpicerieMargeCategorie
    existing = await db.execute(
        select(EpicerieMargeCategorie).where(
            EpicerieMargeCategorie.tenant_id == _EPICERIE_TENANT,
            EpicerieMargeCategorie.categorie == categorie,
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(EpicerieMargeCategorie(
            tenant_id=_EPICERIE_TENANT, categorie=categorie, taux_marge_centieme=taux,
        ))
        await db.flush()


async def _seed_catalogue_produit(db: AsyncSession, ean: str, designation: str) -> int:
    """Seed un CatalogueProduit pour tester cascade marque/cat. Retourne id."""
    cat_prod = CatalogueProduit(
        designation=designation,
        designation_norm=designation.upper(),
        ean=ean,
        unite_base="U",
        source_fournisseur="METRO",
        categorie_code="AUTRE",
    )
    db.add(cat_prod)
    await db.flush()
    return cat_prod.id


@pytest.mark.asyncio
async def test_edit_validated_cascade_categorie(async_db):
    """Changement categorie_code → catalogue + epicerie + prix vente recalculé."""
    from app.services.epicerie.reception_etl import edit_validated_lignes

    db = async_db
    user_id = await _seed_test_account(db)
    await _seed_marge_cat(db, "AUTRE", 2000)       # 20%
    await _seed_marge_cat(db, "ALC_VIN_RGE", 5000)  # 50%

    lignes = [_mk_ligne(
        designation="BORDEAUX TEST", ean="3099111100001",
        quantite=6.0, prix_unitaire_cts=500, taux_tva_centieme=2000,
        categorie_code="AUTRE",
    )]
    await _seed_catalogue_produit(db, "3099111100001", "BORDEAUX TEST")
    etl_import, invoice, prod_ids = await _seed_validated_import(db, lignes)
    # Force catégorie AUTRE sur epicerie_produits
    await db.execute(
        select(EpicerieProduit).where(EpicerieProduit.id == prod_ids[0])
    )
    ep_prod = (await db.execute(select(EpicerieProduit).where(EpicerieProduit.id == prod_ids[0]))).scalar_one()
    ep_prod.categorie = "AUTRE"
    await db.flush()
    old_prix_vente = ep_prod.prix_unitaire_cts

    await edit_validated_lignes(
        db=db, etl_import=etl_import,
        updates=[{"idx": 0, "categorie_code": "ALC_VIN_RGE"}],
        tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()
    await db.refresh(ep_prod)

    # Cascade epicerie
    assert ep_prod.categorie == "ALC_VIN_RGE"
    # Cascade catalogue
    cat_prod = (await db.execute(
        select(CatalogueProduit).where(CatalogueProduit.ean == "3099111100001")
    )).scalar_one()
    assert cat_prod.categorie_code == "ALC_VIN_RGE"
    # Prix de vente recalculé avec marge 50% (vs 20% pour AUTRE)
    assert ep_prod.prix_unitaire_cts != old_prix_vente
    # achat=500, marge=50% → prix_ht=750, TVA 20% → TTC=900
    assert ep_prod.prix_unitaire_cts == 900


@pytest.mark.asyncio
async def test_edit_validated_cascade_marque(async_db):
    """Changement marque → catalogue seul (EpicerieProduit n'a pas de champ marque)."""
    from app.services.epicerie.reception_etl import edit_validated_lignes

    db = async_db
    user_id = await _seed_test_account(db)
    await _seed_marge_cat(db, "AUTRE", 2000)
    lignes = [_mk_ligne(
        designation="CHAMPAGNE BLANK", ean="3099111100002",
        quantite=2.0, prix_unitaire_cts=1200, taux_tva_centieme=2000,
    )]
    await _seed_catalogue_produit(db, "3099111100002", "CHAMPAGNE BLANK")
    etl_import, _, _ = await _seed_validated_import(db, lignes)

    await edit_validated_lignes(
        db=db, etl_import=etl_import,
        updates=[{"idx": 0, "marque": "MOET"}],
        tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()

    cat_prod = (await db.execute(
        select(CatalogueProduit).where(CatalogueProduit.ean == "3099111100002")
    )).scalar_one()
    assert cat_prod.marque == "MOET"

    # Vérif lignes_data mis à jour aussi
    await db.refresh(etl_import)
    assert etl_import.lignes_data[0]["marque"] == "MOET"


@pytest.mark.asyncio
async def test_edit_validated_invoice_payee_allows_non_financial(async_db):
    """Facture PAYEE → modif non-financière (marque) autorisée."""
    from app.services.epicerie.reception_etl import edit_validated_lignes

    db = async_db
    user_id = await _seed_test_account(db)
    await _seed_marge_cat(db, "AUTRE", 2000)
    lignes = [_mk_ligne(
        designation="PAID MARQUE", ean="3099111100003",
        quantite=1.0, prix_unitaire_cts=100, taux_tva_centieme=2000,
    )]
    await _seed_catalogue_produit(db, "3099111100003", "PAID MARQUE")
    etl_import, invoice, _ = await _seed_validated_import(db, lignes, invoice_statut="PAYEE")

    # Ne devrait PAS lever INVOICE_LOCKED
    await edit_validated_lignes(
        db=db, etl_import=etl_import,
        updates=[{"idx": 0, "marque": "LA MARQUE"}],
        tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()

    cat_prod = (await db.execute(
        select(CatalogueProduit).where(CatalogueProduit.ean == "3099111100003")
    )).scalar_one()
    assert cat_prod.marque == "LA MARQUE"
    # Invoice toujours PAYEE, intacte
    await db.refresh(invoice)
    assert invoice.statut == "PAYEE"


# ── P4 : gestion downstream stock négatif ───────────────────────────────────


@pytest.mark.asyncio
async def test_edit_validated_delta_positif_no_warning(async_db):
    """Delta quantité positif → aucun warning (stock ne peut pas devenir négatif)."""
    from app.services.epicerie.reception_etl import edit_validated_lignes

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [_mk_ligne(
        designation="POSITIVE DELTA", ean="3099111100010",
        quantite=10.0, prix_unitaire_cts=500, taux_tva_centieme=2000,
    )]
    etl_import, _, _ = await _seed_validated_import(db, lignes)

    result = await edit_validated_lignes(
        db=db, etl_import=etl_import,
        updates=[{"idx": 0, "quantite": 15.0}],
        tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()

    assert result.warnings == []


@pytest.mark.asyncio
async def test_edit_validated_delta_negatif_in_bounds(async_db):
    """Delta négatif mais stock reste positif → pas de warning."""
    from app.services.epicerie.reception_etl import edit_validated_lignes

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [_mk_ligne(
        designation="NEG DELTA IN BOUNDS", ean="3099111100011",
        quantite=10.0, prix_unitaire_cts=500, taux_tva_centieme=2000,
    )]
    etl_import, _, prod_ids = await _seed_validated_import(db, lignes)

    result = await edit_validated_lignes(
        db=db, etl_import=etl_import,
        updates=[{"idx": 0, "quantite": 5.0}],
        tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()

    assert result.warnings == []
    stock = (await db.execute(
        select(EpicerieStock).where(EpicerieStock.produit_id == prod_ids[0])
    )).scalar_one()
    assert float(stock.quantite) == 5.0


@pytest.mark.asyncio
async def test_edit_validated_stock_clipped_warning(async_db):
    """Vente entre validation et correction → delta clippé à 0 → warning STOCK_CLIPPED.

    Scénario : facture validée avec qte=10 (stock seed=10). Des ventes
    consomment 8 unités → stock=2. L'opérateur corrige qte 10→5 (delta -5),
    mais le stock ne peut que descendre à 0 (pas de négatif). Le delta
    appliqué est -2 (au lieu de -5) et un warning STOCK_CLIPPED est retourné.
    """
    from app.services.epicerie.reception_etl import edit_validated_lignes

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [_mk_ligne(
        designation="STOCK CLIPPED", ean="3099111100012",
        quantite=10.0, prix_unitaire_cts=500, taux_tva_centieme=2000,
    )]
    etl_import, _, prod_ids = await _seed_validated_import(db, lignes)

    # Simule 8 unités consommées par des ventes entre validation et correction.
    stock = (await db.execute(
        select(EpicerieStock).where(EpicerieStock.produit_id == prod_ids[0])
    )).scalar_one()
    stock.quantite = 2.0
    await db.flush()

    result = await edit_validated_lignes(
        db=db, etl_import=etl_import,
        updates=[{"idx": 0, "quantite": 5.0}],
        tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()

    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert warning["code"] == "STOCK_CLIPPED"
    assert warning["idx"] == 0
    assert warning["ean"] == "3099111100012"
    assert warning["stock_before"] == 2.0
    assert warning["stock_after"] == 0.0
    assert warning["delta_requested"] == -5.0
    assert warning["delta_applied"] == -2.0

    # Stock effectivement clippé à 0 (pas de négatif, cohérent avec check constraint)
    stock_refreshed = (await db.execute(
        select(EpicerieStock).where(EpicerieStock.produit_id == prod_ids[0])
    )).scalar_one()
    assert float(stock_refreshed.quantite) == 0.0

    # Le mouvement AJUSTEMENT a la quantite CLIPPÉE (-2), pas celle demandée (-5)
    mvt = (await db.execute(
        select(EpicerieStockMovement).where(
            EpicerieStockMovement.etl_import_id == etl_import.id,
            EpicerieStockMovement.type == "AJUSTEMENT",
        )
    )).scalar_one()
    assert float(mvt.quantite) == -2.0
    assert float(mvt.stock_apres) == 0.0
    assert "clippé" in (mvt.notes or "")

    # Mais lignes_data.quantite reflète la correction LOGIQUE (5), pas le clip
    await db.refresh(etl_import)
    assert etl_import.lignes_data[0]["quantite"] == 5.0


# ── P5 : notifications validateur original ──────────────────────────────────


async def _seed_entree_movement(
    db: AsyncSession, etl_import_id: int, produit_id: int, user_id: int,
) -> None:
    """Seed un mouvement ENTREE factice lié à un import, au nom d'un user donné."""
    from datetime import datetime, timezone
    mvt = EpicerieStockMovement(
        tenant_id=_EPICERIE_TENANT,
        produit_id=produit_id,
        type="ENTREE",
        quantite=1.0,
        stock_apres=1.0,
        date_mouvement=datetime.now(timezone.utc),
        etl_import_id=etl_import_id,
        notes="Seed validation test",
        created_by_id=user_id,
    )
    db.add(mvt)
    await db.flush()


@pytest.mark.asyncio
async def test_edit_validated_notifies_original_validator(async_db):
    """Un correcteur B corrige une ligne validée par A → notification créée pour A."""
    from app.models.notification import Notification
    from app.services.epicerie.reception_etl import edit_validated_lignes

    db = async_db
    validator_id = await _seed_test_account(db)
    # Second account = corrector
    from app.models.account import Account
    corrector_account = Account(
        email="corrector@carocorp.local",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        first_name="Correct", last_name="Or", is_active=True,
    )
    db.add(corrector_account)
    await db.flush()
    corrector_id = corrector_account.id

    lignes = [_mk_ligne(
        designation="NOTIF TEST", ean="3099111100020",
        quantite=10.0, prix_unitaire_cts=500, taux_tva_centieme=2000,
    )]
    etl_import, _, prod_ids = await _seed_validated_import(db, lignes)
    # Seed un mouvement ENTREE par le validateur original
    await _seed_entree_movement(db, etl_import.id, prod_ids[0], validator_id)

    await edit_validated_lignes(
        db=db, etl_import=etl_import,
        updates=[{"idx": 0, "quantite": 15.0}],
        tenant_id=_EPICERIE_TENANT, user_id=corrector_id,
    )
    await db.commit()

    notifs = (await db.execute(
        select(Notification).where(Notification.user_id == validator_id)
    )).scalars().all()
    assert len(notifs) == 1
    notif = notifs[0]
    assert notif.tenant_id == _EPICERIE_TENANT
    assert notif.type == "info"
    assert f"#{etl_import.id}" in notif.title or (etl_import.numero_facture or "") in notif.title
    # Message détaillé : contient le champ et la transition avant → après
    assert "quantite" in (notif.message or "")
    assert "10" in (notif.message or "") and "15" in (notif.message or "")
    assert notif.link == f"/etl-imports/{etl_import.id}"


@pytest.mark.asyncio
async def test_edit_validated_skip_notif_when_self_correct(async_db):
    """Si le correcteur est le validateur original → pas de notification (pas d'auto-notif)."""
    from app.models.notification import Notification
    from app.services.epicerie.reception_etl import edit_validated_lignes

    db = async_db
    user_id = await _seed_test_account(db)

    lignes = [_mk_ligne(
        designation="SELF CORRECT", ean="3099111100021",
        quantite=5.0, prix_unitaire_cts=200, taux_tva_centieme=2000,
    )]
    etl_import, _, prod_ids = await _seed_validated_import(db, lignes)
    await _seed_entree_movement(db, etl_import.id, prod_ids[0], user_id)

    await edit_validated_lignes(
        db=db, etl_import=etl_import,
        updates=[{"idx": 0, "quantite": 8.0}],
        tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()

    notifs = (await db.execute(
        select(Notification).where(Notification.user_id == user_id)
    )).scalars().all()
    assert len(notifs) == 0


# ── P7 : reopen REJECTED / REVERTED → PREVIEW ──────────────────────────────


@pytest.mark.asyncio
async def test_reopen_rejected_to_preview(async_db):
    """Un import REJECTED est réouvert en PREVIEW (pas de cascade)."""
    from app.services.epicerie.reception_etl import reopen_import

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [_mk_ligne(
        designation="REOPEN REJECTED", ean="3099111100030",
        quantite=1.0, prix_unitaire_cts=100,
    )]
    etl_import = await _seed_etl_import(db, lignes)
    etl_import.statut = "REJECTED"
    await db.flush()

    await reopen_import(
        db=db, etl_import=etl_import,
        tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()
    await db.refresh(etl_import)

    assert etl_import.statut == "PREVIEW"
    assert etl_import.reverted_at is None
    assert etl_import.reverted_by_id is None


@pytest.mark.asyncio
async def test_reopen_reverted_to_preview(async_db):
    """Un import REVERTED est réouvert en PREVIEW avec reset des champs revert."""
    from datetime import datetime, timezone
    from app.services.epicerie.reception_etl import reopen_import

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [_mk_ligne(
        designation="REOPEN REVERTED", ean="3099111100031",
        quantite=5.0, prix_unitaire_cts=200, taux_tva_centieme=2000,
    )]
    etl_import, invoice, _ = await _seed_validated_import(db, lignes)
    # Simule un revert passé
    etl_import.statut = "REVERTED"
    etl_import.reverted_at = datetime.now(timezone.utc)
    etl_import.reverted_by_id = user_id
    invoice.statut = "ANNULEE"
    await db.flush()

    await reopen_import(
        db=db, etl_import=etl_import,
        tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()
    await db.refresh(etl_import)

    assert etl_import.statut == "PREVIEW"
    assert etl_import.reverted_at is None
    assert etl_import.reverted_by_id is None


@pytest.mark.asyncio
async def test_reopen_not_reopenable_statut(async_db):
    """Un import en VALIDATED (ni REJECTED ni REVERTED) → NOT_REOPENABLE."""
    from app.services.epicerie.reception_etl import (
        reopen_import, EtlReopenError,
    )

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [_mk_ligne(
        designation="NOT REOPENABLE", ean="3099111100032",
        quantite=1.0, prix_unitaire_cts=100,
    )]
    etl_import, _, _ = await _seed_validated_import(db, lignes)

    with pytest.raises(EtlReopenError) as exc_info:
        await reopen_import(
            db=db, etl_import=etl_import,
            tenant_id=_EPICERIE_TENANT, user_id=user_id,
        )
    assert exc_info.value.code == "NOT_REOPENABLE"


@pytest.mark.asyncio
async def test_reopen_reverted_wrong_tenant(async_db):
    """Reopen REVERTED d'un import dont la facture appartient à un autre tenant → WRONG_TENANT."""
    from datetime import datetime, timezone
    from app.services.epicerie.reception_etl import (
        reopen_import, EtlReopenError,
    )

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [_mk_ligne(
        designation="REOPEN XT", ean="3099111100033",
        quantite=1.0, prix_unitaire_cts=100,
    )]
    etl_import, invoice, _ = await _seed_validated_import(
        db, lignes, invoice_tenant_id=99,  # tenant autre
    )
    etl_import.statut = "REVERTED"
    etl_import.reverted_at = datetime.now(timezone.utc)
    etl_import.reverted_by_id = user_id
    invoice.statut = "ANNULEE"
    await db.flush()

    with pytest.raises(EtlReopenError) as exc_info:
        await reopen_import(
            db=db, etl_import=etl_import,
            tenant_id=_EPICERIE_TENANT, user_id=user_id,
        )
    assert exc_info.value.code == "WRONG_TENANT"


@pytest.mark.asyncio
async def test_edit_validated_invoice_meta_updates_facture(async_db):
    """edit_validated_invoice_meta : numero + date propagés sur FinanceInvoice."""
    from datetime import date as _date
    from app.services.epicerie.reception_etl import edit_validated_invoice_meta

    db = async_db
    user_id = await _seed_test_account(db)
    lignes = [_mk_ligne(
        designation="META TEST", ean="3099111100004",
        quantite=1.0, prix_unitaire_cts=100, taux_tva_centieme=2000,
    )]
    etl_import, invoice, _ = await _seed_validated_import(db, lignes)
    old_numero = etl_import.numero_facture

    new_date = _date(2026, 1, 15)
    await edit_validated_invoice_meta(
        db=db, etl_import=etl_import,
        updates={"numero_facture": "NEW-FAC-999", "date_facture": new_date},
        tenant_id=_EPICERIE_TENANT, user_id=user_id,
    )
    await db.commit()
    await db.refresh(etl_import)
    await db.refresh(invoice)

    assert etl_import.numero_facture == "NEW-FAC-999"
    assert etl_import.numero_facture != old_numero
    assert etl_import.date_facture == new_date
    # Cascade FinanceInvoice
    assert invoice.reference == "NEW-FAC-999"
    assert invoice.date_facture == new_date
