"""Endpoints de gestion des sessions utilisateur."""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.errors import ErrorMessages
from app.core.database import get_async_db
from app.core.deps import get_current_user_async, require_stepup, SessionReader, SessionRevoker, UserCompat
from app.core.security import decode_token
from app.models.account import Account
from app.models.account_session import AccountSession
from app.models.tenant_membership import TenantMembership
from app.services.audit import AuditService
from app.services.session import session_service
from app.schemas.session import (
    SessionResponse,
    SessionListResponse,
    SessionRevokeResponse,
    SessionRevokeAllResponse,
)
from app.constants import ErrorMessages

# Niveaux RBAC pour l'anti-escalade (§6.13)
_ROLE_LEVELS: dict[str, int] = {
    "super_admin": 0, "platform_ops": 1,
    "tenant_admin": 2, "manager": 3, "staff": 4, "viewer": 5,
}


def _can_revoke(executor_role: Optional[str], target_role: Optional[str]) -> bool:
    """True si l'executor peut révoquer une session du user cible (§6.13 anti-escalade).

    Un executor ne peut révoquer que des sessions d'users de niveau INFÉRIEUR.
    ApiKeyClient (role=None) est traité comme autorisé (pas de hiérarchie).
    """
    if executor_role is None:
        return True
    exec_level = _ROLE_LEVELS.get(executor_role, 99)
    target_level = _ROLE_LEVELS.get(target_role or "viewer", 99)
    return exec_level < target_level

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/sessions", tags=["Sessions"])


def _get_current_session_id(request: Request) -> Optional[str]:
    """Extrait le session_id (claim 'sid') du bearer token courant.

    Utilisé pour marquer la session courante dans la liste des sessions.

    Returns:
        session_id string ou None si introuvable
    """
    try:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[len("Bearer "):]
        payload = decode_token(token)
        return payload.get("sid")
    except Exception:
        return None


@router.get("", response_model=SessionListResponse, status_code=status.HTTP_200_OK)
async def list_sessions(
    request: Request,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> SessionListResponse:
    """Liste toutes les sessions actives de l'utilisateur connecté.

    Returns:
        SessionListResponse avec la liste des sessions et leur nombre

    Security:
        - Requiert authentification JWT
        - Retourne uniquement les sessions du user connecté (isolation)
        - La session courante est marquée is_current=True
    """
    sessions = await session_service.list_sessions(db, current_user.id)
    current_session_id = _get_current_session_id(request)

    session_responses = [
        SessionResponse(
            session_id=sess.session_id,
            device_id=sess.device_id,
            ip_address=sess.ip_address,
            user_agent=sess.user_agent or "unknown",
            created_at=sess.created_at.isoformat(),
            last_activity=sess.last_active_at.isoformat(),
            is_current=bool(current_session_id and sess.session_id == current_session_id),
        )
        for sess in sessions
    ]

    return SessionListResponse(
        sessions=session_responses,
        total=len(session_responses),
        active_count=len(session_responses),
    )


@router.delete(
    "/{session_id}",
    response_model=SessionRevokeResponse,
    status_code=status.HTTP_200_OK,
)
async def revoke_session(
    session_id: str,
    request: Request,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> SessionRevokeResponse:
    """Révoque une session spécifique et ses tokens associés.

    Args:
        session_id: ID de la session à révoquer
        request: Requête HTTP (pour extraire le sid du token courant)

    Returns:
        SessionRevokeResponse avec confirmation

    Raises:
        HTTPException 400: Si tentative de révoquer la session courante (spec §06 §6.12)
        HTTPException 404: Si session non trouvée ou n'appartient pas au user

    Security:
        - Requiert authentification JWT
        - Vérifie que la session appartient au user connecté
        - Interdit la révocation de la session courante (utiliser /auth/logout)
        - Révoque la whitelist refresh Redis pour cette session
    """
    # spec §06 §6.12 — protection session courante
    current_sid = _get_current_session_id(request)
    if current_sid and session_id == current_sid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "CANNOT_REVOKE_CURRENT_SESSION",
                "message": "Use POST /auth/logout to end the current session",
            },
        )

    success = await session_service.revoke_session(db, session_id, current_user.id)
    await db.commit()

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
async def revoke_all_sessions(
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> SessionRevokeAllResponse:
    """Révoque toutes les sessions de l'utilisateur (y compris la session courante).

    Returns:
        SessionRevokeAllResponse avec le nombre de sessions révoquées

    Security:
        - Requiert authentification JWT
        - Révoque toutes les whitelists Redis via user_sessions_index
        - L'utilisateur devra se reconnecter sur tous ses appareils
    """
    count = await session_service.revoke_all_sessions(db, current_user.id)
    await db.commit()

    return SessionRevokeAllResponse(
        message="All sessions revoked",
        count=count,
    )


# ── Admin session endpoints (§6.10 S-12.2) ──────────────────────────────────

admin_router = APIRouter(prefix="/admin/tenants", tags=["Sessions Admin"])


def _make_session_response(sess: AccountSession) -> SessionResponse:
    return SessionResponse(
        session_id=sess.session_id,
        device_id=sess.device_id,
        ip_address=sess.ip_address or "unknown",
        user_agent=sess.user_agent or "unknown",
        created_at=sess.created_at.isoformat(),
        last_activity=sess.last_active_at.isoformat(),
        is_current=False,
    )


@admin_router.get("/{tenant_id}/sessions", response_model=SessionListResponse)
async def admin_list_tenant_sessions(
    tenant_id: int,
    principal: SessionReader,
    db: AsyncSession = Depends(get_async_db),
) -> SessionListResponse:
    """Liste les sessions actives de tous les users d'un tenant (sessions:read §6.10)."""
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ErrorMessages.TENANT_MISMATCH)

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(AccountSession, Account.email)
        .join(Account, AccountSession.account_id == Account.id)
        .where(
            AccountSession.tenant_id == tenant_id,
            AccountSession.revoked_at.is_(None),
            AccountSession.expires_at > now,
        )
        .order_by(AccountSession.created_at.desc())
    )
    rows = result.all()
    items = [
        SessionResponse(
            session_id=sess.session_id,
            account_id=sess.account_id,
            email=email,
            device_id=sess.device_id,
            ip_address=sess.ip_address or "unknown",
            user_agent=sess.user_agent or "unknown",
            created_at=sess.created_at.isoformat(),
            last_activity=sess.last_active_at.isoformat(),
            is_current=False,
        )
        for sess, email in rows
    ]
    return SessionListResponse(sessions=items, total=len(items), active_count=len(items))


