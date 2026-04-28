"""Tests Session 6-C — run_import() ETL pipeline (ADR-08) + LigneParsee.

Spec : ADR-07 (déduplication), ADR-08 (pipeline), ADR-15 (etl_import_id FK nullable).
Stratégie : AsyncSession DB réelle — pas de mocks sur la couche SQL.

Paire CONFLICT vérifiée empiriquement (JW = 0.828) :
    "pain blanc" (designation_norm existant) vs "pain complet" (entrant) → CONFLICT
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.models.catalogue.etl_import import EtlImport
from app.repositories.catalogue.catalogue_produit import AsyncCatalogueProduitRepository
from app.repositories.catalogue.etl_conflict import AsyncEtlConflictRepository
from app.services.catalogue.etl_import_service import run_import
from app.etl_types import LigneParsee


# ── Helpers ────────────────────────────────────────────────────────────────────


def _mk_import() -> EtlImport:
    return EtlImport()


def _mk_ligne(**kwargs) -> LigneParsee:
    defaults = dict(
        designation="Produit test",
        unite_base="piece",
        source_fournisseur="METRO",
    )
    defaults.update(kwargs)
    return LigneParsee(**defaults)


async def _seed_import(db: AsyncSession) -> EtlImport:
    """Crée et flushe un EtlImport PENDING. Retourne l'objet avec ID."""
    import_obj = _mk_import()
    db.add(import_obj)
    await db.flush()
    await db.refresh(import_obj)
    return import_obj


async def _seed_produit(
    db: AsyncSession,
    designation: str,
    designation_norm: str,
    source_fournisseur: str = "METRO",
    ean: str | None = None,
) -> CatalogueProduit:
    """Crée un CatalogueProduit et le flushe."""
    repo = AsyncCatalogueProduitRepository(db)
    return await repo.create(CatalogueProduit(
        designation=designation,
        designation_norm=designation_norm,
        unite_base="piece",
        source_fournisseur=source_fournisseur,
        ean=ean,
    ))


# ── LigneParsee ────────────────────────────────────────────────────────────────


class TestLigneParsee:
    def test_required_fields(self):
        """designation, unite_base, source_fournisseur sont requis."""
        ligne = LigneParsee(
            designation="Huile olive",
            unite_base="L",
            source_fournisseur="METRO",
        )
        assert ligne.designation == "Huile olive"
        assert ligne.unite_base == "L"
        assert ligne.source_fournisseur == "METRO"

    def test_optional_fields_default_none(self):
        """Tous les champs optionnels ont None comme valeur par défaut."""
        ligne = LigneParsee(designation="X", unite_base="pc", source_fournisseur="S")
        assert ligne.ean is None
        assert ligne.designation_norm is None
        assert ligne.marque is None
        assert ligne.conditionnement is None
        assert ligne.categorie_code is None

    def test_all_fields_assignable(self):
        """Tous les champs optionnels sont correctement assignés."""
        ligne = LigneParsee(
            designation="Nutella 400g",
            unite_base="piece",
            source_fournisseur="METRO",
            ean="3017620425035",
            designation_norm="nutella 400g",
            marque="Ferrero",
            conditionnement="bocal",
            categorie_code="SPREADS",
        )
        assert ligne.ean == "3017620425035"
        assert ligne.marque == "Ferrero"
        assert ligne.categorie_code == "SPREADS"


# ── Cycle de vie statut ────────────────────────────────────────────────────────


class TestRunImportStatutCycle:
    async def test_import_ends_succes_when_no_conflicts(self, async_db: AsyncSession):
        """Import sans conflit ni erreur → statut SUCCES."""
        import_obj = await _seed_import(async_db)

        await run_import(async_db, [_mk_ligne(designation="Beurre doux 250g")], import_obj.id)
        await async_db.commit()

        refreshed = await async_db.get(EtlImport, import_obj.id)
        assert refreshed is not None
        assert refreshed.statut == "SUCCES"

    async def test_import_ends_partiel_when_conflicts(self, async_db: AsyncSession):
        """Import avec au moins un conflit → statut PARTIEL."""
        await _seed_produit(async_db, "pain blanc", "pain blanc")
        import_obj = await _seed_import(async_db)

        await run_import(
            async_db,
            [_mk_ligne(designation="pain complet")],
            import_obj.id,
        )
        await async_db.commit()

        refreshed = await async_db.get(EtlImport, import_obj.id)
        assert refreshed is not None
        assert refreshed.statut == "PARTIEL"

    async def test_import_ends_partiel_when_errors(self, async_db: AsyncSession):
        """Import avec au moins une erreur de ligne → statut PARTIEL."""
        import_obj = await _seed_import(async_db)

        invalid = LigneParsee(designation="", unite_base="piece", source_fournisseur="METRO")
        await run_import(async_db, [invalid], import_obj.id)
        await async_db.commit()

        refreshed = await async_db.get(EtlImport, import_obj.id)
        assert refreshed is not None
        assert refreshed.statut == "PARTIEL"

    async def test_nb_lignes_total_set(self, async_db: AsyncSession):
        """nb_lignes_total est mis à jour au début de l'import."""
        import_obj = await _seed_import(async_db)
        lignes = [_mk_ligne(designation=f"Produit {i}") for i in range(3)]

        await run_import(async_db, lignes, import_obj.id)
        await async_db.commit()

        refreshed = await async_db.get(EtlImport, import_obj.id)
        assert refreshed is not None
        assert refreshed.nb_lignes_total == 3


