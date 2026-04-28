"""Endpoints pour le statut du serveur WireGuard."""

import logging

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.deps import InternalAuth, get_internal_auth
from app.schemas.status import PeerStatusResponse, ServerStatusResponse
from app.services.wireguard_backend import get_backend

logger = logging.getLogger(__name__)

router = APIRouter(tags=["status"])


@router.get(
    "/status",
    response_model=ServerStatusResponse,
)
def get_server_status(
    auth: InternalAuth = Depends(get_internal_auth),
):
    """Retourne le statut du serveur WireGuard."""
    settings = get_settings()
    backend = get_backend(settings.WG_BACKEND)

    is_available = backend.is_available()
    peers_stats = backend.list_peers(settings.WG_INTERFACE) if is_available else []

    return ServerStatusResponse(
        backend_available=is_available,
        interface=settings.WG_INTERFACE,
        active_peers_count=len(peers_stats),
        peers=[
            PeerStatusResponse(
                public_key=p.public_key,
                latest_handshake=p.latest_handshake,
                transfer_rx=p.transfer_rx,
                transfer_tx=p.transfer_tx,
                endpoint=p.endpoint,
                allowed_ips=p.allowed_ips,
            )
            for p in peers_stats
        ],
    )
