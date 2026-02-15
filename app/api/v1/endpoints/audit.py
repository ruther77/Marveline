"""Endpoints pour consultation des audit logs (admin uniquement)."""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from app.core.database import get_db
from app.core.deps import require_permission
from app.core.permissions import Permission
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogResponse, AuditLogList


router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=AuditLogList)
def list_audit_logs(
    current_user: User = Depends(require_permission(Permission.AUDIT_READ)),
    skip: int = Query(0, ge=0, description="Offset pagination"),
    limit: int = Query(100, ge=1, le=1000, description="Limite pagination (max 1000)"),
    start_date: Optional[datetime] = Query(None, description="Date début (inclusive)"),
    end_date: Optional[datetime] = Query(None, description="Date fin (inclusive)"),
    user_id: Optional[int] = Query(None, description="Filtrer par ID utilisateur"),
    action: Optional[str] = Query(None, description="Filtrer par type d'action (CREATE, UPDATE, DELETE, etc.)"),
    entity_type: Optional[str] = Query(None, description="Filtrer par type d'entité (Customer, Reservation, etc.)"),
    entity_id: Optional[int] = Query(None, description="Filtrer par ID entité spécifique"),
    db: Session = Depends(get_db),
) -> AuditLogList:
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

        Response:
        {
            "logs": [
                {
                    "id": 123,
                    "user_id": 42,
                    "tenant_id": 1,
                    "action": "UPDATE",
                    "entity_type": "Reservation",
                    "entity_id": 456,
                    "changes": {
                        "status": {"before": "draft", "after": "confirmed"}
                    },
                    "description": "Updated Reservation #456: status",
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0...",
                    "request_id": "550e8400-e29b-41d4-a716-446655440000",
                    "created_at": "2026-02-12T14:30:00Z"
                }
            ],
            "total": 150,
            "skip": 0,
            "limit": 50
        }

    Security:
        - Authentification JWT requise
        - Rôle admin obligatoire
        - Filtrage automatique par tenant_id (isolation multi-tenant)

    Compliance:
        - RGPD Article 30: Registre des activités de traitement
        - SOC 2: Audit trail complet
        - ISO 27001: Traçabilité accès données
    """
    # Construction query avec filtres
    query = db.query(AuditLog).filter(
        AuditLog.tenant_id == current_user.tenant_id
    )

    # Filtres temporels
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)

    # Filtres attributs
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action.upper())
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(AuditLog.entity_id == entity_id)

    # Compte total
    total = query.count()

    # Pagination + ordre décroissant (plus récent en premier)
    logs = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit).all()

    return AuditLogList(
        logs=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/user/{user_id}", response_model=AuditLogList)
def get_user_audit_trail(
    user_id: int,
    current_user: User = Depends(require_permission(Permission.AUDIT_READ)),
    skip: int = Query(0, ge=0, description="Offset pagination"),
    limit: int = Query(100, ge=1, le=1000, description="Limite pagination (max 1000)"),
    start_date: Optional[datetime] = Query(None, description="Date début (inclusive)"),
    end_date: Optional[datetime] = Query(None, description="Date fin (inclusive)"),
    action: Optional[str] = Query(None, description="Filtrer par type d'action"),
    db: Session = Depends(get_db),
) -> AuditLogList:
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

    Example:
        GET /api/v1/audit/user/42?skip=0&limit=100&start_date=2026-02-01T00:00:00Z

        Response:
        {
            "logs": [
                {
                    "id": 125,
                    "user_id": 42,
                    "tenant_id": 1,
                    "action": "CREATE",
                    "entity_type": "Customer",
                    "entity_id": 789,
                    "changes": {
                        "after": {"email": "new@example.com", ...}
                    },
                    "description": "Created Customer #789",
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0...",
                    "request_id": "550e8400-e29b-41d4-a716-446655440001",
                    "created_at": "2026-02-12T15:00:00Z"
                }
            ],
            "total": 87,
            "skip": 0,
            "limit": 100
        }

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
    # Construction query avec filtres
    query = db.query(AuditLog).filter(
        and_(
            AuditLog.user_id == user_id,
            AuditLog.tenant_id == current_user.tenant_id
        )
    )

    # Filtres temporels
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)

    # Filtre action
    if action:
        query = query.filter(AuditLog.action == action.upper())

    # Compte total
    total = query.count()

    # Pagination + ordre décroissant
    logs = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit).all()

    return AuditLogList(
        logs=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/entity/{entity_type}/{entity_id}", response_model=AuditLogList)
def get_entity_audit_trail(
    entity_type: str,
    entity_id: int,
    current_user: User = Depends(require_permission(Permission.AUDIT_READ)),
    skip: int = Query(0, ge=0, description="Offset pagination"),
    limit: int = Query(100, ge=1, le=1000, description="Limite pagination (max 1000)"),
    db: Session = Depends(get_db),
) -> AuditLogList:
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

    Example:
        GET /api/v1/audit/entity/Reservation/456?skip=0&limit=50

        Response:
        {
            "logs": [
                {
                    "id": 123,
                    "user_id": 42,
                    "tenant_id": 1,
                    "action": "UPDATE",
                    "entity_type": "Reservation",
                    "entity_id": 456,
                    "changes": {
                        "status": {"before": "draft", "after": "confirmed"}
                    },
                    "description": "Updated Reservation #456: status",
                    "created_at": "2026-02-12T14:30:00Z"
                },
                {
                    "id": 100,
                    "user_id": 42,
                    "tenant_id": 1,
                    "action": "CREATE",
                    "entity_type": "Reservation",
                    "entity_id": 456,
                    "changes": {
                        "after": {"status": "draft", "total_amount": 10000}
                    },
                    "description": "Created Reservation #456",
                    "created_at": "2026-02-10T10:00:00Z"
                }
            ],
            "total": 5,
            "skip": 0,
            "limit": 50
        }

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
    # Construction query
    query = db.query(AuditLog).filter(
        and_(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
            AuditLog.tenant_id == current_user.tenant_id
        )
    )

    # Compte total
    total = query.count()

    # Pagination + ordre décroissant
    logs = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit).all()

    return AuditLogList(
        logs=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        skip=skip,
        limit=limit
    )
