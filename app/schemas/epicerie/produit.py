"""Schemas Pydantic — Produits épicerie."""
from typing import Optional

from pydantic import BaseModel, Field, field_validator


_EAN_ALLOWED_LENGTHS = {8, 12, 13, 14}


class EpicerieProduitCreate(BaseModel):
    ean: Optional[str] = None
    designation_clean: str = Field(..., min_length=1, max_length=255)
    nom_court: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    categorie: Optional[str] = Field(None, max_length=100)
    unite_vente: str = Field(default="U", max_length=10)
    prix_unitaire_cts: int = Field(..., ge=0)
    taux_tva: int = Field(default=2000, ge=0)
    vendor_id: Optional[int] = None


class EpicerieProduitUpdate(BaseModel):
    ean: Optional[str] = None
    designation_clean: Optional[str] = Field(None, min_length=1, max_length=255)
    nom_court: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    categorie: Optional[str] = Field(None, max_length=100)
    unite_vente: Optional[str] = Field(None, max_length=10)
    prix_unitaire_cts: Optional[int] = Field(None, ge=0)
    taux_tva: Optional[int] = Field(None, ge=0)
    vendor_id: Optional[int] = None
    actif: Optional[bool] = None


class EpicerieProduitRead(BaseModel):
    id: int
    ean: Optional[str]
    designation_clean: str
    nom_court: Optional[str]
    description: Optional[str]
    categorie: Optional[str]
    unite_vente: str
    unite_base: Optional[str] = None
    colisage: Optional[int] = None
    prix_unitaire_cts: int
    taux_tva: int
    vendor_id: Optional[int]
    image_url: Optional[str] = None
    actif: bool

    model_config = {"from_attributes": True}


class ProduitCatalogueRead(BaseModel):
    """Vue catalogue POS — produit + stock fusionnés (LEFT JOIN, 1 requête)."""
    id: int
    ean: Optional[str]
    designation_clean: str
    nom_court: Optional[str]
    categorie: Optional[str]
    unite_vente: str
    unite_base: Optional[str] = None
    colisage: Optional[int] = None
    prix_unitaire_cts: int
    taux_tva: int
    image_url: Optional[str] = None
    actif: bool
    # Champs stock — défaut 0/ok si produit sans ligne epicerie_stock
    quantite: float = 0.0
    seuil_alerte: float = 0.0
    statut_badge: str = 'ok'


class ProduitCatalogueListResponse(BaseModel):
    items: list[ProduitCatalogueRead]
    total: int
    page: int
    per_page: int


class EpicerieEanAdd(BaseModel):
    """Ajout d'un EAN secondaire à un produit (scan caisse multi-fournisseur)."""
    ean: str = Field(..., min_length=8, max_length=20)
    source_fournisseur: Optional[str] = Field(None, max_length=50)

    @field_validator("ean")
    @classmethod
    def _ean_digits(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit():
            raise ValueError("EAN doit contenir uniquement des chiffres")
        if len(v) not in _EAN_ALLOWED_LENGTHS:
            raise ValueError("EAN doit faire 8, 12, 13 ou 14 chiffres")
        return v


class EpicerieEanRead(BaseModel):
    id: int
    produit_id: int
    ean: str
    source_fournisseur: Optional[str]

    model_config = {"from_attributes": True}


class EpicerieProduitEansResponse(BaseModel):
    """Liste des EANs (principal + secondaires) d'un produit."""
    produit_id: int
    ean_principal: Optional[str]
    eans_secondaires: list[EpicerieEanRead]
