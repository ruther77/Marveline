"""Schemas Pydantic — Dashboard épicerie."""
from pydantic import BaseModel


class EpicerieKpiVentes(BaseModel):
    ca_jour_cts: int
    ca_semaine_cts: int
    ca_mois_cts: int
    nb_tickets_jour: int
    panier_moyen_cts: int


class EpicerieKpiStock(BaseModel):
    total_articles: int
    nb_ruptures: int
    nb_stock_bas: int
    valeur_stock_cts: int


class EpicerieKpiAchats(BaseModel):
    commandes_en_cours: int
    montant_commandes_cts: int
    dette_fournisseurs_cts: int
    livraisons_semaine: int


class EpicerieDashboard(BaseModel):
    ventes: EpicerieKpiVentes
    stock: EpicerieKpiStock
    achats: EpicerieKpiAchats
