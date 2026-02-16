"""Repositories pour accès aux données avec isolation multi-tenant."""
from app.repositories.base import BaseRepository
from app.repositories.customer import CustomerRepository
from app.repositories.product import ProductRepository
from app.repositories.reservation import (
    ReservationRepository,
    ReservationLineRepository,
)
from app.repositories.invoice import InvoiceRepository
from app.repositories.api_key import ApiKeyRepository
from app.repositories.feature_flag import FeatureFlagRepository
from app.repositories.user import UserRepository
from app.repositories.inventory_movement import MovementRepository, MovementItemRepository
from app.repositories.bundle import BundleRepository, BundleItemRepository
from app.repositories.category import CategoryRepository

__all__ = [
    "BaseRepository",
    "CustomerRepository",
    "ProductRepository",
    "ReservationRepository",
    "ReservationLineRepository",
    "InvoiceRepository",
    "ApiKeyRepository",
    "FeatureFlagRepository",
    "UserRepository",
    "MovementRepository",
    "MovementItemRepository",
    "BundleRepository",
    "BundleItemRepository",
    "CategoryRepository",
]
