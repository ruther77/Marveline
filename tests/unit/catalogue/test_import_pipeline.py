"""Tests Session 6-E — scripts.etl.import_pipeline.

Stratégie : tester _create_import_record (AsyncSession réelle) + enqueue_import
patché. run_pipeline n'est pas testé directement (crée sa propre session).

Références :
    ADR-08 : rôle du CLI orchestrateur
    test_etl_tasks.py : tests du helper Celery
"""
import dataclasses
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.etl_import import EtlImport
from app.repositories.catalogue.etl_import import AsyncEtlImportRepository
from app.etl_types import LigneParsee
from scripts.etl.import_pipeline import (
    _create_import_record,
    enqueue_import,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mk_ligne(**kwargs) -> LigneParsee:
    defaults = dict(
        designation="Produit test",
        unite_base="piece",
        source_fournisseur="METRO",
    )
    defaults.update(kwargs)
    return LigneParsee(**defaults)


# ── _create_import_record ─────────────────────────────────────────────────────


class TestCreateImportRecord:
    async def test_cree_pending_sans_fournisseur(self, async_db: AsyncSession):
        """Crée un EtlImport PENDING sans fournisseur_id ni fichier_source."""
        etl_id = await _create_import_record(async_db, None, None)
        await async_db.commit()

        repo = AsyncEtlImportRepository(async_db)
        obj = await repo.get_by_id(etl_id)
        assert obj is not None
        assert obj.statut == "PENDING"
        assert obj.fournisseur_id is None
        assert obj.fichier_source is None

    async def test_cree_pending_avec_fournisseur(self, async_db: AsyncSession):
        """Crée un EtlImport PENDING avec fournisseur_id et fichier_source."""
        etl_id = await _create_import_record(
            async_db,
            fournisseur_id=42,
            fichier_source="metro_2026-03-10.csv",
        )
        await async_db.commit()

        repo = AsyncEtlImportRepository(async_db)
        obj = await repo.get_by_id(etl_id)
        assert obj is not None
        assert obj.fournisseur_id == 42
        assert obj.fichier_source == "metro_2026-03-10.csv"
        assert obj.statut == "PENDING"

    async def test_retourne_id_positif(self, async_db: AsyncSession):
        """L'id retourné est un entier positif."""
        etl_id = await _create_import_record(async_db, None, None)
        assert isinstance(etl_id, int)
        assert etl_id > 0

    async def test_deux_appels_retournent_ids_distincts(self, async_db: AsyncSession):
        """Deux appels créent deux enregistrements distincts."""
        id1 = await _create_import_record(async_db, None, None)
        id2 = await _create_import_record(async_db, None, None)
        assert id1 != id2

    async def test_compteurs_initialises_a_zero(self, async_db: AsyncSession):
        """Les compteurs nb_lignes_* sont 0 à la création."""
        etl_id = await _create_import_record(async_db, None, None)
        await async_db.commit()

        repo = AsyncEtlImportRepository(async_db)
        obj = await repo.get_by_id(etl_id)
        assert obj.nb_lignes_ok == 0
        assert obj.nb_lignes_conflit == 0
        assert obj.nb_lignes_erreur == 0
        assert obj.nb_lignes_total is None


# ── enqueue_import ────────────────────────────────────────────────────────────


class TestEnqueueImport:
    def test_appelle_delay_avec_bons_args(self):
        """enqueue_import() appelle run_etl_import.delay(etl_import_id, lignes_data)."""
        lignes_data = [dataclasses.asdict(_mk_ligne(designation="Sel fin"))]

        with patch("app.tasks.etl_tasks.run_etl_import") as mock_task:
            enqueue_import(99, lignes_data)

        mock_task.delay.assert_called_once_with(99, lignes_data)

    def test_appelle_delay_liste_vide(self):
        """enqueue_import() fonctionne avec une liste vide."""
        with patch("app.tasks.etl_tasks.run_etl_import") as mock_task:
            enqueue_import(1, [])
        mock_task.delay.assert_called_once_with(1, [])

    def test_appelle_delay_multiple_lignes(self):
        """enqueue_import() transmet toutes les lignes sérialisées."""
        lignes_data = [
            dataclasses.asdict(_mk_ligne(designation=f"Produit {i}"))
            for i in range(5)
        ]
        with patch("app.tasks.etl_tasks.run_etl_import") as mock_task:
            enqueue_import(7, lignes_data)
        _, call_lignes = mock_task.delay.call_args[0]
        assert len(call_lignes) == 5
