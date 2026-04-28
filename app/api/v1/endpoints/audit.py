"""Endpoints pour consultation des audit logs (admin uniquement)."""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, desc, and_, func, literal, DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogResponse
from app.schemas.common import PaginatedResponse, PaginationParams


router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=PaginatedResponse[AuditLogResponse])
async def list_audit_logs(
    current_user: UserCompat = Depends(require_scope(Scope.AUDIT_READ)),
    pagination: PaginationParams = Depends(),
    start_date: Optional[datetime] = Query(None, description="Date début (inclusive)"),
    end_date: Optional[datetime] = Query(None, description="Date fin (inclusive)"),
    user_id: Optional[int] = Query(None, description="Filtrer par ID utilisateur"),
    action: Optional[str] = Query(None, description="Filtrer par type d'action (CREATE, UPDATE, DELETE, etc.)"),
    entity_type: Optional[str] = Query(None, description="Filtrer par type d'entité (Customer, Reservation, etc.)"),
    entity_id: Optional[int] = Query(None, description="Filtrer par ID entité spécifique"),
    db: AsyncSession = Depends(get_async_db),
) -> PaginatedResponse[AuditLogResponse]:
    """Liste tous les audit logs avec filtres (admin uniquement).

    Args:
        skip: Offset pagination
        limit: Limite pagination (max 1000)
        start_date: Filtrer logs après cette date (inclusive)
        end_date: Filtrer logs avant cette date (inclusive)
        user_id: Filtrer par utilisateur ayant effectué l'action
        action: Filtrer par type d'action (CREATE, UPDATE, DELETE, SOFT_DELETE,
               READ_SENSITIVE, LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT)
        entity_type: Filtrer par type d'entité (Customer, Reservation, Invoice, etc.)
        entity_id: Filtrer par ID entité spécifique
        db: Session de base de données
        current_user: Utilisateur admin authentifié

    Returns:
        Liste paginée d'audit logs avec total

    Example:
        GET /api/v1/audit?skip=0&limit=50&action=UPDATE&start_date=2026-02-01T00:00:00Z

    Security:
        - Authentification JWT requise
        - Rôle admin obligatoire
        - Filtrage automatique par tenant_id (isolation multi-tenant)

    Compliance:
        - RGPD Article 30: Registre des activités de traitement
        - SOC 2: Audit trail complet
        - ISO 27001: Traçabilité accès données
    """
    filters = [AuditLog.tenant_id == current_user.tenant_id]

    if start_date:
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        filters.append(AuditLog.created_at >= literal(start_date, DateTime(timezone=True)))
    if end_date:
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        filters.append(AuditLog.created_at <= literal(end_date, DateTime(timezone=True)))
    if user_id is not None:
        filters.append(AuditLog.account_id == user_id)
    if action:
        filters.append(AuditLog.action == action.upper())
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        filters.append(AuditLog.entity_id == entity_id)

    total = (await db.scalar(
        select(func.count(AuditLog.id)).where(*filters)
    )) or 0

    logs = (await db.execute(
        select(AuditLog).where(*filters)
        .order_by(desc(AuditLog.created_at))
        .offset(pagination.skip)
        .limit(pagination.limit)
    )).scalars().all()

    return PaginatedResponse[AuditLogResponse](
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/user/{user_id}", response_model=PaginatedResponse[AuditLogResponse])
async def get_user_audit_trail(
    user_id: int,
    current_user: UserCompat = Depends(require_scope(Scope.AUDIT_READ)),
    pagination: PaginationParams = Depends(),
    start_date: Optional[datetime] = Query(None, description="Date début (inclusive)"),
    end_date: Optional[datetime] = Query(None, description="Date fin (inclusive)"),
    action: Optional[str] = Query(None, description="Filtrer par type d'action"),
    db: AsyncSession = Depends(get_async_db),
) -> PaginatedResponse[AuditLogResponse]:
    """Récupère l'audit trail complet d'un utilisateur (admin uniquement).

    Args:
        user_id: ID de l'utilisateur dont on veut l'audit trail
        skip: Offset pagination
        limit: Limite pagination (max 1000)
        start_date: Filtrer logs après cette date (inclusive)
        end_date: Filtrer logs avant cette date (inclusive)
        action: Filtrer par type d'action
        db: Session de base de données
        current_user: Utilisateur admin authentifié

    Returns:
        Liste paginée d'audit logs pour cet utilisateur avec total

    Use Cases:
        - Investigation sécurité: tracer actions d'un utilisateur suspect
        - Conformité RGPD: exporter historique complet d'un utilisateur
        - Forensics: reconstruire timeline d'actions lors incident
        - Audit interne: vérifier activité d'un utilisateur

    Security:
        - Authentification JWT requise
        - Rôle admin obligatoire
        - Filtrage automatique par tenant_id (isolation multi-tenant)
    """
    filters = [
        AuditLog.account_id == user_id,
        AuditLog.tenant_id == current_user.tenant_id,
    ]

    if start_date:
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        filters.append(AuditLog.created_at >= literal(start_date, DateTime(timezone=True)))
    if end_date:
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        filters.append(AuditLog.created_at <= literal(end_date, DateTime(timezone=True)))
    if action:
        filters.append(AuditLog.action == action.upper())

    total = (await db.scalar(
        select(func.count(AuditLog.id)).where(*filters)
    )) or 0

    logs = (await db.execute(
        select(AuditLog).where(*filters)
        .order_by(desc(AuditLog.created_at))
        .offset(pagination.skip)
        .limit(pagination.limit)
    )).scalars().all()

    return PaginatedResponse[AuditLogResponse](
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/entity/{entity_type}/{entity_id}", response_model=PaginatedResponse[AuditLogResponse])
async def get_entity_audit_trail(
    entity_type: str,
    entity_id: int,
    current_user: UserCompat = Depends(require_scope(Scope.AUDIT_READ)),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
) -> PaginatedResponse[AuditLogResponse]:
    """Récupère l'historique complet d'une entité (admin uniquement).

    Args:
        entity_type: Type d'entité (Customer, Reservation, Invoice, etc.)
        entity_id: ID de l'entité
        skip: Offset pagination
        limit: Limite pagination (max 1000)
        db: Session de base de données
        current_user: Utilisateur admin authentifié

    Returns:
        Liste paginée d'audit logs pour cette entité avec total

    Use Cases:
        - Reconstruire historique modifications d'une réservation
        - Identifier qui a modifié une facture et quand
        - Forensics: analyser changements suspect sur entité
        - Audit: vérifier timeline complète entité

    Security:
        - Authentification JWT requise
        - Rôle admin obligatoire
        - Filtrage automatique par tenant_id (isolation multi-tenant)
    """
    filters = [
        AuditLog.entity_type == entity_type,
        AuditLog.entity_id == entity_id,
        AuditLog.tenant_id == current_user.tenant_id,
    ]

    total = (await db.scalar(
        select(func.count(AuditLog.id)).where(*filters)
    )) or 0

    logs = (await db.execute(
        select(AuditLog).where(*filters)
        .order_by(desc(AuditLog.created_at))
        .offset(pagination.skip)
        .limit(pagination.limit)
    )).scalars().all()

    return PaginatedResponse[AuditLogResponse](
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )
