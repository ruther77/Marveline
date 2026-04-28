"""Schemas Pydantic — IngredientEpicerieMapping.

Mapping durable entre un ingrédient restaurant et N produits épicerie avec
ordre de préférence + facteur de conversion. Utilisé par le résolveur pour
suggérer les produits sources lors d'un transfert de réapprovisionnement.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field

from app.schemas.base import BaseSchema


# ── CRUD ─────────────────────────────────────────────────────────────────────


class MappingCreate(BaseSchema):
    """POST /restaurant/ingredients/{id}/produits-epicerie."""
    produit_id: int = Field(..., gt=0)
    ordre: int = Field(default=0, ge=0, le=100)
    facteur_conv: Decimal = Field(default=Decimal("1"), gt=0, decimal_places=4)
    notes: Optional[str] = Field(default=None, max_length=500)


class MappingUpdate(BaseSchema):
    """PATCH /restaurant/ingredients/{id}/produits-epicerie/{produit_id}."""
    ordre: Optional[int] = Field(default=None, ge=0, le=100)
    facteur_conv: Optional[Decimal] = Field(default=None, gt=0, decimal_places=4)
    notes: Optional[str] = Field(default=None, max_length=500)


class MappingReorderItem(BaseSchema):
    produit_id: int = Field(..., gt=0)
    ordre: int = Field(..., ge=0, le=100)


class MappingReorderRequest(BaseSchema):
    """POST /restaurant/ingredients/{id}/produits-epicerie/reorder (batch)."""
    items: list[MappingReorderItem] = Field(..., min_length=1, max_length=50)


class MappingRead(BaseSchema):
    id: int
    tenant_id: int
    ingredient_id: int
    produit_id: int
    ordre: int
    facteur_conv: Decimal
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MappingWithProduit(MappingRead):
    """Enrichi avec infos produit pour affichage UI (designation, stock)."""
    produit_designation: str
    produit_unite_vente: str
    produit_stock_disponible: Decimal


class MappingListResponse(BaseSchema):
    items: list[MappingWithProduit]


# ── Résolveur (preview + résultat) ───────────────────────────────────────────


class ResolveRequest(BaseSchema):
    """POST /restaurant/ingredients/{id}/resolve-preview."""
    qte_besoin: Decimal = Field(..., gt=0, decimal_places=3)


class ResolveItem(BaseSchema):
    """Prélèvement suggéré sur un produit épicerie."""
    produit_id: int
    produit_designation: str
    produit_unite_vente: str
    ordre: int
    facteur_conv: Decimal
    stock_disponible: Decimal = Field(
        ..., description="Stock produit en unité vente au moment de la résolution",
    )
    qte_prelevee_unites_vente: Decimal = Field(
        ...,
        description=(
            "Quantité à prélever sur ce produit, exprimée en unité de vente "
            "(ex : 2 bidons de 5L pour couvrir 10L d'ingrédient)"
        ),
    )
    qte_couverte_besoin: Decimal = Field(
        ...,
        description="Quantité couverte en unité de stock ingrédient = qte_prelevee × facteur_conv",
    )


class ResolveResponse(BaseSchema):
    """Résultat d'une résolution cascade mixte."""
    ingredient_id: int
    qte_besoin: Decimal
    qte_couverte_totale: Decimal
    deficit: Decimal = Field(
        ..., description="Besoin non couvert (0 si couverture complète)",
    )
    couverture_complete: bool
    items: list[ResolveItem]


# ── Résolution pour TransferRequest (cas multi-lignes) ───────────────────────


class RequestLineResolution(BaseSchema):
    """Résolution d'une ligne de TransferRequest (un ingrédient)."""
    request_line_id: int
    ingredient_restaurant_id: int
    ingredient_nom: str
    qte_besoin: Decimal
    items: list[ResolveItem]
    couverture_complete: bool
    deficit: Decimal


class PreviewResolutionResponse(BaseSchema):
    """Plan de résolution pour toute une TransferRequest (dry-run)."""
    request_id: int
    lines: list[RequestLineResolution]
    unresolvable_line_ids: list[int] = Field(
        default_factory=list,
        description="IDs de lignes sans ingredient_restaurant_id (texte libre, non résolvables)",
    )
    any_deficit: bool = Field(
        ..., description="True si au moins une ligne a un déficit",
    )


class ApproveOverrideLine(BaseSchema):
    """Override manuel d'une ligne de transfert avant approbation."""
    produit_id: int = Field(..., gt=0)
    ingredient_id: Optional[int] = Field(default=None, gt=0)
    quantite: Decimal = Field(..., gt=0, decimal_places=3)
    unite: str = Field(default="U", min_length=1, max_length=10)
    prix_unitaire: int = Field(..., ge=0)
    tva_pct: int = Field(default=2000, ge=0)


class ApproveWithTransferRequest(BaseSchema):
    """POST /epicerie/transfer-requests/{id}/approve-with-transfer."""
    overrides: Optional[list[ApproveOverrideLine]] = Field(
        default=None,
        description=(
            "Si fourni : utilise ces lignes au lieu de la résolution auto. "
            "Sinon : le résolveur cascade génère automatiquement les lignes."
        ),
    )
    reference: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=2000)


class ApproveWithTransferResponse(BaseSchema):
    """Résultat d'approbation avec création InternalTransfer."""
    transfer_id: int
    warnings: list[str] = Field(
        default_factory=list,
        description="Déficits par ingrédient, lignes non résolvables, etc.",
    )
