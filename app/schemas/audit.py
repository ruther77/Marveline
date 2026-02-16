"""Schemas Pydantic pour Audit Log endpoints."""
import math
from datetime import datetime
from typing import Optional, Any
from pydantic import Field, ConfigDict, computed_field
from app.schemas.base import BaseSchema
from app.constants import Limits


class AuditLogResponse(BaseSchema):
    """Schema pour réponse d'un audit log individuel.

    Example:
        {
            "id": 123,
            "user_id": 42,
            "tenant_id": 1,
            "action": "UPDATE",
            "entity_type": "Reservation",
            "entity_id": 456,
            "changes": {
                "status": {"before": "draft", "after": "confirmed"}
            },
            "description": "Updated Reservation #456: status",
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0...",
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "created_at": "2026-02-12T14:30:00Z"
        }
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 123,
                "user_id": 42,
                "tenant_id": 1,
                "action": "UPDATE",
                "entity_type": "Reservation",
                "entity_id": 456,
                "changes": {
                    "status": {"before": "draft", "after": "confirmed"},
                    "total_amount": {"before": 10000, "after": 12000}
                },
                "description": "Updated Reservation #456: status, total_amount",
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2026-02-12T14:30:00Z"
            }
        }
    )

    id: int = Field(
        ...,
        description="ID unique de l'audit log"
    )

    user_id: Optional[int] = Field(
        None,
        description="ID utilisateur ayant effectué l'action (NULL pour actions système)"
    )

    tenant_id: int = Field(
        ...,
        description="ID du tenant (isolation multi-tenant)"
    )

    action: str = Field(
        ...,
        description="Type d'action: CREATE, UPDATE, DELETE, SOFT_DELETE, READ_SENSITIVE, LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT"
    )

    entity_type: Optional[str] = Field(
        None,
        description="Type d'entité impactée: Customer, Reservation, Invoice, Product, User"
    )

    entity_id: Optional[int] = Field(
        None,
        description="ID de l'entité impactée (NULL pour actions globales)"
    )

    changes: Optional[dict[str, Any]] = Field(
        None,
        description="JSONB modifications (before/after pour UPDATE, after pour CREATE, before pour DELETE)"
    )

    description: Optional[str] = Field(
        None,
        description="Description humaine de l'action"
    )

    ip_address: Optional[str] = Field(
        None,
        description="Adresse IP du client (IPv4/IPv6)"
    )

    user_agent: Optional[str] = Field(
        None,
        description="User-Agent du navigateur/client"
    )

    request_id: Optional[str] = Field(
        None,
        description="UUID de requête pour corrélation logs"
    )

    created_at: datetime = Field(
        ...,
        description="Timestamp immuable de l'action"
    )


class AuditLogList(BaseSchema):
    """Schema pour liste d'audit logs avec pagination.

    Example:
        {
            "logs": [...],
            "total": 150,
            "skip": 0,
            "limit": 100
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "logs": [
                    {
                        "id": 123,
                        "user_id": 42,
                        "action": "CREATE",
                        "entity_type": "Customer",
                        "entity_id": 456,
                        "created_at": "2026-02-12T14:30:00Z"
                    }
                ],
                "total": 150,
                "skip": 0,
                "limit": 100
            }
        }
    )

    logs: list[AuditLogResponse] = Field(
        ...,
        description="Liste des audit logs"
    )

    total: int = Field(
        ...,
        description="Nombre total d'audit logs (avant pagination)"
    )

    skip: int = Field(
        default=0,
        description="Offset pagination"
    )

    limit: int = Field(
        default=Limits.DEFAULT_PAGE_SIZE,
        description="Limite pagination"
    )

    @computed_field
    @property
    def total_pages(self) -> int:
        """Nombre total de pages calculé depuis total et limit."""
        if self.limit <= 0:
            return 1
        return math.ceil(self.total / self.limit)


class AuditLogFilters(BaseSchema):
    """Schema pour filtres de recherche audit logs.

    Example:
        {
            "start_date": "2026-02-01T00:00:00Z",
            "end_date": "2026-02-28T23:59:59Z",
            "user_id": 42,
            "action": "UPDATE",
            "entity_type": "Reservation"
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_date": "2026-02-01T00:00:00Z",
                "end_date": "2026-02-28T23:59:59Z",
                "user_id": 42,
                "action": "UPDATE",
                "entity_type": "Reservation"
            }
        }
    )

    start_date: Optional[datetime] = Field(
        None,
        description="Date début (inclusive)"
    )

    end_date: Optional[datetime] = Field(
        None,
        description="Date fin (inclusive)"
    )

    user_id: Optional[int] = Field(
        None,
        description="Filtrer par ID utilisateur"
    )

    action: Optional[str] = Field(
        None,
        description="Filtrer par type d'action (CREATE, UPDATE, DELETE, etc.)"
    )

    entity_type: Optional[str] = Field(
        None,
        description="Filtrer par type d'entité (Customer, Reservation, etc.)"
    )

    entity_id: Optional[int] = Field(
        None,
        description="Filtrer par ID entité spécifique"
    )
