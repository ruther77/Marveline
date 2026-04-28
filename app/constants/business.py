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

    Correspond aux 20 catégories du catalogue Marveline.

    Utilisé dans :
        - models.Product.category
        - schemas.ProductCreate.category
        - Filtres API GET /products?category=...
    """

    ACCESSOIRES_TRANSPORT = "accessoires_transport"
    ASSIETTES = "assiettes"
    BANCS = "bancs"
    CANDY_BAR = "candy_bar"
    CHAISES = "chaises"
    COUVERTS = "couverts"
    DECORATIONS = "decorations"
    HOUSSES = "housses"
    MACHINES = "machines"
    MANGE_DEBOUT = "mange_debout"
    MOBILIER = "mobilier"
    NAPPAGES = "nappages"
    NAPPES = "nappes"
    PORCELAINE = "porcelaine"
    SERVIETTES = "serviettes"
    TABLES = "tables"
    VAISSELLE = "vaisselle"
    VAISSELLE_SERVICE = "vaisselle_service"
    VAISSELLE_ENFANTS = "vaisselle_enfants"
    VERRES = "verres"


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
    PROFESSIONAL = "professional"
    ASSOCIATION = "association"


class ReservationStatus(str, Enum):
    """Statut du cycle de vie d'une réservation.

    Workflow :
        DRAFT → CONFIRMED → DELIVERED → RETURNED → COMPLETED
                         ↘ CANCELLED
        RETURNED_DISPUTE → RETURNED → COMPLETED
                         ↘ COMPLETED (clôture directe)

    Utilisé dans :
        - models.Reservation.status
        - services.ReservationService (transitions de statut)
        - Filtres API GET /reservations?status=...
    """

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PRE_CHECK = "pre_check"
    CONFIRMED_RISK = "confirmed_risk"
    DELIVERED = "delivered"
    EXTENDED = "extended"
    RETURNED = "returned"
    RETURNED_DISPUTE = "returned_dispute"
    COMPLETED = "completed"
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


class DepositStatus(str, Enum):
    """Statut du cycle de vie d'une caution.

    Workflow :
        HELD → RELEASED (restitution complète)
        HELD → RETAINED  (retenue partielle ou totale, ex: dommages)

    Utilisé dans :
        - models.Deposit.status
        - schemas.DepositUpdate.status
        - Filtres API GET /deposits?status=...
    """

    HELD = "held"
    RELEASED = "released"
    RETAINED = "retained"


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
    """Roles utilisateur pour controle d'acces RBAC (CaroCorp §6.1).

    Hierarchie (level 0 = plus eleve) :
        SUPER_ADMIN(0) > PLATFORM_OPS(1) > TENANT_ADMIN(2) > MANAGER(3) > STAFF(4) > VIEWER(5)

    Niveaux :
        - Niveau 1 (systeme, cross-tenant) : super_admin, platform_ops
        - Niveau 2 (tenant) : tenant_admin, manager, staff, viewer

    Utilise dans :
        - models.User.role (legacy, migration vers user_roles)
        - auth_roles table (source de verite)
        - JWT claim "role"
    """

    SUPER_ADMIN = "super_admin"
    PLATFORM_OPS = "platform_ops"
    TENANT_ADMIN = "tenant_admin"
    MANAGER = "manager"
    STAFF = "staff"
    VIEWER = "viewer"

    # Legacy : "admin" existe en DB (CHECK constraint users.role).
    # Migration Alembic convertira "admin" → "tenant_admin".
    # Jusqu'a la migration, le code legacy utilise ADMIN = "admin".
    ADMIN = "admin"


class TokenType(str, Enum):
    """Types de tokens JWT.

    Utilisé dans :
        - core.security (création tokens access/refresh)
        - core.deps (validation token type)
        - services.auth (refresh token validation)
    """

    ACCESS = "access"
    REFRESH = "refresh"


# ── Inventory Movements ─────────────────────────────────────────────


class MovementType(str, Enum):
    """Type de mouvement de stock.

    Utilisé dans :
        - models.InventoryMovement.movement_type
        - schemas.CreateMovementRequest.movement_type
        - Filtres API GET /inventory-movements?movement_type=...
    """

    DEPARTURE = "departure"
    RETURN = "return"


class MovementStatus(str, Enum):
    """Statut du cycle de vie d'un mouvement de stock.

    Workflow :
        SCHEDULED → IN_TRANSIT → COMPLETED
                               ↘ LATE
        Tout statut → CANCELLED

    Utilisé dans :
        - models.InventoryMovement.status
        - services.MovementService (transitions de statut)
        - Filtres API GET /inventory-movements?status=...
    """

    SCHEDULED = "scheduled"
    IN_TRANSIT = "in_transit"
    COMPLETED = "completed"
    LATE = "late"
    CANCELLED = "cancelled"


class DeliveryMethod(str, Enum):
    """Méthode de livraison pour un mouvement.

    Utilisé dans :
        - models.InventoryMovement.delivery_method
        - schemas.CreateMovementRequest.delivery_method
    """

    DELIVERY = "delivery"
    PICKUP = "pickup"
    SHIPPING = "shipping"


class InspectionStatus(str, Enum):
    """Statut d'inspection au retour du matériel.

    Utilisé dans :
        - models.InventoryMovement.inspection_status
        - schemas.UpdateMovementRequest.inspection_status
    """

    PENDING = "pending"
    OK = "ok"
    DAMAGED = "damaged"
    MISSING = "missing"


class ItemCondition(str, Enum):
    """État d'un article dans un mouvement.

    Utilisé dans :
        - models.MovementItem.condition
        - schemas.CreateMovementRequest.items[].condition
    """

    PERFECT = "perfect"
    GOOD = "good"
    DAMAGED = "damaged"
    MISSING = "missing"


class ProductColor(str, Enum):
    """Couleurs disponibles pour les variantes de produits.

    Couvre les couleurs proposées par Marveline pour :
        - Nappes : blanc, ivoire, bordeaux, noir, rouge, vert_amande, vert_sapin
        - Serviettes : blanc, ivoire, bordeaux, noir, rouge, vert_amande, taupe
        - Housses : blanc, ivoire

    Utilisé dans :
        - models.ProductVariant.color
        - schemas.ProductVariantCreate.color
    """

    BLANC = "blanc"
    IVOIRE = "ivoire"
    BORDEAUX = "bordeaux"
    NOIR = "noir"
    ROUGE = "rouge"
    VERT_AMANDE = "vert_amande"
    VERT_SAPIN = "vert_sapin"
    TAUPE = "taupe"


class ProductGamme(str, Enum):
    """Gammes/finitions disponibles pour les variantes de produits.

    Utilisé pour les verres, couverts et articles avec niveaux de finition :
        - classique : gamme standard
        - elegance  : gamme intermédiaire
        - open_up   : gamme Open'Up (verres spéciaux)
        - prestige  : gamme haut de gamme
        - vintage   : gamme vintage
        - bois      : gamme bois/naturel

    Utilisé dans :
        - models.ProductVariant.gamme
        - schemas.ProductVariantCreate.gamme
    """

    CLASSIQUE = "classique"
    ELEGANCE  = "elegance"
    OPEN_UP   = "open_up"
    PRESTIGE  = "prestige"
    VINTAGE   = "vintage"
    BOIS      = "bois"


class StockItemStatus(str, Enum):
    """Statuts d'une unité physique de stock.

    Cycle de vie :
        available → reserved (reservation.confirm)
        reserved → on_location (mouvement DELIVERY complété)
        on_location → available (mouvement RETURN OK)
        on_location → damaged (mouvement RETURN article cassé)
        damaged → in_repair (action manuelle)
        in_repair → available (action manuelle)
        any → retired (mise au rebut)

    Utilisé dans :
        - models.StockItem.status
        - repositories.stock_item.StockItemRepository
        - services.stock_item.StockItemService
    """

    AVAILABLE = "available"
    RESERVED = "reserved"
    ON_LOCATION = "on_location"
    DAMAGED = "damaged"
    IN_REPAIR = "in_repair"
    RETIRED = "retired"


# Tenant ID spécial pour événements système (login failed sans tenant connu, etc.)
SYSTEM_TENANT_ID: int = 0


# ── RÈGLES MÉTIER MARVELINE.FR ────────────────────────────────────────────────
# Source : CGV et FAQ marveline.fr (relevé 2026-02-17)

DEPOSIT_RATE: float = 3.0
"""Caution = 3× montant TTC facture (règle générale CGV)."""

SELFIE_BOOTH_DEPOSIT_CENTS: int = 300_000
"""Caution fixe borne à selfie = 3 000€ (exception au taux général)."""

ADVANCE_PAYMENT_PERCENT: int = 40
"""Acompte 40% du montant TTC — en pourcentage entier (pas float)."""

ADVANCE_DUE_DAYS: int = 7
"""Echeance acompte : N jours apres confirmation."""

BALANCE_DUE_DAYS_BEFORE_EVENT: int = 7
"""Solde restant du N jours avant la date de l'evenement."""

