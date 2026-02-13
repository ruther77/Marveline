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
    InvoiceStatus,
    PaymentMethod,
    ProductCategory,
    ProductCondition,
    ReservationStatus,
    TokenType,
    UserRole,
)
from app.constants.errors import ErrorMessages, HTTPStatusMessages
from app.constants.http import AuthEndpoints, HealthEndpoints, HTTPMethods, PublicEndpoints
from app.constants.limits import Limits
from app.constants.security import RateLimitScope, RedisKeys, SecurityHeaders

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
    # Messages & Erreurs
    "ErrorMessages",
    "HTTPStatusMessages",
    # Sécurité
    "SecurityHeaders",
    "RedisKeys",
    "RateLimitScope",
    # HTTP
    "HTTPMethods",
    "PublicEndpoints",
    "AuthEndpoints",
    "HealthEndpoints",
    # Configuration
    "Limits",
]
