"""Tests Session 3 — M00 CategorieProduit + constantes approvisionnement.

Spec : V2 §6.0 + ADR-01 (pas de tenant_id) + ADR-05 (structure plate 3 niveaux)
       + ADR-06 (est_ingredient_resto) + ADR-06-BIS (tva_defaut)

Stratégie : AsyncSession DB réelle (CaroCorp_test) — pas de mocks sur la couche SQL.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.categories_produit import CategorieProduit
from app.constants.approvisionnement import (
    EtlResolutionConflit,
    EtlStatutImport,
    EtlTypeConflit,
    SourceFournisseur,
    ETL_SEUIL_CONFLIT_ALERTE,
    ETL_SEUIL_MATCH,
)


# ── Helper ────────────────────────────────────────────────────────────────────

def _cat(code: str, **kwargs) -> CategorieProduit:
    defaults = dict(nom="Nom test", famille="Famille A", categorie="Cat A")
    defaults.update(kwargs)
    return CategorieProduit(code=code, **defaults)


# ── M00 : Création ────────────────────────────────────────────────────────────

class TestCategorieProduitCreation:
    async def test_create_minimal(self, async_db: AsyncSession):
        """Création avec les champs obligatoires uniquement."""
        async_db.add(_cat("test_min"))
        await async_db.commit()

        result = await async_db.execute(
            select(CategorieProduit).where(CategorieProduit.code == "test_min")
        )
        cat = result.scalar_one()
        assert cat.id is not None
        assert cat.sous_categorie is None

    async def test_defaults_applied(self, async_db: AsyncSession):
        """V2 §6.0 + ADR-06-BIS : valeurs par défaut correctes."""
        async_db.add(_cat("test_def"))
        await async_db.commit()

        result = await async_db.execute(
            select(CategorieProduit).where(CategorieProduit.code == "test_def")
        )
        cat = result.scalar_one()
        assert cat.tva_defaut == pytest.approx(0.20)   # ADR-06-BIS
        assert cat.est_ingredient_resto is False         # ADR-06
        assert cat.priorite_ingredient == 0
        assert cat.ordre_famille == 99
        assert cat.ordre_categorie == 99
        assert cat.is_active is True                     # SoftDeleteMixin

    async def test_no_tenant_id(self):
        """ADR-01 : référentiel partagé, pas de tenant_id."""
        assert not hasattr(CategorieProduit, "tenant_id")

    async def test_sous_categorie_nullable(self, async_db: AsyncSession):
        """ADR-05 niveau 3 : sous_categorie est optionnel."""
        async_db.add(_cat("test_sc_null"))
        await async_db.commit()

        result = await async_db.execute(
            select(CategorieProduit).where(CategorieProduit.code == "test_sc_null")
        )
        assert result.scalar_one().sous_categorie is None

    async def test_sous_categorie_set(self, async_db: AsyncSession):
        """ADR-05 niveau 3 : sous_categorie peut être renseigné."""
        async_db.add(_cat("test_sc_set", sous_categorie="Bières artisanales"))
        await async_db.commit()

        result = await async_db.execute(
            select(CategorieProduit).where(CategorieProduit.code == "test_sc_set")
        )
        assert result.scalar_one().sous_categorie == "Bières artisanales"

    async def test_tva_alimentaire(self, async_db: AsyncSession):
        """ADR-06-BIS : tva_defaut 5.5% pour produits alimentaires."""
        async_db.add(_cat("test_tva_alim", tva_defaut=0.055))
        await async_db.commit()

        result = await async_db.execute(
            select(CategorieProduit).where(CategorieProduit.code == "test_tva_alim")
        )
        assert result.scalar_one().tva_defaut == pytest.approx(0.055)

    async def test_code_unique_constraint(self, async_db: AsyncSession):
        """UNIQUE(code) rejeté par PostgreSQL."""
        from sqlalchemy.exc import IntegrityError

        async_db.add(_cat("dup_code"))
        await async_db.commit()

        with pytest.raises(IntegrityError):
            async_db.add(_cat("dup_code"))
            await async_db.commit()

    async def test_timestamps_set(self, async_db: AsyncSession):
        """TimestampMixin : created_at / updated_at initialisés à la création."""
        async_db.add(_cat("test_ts"))
        await async_db.commit()

        result = await async_db.execute(
            select(CategorieProduit).where(CategorieProduit.code == "test_ts")
        )
        cat = result.scalar_one()
        assert cat.created_at is not None
        assert cat.updated_at is not None


# ── M00 : Requêtes ────────────────────────────────────────────────────────────

class TestCategorieProduitQuery:
    async def test_query_by_famille(self, async_db: AsyncSession):
        """idx_categories_famille : filtrage par famille (niveau 1)."""
        for i in range(3):
            async_db.add(_cat(f"frais_{i}", famille="Produits Frais", categorie="Viandes"))
        async_db.add(_cat("boisson_0", famille="Boissons", categorie="Bières"))
        await async_db.commit()

        result = await async_db.execute(
            select(CategorieProduit).where(CategorieProduit.famille == "Produits Frais")
        )
        rows = result.scalars().all()
        assert len(rows) == 3

    async def test_filter_ingredient_resto(self, async_db: AsyncSession):
        """ADR-06 + idx_categories_ingredient : index partiel WHERE est_ingredient_resto=TRUE."""
        async_db.add(_cat("ing_yes", est_ingredient_resto=True, priorite_ingredient=5))
        async_db.add(_cat("ing_no", est_ingredient_resto=False))
        await async_db.commit()

        result = await async_db.execute(
            select(CategorieProduit).where(
                CategorieProduit.est_ingredient_resto.is_(True)
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].code == "ing_yes"
        assert rows[0].priorite_ingredient == 5

    async def test_soft_delete(self, async_db: AsyncSession):
        """SoftDeleteMixin : is_active=False, enregistrement toujours en DB."""
        cat = _cat("test_soft")
        async_db.add(cat)
        await async_db.commit()

        # Recharger depuis DB pour avoir l'objet attaché à la session
        result = await async_db.execute(
            select(CategorieProduit).where(CategorieProduit.code == "test_soft")
        )
        cat = result.scalar_one()
        cat.soft_delete()
        await async_db.commit()

        result = await async_db.execute(
            select(CategorieProduit).where(CategorieProduit.code == "test_soft")
        )
        cat = result.scalar_one()
        assert cat.is_active is False

    async def test_ordre_tri(self, async_db: AsyncSession):
        """ordre_famille et ordre_categorie permettent le tri d'affichage."""
        async_db.add(_cat("ord_b", ordre_famille=2, ordre_categorie=1))
        async_db.add(_cat("ord_a", ordre_famille=1, ordre_categorie=1))
        await async_db.commit()

        result = await async_db.execute(
            select(CategorieProduit)
            .where(CategorieProduit.code.in_(["ord_a", "ord_b"]))
            .order_by(CategorieProduit.ordre_famille)
        )
        rows = result.scalars().all()
        assert rows[0].code == "ord_a"
        assert rows[1].code == "ord_b"