LATE_RETURN_PENALTY_RATE: float = 0.20
"""Pénalité retard : 20% du montant TTC par jour de retard."""

LINEN_MIN_BOOKING_DAYS: int = 90
"""Nappages : réservation obligatoire 90 jours minimum avant l'événement."""

HOURLY_RATE_WEEKDAY_CENTS: int = 3_000
"""Main d'œuvre semaine : 30€ HT/heure (en centimes)."""

HOURLY_RATE_WEEKEND_CENTS: int = 6_000
"""Main d'œuvre nuit/WE/jours fériés : 60€ HT/heure (en centimes)."""

TVA_RATE: float = 0.20
"""Taux de TVA applicable : 20%."""

LOW_STOCK_THRESHOLD: int = 5
"""Seuil d'alerte stock faible : produit en alerte si available_quantity < seuil."""


class DevisStatus(str, Enum):
    """Statut du cycle de vie d'un devis.

    Workflow :
        DRAFT → SENT → NEGOTIATION ↔ VERSION_PENDING
                     → ACCEPTED → CONVERTED
                     → REFUSED
                     → EXPIRED → DRAFT (renouvellement)
        Tout statut actif → CANCELLED

    Utilisé dans :
        - models.Devis.status
        - services.DevisService (transitions)
        - Filtres API GET /devis?status=...
    """

    DRAFT = "draft"
    SENT = "sent"
    NEGOTIATION = "negotiation"
    ACCEPTED = "accepted"
    REFUSED = "refused"
    EXPIRED = "expired"
    CONVERTED = "converted"
    CANCELLED = "cancelled"
    VERSION_PENDING = "version_pending"


