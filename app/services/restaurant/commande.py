"""Service — CommandeRestaurant.

TVA variable par ligne (ADR-06-BIS) : taux_tva en centièmes de %.
  Formule : tva_ligne = round(montant_ttc * taux / (1 + taux))
  sous_total_cts = Σ (montant_ttc - tva_ligne)   ← HT
  tva_cts        = Σ tva_ligne
  total_cts      = sous_total_cts + tva_cts        ← TTC (hors pourboire)

`date_ouverture` mappée sur `created_at` (pas de colonne dédiée).
"""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.restaurant.side_restaurant import SideRestaurant
from app.models.restaurant.table_restaurant import TableRestaurant
from app.models.restaurant.variante_plat import VariantePlat
from app.repositories.restaurant.commande import AsyncCommandeRepo
from app.repositories.restaurant.ligne_commande import AsyncLigneCommandeRepo
from app.repositories.restaurant.table import AsyncTableRepo
from app.schemas.restaurant.commande import (
    CommandeCreate,
    CommandeDetail,
    CommandeDetailHistorique,
    CommandeListResponse,
    CommandeResponse,
    FractionPaiement,
    PaiementRequest,
)
from app.schemas.restaurant.ligne_commande import (
    LigneCommandeResponse,
    LigneHistoriqueResponse,
)
from app.services.restaurant.exceptions import (
    CommandeDejaPayee,
    CommandeNonOuverte,
    TableDejaOccupee,
)

_DIV_TVA = Decimal("10000")


