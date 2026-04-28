"""Schemas Pydantic — ETL Imports (queue factures fournisseur ADR-25).

Couvre :
  - EtlImportRead : vue liste (queue preview + historique)
  - EtlImportDetail : vue détaillée avec lignes
  - EtlImportUpdateRequest : modification preview par opérateur
  - LigneFactureUpdate : modification d'une ligne par l'opérateur
  - FactureUploadResponse : réponse après upload
  - CategoryGroup : catégories groupées pour dropdown
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EtlImportRead(BaseModel):
    """Vue liste d'un import ETL (queue et historique)."""

    id: int
    fournisseur_id: Optional[int] = None
    fichier_source: Optional[str] = None
    fichier_path: Optional[str] = None
    statut: str
    nb_lignes_total: Optional[int] = None
    nb_lignes_ok: int = 0
    nb_lignes_conflit: int = 0
    nb_lignes_erreur: int = 0
    erreur_detail: Optional[str] = None

    # Métadonnées facture (ADR-25)
    numero_facture: Optional[str] = None
    date_facture: Optional[date] = None
    montant_ht_total: Optional[int] = None
    montant_tva_total: Optional[int] = None
    montant_ttc_total: Optional[int] = None
    vendor_code: Optional[str] = None
    quality_score: Optional[int] = None
    ecart_reconciliation: Optional[Decimal] = None

    # Routing multi-tenant (TAIYAT INCONTOURNABLE/NOUTAM)
    client_name: Optional[str] = None
    target_tenant_id: Optional[int] = None

    # Progression + Revert
    validation_step: Optional[str] = None
    reverted_at: Optional[datetime] = None
    reverted_by_id: Optional[int] = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EtlImportListResponse(BaseModel):
    """Réponse paginée de la liste des imports."""

    items: list[EtlImportRead]
    total: int


class LigneFactureRead(BaseModel):
    """Ligne produit parsée (preview facture)."""

    idx: int = 0
    designation: str
    unite_base: str
    source_fournisseur: str
    ean: Optional[str] = None
    marque: Optional[str] = None
    conditionnement: Optional[str] = None
    categorie_code: Optional[str] = None
    quantite: Optional[float] = None
    prix_unitaire_cts: Optional[int] = None
    montant_ht_cts: Optional[int] = None
    montant_ttc_cts: Optional[int] = None
    taux_tva_centieme: Optional[int] = None
    designation_raw: Optional[str] = None
    article_fournisseur: Optional[str] = None
    degre_alcool: Optional[float] = None
    contenant: Optional[str] = None
    volume_unitaire_ml: Optional[int] = None
    colisage: Optional[int] = None

    # Coordonnées PDF et confiance (Phase 2)
    page_number: Optional[int] = None
    y_position: Optional[float] = None
    confidence_score: Optional[int] = None

    # Produits similaires et prix catalogue (Phase 2+3)
    similar_products: Optional[list] = None
    prix_catalogue_actuel_cts: Optional[int] = None

    # Auto-fill traçable (S1-S5) — métadata par champ auto-appliqué
    auto_applied_fields: Optional[dict] = None


class LigneFactureUpdate(BaseModel):
    """Modification d'une ou plusieurs lignes en PREVIEW."""

    idx: int = Field(..., ge=0, description="Index de la ligne dans le tableau")
    designation: Optional[str] = None
    ean: Optional[str] = None
    marque: Optional[str] = None
    conditionnement: Optional[str] = None
    categorie_code: Optional[str] = None
    quantite: Optional[float] = Field(None, ge=0)
    prix_unitaire_cts: Optional[int] = Field(None, ge=0)
    taux_tva_centieme: Optional[int] = Field(None, ge=0)
    # S5 — révocation d'auto-fill : le frontend peut renvoyer le dict tel
    # qu'il le veut persisté (ex: sans la clé du champ révoqué).
    auto_applied_fields: Optional[dict] = None


class LignesBatchUpdateRequest(BaseModel):
    """Batch update de lignes parsées."""

    updates: list[LigneFactureUpdate] = Field(..., min_length=1)


class LigneAddRequest(BaseModel):
    """Ajout manuel d'une ligne produit."""

    designation: str = Field(..., min_length=1, max_length=200)
    unite_base: str = Field(default="PIECE")
    source_fournisseur: str = Field(default="MANUAL")
    ean: Optional[str] = None
    marque: Optional[str] = None
    conditionnement: Optional[str] = None
    categorie_code: Optional[str] = None
    quantite: Optional[float] = Field(None, ge=0)
    prix_unitaire_cts: Optional[int] = Field(None, ge=0)
    taux_tva_centieme: Optional[int] = Field(None, ge=0)


