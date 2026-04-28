"""Service — DashboardService restaurant.

ADR-14 : ca_cts, portions_restantes, stock_actuel lus directement DB.

ticket_moyen_cts = ca_cts // nb_couverts (standard restauration — 0 si nb_couverts = 0).
get_marmites : instances actives du jour (portions_restantes > 0) + protéines disponibles.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.models.tenant_settings import TenantSettings
from app.models.restaurant.type_preparation import TypePreparation
from app.models.restaurant.variante_plat import VariantePlat
from app.repositories.restaurant.alerte_stock import AsyncAlerteStockRepo
from app.repositories.restaurant.commande import AsyncCommandeRepo
from app.repositories.restaurant.ingredient import AsyncIngredientRepo
from app.repositories.restaurant.instance_preparation import AsyncInstancePreparationRepo
from app.schemas.restaurant.dashboard import (
    DashboardStatsResponse,
    IngredientEpuiseResponse,
    InstanceVideResponse,
    RupturesResponse,
)
from app.schemas.restaurant.instance_preparation import (
    MarmiteDetailResponse,
    MarmitesDashboardResponse,
    ProteineDisponibleResponse,
)

_MAX_INSTANCES_PER_DAY = 100
_TENANT_RESTAURANT = 3


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    """Retourne (début, fin) du jour en UTC pour les requêtes date-based."""
    debut = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
    fin = datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=timezone.utc)
    return debut, fin


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._cmd_repo = AsyncCommandeRepo(db)
        self._inst_repo = AsyncInstancePreparationRepo(db)
        self._ing_repo = AsyncIngredientRepo(db)
        self._alerte_repo = AsyncAlerteStockRepo(db)

    async def get_stats(self, date_ref: date) -> DashboardStatsResponse:
        debut, fin = _day_bounds(date_ref)
        ca_cts_pos = await self._cmd_repo.sum_ca_date(debut, fin)
        nb_couverts = await self._cmd_repo.count_couverts_date(debut, fin)
        # Uplift commandes réservées hors POS — appliqué au CA et ticket moyen.
        # Lu depuis tenant_settings.reservation_uplift_pct (default 0).
        uplift_pct = await self._load_uplift_pct()
        ca_cts = ca_cts_pos + (ca_cts_pos * uplift_pct) // 100
        ticket_moyen = ca_cts // nb_couverts if nb_couverts > 0 else 0
        commandes_ouvertes = await self._cmd_repo.count_ouverts_today()
        marmites_actives = await self._inst_repo.count_actives_today(date_ref)
        ruptures_count = await self._alerte_repo.count_actives()
        ca_variation_pct = await self._compute_ca_variation(date_ref, ca_cts)
        return DashboardStatsResponse(
            date=date_ref,
            ca_cts=ca_cts,
            nb_couverts=nb_couverts,
            ticket_moyen_cts=ticket_moyen,
            commandes_ouvertes=commandes_ouvertes,
            marmites_actives=marmites_actives,
            ruptures_count=ruptures_count,
            ca_variation_pct=ca_variation_pct,
        )

    async def _load_uplift_pct(self) -> int:
        """Lit le coefficient d'uplift CA depuis tenant_settings (tenant 3).

        Retourne 0 si aucun setting (POS pur, comportement legacy).
        """
        result = await self._db.execute(
            select(TenantSettings.reservation_uplift_pct).where(
                TenantSettings.tenant_id == _TENANT_RESTAURANT
            )
        )
        return result.scalar_one_or_none() or 0

    async def _compute_ca_variation(
        self, date_ref: date, ca_jour: int
    ) -> Optional[float]:
        """FIN-VARIATION-01 : variation CA jour vs jour-1 (None si jour-1 = 0).

        ca_jour est déjà uplift. Pour cohérence, on uplift aussi ca_hier.
        """
        debut_hier, fin_hier = _day_bounds(date_ref - timedelta(days=1))
        ca_hier_pos = await self._cmd_repo.sum_ca_date(debut_hier, fin_hier)
        uplift_pct = await self._load_uplift_pct()
        ca_hier = ca_hier_pos + (ca_hier_pos * uplift_pct) // 100
        if ca_hier <= 0:
            return None
        return round((ca_jour - ca_hier) / ca_hier * 100, 1)

    async def get_ruptures(self, date_ref: date) -> RupturesResponse:
        instances_vides_raw = await self._inst_repo.list_vides_today(date_ref)
        ingredients_epuises_raw = await self._ing_repo.list_epuises()
        tp_ids = [i.type_preparation_id for i in instances_vides_raw]
        tp_map = await self._batch_types_preparation(tp_ids)
        instances_vides = [
            InstanceVideResponse(
                instance_id=inst.id,
                type_preparation_nom=(
                    tp_map[inst.type_preparation_id].nom
                    if inst.type_preparation_id in tp_map
                    else "—"
                ),
                portions_restantes=inst.portions_restantes,
            )
            for inst in instances_vides_raw
        ]
        ingredients_epuises = [
            IngredientEpuiseResponse(
                ingredient_id=ing.id,
                nom=ing.nom,
                stock_actuel_kg=float(ing.stock_actuel),
                unite_stock=ing.unite_stock,
            )
            for ing in ingredients_epuises_raw
        ]
        return RupturesResponse(
            instances_vides=instances_vides,
            ingredients_epuises=ingredients_epuises,
        )

    async def get_marmites(self, date_ref: date) -> MarmitesDashboardResponse:
        instances, _ = await self._inst_repo.list_by_date(
            date_ref, page=1, per_page=_MAX_INSTANCES_PER_DAY
        )
        actives = [i for i in instances if i.portions_restantes > 0]
        if not actives:
            return MarmitesDashboardResponse(items=[])
        tp_ids = [i.type_preparation_id for i in actives]
        tp_map = await self._batch_types_preparation(tp_ids)
        var_map = await self._batch_variantes_by_type_preparation(tp_ids)
        ing_ids = [
            v.ingredient_proteine_id
            for vars_list in var_map.values()
            for v in vars_list
            if v.ingredient_proteine_id
        ]
        ing_map = await self._batch_ingredients(ing_ids)
        items = [
            self._to_marmite_detail(inst, tp_map, var_map, ing_map)
            for inst in actives
        ]
        return MarmitesDashboardResponse(items=items)

    # ── helpers présentation ──────────────────────────────────────────────────

    def _to_marmite_detail(
        self, inst, tp_map, var_map, ing_map
    ) -> MarmiteDetailResponse:
        tp = tp_map.get(inst.type_preparation_id)
        variantes = var_map.get(inst.type_preparation_id, [])
        proteines = [
            ProteineDisponibleResponse(
                ingredient_id=v.ingredient_proteine_id,
                nom=ing_map[v.ingredient_proteine_id].nom,
                stock_actuel_kg=float(ing_map[v.ingredient_proteine_id].stock_actuel),
                unite_stock=ing_map[v.ingredient_proteine_id].unite_stock,
                variante_plat_id=v.id,
                variante_nom=v.nom,
                prix_vente_cts=v.prix_vente_cts,
            )
            for v in variantes
            if v.ingredient_proteine_id and v.ingredient_proteine_id in ing_map
        ]
        return MarmiteDetailResponse(
            instance_id=inst.id,
            type_preparation_nom=tp.nom if tp else "—",
            date_cuisine=inst.date_cuisine,
            portions_initiales=inst.portions_initiales,
            portions_restantes=inst.portions_restantes,
            proteines_disponibles=proteines,
        )

    # ── batch helpers ─────────────────────────────────────────────────────────

    async def _batch_types_preparation(
        self, ids: list[int]
    ) -> dict[int, TypePreparation]:
        unique = list(set(ids))
        if not unique:
            return {}
        stmt = select(TypePreparation).where(TypePreparation.id.in_(unique))
        result = await self._db.execute(stmt)
        return {t.id: t for t in result.scalars()}

    async def _batch_variantes_by_type_preparation(
        self, tp_ids: list[int]
    ) -> dict[int, list[VariantePlat]]:
        unique = list(set(tp_ids))
        if not unique:
            return {}
        stmt = select(VariantePlat).where(
            VariantePlat.type_preparation_id.in_(unique),
            VariantePlat.is_active.is_(True),
        )
        result = await self._db.execute(stmt)
        out: dict[int, list] = {}
        for v in result.scalars():
            out.setdefault(v.type_preparation_id, []).append(v)
        return out

    async def _batch_ingredients(
        self, ids: list[int]
    ) -> dict[int, IngredientRestaurant]:
        unique = list(set(ids))
        if not unique:
            return {}
        stmt = select(IngredientRestaurant).where(
            IngredientRestaurant.id.in_(unique),
            IngredientRestaurant.is_active.is_(True),
        )
        result = await self._db.execute(stmt)
        return {i.id: i for i in result.scalars()}
