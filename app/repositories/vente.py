"""Repository pour les Ventes et sous-entités."""
from datetime import date
from typing import Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, joinedload
from app.models.vente import Vente, VenteLine, VentePayment
from app.models.customer import Customer
from app.repositories.base import BaseRepository


class VenteRepository(BaseRepository[Vente]):
    """Repository Vente avec isolation tenant stricte."""

    def __init__(self, db: Session):
        super().__init__(db, Vente)

    def get_by_id_with_relations(
        self,
        id: int,
        tenant_id: int,
    ) -> Optional[Vente]:
        """Récupère une vente avec lines, payments et customer."""
        query = (
            select(Vente)
            .options(
                joinedload(Vente.lines),
                joinedload(Vente.payments),
                joinedload(Vente.customer),
            )
            .filter(Vente.id == id, Vente.tenant_id == tenant_id, Vente.is_active.is_(True))
        )
        return self.db.execute(query).unique().scalar_one_or_none()

    def list_ventes(
        self,
        tenant_id: int,
        status: Optional[str] = None,
        customer_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search: Optional[str] = None,
        overdue_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Vente], int]:
        """Liste les ventes avec filtres et pagination."""
        base_query = (
            select(Vente)
            .join(Customer, Customer.id == Vente.customer_id, isouter=True)
            .options(joinedload(Vente.customer))
            .filter(Vente.tenant_id == tenant_id, Vente.is_active.is_(True))
        )
        if status:
            base_query = base_query.filter(Vente.status == status)
        if customer_id:
            base_query = base_query.filter(Vente.customer_id == customer_id)
        if date_from:
            base_query = base_query.filter(func.date(Vente.created_at) >= date_from)
        if date_to:
            base_query = base_query.filter(func.date(Vente.created_at) <= date_to)
        if search and search.strip():
            term = f"%{search.strip()}%"
            base_query = base_query.filter(
                or_(Vente.reference.ilike(term), Customer.display_name.ilike(term))
            )
        if overdue_only:
            base_query = base_query.filter(Vente.status == "overdue")

        count_query = select(func.count()).select_from(
            base_query.subquery()
        )
        total = self.db.execute(count_query).scalar_one()
        items = self.db.execute(
            base_query.order_by(Vente.created_at.desc()).offset(skip).limit(limit)
        ).unique().scalars().all()
        return list(items), total

    def create_vente(
        self,
        tenant_id: int,
        reference: str,
        customer_id: int,
        lines_data: list[dict],
        deposit_pct: Optional[int] = None,
        payment_due_date: Optional[date] = None,
        notes: Optional[str] = None,
        invoice_id: Optional[int] = None,
        reservation_id: Optional[int] = None,
    ) -> Vente:
        """Crée une vente avec ses lignes et calcule les totaux."""
        subtotal = sum(
            d["quantity"] * d["unit_price_cents"] for d in lines_data
        )
        tva_cents = int(subtotal * 0.20)
        total_cents = subtotal + tva_cents

        vente = Vente(
            tenant_id=tenant_id,
            reference=reference,
            customer_id=customer_id,
            subtotal_cents=subtotal,
            tva_cents=tva_cents,
            total_cents=total_cents,
            paid_cents=0,
            deposit_pct=deposit_pct,
            payment_due_date=payment_due_date,
            notes=notes,
            invoice_id=invoice_id,
            reservation_id=reservation_id,
        )
        self.db.add(vente)
        self.db.flush()

        for d in lines_data:
            line = VenteLine(
                tenant_id=tenant_id,
                vente_id=vente.id,
                product_id=d.get("product_id"),
                label=d["label"],
                quantity=d["quantity"],
                unit_price_cents=d["unit_price_cents"],
                subtotal_cents=d["quantity"] * d["unit_price_cents"],
            )
            self.db.add(line)

        self.db.flush()
        return vente

    def add_payment(
        self,
        vente: Vente,
        tenant_id: int,
        amount_cents: int,
        payment_method: str,
        payment_date: date,
        is_deposit: bool,
        created_by: int,
        notes: Optional[str] = None,
    ) -> VentePayment:
        """Ajoute un paiement et met à jour paid_cents."""
        payment = VentePayment(
            tenant_id=tenant_id,
            vente_id=vente.id,
            amount_cents=amount_cents,
            payment_method=payment_method,
            payment_date=payment_date,
            is_deposit=is_deposit,
            created_by=created_by,
            notes=notes,
        )
        self.db.add(payment)
        self.db.flush()

        # Recalcul paid_cents via SUM
        total_paid = (
            self.db.execute(
                select(func.sum(VentePayment.amount_cents))
                .filter(VentePayment.vente_id == vente.id)
            ).scalar_one_or_none()
            or 0
        )
        vente.paid_cents = total_paid
        self.db.flush()
        return payment

    def get_payments(self, vente_id: int, tenant_id: int) -> list[VentePayment]:
        """Retourne les paiements d'une vente."""
        return list(
            self.db.execute(
                select(VentePayment)
                .filter(VentePayment.vente_id == vente_id, VentePayment.tenant_id == tenant_id)
                .order_by(VentePayment.payment_date)
            ).scalars().all()
        )

    def generate_reference(self, tenant_id: int) -> str:
        """Génère une référence unique VTE-YYYY-NNNN (MAX + 1)."""
        from datetime import datetime
        year = datetime.now().year
        prefix = f"VTE-{year}-"
        last = self.db.execute(
            select(func.max(Vente.reference)).filter(
                Vente.tenant_id == tenant_id,
                Vente.reference.like(f"{prefix}%"),
            )
        ).scalar()
        last_counter = 0
        if last:
            try:
                last_counter = int(last.rsplit("-", 1)[-1])
            except (ValueError, IndexError):
                pass
        return f"{prefix}{last_counter + 1:04d}"


