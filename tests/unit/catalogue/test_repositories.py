"""Tests Session 6-A — Repositories M03+M04.

Spec : V2 ADR-07 (Jaro-Winkler) + ADR-08 (ETL Celery) + ADR-15 (FK nullable).
Stratégie : AsyncSession DB réelle — pas de mocks sur la couche SQL.
"""
import pytest
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.etl_import import EtlImport
from app.models.catalogue.etl_conflict import EtlConflict
from app.repositories.catalogue.etl_import import AsyncEtlImportRepository
from app.repositories.catalogue.etl_conflict import AsyncEtlConflictRepository


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mk_import(**kwargs) -> EtlImport:
    defaults = dict(statut="PENDING")
    defaults.update(kwargs)
    return EtlImport(**defaults)


def _mk_conflict(designation_entrante: str, **kwargs) -> EtlConflict:
    defaults = dict(resolution="PENDING")
    defaults.update(kwargs)
    return EtlConflict(designation_entrante=designation_entrante, **defaults)


# ── AsyncEtlImportRepository ───────────────────────────────────────────────────

class TestEtlImportRepositoryCreate:
    async def test_create_returns_with_id(self, async_db: AsyncSession):
        """create() retourne l'objet avec un id assigné."""
        repo = AsyncEtlImportRepository(async_db)
        imp = await repo.create(_mk_import(fichier_source="test_create.csv"))
        assert imp.id is not None
        assert imp.id > 0
        assert imp.statut == "PENDING"

    async def test_create_minimal_defaults(self, async_db: AsyncSession):
        """Création minimale : compteurs initialisés à 0."""
        repo = AsyncEtlImportRepository(async_db)
        imp = await repo.create(_mk_import())
        await async_db.commit()

        fetched = await repo.get_by_id(imp.id)
        assert fetched is not None
        assert fetched.nb_lignes_ok == 0
        assert fetched.nb_lignes_conflit == 0
        assert fetched.nb_lignes_erreur == 0
        assert fetched.erreur_detail is None


class TestEtlImportRepositoryGetById:
    async def test_get_by_id_existing(self, async_db: AsyncSession):
        """get_by_id() retrouve un import existant."""
        repo = AsyncEtlImportRepository(async_db)
        imp = await repo.create(_mk_import(fichier_source="get_test.csv"))
        await async_db.commit()

        fetched = await repo.get_by_id(imp.id)
        assert fetched is not None
        assert fetched.fichier_source == "get_test.csv"

    async def test_get_by_id_unknown(self, async_db: AsyncSession):
        """get_by_id() retourne None pour un ID inexistant."""
        repo = AsyncEtlImportRepository(async_db)
        result = await repo.get_by_id(999_999_999)
        assert result is None


class TestEtlImportRepositoryUpdateStatut:
    async def test_update_statut_succes(self, async_db: AsyncSession):
        """Transition PENDING → SUCCES sans erreur_detail."""
        repo = AsyncEtlImportRepository(async_db)
        imp = await repo.create(_mk_import(fichier_source="statut_ok.csv"))
        await async_db.commit()

        imp.nb_lignes_total = 100
        imp.nb_lignes_ok = 100
        updated = await repo.update_statut(imp, "SUCCES")
        await async_db.commit()

        assert updated.statut == "SUCCES"
        assert updated.erreur_detail is None

    async def test_update_statut_echec_with_detail(self, async_db: AsyncSession):
        """Transition RUNNING → ECHEC avec erreur_detail."""
        repo = AsyncEtlImportRepository(async_db)
        imp = await repo.create(_mk_import(statut="RUNNING", fichier_source="echec.csv"))
        await async_db.commit()

        updated = await repo.update_statut(
            imp, "ECHEC", erreur_detail="ValueError: col manquante"
        )
        await async_db.commit()

        assert updated.statut == "ECHEC"
        assert "col manquante" in updated.erreur_detail

    async def test_update_statut_no_detail_unchanged(self, async_db: AsyncSession):
        """update_statut sans erreur_detail ne touche pas le champ existant."""
        repo = AsyncEtlImportRepository(async_db)
        imp = await repo.create(
            _mk_import(statut="RUNNING", fichier_source="no_detail.csv")
        )
        imp.erreur_detail = "erreur précédente"
        await async_db.commit()

        # Mise à jour sans erreur_detail → le champ ne doit pas changer
        await repo.update_statut(imp, "ECHEC")
        await async_db.commit()

        fetched = await repo.get_by_id(imp.id)
        assert fetched.erreur_detail == "erreur précédente"


