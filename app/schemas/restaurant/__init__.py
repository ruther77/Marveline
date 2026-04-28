"""Package schemas restaurant — DTOs Pydantic domaine restaurant (tenant_id=3)."""
from app.schemas.restaurant.categorie_ingredient import (
    CategorieIngredientCreate,
    CategorieIngredientUpdate,
    CategorieIngredientResponse,
)
from app.schemas.restaurant.ingredient import (
    IngredientCreate,
    IngredientUpdate,
    IngredientResponse,
    IngredientListResponse,
)
from app.schemas.restaurant.mouvement_stock import (
    MouvementStockCreate,
    MouvementStockResponse,
    MouvementStockListResponse,
)
from app.schemas.restaurant.type_preparation import (
    TypePreparationCreate,
    TypePreparationResponse,
    IngredientRequisResponse,
    StockRequisResponse,
)
from app.schemas.restaurant.instance_preparation import (
    InstancePreparationCreate,
    AjustPortionsRequest,
    InstancePreparationResponse,
    ProteineDisponibleResponse,
    MarmiteDetailResponse,
    MarmitesDashboardResponse,
)
from app.schemas.restaurant.variante_plat import (
    VariantePlatCreate,
    VariantePlatUpdate,
    VariantePlatResponse,
)
from app.schemas.restaurant.side import (
    SideCreate,
    SideResponse,
)
from app.schemas.restaurant.table import (
    CommandeActiveResponse,
    TableResponse,
    TableListResponse,
)
from app.schemas.restaurant.ligne_commande import (
    LigneCommandeCreate,
    SuggestionFormule,
    LigneCommandeResponse,
    LigneCommandeCreateResponse,
    TicketCuisineItem,
    TicketCuisineResponse,
    StatutLigneUpdate,
    MarquerPretRequest,
    LigneHistoriqueResponse,
)
from app.schemas.restaurant.commande import (
    CommandeCreate,
    FractionPaiement,
    PaiementRequest,
    CommandeResponse,
    CommandeListResponse,
    CommandeDetail,
    CommandeDetailHistorique,
)
from app.schemas.restaurant.dashboard import (
    DashboardStatsResponse,
    InstanceVideResponse,
    IngredientEpuiseResponse,
    RupturesResponse,
)

__all__ = [
    # CategorieIngredient
    "CategorieIngredientCreate",
    "CategorieIngredientResponse",
    # Ingredient
    "IngredientCreate",
    "IngredientUpdate",
    "IngredientResponse",
    "IngredientListResponse",
    # MouvementStock
    "MouvementStockCreate",
    "MouvementStockResponse",
    "MouvementStockListResponse",
    # TypePreparation
    "TypePreparationCreate",
    "TypePreparationResponse",
    "IngredientRequisResponse",
    "StockRequisResponse",
    # InstancePreparation
    "InstancePreparationCreate",
    "AjustPortionsRequest",
    "InstancePreparationResponse",
    "ProteineDisponibleResponse",
    "MarmiteDetailResponse",
    "MarmitesDashboardResponse",
    # VariantePlat
    "VariantePlatCreate",
    "VariantePlatUpdate",
    "VariantePlatResponse",
    # Side
    "SideCreate",
    "SideResponse",
    # Table
    "CommandeActiveResponse",
    "TableResponse",
    "TableListResponse",
    # LigneCommande
    "LigneCommandeCreate",
    "SuggestionFormule",
    "LigneCommandeResponse",
    "LigneCommandeCreateResponse",
    "TicketCuisineItem",
    "TicketCuisineResponse",
    "StatutLigneUpdate",
    "MarquerPretRequest",
    "LigneHistoriqueResponse",
    # Commande
    "CommandeCreate",
    "FractionPaiement",
    "PaiementRequest",
    "CommandeResponse",
    "CommandeListResponse",
    "CommandeDetail",
    "CommandeDetailHistorique",
    # Dashboard
    "DashboardStatsResponse",
    "InstanceVideResponse",
    "IngredientEpuiseResponse",
    "RupturesResponse",
]
