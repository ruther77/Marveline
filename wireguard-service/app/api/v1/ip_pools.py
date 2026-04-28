"""Endpoints CRUD pour les pools IP WireGuard."""

import ipaddress
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import InternalAuth, get_db, get_internal_auth
from app.repositories.ip_pool import IpPoolRepository
from app.schemas.ip_pool import IpPoolCreate, IpPoolListResponse, IpPoolResponse
from app.services.ip_allocator import IpAllocatorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ip-pools", tags=["ip-pools"])


def _get_ip_pool_repo(
    db: Session = Depends(get_db),
    auth: InternalAuth = Depends(get_internal_auth),
) -> IpPoolRepository:
    """Construit le IpPoolRepository avec les dependances injectees."""
    return IpPoolRepository(db, auth.tenant_id)


def _get_ip_allocator(
    db: Session = Depends(get_db),
    auth: InternalAuth = Depends(get_internal_auth),
) -> IpAllocatorService:
    """Construit le IpAllocatorService."""
    return IpAllocatorService(db, auth.tenant_id)


@router.get(
    "",
    response_model=IpPoolListResponse,
)
def list_ip_pools(
    repo: IpPoolRepository = Depends(_get_ip_pool_repo),
):
    """Liste les pools IP du tenant."""
    pools = repo.list_all()
    return IpPoolListResponse(
        items=[IpPoolResponse.model_validate(p) for p in pools],
        total=len(pools),
    )


@router.post(
    "",
    response_model=IpPoolResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ip_pool(
    body: IpPoolCreate,
    db: Session = Depends(get_db),
    auth: InternalAuth = Depends(get_internal_auth),
):
    """Cree un nouveau pool IP pour le tenant."""
    # Valider le subnet
    try:
        network = ipaddress.IPv4Network(body.subnet, strict=False)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid subnet: {exc}",
        )

    # Valider le gateway
    try:
        gateway = ipaddress.IPv4Address(body.gateway_ip)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid gateway IP: {exc}",
        )

    if gateway not in network:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gateway IP must be within the subnet",
        )

    repo = IpPoolRepository(db, auth.tenant_id)

    # Verifier duplicat
    existing = repo.get_by_subnet(body.subnet)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"IP pool {body.subnet} already exists for this tenant",
        )

    # Calculer le premier IP client (gateway + 1)
    first_client_ip = gateway + 1
    if first_client_ip >= network.broadcast_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subnet too small: no client IPs available",
        )

    pool = repo.create(
        {
            "subnet": str(network),
            "gateway_ip": str(gateway),
            "next_ip": str(first_client_ip),
            "subnet_mask": network.prefixlen,
            "description": body.description,
        }
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to create IP pool")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    return pool