class TestEtlImportRepositoryListAndCount:
    async def test_list_by_statut_filters_correctly(self, async_db: AsyncSession):
        """list_by_statut retourne uniquement les imports du statut demandé."""
        repo = AsyncEtlImportRepository(async_db)
        await repo.create(_mk_import(statut="SUCCES", fichier_source="ok1.csv"))
        await repo.create(_mk_import(statut="SUCCES", fichier_source="ok2.csv"))
        await repo.create(_mk_import(statut="ECHEC", fichier_source="fail.csv"))
        await async_db.commit()

        results = await repo.list_by_statut("SUCCES")
        assert len(results) == 2
        assert all(r.statut == "SUCCES" for r in results)

    async def test_list_by_statut_respects_limit(self, async_db: AsyncSession):
        """list_by_statut respecte le paramètre limit."""
        repo = AsyncEtlImportRepository(async_db)
        for i in range(5):
            await repo.create(_mk_import(statut="PENDING", fichier_source=f"p{i}.csv"))
        await async_db.commit()

        results = await repo.list_by_statut("PENDING", limit=3)
        assert len(results) == 3

    async def test_count_by_statut(self, async_db: AsyncSession):
        """count_by_statut retourne le bon nombre."""
        repo = AsyncEtlImportRepository(async_db)
        await repo.create(_mk_import(statut="RUNNING", fichier_source="r1.csv"))
        await repo.create(_mk_import(statut="RUNNING", fichier_source="r2.csv"))
        await repo.create(_mk_import(statut="SUCCES", fichier_source="s1.csv"))
        await async_db.commit()

        assert await repo.count_by_statut("RUNNING") == 2
        assert await repo.count_by_statut("SUCCES") == 1
        assert await repo.count_by_statut("ECHEC") == 0


# ── AsyncEtlConflictRepository ─────────────────────────────────────────────────

class TestEtlConflictRepositoryCreate:
    async def test_create_returns_with_id(self, async_db: AsyncSession):
        """create() retourne le conflit avec id assigné."""
        repo = AsyncEtlConflictRepository(async_db)
        conflict = await repo.create(_mk_conflict("Huile olive 1L"))
        assert conflict.id is not None
        assert conflict.resolution == "PENDING"

    async def test_create_many_all_persisted(self, async_db: AsyncSession):
        """create_many() persiste tous les conflits du batch."""
        repo = AsyncEtlConflictRepository(async_db)
        batch = [
            _mk_conflict(f"Produit batch {i}", etl_import_id=42)
            for i in range(4)
        ]
        created = await repo.create_many(batch)
        await async_db.commit()

        assert len(created) == 4
        assert all(c.id is not None for c in created)
        assert all(c.id > 0 for c in created)

    async def test_create_many_empty_list(self, async_db: AsyncSession):
        """create_many([]) retourne une liste vide sans erreur."""
        repo = AsyncEtlConflictRepository(async_db)
        result = await repo.create_many([])
        assert result == []


class TestEtlConflictRepositoryGetById:
    async def test_get_by_id_existing(self, async_db: AsyncSession):
        """get_by_id() retrouve un conflit existant."""
        repo = AsyncEtlConflictRepository(async_db)
        c = await repo.create(_mk_conflict("Tomate cerise 250g"))
        await async_db.commit()

        fetched = await repo.get_by_id(c.id)
        assert fetched is not None
        assert fetched.designation_entrante == "Tomate cerise 250g"

    async def test_get_by_id_unknown(self, async_db: AsyncSession):
        """get_by_id() retourne None pour un ID inexistant."""
        repo = AsyncEtlConflictRepository(async_db)
        assert await repo.get_by_id(999_999_999) is None


class TestEtlConflictRepositoryListPending:
    async def test_list_pending_excludes_resolved(self, async_db: AsyncSession):
        """list_pending() exclut les conflits MERGED et KEPT_SEPARATE."""
        repo = AsyncEtlConflictRepository(async_db)
        await repo.create(_mk_conflict("Attente A", resolution="PENDING"))
        await repo.create(_mk_conflict("Attente B", resolution="PENDING"))
        await repo.create(_mk_conflict("Fusionné", resolution="MERGED"))
        await repo.create(_mk_conflict("Séparé", resolution="KEPT_SEPARATE"))
        await async_db.commit()

        pending = await repo.list_pending()
        assert len(pending) == 2
        assert all(c.resolution == "PENDING" for c in pending)

    async def test_list_pending_sorted_by_score_desc(self, async_db: AsyncSession):
        """list_pending() trie par score_similarite DESC (ADR-07 : ambiguïtés prioritaires)."""
        repo = AsyncEtlConflictRepository(async_db)
        await repo.create(_mk_conflict("Score bas", score_similarite=Decimal("0.760")))
        await repo.create(_mk_conflict("Score haut", score_similarite=Decimal("0.840")))
        await repo.create(_mk_conflict("Score moyen", score_similarite=Decimal("0.810")))
        await async_db.commit()

        pending = await repo.list_pending()
        scores = [c.score_similarite for c in pending if c.score_similarite is not None]
        assert scores == sorted(scores, reverse=True)

    async def test_list_pending_limit(self, async_db: AsyncSession):
        """list_pending() respecte le paramètre limit."""
        repo = AsyncEtlConflictRepository(async_db)
        for i in range(6):
            await repo.create(_mk_conflict(f"Produit limite {i}"))
        await async_db.commit()

        result = await repo.list_pending(limit=3)
        assert len(result) == 3


