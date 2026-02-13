"""Constantes métier de l'application CaroCorp.

Ce module centralise tous les Enums et constantes liés au domaine métier :
- Catégories et états des produits
- Types de clients
- Statuts des réservations, factures
- Méthodes de paiement
- Rôles utilisateurs (RBAC)
"""

from enum import Enum


class ProductCategory(str, Enum):
    """Catégories de produits disponibles à la location.

    Utilisé dans :
        - models.Product.category
        - schemas.ProductCreate.category
        - Filtres API GET /products?category=...
    """

    ASSIETTE = "assiette"
    VERRE = "verre"
    COUVERT = "couvert"
    NAPPE = "nappe"
    DECO = "deco"
    AUTRE = "autre"


class ProductCondition(str, Enum):
    """État physique d'un produit.

    Utilisé dans :
        - models.Product.condition
        - schemas.ProductCreate.condition
        - Filtres de qualité pour réservations
    """

    NEUF = "neuf"
    BON = "bon"
    USE = "use"
    HORS_SERVICE = "hors_service"


class CustomerType(str, Enum):
    """Type de client (particulier ou entreprise).

    Utilisé dans :
        - models.Customer.customer_type
        - schemas.CustomerCreate.customer_type
        - Logique de validation (SIRET obligatoire si COMPANY)
    """

    INDIVIDUAL = "individual"
    COMPANY = "company"


class ReservationStatus(str, Enum):
    """Statut du cycle de vie d'une réservation.

    Workflow :
        DRAFT → CONFIRMED → DELIVERED → RETURNED
                         ↘ CANCELLED

    Utilisé dans :
        - models.Reservation.status
        - services.ReservationService (transitions de statut)
        - Filtres API GET /reservations?status=...
    """

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    DELIVERED = "delivered"
    RETURNED = "returned"
    CANCELLED = "cancelled"


class InvoiceStatus(str, Enum):
    """Statut du cycle de vie d'une facture.

    Workflow :
        DRAFT → SENT → PAID
                    ↘ OVERDUE
        Tout statut → CANCELLED

    Utilisé dans :
        - models.Invoice.status
        - services.InvoiceService (calcul auto-overdue)
        - Filtres API GET /invoices?status=...
    """

    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    """Méthodes de paiement acceptées.

    Utilisé dans :
        - models.Payment.payment_method
        - schemas.AddPaymentRequest.payment_method
        - Rapports comptables par méthode
    """

    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"
    CHECK = "check"


class UserRole(str, Enum):
    """Rôles utilisateur pour contrôle d'accès (RBAC).

    Hiérarchie :
        ADMIN > MANAGER > STAFF

    Permissions :
        - ADMIN : Tous droits + gestion users
        - MANAGER : CRUD réservations/factures/clients
        - STAFF : Read-only

    Utilisé dans :
        - models.User.role
        - core.deps.require_role (décorateur endpoints)
        - Middleware RBAC
    """

    ADMIN = "admin"
    MANAGER = "manager"
    STAFF = "staff"


class TokenType(str, Enum):
    """Types de tokens JWT.

    Utilisé dans :
        - core.security (création tokens access/refresh)
        - core.deps (validation token type)
        - services.auth (refresh token validation)
    """

    ACCESS = "access"
    REFRESH = "refresh"


__all__ = [
    "ProductCategory",
    "ProductCondition",
    "CustomerType",
    "ReservationStatus",
    "InvoiceStatus",
    "PaymentMethod",
    "UserRole",
    "TokenType",
]
