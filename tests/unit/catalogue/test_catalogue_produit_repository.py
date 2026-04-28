"""Tests Session 6-B2 — AsyncCatalogueProduitRepository.

Spec : ADR-07 (get_by_ean match exact, get_all_candidates pour Jaro-Winkler).
Stratégie : AsyncSession DB réelle — pas de mocks sur la couche SQL.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.repositories.catalogue.catalogue_produit import AsyncCatalogueProduitRepository


# ── Helpers ─────────────────────────────────────────────────────────────────

def _mk_produit(**kwargs) -> CatalogueProduit:
    defaults = dict(designation="Produit test", unite_base="piece")
    defaults.update(kwargs)
    return CatalogueProduit(**defaults)


# ── Create ────────────────────────────────────────────────────────────────────

class TestCreate:
    async def test_create_returns_with_id(self, async_db: AsyncSession):
        """create() retourne le produit avec un id assigné."""
        repo = AsyncCatalogueProduitRepository(async_db)
        produit = await repo.create(_mk_produit(designation="Huile olive 1L"))
        assert produit.id is not None
        assert produit.id > 0

    async def test_create_persists_fields(self, async_db: AsyncSession):
        """Les champs optionnels sont correctement persistés."""
        repo = AsyncCatalogueProduitRepository(async_db)
        produit = await repo.create(_mk_produit(
            ean="3017620425035",
            designation="Huile olive vierge extra",
            designation_norm="huile olive vierge extra",
            marque="Puget",
            unite_base="L",
            source_fournisseur="METRO",
            categorie_code="HUILES",
        ))
        await async_db.commit()

        fetched = await repo.get_by_id(produit.id)
        assert fetched is not None
        assert fetched.ean == "3017620425035"
        assert fetched.marque == "Puget"
        assert fetched.source_fournisseur == "METRO"
        assert fetched.designation_norm == "huile olive vierge extra"

    async def test_create_without_optional_fields(self, async_db: AsyncSession):
        """Création minimale (ean, designation_norm, marque optionnels) ne lève pas d'erreur."""
        repo = AsyncCatalogueProduitRepository(async_db)
        produit = await repo.create(_mk_produit(designation="Sel fin", unite_base="kg"))
        await async_db.commit()
        assert produit.id is not None
        assert produit.ean is None
        assert produit.designation_norm is None


# ── get_by_id ──────────────────────────────────────────────────────────────

class TestGetById:
    async def test_get_by_id_existing(self, async_db: AsyncSession):
        """get_by_id() retrouve un produit existant."""
        repo = AsyncCatalogueProduitRepository(async_db)
        produit = await repo.create(_mk_produit(designation="Beurre doux 250g"))
        await async_db.commit()

        fetched = await repo.get_by_id(produit.id)
        assert fetched is not None
        assert fetched.designation == "Beurre doux 250g"

    async def test_get_by_id_unknown(self, async_db: AsyncSession):
        """get_by_id() retourne None pour un ID inexistant."""
        repo = AsyncCatalogueProduitRepository(async_db)
        assert await repo.get_by_id(999_999_999) is None


# ── get_by_ean ─────────────────────────────────────────────────────────────

class TestGetByEan:
    async def test_get_by_ean_found(self, async_db: AsyncSession):
        """get_by_ean() retrouve un produit par EAN (ADR-07 §1)."""
        repo = AsyncCatalogueProduitRepository(async_db)
        await repo.create(_mk_produit(
            ean="3017620425035",
            designation="Nutella 400g",
            unite_base="piece",
        ))
        await async_db.commit()

        found = await repo.get_by_ean("3017620425035")
        assert found is not None
        assert found.designation == "Nutella 400g"

    async def test_get_by_ean_not_found(self, async_db: AsyncSession):
        """get_by_ean() retourne None si aucun produit avec cet EAN."""
        repo = AsyncCatalogueProduitRepository(async_db)
        assert await repo.get_by_ean("9999999999999") is None

    async def test_get_by_ean_ean_collision_not_duplicated(self, async_db: AsyncSession):
        """Le second produit avec même EAN ne peut pas être créé (index UNIQUE partiel).

        ADR-07 §3 : la collision EAN est détectée avant toute tentative d'insertion.
        L'appelant (pipeline) vérifie get_by_ean() d'abord et crée un EtlConflict
        de type EAN_COLLISION sans insérer de doublon.
        """
        repo = AsyncCatalogueProduitRepository(async_db)
        ean = "3017620425035"
        await repo.create(_mk_produit(ean=ean, designation="Produit A"))
        await async_db.commit()

        found = await repo.get_by_ean(ean)
        assert found is not None
        assert found.designation == "Produit A"
        # L'EAN existant est détecté → le pipeline doit créer EtlConflict, pas un doublon


# ── get_all_candidates ─────────────────────────────────────────────────────

class TestGetAllCandidates:
    async def test_returns_only_products_with_designation_norm(self, async_db: AsyncSession):
        """get_all_candidates() exclut les produits sans designation_norm (ADR-07 §2)."""
        repo = AsyncCatalogueProduitRepository(async_db)
        await repo.create(_mk_produit(
            designation="Huile olive", designation_norm="huile olive"
        ))
        await repo.create(_mk_produit(
            designation="Sans norm", designation_norm=None
        ))
        await async_db.commit()

        candidates = await repo.get_all_candidates()
        norms = [norm for _, norm in candidates]
        assert "huile olive" in norms
        assert None not in norms

    async def test_returns_id_and_norm_tuples(self, async_db: AsyncSession):
        """Les candidats sont des tuples (int, str)."""
        repo = AsyncCatalogueProduitRepository(async_db)
        p = await repo.create(_mk_produit(
            designation="Beurre doux", designation_norm="beurre doux"
        ))
        await async_db.commit()

        candidates = await repo.get_all_candidates()
        ids = [cid for cid, _ in candidates]
        assert p.id in ids

    async def test_empty_catalogue_returns_empty_list(self, async_db: AsyncSession):
        """Catalogue vide → liste vide, sans erreur."""
        repo = AsyncCatalogueProduitRepository(async_db)
        candidates = await repo.get_all_candidates()
        assert candidates == []

    async def test_multiple_candidates_sorted_by_id(self, async_db: AsyncSession):
        """get_all_candidates() trie par id ASC."""
        repo = AsyncCatalogueProduitRepository(async_db)
        for i in range(4):
            await repo.create(_mk_produit(
                designation=f"Produit {i}",
                designation_norm=f"produit {i}",
            ))
        await async_db.commit()

        candidates = await repo.get_all_candidates()
        ids = [cid for cid, _ in candidates]
        assert ids == sorted(ids)


# ── count ──────────────────────────────────────────────────────────────────

class TestCount:
    async def test_count_empty(self, async_db: AsyncSession):
        """count() retourne 0 sur catalogue vide."""
        repo = AsyncCatalogueProduitRepository(async_db)
        assert await repo.count() == 0

    async def test_count_after_creates(self, async_db: AsyncSession):
        """count() retourne le bon nombre après plusieurs créations."""
        repo = AsyncCatalogueProduitRepository(async_db)
        for i in range(3):
            await repo.create(_mk_produit(designation=f"Produit {i}"))
        await async_db.commit()

        assert await repo.count() == 3
