"""Modèles SQLAlchemy CaroCorp - Import centralisé pour Alembic autogenerate."""
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin
# IAM v2
from app.models.account import Account
from app.models.account_oauth_identity import AccountOAuthIdentity
from app.models.trusted_device import TrustedDevice
from app.models.tenant_membership import TenantMembership
from app.models.account_session import AccountSession
from app.models.customer import Customer
from app.models.product import Product
from app.models.reservation import (
    Reservation,
    ReservationLine,
    ReservationRisk,
    ReservationPreCheckItem,
    ReservationExtension,
    ReservationReturnInspectionItem,
    ReservationDisputeLog,
)
from app.models.invoice import Invoice
from app.models.audit_log import AuditLog
from app.models.mfa import MFADevice
from app.models.category import Category
from app.models.bundle import ProductBundle, BundleItem
from app.models.api_key import ApiKey
from app.models.feature_flag import FeatureFlag
from app.models.inventory_movement import InventoryMovement, MovementItem
from app.models.delivery_zone import DeliveryZone
from app.models.product_variant import ProductVariant
from app.models.invoice_charge import InvoiceCharge
from app.models.damage_type import DamageType
from app.models.payment import Payment
from app.models.deposit import Deposit
from app.models.stock_item import StockItem
from app.models.movement_item_unit import MovementItemUnit
from app.models.relance import Relance
from app.models.devis import Devis, DevisLine, DevisLineHistory, DevisAttachment, DevisModule, DevisPhase, DevisVersion, DevisNegotiation, DevisChangeRequest, DevisCoverageItem
from app.models.vente import Vente, VenteLine, VentePayment
from app.models.invoice_credit_note import InvoiceCreditNote
from app.models.evenements import Evenement, EventIncident, IncidentAction
from app.models.supplier import Supplier
from app.models.stock_management import StockInventaireSession, StockAdjustment
from app.models.pricing import PricingRule, PricingTier
from app.models.product_maintenance import ProductMaintenance
from app.models.product_image import ProductImage
from app.models.notification import Notification
from app.models.tenant import Tenant
from app.models.tenant_settings import TenantSettings
from app.models.tenant_brand import TenantBrand
from app.models.product_collection import ProductCollection, product_collection_items
from app.models.formula import Formula, FormulaItem
from app.models.supplier_order import SupplierOrder, SupplierOrderLine, SupplierOrderReceipt, SupplierOrderReceiptLine
from app.models.movement_damage import InventoryMovementDamage
from app.models.container import Container, ContainerAssignment, ContainerItem, ContainerContent
from app.models.auth_role import AuthRole
from app.models.auth_scope import AuthScope
from app.models.auth_role_scope import AuthRoleScope
from app.models.user_role import UserRole
from app.models.password_reset_token import PasswordResetToken
# Loyalty
from app.models.loyalty import (
    FlashOffer,
    LoyaltyMember,
    LoyaltyNotificationLog,
    LoyaltyProgram,
    PointsLedger,
    ReferralLink,
    RevenueLedger,
    RewardRedemption,
    RewardsCatalog,
    TierHistory,
    WalletPass,
)

# ── V2 : Domaines alimentaires ──────────────────────────────────────────────
# Catalogue partagé (sans tenant_id — ADR-01, ADR-02)
from app.models.catalogue.categories_produit import CategorieProduit
from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.models.catalogue.etl_import import EtlImport
from app.models.catalogue.etl_conflict import EtlConflict
# Approvisionnement partagé (sans tenant_id — ADR-02)
from app.models.approvisionnement.fournisseur_alim import FournisseurAlim
# V2 — Restaurant (tenant_id=3)
from app.models.restaurant import (
    TableRestaurant,
    CategorieIngredient,
    IngredientRestaurant,
    MouvementStockRestaurant,
    TypePreparation,
    RecetteTypePreparation,
    InstancePreparation,
    VariantePlat,
    SideRestaurant,
    CommandeRestaurant,
    LigneCommandeRestaurant,
    AlerteStockRestaurant,
)
# V2 — Finance (référentiel partagé)
from app.models.finance import FinanceEntity, FinanceVendor, FinanceInvoice, FinancePayment
# V2 — Épicerie (tenant_id=2)
from app.models.epicerie import (
    EpicerieProduit,
    EpicerieStock,
    EpicerieStockMovement,
    EpicerieVente,
    EpicerieVenteLigne,
    SupplyOrder,
    SupplyOrderLine,
    InternalTransfer,
    InternalTransferLine,
)