class TestEtlConflictRepositoryListByImport:
    async def test_list_by_import_all(self, async_db: AsyncSession):
        """list_by_import() retourne tous les conflits d'un import."""
        repo = AsyncEtlConflictRepository(async_db)
        for i in range(3):
            await repo.create(_mk_conflict(f"Import 77 produit {i}", etl_import_id=77))
        await repo.create(_mk_conflict("Autre import", etl_import_id=88))
        await async_db.commit()

        results = await repo.list_by_import(77)
        assert len(results) == 3
        assert all(c.etl_import_id == 77 for c in results)

    async def test_list_by_import_with_resolution_filter(self, async_db: AsyncSession):
        """list_by_import() avec filtre résolution."""
        repo = AsyncEtlConflictRepository(async_db)
        await repo.create(_mk_conflict("Pending import 55", etl_import_id=55, resolution="PENDING"))
        await repo.create(_mk_conflict("Merged import 55", etl_import_id=55, resolution="MERGED"))
        await async_db.commit()

        pending = await repo.list_by_import(55, resolution="PENDING")
        assert len(pending) == 1
        assert pending[0].resolution == "PENDING"

    async def test_list_by_import_empty(self, async_db: AsyncSession):
        """list_by_import() retourne une liste vide si aucun conflit."""
        repo = AsyncEtlConflictRepository(async_db)
        result = await repo.list_by_import(999_888)
        assert result == []


class TestEtlConflictRepositoryResolve:
    async def test_resolve_to_merged(self, async_db: AsyncSession):
        """resolve() passe un conflit de PENDING à MERGED."""
        repo = AsyncEtlConflictRepository(async_db)
        c = await repo.create(_mk_conflict("Produit à fusionner"))
        await async_db.commit()

        updated = await repo.resolve(c, "MERGED")
        await async_db.commit()

        assert updated.resolution == "MERGED"

    async def test_resolve_to_kept_separate(self, async_db: AsyncSession):
        """resolve() passe un conflit de PENDING à KEPT_SEPARATE."""
        repo = AsyncEtlConflictRepository(async_db)
        c = await repo.create(_mk_conflict("Produit à garder séparé"))
        await async_db.commit()

        updated = await repo.resolve(c, "KEPT_SEPARATE")
        await async_db.commit()

        assert updated.resolution == "KEPT_SEPARATE"

    async def test_resolve_persisted_in_db(self, async_db: AsyncSession):
        """La résolution est bien persistée et lisible via get_by_id."""
        repo = AsyncEtlConflictRepository(async_db)
        c = await repo.create(_mk_conflict("Persistance résolution"))
        await async_db.commit()

        await repo.resolve(c, "MERGED")
        await async_db.commit()

        fetched = await repo.get_by_id(c.id)
        assert fetched.resolution == "MERGED"


class TestEtlConflictRepositoryCountPending:
    async def test_count_pending_by_import(self, async_db: AsyncSession):
        """count_pending_by_import() retourne le bon compte (ADR-07 indicateur PARTIEL)."""
        repo = AsyncEtlConflictRepository(async_db)
        for i in range(3):
            await repo.create(_mk_conflict(f"Pending {i}", etl_import_id=100))
        await repo.create(_mk_conflict("Merged", etl_import_id=100, resolution="MERGED"))
        await async_db.commit()

        count = await repo.count_pending_by_import(100)
        assert count == 3

    async def test_count_pending_zero(self, async_db: AsyncSession):
        """count_pending_by_import() retourne 0 si aucun PENDING."""
        repo = AsyncEtlConflictRepository(async_db)
        await repo.create(_mk_conflict("Tout résolu", etl_import_id=200, resolution="MERGED"))
        await async_db.commit()

        count = await repo.count_pending_by_import(200)
        assert count == 0

    async def test_count_pending_unknown_import(self, async_db: AsyncSession):
        """count_pending_by_import() retourne 0 pour un import inexistant (ADR-15)."""
        repo = AsyncEtlConflictRepository(async_db)
        count = await repo.count_pending_by_import(999_777)
        assert count == 0
