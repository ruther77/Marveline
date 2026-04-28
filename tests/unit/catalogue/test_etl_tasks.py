"""Tests Session 6-D — app.tasks.etl_tasks (_execute_import_with_session).

Stratégie : tests de _execute_import_with_session avec AsyncSession réelle.
La Celery task run_etl_import elle-même n'est pas testée ici (bridge asyncio.run()
non compatible avec pytest-asyncio ; la logique est entièrement dans le helper).

Références :
    ADR-08 : pipeline ETL Celery
    test_etl_import_service.py : même setup de DB utilisé comme base
"""
import dataclasses
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.models.catalogue.etl_import import EtlImport
from app.repositories.catalogue.catalogue_produit import AsyncCatalogueProduitRepository
from app.repositories.catalogue.etl_conflict import AsyncEtlConflictRepository
from app.repositories.catalogue.etl_import import AsyncEtlImportRepository
from app.etl_types import LigneParsee
from app.tasks.etl_tasks import _execute_import_with_session


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _seed_import(db: AsyncSession) -> int:
    """Crée un EtlImport PENDING et retourne son id."""
    repo = AsyncEtlImportRepository(db)
    obj = EtlImport(statut="PENDING")
    created = await repo.create(obj)
    await db.commit()
    return created.id


async def _seed_produit(
    db: AsyncSession,
    designation: str,
    designation_norm: str,
    source_fournisseur: str = "METRO",
    ean: str | None = None,
) -> CatalogueProduit:
    repo = AsyncCatalogueProduitRepository(db)
    produit = await repo.create(CatalogueProduit(
        designation=designation,
        designation_norm=designation_norm,
        unite_base="piece",
        source_fournisseur=source_fournisseur,
        ean=ean,
    ))
    await db.commit()
    return produit


def _mk_ligne(**kwargs) -> LigneParsee:
    defaults = dict(
        designation="Produit test",
        unite_base="piece",
        source_fournisseur="METRO",
    )
    defaults.update(kwargs)
    return LigneParsee(**defaults)


def _ligne_as_dict(ligne: LigneParsee) -> dict:
    return dataclasses.asdict(ligne)


# ── Désérialisation dict → LigneParsee ───────────────────────────────────────


class TestLigneParseeRoundtrip:
    def test_asdict_roundtrip_complet(self):
        """dataclasses.asdict() puis LigneParsee(**d) conserve tous les champs."""
        ligne = LigneParsee(
            designation="Huile olive",
            unite_base="L",
            source_fournisseur="METRO",
            ean="3017620425035",
            designation_norm="huile olive",
            marque="Puget",
            conditionnement="bouteille",
            categorie_code="HUILES",
        )
        d = dataclasses.asdict(ligne)
        reconstruit = LigneParsee(**d)
        assert reconstruit == ligne

    def test_asdict_roundtrip_minimal(self):
        """Champs optionnels None conservés dans le round-trip."""
        ligne = LigneParsee(
            designation="Sel fin",
            unite_base="kg",
            source_fournisseur="POMONA",
        )
        d = dataclasses.asdict(ligne)
        reconstruit = LigneParsee(**d)
        assert reconstruit.ean is None
        assert reconstruit.designation_norm is None
        assert reconstruit.marque is None

    def test_asdict_json_serializable(self):
        """Le dict produit par asdict() est JSON-sérialisable (Celery)."""
        import json
        ligne = _mk_ligne(ean="3017620425035", designation_norm="produit test")
        d = _ligne_as_dict(ligne)
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
        parsed = json.loads(serialized)
        assert parsed["designation"] == "Produit test"


# ── _execute_import_with_session — cas nominaux ───────────────────────────────


