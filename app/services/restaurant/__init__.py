"""Services — domaine Restaurant.

Exports publics du module. Chaque service encapsule la logique métier
d'un agrégat du domaine restaurant.
"""
from app.services.restaurant.categorie_ingredient import CategorieIngredientService
from app.services.restaurant.commande import CommandeService
from app.services.restaurant.dashboard import DashboardService
from app.services.restaurant.ingredient import IngredientService
from app.services.restaurant.instance_preparation import InstancePreparationService
from app.services.restaurant.ligne_commande import LigneCommandeService
from app.services.restaurant.mouvement_stock import MouvementStockService
from app.services.restaurant.side import SideService
from app.services.restaurant.table import TableService
from app.services.restaurant.type_preparation import TypePreparationService
from app.services.restaurant.variante_plat import VariantePlatService

__all__ = [
    "CategorieIngredientService",
    "CommandeService",
    "DashboardService",
    "IngredientService",
    "InstancePreparationService",
    "LigneCommandeService",
    "MouvementStockService",
    "SideService",
    "TableService",
    "TypePreparationService",
    "VariantePlatService",
]
