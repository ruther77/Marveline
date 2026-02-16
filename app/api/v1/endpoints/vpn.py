"""Endpoints proxy VPN WireGuard.

Proxy les requetes vers le microservice WireGuard interne.
Ajoute automatiquement tenant_id et actor_id depuis le JWT.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response

from app.core.deps import get_current_user, VpnReader, VpnWriter, VpnAdmin
from app.models.user import User
from app.schemas.vpn import (
    VpnConfigResponse,
    VpnIpPoolCreate,
    VpnIpPoolListResponse,
    VpnIpPoolResponse,
    VpnPeerCreate,
    VpnPeerListResponse,
    VpnPeerResponse,
    VpnPeerUpdate,
    VpnServerStatusResponse,
)
from app.services.wireguard_client import WireGuardClient, WireGuardClientError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vpn", tags=["VPN"])


def _get_wg_client(current_user: User = Depends(get_current_user)) -> WireGuardClient:
    """Construit un WireGuardClient avec le tenant et actor du user courant."""
    return WireGuardClient(
        tenant_id=current_user.tenant_id,
        actor_id=str(current_user.id),
    )


def _handle_wg_error(exc: WireGuardClientError) -> HTTPException:
    """Convertit une WireGuardClientError en HTTPException."""
    return HTTPException(status_code=exc.status_code, detail=exc.message)


# ── Peers ──────────────────────────────────────────────────────────────


@router.get("/peers", response_model=VpnPeerListResponse)
def list_vpn_peers(
    current_user: VpnReader,
    client: WireGuardClient = Depends(_get_wg_client),
):
    """Liste les peers VPN du tenant."""
    try:
        return client.list_peers()
    except WireGuardClientError as exc:
        raise _handle_wg_error(exc)


@router.get("/peers/{peer_id}", response_model=VpnPeerResponse)
def get_vpn_peer(
    peer_id: str,
    current_user: VpnReader,
    client: WireGuardClient = Depends(_get_wg_client),
):
    """Recupere un peer VPN par son ID."""
    try:
        return client.get_peer(peer_id)
    except WireGuardClientError as exc:
        raise _handle_wg_error(exc)


@router.post("/peers", response_model=VpnPeerResponse, status_code=201)
def create_vpn_peer(
    body: VpnPeerCreate,
    current_user: VpnWriter,
    client: WireGuardClient = Depends(_get_wg_client),
):
    """Cree un nouveau peer VPN."""
    try:
        return client.create_peer(body.model_dump(exclude_unset=True))
    except WireGuardClientError as exc:
        raise _handle_wg_error(exc)


@router.patch("/peers/{peer_id}", response_model=VpnPeerResponse)
def update_vpn_peer(
    peer_id: str,
    body: VpnPeerUpdate,
    current_user: VpnWriter,
    client: WireGuardClient = Depends(_get_wg_client),
):
    """Met a jour un peer VPN."""
    try:
        return client.update_peer(peer_id, body.model_dump(exclude_unset=True))
    except WireGuardClientError as exc:
        raise _handle_wg_error(exc)


@router.delete("/peers/{peer_id}", status_code=204)
def delete_vpn_peer(
    peer_id: str,
    current_user: VpnAdmin,
    client: WireGuardClient = Depends(_get_wg_client),
):
    """Supprime (soft delete) un peer VPN."""
    try:
        client.delete_peer(peer_id)
    except WireGuardClientError as exc:
        raise _handle_wg_error(exc)


@router.post("/peers/{peer_id}/rotate", response_model=VpnPeerResponse)
def rotate_vpn_peer_keys(
    peer_id: str,
    current_user: VpnAdmin,
    client: WireGuardClient = Depends(_get_wg_client),
):
    """Rotation des cles d'un peer VPN."""
    try:
        return client.rotate_peer_keys(peer_id)
    except WireGuardClientError as exc:
        raise _handle_wg_error(exc)


@router.post("/peers/{peer_id}/enable", response_model=VpnPeerResponse)
def enable_vpn_peer(
    peer_id: str,
    current_user: VpnWriter,
    client: WireGuardClient = Depends(_get_wg_client),
):
    """Active un peer VPN."""
    try:
        return client.enable_peer(peer_id)
    except WireGuardClientError as exc:
        raise _handle_wg_error(exc)


@router.post("/peers/{peer_id}/disable", response_model=VpnPeerResponse)
def disable_vpn_peer(
    peer_id: str,
    current_user: VpnWriter,
    client: WireGuardClient = Depends(_get_wg_client),
):
    """Desactive un peer VPN."""
    try:
        return client.disable_peer(peer_id)
    except WireGuardClientError as exc:
        raise _handle_wg_error(exc)


# ── Config & QR ───────────────────────────────────────────────────────


@router.get("/peers/{peer_id}/config", response_model=VpnConfigResponse)
def get_vpn_peer_config(
    peer_id: str,
    current_user: VpnReader,
    client: WireGuardClient = Depends(_get_wg_client),
):
    """Recupere la configuration WireGuard d'un peer."""
    try:
        return client.get_peer_config(peer_id)
    except WireGuardClientError as exc:
        raise _handle_wg_error(exc)


@router.get(
    "/peers/{peer_id}/qrcode",
    responses={200: {"content": {"image/png": {}}}},
)
def get_vpn_peer_qrcode(
    peer_id: str,
    current_user: VpnReader,
    client: WireGuardClient = Depends(_get_wg_client),
):
    """Recupere le QR code WireGuard d'un peer (image PNG)."""
    try:
        png_bytes = client.get_peer_qrcode(peer_id)
    except WireGuardClientError as exc:
        raise _handle_wg_error(exc)
    return Response(content=png_bytes, media_type="image/png")


# ── Status ────────────────────────────────────────────────────────────


@router.get("/status", response_model=VpnServerStatusResponse)
def get_vpn_status(
    current_user: VpnReader,
    client: WireGuardClient = Depends(_get_wg_client),
):
    """Statut du serveur WireGuard."""
    try:
        return client.get_status()
    except WireGuardClientError as exc:
        raise _handle_wg_error(exc)


# ── IP Pools ──────────────────────────────────────────────────────────


@router.get("/ip-pools", response_model=VpnIpPoolListResponse)
def list_vpn_ip_pools(
    current_user: VpnReader,
    client: WireGuardClient = Depends(_get_wg_client),
):
    """Liste les pools IP du tenant."""
    try:
        return client.list_ip_pools()
    except WireGuardClientError as exc:
        raise _handle_wg_error(exc)


@router.post("/ip-pools", response_model=VpnIpPoolResponse, status_code=201)
def create_vpn_ip_pool(
    body: VpnIpPoolCreate,
    current_user: VpnAdmin,
    client: WireGuardClient = Depends(_get_wg_client),
):
    """Cree un nouveau pool IP."""
    try:
        return client.create_ip_pool(body.model_dump(exclude_unset=True))
    except WireGuardClientError as exc:
        raise _handle_wg_error(exc)
