"""Repository pour le module Devis."""
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload
from app.models.devis import (
    Devis, DevisLine, DevisModule, DevisPhase,
    DevisVersion, DevisNegotiation, DevisChangeRequest,
)
from app.models.customer import Customer
from app.repositories.base import BaseRepository
from app.constants import DevisStatus


class DevisRepository(BaseRepository[Devis]):
    """Repository pour les devis avec méthodes spécialisées."""

    def __init__(self, db: Session):
        super().__init__(db, Devis)

    def get_by_id_full(self, id: int, tenant_id: int) -> Optional[Devis]:
        """Récupère un devis avec toutes ses relations chargées.

        Args:
            id: ID du devis
            tenant_id: ID du tenant (OBLIGATOIRE)

        Returns:
            Devis avec lignes, modules, phases, négociations, change_requests ou None
        """
        query = (
            select(Devis)
            .options(
                joinedload(Devis.customer),
                joinedload(Devis.lines).joinedload(DevisLine.product),
                joinedload(Devis.modules),
                joinedload(Devis.phases),
                joinedload(Devis.negotiations),
                joinedload(Devis.change_requests),
                joinedload(Devis.versions),
            )
            .filter(Devis.id == id, Devis.tenant_id == tenant_id, Devis.is_active == True)
        )
        return self.db.execute(query).unique().scalar_one_or_none()

    def list_by_tenant(
        self,
        tenant_id: int,
        status: Optional[str] = None,
        customer_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Devis]:
        """Liste les devis du tenant avec filtres optionnels.

        Args:
            tenant_id: ID du tenant (OBLIGATOIRE)
            status: Filtre par statut
            customer_id: Filtre par client
            date_from: Filtre par date de création (>=)
            date_to: Filtre par date de création (<=)
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            Liste de devis triés par date de création DESC
        """
        query = (
            select(Devis)
            .options(joinedload(Devis.customer))
            .filter(Devis.tenant_id == tenant_id, Devis.is_active == True)
        )
        if status:
            query = query.filter(Devis.status == status)
        if customer_id:
            query = query.filter(Devis.customer_id == customer_id)
        if date_from:
            query = query.filter(Devis.created_at >= date_from)
        if date_to:
            query = query.filter(Devis.created_at <= date_to)
        query = query.order_by(Devis.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(query).unique().scalars().all())

    def generate_reference(self, tenant_id: int) -> str:
        """Génère une référence unique DEV-YYYY-NNNN pour le tenant.

        Utilise MAX du dernier segment numérique + 1 pour résister aux suppressions.
        """
        year = datetime.now(tz=timezone.utc).year
        prefix = f"DEV-{year}-"
        last = self.db.execute(
            select(func.max(Devis.reference)).filter(
                Devis.tenant_id == tenant_id,
                Devis.reference.like(f"{prefix}%"),
            )
        ).scalar()
        last_counter = 0
        if last:
            try:
                last_counter = int(last.rsplit("-", 1)[-1])
            except (ValueError, IndexError):
                pass
        return f"{prefix}{last_counter + 1:04d}"

    def create_with_lines(
        self,
        tenant_id: int,
        data: dict,
        lines_data: list[dict],
        reference: str,
    ) -> Devis:
        """Crée un devis avec ses lignes et calcule les montants.

        Args:
            tenant_id: ID du tenant
            data: Données du devis (sans lines)
            lines_data: Liste des lignes à créer
            reference: Référence générée

        Returns:
            Devis créé avec lignes
        """
        devis = Devis(
            tenant_id=tenant_id,
            reference=reference,
            **data,
        )
        self.db.add(devis)
        self.db.flush()

        subtotal = 0
        for i, line_data in enumerate(lines_data):
            qty = line_data["quantity"]
            price = line_data["unit_price_cents"]
            discount = line_data.get("discount_pct", 0)
            sub = qty * price * (10000 - discount) // 10000
            line = DevisLine(
                tenant_id=tenant_id,
                devis_id=devis.id,
                label=line_data["label"],
                product_id=line_data.get("product_id"),
                bundle_id=line_data.get("bundle_id"),
                variant_id=line_data.get("variant_id"),
                quantity=qty,
                unit_price_cents=price,
                discount_pct=discount,
                subtotal_cents=sub,
                sort_order=line_data.get("sort_order", i),
            )
            self.db.add(line)
            subtotal += sub

        # Appliquer remise globale
        discount_pct = data.get("discount_pct") or 0
        if discount_pct:
            subtotal = subtotal * (10000 - discount_pct) // 10000

        tva_rate = data.get("tva_rate", 2000)
        tva = subtotal * tva_rate // 10000
        delivery_fee = data.get("delivery_fee_cents") or 0
        total = subtotal + tva + delivery_fee

        devis.subtotal_cents = subtotal
        devis.tva_cents = tva
        devis.total_cents = total

        self.db.flush()
        return devis

    def recalculate_amounts(self, devis: Devis) -> None:
        """Recalcule les montants du devis à partir de ses lignes.

        Args:
            devis: Instance Devis avec lines chargées
        """
        subtotal = sum(line.subtotal_cents for line in devis.lines)
        discount_pct = devis.discount_pct or 0
        if discount_pct:
            subtotal = subtotal * (10000 - discount_pct) // 10000
        tva = subtotal * devis.tva_rate // 10000
        devis.subtotal_cents = subtotal
        devis.tva_cents = tva
        devis.total_cents = subtotal + tva + (devis.delivery_fee_cents or 0)

    def get_next_version_number(self, devis_id: int) -> int:
        """Retourne le prochain numéro de version pour un devis.

        Args:
            devis_id: ID du devis

        Returns:
            Prochain numéro de version (1 si aucune version existante)
        """
        result = self.db.execute(
            select(func.max(DevisVersion.version_number))
            .filter(DevisVersion.devis_id == devis_id)
        ).scalar()
        return (result or 0) + 1

    def create_version_snapshot(
        self, devis: Devis, user_id: int
    ) -> DevisVersion:
        """Crée un snapshot immuable du devis.

        Args:
            devis: Instance Devis avec relations chargées
            user_id: ID de l'auteur de la version

        Returns:
            DevisVersion créée
        """
        version_number = self.get_next_version_number(devis.id)
        snapshot = {
            "id": devis.id,
            "reference": devis.reference,
            "status": devis.status,
            "customer_id": devis.customer_id,
            "total_cents": devis.total_cents,
            "subtotal_cents": devis.subtotal_cents,
            "tva_cents": devis.tva_cents,
            "tva_rate": devis.tva_rate,
            "valid_until": devis.valid_until.isoformat() if devis.valid_until else None,
            "lines": [
                {
                    "id": l.id,
                    "label": l.label,
                    "product_id": l.product_id,
                    "bundle_id": l.bundle_id,
                    "quantity": l.quantity,
                    "unit_price_cents": l.unit_price_cents,
                    "subtotal_cents": l.subtotal_cents,
                }
                for l in devis.lines
            ],
        }
        created_at_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        version = DevisVersion(
            tenant_id=devis.tenant_id,
            devis_id=devis.id,
            version_number=version_number,
            snapshot_json=snapshot,
            created_by=user_id,
            created_at=created_at_utc_naive,
        )
        self.db.add(version)
        self.db.flush()
        return version