class TestExecuteImportStatut:
    async def test_succes_sur_lignes_nouvelles(self, async_db: AsyncSession):
        """Statut SUCCES si toutes les lignes sont nouvelles (0 conflit, 0 erreur)."""
        etl_id = await _seed_import(async_db)
        lignes_data = [
            _ligne_as_dict(_mk_ligne(designation="Beurre doux 250g")),
            _ligne_as_dict(_mk_ligne(designation="Crème fraîche 20cl")),
        ]
        await _execute_import_with_session(async_db, etl_id, lignes_data)

        repo = AsyncEtlImportRepository(async_db)
        obj = await repo.get_by_id(etl_id)
        assert obj is not None
        assert obj.statut == "SUCCES"
        assert obj.nb_lignes_total == 2
        assert obj.nb_lignes_ok == 2
        assert obj.nb_lignes_conflit == 0
        assert obj.nb_lignes_erreur == 0

    async def test_partiel_sur_conflit(self, async_db: AsyncSession):
        """Statut PARTIEL si au moins un conflit de désignation proche."""
        await _seed_produit(
            async_db,
            designation="pain blanc",
            designation_norm="pain blanc",
        )
        etl_id = await _seed_import(async_db)
        # "pain complet" est proche de "pain blanc" (JW ≈ 0.828 → CONFLICT)
        lignes_data = [
            _ligne_as_dict(_mk_ligne(designation="pain complet")),
        ]
        await _execute_import_with_session(async_db, etl_id, lignes_data)

        repo = AsyncEtlImportRepository(async_db)
        obj = await repo.get_by_id(etl_id)
        assert obj.statut == "PARTIEL"
        assert obj.nb_lignes_conflit == 1
        assert obj.nb_lignes_ok == 0

    async def test_partiel_sur_erreur(self, async_db: AsyncSession):
        """Statut PARTIEL si au moins une ligne invalide (champ requis manquant)."""
        etl_id = await _seed_import(async_db)
        # ligne avec designation vide → _RESULT_ERREUR
        lignes_data = [
            {"designation": "", "unite_base": "piece", "source_fournisseur": "METRO",
             "ean": None, "designation_norm": None, "marque": None,
             "conditionnement": None, "categorie_code": None},
        ]
        await _execute_import_with_session(async_db, etl_id, lignes_data)

        repo = AsyncEtlImportRepository(async_db)
        obj = await repo.get_by_id(etl_id)
        assert obj.statut == "PARTIEL"
        assert obj.nb_lignes_erreur == 1

    async def test_succes_liste_vide(self, async_db: AsyncSession):
        """Liste vide → statut SUCCES, compteurs à 0."""
        etl_id = await _seed_import(async_db)
        await _execute_import_with_session(async_db, etl_id, [])

        repo = AsyncEtlImportRepository(async_db)
        obj = await repo.get_by_id(etl_id)
        assert obj.statut == "SUCCES"
        assert obj.nb_lignes_total == 0
        assert obj.nb_lignes_ok == 0

    async def test_valuerror_si_import_introuvable(self, async_db: AsyncSession):
        """ValueError levée si etl_import_id inexistant en DB."""
        with pytest.raises(ValueError, match="introuvable"):
            await _execute_import_with_session(async_db, 999_999_999, [])


# ── _execute_import_with_session — commit + persistance ──────────────────────


class TestExecuteImportPersistance:
    async def test_produits_crees_en_db(self, async_db: AsyncSession):
        """Les nouveaux produits sont persistés en DB après l'appel."""
        etl_id = await _seed_import(async_db)
        lignes_data = [
            _ligne_as_dict(_mk_ligne(designation="Tomate cerise", ean="1234567890123")),
        ]
        await _execute_import_with_session(async_db, etl_id, lignes_data)

        produit_repo = AsyncCatalogueProduitRepository(async_db)
        found = await produit_repo.get_by_ean("1234567890123")
        assert found is not None
        assert found.designation == "Tomate cerise"

    async def test_conflit_cree_en_db(self, async_db: AsyncSession):
        """Un EtlConflict DESIGNATION_PROCHE est persisté en DB."""
        await _seed_produit(
            async_db,
            designation="pain blanc",
            designation_norm="pain blanc",
        )
        etl_id = await _seed_import(async_db)
        lignes_data = [
            _ligne_as_dict(_mk_ligne(designation="pain complet")),
        ]
        await _execute_import_with_session(async_db, etl_id, lignes_data)

        conflict_repo = AsyncEtlConflictRepository(async_db)
        count = await conflict_repo.count_pending_by_import(etl_id)
        assert count == 1

    async def test_ean_collision_cree_conflit(self, async_db: AsyncSession):
        """EAN identique de source différente crée un conflit EAN_COLLISION."""
        ean = "3017620425035"
        await _seed_produit(
            async_db,
            designation="Nutella 400g",
            designation_norm="nutella 400g",
            source_fournisseur="METRO",
            ean=ean,
        )
        etl_id = await _seed_import(async_db)
        # Même EAN, source différente → EAN_COLLISION
        lignes_data = [
            _ligne_as_dict(_mk_ligne(
                designation="Nutella 400g",
                ean=ean,
                source_fournisseur="POMONA",
            )),
        ]
        await _execute_import_with_session(async_db, etl_id, lignes_data)

        conflict_repo = AsyncEtlConflictRepository(async_db)
        count = await conflict_repo.count_pending_by_import(etl_id)
        assert count == 1

        repo = AsyncEtlImportRepository(async_db)
        obj = await repo.get_by_id(etl_id)
        assert obj.statut == "PARTIEL"
        assert obj.nb_lignes_conflit == 1
