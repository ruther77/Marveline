"""Schemas Pydantic — Commandes fournisseurs épicerie."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class SupplyOrderLineCreate(BaseModel):
    produit_id: Optional[int] = None
    designation: str = Field(..., min_length=1, max_length=255)
    quantity: float = Field(..., gt=0)
    prix_unitaire: int = Field(..., ge=0)
    taux_tva: int = Field(default=2000, ge=0)
    notes: Optional[str] = None


class SupplyOrderCreate(BaseModel):
    vendor_id: int
    reference: Optional[str] = Field(None, max_length=100)
    date_commande: date
    date_livraison_prevue: Optional[date] = None
    notes: Optional[str] = None
    lignes: list[SupplyOrderLineCreate] = Field(..., min_length=1)


class SupplyOrderUpdate(BaseModel):
    reference: Optional[str] = Field(None, max_length=100)
    date_livraison_prevue: Optional[date] = None
    notes: Optional[str] = None


class ReceiveLineItem(BaseModel):
    line_id: int
    received_quantity: float = Field(..., ge=0)
    notes: Optional[str] = None


class ReceiveOrderRequest(BaseModel):
    date_livraison_reelle: date
    lignes: list[ReceiveLineItem] = Field(..., min_length=1)
    notes: Optional[str] = None


class SupplyOrderLineRead(BaseModel):
    id: int
    order_id: int
    produit_id: Optional[int]
    designation: str
    quantity: float
    prix_unitaire: int
    taux_tva: int
    received_quantity: Optional[float]
    notes: Optional[str]
    total_ligne_cts: Optional[int] = None  # F6 : quantity * prix_unitaire

    model_config = {"from_attributes": True}


class SupplyOrderRead(BaseModel):
    id: int
    vendor_id: int
    vendor_nom: Optional[str] = None  # F6 : nom du fournisseur
    reference: Optional[str]
    date_commande: date
    date_livraison_prevue: Optional[date]
    date_livraison_reelle: Optional[date]
    statut: str
    montant_ht: int
    montant_tva: int
    montant_ttc: int
    total_cts: Optional[int] = None  # F6 : alias montant_ttc pour l'UI
    notes: Optional[str]
    invoice_id: Optional[int]
    lignes: list[SupplyOrderLineRead] = []

    model_config = {"from_attributes": True}


class SupplyOrderListResponse(BaseModel):
    items: list[SupplyOrderRead]
    total: int
    page: int
    per_page: int
