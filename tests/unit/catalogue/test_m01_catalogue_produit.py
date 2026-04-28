"""Tests Session 4 — M01 CatalogueProduit.

Spec : V2 §6.1 + ADR-01 (pas de tenant_id) + ADR-07 (déduplication Jaro-Winkler).
Stratégie : AsyncSession DB réelle (CaroCorp_test) — pas de mocks sur la couche SQL.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.catalogue_produit import CatalogueProduit


# ── Helper ────────────────────────────────────────────────────────────────────

def _prod(designation: str = "Produit test", **kwargs) -> CatalogueProduit:
    defaults = dict(unite_base="piece")
    defaults.update(kwargs)
    return CatalogueProduit(designation=designation, **defaults)


# ── M01 : Création ────────────────────────────────────────────────────────────

class TestCatalogueProduitCreation:
    async def test_create_minimal(self, async_db: AsyncSession):
        """V2 §6.1 : création avec les champs obligatoires uniquement."""
        async_db.add(_prod("Lait demi-écrémé 1L"))
        await async_db.commit()

        result = await async_db.execute(
            select(CatalogueProduit).where(CatalogueProduit.designation == "Lait demi-écrémé 1L")
        )
        prod = result.scalar_one()
        assert prod.id is not None
        assert prod.ean is None
        assert prod.designation_norm is None
        assert prod.marque is None
        assert prod.conditionnement is None
        assert prod.source_fournisseur is None
        assert prod.categorie_code is None

    async def test_no_tenant_id(self):
        """ADR-01 : référentiel partagé, pas de tenant_id."""
        assert not hasattr(CatalogueProduit, "tenant_id")

    async def test_no_soft_delete(self):
        """M01 : catalogue ETL non soft-deletable (pas de is_active)."""
        assert not hasattr(CatalogueProduit, "is_active")

    async def test_create_with_ean(self, async_db: AsyncSession):
        """V2 §6.1 : création avec EAN-13."""
        async_db.add(_prod("Coca-Cola 33cl", ean="5449000000996"))
        await async_db.commit()

        result = await async_db.execute(
            select(CatalogueProduit).where(CatalogueProduit.ean == "5449000000996")
        )
        prod = result.scalar_one()
        assert prod.ean == "5449000000996"

    async def test_create_full(self, async_db: AsyncSession):
        """V2 §6.1 : création avec tous les champs renseignés."""
        async_db.add(_prod(
            "Pasta Penne 500g",
            ean="3017620422003",
            designation_norm="pasta penne 500g",
            marque="Barilla",
            unite_base="piece",
            conditionnement="24 × 500g",
            source_fournisseur="METRO",
            categorie_code="epic_pate",
        ))
        await async_db.commit()

        result = await async_db.execute(
            select(CatalogueProduit).where(CatalogueProduit.ean == "3017620422003")
        )
        prod = result.scalar_one()
        assert prod.marque == "Barilla"
        assert prod.source_fournisseur == "METRO"
        assert prod.categorie_code == "epic_pate"
        assert prod.designation_norm == "pasta penne 500g"

    async def test_timestamps_set(self, async_db: AsyncSession):
        """TimestampMixin : created_at / updated_at initialisés à la création."""
        async_db.add(_prod("Huile d'olive 1L", unite_base="L"))
        await async_db.commit()

        result = await async_db.execute(
            select(CatalogueProduit).where(CatalogueProduit.designation == "Huile d'olive 1L")
        )
        prod = result.scalar_one()
        assert prod.created_at is not None
        assert prod.updated_at is not None


# ── M01 : Contraintes unicité EAN ─────────────────────────────────────────────

class TestCatalogueProduitEanUnique:
    async def test_ean_unique_conflict(self, async_db: AsyncSession):
        """V2 §6.1 UNIQUE partielle : deux entrées avec même EAN sont interdites."""
        async_db.add(_prod("Produit A", ean="1234567890123"))
        await async_db.commit()

        with pytest.raises(IntegrityError):
            async_db.add(_prod("Produit B doublon", ean="1234567890123"))
            await async_db.commit()

    async def test_null_ean_not_unique_constrained(self, async_db: AsyncSession):
        """V2 §6.1 UNIQUE partielle WHERE ean IS NOT NULL : deux entrées sans EAN sont autorisées."""
        async_db.add(_prod("Produit maison 1", ean=None))
        await async_db.commit()
        async_db.add(_prod("Produit maison 2", ean=None))
        await async_db.commit()

        result = await async_db.execute(
            select(CatalogueProduit).where(CatalogueProduit.ean.is_(None))
        )
        rows = result.scalars().all()
        assert len(rows) >= 2


# ── M01 : Requêtes / index ────────────────────────────────────────────────────

class TestCatalogueProduitQuery:
    async def test_query_by_categorie_code(self, async_db: AsyncSession):
        """idx_catalogue_categorie : filtrage par catégorie (ADR-05 lien FK applicative)."""
        for i in range(3):
            async_db.add(_prod(f"Pâte {i}", categorie_code="epic_pate"))
        async_db.add(_prod("Bière test", categorie_code="bois_biere"))
        await async_db.commit()

        result = await async_db.execute(
            select(CatalogueProduit).where(CatalogueProduit.categorie_code == "epic_pate")
        )
        rows = result.scalars().all()
        assert len(rows) == 3

    async def test_query_by_source_fournisseur(self, async_db: AsyncSession):
        """idx_catalogue_source : filtrage par fournisseur ETL."""
        async_db.add(_prod("Article METRO", source_fournisseur="METRO"))
        async_db.add(_prod("Article TAIYAT", source_fournisseur="TAIYAT"))
        await async_db.commit()

        result = await async_db.execute(
            select(CatalogueProduit).where(CatalogueProduit.source_fournisseur == "METRO")
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].source_fournisseur == "METRO"

    async def test_bigserial_pk(self, async_db: AsyncSession):
        """V2 §6.1 BIGSERIAL : PK de type entier positif (prêt pour large volume ETL)."""
        async_db.add(_prod("Produit BIGSERIAL test"))
        await async_db.commit()

        result = await async_db.execute(
            select(CatalogueProduit).where(
                CatalogueProduit.designation == "Produit BIGSERIAL test"
            )
        )
        prod = result.scalar_one()
        assert isinstance(prod.id, int)
        assert prod.id > 0
