"""Repository pour les peers WireGuard."""

import logging
from typing import List, Optional

from sqlalchemy import func, or_, select

from app.models.peer import WgPeer
from app.repositories.base import (
    DEFAULT_PAGE_SIZE,
    PaginatedResult,
    TenantAwareBaseRepository,
)

logger = logging.getLogger(__name__)


class PeerRepository(TenantAwareBaseRepository[WgPeer]):
    """Repository pour les opérations CRUD sur les peers WireGuard."""

    model = WgPeer

    def get_by_public_key(self, public_key: str) -> Optional[WgPeer]:
        """Récupère un peer par sa clé publique dans le tenant."""
        stmt = self._tenant_query().where(WgPeer.public_key == public_key)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_assigned_ip(self, assigned_ip: str) -> Optional[WgPeer]:
        """Récupère un peer par son IP assignée dans le tenant."""
        stmt = self._tenant_query().where(WgPeer.assigned_ip == assigned_ip)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_active(
        self, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
    ) -> PaginatedResult[WgPeer]:
        """Liste les peers actifs et activés du tenant."""
        query = self._tenant_query().where(
            WgPeer.is_active == True,
            WgPeer.is_enabled == True,
        )
        return self.paginate(page=page, page_size=page_size, query=query)

    def list_expired(self) -> List[WgPeer]:
        """Liste les peers expirés (actifs mais date dépassée)."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        stmt = self._tenant_query().where(
            WgPeer.is_active == True,
            WgPeer.expires_at.isnot(None),
            WgPeer.expires_at < now,
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_by_type(
        self,
        peer_type: str,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedResult[WgPeer]:
        """Liste les peers d'un type donné dans le tenant."""
        query = self._tenant_query().where(
            WgPeer.is_active == True,
            WgPeer.peer_type == peer_type,
        )
        return self.paginate(page=page, page_size=page_size, query=query)

    def list_all_paginated(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        include_inactive: bool = False,
    ) -> PaginatedResult[WgPeer]:
        """Liste tous les peers du tenant, avec option d'inclure les inactifs."""
        query = self._tenant_query()
        if not include_inactive:
            query = query.where(WgPeer.is_active == True)
        return self.paginate(page=page, page_size=page_size, query=query)

    def count_active(self) -> int:
        """Compte les peers actifs et activés du tenant."""
        stmt = (
            select(func.count())
            .select_from(WgPeer)
            .where(
                WgPeer.tenant_id == self._tenant_id,
                WgPeer.is_active == True,
                WgPeer.is_enabled == True,
            )
        )
        return self.session.execute(stmt).scalar() or 0

    def search(
        self,
        search_term: str,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedResult[WgPeer]:
        """Recherche dans les peers (nom, description, IP) du tenant."""
        pattern = f"%{search_term}%"
        query = self._tenant_query().where(
            WgPeer.is_active == True,
            or_(
                WgPeer.name.ilike(pattern),
                WgPeer.description.ilike(pattern),
                WgPeer.assigned_ip.ilike(pattern),
            ),
        )
        return self.paginate(page=page, page_size=page_size, query=query)
