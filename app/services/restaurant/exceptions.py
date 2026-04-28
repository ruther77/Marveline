"""Exceptions domaine restaurant — codes métier retournés par les services.

Codes HTTP :
  409 : PortionsEpuisees, StockIngredientInsuffisant, CommandeDejaPayee,
        LigneNonAnnulable, CommandeNonOuverte, TableDejaOccupee
  422 : PortionsInsuffisantes, StockRequisInsuffisant
"""
from app.core.exceptions import AppException


class PortionsEpuisees(AppException):
    """Instance de préparation épuisée — portions_restantes = 0."""
    status_code = 409
    error_code = "PORTIONS_EPUISEES"
    message = "La marmite est épuisée"


class StockIngredientInsuffisant(AppException):
    """Stock ingrédient insuffisant pour servir le side ou la proteïne."""
    status_code = 409
    error_code = "STOCK_INGREDIENT_INSUFFISANT"
    message = "Stock ingrédient insuffisant"


class PortionsInsuffisantes(AppException):
    """Requête incohérente — portions demandées > disponibles."""
    status_code = 422
    error_code = "PORTIONS_INSUFFISANTES"
    message = "Quantité de portions insuffisante"


class CommandeDejaPayee(AppException):
    """Tentative de modification sur une commande déjà PAYEE ou ANNULEE."""
    status_code = 409
    error_code = "COMMANDE_DEJA_PAYEE"
    message = "La commande est déjà clôturée"


class LigneNonAnnulable(AppException):
    """Ligne en cours de préparation — ne peut pas être annulée."""
    status_code = 409
    error_code = "LIGNE_NON_ANNULABLE"
    message = "La ligne est en cours de préparation et ne peut pas être annulée"


class CommandeNonOuverte(AppException):
    """Opération impossible — la commande n'est pas en statut OUVERTE."""
    status_code = 409
    error_code = "COMMANDE_NON_OUVERTE"
    message = "La commande n'est pas ouverte"


class TableDejaOccupee(AppException):
    """Une commande OUVERTE existe déjà sur cette table."""
    status_code = 409
    error_code = "TABLE_DEJA_OCCUPEE"
    message = "La table est déjà occupée"


class StockRequisInsuffisant(AppException):
    """Stock insuffisant pour cuisiner la recette d'un type de préparation."""
    status_code = 422
    error_code = "STOCK_REQUIS_INSUFFISANT"
    message = "Stock insuffisant pour préparer la recette"
