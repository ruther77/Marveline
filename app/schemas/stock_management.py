"""Schémas Pydantic pour la gestion du stock (inventaire physique + ajustements)."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Inventaire physique
# ---------------------------------------------------------------------------

class StartInventaireRequest(BaseModel):
    """Démarre une session d'inventaire."""
    pass  # Aucun paramètre requis


class CountingEntry(BaseModel):
    """Saisie de comptage pour un produit (ou une variante)."""
    product_id: int
    variant_id: Optional[int] = None
    counted_quantity: int


class UpdateInventaireRequest(BaseModel):
    """Met à jour les comptages d'une session en cours."""
    entries: list[CountingEntry]


class InventaireSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    created_by: int
    variances_json: Any


# ---------------------------------------------------------------------------
# Ajustements manuels
# ---------------------------------------------------------------------------

class StockAdjustmentCreate(BaseModel):
    """Ajustement manuel de stock (produit ou variante)."""
    product_id: int
    variant_id: Optional[int] = None
    delta: int
    reason: str


class StockAdjustmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    product_id: int
    variant_id: Optional[int] = None
    delta: int
    reason: str
    created_at: datetime
    created_by: int


# ---------------------------------------------------------------------------
# Niveaux stock
# ---------------------------------------------------------------------------

class StockLevelItem(BaseModel):
    """Niveau de stock d'un produit."""
    product_id: int
    product_name: str
    stock_quantity: int
    available_quantity: int
    level: str  # critical | low | ok | overstock
    low_stock_threshold: int


class ReorderItem(BaseModel):
    """Produit sous seuil de réassort."""
    product_id: int
    product_name: str
    available_quantity: int
    low_stock_threshold: int
    deficit: int


class ReorderRequest(BaseModel):
    """Crée une commande de réassort."""
    items: list[dict]  # [{product_id, quantity}]
    supplier_id: Optional[int] = None
    notes: Optional[str] = None


class ReorderResponse(BaseModel):
    created: int
    message: str


# ---------------------------------------------------------------------------
# Couverture stock
# ---------------------------------------------------------------------------

class StockCoverageItem(BaseModel):
    """Métriques de couverture et rotation pour un produit."""
    product_id: int
    product_name: str
    sku: str
    available_qty: int
    total_qty: int
    movements_30d: int
    avg_daily_movements: float
    days_of_coverage: Optional[float]  # None = infini (aucun mouvement)
    rotation_rate: float  # % sorties 30j / stock total
    status: str  # critical | low | ok | good


class StockCoverageResponse(BaseModel):
    items: list[StockCoverageItem]
    computed_at: datetime
