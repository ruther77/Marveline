"""Modèles SQLAlchemy CaroCorp - Import centralisé pour Alembic autogenerate."""
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin
from app.models.customer import Customer
from app.models.product import Product
from app.models.reservation import Reservation, ReservationLine
from app.models.invoice import Invoice

__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",
    "TenantMixin",
    "SoftDeleteMixin",
    # Business models
    "Customer",
    "Product",
    "Reservation",
    "ReservationLine",
    "Invoice",
]