# ── Constantes : SourceFournisseur ────────────────────────────────────────────

class TestSourceFournisseur:
    def test_is_str_enum(self):
        for member in SourceFournisseur:
            assert isinstance(member, str)

    def test_known_codes(self):
        codes = {f.value for f in SourceFournisseur}
        assert {"METRO", "TAIYAT", "EUROCIEL", "ETHAN", "GNANAM"} == codes

    def test_str_equality(self):
        # Python 3.11 : str(member) retourne "ClassName.MEMBER" — utiliser .value
        assert SourceFournisseur.METRO == "METRO"
        assert SourceFournisseur.TAIYAT.value == "TAIYAT"


# ── Constantes : EtlStatutImport ─────────────────────────────────────────────

class TestEtlStatutImport:
    def test_operational_states(self):
        """PENDING + RUNNING ajoutés pour suivi Celery (amélioration Phase A)."""
        assert EtlStatutImport.PENDING.value == "PENDING"
        assert EtlStatutImport.RUNNING.value == "RUNNING"

    def test_v2_terminal_states(self):
        """V2 §6.3 : SUCCES / PARTIEL / ECHEC."""
        assert EtlStatutImport.SUCCES.value == "SUCCES"
        assert EtlStatutImport.PARTIEL.value == "PARTIEL"
        assert EtlStatutImport.ECHEC.value == "ECHEC"

    def test_preview_workflow_states(self):
        """ADR-25 : PREVIEW / VALIDATED / REJECTED pour workflow facture."""
        assert EtlStatutImport.PREVIEW.value == "PREVIEW"
        assert EtlStatutImport.VALIDATED.value == "VALIDATED"
        assert EtlStatutImport.REJECTED.value == "REJECTED"

    def test_eight_states_total(self):
        assert len(EtlStatutImport) == 8


# ── Constantes : EtlResolutionConflit ────────────────────────────────────────

class TestEtlResolutionConflit:
    def test_v2_values(self):
        """V2 §6.4 : PENDING / MERGED / KEPT_SEPARATE."""
        assert EtlResolutionConflit.PENDING.value == "PENDING"
        assert EtlResolutionConflit.MERGED.value == "MERGED"
        assert EtlResolutionConflit.KEPT_SEPARATE.value == "KEPT_SEPARATE"

    def test_str_compatible(self):
        assert EtlResolutionConflit.MERGED == "MERGED"


# ── Constantes : EtlTypeConflit ───────────────────────────────────────────────

class TestEtlTypeConflit:
    def test_phase_a_types(self):
        """Conservé de Phase A pour interface opérateur (absent spec V2)."""
        assert EtlTypeConflit.EAN_COLLISION.value == "EAN_COLLISION"
        assert EtlTypeConflit.DESIGNATION_PROCHE.value == "DESIGNATION_PROCHE"
        assert EtlTypeConflit.CATEGORIE_INCONNUE.value == "CATEGORIE_INCONNUE"

    def test_three_types(self):
        assert len(EtlTypeConflit) == 3


# ── Constantes : Seuils Jaro-Winkler ─────────────────────────────────────────

class TestSeuilsDeduplication:
    def test_seuil_match_v2(self):
        """V2 ADR-07 : correspondance automatique à 85%."""
        assert ETL_SEUIL_MATCH == pytest.approx(0.85)

    def test_seuil_alerte_inferieur_a_match(self):
        """Invariant : seuil d'alerte < seuil de match."""
        assert ETL_SEUIL_CONFLIT_ALERTE < ETL_SEUIL_MATCH

    def test_seuil_alerte_valeur(self):
        assert ETL_SEUIL_CONFLIT_ALERTE == pytest.approx(0.75)
