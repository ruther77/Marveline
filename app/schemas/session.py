"""Schemas Pydantic pour la gestion des sessions utilisateur."""
from typing import Optional
from pydantic import Field
from app.schemas.base import BaseSchema


class SessionResponse(BaseSchema):
    """Schema pour une session active.

    Example:
        {
            "session_id": "a1b2c3d4-...",
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0 ...",
            "created_at": "2026-02-13T10:00:00+00:00",
            "last_activity": "2026-02-13T14:30:00+00:00"
        }
    """

    session_id: str = Field(
        ...,
        description="Identifiant unique de la session"
    )

    ip_address: str = Field(
        ...,
        description="Adresse IP du client lors de la creation de la session"
    )

    user_agent: str = Field(
        ...,
        description="User-Agent du navigateur/client"
    )

    created_at: str = Field(
        ...,
        description="Date de creation de la session (ISO 8601)"
    )

    last_activity: str = Field(
        ...,
        description="Date de derniere activite (ISO 8601)"
    )


class SessionListResponse(BaseSchema):
    """Schema pour la liste des sessions actives.

    Example:
        {
            "sessions": [...],
            "total": 3,
            "active_count": 3
        }
    """

    sessions: list[SessionResponse] = Field(
        default_factory=list,
        description="Liste des sessions actives"
    )

    total: int = Field(
        ...,
        ge=0,
        description="Nombre total de sessions"
    )

    active_count: int = Field(
        ...,
        ge=0,
        description="Nombre de sessions actives"
    )


class SessionRevokeResponse(BaseSchema):
    """Schema pour la reponse de revocation de session.

    Example:
        {
            "message": "Session revoked",
            "session_id": "a1b2c3d4-..."
        }
    """

    message: str = Field(
        ...,
        description="Message de confirmation"
    )

    session_id: Optional[str] = Field(
        default=None,
        description="ID de la session revoquee (si applicable)"
    )


class SessionRevokeAllResponse(BaseSchema):
    """Schema pour la reponse de revocation de toutes les sessions.

    Example:
        {
            "message": "All sessions revoked",
            "count": 3
        }
    """

    message: str = Field(
        ...,
        description="Message de confirmation"
    )

    count: int = Field(
        ...,
        ge=0,
        description="Nombre de sessions revoquees"
    )
