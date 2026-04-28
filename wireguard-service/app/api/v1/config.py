"""Endpoints pour la configuration client et QR code WireGuard."""

import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import InternalAuth, get_db, get_internal_auth
from app.schemas.config import ClientConfigResponse
from app.services.config_generator import ConfigGeneratorService, get_server_public_key
from app.services.peer_service import PeerNotFoundError, PeerService
from app.services.wireguard_backend import get_backend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/peers", tags=["config"])


def _get_peer_service(
    request: Request,
    db: Session = Depends(get_db),
    auth: InternalAuth = Depends(get_internal_auth),
) -> PeerService:
    """Construit le PeerService avec les dependances injectees."""
    settings = get_settings()
    backend = get_backend(settings.WG_BACKEND)
    return PeerService(
        session=db,
        tenant_id=auth.tenant_id,
        backend=backend,
        actor_id=auth.actor_id,
        ip_address=request.client.host if request.client else None,
    )


def _get_config_generator() -> ConfigGeneratorService:
    """Construit le ConfigGeneratorService."""
    settings = get_settings()
    server_public_key = get_server_public_key(settings.WG_PRIVATE_KEY)
    return ConfigGeneratorService(
        server_public_key=server_public_key,
        server_endpoint=settings.WG_ENDPOINT,
        server_port=settings.WG_LISTEN_PORT,
    )


def _sanitize_filename(name: str) -> str:
    """Nettoie le nom du peer pour l'utiliser comme nom de fichier."""
    sanitized = re.sub(r"[^\w\-.]", "_", name)
    return sanitized[:50] if sanitized else "peer"


@router.get(
    "/{peer_id}/config",
    response_model=ClientConfigResponse,
)
def get_peer_config(
    peer_id: uuid.UUID,
    service: PeerService = Depends(_get_peer_service),
    config_gen: ConfigGeneratorService = Depends(_get_config_generator),
):
    """Genere la configuration client WireGuard pour un peer."""
    try:
        peer = service.get_peer(peer_id)
        private_key = service.get_peer_private_key(peer_id)
    except PeerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Peer {peer_id} not found",
        )

    conf_text = config_gen.generate_conf_text(
        peer_name=peer.name,
        private_key=private_key,
        address=peer.assigned_ip,
        dns=peer.dns or "",
        preshared_key=peer.preshared_key,
        allowed_ips=peer.allowed_ips,
        persistent_keepalive=peer.persistent_keepalive,
    )

    filename = f"{_sanitize_filename(peer.name)}.conf"

    return ClientConfigResponse(
        peer_name=peer.name,
        config_text=conf_text,
        filename=filename,
    )


@router.get(
    "/{peer_id}/qrcode",
    responses={200: {"content": {"image/png": {}}}},
)
def get_peer_qrcode(
    peer_id: uuid.UUID,
    service: PeerService = Depends(_get_peer_service),
    config_gen: ConfigGeneratorService = Depends(_get_config_generator),
):
    """Genere le QR code de la configuration WireGuard pour un peer."""
    try:
        peer = service.get_peer(peer_id)
        private_key = service.get_peer_private_key(peer_id)
    except PeerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Peer {peer_id} not found",
        )

    conf_text = config_gen.generate_conf_text(
        peer_name=peer.name,
        private_key=private_key,
        address=peer.assigned_ip,
        dns=peer.dns or "",
        preshared_key=peer.preshared_key,
        allowed_ips=peer.allowed_ips,
        persistent_keepalive=peer.persistent_keepalive,
    )

    qr_bytes = config_gen.generate_qr_code(conf_text)

    return Response(
        content=qr_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="{_sanitize_filename(peer.name)}_qr.png"',
        },
    )
