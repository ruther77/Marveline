"""Services métier pour logique applicative et transactions."""
from app.services.product import ProductService, AsyncProductService
from app.services.reservation import ReservationService, AsyncReservationService
from app.services.invoice import InvoiceService, AsyncInvoiceService
from app.services.audit import AuditService
from app.core.cache import CacheService, cache_invalidate, cache_service
from app.services.token import TokenService, token_service
from app.services.bruteforce import BruteForceService, brute_force_service
from app.services.session import SessionService, session_service
from app.services.mfa import MFAService, mfa_service
from app.services.api_key import ApiKeyService
from app.services.feature_flag import FeatureFlagService
from app.services.notification import NotificationService, notification_service
from app.services.inventory_movement import MovementService, AsyncMovementService
from app.services.reservation_workflow import ReservationWorkflowService
from app.services.customer import CustomerService, AsyncCustomerService
from app.services.stock_item import StockItemService
from app.services.bundle import BundleService
from app.services.category import CategoryService
from app.services.delivery_zone import DeliveryZoneService
from app.services.product_variant import ProductVariantService
from app.services.damage_type import DamageTypeService
from app.services.payment import PaymentService
from app.services.deposit import DepositService
from app.services.product_maintenance import ProductMaintenanceService
from app.services.devis import DevisService
# IAM v2
from app.services.account import AccountService
from app.services.membership import MembershipService
from app.services.account_session import AccountSessionService
# Loyalty
from app.services.loyalty import LoyaltyService
from app.services.auth_v2 import AuthV2Service, MFARequiredResult as MFARequiredResultV2
from app.services.rbac import (
    get_role_scopes,
    has_scope,
    can_manage_role,
    invalidate_role_cache,
    ROLE_LEVELS,
    ROLE_SCOPES_FALLBACK,
)
from app.services.pricing_engine import PricingEngine

__all__ = [
    "ProductService",
    "AsyncProductService",
    "ReservationService",
    "AsyncReservationService",
    "InvoiceService",
    "AsyncInvoiceService",
    "AuditService",
    "CacheService",
    "cache_invalidate",
    "cache_service",
    "TokenService",
    "token_service",
    "BruteForceService",
    "brute_force_service",
    "SessionService",
    "session_service",
    "MFAService",
    "mfa_service",
    "ApiKeyService",
    "FeatureFlagService",
    "NotificationService",
    "notification_service",
    "MovementService",
    "AsyncMovementService",
    "ReservationWorkflowService",
    "CustomerService",
    "AsyncCustomerService",
    "StockItemService",
    "BundleService",
    "CategoryService",
    "DeliveryZoneService",
    "ProductVariantService",
    "DamageTypeService",
    "PaymentService",
    "DepositService",
    "ProductMaintenanceService",
    "DevisService",
    # IAM v2
    "AccountService",
    "MembershipService",
    "AccountSessionService",
    "AuthV2Service",
    "MFARequiredResultV2",
    # RBAC v3
    "get_role_scopes",
    "has_scope",
    "can_manage_role",
    "invalidate_role_cache",
    "ROLE_LEVELS",
    "ROLE_SCOPES_FALLBACK",
    # Pricing
    "PricingEngine",
]
