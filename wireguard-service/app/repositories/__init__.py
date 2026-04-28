"""Repositories pour le microservice WireGuard."""

from app.repositories.audit_log import AuditLogRepository
from app.repositories.base import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    PaginatedResult,
    PaginationError,
    RepositoryException,
    TenantAwareBaseRepository,
    TenantIsolationError,
)
from app.repositories.ip_pool import IpPoolRepository
from app.repositories.peer import PeerRepository

__all__ = [
    "AuditLogRepository",
    "DEFAULT_PAGE_SIZE",
    "IpPoolRepository",
    "MAX_PAGE_SIZE",
    "PaginatedResult",
    "PaginationError",
    "PeerRepository",
    "RepositoryException",
    "TenantAwareBaseRepository",
    "TenantIsolationError",
]
