"""Schemas Pydantic pour le microservice WireGuard."""

from app.schemas.config import ClientConfigResponse
from app.schemas.ip_pool import IpPoolCreate, IpPoolListResponse, IpPoolResponse
from app.schemas.peer import PeerCreate, PeerListResponse, PeerResponse, PeerUpdate
from app.schemas.status import PeerStatusResponse, ServerStatusResponse

__all__ = [
    "ClientConfigResponse",
    "IpPoolCreate",
    "IpPoolListResponse",
    "IpPoolResponse",
    "PeerCreate",
    "PeerListResponse",
    "PeerResponse",
    "PeerStatusResponse",
    "PeerUpdate",
    "ServerStatusResponse",
]
