"""Tests Session 5 — M04 EtlConflict.

Spec : V2 §6.4 + ADR-07 (Jaro-Winkler) + ADR-15 (etl_import_id nullable).
Stratégie : AsyncSession DB réelle (CaroCorp_test) — pas de mocks sur la couche SQL.
"""
import pytest
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.etl_conflict import EtlConflict


# ── Helper ────────────────────────────────────────────────────────────────────

def _conflict(designation_entrante: str, **kwargs) -> EtlConflict:
    defaults = dict(resolution="PENDING")
    defaults.update(kwargs)
    return EtlConflict(designation_entrante=designation_entrante, **defaults)


# ── M04 : Création ────────────────────────────────────────────────────────────

class TestEtlConflictCreation:
    async def test_create_minimal(self, async_db: AsyncSession):
        """V2 §6.4 : création avec designation_entrante uniquement."""
        async_db.add(_conflict("Lait demi écrémé 1L UHT"))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(
                EtlConflict.designation_entrante == "Lait demi écrémé 1L UHT"
            )
        )
        c = result.scalar_one()
        assert c.id is not None
        assert c.resolution == "PENDING"
        assert c.etl_import_id is None
        assert c.catalogue_produit_id is None
        assert c.score_similarite is None
        assert c.type_conflit is None
        assert c.designation_existante is None

    async def test_no_tenant_id(self):
        """ADR-02 : log déduplication partagé, pas de tenant_id."""
        assert not hasattr(EtlConflict, "tenant_id")

    async def test_no_soft_delete(self):
        """M04 : log append-only, pas de is_active."""
        assert not hasattr(EtlConflict, "is_active")

    async def test_create_designation_proche(self, async_db: AsyncSession):
        """ADR-07 : conflit DESIGNATION_PROCHE avec score Jaro-Winkler."""
        async_db.add(_conflict(
            "Pasta Penne Barilla 500g",
            designation_existante="Penne Barilla 500g",
            score_similarite=Decimal("0.812"),
            type_conflit="DESIGNATION_PROCHE",
            resolution="PENDING",
        ))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(
                EtlConflict.designation_entrante == "Pasta Penne Barilla 500g"
            )
        )
        c = result.scalar_one()
        assert c.type_conflit == "DESIGNATION_PROCHE"
        assert c.score_similarite == Decimal("0.812")
        assert c.resolution == "PENDING"

    async def test_create_ean_collision(self, async_db: AsyncSession):
        """V2 §6.4 : conflit EAN_COLLISION sans score (collision exacte)."""
        async_db.add(_conflict(
            "Coca-Cola 33cl fournisseur A",
            type_conflit="EAN_COLLISION",
            score_similarite=None,  # pas de score pour collision EAN
            resolution="PENDING",
        ))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(
                EtlConflict.designation_entrante == "Coca-Cola 33cl fournisseur A"
            )
        )
        c = result.scalar_one()
        assert c.type_conflit == "EAN_COLLISION"
        assert c.score_similarite is None

    async def test_create_categorie_inconnue(self, async_db: AsyncSession):
        """V2 §6.4 : conflit CATEGORIE_INCONNUE."""
        async_db.add(_conflict(
            "Produit catégorie inconnue XYZ",
            type_conflit="CATEGORIE_INCONNUE",
            resolution="PENDING",
        ))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(
                EtlConflict.designation_entrante == "Produit catégorie inconnue XYZ"
            )
        )
        c = result.scalar_one()
        assert c.type_conflit == "CATEGORIE_INCONNUE"

    async def test_timestamps_set(self, async_db: AsyncSession):
        """TimestampMixin : created_at / updated_at initialisés à la création."""
        async_db.add(_conflict("Produit TS test"))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(
                EtlConflict.designation_entrante == "Produit TS test"
            )
        )
        c = result.scalar_one()
        assert c.created_at is not None
        assert c.updated_at is not None

    async def test_bigserial_pk(self, async_db: AsyncSession):
        """V2 §6.4 BIGSERIAL : PK entier positif."""
        async_db.add(_conflict("Produit BIGSERIAL conflit"))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(
                EtlConflict.designation_entrante == "Produit BIGSERIAL conflit"
            )
        )
        c = result.scalar_one()
        assert isinstance(c.id, int)
        assert c.id > 0


