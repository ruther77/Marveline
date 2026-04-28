"""Service — TableRestaurant.

Statut calculé côté service (ADR-14) :
  LIBRE  : aucune commande OUVERTE liée
  OUVERTE: commande OUVERTE, au moins un plat non servi
  SERVIE : commande OUVERTE, tous plats servis
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.restaurant.variante_plat import VariantePlat
from app.repositories.restaurant.commande import AsyncCommandeRepo
from app.repositories.restaurant.ligne_commande import AsyncLigneCommandeRepo
from app.repositories.restaurant.table import AsyncTableRepo
from app.schemas.restaurant.table import (
    CommandeActiveResponse,
    LignePreviewResponse,
    TableCreate,
    TableListResponse,
    TableResponse,
    TableUpdate,
)

_STATUT_LIBRE = "LIBRE"
_STATUT_OUVERTE = "OUVERTE"
_STATUT_SERVIE = "SERVIE"


def _commande_active_response(cmd, lignes, var_map: dict) -> CommandeActiveResponse:
    """Construit CommandeActiveResponse avec lignes_preview (S6)."""
    nb_plats = sum(l.quantite for l in lignes)
    nb_plats_servis = sum(l.quantite for l in lignes if l.statut_plat == "SERVIE")
    total = sum(l.prix_unitaire_cts * l.quantite for l in lignes)
    lignes_preview = [
        LignePreviewResponse(
            ligne_id=l.id,
            variante_nom=var_map.get(l.variante_id, "—"),
            quantite=l.quantite,
            statut_plat=l.statut_plat,
        )
        for l in lignes
    ]
    return CommandeActiveResponse(
        commande_id=cmd.id,
        nb_couverts=cmd.nb_couverts,
        nom_client=cmd.nom_client,
        date_ouverture=cmd.created_at,
        nb_plats=nb_plats,
        nb_plats_servis=nb_plats_servis,
        total_provisoire_cts=total,
        lignes_preview=lignes_preview,
    )


def _statut_table(lignes) -> str:
    """R3 : LIBRE|OUVERTE|SERVIE — SERVIE si tous plats servis."""
    if not lignes:
        return _STATUT_OUVERTE
    nb_plats = sum(l.quantite for l in lignes)
    nb_servis = sum(l.quantite for l in lignes if l.statut_plat == "SERVIE")
    return _STATUT_SERVIE if nb_plats == nb_servis else _STATUT_OUVERTE


class TableService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AsyncTableRepo(db)
        self._cmd_repo = AsyncCommandeRepo(db)
        self._ligne_repo = AsyncLigneCommandeRepo(db)

    async def get_avec_statut(self, table_id: int) -> TableResponse:
        table = await self._repo.get_by_id(table_id)
        if table is None:
            raise NotFound("TableRestaurant")
        return await self._enrichir(table)

    async def list_avec_statut(self) -> TableListResponse:
        tables = await self._repo.list_actives()
        items = [await self._enrichir(t) for t in tables]
        return TableListResponse(items=items)

    async def _batch_variantes(self, lignes) -> dict:
        """Charge les noms des variantes en une seule requête (anti-N+1)."""
        ids = list({l.variante_id for l in lignes if l.variante_id})
        if not ids:
            return {}
        result = await self._db.execute(
            select(VariantePlat.id, VariantePlat.nom).where(VariantePlat.id.in_(ids))
        )
        return {row.id: row.nom for row in result}

    async def _enrichir(self, table) -> TableResponse:
        cmd = await self._cmd_repo.get_by_table_ouverte(table.id)
        if cmd is None:
            return TableResponse(
                id=table.id,
                numero=table.numero,
                capacite=table.capacite,
                statut=_STATUT_LIBRE,
                commande_active=None,
            )
        lignes = await self._ligne_repo.list_by_commande(cmd.id)
        var_map = await self._batch_variantes(lignes)
        commande_active = _commande_active_response(cmd, lignes, var_map)
        return TableResponse(
            id=table.id,
            numero=table.numero,
            capacite=table.capacite,
            statut=_statut_table(lignes),
            commande_active=commande_active,
        )

    async def create_table(self, payload: TableCreate) -> TableResponse:
        obj = await self._repo.create(
            numero=payload.numero,
            capacite=payload.capacite,
        )
        return TableResponse(
            id=obj.id, numero=obj.numero, capacite=obj.capacite,
            statut=_STATUT_LIBRE, commande_active=None,
        )

    async def update_table(self, table_id: int, payload: TableUpdate) -> TableResponse:
        table = await self._repo.get_by_id(table_id)
        if table is None:
            raise NotFound("TableRestaurant")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(table, key, value)
        await self._db.flush()
        return await self._enrichir(table)

    async def delete_table(self, table_id: int) -> Optional[int]:
        """Soft-delete la table ; retourne l'id de la commande OUVERTE à annuler, ou None."""
        table = await self._repo.get_by_id(table_id)
        if table is None:
            raise NotFound("TableRestaurant")
        cmd = await self._cmd_repo.get_by_table_ouverte(table.id)
        commande_id = cmd.id if cmd else None
        table.is_active = False
        await self._db.flush()
        return commande_id
