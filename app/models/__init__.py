"""Modèles SQLAlchemy CaroCorp - Import centralisé pour Alembic autogenerate."""
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin
from app.models.user import User
from app.models.customer import Customer
from app.models.product import Product
from app.models.reservation import Reservation, ReservationLine
from app.models.invoice import Invoice
from app.models.audit_log import AuditLog
from app.models.mfa import MFADevice
from app.models.category import Category
from app.models.bundle import ProductBundle, BundleItem
from app.models.api_key import ApiKey
from app.models.feature_flag import FeatureFlag
from app.models.inventory_movement import InventoryMovement, MovementItem

__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",
    "TenantMixin",
    "SoftDeleteMixin",
    # Auth models
    "User",
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
    "Invoice",
    "InventoryMovement",
    "MovementItem",
    # Audit & Security
    "AuditLog",
]
