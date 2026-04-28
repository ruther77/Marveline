"""Tests service — InstancePreparationService (F906 FIRE-DRILL régression).

Couvre la régression MARMITE-QPP-01 :
  - Avant fix : `ligne.quantite_par_portion` (attribut inexistant) → AttributeError 500.
  - Après fix : formule `quantite_par_batch × (nb_portions / portions_par_batch)`.

Tests :
  1. Formule consommation correcte (15/20 batch → 0.75 × stock recette).
  2. Stock insuffisant lève StockRequisInsuffisant (pas AttributeError).
  3. Régression : aucun chemin de code ne lit `quantite_par_portion`
     (verrouillé via attribut absent dans le model).
  4. Mouvement de stock créé avec quantité négative correcte.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.models.restaurant.mouvement_stock_restaurant import MouvementStockRestaurant
from app.models.restaurant.recette_type_preparation import RecetteTypePreparation
from app.models.restaurant.type_preparation import TypePreparation
from app.schemas.restaurant.instance_preparation import InstancePreparationCreate
from app.services.restaurant.exceptions import StockRequisInsuffisant
from app.services.restaurant.instance_preparation import InstancePreparationService

from tests.conftest import ASYNC_TEST_DATABASE_URL


_TENANT_RESTO = 3


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
async def async_db(test_engine):
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _seed_marmite_setup(
    db: AsyncSession,
    *,
    nom_recette: str = "Carry poulet",
    portions_par_batch: int = 20,
    quantite_par_batch: Decimal = Decimal("5.000"),
    stock_actuel: Decimal = Decimal("10.000"),
    stock_alerte: Decimal = Decimal("0"),
) -> tuple[TypePreparation, IngredientRestaurant, RecetteTypePreparation]:
    """Helper : crée TypePreparation + IngredientRestaurant + RecetteTypePreparation."""
    ingredient = IngredientRestaurant(
        tenant_id=_TENANT_RESTO,
        nom="Poulet",
        unite_stock="kg",
        stock_actuel=stock_actuel,
        stock_alerte=stock_alerte,
    )
    db.add(ingredient)
    await db.flush()

    tp = TypePreparation(
        tenant_id=_TENANT_RESTO,
        nom=nom_recette,
        portions_par_batch=portions_par_batch,
        seuil_alerte_portions=5,
    )
    db.add(tp)
    await db.flush()

    recette = RecetteTypePreparation(
        tenant_id=_TENANT_RESTO,
        type_preparation_id=tp.id,
        ingredient_id=ingredient.id,
        quantite_par_batch=quantite_par_batch,
    )
    db.add(recette)
    await db.commit()
    return tp, ingredient, recette


# ── Tests F906 régression ────────────────────────────────────────────────────


class TestVerifierEtConsommerRecetteF906:
    @pytest.mark.asyncio
    async def test_formule_quantite_par_batch_ratio(self, async_db):
        """F906 : qte_consommée = quantite_par_batch × (nb_portions / portions_par_batch).

        Setup : batch=20 portions, recette=5kg/batch, stock=10kg.
        Lancement de 15 portions → ratio = 15/20 = 0.75 → conso = 5 × 0.75 = 3.75kg.
        Stock final attendu = 10 - 3.75 = 6.25kg.
        """
        tp, ingredient, _ = await _seed_marmite_setup(async_db)

        service = InstancePreparationService(async_db)
        await service._verifier_et_consommer_recette(tp_id=tp.id, nb_portions=15)
        await async_db.commit()

        await async_db.refresh(ingredient)
        assert ingredient.stock_actuel == Decimal("6.250"), (
            f"F906 régression formule : stock={ingredient.stock_actuel}, attendu 6.250"
        )

    @pytest.mark.asyncio
    async def test_stock_insuffisant_raise_business_exception(self, async_db):
        """Stock insuffisant → StockRequisInsuffisant (pas AttributeError 500)."""
        tp, _, _ = await _seed_marmite_setup(
            async_db, stock_actuel=Decimal("1.000"),  # 1kg, requis 3.75kg
        )

        service = InstancePreparationService(async_db)
        with pytest.raises(StockRequisInsuffisant):
            await service._verifier_et_consommer_recette(tp_id=tp.id, nb_portions=15)

    @pytest.mark.asyncio
    async def test_no_attributeerror_quantite_par_portion(self, async_db):
        """F906 régression : aucune levée d'AttributeError sur `quantite_par_portion`.

        Le modèle RecetteTypePreparation n'a QUE `quantite_par_batch`. Si quelqu'un
        ré-introduit une lecture de `quantite_par_portion`, ce test pète au lieu de
        passer (AttributeError n'est pas un sous-type de StockRequisInsuffisant).
        """
        tp, _, _ = await _seed_marmite_setup(async_db)

        service = InstancePreparationService(async_db)
        # Ne doit lever NI AttributeError NI exception inattendue.
        try:
            await service._verifier_et_consommer_recette(tp_id=tp.id, nb_portions=10)
        except AttributeError as e:  # pragma: no cover — fail explicite
            pytest.fail(f"F906 régression : AttributeError sur recette: {e}")

    @pytest.mark.asyncio
    async def test_mouvement_stock_quantite_negative_correcte(self, async_db):
        """Mouvement créé avec quantité négative = -3.75 (consommation)."""
        from sqlalchemy import select

        tp, ingredient, _ = await _seed_marmite_setup(async_db)
        service = InstancePreparationService(async_db)
        await service._verifier_et_consommer_recette(tp_id=tp.id, nb_portions=15)
        await async_db.commit()

        result = await async_db.execute(
            select(MouvementStockRestaurant).where(MouvementStockRestaurant.ingredient_id == ingredient.id)
        )
        mouvements = list(result.scalars())
        assert len(mouvements) == 1
        mvt = mouvements[0]
        assert mvt.quantite == Decimal("-3.750"), (
            f"Mouvement quantité incorrecte : {mvt.quantite}, attendu -3.750"
        )
        assert mvt.stock_apres == Decimal("6.250")
        assert mvt.type_mouvement == "consommation"

    @pytest.mark.asyncio
    async def test_create_endpoint_full_path_with_recette(self, async_db):
        """E2E service : create() avec recette → consomme stock + retourne instance."""
        tp, ingredient, _ = await _seed_marmite_setup(async_db)

        service = InstancePreparationService(async_db)
        payload = InstancePreparationCreate(
            type_preparation_id=tp.id,
            portions_initiales=10,  # ratio = 10/20 = 0.5 → conso = 2.5kg
            date_cuisine=date.today(),
            notes=None,
        )
        response = await service.create(payload, created_by_id=None)
        await async_db.commit()

        assert response.portions_initiales == 10
        assert response.portions_restantes == 10
        await async_db.refresh(ingredient)
        assert ingredient.stock_actuel == Decimal("7.500")
