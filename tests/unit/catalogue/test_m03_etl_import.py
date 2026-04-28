"""Tests Session 5 — M03 EtlImport.

Spec : V2 §6.3 + états opérationnels Celery (PENDING, RUNNING).
Stratégie : AsyncSession DB réelle (CaroCorp_test) — pas de mocks sur la couche SQL.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.etl_import import EtlImport


# ── Helper ────────────────────────────────────────────────────────────────────

def _import(**kwargs) -> EtlImport:
    defaults = dict(statut="PENDING")
    defaults.update(kwargs)
    return EtlImport(**defaults)


# ── M03 : Création ────────────────────────────────────────────────────────────

class TestEtlImportCreation:
    async def test_create_minimal(self, async_db: AsyncSession):
        """V2 §6.3 : création avec statut uniquement (champs optionnels absents)."""
        async_db.add(_import())
        await async_db.commit()

        result = await async_db.execute(
            select(EtlImport).where(EtlImport.statut == "PENDING")
        )
        imp = result.scalars().first()
        assert imp is not None
        assert imp.id is not None
        assert imp.fournisseur_id is None
        assert imp.fichier_source is None
        assert imp.nb_lignes_total is None
        assert imp.nb_lignes_ok == 0
        assert imp.nb_lignes_conflit == 0
        assert imp.nb_lignes_erreur == 0
        assert imp.erreur_detail is None

    async def test_no_tenant_id(self):
        """ADR-02 : log ETL partagé, pas de tenant_id."""
        assert not hasattr(EtlImport, "tenant_id")

    async def test_no_soft_delete(self):
        """M03 : log append-only, pas de is_active."""
        assert not hasattr(EtlImport, "is_active")

    async def test_create_metro_import(self, async_db: AsyncSession):
        """V2 §6.3 : création d'un import METRO complet."""
        async_db.add(_import(
            fichier_source="metro_2026-03-10.csv",
            nb_lignes_total=1500,
            nb_lignes_ok=1480,
            nb_lignes_conflit=15,
            nb_lignes_erreur=5,
            statut="SUCCES",
        ))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlImport).where(EtlImport.fichier_source == "metro_2026-03-10.csv")
        )
        imp = result.scalar_one()
        assert imp.statut == "SUCCES"
        assert imp.nb_lignes_total == 1500
        assert imp.nb_lignes_ok == 1480
        assert imp.nb_lignes_conflit == 15
        assert imp.nb_lignes_erreur == 5

    async def test_create_echec_with_detail(self, async_db: AsyncSession):
        """V2 §6.3 : import échoué avec détail d'erreur."""
        async_db.add(_import(
            fichier_source="taiyat_corrupt.xlsx",
            statut="ECHEC",
            erreur_detail="ValueError: colonne 'prix_ht' introuvable ligne 42",
        ))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlImport).where(EtlImport.fichier_source == "taiyat_corrupt.xlsx")
        )
        imp = result.scalar_one()
        assert imp.statut == "ECHEC"
        assert "ligne 42" in imp.erreur_detail

    async def test_timestamps_set(self, async_db: AsyncSession):
        """TimestampMixin : created_at / updated_at initialisés à la création."""
        async_db.add(_import(fichier_source="ts_test.csv"))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlImport).where(EtlImport.fichier_source == "ts_test.csv")
        )
        imp = result.scalar_one()
        assert imp.created_at is not None
        assert imp.updated_at is not None

    async def test_bigserial_pk(self, async_db: AsyncSession):
        """V2 §6.3 BIGSERIAL : PK entier positif."""
        async_db.add(_import(fichier_source="bigserial_test.csv"))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlImport).where(EtlImport.fichier_source == "bigserial_test.csv")
        )
        imp = result.scalar_one()
        assert isinstance(imp.id, int)
        assert imp.id > 0


# ── M03 : Cycle de vie statuts ────────────────────────────────────────────────

class TestEtlImportStatuts:
    async def test_statut_pending(self, async_db: AsyncSession):
        """Statut initial PENDING (attente worker Celery)."""
        async_db.add(_import(statut="PENDING", fichier_source="pending_test.csv"))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlImport).where(EtlImport.fichier_source == "pending_test.csv")
        )
        imp = result.scalar_one()
        assert imp.statut == "PENDING"

    async def test_statut_running(self, async_db: AsyncSession):
        """Statut RUNNING (worker actif)."""
        async_db.add(_import(statut="RUNNING", fichier_source="running_test.csv"))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlImport).where(EtlImport.fichier_source == "running_test.csv")
        )
        imp = result.scalar_one()
        assert imp.statut == "RUNNING"

    async def test_statut_partiel(self, async_db: AsyncSession):
        """Statut PARTIEL : conflits restant en attente."""
        async_db.add(_import(
            statut="PARTIEL",
            fichier_source="partiel_test.csv",
            nb_lignes_conflit=3,
        ))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlImport).where(EtlImport.fichier_source == "partiel_test.csv")
        )
        imp = result.scalar_one()
        assert imp.statut == "PARTIEL"
        assert imp.nb_lignes_conflit == 3

    async def test_invalid_statut_rejected(self, async_db: AsyncSession):
        """CHECK constraint : statut invalide rejeté par la DB."""
        async_db.add(_import(statut="invalide_lowercase", fichier_source="invalid_test.csv"))
        with pytest.raises(Exception):
            await async_db.commit()

    async def test_update_statut(self, async_db: AsyncSession):
        """Mise à jour du statut PENDING → SUCCES."""
        imp = _import(statut="PENDING", fichier_source="update_test.csv")
        async_db.add(imp)
        await async_db.commit()

        imp.statut = "SUCCES"
        imp.nb_lignes_ok = 100
        await async_db.commit()

        result = await async_db.execute(
            select(EtlImport).where(EtlImport.fichier_source == "update_test.csv")
        )
        updated = result.scalar_one()
        assert updated.statut == "SUCCES"
        assert updated.nb_lignes_ok == 100


# ── M03 : Requêtes ────────────────────────────────────────────────────────────

class TestEtlImportQuery:
    async def test_query_by_statut(self, async_db: AsyncSession):
        """Filtrage par statut (monitoring ETL)."""
        async_db.add(_import(statut="SUCCES", fichier_source="ok1.csv"))
        async_db.add(_import(statut="SUCCES", fichier_source="ok2.csv"))
        async_db.add(_import(statut="ECHEC", fichier_source="fail1.csv"))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlImport).where(EtlImport.statut == "SUCCES")
        )
        rows = result.scalars().all()
        assert len(rows) == 2

    async def test_query_fournisseur_id_null(self, async_db: AsyncSession):
        """Import sans fournisseur_id (fichier manuel sans FK)."""
        async_db.add(_import(statut="SUCCES", fichier_source="manuel.csv", fournisseur_id=None))
        await async_db.commit()

        result = await async_db.execute(
            select(EtlImport).where(
                EtlImport.fichier_source == "manuel.csv",
                EtlImport.fournisseur_id.is_(None),
            )
        )
        imp = result.scalar_one()
        assert imp.fournisseur_id is None
