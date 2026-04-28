"""Schemas Pydantic — Finance épicerie (vendors, factures, stats fournisseurs)."""
from datetime import date
from typing import Optional

from pydantic import BaseModel


class CaHistoriqueItem(BaseModel):
    mois: str        # format 'YYYY-MM'
    montant_cts: int


class CaHistoriqueResponse(BaseModel):
    items: list[CaHistoriqueItem]
    variation_pct: Optional[float]   # variation M vs M-1 (None si < 2 mois de données)


class StockMargesResponse(BaseModel):
    marge_moy_pct: float             # marge réelle moyenne pour ce fournisseur
    marge_catalogue_moy_pct: float   # marge moyenne de tout le catalogue
    nb_articles: int


class AlertePrixItem(BaseModel):
    designation: str
    ean: Optional[str]
    prix_precedent_cts: int
    prix_actuel_cts: int
    variation_pct: float


class AlertesPrixResponse(BaseModel):
    alertes: list[AlertePrixItem]
    date_import_precedente: Optional[str]
    date_import_actuelle: Optional[str]


class QualiteResponse(BaseModel):
    taux_livraison_temps_pct: Optional[float]   # None si < 3 commandes évaluées
    taux_factures_retard_pct: Optional[float]   # None si aucune facture
    nb_commandes_evaluees: int
    nb_factures_total: int


class FinanceVendorRead(BaseModel):
    id: int
    name: str
    code: Optional[str]
    adresse: Optional[str]
    telephone: Optional[str]
    email: Optional[str]

    model_config = {"from_attributes": True}


class FinanceInvoiceRead(BaseModel):
    id: int
    type: str
    numero: str
    date_facture: date
    date_echeance: Optional[date]
    montant_ht: int
    montant_tva: int
    montant_ttc: int
    montant_cts: Optional[int] = None  # F5 : alias montant_ttc exposé à l'UI
    statut: str
    vendor_id: Optional[int]
    supply_order_id: Optional[int]
    vente_id: Optional[int]
    transfer_id: Optional[int]
    reference: Optional[str]

    model_config = {"from_attributes": True}


class CategoryDistribution(BaseModel):
    """F3 : entrée de distribution catégorie (FC_EPICERIE_FOURNISSEURS §stats)."""
    categorie_nom: str
    pct: float


class FournisseurStats(BaseModel):
    """Statistiques agrégées d'un fournisseur."""
    livraisons_mois: int
    achats_mois_cts: int
    delai_paiement_moyen_jours: float
    distribution_categories: list[CategoryDistribution]  # F3 : list, pas dict


class FournisseurRead(BaseModel):
    """Vue consolidée fournisseur pour l'UI épicerie."""
    vendor_id: int
    nom: str
    code: Optional[str]
    nb_articles: int
    ca_mensuel_cts: int
    dette_cts: int
    badge_statut: str  # F2 : a_jour | en_attente | en_retard


class FournisseurListResponse(BaseModel):
    items: list[FournisseurRead]


class FinanceInvoiceListResponse(BaseModel):
    items: list[FinanceInvoiceRead]
