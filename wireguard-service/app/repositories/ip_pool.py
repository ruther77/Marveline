"""Repository pour les pools d'adresses IP WireGuard."""

import logging
from typing import List, Optional

from sqlalchemy import select

from app.models.ip_pool import WgIpPool
from app.repositories.base import TenantAwareBaseRepository

logger = logging.getLogger(__name__)


class IpPoolRepository(TenantAwareBaseRepository[WgIpPool]):
    """Repository pour les opérations sur les pools IP.

    L'allocation d'IP utilise SELECT ... FOR UPDATE pour garantir
    l'atomicité en environnement concurrent.
    """

    model = WgIpPool

    def get_by_subnet(self, subnet: str) -> Optional[WgIpPool]:
        """Récupère un pool par son subnet dans le tenant."""
        stmt = self._tenant_query().where(WgIpPool.subnet == subnet)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_all(self) -> List[WgIpPool]:
        """Liste tous les pools du tenant."""
        stmt = self._tenant_query()
        return list(self.session.execute(stmt).scalars().all())

    def lock_for_allocation(self, pool_id: int) -> Optional[WgIpPool]:
        """Verrouille un pool pour allocation atomique (SELECT FOR UPDATE).

        Doit être appelé dans une transaction active.
        Le verrou est relâché au commit/rollback.
        """
        stmt = (
            select(WgIpPool)
            .where(
                WgIpPool.tenant_id == self._tenant_id,
                WgIpPool.id == pool_id,
            )
            .with_for_update()
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def update_next_ip(self, pool_id: int, next_ip: str) -> bool:
        """Met à jour la prochaine IP à allouer.

        Doit être appelé après lock_for_allocation() dans la même transaction.
        """
        pool = self.get(pool_id)
        if pool is None:
            return False
        pool.next_ip = next_ip
        self.session.flush()
        return True
