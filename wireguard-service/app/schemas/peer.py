"""Schemas Pydantic pour les peers WireGuard."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PeerCreate(BaseModel):
    """Schema de création d'un peer."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    peer_type: str = Field(default="permanent", pattern=r"^(permanent|temporary|technician)$")
    expires_at: Optional[datetime] = None
    allowed_ips: str = Field(default="0.0.0.0/0", max_length=255)
    dns: Optional[str] = Field(default=None, max_length=255)
    persistent_keepalive: Optional[int] = Field(default=None, ge=0, le=65535)
    pool_id: Optional[int] = None

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None:
            from datetime import timezone

            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            if v <= datetime.now(timezone.utc):
                raise ValueError("expires_at doit être dans le futur")
        return v


class PeerUpdate(BaseModel):
    """Schema de mise à jour d'un peer."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    allowed_ips: Optional[str] = Field(default=None, max_length=255)
    dns: Optional[str] = Field(default=None, max_length=255)
    persistent_keepalive: Optional[int] = Field(default=None, ge=0, le=65535)
    expires_at: Optional[datetime] = None


class PeerResponse(BaseModel):
    """Schema de réponse pour un peer."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = None
    public_key: str
    assigned_ip: str
    allowed_ips: str
    persistent_keepalive: int
    dns: Optional[str] = None
    is_enabled: bool
    is_active: bool
    peer_type: str
    expires_at: Optional[datetime] = None
    created_by: Optional[int] = None
    last_handshake_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PeerListResponse(BaseModel):
    """Schema de réponse paginée pour les peers."""

    items: list[PeerResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
