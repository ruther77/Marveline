"""Repositories pour accès aux données avec isolation multi-tenant."""
from app.repositories.base import BaseRepository
from app.repositories.customer import CustomerRepository
from app.repositories.product import ProductRepository
from app.repositories.reservation import (
    ReservationRepository,
    ReservationLineRepository,
)
from app.repositories.invoice import InvoiceRepository
from app.repositories.api_key import ApiKeyRepository
from app.repositories.feature_flag import FeatureFlagRepository
from app.repositories.inventory_movement import MovementRepository, MovementItemRepository
from app.repositories.bundle import BundleRepository, BundleItemRepository
from app.repositories.category import CategoryRepository
from app.repositories.delivery_zone import DeliveryZoneRepository
from app.repositories.product_variant import ProductVariantRepository
from app.repositories.stock_item import StockItemRepository
from app.repositories.devis import DevisRepository
from app.repositories.damage_type import DamageTypeRepository
from app.repositories.payment import PaymentRepository
from app.repositories.deposit import DepositRepository
from app.repositories.vente import VenteRepository
from app.repositories.invoice_credit_note import CreditNoteRepository
from app.repositories.supplier import SupplierRepository
from app.repositories.product_maintenance import ProductMaintenanceRepository
from app.repositories.notification import NotificationRepository
from app.repositories.evenements import EvenementRepository, EventIncidentRepository, IncidentActionRepository
from app.repositories.tenant_settings import TenantSettingsRepository
from app.repositories.collection import CollectionRepository
from app.repositories.inventory_movement import AsyncMovementRepository, AsyncMovementItemRepository
from app.repositories.api_key import AsyncApiKeyRepository
from app.repositories.bundle import AsyncBundleRepository, AsyncBundleItemRepository
from app.repositories.category import AsyncCategoryRepository
from app.repositories.delivery_zone import AsyncDeliveryZoneRepository
from app.repositories.product_variant import AsyncProductVariantRepository
from app.repositories.stock_item import AsyncStockItemRepository
from app.repositories.devis import AsyncDevisRepository
from app.repositories.damage_type import AsyncDamageTypeRepository
from app.repositories.payment import AsyncPaymentRepository
from app.repositories.deposit import AsyncDepositRepository
from app.repositories.vente import AsyncVenteRepository
from app.repositories.invoice_credit_note import AsyncCreditNoteRepository
from app.repositories.supplier import AsyncSupplierRepository
from app.repositories.supplier_order import AsyncSupplierOrderRepository
from app.repositories.product_maintenance import AsyncProductMaintenanceRepository
from app.repositories.notification import AsyncNotificationRepository
from app.repositories.evenements import AsyncEvenementRepository, AsyncEventIncidentRepository, AsyncIncidentActionRepository
from app.repositories.tenant_settings import AsyncTenantSettingsRepository
from app.repositories.feature_flag import AsyncFeatureFlagRepository
from app.repositories.formula import AsyncFormulaRepository
from app.repositories.password_reset_token import PasswordResetTokenRepository
# IAM v2
from app.repositories.account import AsyncAccountRepository
from app.repositories.tenant_membership import AsyncTenantMembershipRepository
from app.repositories.account_session import AsyncAccountSessionRepository
# Loyalty
from app.repositories.loyalty import (
    AsyncFlashOfferRepository,
    AsyncLoyaltyMemberRepository,
    AsyncLoyaltyNotifLogRepository,
    AsyncLoyaltyProgramRepository,
    AsyncPointsLedgerRepository,
    AsyncReferralLinkRepository,
    AsyncRevenueLedgerRepository,
    AsyncRewardRedemptionRepository,
    AsyncRewardsCatalogRepository,
    AsyncTierHistoryRepository,
    AsyncWalletPassRepository,
)

__all__ = [
    "BaseRepository",
    "CustomerRepository",
    "ProductRepository",
    "ReservationRepository",
    "ReservationLineRepository",
    "InvoiceRepository",
    "ApiKeyRepository",
    "FeatureFlagRepository",
    "MovementRepository",
    "MovementItemRepository",
    "BundleRepository",
    "BundleItemRepository",
    "CategoryRepository",
    "DeliveryZoneRepository",
    "ProductVariantRepository",
    "StockItemRepository",
    "DevisRepository",
    "DamageTypeRepository",
    "PaymentRepository",
    "DepositRepository",
    "VenteRepository",
    "CreditNoteRepository",
    "SupplierRepository",
    "ProductMaintenanceRepository",
    "NotificationRepository",
    "EvenementRepository",
    "EventIncidentRepository",
    "IncidentActionRepository",
    "TenantSettingsRepository",
    "CollectionRepository",
    "PasswordResetTokenRepository",
    # Async repositories
    "AsyncMovementRepository",
    "AsyncMovementItemRepository",
    "AsyncApiKeyRepository",
    "AsyncBundleRepository",
    "AsyncBundleItemRepository",
    "AsyncCategoryRepository",
    "AsyncDeliveryZoneRepository",
    "AsyncProductVariantRepository",
    "AsyncStockItemRepository",
    "AsyncDevisRepository",
    "AsyncDamageTypeRepository",
    "AsyncPaymentRepository",
    "AsyncDepositRepository",
    "AsyncVenteRepository",
    "AsyncCreditNoteRepository",
    "AsyncSupplierRepository",
    "AsyncSupplierOrderRepository",
    "AsyncProductMaintenanceRepository",
    "AsyncNotificationRepository",
    "AsyncEvenementRepository",
    "AsyncEventIncidentRepository",
    "AsyncIncidentActionRepository",
    "AsyncTenantSettingsRepository",
    "AsyncFeatureFlagRepository",
    "AsyncFormulaRepository",
    # IAM v2
    "AsyncAccountRepository",
    "AsyncTenantMembershipRepository",
    "AsyncAccountSessionRepository",
    # Loyalty
    "AsyncLoyaltyProgramRepository",
    "AsyncLoyaltyMemberRepository",
    "AsyncPointsLedgerRepository",
    "AsyncRevenueLedgerRepository",
    "AsyncRewardsCatalogRepository",
    "AsyncRewardRedemptionRepository",
    "AsyncReferralLinkRepository",
    "AsyncFlashOfferRepository",
    "AsyncWalletPassRepository",
    "AsyncTierHistoryRepository",
    "AsyncLoyaltyNotifLogRepository",
]