# ── Import vide ────────────────────────────────────────────────────────────────


class TestRunImportEmpty:
    async def test_empty_import_succes(self, async_db: AsyncSession):
        """Import avec liste vide → SUCCES, tous compteurs à 0."""
        import_obj = await _seed_import(async_db)

        await run_import(async_db, [], import_obj.id)
        await async_db.commit()

        refreshed = await async_db.get(EtlImport, import_obj.id)
        assert refreshed is not None
        assert refreshed.statut == "SUCCES"
        assert refreshed.nb_lignes_total == 0
        assert refreshed.nb_lignes_ok == 0
        assert refreshed.nb_lignes_conflit == 0
        assert refreshed.nb_lignes_erreur == 0


# ── Nouveau produit (NEW) ──────────────────────────────────────────────────────


class TestRunImportNew:
    async def test_new_product_no_ean_created(self, async_db: AsyncSession):
        """Ligne sans EAN, catalogue vide → NEW → produit créé, nb_lignes_ok=1."""
        import_obj = await _seed_import(async_db)

        await run_import(
            async_db,
            [_mk_ligne(designation="Sel fin de Guérande", unite_base="kg")],
            import_obj.id,
        )
        await async_db.commit()

        produit_repo = AsyncCatalogueProduitRepository(async_db)
        count = await produit_repo.count()
        assert count == 1

        refreshed = await async_db.get(EtlImport, import_obj.id)
        assert refreshed is not None
        assert refreshed.nb_lignes_ok == 1
        assert refreshed.nb_lignes_conflit == 0
        assert refreshed.nb_lignes_erreur == 0

    async def test_new_product_with_valid_ean_stores_ean(self, async_db: AsyncSession):
        """Ligne avec EAN valide non existant → NEW → produit créé avec EAN."""
        import_obj = await _seed_import(async_db)

        await run_import(
            async_db,
            [_mk_ligne(designation="Nutella 400g", ean="3017620425035")],
            import_obj.id,
        )
        await async_db.commit()

        produit_repo = AsyncCatalogueProduitRepository(async_db)
        produit = await produit_repo.get_by_ean("3017620425035")
        assert produit is not None
        assert produit.designation == "Nutella 400g"
        assert produit.source_fournisseur == "METRO"

    async def test_new_product_with_invalid_ean_ignores_ean(self, async_db: AsyncSession):
        """EAN invalide (longueur 6) → ignoré → produit créé sans EAN."""
        import_obj = await _seed_import(async_db)

        await run_import(
            async_db,
            [_mk_ligne(designation="Produit EAN invalide", ean="123456")],
            import_obj.id,
        )
        await async_db.commit()

        produit_repo = AsyncCatalogueProduitRepository(async_db)
        count = await produit_repo.count()
        assert count == 1
        produit = (await produit_repo.get_all_candidates())[0]
        # on vérifie via count ; EAN non stocké car invalide
        assert await produit_repo.get_by_ean("123456") is None

    async def test_invalid_ligne_missing_designation_counts_as_erreur(
        self, async_db: AsyncSession
    ):
        """Ligne avec designation vide → erreur → nb_lignes_erreur=1, aucun produit créé."""
        import_obj = await _seed_import(async_db)

        invalid = LigneParsee(designation="", unite_base="piece", source_fournisseur="METRO")
        await run_import(async_db, [invalid], import_obj.id)
        await async_db.commit()

        refreshed = await async_db.get(EtlImport, import_obj.id)
        assert refreshed is not None
        assert refreshed.nb_lignes_erreur == 1
        assert refreshed.nb_lignes_ok == 0

        produit_repo = AsyncCatalogueProduitRepository(async_db)
        assert await produit_repo.count() == 0

    async def test_invalid_ligne_missing_source_counts_as_erreur(
        self, async_db: AsyncSession
    ):
        """Ligne avec source_fournisseur vide → erreur → nb_lignes_erreur=1."""
        import_obj = await _seed_import(async_db)

        invalid = LigneParsee(designation="Produit X", unite_base="piece", source_fournisseur="")
        await run_import(async_db, [invalid], import_obj.id)
        await async_db.commit()

        refreshed = await async_db.get(EtlImport, import_obj.id)
        assert refreshed is not None
        assert refreshed.nb_lignes_erreur == 1


