"""Service — InstancePreparation (marmites restaurant).

`portions_restantes` lu directement DB (ADR-14) — jamais mis en cache.
Ajustement de portions : SELECT FOR UPDATE + validation métier.

Enrichissement R1 :
  - statut_badge : dispo | faible | epuise (calculé vs seuil_alerte_portions)
  - est_fraiche  : date_cuisine == today()
  - proteines_disponibles : ingrédients protéines avec stock_badge
  - heure_lancement : created_at de l'instance
  - created_by_nom : full_name du créateur
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.restaurant.categorie_ingredient import CategorieIngredient
from app.models.restaurant.variante_plat import VariantePlat
from app.models.account import Account
from app.repositories.restaurant.alerte_stock import AsyncAlerteStockRepo
from app.repositories.restaurant.ingredient import AsyncIngredientRepo
from app.repositories.restaurant.instance_preparation import AsyncInstancePreparationRepo
from app.repositories.restaurant.mouvement_stock import AsyncMouvementStockRepo
from app.repositories.restaurant.type_preparation import (
    AsyncRecetteTypePreparationRepo,
    AsyncTypePreparationRepo,
)
from app.schemas.restaurant.instance_preparation import (
    AjustPortionsRequest,
    InstancePreparationCreate,
    InstancePreparationResponse,
    ProteineDisponibleResponse,
)
from app.services.restaurant.exceptions import PortionsInsuffisantes, StockRequisInsuffisant


def _statut_badge(portions_restantes: int, tp) -> str:
    """R1 : dispo | faible | epuise selon seuil_alerte_portions du TypePreparation."""
    if portions_restantes == 0:
        return "epuise"
    seuil = getattr(tp, "seuil_alerte_portions", None) if tp else None
    if seuil and portions_restantes <= seuil:
        return "faible"
    return "dispo"


def _stock_badge(stock_actuel: float, stock_alerte: float) -> str:
    """R1 : full | low | out pour stock ingrédient protéine."""
    if stock_actuel <= 0:
        return "out"
    if stock_alerte > 0 and stock_actuel <= stock_alerte:
        return "low"
    return "full"


def _to_response(
    obj, tp, created_by_nom: Optional[str] = None,
    proteines: Optional[list] = None,
) -> InstancePreparationResponse:
    portions_initiales = obj.portions_initiales or 1
    pourcentage = round(obj.portions_restantes * 100 / portions_initiales)
    return InstancePreparationResponse(
        instance_id=obj.id,
        type_preparation_id=obj.type_preparation_id,
        type_preparation_nom=tp.nom if tp else "—",
        date_cuisine=obj.date_cuisine,
        heure_lancement=obj.created_at,
        created_by_nom=created_by_nom,
        portions_initiales=obj.portions_initiales,
        portions_restantes=obj.portions_restantes,
        pourcentage_restant=pourcentage,
        statut_badge=_statut_badge(obj.portions_restantes, tp),
        est_fraiche=(obj.date_cuisine == date.today()),
        proteines_disponibles=proteines or [],
    )


class InstancePreparationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AsyncInstancePreparationRepo(db)
        self._tp_repo = AsyncTypePreparationRepo(db)
        self._recette_repo = AsyncRecetteTypePreparationRepo(db)
        self._ing_repo = AsyncIngredientRepo(db)
        self._mouv_repo = AsyncMouvementStockRepo(db)
        self._alerte_repo = AsyncAlerteStockRepo(db)

    async def create(
        self, payload: InstancePreparationCreate, created_by_id: Optional[int] = None
    ) -> InstancePreparationResponse:
        tp = await self._tp_repo.get_by_id(payload.type_preparation_id)
        if tp is None:
            raise NotFound("TypePreparation")
        await self._verifier_et_consommer_recette(
            payload.type_preparation_id, payload.portions_initiales
        )
        obj = await self._repo.create(
            type_preparation_id=payload.type_preparation_id,
            portions_initiales=payload.portions_initiales,
            portions_restantes=payload.portions_initiales,
            date_cuisine=payload.date_cuisine,
            notes=payload.notes,
            created_by_id=created_by_id,
        )
        return await self._enrichir(obj, tp)

    async def _verifier_et_consommer_recette(
        self, tp_id: int, nb_portions: int
    ) -> None:
        """Vérifie et consomme les stocks de la recette (SELECT FOR UPDATE par ingrédient).

        Formule de consommation :
            qte_requise = quantite_par_batch × (nb_portions / portions_par_batch)
        """
        tp = await self._tp_repo.get_by_id(tp_id)
        if tp is None:
            raise NotFound("TypePreparation")
        if tp.portions_par_batch <= 0:
            raise ValueError(f"TypePreparation {tp_id} a portions_par_batch <= 0")

        recette = await self._recette_repo.list_by_type_preparation(tp_id)
        now = datetime.now(timezone.utc)
        ratio = Decimal(nb_portions) / Decimal(tp.portions_par_batch)

        for ligne in recette:
            qtite_requise = Decimal(str(ligne.quantite_par_batch)) * ratio
            ing = await self._ing_repo.get_by_id_lock(ligne.ingredient_id)
            if ing is None:
                raise NotFound("IngredientRestaurant")
            stock_actuel = Decimal(str(ing.stock_actuel))
            if stock_actuel < qtite_requise:
                raise StockRequisInsuffisant(
                    f"Ingrédient {ing.nom} : {stock_actuel} dispo, {qtite_requise} requis"
                )
            nouveau_stock = stock_actuel - qtite_requise
            ing.stock_actuel = nouveau_stock
            await self._mouv_repo.create(
                ingredient_id=ing.id,
                type_mouvement="consommation",
                quantite=-qtite_requise,
                stock_apres=nouveau_stock,
                date_mouvement=now,
            )
            await self._db.flush()
            stock_alerte = Decimal(str(ing.stock_alerte))
            await self._gerer_alertes_ingredient(ing.id, nouveau_stock, stock_alerte)

    async def _gerer_alertes_ingredient(
        self, ing_id: int, nouveau_stock: Decimal, stock_alerte: Decimal
    ) -> None:
        _zero = Decimal("0")
        if nouveau_stock <= _zero:
            if await self._alerte_repo.get_active_by_entite("ingredient", ing_id) is None:
                await self._alerte_repo.create("ingredient", ing_id, "zero")
        elif stock_alerte > _zero and nouveau_stock <= stock_alerte:
            if await self._alerte_repo.get_active_by_entite("ingredient", ing_id) is None:
                await self._alerte_repo.create("ingredient", ing_id, "bas")
        else:
            await self._alerte_repo.resoudre_by_entite("ingredient", ing_id)

    async def get_by_id(self, inst_id: int) -> InstancePreparationResponse:
        obj = await self._repo.get_by_id(inst_id)
        if obj is None:
            raise NotFound("InstancePreparation")
        tp = await self._tp_repo.get_by_id(obj.type_preparation_id)
        return await self._enrichir(obj, tp)

    async def list_by_date(
        self, date_cuisine: date, page: int = 1, per_page: int = 20
    ) -> tuple[list[InstancePreparationResponse], int]:
        items, total = await self._repo.list_by_date(date_cuisine, page, per_page)
        result = []
        for obj in items:
            tp = await self._tp_repo.get_by_id(obj.type_preparation_id)
            result.append(await self._enrichir(obj, tp))
        return result, total

    async def ajuster_portions(
        self, inst_id: int, payload: AjustPortionsRequest
    ) -> InstancePreparationResponse:
        """PATCH portions — SELECT FOR UPDATE, validation, alerte si épuisé (ADR-14)."""
        obj = await self._repo.get_by_id_lock(inst_id)
        if obj is None:
            raise NotFound("InstancePreparation")
        nouvelles = obj.portions_restantes + payload.ajustement
        if nouvelles < 0:
            raise PortionsInsuffisantes(
                f"Portions restantes ({obj.portions_restantes}) insuffisantes pour ajustement {payload.ajustement}"
            )
        obj.portions_restantes = nouvelles
        await self._gerer_alertes(inst_id, nouvelles)
        tp = await self._tp_repo.get_by_id(obj.type_preparation_id)
        return await self._enrichir(obj, tp)

    async def _gerer_alertes(self, inst_id: int, portions_restantes: int) -> None:
        if portions_restantes == 0:
            alerte = await self._alerte_repo.get_active_by_entite("instance_preparation", inst_id)
            if alerte is None:
                await self._alerte_repo.create("instance_preparation", inst_id, "zero")
        else:
            await self._alerte_repo.resoudre_by_entite("instance_preparation", inst_id)

    # ── Enrichissement R1 ─────────────────────────────────────────────────────

    async def _enrichir(self, obj, tp) -> InstancePreparationResponse:
        created_by_nom = await self._get_created_by_nom(getattr(obj, "created_by_id", None))
        proteines = await self._charger_proteines(obj.type_preparation_id) if tp else []
        return _to_response(obj, tp, created_by_nom, proteines)

    async def _get_created_by_nom(self, user_id: Optional[int]) -> Optional[str]:
        if not user_id:
            return None
        account = (await self._db.execute(
            select(Account).where(Account.id == user_id)
        )).scalar_one_or_none()
        return account.full_name if account else None

    async def _charger_proteines(self, tp_id: int) -> list[ProteineDisponibleResponse]:
        """Charge les ingrédients protéines associés au TypePreparation — R1."""
        recette = await self._recette_repo.list_by_type_preparation(tp_id)
        result = []
        for ligne in recette:
            ing = await self._ing_repo.get_by_id(ligne.ingredient_id)
            if ing is None or not ing.categorie_id:
                continue
            cat = (await self._db.execute(
                select(CategorieIngredient).where(CategorieIngredient.id == ing.categorie_id)
            )).scalar_one_or_none()
            if cat is None or not cat.is_proteine:
                continue
            var = (await self._db.execute(
                select(VariantePlat).where(
                    VariantePlat.ingredient_proteine_id == ing.id,
                    VariantePlat.is_active.is_(True),
                )
            )).scalars().first()
            result.append(ProteineDisponibleResponse(
                ingredient_id=ing.id,
                nom=ing.nom,
                stock_actuel_kg=float(ing.stock_actuel),
                stock_badge=_stock_badge(float(ing.stock_actuel), float(ing.stock_alerte)),
                unite_stock=ing.unite_stock,
                variante_plat_id=var.id if var else None,
                variante_nom=var.nom if var else None,
                prix_vente_cts=var.prix_vente_cts if var else None,
            ))
        return result