@admin_router.get("/{tenant_id}/users/{user_id}/sessions", response_model=SessionListResponse)
async def admin_list_user_sessions(
    tenant_id: int,
    user_id: int,
    principal: SessionReader,
    db: AsyncSession = Depends(get_async_db),
) -> SessionListResponse:
    """Liste les sessions actives d'un user spécifique du tenant (sessions:read §6.10)."""
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ErrorMessages.TENANT_MISMATCH)

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(AccountSession)
        .where(
            AccountSession.tenant_id == tenant_id,
            AccountSession.account_id == user_id,
            AccountSession.revoked_at.is_(None),
            AccountSession.expires_at > now,
        )
        .order_by(AccountSession.created_at.desc())
    )
    sessions = result.scalars().all()
    items = [_make_session_response(s) for s in sessions]
    return SessionListResponse(sessions=items, total=len(items), active_count=len(items))


@admin_router.delete("/{tenant_id}/sessions/{session_id}", response_model=SessionRevokeResponse)
async def admin_revoke_session(
    tenant_id: int,
    session_id: str,
    request: Request,
    principal: SessionRevoker,
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_stepup),
    reason: Optional[str] = Body(default=None),
) -> SessionRevokeResponse:
    """Révoque une session d'un user du tenant (sessions:revoke + step-up + anti-escalade §6.13)."""
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ErrorMessages.TENANT_MISMATCH)

    # Récupérer session + rôle du user cible pour anti-escalade (IAM v2 — TenantMembership)
    row = (await db.execute(
        select(AccountSession, TenantMembership.role_name.label("target_role"))
        .outerjoin(
            TenantMembership,
            (TenantMembership.account_id == AccountSession.account_id)
            & (TenantMembership.tenant_id == tenant_id)
            & (TenantMembership.revoked_at.is_(None)),
        )
        .where(
            AccountSession.session_id == session_id,
            AccountSession.tenant_id == tenant_id,
            AccountSession.revoked_at.is_(None),
        )
    )).first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorMessages.SESSION_NOT_FOUND)

    db_session, target_role = row
    executor_role = getattr(principal, "role", None)
    if not _can_revoke(executor_role, target_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "CANNOT_REVOKE_HIGHER_ROLE"},
        )

    await session_service.revoke_session(db, session_id, db_session.account_id, reason=reason or "admin_revoke")

    audit = AuditService(db)
    await audit.log_action(
        action="ADMIN_SESSION_REVOKED",
        tenant_id=tenant_id,
        user_id=getattr(principal, "id", None) or int(principal.principal_id),
        entity_type="Session",
        entity_id=db_session.account_id,
        description=f"Admin revoked session {session_id[:8]}… reason={reason or 'none'}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    return SessionRevokeResponse(message="Session revoked", session_id=session_id)


@admin_router.delete("/{tenant_id}/users/{user_id}/sessions", response_model=SessionRevokeAllResponse)
async def admin_revoke_user_sessions(
    tenant_id: int,
    user_id: int,
    request: Request,
    principal: SessionRevoker,
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_stepup),
    reason: Optional[str] = Body(default=None),
) -> SessionRevokeAllResponse:
    """Révoque toutes les sessions d'un user du tenant (sessions:revoke + step-up + anti-escalade §6.10)."""
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ErrorMessages.TENANT_MISMATCH)

    target_role = (await db.execute(
        select(TenantMembership.role_name).where(
            TenantMembership.account_id == user_id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.revoked_at.is_(None),
            TenantMembership.status == "active",
        )
    )).scalar()

    if target_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorMessages.USER_NOT_FOUND)

    executor_role = getattr(principal, "role", None)
    if not _can_revoke(executor_role, target_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "CANNOT_REVOKE_HIGHER_ROLE"},
        )

    count = await session_service.revoke_all_sessions(db, user_id, reason=reason or "admin_revoke")

    audit = AuditService(db)
    await audit.log_action(
        action="ADMIN_USER_SESSIONS_REVOKED",
        tenant_id=tenant_id,
        user_id=getattr(principal, "id", None) or int(principal.principal_id),
        entity_type="User",
        entity_id=user_id,
        description=f"Admin revoked all sessions for user {user_id} reason={reason or 'none'}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    return SessionRevokeAllResponse(message="All user sessions revoked", count=count)