# ── Match (JW ≥ 0.85) ─────────────────────────────────────────────────────────


class TestRunImportMatch:
    async def test_match_does_not_create_duplicate(self, async_db: AsyncSession):
        """Score JW ≥ 0.85 → MATCH → produit non recréé, nb_lignes_ok++."""
        await _seed_produit(
            async_db,
            designation="Huile olive vierge",
            designation_norm="huile olive vierge",
        )
        import_obj = await _seed_import(async_db)

        # désignation identique → score 1.0 → MATCH
        await run_import(
            async_db,
            [_mk_ligne(designation="Huile olive vierge")],
            import_obj.id,
        )
        await async_db.commit()

        produit_repo = AsyncCatalogueProduitRepository(async_db)
        assert await produit_repo.count() == 1  # pas de doublon

        refreshed = await async_db.get(EtlImport, import_obj.id)
        assert refreshed is not None
        assert refreshed.nb_lignes_ok == 1
        assert refreshed.nb_lignes_conflit == 0


# ── Conflit désignation proche (CONFLICT zone [0.75, 0.85[) ──────────────────


class TestRunImportDesignationProche:
    async def test_conflict_creates_etl_conflict(self, async_db: AsyncSession):
        """Score JW dans [0.75, 0.85[ → CONFLICT → EtlConflict DESIGNATION_PROCHE créé."""
        # "pain blanc" vs "pain complet" → JW = 0.828 → CONFLICT
        await _seed_produit(async_db, "pain blanc", "pain blanc")
        import_obj = await _seed_import(async_db)

        await run_import(
            async_db,
            [_mk_ligne(designation="pain complet")],
            import_obj.id,
        )
        await async_db.commit()

        conflict_repo = AsyncEtlConflictRepository(async_db)
        conflicts = await conflict_repo.list_by_import(import_obj.id)
        assert len(conflicts) == 1
        assert conflicts[0].type_conflit == "DESIGNATION_PROCHE"
        assert conflicts[0].suggestion == "MERGED"
        assert conflicts[0].score_similarite is not None
        assert float(conflicts[0].score_similarite) >= 0.75
        assert float(conflicts[0].score_similarite) < 0.85

    async def test_conflict_stores_designations(self, async_db: AsyncSession):
        """Le conflit stocke designation_entrante et designation_existante."""
        await _seed_produit(async_db, "pain blanc", "pain blanc")
        import_obj = await _seed_import(async_db)

        await run_import(
            async_db,
            [_mk_ligne(designation="pain complet")],
            import_obj.id,
        )
        await async_db.commit()

        conflict_repo = AsyncEtlConflictRepository(async_db)
        conflicts = await conflict_repo.list_by_import(import_obj.id)
        assert len(conflicts) == 1
        assert conflicts[0].designation_entrante == "pain complet"
        assert conflicts[0].designation_existante == "pain blanc"

    async def test_conflict_stores_ean_pair_when_available(
        self, async_db: AsyncSession
    ):
        """DESIGNATION_PROCHE stocke ean_a/ean_b si disponibles.

        Paire JW=0.828 (validée empiriquement) pour tomber dans [0.75, 0.85[.
        """
        await _seed_produit(
            async_db,
            designation="pain blanc",
            designation_norm="pain blanc",
            ean="3017620425035",
        )
        import_obj = await _seed_import(async_db)

        await run_import(
            async_db,
            [_mk_ligne(
                designation="pain complet",
                ean="4008400402229",
            )],
            import_obj.id,
        )
        await async_db.commit()

        conflict_repo = AsyncEtlConflictRepository(async_db)
        conflicts = await conflict_repo.list_by_import(import_obj.id)
        assert len(conflicts) == 1
        assert conflicts[0].type_conflit == "DESIGNATION_PROCHE"
        assert conflicts[0].ean_a == "4008400402229"
        assert conflicts[0].ean_b == "3017620425035"
        assert conflicts[0].suggestion == "MERGED"

    async def test_conflict_nb_lignes_conflit_incremented(self, async_db: AsyncSession):
        """nb_lignes_conflit est incrémenté pour chaque conflit."""
        await _seed_produit(async_db, "pain blanc", "pain blanc")
        import_obj = await _seed_import(async_db)

        await run_import(
            async_db,
            [_mk_ligne(designation="pain complet")],
            import_obj.id,
        )
        await async_db.commit()

        refreshed = await async_db.get(EtlImport, import_obj.id)
        assert refreshed is not None
        assert refreshed.nb_lignes_conflit == 1
        assert refreshed.nb_lignes_ok == 0


