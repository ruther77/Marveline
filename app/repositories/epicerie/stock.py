"""Repository EpicerieStock + EpicerieStockMovement."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.epicerie.stock import EpicerieStock
from app.models.epicerie.stock_movement import EpicerieStockMovement
from app.models.epicerie.produit import EpicerieProduit

_SEUIL_BAS_RATIO = 1.0  # quantite <= seuil_alerte → stock bas


class AsyncEpicerieStockRepository:
    """Repository async pour EpicerieStock et EpicerieStockMovement."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Stock courant ──────────────────────────────────────────────────────

    async def get_by_produit(
        self, produit_id: int, tenant_id: int
    ) -> Optional[EpicerieStock]:
        result = await self._db.execute(
            select(EpicerieStock).where(
                EpicerieStock.produit_id == produit_id,
                EpicerieStock.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, produit_id: int, tenant_id: int) -> EpicerieStock:
        stock = await self.get_by_produit(produit_id, tenant_id)
        if stock is None:
            stock = EpicerieStock(
                produit_id=produit_id, tenant_id=tenant_id,
                quantite=0, seuil_alerte=0,
            )
            self._db.add(stock)
            await self._db.flush()
        return stock

    async def get_by_produit_ids(
        self, produit_ids: list[int], tenant_id: int
    ) -> dict[int, EpicerieStock]:
        """Charge les stocks de plusieurs produits en une requête. Retourne {produit_id: stock}."""
        if not produit_ids:
            return {}
        result = await self._db.execute(
            select(EpicerieStock).where(
                EpicerieStock.produit_id.in_(produit_ids),
                EpicerieStock.tenant_id == tenant_id,
            )
        )
        return {s.produit_id: s for s in result.scalars().all()}

    async def get_or_create_batch(
        self, produit_ids: list[int], tenant_id: int
    ) -> dict[int, EpicerieStock]:
        """Charge ou crée les stocks pour une liste de produit_ids. 1 SELECT + N INSERT max."""
        existing = await self.get_by_produit_ids(produit_ids, tenant_id)
        missing = [pid for pid in produit_ids if pid not in existing]
        for pid in missing:
            stock = EpicerieStock(
                produit_id=pid, tenant_id=tenant_id,
                quantite=0, seuil_alerte=0,
            )
            self._db.add(stock)
            existing[pid] = stock
        if missing:
            await self._db.flush()
        return existing

    async def list_with_produit(
        self,
        tenant_id: int,
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None,
        categorie: Optional[str] = None,
        vendor_id: Optional[int] = None,
        is_low: Optional[bool] = None,
        is_empty: Optional[bool] = None,
    ) -> tuple[list[tuple[EpicerieProduit, Optional[EpicerieStock]]], int]:
        """LEFT JOIN produit → stock : les produits sans stock apparaissent avec quantite=0."""
        from sqlalchemy import or_
        q = (
            select(EpicerieProduit, EpicerieStock)
            .outerjoin(
                EpicerieStock,
                and_(
                    EpicerieStock.produit_id == EpicerieProduit.id,
                    EpicerieStock.tenant_id == tenant_id,
                ),
            )
            .where(
                EpicerieProduit.tenant_id == tenant_id,
                EpicerieProduit.actif.is_(True),
            )
        )
        if search:
            # Recherche tokenisée pour éviter les "faux négatifs" sur
            # les désignations longues et permettre un lookup par EAN.
            tokens = [token.strip() for token in search.split() if token.strip()]
            for token in tokens:
                like = f"%{token}%"
                q = q.where(or_(
                    EpicerieProduit.designation_clean.ilike(like),
                    EpicerieProduit.nom_court.ilike(like),
                    EpicerieProduit.ean.ilike(like),
                ))
        if categorie:
            q = q.where(EpicerieProduit.categorie == categorie)
        if vendor_id is not None:
            q = q.where(EpicerieProduit.vendor_id == vendor_id)
        # COALESCE nécessaire : stock NULL (produit sans entrée) traité comme quantite=0
        if is_empty is True:
            q = q.where(func.coalesce(EpicerieStock.quantite, 0) <= 0)
        elif is_low is True:
            q = q.where(
                func.coalesce(EpicerieStock.quantite, 0) > 0,
                func.coalesce(EpicerieStock.quantite, 0) <= func.coalesce(EpicerieStock.seuil_alerte, 0),
            )

        total_result = await self._db.execute(
            select(func.count()).select_from(q.subquery())
        )
        total = total_result.scalar_one()

        items_result = await self._db.execute(
            q.order_by(EpicerieProduit.designation_clean)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        # Retourne (EpicerieProduit, EpicerieStock | None) — ordre inversé vs ancienne version
        return [(row[0], row[1]) for row in items_result.all()], total

    async def summary(self, tenant_id: int) -> dict:
        """Résumé stock : total_articles, nb_ruptures, nb_stock_bas, valeur_stock_cts."""
        result = await self._db.execute(
            select(
                func.count().label("total"),
                func.count().filter(EpicerieStock.quantite <= 0).label("ruptures"),
                func.count().filter(
                    and_(
                        EpicerieStock.quantite > 0,
                        EpicerieStock.quantite <= EpicerieStock.seuil_alerte,
                    )
                ).label("bas"),
                func.coalesce(
                    func.sum(
                        EpicerieStock.quantite * EpicerieProduit.prix_unitaire_cts
                    ), 0
                ).label("valeur"),
            )
            .select_from(EpicerieStock)
            .join(EpicerieProduit, EpicerieStock.produit_id == EpicerieProduit.id)
            .where(
                EpicerieStock.tenant_id == tenant_id,
                EpicerieProduit.actif.is_(True),
            )
        )
        row = result.one()
        return {
            "total_articles": row.total,
            "nb_ruptures": row.ruptures,
            "nb_stock_bas": row.bas,
            "valeur_stock_cts": int(row.valeur),
        }

    async def update_quantite(
        self, stock: EpicerieStock, delta: float
    ) -> EpicerieStock:
        """Met à jour quantite += delta (delta peut être négatif)."""
        stock.quantite = float(stock.quantite) + float(delta)
        await self._db.flush()
        return stock

    async def set_seuil(
        self, stock: EpicerieStock, seuil: float
    ) -> EpicerieStock:
        stock.seuil_alerte = seuil
        await self._db.flush()
        return stock

    # ── Mouvements de stock ────────────────────────────────────────────────

    async def create_movement(
        self,
        tenant_id: int,
        produit_id: int,
        type: str,
        quantite: float,
        stock_apres: float,
        date_mouvement: Optional[datetime] = None,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
        created_by_id: Optional[int] = None,
        vente_id: Optional[int] = None,
        supply_order_id: Optional[int] = None,
        transfer_id: Optional[int] = None,
        etl_import_id: Optional[int] = None,
    ) -> EpicerieStockMovement:
        mvt = EpicerieStockMovement(
            tenant_id=tenant_id,
            produit_id=produit_id,
            type=type,
            quantite=quantite,
            stock_apres=stock_apres,
            date_mouvement=date_mouvement or datetime.now(timezone.utc),
            reference=reference,
            notes=notes,
            created_by_id=created_by_id,
            vente_id=vente_id,
            supply_order_id=supply_order_id,
            transfer_id=transfer_id,
            etl_import_id=etl_import_id,
        )
        self._db.add(mvt)
        await self._db.flush()
        return mvt

    async def list_movements(
        self,
        tenant_id: int,
        produit_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[EpicerieStockMovement], int]:
        q = select(EpicerieStockMovement).where(
            EpicerieStockMovement.tenant_id == tenant_id
        )
        if produit_id is not None:
            q = q.where(EpicerieStockMovement.produit_id == produit_id)

        total_result = await self._db.execute(
            select(func.count()).select_from(q.subquery())
        )
        total = total_result.scalar_one()

        items_result = await self._db.execute(
            q.order_by(EpicerieStockMovement.date_mouvement.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(items_result.scalars().all()), total