class AsyncDevisRepository:
    """Version async de DevisRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def get_by_id(self, id: int, tenant_id: int):
        from sqlalchemy import select
        from app.models.devis import Devis
        result = await self.db.execute(
            select(Devis).filter(Devis.id == id, Devis.tenant_id == tenant_id, Devis.is_active == True)  # noqa: E712
        )
        return result.scalar_one_or_none()

    async def get_by_id_full(self, id: int, tenant_id: int):
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        from app.models.devis import Devis, DevisLine
        from app.models.bundle import ProductBundle, BundleItem
        result = await self.db.execute(
            select(Devis)
            .options(
                joinedload(Devis.customer),
                joinedload(Devis.lines).joinedload(DevisLine.product),
                joinedload(Devis.lines).joinedload(DevisLine.variant),
                joinedload(Devis.lines)
                    .joinedload(DevisLine.bundle)
                    .joinedload(ProductBundle.items)
                    .joinedload(BundleItem.product),
                joinedload(Devis.lines)
                    .joinedload(DevisLine.bundle)
                    .joinedload(ProductBundle.items)
                    .joinedload(BundleItem.variant),
                joinedload(Devis.modules),
                joinedload(Devis.phases),
                joinedload(Devis.negotiations),
                joinedload(Devis.change_requests),
                joinedload(Devis.versions),
            )
            .filter(Devis.id == id, Devis.tenant_id == tenant_id, Devis.is_active == True)  # noqa: E712
        )
        return result.unique().scalar_one_or_none()

    def _apply_devis_filters(self, q, tenant_id: int, status=None, customer_id=None, date_from=None, date_to=None, search=None):
        from app.models.devis import Devis
        q = q.filter(Devis.tenant_id == tenant_id, Devis.is_active == True)  # noqa: E712
        if status:
            q = q.filter(Devis.status == status)
        if customer_id:
            q = q.filter(Devis.customer_id == customer_id)
        if date_from:
            q = q.filter(Devis.created_at >= date_from)
        if date_to:
            q = q.filter(Devis.created_at <= date_to)
        if search:
            q = q.filter(Devis.reference.ilike(f"%{search}%"))
        return q

    async def list_by_tenant(self, tenant_id: int, status=None, customer_id=None, date_from=None, date_to=None, search=None, skip=0, limit=50) -> list:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        from app.models.devis import Devis
        q = select(Devis).options(joinedload(Devis.customer))
        q = self._apply_devis_filters(q, tenant_id, status, customer_id, date_from, date_to, search)
        q = q.order_by(Devis.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(q)
        return list(result.unique().scalars().all())

    async def count_by_tenant(self, tenant_id: int, status=None, customer_id=None, date_from=None, date_to=None, search=None) -> int:
        from sqlalchemy import select, func
        from app.models.devis import Devis
        q = select(func.count(Devis.id))
        q = self._apply_devis_filters(q, tenant_id, status, customer_id, date_from, date_to, search)
        result = await self.db.execute(q)
        return result.scalar() or 0

    async def generate_reference(self, tenant_id: int) -> str:
        from datetime import datetime, timezone
        from sqlalchemy import select, func
        from app.models.devis import Devis
        year = datetime.now(tz=timezone.utc).year
        prefix = f"DEV-{year}-"
        last = await self.db.scalar(
            select(func.max(Devis.reference)).filter(
                Devis.tenant_id == tenant_id,
                Devis.reference.like(f"{prefix}%"),
            )
        )
        last_counter = 0
        if last:
            try:
                last_counter = int(last.rsplit("-", 1)[-1])
            except (ValueError, IndexError):
                pass
        return f"{prefix}{last_counter + 1:04d}"

    async def create_with_lines(self, tenant_id: int, data: dict, lines_data: list, reference: str):
        from app.models.devis import Devis, DevisLine
        devis = Devis(tenant_id=tenant_id, reference=reference, **data)
        self.db.add(devis)
        await self.db.flush()

        subtotal = 0
        for i, line_data in enumerate(lines_data):
            qty = line_data["quantity"]
            price = line_data["unit_price_cents"]
            discount = line_data.get("discount_pct", 0)
            sub = qty * price * (10000 - discount) // 10000
            line = DevisLine(
                tenant_id=tenant_id,
                devis_id=devis.id,
                label=line_data["label"],
                product_id=line_data.get("product_id"),
                bundle_id=line_data.get("bundle_id"),
                variant_id=line_data.get("variant_id"),
                quantity=qty,
                unit_price_cents=price,
                discount_pct=discount,
                subtotal_cents=sub,
                sort_order=line_data.get("sort_order", i),
            )
            self.db.add(line)
            subtotal += sub

        discount_pct = data.get("discount_pct") or 0
        if discount_pct:
            subtotal = subtotal * (10000 - discount_pct) // 10000

        tva_rate = data.get("tva_rate", 2000)
        tva = subtotal * tva_rate // 10000
        delivery_fee = data.get("delivery_fee_cents") or 0
        total = subtotal + tva + delivery_fee

        devis.subtotal_cents = subtotal
        devis.tva_cents = tva
        devis.total_cents = total

        await self.db.flush()
        await self.db.refresh(devis)
        return devis

    def recalculate_amounts(self, devis) -> None:
        """Recalcule synchrone (opère sur objet déjà chargé en mémoire)."""
        subtotal = sum(line.subtotal_cents for line in devis.lines)
        discount_pct = devis.discount_pct or 0
        if discount_pct:
            subtotal = subtotal * (10000 - discount_pct) // 10000
        tva = subtotal * devis.tva_rate // 10000
        devis.subtotal_cents = subtotal
        devis.tva_cents = tva
        devis.total_cents = subtotal + tva + (devis.delivery_fee_cents or 0)

    async def get_next_version_number(self, devis_id: int) -> int:
        from sqlalchemy import select, func
        from app.models.devis import DevisVersion
        result = await self.db.execute(
            select(func.max(DevisVersion.version_number))
            .filter(DevisVersion.devis_id == devis_id)
        )
        return (result.scalar() or 0) + 1

    async def create_version_snapshot(self, devis, user_id: int):
        from datetime import datetime, timezone
        from app.models.devis import DevisVersion
        version_number = await self.get_next_version_number(devis.id)
        snapshot = {
            "id": devis.id,
            "reference": devis.reference,
            "status": devis.status,
            "customer_id": devis.customer_id,
            "total_cents": devis.total_cents,
            "subtotal_cents": devis.subtotal_cents,
            "tva_cents": devis.tva_cents,
            "tva_rate": devis.tva_rate,
            "valid_until": devis.valid_until.isoformat() if devis.valid_until else None,
            "lines": [
                {
                    "id": l.id,
                    "label": l.label,
                    "product_id": l.product_id,
                    "bundle_id": l.bundle_id,
                    "quantity": l.quantity,
                    "unit_price_cents": l.unit_price_cents,
                    "subtotal_cents": l.subtotal_cents,
                }
                for l in devis.lines
            ],
        }
        created_at_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        version = DevisVersion(
            tenant_id=devis.tenant_id,
            devis_id=devis.id,
            version_number=version_number,
            snapshot_json=snapshot,
            created_by=user_id,
            created_at=created_at_utc_naive,
        )
        self.db.add(version)
        await self.db.flush()
        await self.db.refresh(version)
        return version