# ── Collision EAN ─────────────────────────────────────────────────────────────


class TestRunImportEanCollision:
    async def test_ean_collision_different_supplier_creates_conflict(
        self, async_db: AsyncSession
    ):
        """Même EAN, source différente → EAN_COLLISION → EtlConflict créé."""
        await _seed_produit(
            async_db,
            designation="Nutella 400g",
            designation_norm="nutella 400g",
            source_fournisseur="METRO",
            ean="3017620425035",
        )
        import_obj = await _seed_import(async_db)

        await run_import(
            async_db,
            [_mk_ligne(
                designation="Nutella 400g",
                ean="3017620425035",
                source_fournisseur="LECLERC",
            )],
            import_obj.id,
        )
        await async_db.commit()

        conflict_repo = AsyncEtlConflictRepository(async_db)
        conflicts = await conflict_repo.list_by_import(import_obj.id)
        assert len(conflicts) == 1
        assert conflicts[0].type_conflit == "EAN_COLLISION"
        assert conflicts[0].score_similarite is None
        assert conflicts[0].ean_a == "3017620425035"
        assert conflicts[0].ean_b == "3017620425035"
        assert conflicts[0].suggestion == "KEPT_SEPARATE"

    async def test_ean_collision_no_new_product_created(self, async_db: AsyncSession):
        """EAN_COLLISION → le produit existant n'est pas dupliqué."""
        await _seed_produit(
            async_db,
            designation="Nutella 400g",
            designation_norm="nutella 400g",
            source_fournisseur="METRO",
            ean="3017620425035",
        )
        import_obj = await _seed_import(async_db)

        await run_import(
            async_db,
            [_mk_ligne(
                designation="Nutella 400g",
                ean="3017620425035",
                source_fournisseur="LECLERC",
            )],
            import_obj.id,
        )
        await async_db.commit()

        produit_repo = AsyncCatalogueProduitRepository(async_db)
        assert await produit_repo.count() == 1  # pas de doublon

    async def test_ean_same_supplier_is_ok_not_collision(self, async_db: AsyncSession):
        """Même EAN, même source → doublon exact → nb_lignes_ok, pas de conflit."""
        await _seed_produit(
            async_db,
            designation="Nutella 400g",
            designation_norm="nutella 400g",
            source_fournisseur="METRO",
            ean="3017620425035",
        )
        import_obj = await _seed_import(async_db)

        await run_import(
            async_db,
            [_mk_ligne(designation="Nutella 400g", ean="3017620425035")],
            import_obj.id,
        )
        await async_db.commit()

        conflict_repo = AsyncEtlConflictRepository(async_db)
        conflicts = await conflict_repo.list_by_import(import_obj.id)
        assert len(conflicts) == 0

        refreshed = await async_db.get(EtlImport, import_obj.id)
        assert refreshed is not None
        assert refreshed.nb_lignes_ok == 1
        assert refreshed.nb_lignes_conflit == 0


# ── Compteurs mixtes ───────────────────────────────────────────────────────────


class TestRunImportCountersMixed:
    async def test_counters_mixed_batch(self, async_db: AsyncSession):
        """2 NEW + 1 CONFLICT + 1 erreur → compteurs corrects, statut PARTIEL."""
        await _seed_produit(async_db, "pain blanc", "pain blanc")
        import_obj = await _seed_import(async_db)

        lignes = [
            _mk_ligne(designation="Beurre doux"),    # NEW → ok
            _mk_ligne(designation="Sel fin"),         # NEW → ok
            _mk_ligne(designation="pain complet"),    # CONFLICT
            LigneParsee(designation="", unite_base="", source_fournisseur=""),  # erreur
        ]
        await run_import(async_db, lignes, import_obj.id)
        await async_db.commit()

        refreshed = await async_db.get(EtlImport, import_obj.id)
        assert refreshed is not None
        assert refreshed.nb_lignes_total == 4
        assert refreshed.nb_lignes_ok == 2
        assert refreshed.nb_lignes_conflit == 1
        assert refreshed.nb_lignes_erreur == 1
        assert refreshed.statut == "PARTIEL"

    async def test_import_not_found_raises_value_error(self, async_db: AsyncSession):
        """EtlImport introuvable → ValueError levée."""
        with pytest.raises(ValueError, match="999999"):
            await run_import(async_db, [], 999_999)
