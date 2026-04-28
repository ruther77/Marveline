"""Package models restaurant — Domaine restaurant (tenant_id=3).

Tables du domaine :
  Salle        : TableRestaurant
  Menu         : VariantePlat, SideRestaurant
  Cuisine      : TypePreparation, RecetteTypePreparation, InstancePreparation
  Commandes    : CommandeRestaurant, LigneCommandeRestaurant
  Ingrédients  : CategorieIngredient, IngredientRestaurant, MouvementStockRestaurant
  Alertes      : AlerteStockRestaurant
"""
from app.models.restaurant.table_restaurant import TableRestaurant
from app.models.restaurant.categorie_ingredient import CategorieIngredient
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.models.restaurant.mouvement_stock_restaurant import MouvementStockRestaurant
from app.models.restaurant.type_preparation import TypePreparation
from app.models.restaurant.recette_type_preparation import RecetteTypePreparation
from app.models.restaurant.instance_preparation import InstancePreparation
from app.models.restaurant.variante_plat import VariantePlat
from app.models.restaurant.side_restaurant import SideRestaurant
from app.models.restaurant.variante_side import VarianteSide
from app.models.restaurant.commande_restaurant import CommandeRestaurant
from app.models.restaurant.ligne_commande_restaurant import LigneCommandeRestaurant
from app.models.restaurant.alerte_stock_restaurant import AlerteStockRestaurant
from app.models.restaurant.transfer_request import TransferRequest, TransferRequestLine
from app.models.restaurant.ingredient_epicerie_mapping import IngredientEpicerieMapping

__all__ = [
    "TableRestaurant",
    "CategorieIngredient",
    "IngredientRestaurant",
    "MouvementStockRestaurant",
    "TypePreparation",
    "RecetteTypePreparation",
    "InstancePreparation",
    "VariantePlat",
    "SideRestaurant",
    "VarianteSide",
    "CommandeRestaurant",
    "LigneCommandeRestaurant",
    "AlerteStockRestaurant",
    "TransferRequest",
    "TransferRequestLine",
    "IngredientEpicerieMapping",
]
