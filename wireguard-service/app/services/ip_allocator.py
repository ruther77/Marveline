"""Service d'allocation IP atomique pour les peers WireGuard."""

import ipaddress
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.ip_pool import IpPoolRepository

logger = logging.getLogger(__name__)


class IpExhaustedError(Exception):
    """Le pool IP est épuisé — plus d'adresses disponibles."""
    pass


class IpAllocatorService:
    """Gère l'allocation et la libération d'adresses IP.

    Utilise SELECT FOR UPDATE via IpPoolRepository pour garantir
    l'atomicité en environnement concurrent.
    """

    def __init__(self, session: Session, tenant_id: int) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.ip_pool_repo = IpPoolRepository(session, tenant_id)

    def allocate_ip(self, pool_id: int) -> str:
        """Alloue la prochaine IP disponible dans le pool.

        Verrouille le pool (FOR UPDATE), incrémente next_ip, retourne l'IP
        allouée au format "x.x.x.x/32".

        Raises:
            IpExhaustedError: Plus d'adresses disponibles dans le pool.
            ValueError: Pool introuvable.
        """
        pool = self.ip_pool_repo.lock_for_allocation(pool_id)
        if pool is None:
            raise ValueError(f"IP pool {pool_id} not found for tenant {self.tenant_id}")

        current_ip = ipaddress.IPv4Address(pool.next_ip)
        network = ipaddress.IPv4Network(pool.subnet, strict=False)
        broadcast = network.broadcast_address

        if current_ip >= broadcast:
            raise IpExhaustedError(
                f"IP pool {pool.subnet} exhausted: no addresses available"
            )

        allocated_ip = str(current_ip)

        next_ip = current_ip + 1
        # Skip broadcast address
        if next_ip >= broadcast:
            next_ip = broadcast  # Mark as exhausted for next call

        self.ip_pool_repo.update_next_ip(pool_id, str(next_ip))

        logger.info(
            "Allocated IP %s/32 from pool %s (tenant=%d)",
            allocated_ip, pool.subnet, self.tenant_id,
        )

        return f"{allocated_ip}/32"

    def get_available_count(self, pool_id: int) -> int:
        """Retourne le nombre d'IPs encore disponibles dans le pool."""
        pool = self.ip_pool_repo.get(pool_id)
        if pool is None:
            return 0

        current_ip = ipaddress.IPv4Address(pool.next_ip)
        network = ipaddress.IPv4Network(pool.subnet, strict=False)
        broadcast = network.broadcast_address

        if current_ip >= broadcast:
            return 0

        return int(broadcast) - int(current_ip)

    def is_exhausted(self, pool_id: int) -> bool:
        """Vérifie si le pool est épuisé."""
        return self.get_available_count(pool_id) == 0

    def find_pool_with_capacity(self) -> Optional[int]:
        """Trouve le premier pool avec de la capacité pour le tenant."""
        pools = self.ip_pool_repo.list_all()
        for pool in pools:
            current_ip = ipaddress.IPv4Address(pool.next_ip)
            network = ipaddress.IPv4Network(pool.subnet, strict=False)
            if current_ip < network.broadcast_address:
                return pool.id
        return None
