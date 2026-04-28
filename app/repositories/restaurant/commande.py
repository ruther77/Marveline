"""Repository — CommandeRestaurant (restaurant, tenant_id=3)."""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.restaurant.commande_restaurant import CommandeRestaurant
from app.models.restaurant.ligne_commande_restaurant import LigneCommandeRestaurant

_TENANT_RESTAURANT = 3
_DEFAULT_PER_PAGE = 20
_MAX_PER_PAGE = 100


class AsyncCommandeRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs) -> CommandeRestaurant:
        obj = CommandeRestaurant(tenant_id=_TENANT_RESTAURANT, **kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, cmd_id: int) -> Optional[CommandeRestaurant]:
        stmt = select(CommandeRestaurant).where(
            CommandeRestaurant.id == cmd_id,
            CommandeRestaurant.tenant_id == _TENANT_RESTAURANT,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_table_ouverte(
        self, table_id: int
    ) -> Optional[CommandeRestaurant]:
        """Retourne la commande OUVERTE d'une table, ou None si table libre."""
        stmt = select(CommandeRestaurant).where(
            CommandeRestaurant.table_id == table_id,
            CommandeRestaurant.tenant_id == _TENANT_RESTAURANT,
            CommandeRestaurant.statut == "OUVERTE",
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        page: int = 1,
        per_page: int = _DEFAULT_PER_PAGE,
        statut: Optional[str] = None,
        date_debut: Optional[datetime] = None,
        date_fin: Optional[datetime] = None,
    ) -> tuple[list[CommandeRestaurant], int]:
        effective_per_page = min(per_page, _MAX_PER_PAGE)
        base = select(CommandeRestaurant).where(
            CommandeRestaurant.tenant_id == _TENANT_RESTAURANT,
        )
        if statut is not None:
            base = base.where(CommandeRestaurant.statut == statut)
        if date_debut is not None:
            base = base.where(CommandeRestaurant.created_at >= date_debut)
        if date_fin is not None:
            base = base.where(CommandeRestaurant.created_at <= date_fin)
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0
        data_stmt = (
            base.order_by(CommandeRestaurant.created_at.desc())
            .offset((page - 1) * effective_per_page)
            .limit(effective_per_page)
        )
        rows = await self.db.execute(data_stmt)
        return list(rows.scalars().all()), total

    async def update(self, cmd_id: int, **kwargs: Any) -> Optional[CommandeRestaurant]:
        obj = await self.get_by_id(cmd_id)
        if obj is None:
            return None
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def count_ouverts_today(self) -> int:
        """Nombre de commandes OUVERTE aujourd'hui — stats dashboard."""
        stmt = select(func.count()).where(
            CommandeRestaurant.tenant_id == _TENANT_RESTAURANT,
            CommandeRestaurant.statut == "OUVERTE",
        )
        return (await self.db.execute(stmt)).scalar() or 0

    async def sum_ca_date(self, date_debut: datetime, date_fin: datetime) -> int:
        """Somme total_cts des commandes PAYEE sur la période — CA dashboard (centimes)."""
        stmt = select(func.coalesce(func.sum(CommandeRestaurant.total_cts), 0)).where(
            CommandeRestaurant.tenant_id == _TENANT_RESTAURANT,
            CommandeRestaurant.statut == "PAYEE",
            CommandeRestaurant.date_fermeture >= date_debut,
            CommandeRestaurant.date_fermeture <= date_fin,
        )
        return (await self.db.execute(stmt)).scalar() or 0

    async def count_couverts_date(
        self, date_debut: datetime, date_fin: datetime
    ) -> int:
        """Somme nb_couverts des commandes PAYEE sur la période — stats dashboard."""
        stmt = select(
            func.coalesce(func.sum(CommandeRestaurant.nb_couverts), 0)
        ).where(
            CommandeRestaurant.tenant_id == _TENANT_RESTAURANT,
            CommandeRestaurant.statut == "PAYEE",
            CommandeRestaurant.date_fermeture >= date_debut,
            CommandeRestaurant.date_fermeture <= date_fin,
        )
        return (await self.db.execute(stmt)).scalar() or 0

    async def list_active_for_kds(self, tenant_id: int) -> list[dict]:
        """Commandes actives (OUVERTE/SERVIE) avec leurs lignes — snapshot KDS.

        Retourne une liste de dicts serialisables JSON pour le WebSocket.
        """
        stmt = (
            select(CommandeRestaurant)
            .where(
                CommandeRestaurant.tenant_id == tenant_id,
                CommandeRestaurant.statut.in_(["OUVERTE", "SERVIE"]),
            )
            .order_by(CommandeRestaurant.created_at.asc())
        )
        result = await self.db.execute(stmt)
        commandes = list(result.scalars().all())

        if not commandes:
            return []

        # Charger les lignes pour ces commandes
        commande_ids = [c.id for c in commandes]
        lignes_stmt = (
            select(LigneCommandeRestaurant)
            .where(LigneCommandeRestaurant.commande_id.in_(commande_ids))
            .order_by(LigneCommandeRestaurant.created_at.asc())
        )
        lignes_result = await self.db.execute(lignes_stmt)
        all_lignes = list(lignes_result.scalars().all())

        # Grouper par commande_id
        lignes_by_cmd: dict[int, list[dict]] = {}
        for ligne in all_lignes:
            entry = {
                "id": ligne.id,
                "variante_id": ligne.variante_id,
                "quantite": ligne.quantite,
                "prix_unitaire_cts": ligne.prix_unitaire_cts,
                "statut_plat": ligne.statut_plat,
                "notes": ligne.notes,
            }
            lignes_by_cmd.setdefault(ligne.commande_id, []).append(entry)

        return [
            {
                "id": c.id,
                "table_id": c.table_id,
                "statut": c.statut,
                "nb_couverts": c.nb_couverts,
                "notes": c.notes,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "lignes": lignes_by_cmd.get(c.id, []),
            }
            for c in commandes
        ]
