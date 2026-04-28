"""Service StockItem — orchestration du tracking individuel des unités physiques."""
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.stock_item import StockItem
from app.repositories.stock_item import AsyncStockItemRepository
from app.repositories.product import AsyncProductRepository
from app.constants.errors import ErrorMessages

logger = logging.getLogger(__name__)

# Transitions valides : {from_status: [to_statuses autorisés]}
VALID_TRANSITIONS: dict[str, list[str]] = {
    "available": ["reserved", "retired"],
    "reserved": ["on_location", "available", "retired"],
    "on_location": ["available", "damaged", "retired"],
    "damaged": ["in_repair", "retired"],
    "in_repair": ["available", "retired"],
    "retired": [],
}


class StockItemService:
    """Service métier pour le tracking individuel des unités physiques.

    Responsibilities:
        - Réservation d'unités lors de la confirmation réservation
        - Libération en cas d'annulation
        - Transitions de statut lors des mouvements d'inventaire
        - Synchronisation du cache available_quantity sur Product
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AsyncStockItemRepository(db)
        self.product_repo = AsyncProductRepository(db)

    async def list_by_product(self, product_id: int, tenant_id: int) -> list[StockItem]:
        """Liste toutes les unités d'un produit."""
        return await self.repo.list_by_product(product_id, tenant_id)

    async def list_by_products(self, product_ids: list[int], tenant_id: int) -> list[StockItem]:
        """Liste toutes les unités d'un ensemble de produits."""
        return await self.repo.list_by_products(product_ids, tenant_id)

    async def get_counts(self, product_id: int, tenant_id: int) -> dict[str, int]:
        """Retourne les compteurs par statut pour un produit."""
        counts = await self.repo.count_by_statuses(product_id, tenant_id)
        for s in ("available", "reserved", "on_location", "damaged", "in_repair", "retired"):
            counts.setdefault(s, 0)
        return counts

    async def reserve_n(
        self,
        product_id: int,
        n: int,
        tenant_id: int,
        reservation_id: Optional[int] = None,
        variant_id: Optional[int] = None,
    ) -> list[StockItem]:
        """Réserve N unités disponibles pour une réservation.

        Si variant_id fourni, restreint aux items de cette variante.

        Raises:
            HTTPException 400: Si stock insuffisant.
        """
        try:
            items = await self.repo.reserve_n(
                product_id, n, tenant_id, reservation_id, variant_id
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        await self.product_repo.sync_available_from_variants(product_id, tenant_id)
        logger.info("StockItem: %d unités réservées (product_id=%d, variant_id=%s)", n, product_id, variant_id)
        return items

    async def release_n(
        self,
        product_id: int,
        n: int,
        tenant_id: int,
        variant_id: Optional[int] = None,
        reservation_id: Optional[int] = None,
    ) -> list[StockItem]:
        """Libère N unités réservées (annulation réservation).

        Si ``reservation_id`` est fourni, ne libère que les items appartenant
        à cette résa (filtre ``current_reservation_id``). Sans cet argument,
        comportement legacy (libération aveugle) — émet un warning.

        Si variant_id fourni, restreint aux items de cette variante.

        Raises:
            HTTPException 400: Si pas assez d'items réservés correspondants.
        """
        try:
            items = await self.repo.release_n(
                product_id, n, tenant_id, variant_id, reservation_id=reservation_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        await self.product_repo.sync_available_from_variants(product_id, tenant_id)
        logger.info(
            "StockItem: %d unités libérées (product_id=%d, variant_id=%s, reservation_id=%s)",
            n, product_id, variant_id, reservation_id,
        )
        return items

    async def transition_n(
        self,
        product_id: int,
        n: int,
        from_status: str,
        to_status: str,
        tenant_id: int,
        variant_id: Optional[int] = None,
    ) -> list[StockItem]:
        """Transition N items d'un statut vers un autre.

        Si variant_id fourni, restreint aux items de cette variante.

        Raises:
            HTTPException 400: Si transition invalide ou stock insuffisant.
        """
        if to_status not in VALID_TRANSITIONS.get(from_status, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.STOCK_ITEM_NOT_AVAILABLE,
            )
        try:
            items = await self.repo.transition_n(
                product_id, n, from_status, to_status, tenant_id, variant_id
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        await self.product_repo.sync_available_from_variants(product_id, tenant_id)
        logger.info(
            "StockItem: %d unités %s→%s (product_id=%d, variant_id=%s)",
            n, from_status, to_status, product_id, variant_id,
        )
        return items

    async def transition_status(
        self, stock_item_id: int, new_status: str, tenant_id: int
    ) -> StockItem:
        """Transition d'un item individuel avec validation.

        Raises:
            HTTPException 400: Si transition invalide ou item introuvable.
        """
        try:
            item = await self.repo.transition_status(stock_item_id, new_status, tenant_id)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        await self.product_repo.sync_available_from_variants(item.product_id, tenant_id)
        return item
