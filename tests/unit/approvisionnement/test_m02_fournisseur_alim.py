"""Tests Session 4 — M02 FournisseurAlim.

Spec : V2 §6.2 + ADR-02 (pas de tenant_id).
Stratégie : AsyncSession DB réelle (CaroCorp_test) — pas de mocks sur la couche SQL.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approvisionnement.fournisseur_alim import FournisseurAlim


# ── Helper ────────────────────────────────────────────────────────────────────

def _fournisseur(nom: str, **kwargs) -> FournisseurAlim:
    return FournisseurAlim(nom=nom, **kwargs)


# ── M02 : Création ────────────────────────────────────────────────────────────

class TestFournisseurAlimCreation:
    async def test_create_minimal(self, async_db: AsyncSession):
        """V2 §6.2 : création avec le nom uniquement."""
        async_db.add(_fournisseur("Grossiste Test SA"))
        await async_db.commit()

        result = await async_db.execute(
            select(FournisseurAlim).where(FournisseurAlim.nom == "Grossiste Test SA")
        )
        f = result.scalar_one()
        assert f.id is not None
        assert f.code_fournisseur is None
        assert f.type_facturation is None

    async def test_no_tenant_id(self):
        """ADR-02 : référentiel partagé, pas de tenant_id."""
        assert not hasattr(FournisseurAlim, "tenant_id")

    async def test_no_soft_delete(self):
        """M02 : référentiel fournisseur non soft-deletable."""
        assert not hasattr(FournisseurAlim, "is_active")

    async def test_create_metro(self, async_db: AsyncSession):
        """V2 §6.2 : création METRO avec tous les champs."""
        async_db.add(_fournisseur(
            "Metro Cash & Carry France",
            code_fournisseur="METRO",
            type_facturation="pdf",
        ))
        await async_db.commit()

        result = await async_db.execute(
            select(FournisseurAlim).where(FournisseurAlim.code_fournisseur == "METRO")
        )
        f = result.scalar_one()
        assert f.nom == "Metro Cash & Carry France"
        assert f.type_facturation == "pdf"

    async def test_create_taiyat(self, async_db: AsyncSession):
        """V2 §6.2 : création TAIYAT (type_facturation='email')."""
        async_db.add(_fournisseur(
            "TAIYAT Distribution",
            code_fournisseur="TAIYAT",
            type_facturation="email",
        ))
        await async_db.commit()

        result = await async_db.execute(
            select(FournisseurAlim).where(FournisseurAlim.code_fournisseur == "TAIYAT")
        )
        f = result.scalar_one()
        assert f.code_fournisseur == "TAIYAT"
        assert f.type_facturation == "email"

    async def test_timestamps_set(self, async_db: AsyncSession):
        """TimestampMixin : created_at / updated_at initialisés à la création."""
        async_db.add(_fournisseur("Fournisseur TS Test"))
        await async_db.commit()

        result = await async_db.execute(
            select(FournisseurAlim).where(FournisseurAlim.nom == "Fournisseur TS Test")
        )
        f = result.scalar_one()
        assert f.created_at is not None
        assert f.updated_at is not None

    async def test_bigserial_pk(self, async_db: AsyncSession):
        """V2 §6.2 BIGSERIAL : PK entier positif."""
        async_db.add(_fournisseur("Fournisseur BIGSERIAL"))
        await async_db.commit()

        result = await async_db.execute(
            select(FournisseurAlim).where(FournisseurAlim.nom == "Fournisseur BIGSERIAL")
        )
        f = result.scalar_one()
        assert isinstance(f.id, int)
        assert f.id > 0


# ── M02 : Contraintes unicité ─────────────────────────────────────────────────

class TestFournisseurAlimUnique:
    async def test_nom_unique_conflict(self, async_db: AsyncSession):
        """V2 §6.2 UNIQUE(nom) : deux fournisseurs avec le même nom sont interdits."""
        async_db.add(_fournisseur("Eurociel Grossiste"))
        await async_db.commit()

        with pytest.raises(IntegrityError):
            async_db.add(_fournisseur("Eurociel Grossiste"))
            await async_db.commit()

    async def test_code_fournisseur_unique_conflict(self, async_db: AsyncSession):
        """V2 §6.2 UNIQUE(code_fournisseur) : deux entrées avec même code interdites."""
        async_db.add(_fournisseur("Eurociel A", code_fournisseur="EUROCIEL"))
        await async_db.commit()

        with pytest.raises(IntegrityError):
            async_db.add(_fournisseur("Eurociel B", code_fournisseur="EUROCIEL"))
            await async_db.commit()

    async def test_null_code_not_unique_constrained(self, async_db: AsyncSession):
        """UNIQUE(code_fournisseur) nullable : deux entrées sans code sont autorisées."""
        async_db.add(_fournisseur("Producteur local 1", code_fournisseur=None))
        await async_db.commit()
        async_db.add(_fournisseur("Producteur local 2", code_fournisseur=None))
        await async_db.commit()

        result = await async_db.execute(
            select(FournisseurAlim).where(FournisseurAlim.code_fournisseur.is_(None))
        )
        rows = result.scalars().all()
        assert len(rows) >= 2


# ── M02 : Requêtes ───────────────────────────────────────────────────────────

class TestFournisseurAlimQuery:
    async def test_query_by_code(self, async_db: AsyncSession):
        """Lookup par code_fournisseur (usage ETL — lookup avant import)."""
        async_db.add(_fournisseur("GNANAM Épicerie", code_fournisseur="GNANAM"))
        await async_db.commit()

        result = await async_db.execute(
            select(FournisseurAlim).where(FournisseurAlim.code_fournisseur == "GNANAM")
        )
        f = result.scalar_one()
        assert f.nom == "GNANAM Épicerie"

    async def test_query_by_type_facturation(self, async_db: AsyncSession):
        """Filtrage par type_facturation (usage admin — identifier les parsers actifs)."""
        async_db.add(_fournisseur("Ethan SARL", code_fournisseur="ETHAN", type_facturation="xlsx"))
        async_db.add(_fournisseur("Autre PDF", type_facturation="pdf"))
        await async_db.commit()

        result = await async_db.execute(
            select(FournisseurAlim).where(FournisseurAlim.type_facturation == "xlsx")
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].code_fournisseur == "ETHAN"
