"""Service IngredientSourcing — Résolveur cascade mixte pour réapprovisionnement.

Pour un ingrédient restaurant et une quantité besoin donnés, retourne la
liste ordonnée des prélèvements à effectuer sur les produits épicerie
sources (tels que définis dans `IngredientEpicerieMapping`).

Cascade mixte (ADR — 2026-04-21) :
  - Parcourir les mappings triés par `ordre` (0 = préféré)
  - Pour chaque produit, lire le stock épicerie disponible (unité vente)
  - Convertir en unité stock ingrédient via `facteur_conv`
  - Cumuler les prélèvements jusqu'à couvrir la quantité besoin
  - Passer au suivant en cas de rupture partielle (pas d'attente, pas de
    fallback unique : cumul de plusieurs produits autorisé et préféré)

Sortie : ResolveResponse avec flag `couverture_complete` + `deficit` si non.
"""
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyExists, NotFound
from app.models.epicerie.produit import EpicerieProduit
from app.models.epicerie.stock import EpicerieStock
from app.models.restaurant.ingredient_epicerie_mapping import IngredientEpicerieMapping
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.repositories.restaurant.ingredient_epicerie_mapping import (
    AsyncIngredientEpicerieMappingRepo,
)
from app.schemas.restaurant.ingredient_epicerie_mapping import (
    MappingCreate,
    MappingReorderRequest,
    MappingUpdate,
    MappingWithProduit,
    ResolveItem,
    ResolveResponse,
)


