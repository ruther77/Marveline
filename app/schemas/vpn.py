"""Schemas Pydantic pour le proxy VPN WireGuard.

Ces schemas re-exposent les memes structures que le microservice WireGuard
pour validation cote API Marveline avant proxy.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Peers ──────────────────────────────────────────────────────────────


class VpnPeerCreate(BaseModel):
    """Donnees de creation d'un peer VPN."""

    name: str = Field(..., min_length=1, max_length=100)
    peer_type: str = Field(default="client", pattern=r"^(client|site|mobile|temporary)$")
    allowed_ips: Optional[str] = None
    dns: Optional[str] = None
    persistent_keepalive: int = Field(default=25, ge=0, le=300)
    expires_at: Optional[datetime] = None


class VpnPeerUpdate(BaseModel):
    """Donnees de mise a jour d'un peer VPN."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    allowed_ips: Optional[str] = None
    dns: Optional[str] = None
    persistent_keepalive: Optional[int] = Field(default=None, ge=0, le=300)
    expires_at: Optional[datetime] = None
    is_enabled: Optional[bool] = None


class VpnPeerResponse(BaseModel):
    """Reponse peer VPN (passthrough du WG service)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: Optional[int] = None  # Optionnel car non retourne par le microservice
    name: str
    public_key: str
    assigned_ip: Optional[str] = None
    allowed_ips: str = "0.0.0.0/0"
    dns: Optional[str] = None
    persistent_keepalive: int = 25
    peer_type: str = "client"
    is_enabled: bool = True
    is_active: bool = True
    expires_at: Optional[datetime] = None
    created_by: Optional[int] = None  # Int car le microservice retourne un int
    created_at: datetime
    updated_at: datetime


class VpnPeerListResponse(BaseModel):
    """Liste paginee de peers VPN."""

    items: list[VpnPeerResponse]
    total: int


# ── Config ─────────────────────────────────────────────────────────────


class VpnConfigResponse(BaseModel):
    """Configuration WireGuard d'un peer."""

    peer_name: str
    config_text: str
    filename: str


# ── Status ─────────────────────────────────────────────────────────────


class VpnPeerStatusResponse(BaseModel):
    """Statut temps reel d'un peer WireGuard."""

    public_key: str
    latest_handshake: int = 0
    transfer_rx: int = 0
    transfer_tx: int = 0
    endpoint: str = ""
    allowed_ips: str = ""


class VpnServerStatusResponse(BaseModel):
    """Statut du serveur WireGuard."""

    backend_available: bool
    interface: str
    active_peers_count: int
    peers: list[VpnPeerStatusResponse]


# ── IP Pools ───────────────────────────────────────────────────────────


class VpnIpPoolCreate(BaseModel):
    """Creation d'un pool IP."""

    subnet: str = Field(
        ...,
        min_length=7,
        max_length=18,
        pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$",
    )
    gateway_ip: str = Field(..., min_length=7, max_length=15)
    description: Optional[str] = Field(default=None, max_length=255)


class VpnIpPoolResponse(BaseModel):
    """Reponse pool IP."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    subnet: str
    gateway_ip: str
    next_ip: str
    subnet_mask: int
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class VpnIpPoolListResponse(BaseModel):
    """Liste des pools IP."""

    items: list[VpnIpPoolResponse]
    total: int
