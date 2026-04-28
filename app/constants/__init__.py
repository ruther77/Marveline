"""Constantes globales de l'application CaroCorp.

Ce package centralise TOUTES les constantes de l'application organisées par domaine :

Structure :
    - business.py : Enums métier (ProductCategory, ReservationStatus, etc.)
    - errors.py : Messages d'erreur et statuts HTTP
    - security.py : Headers de sécurité, clés Redis
    - http.py : Méthodes HTTP, endpoints publics
    - limits.py : Limites et configurations

Usage :
    from app.constants import ProductCategory, ErrorMessages, UserRole

    product.category = ProductCategory.ASSIETTE
    raise NotFound(ErrorMessages.PRODUCT_NOT_FOUND)
"""

# Import de tous les Enums et classes depuis les sous-modules
from app.constants.business import (
    CustomerType,
    DeliveryMethod,
    DepositStatus,
    DevisStatus,
    EventStatus,
    RelanceStatus,
    InspectionStatus,
    InvoiceStatus,
    ItemCondition,
    MovementStatus,
    MovementType,
    PaymentMethod,
    ProductCategory,
    ProductColor,
    ProductCondition,
    ReservationStatus,
    StockItemStatus,
    SYSTEM_TENANT_ID,
    TokenType,
    UserRole,
    VenteStatus,
    ADVANCE_DUE_DAYS,
    ADVANCE_PAYMENT_PERCENT,
    BALANCE_DUE_DAYS_BEFORE_EVENT,
    DEPOSIT_RATE,
    HOURLY_RATE_WEEKDAY_CENTS,
    HOURLY_RATE_WEEKEND_CENTS,
    LATE_RETURN_PENALTY_RATE,
    LINEN_MIN_BOOKING_DAYS,
    LOW_STOCK_THRESHOLD,
    SELFIE_BOOTH_DEPOSIT_CENTS,
    TVA_RATE,
)
from app.constants.errors import ErrorMessages, HTTPStatusMessages
from app.constants.http import AuthEndpoints, HealthEndpoints, HTTPMethods, PASSWORD_CHANGE_ALLOWED, PublicEndpoints
from app.constants.limits import Limits
from app.constants.loyalty import (
    FlashOfferStatus,
    FlashOfferTarget,
    LedgerSource,
    LedgerType,
    LoyaltyNotifType,
    LoyaltyProgramType,
    LoyaltyTier,
    NotifChannel,
    RedemptionStatus,
    RevenueLedgerType,
    RewardTier,
    WalletPassStatus,
    WalletPlatform,
    CHURN_RISK_MAX_DAYS,
    CHURN_RISK_MIN_DAYS,
    DISCOUNT_HABITUE_PERCENT,
    DISCOUNT_PRIVILEGIE_PERCENT,
    EXPIRY_WARNING_DAYS_FIRST,
    EXPIRY_WARNING_DAYS_SECOND,
    MAX_REFERRALS_PER_MEMBER,
    POINTS_EXPIRY_MONTHS_BONUS,
    POINTS_EXPIRY_MONTHS_EARNED,
    POINTS_PER_EUR_EPICERIE,
    POINTS_PER_EUR_RESTAURANT,
    REFERRAL_BONUS_POINTS,
    REFERRAL_CODE_DIGITS,
    REVENUE_WINDOW_MONTHS,
    REWARD_TIER_1_COST,
    REWARD_TIER_2_COST,
    REWARD_TIER_3_COST,
    TIER_HABITUE_THRESHOLD_CENTS,
    TIER_PRIVILEGIE_THRESHOLD_CENTS,
    VIP_GRACE_DAYS,
    VIP_MULTIPLIER,
    VIP_THRESHOLD_POINTS_PER_YEAR,
)
from app.constants.metrics import PATH_NORMALIZATION_PATTERNS
from app.constants.security import Argon2Params, BruteForceThresholds, CredentialStuffingThresholds, MFAConfig, PasswordPolicy, RateLimitScope, RedisKeys, SecurityHeaders, SessionConfig

# Exports publics du package
__all__ = [
    # Enums métier
    "ProductCategory",
    "ProductColor",
    "ProductCondition",
    "CustomerType",
    "ReservationStatus",
    "InvoiceStatus",
    "PaymentMethod",
    "UserRole",
    "TokenType",
    "MovementType",
    "MovementStatus",
    "DeliveryMethod",
    "InspectionStatus",
    "ItemCondition",
    "StockItemStatus",
    "SYSTEM_TENANT_ID",
    # Nouveaux enums B1→B4
    "DevisStatus",
    "VenteStatus",
    "EventStatus",
    "RelanceStatus",
    # Règles métier marveline.fr
    "ADVANCE_DUE_DAYS",
    "ADVANCE_PAYMENT_PERCENT",
    "BALANCE_DUE_DAYS_BEFORE_EVENT",
    "DEPOSIT_RATE",
    "HOURLY_RATE_WEEKDAY_CENTS",
    "HOURLY_RATE_WEEKEND_CENTS",
    "LATE_RETURN_PENALTY_RATE",
    "LINEN_MIN_BOOKING_DAYS",
    "LOW_STOCK_THRESHOLD",
    "SELFIE_BOOTH_DEPOSIT_CENTS",
    "TVA_RATE",
    # Messages & Erreurs
    "ErrorMessages",
    "HTTPStatusMessages",
    # Sécurité
    "Argon2Params",
    "BruteForceThresholds",
    "CredentialStuffingThresholds",
    "PasswordPolicy",
    "SecurityHeaders",
    "RedisKeys",
    "RateLimitScope",
    "MFAConfig",
    "SessionConfig",
    # HTTP
    "HTTPMethods",
    "PublicEndpoints",
    "AuthEndpoints",
    "HealthEndpoints",
    "PASSWORD_CHANGE_ALLOWED",
    # Configuration
    "Limits",
    # Metrics
    "PATH_NORMALIZATION_PATTERNS",
    # Loyalty enums
    "LoyaltyProgramType",
    "LoyaltyTier",
    "LedgerType",
    "LedgerSource",
    "RevenueLedgerType",
    "RewardTier",
    "RedemptionStatus",
    "WalletPlatform",
    "WalletPassStatus",
    "FlashOfferTarget",
    "FlashOfferStatus",
    "LoyaltyNotifType",
    "NotifChannel",
    # Loyalty constants
    "POINTS_PER_EUR_RESTAURANT",
    "POINTS_PER_EUR_EPICERIE",
    "VIP_MULTIPLIER",
    "VIP_THRESHOLD_POINTS_PER_YEAR",
    "VIP_GRACE_DAYS",
    "POINTS_EXPIRY_MONTHS_EARNED",
    "POINTS_EXPIRY_MONTHS_BONUS",
    "REFERRAL_BONUS_POINTS",
    "MAX_REFERRALS_PER_MEMBER",
    "REWARD_TIER_1_COST",
    "REWARD_TIER_2_COST",
    "REWARD_TIER_3_COST",
    "EXPIRY_WARNING_DAYS_FIRST",
    "EXPIRY_WARNING_DAYS_SECOND",
    "CHURN_RISK_MIN_DAYS",
    "CHURN_RISK_MAX_DAYS",
    "TIER_HABITUE_THRESHOLD_CENTS",
    "TIER_PRIVILEGIE_THRESHOLD_CENTS",
    "DISCOUNT_HABITUE_PERCENT",
    "DISCOUNT_PRIVILEGIE_PERCENT",
    "REVENUE_WINDOW_MONTHS",
    "REFERRAL_CODE_DIGITS",
]