class AsyncVenteRepository:
    """Version async de VenteRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def get_by_id_with_relations(self, id: int, tenant_id: int):
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        from app.models.vente import Vente
        result = await self.db.execute(
            select(Vente)
            .options(
                joinedload(Vente.lines),
                joinedload(Vente.payments),
                joinedload(Vente.customer),
            )
            .filter(Vente.id == id, Vente.tenant_id == tenant_id, Vente.is_active.is_(True))
        )
        return result.unique().scalar_one_or_none()

    async def list_ventes(
        self,
        tenant_id: int,
        status=None,
        customer_id=None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search: Optional[str] = None,
        overdue_only=False,
        skip=0,
        limit=50,
    ):
        from sqlalchemy import select, func, or_
        from sqlalchemy.orm import joinedload
        from app.models.vente import Vente
        from app.models.customer import Customer
        base_q = (
            select(Vente)
            .join(Customer, Customer.id == Vente.customer_id, isouter=True)
            .options(joinedload(Vente.customer))
            .filter(Vente.tenant_id == tenant_id, Vente.is_active.is_(True))
        )
        if status:
            base_q = base_q.filter(Vente.status == status)
        if customer_id:
            base_q = base_q.filter(Vente.customer_id == customer_id)
        if date_from:
            base_q = base_q.filter(func.date(Vente.created_at) >= date_from)
        if date_to:
            base_q = base_q.filter(func.date(Vente.created_at) <= date_to)
        if search and search.strip():
            term = f"%{search.strip()}%"
            base_q = base_q.filter(
                or_(Vente.reference.ilike(term), Customer.display_name.ilike(term))
            )
        if overdue_only:
            base_q = base_q.filter(Vente.status == "overdue")

        total_result = await self.db.execute(
            select(func.count()).select_from(base_q.subquery())
        )
        total = total_result.scalar_one()

        items_result = await self.db.execute(
            base_q.order_by(Vente.created_at.desc()).offset(skip).limit(limit)
        )
        return list(items_result.unique().scalars().all()), total

    async def create_vente(self, tenant_id: int, reference: str, customer_id: int, lines_data: list, deposit_pct=None, payment_due_date=None, notes=None, invoice_id=None, reservation_id=None):
        from app.models.vente import Vente, VenteLine
        subtotal = sum(d["quantity"] * d["unit_price_cents"] for d in lines_data)
        tva_cents = int(subtotal * 0.20)
        total_cents = subtotal + tva_cents

        vente = Vente(
            tenant_id=tenant_id,
            reference=reference,
            customer_id=customer_id,
            subtotal_cents=subtotal,
            tva_cents=tva_cents,
            total_cents=total_cents,
            paid_cents=0,
            deposit_pct=deposit_pct,
            payment_due_date=payment_due_date,
            notes=notes,
            invoice_id=invoice_id,
            reservation_id=reservation_id,
        )
        self.db.add(vente)
        await self.db.flush()

        for d in lines_data:
            line = VenteLine(
                tenant_id=tenant_id,
                vente_id=vente.id,
                product_id=d.get("product_id"),
                label=d["label"],
                quantity=d["quantity"],
                unit_price_cents=d["unit_price_cents"],
                subtotal_cents=d["quantity"] * d["unit_price_cents"],
            )
            self.db.add(line)

        await self.db.flush()
        await self.db.refresh(vente)
        hydrated = await self.get_by_id_with_relations(vente.id, tenant_id)
        return hydrated or vente

    async def add_payment(self, vente, tenant_id: int, amount_cents: int, payment_method: str, payment_date, is_deposit: bool, created_by: int, notes=None):
        from sqlalchemy import select, func
        from app.models.vente import VentePayment
        payment = VentePayment(
            tenant_id=tenant_id,
            vente_id=vente.id,
            amount_cents=amount_cents,
            payment_method=payment_method,
            payment_date=payment_date,
            is_deposit=is_deposit,
            created_by=created_by,
            notes=notes,
        )
        self.db.add(payment)
        await self.db.flush()

        total_paid_result = await self.db.execute(
            select(func.sum(VentePayment.amount_cents))
            .filter(VentePayment.vente_id == vente.id)
        )
        vente.paid_cents = total_paid_result.scalar_one_or_none() or 0
        await self.db.flush()
        return payment

    async def get_payments(self, vente_id: int, tenant_id: int) -> list:
        from sqlalchemy import select
        from app.models.vente import VentePayment
        result = await self.db.execute(
            select(VentePayment)
            .filter(VentePayment.vente_id == vente_id, VentePayment.tenant_id == tenant_id)
            .order_by(VentePayment.payment_date)
        )
        return list(result.scalars().all())

    async def generate_reference(self, tenant_id: int) -> str:
        from datetime import datetime
        from sqlalchemy import select, func
        from app.models.vente import Vente
        year = datetime.now().year
        prefix = f"VTE-{year}-"
        last = await self.db.scalar(
            select(func.max(Vente.reference)).filter(
                Vente.tenant_id == tenant_id,
                Vente.reference.like(f"{prefix}%"),
            )
        )
        last_counter = 0
        if last:
            try:
                last_counter = int(last.rsplit("-", 1)[-1])
            except (ValueError, IndexError):
                pass
        return f"{prefix}{last_counter + 1:04d}"

    async def get_by_id(self, vente_id: int, tenant_id: int):
        from sqlalchemy import select
        from app.models.vente import Vente
        result = await self.db.execute(
            select(Vente).filter(Vente.id == vente_id, Vente.tenant_id == tenant_id, Vente.is_active.is_(True))
        )
        return result.scalar_one_or_none()
