"""Endpoints de gestion des sessions utilisateur."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from app.core.deps import get_current_user
from app.models.user import User
from app.services.session import session_service
from app.schemas.session import (
    SessionResponse,
    SessionListResponse,
    SessionRevokeResponse,
    SessionRevokeAllResponse,
)
from app.constants import ErrorMessages

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("", response_model=SessionListResponse, status_code=status.HTTP_200_OK)
def list_sessions(
    current_user: User = Depends(get_current_user),
) -> SessionListResponse:
    """Liste toutes les sessions actives de l'utilisateur connecte.

    Returns:
        SessionListResponse avec la liste des sessions et leur nombre

    Security:
        - Requiert authentification JWT
        - Retourne uniquement les sessions du user connecte (isolation)
    """
    sessions = session_service.list_sessions(current_user.id)

    session_responses = [
        SessionResponse(
            session_id=s.get("session_id", ""),
            ip_address=s.get("ip_address", "unknown"),
            user_agent=s.get("user_agent", "unknown"),
            created_at=s.get("created_at", ""),
            last_activity=s.get("last_activity", ""),
        )
        for s in sessions
    ]

    return SessionListResponse(
        sessions=session_responses,
        count=len(session_responses),
    )


@router.delete(
    "/{session_id}",
    response_model=SessionRevokeResponse,
    status_code=status.HTTP_200_OK,
)
def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
) -> SessionRevokeResponse:
    """Revoque une session specifique et ses tokens associes.

    Args:
        session_id: ID de la session a revoquer

    Returns:
        SessionRevokeResponse avec confirmation

    Raises:
        HTTPException 404: Si session non trouvee ou n'appartient pas au user

    Security:
        - Requiert authentification JWT
        - Verifie que la session appartient au user connecte
        - Revoque la famille de tokens associee (force re-login sur ce device)
    """
    success = session_service.revoke_session(session_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.SESSION_NOT_FOUND,
        )

    return SessionRevokeResponse(
        message="Session revoked",
        session_id=session_id,
    )


@router.delete("", response_model=SessionRevokeAllResponse, status_code=status.HTTP_200_OK)
def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
) -> SessionRevokeAllResponse:
    """Revoque toutes les sessions de l'utilisateur (force re-login partout).

    Returns:
        SessionRevokeAllResponse avec le nombre de sessions revoquees

    Security:
        - Requiert authentification JWT
        - Revoque toutes les familles de tokens associees
        - L'utilisateur devra se reconnecter sur tous ses appareils
    """
    count = session_service.revoke_all_sessions(current_user.id)

    return SessionRevokeAllResponse(
        message="All sessions revoked",
        count=count,
    )
