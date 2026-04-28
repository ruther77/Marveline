"""Service — LigneCommandeRestaurant.

Atomicité POST /lignes (tout-ou-rien dans la transaction) :
  1. Vérifier commande OUVERTE
  2. Charger VariantePlat (snapshot prix)
  3. Si instance_preparation_id → décrément portions (SELECT FOR UPDATE, ADR-14)
  4. Si variante.ingredient_proteine_id → consommation stock (SELECT FOR UPDATE)
  5. Si side_id et side.ingredient_id → consommation stock (SELECT FOR UPDATE)
  6. INSERT LigneCommande (statut ENVOYEE)
  7. Suggestion formule si type=boisson et total × 3 dans la commande

Validation stock avant consommation → StockIngredientInsuffisant si stock < requis.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.restaurant.commande_restaurant import CommandeRestaurant
from app.models.restaurant.instance_preparation import InstancePreparation
from app.models.restaurant.side_restaurant import SideRestaurant
from app.models.restaurant.table_restaurant import TableRestaurant
from app.models.restaurant.variante_side import VarianteSide
from app.models.restaurant.variante_plat import VariantePlat
from app.repositories.restaurant.alerte_stock import AsyncAlerteStockRepo
from app.repositories.restaurant.commande import AsyncCommandeRepo
from app.repositories.restaurant.ingredient import AsyncIngredientRepo
from app.repositories.restaurant.instance_preparation import AsyncInstancePreparationRepo
from app.repositories.restaurant.ligne_commande import AsyncLigneCommandeRepo
from app.repositories.restaurant.mouvement_stock import AsyncMouvementStockRepo
from app.repositories.restaurant.side import AsyncSideRepo
from app.repositories.restaurant.variante_plat import AsyncVariantePlatRepo
from app.schemas.restaurant.commande import CommandeDetail
from app.schemas.restaurant.ligne_commande import (
    BoissonsTicket,
    BoissonsTicketLigne,
    BoissonsTicketResponse,
    LigneCommandeCreate,
    LigneCommandeCreateResponse,
    LigneCommandeResponse,
    MarquerPretRequest,
    MarquerPretResponse,
    StatutLigneUpdate,
    SuggestionFormule,
    TicketCuisineLigne,
    TicketCuisineResponse,
    TicketCuisineTicket,
)
from app.services.restaurant.exceptions import (
    CommandeNonOuverte,
    LigneNonAnnulable,
    PortionsEpuisees,
    StockIngredientInsuffisant,
)

_ZERO = Decimal("0")
_STATUTS_NON_ANNULABLES = frozenset({"PRETE", "SERVIE"})


class LigneCommandeService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._ligne_repo = AsyncLigneCommandeRepo(db)
        self._cmd_repo = AsyncCommandeRepo(db)
        self._var_repo = AsyncVariantePlatRepo(db)
        self._side_repo = AsyncSideRepo(db)
        self._inst_repo = AsyncInstancePreparationRepo(db)
        self._ing_repo = AsyncIngredientRepo(db)
        self._mouv_repo = AsyncMouvementStockRepo(db)
        self._alerte_repo = AsyncAlerteStockRepo(db)

    async def create_ligne(
        self, commande_id: int, payload: LigneCommandeCreate, created_by_id: Optional[int] = None
    ) -> LigneCommandeCreateResponse:
        cmd = await self._cmd_repo.get_by_id(commande_id)
        if cmd is None:
            raise NotFound("CommandeRestaurant")
        if cmd.statut != "OUVERTE":
            raise CommandeNonOuverte("La commande n'est pas ouverte")
        var = await self._var_repo.get_by_id(payload.variante_plat_id)
        if var is None:
            raise NotFound("VariantePlat")
        if payload.instance_preparation_id:
            await self._decrire_instance(payload.instance_preparation_id, payload.quantite)
        await self._consommer_stocks(var, payload)
        # Calculer le prix unitaire avec supplément side
        prix_unitaire = var.prix_vente_cts
        if payload.side_id:
            supplement = await self._get_side_supplement(
                payload.variante_plat_id, payload.side_id
            )
            prix_unitaire += supplement
        ligne = await self._ligne_repo.create(
            commande_id=commande_id,
            variante_id=payload.variante_plat_id,
            quantite=payload.quantite,
            prix_unitaire_cts=prix_unitaire,
            instance_preparation_id=payload.instance_preparation_id,
            side_id=payload.side_id,
            notes=payload.notes,
        )
        suggestion = await self._suggestion_formule(commande_id, var, payload.quantite)
        return LigneCommandeCreateResponse(
            ligne_id=ligne.id,
            variante_nom=var.nom,
            statut_plat=ligne.statut_plat,
            prix_unitaire_cts=prix_unitaire,
            suggestion_formule=suggestion,
        )

    async def update_statut(
        self, ligne_id: int, payload: StatutLigneUpdate
    ) -> LigneCommandeResponse:
        ligne = await self._ligne_repo.update_statut(ligne_id, payload.statut)
        if ligne is None:
            raise NotFound("LigneCommandeRestaurant")
        var = await self._var_repo.get_by_id(ligne.variante_id)
        side = await self._side_repo.get_by_id(ligne.side_id) if ligne.side_id else None
        return self._to_response(ligne, var, side)

    async def marquer_pret(
        self, commande_id: int, payload: MarquerPretRequest
    ) -> MarquerPretResponse:
        lignes = await self._ligne_repo.list_by_commande(commande_id)
        total_demandees = len(payload.ligne_ids) if payload.ligne_ids is not None else len(lignes)
        cibles = [
            l for l in lignes
            if l.statut_plat in ("ENVOYEE", "LANCEE")
            and (payload.ligne_ids is None or l.id in payload.ligne_ids)
        ]
        nb_mises_a_jour = 0
        for l in cibles:
            updated = await self._ligne_repo.update_statut(l.id, "PRETE")
            if updated:
                nb_mises_a_jour += 1
        return MarquerPretResponse(
            commande_id=commande_id,
            lignes_mises_a_jour=nb_mises_a_jour,
            lignes_ignorees=total_demandees - nb_mises_a_jour,
        )

    async def marquer_servi(
        self, commande_id: int, payload: MarquerPretRequest
    ) -> MarquerPretResponse:
        """Transition PRETE -> SERVIE pour les lignes d'une commande."""
        lignes = await self._ligne_repo.list_by_commande(commande_id)
        total_demandees = len(payload.ligne_ids) if payload.ligne_ids is not None else len(lignes)
        cibles = [
            l for l in lignes
            if l.statut_plat == "PRETE"
            and (payload.ligne_ids is None or l.id in payload.ligne_ids)
        ]
        nb_mises_a_jour = 0
        for l in cibles:
            updated = await self._ligne_repo.update_statut(l.id, "SERVIE")
            if updated:
                nb_mises_a_jour += 1
        return MarquerPretResponse(
            commande_id=commande_id,
            lignes_mises_a_jour=nb_mises_a_jour,
            lignes_ignorees=total_demandees - nb_mises_a_jour,
        )

    async def delete(self, ligne_id: int) -> None:
        ligne = await self._ligne_repo.get_by_id(ligne_id)
        if ligne is None:
            raise NotFound("LigneCommandeRestaurant")
        if ligne.statut_plat in _STATUTS_NON_ANNULABLES:
            raise LigneNonAnnulable(f"Ligne en statut {ligne.statut_plat} non annulable")
        await self._ligne_repo.delete(ligne_id)

    async def get_ticket_cuisine(
        self, date_cuisine=None
    ) -> TicketCuisineResponse:
        """Ticket cuisine groupé par commande — R2 (FC_RESTAURANT_CUISINE.md §GET /tickets-cuisine)."""
        lignes = await self._ligne_repo.list_ticket_cuisine(date_cuisine)
        if not lignes:
            return TicketCuisineResponse(items=[])
        cmd_map = await self._batch_commandes([l.commande_id for l in lignes])
        table_map = await self._batch_tables(
            [c.table_id for c in cmd_map.values() if c.table_id]
        )
        var_map = await self._batch_variantes([l.variante_id for l in lignes])
        side_map = await self._batch_sides([l.side_id for l in lignes if l.side_id])
        inst_map = await self._batch_instances(
            [l.instance_preparation_id for l in lignes if l.instance_preparation_id]
        )
        tickets = self._grouper_en_tickets_cuisine(
            lignes, cmd_map, table_map, var_map, side_map, inst_map
        )
        return TicketCuisineResponse(items=tickets)

    async def get_ticket_bar(self) -> BoissonsTicketResponse:
        """Lignes boissons en attente groupées par commande (ticket bar)."""
        lignes = await self._ligne_repo.list_ticket_bar()
        if not lignes:
            return BoissonsTicketResponse(items=[])
        cmd_map = await self._batch_commandes([l.commande_id for l in lignes])
        table_map = await self._batch_tables(
            [c.table_id for c in cmd_map.values() if c.table_id]
        )
        var_map = await self._batch_variantes([l.variante_id for l in lignes])
        suggestion_map = await self._build_bar_suggestions(lignes, var_map)
        items = self._group_lignes_en_tickets(lignes, cmd_map, table_map, var_map, suggestion_map)
        return BoissonsTicketResponse(items=items)

    async def appliquer_formule(
        self, commande_id: int, variante_formule_id: int
    ) -> CommandeDetail:
        """Ajoute une ligne formule à la commande et retourne la commande actualisée."""
        from app.services.restaurant.commande import CommandeService  # lazy — évite cycle
        cmd = await self._cmd_repo.get_by_id(commande_id)
        if cmd is None:
            raise NotFound("CommandeRestaurant")
        if cmd.statut != "OUVERTE":
            raise CommandeNonOuverte("La commande n'est pas ouverte")
        formule = await self._var_repo.get_by_id(variante_formule_id)
        if formule is None or formule.type != "formule":
            raise NotFound("VariantePlat")
        await self._ligne_repo.create(
            commande_id=commande_id,
            variante_id=variante_formule_id,
            quantite=1,
            prix_unitaire_cts=formule.prix_vente_cts,
            instance_preparation_id=None,
            side_id=None,
            notes=None,
        )
        return await CommandeService(self._db).get_detail(commande_id)

    # ── helpers atomicité ──────────────────────────────────────────────────────

    async def _decrire_instance(self, inst_id: int, quantite: int) -> None:
        """Décrément atomique portions_restantes (SELECT FOR UPDATE)."""
        inst = await self._inst_repo.get_by_id_lock(inst_id)
        if inst is None:
            raise NotFound("InstancePreparation")
        nouvelles = inst.portions_restantes - quantite
        if nouvelles < 0:
            raise PortionsEpuisees(
                f"Portions insuffisantes : {inst.portions_restantes} dispo, {quantite} demandées"
            )
        inst.portions_restantes = nouvelles
        await self._db.flush()
        await self._gerer_alertes_instance(inst_id, nouvelles)

    async def _gerer_alertes_instance(self, inst_id: int, portions: int) -> None:
        if portions == 0:
            if await self._alerte_repo.get_active_by_entite("instance_preparation", inst_id) is None:
                await self._alerte_repo.create("instance_preparation", inst_id, "zero")
        else:
            await self._alerte_repo.resoudre_by_entite("instance_preparation", inst_id)

    async def _get_side_supplement(self, variante_plat_id: int, side_id: int) -> int:
        """Retourne le supplément du side pour ce plat (0 si pas de liaison configurée)."""
        stmt = select(VarianteSide.supplement_cts).where(
            VarianteSide.variante_plat_id == variante_plat_id,
            VarianteSide.side_id == side_id,
            VarianteSide.is_active.is_(True),
        )
        result = await self._db.execute(stmt)
        row = result.scalar_one_or_none()
        return row or 0

    async def _consommer_stocks(self, var: VariantePlat, payload: LigneCommandeCreate) -> None:
        """Consomme les stocks selon la variante et l'accompagnement.

        Ordre de consommation :
        1. Marmite (instance_preparation_id) → décrément portions (fait en amont dans create_ligne)
        2. Protéine (ingredient_proteine_id) → 1 ingrédient spécifique
        3. Side (side_id) → ingrédient de l'accompagnement

        Note : la recette de la base cuisinée est consommée au LANCEMENT de la marmite,
        pas à la commande. La commande retire juste 1 portion de la marmite.
        """
        # 1. Protéine (ex: Bœuf pour Gombo Viande, Heineken pour formule bière)
        if var.ingredient_proteine_id and var.quantite_proteine:
            qtite = Decimal(str(var.quantite_proteine)) * payload.quantite
            await self._consommer_ingredient(var.ingredient_proteine_id, qtite)

        # 2. Side (ex: Riz blanc → stock riz, Frites → stock pommes de terre)
        if not payload.side_id:
            return
        side = await self._side_repo.get_by_id(payload.side_id)
        if side is None:
            raise NotFound("SideRestaurant")
        if side.ingredient_id and side.quantite_par_portion:
            qtite = Decimal(str(side.quantite_par_portion)) * payload.quantite
            await self._consommer_ingredient(side.ingredient_id, qtite)

    async def _consommer_ingredient(self, ing_id: int, quantite: Decimal) -> None:
        """SELECT FOR UPDATE → validation stock → mouvement consommation → alertes."""
        ing = await self._ing_repo.get_by_id_lock(ing_id)
        if ing is None:
            raise NotFound("IngredientRestaurant")
        stock_actuel = Decimal(str(ing.stock_actuel))
        if stock_actuel < quantite:
            raise StockIngredientInsuffisant(
                f"Stock insuffisant : {stock_actuel} dispo, {quantite} requis"
            )
        nouveau_stock = stock_actuel - quantite
        ing.stock_actuel = nouveau_stock
        now = datetime.now(timezone.utc)
        await self._mouv_repo.create(
            ingredient_id=ing_id,
            type_mouvement="consommation",
            quantite=-quantite,
            stock_apres=nouveau_stock,
            date_mouvement=now,
        )
        await self._db.flush()
        await self._gerer_alertes_ingredient(ing_id, nouveau_stock, Decimal(str(ing.stock_alerte)))

    async def _gerer_alertes_ingredient(
        self, ing_id: int, nouveau_stock: Decimal, stock_alerte: Decimal
    ) -> None:
        if nouveau_stock <= _ZERO:
            if await self._alerte_repo.get_active_by_entite("ingredient", ing_id) is None:
                await self._alerte_repo.create("ingredient", ing_id, "zero")
        elif stock_alerte > _ZERO and nouveau_stock <= stock_alerte:
            if await self._alerte_repo.get_active_by_entite("ingredient", ing_id) is None:
                await self._alerte_repo.create("ingredient", ing_id, "bas")
        else:
            await self._alerte_repo.resoudre_by_entite("ingredient", ing_id)

    async def _suggestion_formule(
        self, commande_id: int, variante: VariantePlat, quantite: int
    ) -> Optional[SuggestionFormule]:
        """Retourne une suggestion formule si total boissons atteint un multiple de 3."""
        if variante.type != "boisson" or variante.type_preparation_id is None:
            return None
        total = await self._ligne_repo.count_by_commande_variante(commande_id, variante.id)
        if total < 3 or total % 3 != 0:
            return None
        formules = await self._var_repo.list_actives("formule")
        formule = next(
            (f for f in formules if f.type_preparation_id == variante.type_preparation_id), None
        )
        if formule is None:
            return None
        economies_cts = variante.prix_vente_cts * 3 - formule.prix_vente_cts
        if economies_cts <= 0:
            return None
        boissons_ids = await self._ligne_repo.list_ids_by_commande_variante(commande_id, variante.id)
        return SuggestionFormule(
            variante_formule_id=formule.id,
            label=formule.nom,
            economies_cts=economies_cts,
            boissons_concernees_ids=boissons_ids,
        )

    # ── helpers présentation ──────────────────────────────────────────────────

    def _to_response(self, ligne, var, side) -> LigneCommandeResponse:
        return LigneCommandeResponse(
            ligne_id=ligne.id,
            variante_nom=var.nom if var else "—",
            side_nom=side.nom if side else None,
            instance_preparation_id=ligne.instance_preparation_id,
            statut_plat=ligne.statut_plat,
            prix_unitaire_cts=ligne.prix_unitaire_cts,
            quantite=ligne.quantite,
            notes=ligne.notes,
        )

    def _to_ticket_ligne(self, ligne, var_map, side_map, inst_map) -> TicketCuisineLigne:
        """Convertit une LigneCommande en TicketCuisineLigne avec stock_disponible — R2."""
        var = var_map.get(ligne.variante_id)
        side = side_map.get(ligne.side_id) if ligne.side_id else None
        inst = inst_map.get(ligne.instance_preparation_id) if ligne.instance_preparation_id else None
        stock_disponible = (
            ligne.instance_preparation_id is None
            or (inst is not None and inst.portions_restantes > 0)
        )
        return TicketCuisineLigne(
            ligne_id=ligne.id,
            variante_nom=var.nom if var else "—",
            side_nom=side.nom if side else None,
            statut_plat=ligne.statut_plat,
            instance_preparation_id=ligne.instance_preparation_id,
            stock_disponible=stock_disponible,
            notes=ligne.notes,
        )

    def _grouper_en_tickets_cuisine(
        self, lignes, cmd_map, table_map, var_map, side_map, inst_map
    ) -> list[TicketCuisineTicket]:
        """Groupe les lignes par commande en TicketCuisineTicket — R2."""
        groupes: dict[int, list] = {}
        for l in lignes:
            groupes.setdefault(l.commande_id, []).append(l)
        tickets = []
        for cmd_id, cmd_lignes in groupes.items():
            cmd = cmd_map.get(cmd_id)
            table = table_map.get(cmd.table_id) if (cmd and cmd.table_id) else None
            lignes_resp = [
                self._to_ticket_ligne(l, var_map, side_map, inst_map) for l in cmd_lignes
            ]
            tickets.append(TicketCuisineTicket(
                ticket_id=f"T{cmd_id}",
                commande_id=cmd_id,
                table_numero=table.numero if table else None,
                heure_envoi=cmd.created_at if cmd else None,
                lignes=lignes_resp,
            ))
        return tickets

    async def _build_bar_suggestions(
        self, lignes, var_map: dict
    ) -> dict[tuple[int, int], Optional[SuggestionFormule]]:
        """Calcule les suggestions formule par paire (commande_id, variante_id) sans N+1."""
        result: dict[tuple[int, int], Optional[SuggestionFormule]] = {}
        seen: set[tuple[int, int]] = set()
        for l in lignes:
            pair = (l.commande_id, l.variante_id)
            if pair not in seen:
                seen.add(pair)
                var = var_map.get(l.variante_id)
                result[pair] = await self._suggestion_formule(l.commande_id, var, l.quantite) if var else None
        return result

    def _group_lignes_en_tickets(
        self, lignes, cmd_map, table_map, var_map, suggestion_map
    ) -> list[BoissonsTicket]:
        """Groupe les lignes boissons par commande en BoissonsTicket."""
        groupes: dict[int, list] = {}
        for l in lignes:
            groupes.setdefault(l.commande_id, []).append(l)
        tickets = []
        for cmd_id, cmd_lignes in groupes.items():
            cmd = cmd_map.get(cmd_id)
            table = table_map.get(cmd.table_id) if (cmd and cmd.table_id) else None
            lignes_resp = []
            ticket_suggestion: Optional[SuggestionFormule] = None
            for l in cmd_lignes:
                var = var_map.get(l.variante_id)
                ligne_suggestion = suggestion_map.get((l.commande_id, l.variante_id))
                if ticket_suggestion is None and ligne_suggestion is not None:
                    ticket_suggestion = ligne_suggestion
                lignes_resp.append(BoissonsTicketLigne(
                    ligne_id=l.id,
                    variante_nom=var.nom if var else "—",
                    quantite=l.quantite,
                    prix_unitaire_cts=l.prix_unitaire_cts,
                    statut_plat=l.statut_plat,
                    notes=l.notes,
                    heure_commande=l.created_at,
                    suggestion_formule=ligne_suggestion,
                ))
            tickets.append(BoissonsTicket(
                commande_id=cmd_id,
                table_numero=table.numero if table else None,
                date_ouverture=cmd.created_at if cmd else datetime.now(timezone.utc),
                suggestion_formule=ticket_suggestion,
                lignes=lignes_resp,
            ))
        return tickets

    async def _batch_commandes(self, ids: list[int]) -> dict[int, CommandeRestaurant]:
        unique = list(set(ids))
        if not unique:
            return {}
        stmt = select(CommandeRestaurant).where(CommandeRestaurant.id.in_(unique))
        result = await self._db.execute(stmt)
        return {c.id: c for c in result.scalars()}

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

    async def _batch_tables(self, ids: list[int]) -> dict[int, TableRestaurant]:
        unique = list(set(ids))
        if not unique:
            return {}
        stmt = select(TableRestaurant).where(TableRestaurant.id.in_(unique))
        result = await self._db.execute(stmt)
        return {t.id: t for t in result.scalars()}

    async def _batch_instances(self, ids: list[int]) -> dict[int, InstancePreparation]:
        unique = list(set(ids))
        if not unique:
            return {}
        stmt = select(InstancePreparation).where(InstancePreparation.id.in_(unique))
        result = await self._db.execute(stmt)
        return {i.id: i for i in result.scalars()}
