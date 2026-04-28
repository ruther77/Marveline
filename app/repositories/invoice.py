"""Repository pour l'entité Invoice."""
from datetime import date
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.invoice import Invoice
from app.models.invoice_charge import InvoiceCharge
from app.models.payment import Payment
from app.models.reservation import Reservation, ReservationLine
from app.models.bundle import ProductBundle, BundleItem
from app.repositories.base import BaseRepository, AsyncBaseRepository
from app.constants import InvoiceStatus


class InvoiceRepository(BaseRepository[Invoice]):
    """Repository pour les factures avec méthodes spécialisées."""

    def __init__(self, db: Session):
        """Initialise le repository Invoice.

        Args:
            db: Session SQLAlchemy active
        """
        super().__init__(db, Invoice)

    def get_by_id_with_relations(
        self,
        id: int,
        tenant_id: int,
        include_inactive: bool = False
    ) -> Optional[Invoice]:
        """Récupère une facture avec ses relations (reservation).

        Args:
            id: ID de la facture
            tenant_id: ID du tenant (OBLIGATOIRE)
            include_inactive: Inclure les factures soft-deleted

        Returns:
            La facture avec relations chargées ou None

        Note:
            - Utilise joinedload pour éviter N+1 queries
            - Charge: reservation, reservation.customer
        """
        query = select(Invoice).options(
            joinedload(Invoice.reservation).joinedload(Reservation.customer),
            selectinload(Invoice.charges),
            selectinload(Invoice.payments),
        ).filter(Invoice.id == id)

        query = self._apply_tenant_filter(query, tenant_id)

        if not include_inactive:
            query = self._apply_active_filter(query)

        result = self.db.execute(query).unique().scalar_one_or_none()
        return result

    def get_by_invoice_number(
        self,
        invoice_number: str,
        tenant_id: int,
        include_inactive: bool = False
    ) -> Optional[Invoice]:
        """Récupère une facture par son numéro (unique par tenant).

        Args:
            invoice_number: Numéro de facture (ex: "INV-2026-0001")
            tenant_id: ID du tenant (OBLIGATOIRE)
            include_inactive: Inclure les factures soft-deleted

        Returns:
            La facture trouvée ou None

        Security:
            - Filtre tenant_id automatique
        """
        query = select(Invoice).filter(
            Invoice.invoice_number == invoice_number.upper().strip()
        )
        query = self._apply_tenant_filter(query, tenant_id)

        if not include_inactive:
            query = self._apply_active_filter(query)

        result = self.db.execute(query).scalar_one_or_none()
        return result

    def invoice_number_exists(
        self,
        invoice_number: str,
        tenant_id: int,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Vérifie si un numéro de facture existe déjà (unique par tenant).

        Args:
            invoice_number: Numéro à vérifier
            tenant_id: ID du tenant (OBLIGATOIRE)
            exclude_id: ID de la facture à exclure (pour UPDATE)

        Returns:
            True si le numéro existe déjà, False sinon
        """
        query = select(Invoice).filter(
            Invoice.invoice_number == invoice_number.upper().strip()
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)

        if exclude_id:
            query = query.filter(Invoice.id != exclude_id)

        result = self.db.execute(query).scalar_one_or_none()
        return result is not None

    def get_by_reservation(
        self,
        reservation_id: int,
        tenant_id: int
    ) -> Optional[Invoice]:
        """Récupère la facture d'une réservation (relation one-to-one).

        Args:
            reservation_id: ID de la réservation
            tenant_id: ID du tenant (OBLIGATOIRE)

        Returns:
            La facture trouvée ou None

        Security:
            - Filtre tenant_id automatique
        """
        query = select(Invoice).filter(
            Invoice.reservation_id == reservation_id
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)

        result = self.db.execute(query).scalar_one_or_none()
        return result

    def get_by_reservation_and_type(
        self,
        reservation_id: int,
        invoice_type: str,
        tenant_id: int
    ) -> Optional[Invoice]:
        """Récupère la facture d'une réservation par type (advance/balance/full).

        Args:
            reservation_id: ID de la réservation
            invoice_type: Type de facture ('full', 'advance', 'balance')
            tenant_id: ID du tenant (OBLIGATOIRE)

        Returns:
            La facture trouvée ou None
        """
        query = select(Invoice).filter(
            Invoice.reservation_id == reservation_id,
            Invoice.invoice_type == invoice_type,
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)

        result = self.db.execute(query).scalar_one_or_none()
        return result

    def list_by_status(
        self,
        status: str,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> list[Invoice]:
        """Liste les factures filtrées par statut.

        Args:
            status: Statut ('draft', 'sent', 'paid', 'overdue', 'cancelled')
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination

        Returns:
            Liste des factures du statut spécifié
        """
        return self.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters={"status": status}
        )

    def list_overdue(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        as_of_date: Optional[date] = None
    ) -> list[Invoice]:
        """Liste les factures en retard de paiement.

        Args:
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination
            as_of_date: Date de référence (défaut: aujourd'hui)

        Returns:
            Liste des factures en retard

        Note:
            - Facture en retard si: due_date < today AND paid_amount_cents < total_amount_cents
            - Exclut les factures annulées

        Security:
            - Filtre tenant_id automatique
        """
        reference_date = as_of_date or date.today()

        query = select(Invoice).filter(
            and_(
                Invoice.due_date < reference_date,
                Invoice.paid_amount_cents < Invoice.total_amount_cents,
                Invoice.status != InvoiceStatus.CANCELLED
            )
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        query = query.order_by(Invoice.due_date, Invoice.id)
        query = query.offset(skip).limit(min(limit, 1000))

        result = self.db.execute(query).scalars().all()
        return list(result)

    def list_unpaid(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> list[Invoice]:
        """Liste les factures non payées (paid_amount_cents < total_amount_cents).

        Args:
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination

        Returns:
            Liste des factures non entièrement payées

        Security:
            - Filtre tenant_id automatique
            - Exclut les factures annulées
        """
        query = select(Invoice).filter(
            and_(
                Invoice.paid_amount_cents < Invoice.total_amount_cents,
                Invoice.status != InvoiceStatus.CANCELLED
            )
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        query = query.order_by(Invoice.due_date, Invoice.id)
        query = query.offset(skip).limit(min(limit, 1000))

        result = self.db.execute(query).scalars().all()
        return list(result)

    def list_with_customer(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[dict] = None,
    ) -> tuple[list[Invoice], int]:
        """Liste les factures avec relations reservation→customer chargées (joinedload).

        Args:
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pagination
            limit: Limite pagination
            filters: Filtres additionnels (ex: {"status": "draft"})

        Returns:
            Tuple (items, total)

        Security:
            - Filtre tenant_id automatique
        """
        limit = min(limit, 1000)

        total = self.count(tenant_id=tenant_id, filters=filters)

        query = select(Invoice).options(
            joinedload(Invoice.reservation).joinedload(Reservation.customer)
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)

        if filters:
            for key, value in filters.items():
                if hasattr(Invoice, key):
                    query = query.filter(getattr(Invoice, key) == value)

        query = query.order_by(Invoice.id)
        query = query.offset(skip).limit(limit)

        result = self.db.execute(query).unique().scalars().all()
        return list(result), total

    def list_by_date_range(
        self,
        start_date: date,
        end_date: date,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> list[Invoice]:
        """Liste les factures dans une plage de dates (issue_date).

        Args:
            start_date: Date de début (inclusive)
            end_date: Date de fin (inclusive)
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination
            status: Filtrer par statut (optionnel)

        Returns:
            Liste des factures dans la plage de dates

        Security:
            - Filtre tenant_id automatique
        """
        query = select(Invoice).filter(
            and_(
                Invoice.issue_date >= start_date,
                Invoice.issue_date <= end_date
            )
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)

        if status:
            query = query.filter(Invoice.status == status)

        query = query.order_by(Invoice.issue_date, Invoice.id)
        query = query.offset(skip).limit(min(limit, 1000))

        result = self.db.execute(query).scalars().all()
        return list(result)

    def add_charge(self, charge: InvoiceCharge) -> InvoiceCharge:
        """Persiste une charge additionnelle en base.

        Args:
            charge: Instance InvoiceCharge à persister (tenant_id déjà renseigné)

        Returns:
            La charge persistée avec id généré
        """
        self.db.add(charge)
        self.db.flush()
        self.db.refresh(charge)
        return charge

    def list_charges(self, invoice_id: int, tenant_id: int) -> list[InvoiceCharge]:
        """Liste toutes les charges d'une facture.

        Args:
            invoice_id: ID de la facture
            tenant_id: ID du tenant (isolation obligatoire)

        Returns:
            Liste des charges triées par id
        """
        query = select(InvoiceCharge).filter(
            and_(
                InvoiceCharge.invoice_id == invoice_id,
                InvoiceCharge.tenant_id == tenant_id,
            )
        ).order_by(InvoiceCharge.id)
        result = self.db.execute(query).scalars().all()
        return list(result)


class AsyncInvoiceRepository(AsyncBaseRepository[Invoice]):
    """Version async de InvoiceRepository pour FastAPI."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Invoice)

    async def get_by_id_with_relations(
        self, id: int, tenant_id: int, include_inactive: bool = False
    ) -> Optional[Invoice]:
        query = select(Invoice).options(
            joinedload(Invoice.reservation).options(
                joinedload(Reservation.customer),
                selectinload(Reservation.lines).options(
                    joinedload(ReservationLine.product),
                    joinedload(ReservationLine.variant),
                    joinedload(ReservationLine.bundle).selectinload(ProductBundle.items).joinedload(BundleItem.product),
                ),
            ),
            selectinload(Invoice.charges),
            selectinload(Invoice.payments),
        ).filter(Invoice.id == id)
        query = self._apply_tenant_filter(query, tenant_id)
        if not include_inactive:
            query = self._apply_active_filter(query)
        result = await self.db.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_by_invoice_number(
        self, invoice_number: str, tenant_id: int, include_inactive: bool = False
    ) -> Optional[Invoice]:
        query = select(Invoice).filter(
            Invoice.invoice_number == invoice_number.upper().strip()
        )
        query = self._apply_tenant_filter(query, tenant_id)
        if not include_inactive:
            query = self._apply_active_filter(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def invoice_number_exists(
        self, invoice_number: str, tenant_id: int, exclude_id: Optional[int] = None
    ) -> bool:
        query = select(Invoice).filter(
            Invoice.invoice_number == invoice_number.upper().strip()
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if exclude_id:
            query = query.filter(Invoice.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_by_reservation(
        self, reservation_id: int, tenant_id: int
    ) -> Optional[Invoice]:
        query = select(Invoice).filter(Invoice.reservation_id == reservation_id)
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_reservation_and_type(
        self, reservation_id: int, invoice_type: str, tenant_id: int
    ) -> Optional[Invoice]:
        query = select(Invoice).filter(
            Invoice.reservation_id == reservation_id,
            Invoice.invoice_type == invoice_type,
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_by_status(
        self, status: str, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> list[Invoice]:
        items, _ = await self.list(
            tenant_id=tenant_id, skip=skip, limit=limit, filters={"status": status}
        )
        return items

    async def list_overdue(
        self, tenant_id: int, skip: int = 0, limit: int = 100, as_of_date: Optional[date] = None
    ) -> list[Invoice]:
        reference_date = as_of_date or date.today()
        query = select(Invoice).filter(
            and_(
                Invoice.due_date < reference_date,
                Invoice.paid_amount_cents < Invoice.total_amount_cents,
                Invoice.status != InvoiceStatus.CANCELLED,
            )
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        query = query.order_by(Invoice.due_date, Invoice.id).offset(skip).limit(min(limit, 1000))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_unpaid(
        self, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> list[Invoice]:
        query = select(Invoice).filter(
            and_(
                Invoice.paid_amount_cents < Invoice.total_amount_cents,
                Invoice.status != InvoiceStatus.CANCELLED,
            )
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        query = query.order_by(Invoice.due_date, Invoice.id).offset(skip).limit(min(limit, 1000))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_with_customer(
        self, tenant_id: int, skip: int = 0, limit: int = 100, filters: Optional[dict] = None
    ) -> tuple[list[Invoice], int]:
        limit = min(limit, 1000)
        total = await self.count(tenant_id=tenant_id, filters=filters)

        query = select(Invoice).options(
            joinedload(Invoice.reservation).joinedload(Reservation.customer)
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if filters:
            for key, value in filters.items():
                if hasattr(Invoice, key):
                    query = query.filter(getattr(Invoice, key) == value)
        query = query.order_by(Invoice.id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return (list(result.unique().scalars().all()), total)

    async def list_by_date_range(
        self,
        start_date: date,
        end_date: date,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> list[Invoice]:
        query = select(Invoice).filter(
            and_(Invoice.issue_date >= start_date, Invoice.issue_date <= end_date)
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if status:
            query = query.filter(Invoice.status == status)
        query = query.order_by(Invoice.issue_date, Invoice.id).offset(skip).limit(min(limit, 1000))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def add_charge(self, charge: InvoiceCharge) -> InvoiceCharge:
        self.db.add(charge)
        await self.db.flush()
        await self.db.refresh(charge)
        return charge

    async def list_charges(self, invoice_id: int, tenant_id: int) -> list[InvoiceCharge]:
        query = select(InvoiceCharge).filter(
            and_(
                InvoiceCharge.invoice_id == invoice_id,
                InvoiceCharge.tenant_id == tenant_id,
            )
        ).order_by(InvoiceCharge.id)
        result = await self.db.execute(query)
        return list(result.scalars().all())
