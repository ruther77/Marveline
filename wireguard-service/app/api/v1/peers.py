"""Endpoints CRUD et actions pour les peers WireGuard."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import InternalAuth, get_db, get_internal_auth
from app.schemas.peer import PeerCreate, PeerListResponse, PeerResponse, PeerUpdate
from app.services.ip_allocator import IpExhaustedError
from app.services.peer_service import (
    PeerLimitReachedError,
    PeerNotFoundError,
    PeerService,
)
from app.services.wireguard_backend import get_backend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/peers", tags=["peers"])


def _get_peer_service(
    request: Request,
    db: Session = Depends(get_db),
    auth: InternalAuth = Depends(get_internal_auth),
) -> PeerService:
    """Construit le PeerService avec les dépendances injectées."""
    settings = get_settings()
    backend = get_backend(settings.WG_BACKEND)
    return PeerService(
        session=db,
        tenant_id=auth.tenant_id,
        backend=backend,
        actor_id=auth.actor_id,
        ip_address=request.client.host if request.client else None,
    )


# ------------------------------------------------------------------
# CRUD
# ------------------------------------------------------------------


@router.post(
    "",
    response_model=PeerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_peer(
    body: PeerCreate,
    db: Session = Depends(get_db),
    service: PeerService = Depends(_get_peer_service),
):
    """Crée un nouveau peer WireGuard."""
    try:
        peer = service.create_peer(
            name=body.name,
            description=body.description,
            peer_type=body.peer_type,
            expires_at=body.expires_at,
            allowed_ips=body.allowed_ips,
            dns=body.dns,
            persistent_keepalive=body.persistent_keepalive,
            pool_id=body.pool_id,
        )
        db.commit()
        return peer
    except PeerLimitReachedError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except IpExhaustedError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except Exception:
        db.rollback()
        logger.exception("Unexpected error creating peer")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/{peer_id}",
    response_model=PeerResponse,
)
def get_peer(
    peer_id: uuid.UUID,
    service: PeerService = Depends(_get_peer_service),
):
    """Récupère un peer par son ID."""
    try:
        return service.get_peer(peer_id)
    except PeerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Peer {peer_id} not found",
        )


@router.get(
    "",
    response_model=PeerListResponse,
)
def list_peers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_inactive: bool = Query(False),
    search: str | None = Query(None, min_length=1, max_length=255),
    service: PeerService = Depends(_get_peer_service),
):
    """Liste les peers du tenant avec pagination et recherche."""
    if search:
        result = service.search_peers(
            search_term=search, page=page, page_size=page_size
        )
    else:
        result = service.list_peers(
            page=page, page_size=page_size, include_inactive=include_inactive
        )

    return PeerListResponse(
        items=[PeerResponse.model_validate(p) for p in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next=result.has_next,
        has_prev=result.has_prev,
    )


@router.patch(
    "/{peer_id}",
    response_model=PeerResponse,
)
def update_peer(
    peer_id: uuid.UUID,
    body: PeerUpdate,
    db: Session = Depends(get_db),
    service: PeerService = Depends(_get_peer_service),
):
    """Met à jour les métadonnées d'un peer."""
    try:
        peer = service.update_peer(
            peer_id=peer_id,
            name=body.name,
            description=body.description,
            allowed_ips=body.allowed_ips,
            dns=body.dns,
            persistent_keepalive=body.persistent_keepalive,
            expires_at=body.expires_at,
        )
        db.commit()
        return peer
    except PeerNotFoundError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Peer {peer_id} not found",
        )


@router.delete(
    "/{peer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_peer(
    peer_id: uuid.UUID,
    db: Session = Depends(get_db),
    service: PeerService = Depends(_get_peer_service),
):
    """Supprime un peer (soft delete)."""
    try:
        service.delete_peer(peer_id)
        db.commit()
    except PeerNotFoundError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Peer {peer_id} not found",
        )


# ------------------------------------------------------------------
# ACTIONS
# ------------------------------------------------------------------


@router.post(
    "/{peer_id}/rotate",
    response_model=PeerResponse,
)
def rotate_keys(
    peer_id: uuid.UUID,
    db: Session = Depends(get_db),
    service: PeerService = Depends(_get_peer_service),
):
    """Rotation des clés d'un peer."""
    try:
        peer = service.rotate_keys(peer_id)
        db.commit()
        return peer
    except PeerNotFoundError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Peer {peer_id} not found",
        )


@router.post(
    "/{peer_id}/enable",
    response_model=PeerResponse,
)
def enable_peer(
    peer_id: uuid.UUID,
    db: Session = Depends(get_db),
    service: PeerService = Depends(_get_peer_service),
):
    """Active un peer (l'ajoute au backend WG)."""
    try:
        peer = service.enable_peer(peer_id)
        db.commit()
        return peer
    except PeerNotFoundError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Peer {peer_id} not found",
        )


@router.post(
    "/{peer_id}/disable",
    response_model=PeerResponse,
)
def disable_peer(
    peer_id: uuid.UUID,
    db: Session = Depends(get_db),
    service: PeerService = Depends(_get_peer_service),
):
    """Désactive un peer (le retire du backend WG)."""
    try:
        peer = service.disable_peer(peer_id)
        db.commit()
        return peer
    except PeerNotFoundError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Peer {peer_id} not found",
        )