__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",
    "TenantMixin",
    "SoftDeleteMixin",
    # IAM v2 — nouveaux modèles
    "Account",
    "AccountOAuthIdentity",
    "TenantMembership",
    "AccountSession",
    # RBAC models (CaroCorp §6.5)
    "AuthRole",
    "AuthScope",
    "AuthRoleScope",
    # Auth models
    "MFADevice",
    "ApiKey",
    # Feature Flags
    "FeatureFlag",
    # Business models
    "Customer",
    "Product",
    "Category",
    "ProductBundle",
    "BundleItem",
    "Reservation",
    "ReservationLine",
    "ReservationRisk",
    "ReservationPreCheckItem",
    "ReservationExtension",
    "ReservationReturnInspectionItem",
    "ReservationDisputeLog",
    "Invoice",
    "InvoiceCharge",
    "DamageType",
    "Payment",
    "Deposit",
    "Relance",
    "Devis",
    "DevisLine",
    "DevisLineHistory",
    "DevisAttachment",
    "DevisModule",
    "DevisPhase",
    "DevisVersion",
    "DevisNegotiation",
    "DevisChangeRequest",
    "DevisCoverageItem",
    "Vente",
    "VenteLine",
    "VentePayment",
    "InvoiceCreditNote",
    "Evenement",
    "EventIncident",
    "IncidentAction",
    "StockItem",
    "InventoryMovement",
    "MovementItem",
    "MovementItemUnit",
    "DeliveryZone",
    "ProductVariant",
    "Supplier",
    "StockInventaireSession",
    "StockAdjustment",
    "PricingRule",
    "PricingTier",
    "ProductMaintenance",
    "ProductImage",
    "Notification",
    "Tenant",
    "TenantSettings",
    "ProductCollection",
    "Formula",
    "FormulaItem",
    "SupplierOrder",
    "SupplierOrderLine",
    "SupplierOrderReceipt",
    "SupplierOrderReceiptLine",
    "InventoryMovementDamage",
    # Containers (logistique + contenu persistant)
    "Container",
    "ContainerAssignment",
    "ContainerItem",
    "ContainerContent",
    # Audit & Security
    "AuditLog",
    # Legacy RBAC (User→role, migration progressive)
    "UserRole",
    # Auth tokens
    "PasswordResetToken",
    # V2 — Catalogue partagé
    "CategorieProduit",
    "CatalogueProduit",
    "EtlImport",
    "EtlConflict",
    # V2 — Approvisionnement partagé
    "FournisseurAlim",
    # V2 — Restaurant (tenant_id=3)
    "TableRestaurant",
    "CategorieIngredient",
    "IngredientRestaurant",
    "MouvementStockRestaurant",
    "TypePreparation",
    "RecetteTypePreparation",
    "InstancePreparation",
    "VariantePlat",
    "SideRestaurant",
    "CommandeRestaurant",
    "LigneCommandeRestaurant",
    "AlerteStockRestaurant",
    # V2 — Finance (référentiel partagé)
    "FinanceEntity",
    "FinanceVendor",
    "FinanceInvoice",
    "FinancePayment",
    # V2 — Épicerie (tenant_id=2)
    "EpicerieProduit",
    "EpicerieStock",
    "EpicerieStockMovement",
    "EpicerieVente",
    "EpicerieVenteLigne",
    "SupplyOrder",
    "SupplyOrderLine",
    "InternalTransfer",
    "InternalTransferLine",
    # Loyalty
    "LoyaltyProgram",
    "LoyaltyMember",
    "PointsLedger",
    "RevenueLedger",
    "TierHistory",
    "WalletPass",
    "RewardsCatalog",
    "RewardRedemption",
    "ReferralLink",
    "FlashOffer",
    "LoyaltyNotificationLog",
]