class VenteStatus(str, Enum):
    """Statut du cycle de vie d'une vente directe.

    Workflow :
        DRAFT → PENDING → DEPOSIT_PAID → FULLY_PAID
                        ↘ OVERDUE
        Tout statut → REFUNDED

    Utilisé dans :
        - models.Vente.status
        - services.VenteService (transitions)
    """

    DRAFT = "draft"
    PENDING = "pending"
    DEPOSIT_PAID = "deposit_paid"
    FULLY_PAID = "fully_paid"
    OVERDUE = "overdue"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class EventStatus(str, Enum):
    """Statut du cycle de vie d'un événement.

    Workflow :
        PLANNED → IN_PROGRESS → RETURNED → CLOSED
               ↘ RISK → IN_PROGRESS
               → INCIDENT → DAMAGE → CLOSED
               → CANCELLED

    Utilisé dans :
        - models.Evenement.status
        - services.EvenementService (transitions)
    """

    PLANNED = "planned"
    RISK = "risk"
    IN_PROGRESS = "in_progress"
    INCIDENT = "incident"
    RETURNED = "returned"
    DAMAGE = "damage"
    CANCELLED = "cancelled"
    CLOSED = "closed"


class ReservationDeliveryMethod(str, Enum):
    """Méthode de livraison d'une réservation.

    Utilisé dans :
        - models.Reservation.delivery_method
        - schemas.ReservationUpdate.delivery_method
    """

    SELF = "self"        # Livraison propre — calcul auto frais
    CARRIER = "carrier"  # Transporteur externe (Boxtal) — tarif choisi
    PICKUP = "pickup"    # Retrait client — 0€


# Seuils logistiques livraison
WEIGHT_SURCHARGE_THRESHOLD_GRAMS = 500_000  # 500 kg
WEIGHT_SURCHARGE_CENTS = 5000  # 50€ de surcharge poids


class ContainerType(str, Enum):
    """Type de contenant logistique Marveline.

    Utilisé dans :
        - models.Container.container_type
        - schemas.ContainerCreate.container_type
    """

    BAC = "bac"
    CARTON = "carton"
    PALETTE = "palette"
    HOUSSE = "housse"
    CAISSE = "caisse"


class RelanceStatus(str, Enum):
    """Statut d'une relance planifiée.

    Workflow :
        SCHEDULED → SENT
                  → CANCELLED

    Utilisé dans :
        - models.Relance.status
        - schemas.RelanceResponse
    """

    SCHEDULED = "scheduled"
    SENT = "sent"
    CANCELLED = "cancelled"


# ── Event type constraints ──────────────────────────────────────────
EVENT_TYPE_MIN_DAYS: dict[str, int] = {
    "mariage": 3,
    "entreprise": 2,
    "anniversaire": 1,
    "autre": 1,
}


__all__ = [
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
    # Nouvelles sessions B1→B4
    "DevisStatus",
    "VenteStatus",
    "EventStatus",
    "ReservationDeliveryMethod",
    "WEIGHT_SURCHARGE_THRESHOLD_GRAMS",
    "WEIGHT_SURCHARGE_CENTS",
    "ContainerType",
    "RelanceStatus",
    # Règles métier marveline.fr
    "DEPOSIT_RATE",
    "SELFIE_BOOTH_DEPOSIT_CENTS",
    "ADVANCE_DUE_DAYS",
    "ADVANCE_PAYMENT_PERCENT",
    "BALANCE_DUE_DAYS_BEFORE_EVENT",
    "LATE_RETURN_PENALTY_RATE",
    "LINEN_MIN_BOOKING_DAYS",
    "HOURLY_RATE_WEEKDAY_CENTS",
    "HOURLY_RATE_WEEKEND_CENTS",
    "TVA_RATE",
    "LOW_STOCK_THRESHOLD",
    "ProductColor",
    "ProductGamme",
    "StockItemStatus",
    "EVENT_TYPE_MIN_DAYS",
]
