"""Package schemas Épicerie."""
from app.schemas.epicerie.produit import (
    EpicerieProduitCreate,
    EpicerieProduitUpdate,
    EpicerieProduitRead,
)
from app.schemas.epicerie.stock import (
    EpicerieStockRead,
    EpicerieStockListResponse,
    EpicerieStockSummary,
    SeuilUpdate,
    AjustementCreate,
    ComptageRequest,
    ComptageResponse,
    StockMovementRead,
    StockMovementsListResponse,
)
from app.schemas.epicerie.vente import (
    EncaissementRequest,
    EncaissementResponse,
    EpicerieVenteRead,
    EpicerieVenteListResponse,
)
from app.schemas.epicerie.supply_order import (
    SupplyOrderCreate,
    SupplyOrderUpdate,
    SupplyOrderRead,
    SupplyOrderListResponse,
    ReceiveOrderRequest,
    SupplyOrderLineRead,
)
from app.schemas.epicerie.transfert import (
    InternalTransferCreate,
    InternalTransferRead,
    InternalTransferListResponse,
)
from app.schemas.epicerie.finance import (
    FinanceVendorRead,
    FinanceInvoiceRead,
    FournisseurStats,
    FournisseurRead,
)
from app.schemas.epicerie.dashboard import EpicerieDashboard

__all__ = [
    "EpicerieProduitCreate",
    "EpicerieProduitUpdate",
    "EpicerieProduitRead",
    "EpicerieStockRead",
    "EpicerieStockListResponse",
    "EpicerieStockSummary",
    "SeuilUpdate",
    "AjustementCreate",
    "ComptageRequest",
    "ComptageResponse",
    "StockMovementRead",
    "StockMovementsListResponse",
    "EncaissementRequest",
    "EncaissementResponse",
    "EpicerieVenteRead",
    "EpicerieVenteListResponse",
    "SupplyOrderCreate",
    "SupplyOrderUpdate",
    "SupplyOrderRead",
    "SupplyOrderListResponse",
    "ReceiveOrderRequest",
    "SupplyOrderLineRead",
    "InternalTransferCreate",
    "InternalTransferRead",
    "InternalTransferListResponse",
    "FinanceVendorRead",
    "FinanceInvoiceRead",
    "FournisseurStats",
    "FournisseurRead",
    "EpicerieDashboard",
]
