"""Modèles SQLAlchemy CaroCorp - Import centralisé pour Alembic autogenerate."""
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin
from app.models.user import User
from app.models.customer import Customer
from app.models.product import Product
from app.models.reservation import Reservation, ReservationLine
from app.models.invoice import Invoice
from app.models.audit_log import AuditLog

__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",
    "TenantMixin",
    "SoftDeleteMixin",
    # Auth models
    "User",
    # Business models
    "Customer",
    "Product",
    "Reservation",
    "ReservationLine",
    "Invoice",
    # Audit & Security
    "AuditLog",
]
