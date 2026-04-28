"""Repository Formula — accès DB multi-tenant."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.formula import Formula, FormulaItem


class FormulaRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Formula ──────────────────────────────────────────────────────────────

    def get_by_id(self, formula_id: int, tenant_id: int) -> Optional[Formula]:
        return (
            self.db.query(Formula)
            .filter(
                Formula.id == formula_id,
                Formula.tenant_id == tenant_id,
                Formula.is_active.is_(True),
            )
            .first()
        )

    def get_by_slug(self, slug: str, tenant_id: int) -> Optional[Formula]:
        return (
            self.db.query(Formula)
            .filter(
                Formula.slug == slug,
                Formula.tenant_id == tenant_id,
                Formula.is_active.is_(True),
            )
            .first()
        )

    def list_formulas(
        self,
        tenant_id: int,
        formula_type: Optional[str] = None,
        featured_only: bool = False,
    ) -> Tuple[List[Formula], int]:
        q = self.db.query(Formula).filter(
            Formula.tenant_id == tenant_id,
            Formula.is_active.is_(True),
        )
        if formula_type:
            q = q.filter(Formula.formula_type == formula_type)
        if featured_only:
            q = q.filter(Formula.featured.is_(True))
        q = q.order_by(Formula.sort_order, Formula.id)
        items = q.all()
        return items, len(items)

    def create(self, formula: Formula) -> Formula:
        self.db.add(formula)
        self.db.flush()
        return formula

    def update(self, formula: Formula) -> Formula:
        self.db.flush()
        return formula

    def soft_delete(self, formula: Formula) -> None:
        formula.is_active = False
        self.db.flush()

    # ── FormulaItem ──────────────────────────────────────────────────────────

    def replace_items(self, formula: Formula, items_data: list) -> None:
        """Remplace toutes les lignes d'une formule."""
        for item in list(formula.items):
            self.db.delete(item)
        self.db.flush()

        for item_data in items_data:
            item = FormulaItem(
                formula_id=formula.id,
                product_id=item_data["product_id"],
                quantity_per_person=item_data["quantity_per_person"],
            )
            self.db.add(item)
        self.db.flush()


class AsyncFormulaRepository:
    """Version async de FormulaRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def get_by_id(self, formula_id: int, tenant_id: int) -> Optional[Formula]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(Formula).filter(Formula.id == formula_id, Formula.tenant_id == tenant_id, Formula.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str, tenant_id: int) -> Optional[Formula]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(Formula).filter(Formula.slug == slug, Formula.tenant_id == tenant_id, Formula.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def list_formulas(
        self,
        tenant_id: int,
        formula_type: Optional[str] = None,
        featured_only: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Formula], int]:
        from sqlalchemy import select, func
        base = select(Formula).filter(Formula.tenant_id == tenant_id, Formula.is_active.is_(True))
        if formula_type:
            base = base.filter(Formula.formula_type == formula_type)
        if featured_only:
            base = base.filter(Formula.featured.is_(True))
        count_result = await self.db.execute(select(func.count()).select_from(base.subquery()))
        total = count_result.scalar() or 0
        q = base.order_by(Formula.sort_order, Formula.id).offset(skip).limit(limit)
        result = await self.db.execute(q)
        items = list(result.scalars().all())
        return items, total

    async def create(self, formula: Formula) -> Formula:
        self.db.add(formula)
        await self.db.flush()
        await self.db.refresh(formula)
        return formula

    async def update(self, formula: Formula) -> Formula:
        await self.db.flush()
        await self.db.refresh(formula)
        return formula

    async def soft_delete(self, formula: Formula) -> None:
        formula.is_active = False
        await self.db.flush()

    async def replace_items(self, formula: Formula, items_data: list) -> None:
        from sqlalchemy import select
        result = await self.db.execute(
            select(FormulaItem).filter(FormulaItem.formula_id == formula.id)
        )
        for item in result.scalars().all():
            await self.db.delete(item)
        await self.db.flush()
        for item_data in items_data:
            item = FormulaItem(
                formula_id=formula.id,
                product_id=item_data["product_id"],
                quantity_per_person=item_data["quantity_per_person"],
            )
            self.db.add(item)
        await self.db.flush()
