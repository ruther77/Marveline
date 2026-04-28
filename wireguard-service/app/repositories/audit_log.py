"""Repository pour les logs d'audit WireGuard (append-only)."""

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.models.audit_log import WgAuditLog
from app.repositories.base import (
    DEFAULT_PAGE_SIZE,
    PaginatedResult,
    RepositoryException,
    TenantAwareBaseRepository,
)

logger = logging.getLogger(__name__)


class AuditLogRepository(TenantAwareBaseRepository[WgAuditLog]):
    """Repository append-only pour les logs d'audit WireGuard.

    Seules les opérations de lecture et d'ajout sont autorisées.
    La modification et la suppression sont interdites.
    """

    model = WgAuditLog

    def log_action(
        self,
        action: str,
        peer_id: Optional[uuid.UUID] = None,
        actor_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> WgAuditLog:
        """Ajoute une entrée d'audit."""
        entry = WgAuditLog(
            tenant_id=self._tenant_id,
            peer_id=str(peer_id) if peer_id else None,
            action=action,
            actor_id=actor_id,
            details=details,
            ip_address=ip_address,
        )
        self.session.add(entry)
        self.session.flush()
        return entry

    def list_by_peer(
        self,
        peer_id: uuid.UUID,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedResult[WgAuditLog]:
        """Liste les entrées d'audit pour un peer donné."""
        query = self._tenant_query().where(
            WgAuditLog.peer_id == str(peer_id)
        ).order_by(WgAuditLog.created_at.desc())
        return self.paginate(page=page, page_size=page_size, query=query)

    def list_by_action(
        self,
        action: str,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedResult[WgAuditLog]:
        """Liste les entrées d'audit pour une action donnée."""
        query = self._tenant_query().where(
            WgAuditLog.action == action
        ).order_by(WgAuditLog.created_at.desc())
        return self.paginate(page=page, page_size=page_size, query=query)

    def list_recent(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedResult[WgAuditLog]:
        """Liste les entrées d'audit récentes du tenant."""
        query = self._tenant_query().order_by(
            WgAuditLog.created_at.desc()
        )
        return self.paginate(page=page, page_size=page_size, query=query)

    def update(self, id, data) -> None:
        """Interdit — les logs d'audit sont immutables."""
        raise RepositoryException("Audit logs are immutable: update forbidden")

    def soft_delete(self, id) -> bool:
        """Interdit — les logs d'audit ne peuvent pas être supprimés."""
        raise RepositoryException("Audit logs are immutable: delete forbidden")