class IngredientSourcingService:
    """Résolveur stateless : lit le mapping + stocks épicerie et produit une
    proposition de prélèvement. N'écrit rien en base.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _load_ingredient(
        self, ingredient_id: int, tenant_id: int,
    ) -> Optional[IngredientRestaurant]:
        stmt = select(IngredientRestaurant).where(
            IngredientRestaurant.id == ingredient_id,
            IngredientRestaurant.tenant_id == tenant_id,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def _load_mappings_with_stock(
        self, ingredient_id: int, tenant_id: int,
    ) -> list[tuple[IngredientEpicerieMapping, EpicerieProduit, Decimal]]:
        """Jointure mappings × produits × stock, triée par ordre.

        Renvoie stock = 0 si aucune entrée EpicerieStock n'existe pour le produit
        (un produit sans stock ligne est considéré comme rupture).
        """
        stmt = (
            select(IngredientEpicerieMapping, EpicerieProduit, EpicerieStock.quantite)
            .join(EpicerieProduit, EpicerieProduit.id == IngredientEpicerieMapping.produit_id)
            .outerjoin(EpicerieStock, EpicerieStock.produit_id == EpicerieProduit.id)
            .where(
                IngredientEpicerieMapping.ingredient_id == ingredient_id,
                IngredientEpicerieMapping.tenant_id == tenant_id,
            )
            .order_by(
                IngredientEpicerieMapping.ordre.asc(),
                IngredientEpicerieMapping.id.asc(),
            )
        )
        result = []
        for row in (await self._db.execute(stmt)).all():
            mapping, produit, stock_qte = row
            result.append((mapping, produit, Decimal(stock_qte or 0)))
        return result

    async def resolve(
        self, ingredient_id: int, qte_besoin: Decimal, tenant_id: int,
    ) -> ResolveResponse:
        """Résout le besoin en cascade mixte.

        Raises:
            ValueError: ingrédient non trouvé ou cross-tenant.
        """
        ingredient = await self._load_ingredient(ingredient_id, tenant_id)
        if ingredient is None:
            raise ValueError(
                f"Ingrédient {ingredient_id} introuvable pour tenant {tenant_id}"
            )

        rows = await self._load_mappings_with_stock(ingredient_id, tenant_id)

        besoin_restant = Decimal(qte_besoin)
        items: list[ResolveItem] = []
        couverture_totale = Decimal("0")

        for mapping, produit, stock_dispo in rows:
            if besoin_restant <= 0:
                break
            if stock_dispo <= 0:
                continue

            facteur = Decimal(mapping.facteur_conv)
            # Combien d'unités stock ingrédient ce produit peut fournir max
            capacite_ingredient = stock_dispo * facteur
            # On prélève le minimum (besoin restant, capacité dispo)
            couverture = min(besoin_restant, capacite_ingredient)
            # Conversion inverse : unités vente à prélever
            qte_prelevee_vente = couverture / facteur

            items.append(
                ResolveItem(
                    produit_id=produit.id,
                    produit_designation=produit.designation_clean,
                    produit_unite_vente=produit.unite_vente,
                    ordre=mapping.ordre,
                    facteur_conv=facteur,
                    stock_disponible=stock_dispo,
                    qte_prelevee_unites_vente=qte_prelevee_vente,
                    qte_couverte_besoin=couverture,
                )
            )
            couverture_totale += couverture
            besoin_restant -= couverture

        deficit = max(Decimal("0"), Decimal(qte_besoin) - couverture_totale)
        return ResolveResponse(
            ingredient_id=ingredient_id,
            qte_besoin=Decimal(qte_besoin),
            qte_couverte_totale=couverture_totale,
            deficit=deficit,
            couverture_complete=deficit == 0,
            items=items,
        )

    # ── CRUD mappings ────────────────────────────────────────────────────

    async def list_mappings(
        self, ingredient_id: int, tenant_id: int,
    ) -> list[MappingWithProduit]:
        """Liste enrichie (jointure produit + stock) triée par ordre."""
        ingr = await self._load_ingredient(ingredient_id, tenant_id)
        if ingr is None:
            raise NotFound("Ingrédient")

        rows = await self._load_mappings_with_stock(ingredient_id, tenant_id)
        return [
            MappingWithProduit(
                id=mapping.id,
                tenant_id=mapping.tenant_id,
                ingredient_id=mapping.ingredient_id,
                produit_id=mapping.produit_id,
                ordre=mapping.ordre,
                facteur_conv=Decimal(mapping.facteur_conv),
                notes=mapping.notes,
                created_at=mapping.created_at,
                updated_at=mapping.updated_at,
                produit_designation=produit.designation_clean,
                produit_unite_vente=produit.unite_vente,
                produit_stock_disponible=stock_qte,
            )
            for mapping, produit, stock_qte in rows
        ]

    async def _assert_produit_exists(self, produit_id: int) -> EpicerieProduit:
        stmt = select(EpicerieProduit).where(EpicerieProduit.id == produit_id)
        prod = (await self._db.execute(stmt)).scalar_one_or_none()
        if prod is None:
            raise NotFound("Produit épicerie")
        return prod

    async def add_mapping(
        self, ingredient_id: int, tenant_id: int, payload: MappingCreate,
    ) -> IngredientEpicerieMapping:
        ingr = await self._load_ingredient(ingredient_id, tenant_id)
        if ingr is None:
            raise NotFound("Ingrédient")
        await self._assert_produit_exists(payload.produit_id)

        repo = AsyncIngredientEpicerieMappingRepo(self._db)
        try:
            return await repo.create(
                tenant_id=tenant_id,
                ingredient_id=ingredient_id,
                produit_id=payload.produit_id,
                ordre=payload.ordre,
                facteur_conv=payload.facteur_conv,
                notes=payload.notes,
            )
        except IntegrityError as exc:
            await self._db.rollback()
            raise AlreadyExists(
                "Ce produit est déjà mappé sur cet ingrédient."
            ) from exc

    async def update_mapping(
        self, ingredient_id: int, produit_id: int, tenant_id: int,
        payload: MappingUpdate,
    ) -> IngredientEpicerieMapping:
        repo = AsyncIngredientEpicerieMappingRepo(self._db)
        mapping = await repo.get(ingredient_id, produit_id, tenant_id)
        if mapping is None:
            raise NotFound("Mapping")
        return await repo.update(
            mapping,
            ordre=payload.ordre,
            facteur_conv=payload.facteur_conv,
            notes=payload.notes,
        )

    async def remove_mapping(
        self, ingredient_id: int, produit_id: int, tenant_id: int,
    ) -> None:
        repo = AsyncIngredientEpicerieMappingRepo(self._db)
        mapping = await repo.get(ingredient_id, produit_id, tenant_id)
        if mapping is None:
            raise NotFound("Mapping")
        await repo.delete(mapping)

    async def reorder_mappings(
        self, ingredient_id: int, tenant_id: int, payload: MappingReorderRequest,
    ) -> list[IngredientEpicerieMapping]:
        """Met à jour l'ordre de plusieurs mappings en batch.

        Chaque produit_id doit référencer un mapping existant pour cet ingrédient.
        Les mappings non mentionnés gardent leur ordre actuel.
        """
        repo = AsyncIngredientEpicerieMappingRepo(self._db)
        ingr = await self._load_ingredient(ingredient_id, tenant_id)
        if ingr is None:
            raise NotFound("Ingrédient")

        for item in payload.items:
            mapping = await repo.get(ingredient_id, item.produit_id, tenant_id)
            if mapping is None:
                raise NotFound(f"Mapping pour produit_id={item.produit_id}")
            mapping.ordre = item.ordre
        await self._db.flush()
        return await repo.list_by_ingredient(ingredient_id, tenant_id)
