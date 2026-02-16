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
    raise HTTPException(status_code=404, detail=ErrorMessages.PRODUCT_NOT_FOUND)
"""

# Import de tous les Enums et classes depuis les sous-modules
from app.constants.business import (
    CustomerType,
    DeliveryMethod,
    InspectionStatus,
    InvoiceStatus,
    ItemCondition,
    MovementStatus,
    MovementType,
    PaymentMethod,
    ProductCategory,
    ProductCondition,
    ReservationStatus,
    SYSTEM_TENANT_ID,
    TokenType,
    UserRole,
)
from app.constants.errors import ErrorMessages, HTTPStatusMessages
from app.constants.http import AuthEndpoints, HealthEndpoints, HTTPMethods, PublicEndpoints
from app.constants.limits import Limits
from app.constants.metrics import PATH_NORMALIZATION_PATTERNS
from app.constants.security import Argon2Params, BruteForceThresholds, MFAConfig, PasswordPolicy, RateLimitScope, RedisKeys, SecurityHeaders, SessionConfig

# Exports publics du package
__all__ = [
    # Enums métier
    "ProductCategory",
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
    "SYSTEM_TENANT_ID",
    # Messages & Erreurs
    "ErrorMessages",
    "HTTPStatusMessages",
    # Sécurité
    "Argon2Params",
    "BruteForceThresholds",
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
    # Configuration
    "Limits",
    # Metrics
    "PATH_NORMALIZATION_PATTERNS",
]