def _calculer_tva_ligne(montant_ttc: int, taux_tva: int) -> int:
    """Extrait la TVA d'un montant TTC. taux_tva en centièmes de % (ex: 550=5,5%)."""
    if taux_tva <= 0:
        return 0
    taux = Decimal(str(taux_tva)) / _DIV_TVA
    raw = Decimal(str(montant_ttc)) * taux / (1 + taux)
    return int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class CommandeService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AsyncCommandeRepo(db)
        self._ligne_repo = AsyncLigneCommandeRepo(db)
        self._table_repo = AsyncTableRepo(db)

    async def ouvrir(
        self, payload: CommandeCreate, created_by_id: Optional[int] = None
    ) -> CommandeResponse:
        table_numero = None
        if payload.table_id:
            table = await self._table_repo.get_by_id(payload.table_id)
            if table is None:
                raise NotFound("TableRestaurant")
            if await self._repo.get_by_table_ouverte(payload.table_id) is not None:
                raise TableDejaOccupee("Une commande est déjà ouverte sur cette table")
            table_numero = table.numero
        cmd = await self._repo.create(
            table_id=payload.table_id,
            nb_couverts=payload.nb_couverts,
            nom_client=payload.nom_client,
            notes=payload.notes,
            created_by_id=created_by_id,
        )
        return self._to_response(cmd, table_numero)

    async def annuler(self, cmd_id: int) -> CommandeResponse:
        cmd = await self._repo.get_by_id(cmd_id)
        if cmd is None:
            raise NotFound("CommandeRestaurant")
        if cmd.statut != "OUVERTE":
            raise CommandeNonOuverte("Seule une commande OUVERTE peut être annulée")
        now = datetime.now(timezone.utc)
        cmd = await self._repo.update(cmd_id, statut="ANNULEE", date_fermeture=now)
        table_num = await self._resolve_table_numero(cmd.table_id)
        return self._to_response(cmd, table_num)

    async def payer(self, cmd_id: int, payload: PaiementRequest) -> CommandeDetailHistorique:
        cmd = await self._repo.get_by_id(cmd_id)
        if cmd is None:
            raise NotFound("CommandeRestaurant")
        if cmd.statut == "PAYEE":
            raise CommandeDejaPayee("Commande déjà payée")
        if cmd.statut != "OUVERTE":
            raise CommandeNonOuverte("Seule une commande OUVERTE peut être payée")
        lignes = await self._ligne_repo.list_by_commande(cmd_id)
        var_map = await self._batch_variantes([l.variante_id for l in lignes])
        sous_total, tva_total = self._calculer_totaux(lignes, var_map)
        total_ttc = sous_total + tva_total
        now = datetime.now(timezone.utc)
        fractions_json = (
            [f.model_dump() for f in payload.fractions] if payload.fractions else None
        )
        await self._repo.update(
            cmd_id,
            statut="PAYEE",
            sous_total_cts=sous_total,
            tva_cts=tva_total,
            total_cts=total_ttc,
            pourboire_cts=payload.pourboire_cts,
            mode_paiement=payload.mode_paiement,
            fractionnement=fractions_json,
            date_fermeture=now,
        )
        return await self.get_detail_historique(cmd_id)

    async def get_detail(self, cmd_id: int) -> CommandeDetail:
        cmd = await self._repo.get_by_id(cmd_id)
        if cmd is None:
            raise NotFound("CommandeRestaurant")
        raw_lignes = await self._ligne_repo.list_by_commande(cmd_id)
        var_map = await self._batch_variantes([l.variante_id for l in raw_lignes])
        side_map = await self._batch_sides([l.side_id for l in raw_lignes if l.side_id])
        lignes_schema = []
        sous_total, tva_total = 0, 0
        for l in raw_lignes:
            var = var_map.get(l.variante_id)
            side = side_map.get(l.side_id) if l.side_id else None
            montant = l.prix_unitaire_cts * l.quantite
            tva = _calculer_tva_ligne(montant, var.taux_tva if var else 0)
            sous_total += montant - tva
            tva_total += tva
            lignes_schema.append(LigneCommandeResponse(
                ligne_id=l.id,
                variante_nom=var.nom if var else "—",
                side_nom=side.nom if side else None,
                instance_preparation_id=l.instance_preparation_id,
                statut_plat=l.statut_plat,
                prix_unitaire_cts=l.prix_unitaire_cts,
                quantite=l.quantite,
                notes=l.notes,
            ))
        table_num = await self._resolve_table_numero(cmd.table_id)
        return CommandeDetail(
            id=cmd.id,
            table_numero=table_num,
            statut=cmd.statut,
            date_ouverture=cmd.created_at,
            nb_couverts=cmd.nb_couverts,
            nom_client=cmd.nom_client,
            lignes=lignes_schema,
            sous_total_cts=sous_total,
            tva_cts=tva_total,
            total_cts=sous_total + tva_total,
        )

    async def get_detail_historique(self, cmd_id: int) -> CommandeDetailHistorique:
        cmd = await self._repo.get_by_id(cmd_id)
        if cmd is None:
            raise NotFound("CommandeRestaurant")
        lignes_hist, sous_total, tva_total = await self._build_lignes_historique(cmd_id)
        table_num = await self._resolve_table_numero(cmd.table_id)
        fractions = (
            [FractionPaiement(**f) for f in cmd.fractionnement]
            if cmd.fractionnement
            else None
        )
        return CommandeDetailHistorique(
            id=cmd.id,
            table_numero=table_num,
            statut=cmd.statut,
            date_ouverture=cmd.created_at,
            date_fermeture=cmd.date_fermeture,
            lignes=lignes_hist,
            sous_total_cts=cmd.sous_total_cts or sous_total,
            tva_cts=cmd.tva_cts or tva_total,
            total_ttc_cts=cmd.total_cts or (sous_total + tva_total),
            pourboire_cts=cmd.pourboire_cts,
            mode_paiement=cmd.mode_paiement,
            fractions=fractions,
        )

    async def list_paginated(
        self,
        page: int = 1,
        per_page: int = 20,
        statut: Optional[str] = None,
        date_debut: Optional[datetime] = None,
        date_fin: Optional[datetime] = None,
    ) -> CommandeListResponse:
        commandes, total = await self._repo.list_paginated(
            page, per_page, statut, date_debut, date_fin
        )
        table_nums = await self._batch_table_numeros(
            [c.table_id for c in commandes if c.table_id]
        )
        items = [self._to_response(c, table_nums.get(c.table_id)) for c in commandes]
        ca = 0
        if date_debut and date_fin:
            ca = await self._repo.sum_ca_date(date_debut, date_fin)
        return CommandeListResponse(
            items=items, page=page, per_page=per_page, total=total, ca_periode_cts=ca
        )

    # ── helpers privés ────────────────────────────────────────────────────────

    async def _build_lignes_detail(self, commande_id: int) -> list[LigneCommandeResponse]:
        lignes = await self._ligne_repo.list_by_commande(commande_id)
        if not lignes:
            return []
        var_map = await self._batch_variantes([l.variante_id for l in lignes])
        side_map = await self._batch_sides([l.side_id for l in lignes if l.side_id])
        result = []
        for l in lignes:
            var = var_map.get(l.variante_id)
            side = side_map.get(l.side_id) if l.side_id else None
            result.append(LigneCommandeResponse(
                ligne_id=l.id,
                variante_nom=var.nom if var else "—",
                side_nom=side.nom if side else None,
                instance_preparation_id=l.instance_preparation_id,
                statut_plat=l.statut_plat,
                prix_unitaire_cts=l.prix_unitaire_cts,
                quantite=l.quantite,
                notes=l.notes,
            ))
        return result

    async def _build_lignes_historique(
        self, commande_id: int
    ) -> tuple[list[LigneHistoriqueResponse], int, int]:
        lignes = await self._ligne_repo.list_by_commande(commande_id)
        if not lignes:
            return [], 0, 0
        var_map = await self._batch_variantes([l.variante_id for l in lignes])
        side_map = await self._batch_sides([l.side_id for l in lignes if l.side_id])
        result, sous_total, tva_total = [], 0, 0
        for l in lignes:
            var = var_map.get(l.variante_id)
            side = side_map.get(l.side_id) if l.side_id else None
            montant = l.prix_unitaire_cts * l.quantite
            tva = _calculer_tva_ligne(montant, var.taux_tva if var else 0)
            sous_total += montant - tva
            tva_total += tva
            result.append(LigneHistoriqueResponse(
                ligne_id=l.id,
                type=var.type if var else "plat",
                description=var.nom if var else "—",
                side=side.nom if side else None,
                quantite=l.quantite,
                prix_unitaire_cts=l.prix_unitaire_cts,
                montant_cts=montant,
            ))
        return result, sous_total, tva_total

    def _calculer_totaux(self, lignes, var_map: dict) -> tuple[int, int]:
        sous_total, tva_total = 0, 0
        for l in lignes:
            montant_ttc = l.prix_unitaire_cts * l.quantite
            var = var_map.get(l.variante_id)
            tva = _calculer_tva_ligne(montant_ttc, var.taux_tva if var else 0)
            sous_total += montant_ttc - tva
            tva_total += tva
        return sous_total, tva_total

    def _to_response(self, cmd, table_numero: Optional[str]) -> CommandeResponse:
        return CommandeResponse(
            id=cmd.id,
            table_numero=table_numero,
            statut=cmd.statut,
            date_ouverture=cmd.created_at,
            date_fermeture=cmd.date_fermeture,
            nb_couverts=cmd.nb_couverts,
            nom_client=cmd.nom_client,
            total_cts=cmd.total_cts,
            pourboire_cts=cmd.pourboire_cts,
        )

    async def _resolve_table_numero(self, table_id: Optional[int]) -> Optional[str]:
        if not table_id:
            return None
        table = await self._table_repo.get_by_id(table_id)
        return table.numero if table else None

    async def _batch_variantes(self, ids: list[int]) -> dict[int, VariantePlat]:
        unique = list(set(ids))
        if not unique:
            return {}
        stmt = select(VariantePlat).where(VariantePlat.id.in_(unique))
        result = await self._db.execute(stmt)
        return {v.id: v for v in result.scalars()}

    async def _batch_sides(self, ids: list[int]) -> dict[int, SideRestaurant]:
        unique = list(set(ids))
        if not unique:
            return {}
        stmt = select(SideRestaurant).where(SideRestaurant.id.in_(unique))
        result = await self._db.execute(stmt)
        return {s.id: s for s in result.scalars()}

    async def _batch_table_numeros(self, table_ids: list[int]) -> dict[int, str]:
        unique = list(set(table_ids))
        if not unique:
            return {}
        stmt = select(TableRestaurant).where(TableRestaurant.id.in_(unique))
        result = await self._db.execute(stmt)
        return {t.id: t.numero for t in result.scalars()}
