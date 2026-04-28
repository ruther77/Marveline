"""Schemas Pydantic — Stock épicerie."""
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field

TYPES_AJUSTEMENT = Literal['PERTE', 'ENTREE', 'SORTIE', 'AJUSTEMENT']


class EpicerieStockRead(BaseModel):
    """Vue stock d'un produit (produit + stock fusionnés).

    id et derniere_mise_a_jour sont None quand le produit n'a pas encore
    de ligne epicerie_stock (LEFT JOIN — stock virtuel à quantite=0).
    """
    id: Optional[int] = None
    produit_id: int
    designation: str
    categorie: Optional[str]
    fournisseur_source: Optional[str]  # vendor code ou nom
    image_url: Optional[str] = None
    quantite: float
    seuil_alerte: float
    prix_achat_cts: int = 0
    prix_unitaire_cts: int = 0
    unite_vente: str = 'U'
    unite_base: Optional[str] = None
    colisage: Optional[int] = None
    volume_unitaire_ml: Optional[int] = None
    conditionnement: Optional[str] = None
    statut_badge: str  # ok | bas | rupture
    derniere_mise_a_jour: Optional[datetime] = None
    actif: bool


class EpicerieStockSummary(BaseModel):
    total_articles: int
    nb_ruptures: int
    nb_stock_bas: int
    valeur_stock_cts: int


class EpicerieStockListResponse(BaseModel):
    items: list[EpicerieStockRead]
    total: int
    page: int
    per_page: int


class SeuilUpdate(BaseModel):
    """I3 : champ renommé seuil_alerte → seuil (FC_EPICERIE_INVENTAIRE §seuil)."""
    seuil: float = Field(..., ge=0)


class AjustementCreate(BaseModel):
    produit_id: int
    type_ajustement: TYPES_AJUSTEMENT
    quantite: float = Field(..., gt=0)
    raison: Optional[str] = None


class AjustementResponse(BaseModel):
    """I4 : réponse détaillée POST /ajustement (FC_EPICERIE_INVENTAIRE §ajustement)."""
    success: bool
    ancien_stock: float
    nouveau_stock: float
    quantite_ajustee: float
    mouvement_id: int


class ComptageItem(BaseModel):
    produit_id: int
    quantite_comptee: float = Field(..., ge=0)
    notes: Optional[str] = None


class ComptageRequest(BaseModel):
    lignes: list[ComptageItem] = Field(..., min_length=1)
    notes: str = Field(..., min_length=1)


class ComptageLineResult(BaseModel):
    """I5 : résultat par ligne du comptage physique."""
    produit_id: int
    designation: str
    ancien_stock: float
    nouveau_stock: float
    ecart: float
    ecart_pct: Optional[float]
    ajustement_cree: bool


class ComptageResponse(BaseModel):
    """I5 : réponse détaillée POST /comptage (FC_EPICERIE_INVENTAIRE §comptage)."""
    nb_lignes: int
    nb_ajustements: int
    message: str
    lignes: list[ComptageLineResult] = []


class StockMovementRead(BaseModel):
    """I7 : champs additionnels signed_quantite, produit_designation, created_by_name."""
    id: int
    produit_id: int
    type: str
    quantite: float
    signed_quantite: float  # quantite signée (positive = entrée, négative = sortie)
    stock_apres: float
    date_mouvement: datetime
    reference: Optional[str]
    notes: Optional[str]
    created_by_id: Optional[int]
    produit_designation: Optional[str] = None
    created_by_name: Optional[str] = None

    model_config = {"from_attributes": True}


class StockMovementsListResponse(BaseModel):
    items: list[StockMovementRead]
    total: int
    page: int
    per_page: int
