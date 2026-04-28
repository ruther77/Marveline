"""Service Formula — CRUD + application aux réservations."""
import math
import logging
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.formula import Formula, FormulaItem
from app.models.product import Product
from app.models.reservation import Reservation, ReservationLine
from app.repositories.formula import AsyncFormulaRepository

logger = logging.getLogger(__name__)


class FormulaService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncFormulaRepository(db)

    # ── CRUD ─────────────────────────────────────────────────────────────────

    async def get_formula(self, formula_id: int, tenant_id: int) -> Formula:
        formula = await self.repo.get_by_id(formula_id, tenant_id)
        if not formula:
            raise NotFound(f"Formula {formula_id} not found")
        return formula

    async def list_formulas(
        self,
        tenant_id: int,
        formula_type: Optional[str] = None,
        featured_only: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Formula], int]:
        return await self.repo.list_formulas(
            tenant_id, formula_type, featured_only, skip=skip, limit=limit,
        )

    async def create_formula(self, tenant_id: int, data: dict) -> Formula:
        items_data = data.pop("items", [])

        existing = await self.repo.get_by_slug(data["slug"], tenant_id)
        if existing:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Formula with slug '{data['slug']}' already exists",
            )

        formula = Formula(tenant_id=tenant_id, **data)
        await self.repo.create(formula)

        for item_data in items_data:
            item = FormulaItem(
                formula_id=formula.id,
                product_id=item_data["product_id"],
                quantity_per_person=item_data["quantity_per_person"],
            )
            self.db.add(item)
        await self.db.flush()

        logger.info("Formula created: %s (tenant=%d)", formula.slug, tenant_id)
        return formula

    async def update_formula(self, formula_id: int, tenant_id: int, data: dict) -> Formula:
        formula = await self.get_formula(formula_id, tenant_id)
        items_data = data.pop("items", None)

        for key, value in data.items():
            if value is not None:
                setattr(formula, key, value)

        if items_data is not None:
            await self.repo.replace_items(formula, items_data)

        await self.repo.update(formula)
        return formula

    async def delete_formula(self, formula_id: int, tenant_id: int) -> None:
        formula = await self.get_formula(formula_id, tenant_id)
        await self.repo.soft_delete(formula)

    # ── Application à une réservation ────────────────────────────────────────

    async def apply_to_reservation(
        self,
        formula_id: int,
        nb_guests: int,
        reservation_id: int,
        tenant_id: int,
    ) -> dict:
        """Génère des ReservationLine depuis une formule × nb_guests.

        Pour chaque FormulaItem :
            quantity = ceil(item.quantity_per_person × nb_guests)
            unit_price = snapshot depuis Product (0 si produit manquant)
            subtotal = quantity × unit_price

        Returns:
            dict: {lines_created, total_quantity}
        """
        formula = await self.get_formula(formula_id, tenant_id)

        reservation = (await self.db.execute(
            select(Reservation).filter(
                Reservation.id == reservation_id,
                Reservation.tenant_id == tenant_id,
            )
        )).scalars().first()
        if not reservation:
            raise NotFound(f"Reservation {reservation_id} not found")

        lines_created = 0
        total_quantity = 0

        for item in formula.items:
            quantity = max(1, math.ceil(item.quantity_per_person * nb_guests))

            product = (await self.db.execute(
                select(Product).filter(
                    Product.id == item.product_id,
                    Product.tenant_id == tenant_id,
                )
            )).scalars().first()
            unit_price = product.price_per_day_cents if product else 0
            subtotal = quantity * unit_price
            tva_rate = getattr(product, "tva_rate", 0.20) if product else 0.20

            line = ReservationLine(
                reservation_id=reservation_id,
                tenant_id=tenant_id,
                product_id=item.product_id,
                quantity=quantity,
                unit_price_cents=unit_price,
                subtotal_cents=subtotal,
                tva_rate=tva_rate,
            )
            self.db.add(line)
            lines_created += 1
            total_quantity += quantity

        await self.db.flush()
        logger.info(
            "Applied formula %s to reservation %d: %d lines, %d items (tenant=%d)",
            formula.slug,
            reservation_id,
            lines_created,
            total_quantity,
            tenant_id,
        )
        return {
            "formula_id": formula_id,
            "nb_guests": nb_guests,
            "lines_created": lines_created,
            "total_quantity": total_quantity,
        }
