"""Schemas Pydantic — Transferts internes epicerie -> restaurant."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Input ──────────────────────────────────────────────────────────────────────


class TransferLineCreate(BaseModel):
    """Ligne de transfert : produit epicerie requis, ingredient restaurant optionnel."""

    produit_id: int
    ingredient_id: Optional[int] = None
    quantite: float = Field(..., gt=0)
    unite: str = Field(default="U", max_length=10)
    prix_unitaire: int = Field(..., ge=0, description="Prix unitaire HT en centimes")
    tva_pct: int = Field(default=2000, ge=0, description="TVA en centiemes de pourcent")


class InternalTransferCreate(BaseModel):
    """Creation d'un transfert interne."""

    dest_tenant_id: int
    reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    lignes: list[TransferLineCreate] = Field(..., min_length=1)


class AnnulationPayload(BaseModel):
    """Payload pour annulation d'un transfert."""

    raison: Optional[str] = None


# ── Output ─────────────────────────────────────────────────────────────────────


class InternalTransferLineRead(BaseModel):
    """Ligne de transfert en lecture."""

    id: int
    transfer_id: int
    produit_id: int
    designation: str
    ingredient_id: Optional[int] = None
    quantite: float
    unite: str
    prix_unitaire: int
    tva_pct: int
    montant_ht: int
    montant_ttc: int
    mouvement_epicerie_id: Optional[int] = None
    mouvement_restaurant_id: Optional[int] = None

    model_config = {"from_attributes": True}


class InternalTransferRead(BaseModel):
    """Transfert interne en lecture avec lignes."""

    id: int
    tenant_id: int
    dest_tenant_id: int
    reference: Optional[str] = None
    status: str
    notes: Optional[str] = None
    montant_ht: int
    montant_ttc: int
    invoice_id: Optional[int] = None
    invoice_numero: Optional[str] = None
    invoice_statut: Optional[str] = None
    created_by: Optional[int] = None
    validated_at: Optional[datetime] = None
    validated_by: Optional[int] = None
    cancelled_at: Optional[datetime] = None
    raison_annulation: Optional[str] = None
    created_at: datetime
    lignes: list[InternalTransferLineRead] = []

    model_config = {"from_attributes": True}


class InternalTransferListResponse(BaseModel):
    """Reponse paginee pour la liste des transferts."""

    items: list[InternalTransferRead]
    total: int
    page: int
    per_page: int
