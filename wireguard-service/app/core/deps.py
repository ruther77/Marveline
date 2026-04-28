"""Dependency injection pour le microservice WireGuard.

Fournit les dépendances FastAPI :
- get_db() : session SQLAlchemy
- get_internal_auth() : validation API key + extraction tenant_id/actor_id
"""

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from app.core.database import SessionLocal
from app.core.security import verify_internal_api_key

logger = logging.getLogger(__name__)


@dataclass
class InternalAuth:
    """Contexte d'authentification inter-service."""

    tenant_id: int
    actor_id: Optional[int] = None


def get_db():
    """Dependency injection pour obtenir une session DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_internal_auth(
    x_internal_api_key: str = Header(..., alias="X-Internal-API-Key"),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_actor_id: Optional[str] = Header(None, alias="X-Actor-ID"),
) -> InternalAuth:
    """Valide l'API key interne et extrait le contexte tenant/actor.

    Headers requis :
    - X-Internal-API-Key : clé API inter-service
    - X-Tenant-ID : ID du tenant (obligatoire)
    - X-Actor-ID : ID de l'utilisateur (optionnel)

    Raises:
        HTTPException 401 : API key invalide
        HTTPException 400 : tenant_id invalide
    """
    if not verify_internal_api_key(x_internal_api_key):
        logger.warning("Rejected internal API call: invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )

    try:
        tenant_id = int(x_tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID must be a valid integer",
        )

    if tenant_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID must be positive",
        )

    actor_id = None
    if x_actor_id:
        try:
            actor_id = int(x_actor_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Actor-ID must be a valid integer",
            )

    return InternalAuth(tenant_id=tenant_id, actor_id=actor_id)
