"""Repository — LigneCommandeRestaurant (restaurant, tenant_id=3)."""
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.commande_restaurant import CommandeRestaurant
from app.models.restaurant.ligne_commande_restaurant import LigneCommandeRestaurant
from app.models.restaurant.variante_plat import VariantePlat

_TENANT_RESTAURANT = 3


class AsyncLigneCommandeRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs) -> LigneCommandeRestaurant:
        obj = LigneCommandeRestaurant(tenant_id=_TENANT_RESTAURANT, **kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, ligne_id: int) -> Optional[LigneCommandeRestaurant]:
        stmt = select(LigneCommandeRestaurant).where(
            LigneCommandeRestaurant.id == ligne_id,
            LigneCommandeRestaurant.tenant_id == _TENANT_RESTAURANT,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_commande(
        self, commande_id: int
    ) -> list[LigneCommandeRestaurant]:
        stmt = (
            select(LigneCommandeRestaurant)
            .where(
                LigneCommandeRestaurant.commande_id == commande_id,
                LigneCommandeRestaurant.tenant_id == _TENANT_RESTAURANT,
            )
            .order_by(LigneCommandeRestaurant.created_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_statut(
        self,
        ligne_id: int,
        statut: str,
        instance_preparation_id: Optional[int] = None,
    ) -> Optional[LigneCommandeRestaurant]:
        obj = await self.get_by_id(ligne_id)
        if obj is None:
            return None
        obj.statut_plat = statut
        if instance_preparation_id is not None:
            obj.instance_preparation_id = instance_preparation_id
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def list_ticket_cuisine(
        self, date_cuisine: Optional[date] = None
    ) -> list[LigneCommandeRestaurant]:
        """Lignes non SERVIE pour le ticket cuisine (commande OUVERTE uniquement)."""
        stmt = (
            select(LigneCommandeRestaurant)
            .join(CommandeRestaurant, LigneCommandeRestaurant.commande_id == CommandeRestaurant.id)
            .where(
                LigneCommandeRestaurant.tenant_id == _TENANT_RESTAURANT,
                LigneCommandeRestaurant.statut_plat != "SERVIE",
                CommandeRestaurant.statut == "OUVERTE",
            )
        )
        if date_cuisine is not None:
            stmt = stmt.where(
                func.date(LigneCommandeRestaurant.created_at) == date_cuisine
            )
        stmt = stmt.order_by(LigneCommandeRestaurant.created_at)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_commande_variante(
        self, commande_id: int, variante_id: int
    ) -> int:
        """Somme des quantités pour une variante dans une commande (formule boissons)."""
        stmt = select(
            func.coalesce(func.sum(LigneCommandeRestaurant.quantite), 0)
        ).where(
            LigneCommandeRestaurant.commande_id == commande_id,
            LigneCommandeRestaurant.variante_id == variante_id,
            LigneCommandeRestaurant.tenant_id == _TENANT_RESTAURANT,
        )
        return (await self.db.execute(stmt)).scalar() or 0

    async def list_ids_by_commande_variante(
        self, commande_id: int, variante_id: int
    ) -> list[int]:
        """IDs des lignes pour une variante dans une commande (pour suggestion formule)."""
        stmt = select(LigneCommandeRestaurant.id).where(
            LigneCommandeRestaurant.commande_id == commande_id,
            LigneCommandeRestaurant.variante_id == variante_id,
            LigneCommandeRestaurant.tenant_id == _TENANT_RESTAURANT,
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def list_ticket_bar(self) -> list[LigneCommandeRestaurant]:
        """Lignes boissons en statut ENVOYEE ou LANCEE (ticket bar).

        JOIN sur VariantePlat.type = 'boisson' pour ne retourner que les boissons.
        Triées par heure de commande croissante.
        """
        stmt = (
            select(LigneCommandeRestaurant)
            .join(
                VariantePlat,
                LigneCommandeRestaurant.variante_id == VariantePlat.id,
            )
            .where(
                LigneCommandeRestaurant.tenant_id == _TENANT_RESTAURANT,
                LigneCommandeRestaurant.statut_plat.in_(["ENVOYEE", "LANCEE"]),
                VariantePlat.type == "boisson",
            )
            .order_by(LigneCommandeRestaurant.created_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, ligne_id: int) -> bool:
        obj = await self.get_by_id(ligne_id)
        if obj is None:
            return False
        await self.db.delete(obj)
        await self.db.flush()
        return True
