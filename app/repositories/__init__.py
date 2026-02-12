"""Repositories pour accès aux données avec isolation multi-tenant."""
from app.repositories.base import BaseRepository
from app.repositories.customer import CustomerRepository
from app.repositories.product import ProductRepository
from app.repositories.reservation import (
    ReservationRepository,
    ReservationLineRepository,
)
from app.repositories.invoice import InvoiceRepository

__all__ = [
    "BaseRepository",
    "CustomerRepository",
    "ProductRepository",
    "ReservationRepository",
    "ReservationLineRepository",
    "InvoiceRepository",
]
