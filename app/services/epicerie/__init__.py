"""Package services Épicerie."""
from app.services.epicerie.inventaire import (
    ajuster_stock,
    comptage_inventaire,
    set_seuil_alerte,
)
from app.services.epicerie.vente import encaisser, annuler_vente
from app.services.epicerie.supply_order import (
    creer_commande,
    changer_statut,
    recevoir_commande,
)
from app.services.epicerie.transfert import (
    creer_transfert,
    valider_transfert,
    annuler_transfert,
)
from app.services.epicerie.dashboard import get_dashboard
from app.services.epicerie.fournisseurs import (
    list_fournisseurs,
    get_fournisseur_stats,
    list_factures_fournisseur,
)

__all__ = [
    "ajuster_stock",
    "comptage_inventaire",
    "set_seuil_alerte",
    "encaisser",
    "annuler_vente",
    "creer_commande",
    "changer_statut",
    "recevoir_commande",
    "creer_transfert",
    "valider_transfert",
    "annuler_transfert",
    "get_dashboard",
    "list_fournisseurs",
    "get_fournisseur_stats",
    "list_factures_fournisseur",
]
