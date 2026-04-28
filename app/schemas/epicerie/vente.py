"""Schemas Pydantic — Ventes POS épicerie."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LigneEncaissement(BaseModel):
    produit_id: int
    quantite: float = Field(..., gt=0)
    # informatif : prix affiché au POS — le backend recalcule depuis DB (ADR-14)
    prix_unitaire_ttc: Optional[int] = None


class EncaissementRequest(BaseModel):
    lignes: list[LigneEncaissement] = Field(..., min_length=1)
    mode_paiement: str = Field(..., description="ESPECES | CB | VIREMENT")
    montant_especes: int = Field(default=0, ge=0)
    montant_cb: int = Field(default=0, ge=0)
    montant_virement: int = Field(default=0, ge=0)
    remise_centimes: int = Field(default=0, ge=0)
    remise_motif: Optional[str] = None
    client_nom: Optional[str] = None
    check_stock: bool = True
    """S1.T3 (F870 / EPI-CHECKSTK-01) : default True pour eviter IntegrityError 500
    sur stock insuffisant. Le service verifie en phase 5 et raise 409 STOCK_INSUFFISANT
    propre. Override `False` reserve aux admins (force-validate + backfill manuel)."""


class EncaissementResponse(BaseModel):
    id: int
    numero_ticket: str
    statut: str
    total_ht_brut: int
    total_tva_brut: int
    total_ttc_brut: int
    remise_centimes: int
    remise_motif: Optional[str]
    total_ttc_remise: int
    total_ht_remise: int
    total_tva_remise: int
    monnaie_rendue: int
    created_at: datetime


class VenteLigneRead(BaseModel):
    id: int
    produit_id: int
    quantite: float
    prix_unitaire_ht: int
    taux_tva: int
    montant_ht: int
    montant_tva: int
    montant_ttc: int
    remise_pct: float

    model_config = ConfigDict(from_attributes=True)


class EpicerieVenteRead(BaseModel):
    id: int
    numero_ticket: str
    date_vente: datetime
    statut: str
    mode_paiement: Optional[str]
    total_ht: int
    total_tva: int
    total_ttc: int
    remise_pct: float
    remise_montant: int
    montant_especes: int
    montant_cb: int
    montant_rendu: int
    client_nom: Optional[str]
    client_email: Optional[str]
    vendeur_id: Optional[int]
    notes: Optional[str]
    invoice_id: Optional[int]
    lignes: list[VenteLigneRead] = []

    model_config = ConfigDict(from_attributes=True)


class EpicerieVenteListItem(BaseModel):
    """Schéma allégé pour la liste historique (sans lignes détaillées)."""

    id: int
    numero_ticket: str
    date_vente: datetime
    statut: str
    mode_paiement: Optional[str]
    total_ht: int
    total_tva: int
    total_ttc: int
    remise_pct: float
    remise_montant: int
    montant_especes: int
    montant_cb: int
    montant_rendu: int
    client_nom: Optional[str]
    vendeur_id: Optional[int]
    nb_articles: int

    model_config = ConfigDict(from_attributes=True)


class EpicerieVenteListResponse(BaseModel):
    items: list[EpicerieVenteListItem]
    total: int
    limit: int
    offset: int
    counts: dict[str, int]
