"""Schemas Pydantic pour le statut du serveur WireGuard."""

from pydantic import BaseModel


class PeerStatusResponse(BaseModel):
    """Statistiques d'un peer individuel."""

    public_key: str
    latest_handshake: int = 0
    transfer_rx: int = 0
    transfer_tx: int = 0
    endpoint: str = ""
    allowed_ips: str = ""


class ServerStatusResponse(BaseModel):
    """Statut global du serveur WireGuard."""

    backend_available: bool
    interface: str
    active_peers_count: int
    peers: list[PeerStatusResponse]