# ── M04 : Cycle de résolution ─────────────────────────────────────────────────

class TestEtlConflictResolution:
    async def test_resolution_merged(self, async_db: AsyncSession):
        """Résolution MERGED : désignation fusionnée dans le catalogue."""
        async_db.add(_conflict(
            "Pasta Rigatoni 500g",
            resolution="MERGED",
        ))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(
                EtlConflict.designation_entrante == "Pasta Rigatoni 500g"
            )
        )
        c = result.scalar_one()
        assert c.resolution == "MERGED"

    async def test_resolution_kept_separate(self, async_db: AsyncSession):
        """Résolution KEPT_SEPARATE : conservé comme entrée distincte."""
        async_db.add(_conflict(
            "Fromage Comté 12 mois",
            resolution="KEPT_SEPARATE",
        ))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(
                EtlConflict.designation_entrante == "Fromage Comté 12 mois"
            )
        )
        c = result.scalar_one()
        assert c.resolution == "KEPT_SEPARATE"

    async def test_invalid_resolution_rejected(self, async_db: AsyncSession):
        """CHECK constraint : résolution invalide rejetée par la DB."""
        async_db.add(_conflict("Produit invalide", resolution="invalid_value"))
        with pytest.raises(Exception):
            await async_db.commit()

    async def test_update_resolution(self, async_db: AsyncSession):
        """Mise à jour de résolution PENDING → MERGED."""
        c = _conflict("Produit à résoudre", resolution="PENDING")
        async_db.add(c)
        await async_db.commit()

        c.resolution = "MERGED"
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(
                EtlConflict.designation_entrante == "Produit à résoudre"
            )
        )
        updated = result.scalar_one()
        assert updated.resolution == "MERGED"


# ── M04 : ADR-15 (etl_import_id nullable) ────────────────────────────────────

class TestEtlConflictAdr15:
    async def test_etl_import_id_nullable(self, async_db: AsyncSession):
        """ADR-15 : etl_import_id nullable — conflit survit à la suppression du log."""
        async_db.add(_conflict("Conflit sans import", etl_import_id=None))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(
                EtlConflict.designation_entrante == "Conflit sans import"
            )
        )
        c = result.scalar_one()
        assert c.etl_import_id is None

    async def test_multiple_conflicts_same_import(self, async_db: AsyncSession):
        """Plusieurs conflits peuvent référencer le même etl_import_id."""
        for i in range(3):
            async_db.add(_conflict(
                f"Produit conflit {i}",
                etl_import_id=999,
            ))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(EtlConflict.etl_import_id == 999)
        )
        rows = result.scalars().all()
        assert len(rows) == 3


# ── M04 : Requêtes ────────────────────────────────────────────────────────────

class TestEtlConflictQuery:
    async def test_query_pending_conflicts(self, async_db: AsyncSession):
        """Filtrage des conflits en attente de résolution (tableau de bord)."""
        async_db.add(_conflict("Attente 1", resolution="PENDING"))
        async_db.add(_conflict("Attente 2", resolution="PENDING"))
        async_db.add(_conflict("Résolu", resolution="MERGED"))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(EtlConflict.resolution == "PENDING")
        )
        rows = result.scalars().all()
        assert len(rows) == 2

    async def test_query_by_type_conflit(self, async_db: AsyncSession):
        """Filtrage par type_conflit pour reporting ETL."""
        async_db.add(_conflict("EAN A", type_conflit="EAN_COLLISION"))
        async_db.add(_conflict("EAN B", type_conflit="EAN_COLLISION"))
        async_db.add(_conflict("Désig proche", type_conflit="DESIGNATION_PROCHE"))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(EtlConflict.type_conflit == "EAN_COLLISION")
        )
        rows = result.scalars().all()
        assert len(rows) == 2

    async def test_score_range_filter(self, async_db: AsyncSession):
        """ADR-07 : filtrage dans la plage d'alerte [0.75, 0.85[."""
        async_db.add(_conflict("Score 0.80", score_similarite=Decimal("0.800")))
        async_db.add(_conflict("Score 0.76", score_similarite=Decimal("0.760")))
        async_db.add(_conflict("Score 0.90", score_similarite=Decimal("0.900")))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlConflict).where(
                EtlConflict.score_similarite >= Decimal("0.75"),
                EtlConflict.score_similarite < Decimal("0.85"),
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 2
