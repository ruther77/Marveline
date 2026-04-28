"""Package repositories restaurant — accès DB domaine restaurant (tenant_id=3)."""
from app.repositories.restaurant.alerte_stock import AsyncAlerteStockRepo
from app.repositories.restaurant.categorie_ingredient import AsyncCategorieIngredientRepo
from app.repositories.restaurant.commande import AsyncCommandeRepo
from app.repositories.restaurant.ingredient import AsyncIngredientRepo
from app.repositories.restaurant.instance_preparation import AsyncInstancePreparationRepo
from app.repositories.restaurant.ligne_commande import AsyncLigneCommandeRepo
from app.repositories.restaurant.mouvement_stock import AsyncMouvementStockRepo
from app.repositories.restaurant.side import AsyncSideRepo
from app.repositories.restaurant.table import AsyncTableRepo
from app.repositories.restaurant.type_preparation import (
    AsyncRecetteTypePreparationRepo,
    AsyncTypePreparationRepo,
)
from app.repositories.restaurant.variante_plat import AsyncVariantePlatRepo

__all__ = [
    "AsyncAlerteStockRepo",
    "AsyncCategorieIngredientRepo",
    "AsyncCommandeRepo",
    "AsyncIngredientRepo",
    "AsyncInstancePreparationRepo",
    "AsyncLigneCommandeRepo",
    "AsyncMouvementStockRepo",
    "AsyncRecetteTypePreparationRepo",
    "AsyncSideRepo",
    "AsyncTableRepo",
    "AsyncTypePreparationRepo",
    "AsyncVariantePlatRepo",
]