class EtlImportDetail(EtlImportRead):
    """Vue détaillée d'un import avec les lignes parsées."""

    lignes: list[LigneFactureRead] = Field(default_factory=list)
    montant_ht_calcule: Optional[int] = None
    montant_ttc_calcule: Optional[int] = None


class ValidatedLignesEditResponse(EtlImportDetail):
    """Réponse PATCH validated-lignes — EtlImportDetail + avertissements downstream.

    `warnings` contient les alertes non bloquantes (ex: STOCK_NEGATIVE quand
    le stock est passé sous zéro suite au delta). Le client peut les afficher
    en toast pour informer l'opérateur.
    """

    warnings: list[dict] = Field(default_factory=list)


class ValidatedLigneEdit(BaseModel):
    """Édition d'une ligne d'un import VALIDATED.

    Champs financiers (P1) : quantite, prix_unitaire_cts, taux_tva_centieme.
    Champs non-financiers (P2) : marque, categorie_code.
    EAN et designation sont interdits post-validation (reparenting produit ingérable).

    Gate facture PAYEE : s'applique uniquement si au moins un champ financier
    est présent dans l'update (les modifs non-financières restent autorisées
    même sur une facture payée).
    """

    idx: int = Field(..., ge=0, description="Index ligne dans lignes_data")
    # Financier
    quantite: Optional[float] = Field(None, ge=0)
    prix_unitaire_cts: Optional[int] = Field(None, ge=0)
    taux_tva_centieme: Optional[int] = Field(None, ge=0)
    # Non-financier (P2)
    marque: Optional[str] = Field(None, max_length=100)
    categorie_code: Optional[str] = Field(None, max_length=50)


class ValidatedLignesBatchEditRequest(BaseModel):
    """Batch édition de lignes sur un import VALIDATED."""

    updates: list[ValidatedLigneEdit] = Field(..., min_length=1)


class ValidatedInvoiceMetaEditRequest(BaseModel):
    """Édition des métadonnées facture d'un import VALIDATED (P2).

    Répercute les champs sur l'EtlImport ET sur FinanceInvoice liée
    (reference / date_facture). Non-financier → pas de gate PAYEE.
    """

    numero_facture: Optional[str] = Field(None, max_length=100)
    date_facture: Optional[date] = None
    vendor_code: Optional[str] = Field(None, max_length=50)


class EtlImportUpdateRequest(BaseModel):
    """Modification d'un import en PREVIEW par l'opérateur."""

    numero_facture: Optional[str] = None
    date_facture: Optional[date] = None
    montant_ht_total: Optional[int] = Field(None, ge=0)
    montant_tva_total: Optional[int] = Field(None, ge=0)
    montant_ttc_total: Optional[int] = Field(None, ge=0)


class FactureUploadResponse(BaseModel):
    """Réponse après upload d'un fichier fournisseur."""

    etl_import_id: int
    statut: str
    nb_lignes: int
    numero_facture: Optional[str] = None
    vendor_code: Optional[str] = None
    quality_score: Optional[int] = None


class CategoryItem(BaseModel):
    """Une catégorie alimentaire."""

    code: str
    label: str


class CategoryGroup(BaseModel):
    """Groupe de catégories pour dropdown."""

    group: str
    label: str
    items: list[CategoryItem]


class CategoriesResponse(BaseModel):
    """Liste groupée des catégories alimentaires."""

    groups: list[CategoryGroup]
    total: int


class RevertImportResponse(BaseModel):
    """Résultat d'un revert d'import ETL."""

    mouvements_annules: int
    invoice_annulee: bool
    prix_restaures: int


class DashboardQualityTrend(BaseModel):
    """Point de tendance qualité."""

    id: int
    import_date: Optional[date] = Field(None, alias="date")
    quality_score: Optional[int] = None
    vendor_code: Optional[str] = None
    nb_lignes_total: Optional[int] = None

    model_config = ConfigDict(populate_by_name=True)


class DashboardVendorStats(BaseModel):
    """Stats par fournisseur."""

    vendor_code: str
    total_imports: int
    avg_quality: Optional[float] = None
    recognition_rate: Optional[float] = None


class DashboardResponse(BaseModel):
    """Dashboard analytique ETL."""

    total_imports: int
    by_status: dict[str, int]
    avg_quality_global: Optional[float] = None
    quality_trend: list[DashboardQualityTrend]
    vendor_stats: list[DashboardVendorStats]
    pending_conflicts: int
    avg_correction_time_sec: Optional[float] = None
