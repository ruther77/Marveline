"""Repository pour l'entité Customer."""
from typing import Optional
from datetime import date
from sqlalchemy import select, func, exists
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.customer import Customer
from app.models.reservation import Reservation
from app.models.invoice import Invoice
from app.models.relance import Relance
from app.repositories.base import BaseRepository, AsyncBaseRepository


class CustomerRepository(BaseRepository[Customer]):
    """Repository pour les clients avec méthodes spécialisées."""

    def __init__(self, db: Session):
        """Initialise le repository Customer.

        Args:
            db: Session SQLAlchemy active
        """
        super().__init__(db, Customer)

    def get_by_email(
        self,
        email: str,
        tenant_id: int,
        include_inactive: bool = False
    ) -> Optional[Customer]:
        """Récupère un client par son email (unique par tenant).

        Args:
            email: Email du client (case-insensitive)
            tenant_id: ID du tenant (OBLIGATOIRE)
            include_inactive: Inclure les clients soft-deleted

        Returns:
            Le client trouvé ou None

        Security:
            - Filtre tenant_id automatique
            - Email normalisé en lowercase pour comparaison
        """
        query = select(Customer).filter(
            Customer.email.ilike(email.lower().strip())
        )
        query = self._apply_tenant_filter(query, tenant_id)

        if not include_inactive:
            query = self._apply_active_filter(query)

        result = self.db.execute(query).scalar_one_or_none()
        return result

    def email_exists(
        self,
        email: str,
        tenant_id: int,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Vérifie si un email existe déjà (pour validation unicité).

        Args:
            email: Email à vérifier
            tenant_id: ID du tenant (OBLIGATOIRE)
            exclude_id: ID du client à exclure (pour UPDATE)

        Returns:
            True si l'email existe déjà, False sinon

        Use cases:
            - CREATE: email_exists(email, tenant_id) → doit être False
            - UPDATE: email_exists(email, tenant_id, exclude_id=customer.id) → doit être False
        """
        query = select(Customer).filter(
            Customer.email.ilike(email.lower().strip())
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)

        if exclude_id:
            query = query.filter(Customer.id != exclude_id)

        result = self.db.execute(query).scalar_one_or_none()
        return result is not None

    def list_by_type(
        self,
        customer_type: str,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> list[Customer]:
        """Liste les clients filtrés par type (individual ou company).

        Args:
            customer_type: Type de client ('individual' ou 'company')
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination

        Returns:
            Liste des clients du type spécifié
        """
        return self.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters={"customer_type": customer_type}
        )

    def search(
        self,
        search_term: str,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        customer_type: Optional[str] = None,
    ) -> tuple[list[Customer], int]:
        """Recherche des clients par nom, prénom, raison sociale ou email.

        Args:
            search_term: Terme de recherche (case-insensitive)
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination
            customer_type: Filtre optionnel sur le type de client

        Returns:
            Tuple (items, total) où items est la liste paginée et total le nombre total

        Security:
            - Filtre tenant_id automatique
        """
        search_pattern = f"%{search_term.lower()}%"
        text_filter = (
            (Customer.first_name.ilike(search_pattern)) |
            (Customer.last_name.ilike(search_pattern)) |
            (Customer.company_name.ilike(search_pattern)) |
            (Customer.email.ilike(search_pattern))
        )

        count_query = select(func.count()).select_from(Customer).filter(text_filter)
        count_query = self._apply_tenant_filter(count_query, tenant_id)
        count_query = self._apply_active_filter(count_query)
        if customer_type:
            count_query = count_query.filter(Customer.customer_type == customer_type)
        total = self.db.execute(count_query).scalar() or 0

        query = select(Customer).filter(text_filter)
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if customer_type:
            query = query.filter(Customer.customer_type == customer_type)
        query = query.order_by(Customer.id).offset(skip).limit(min(limit, 1000))

        result = self.db.execute(query).scalars().all()
        return (list(result), total)

    def get_customer_history(
        self,
        customer_id: int,
        tenant_id: int,
    ) -> dict:
        """Récupère l'historique complet d'un client.

        Args:
            customer_id: ID du client
            tenant_id: ID du tenant (OBLIGATOIRE)

        Returns:
            dict avec reservations, invoices, stats

        Security:
            - Filtre tenant_id sur toutes les requêtes
        """
        reservations = (
            self.db.execute(
                select(Reservation)
                .filter(
                    Reservation.tenant_id == tenant_id,
                    Reservation.customer_id == customer_id,
                )
                .order_by(Reservation.event_date.desc())
            )
            .scalars()
            .all()
        )

        reservation_ids = [r.id for r in reservations]

        invoices: list[Invoice] = []
        if reservation_ids:
            invoices = (
                self.db.execute(
                    select(Invoice)
                    .filter(
                        Invoice.tenant_id == tenant_id,
                        Invoice.reservation_id.in_(reservation_ids),
                    )
                    .order_by(Invoice.issue_date.desc())
                )
                .scalars()
                .all()
            )

        total_revenue_cents = sum(
            r.total_amount_cents for r in reservations if r.total_amount_cents
        )
        last_event_date: Optional[date] = (
            reservations[0].event_date if reservations else None
        )

        return {
            "reservations": list(reservations),
            "invoices": list(invoices),
            "stats": {
                "total_reservations": len(reservations),
                "total_revenue_cents": total_revenue_cents,
                "last_event_date": last_event_date,
            },
        }

    def list_with_pending_relances(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Customer], int]:
        """Liste les clients ayant au moins une relance planifiée (status='scheduled').

        Jointure : Customer → Reservation → Invoice → Relance(status=scheduled)
        """
        pending_subq = (
            select(Relance.id)
            .join(Invoice, Relance.invoice_id == Invoice.id)
            .join(Reservation, Invoice.reservation_id == Reservation.id)
            .where(
                Reservation.customer_id == Customer.id,
                Relance.tenant_id == tenant_id,
                Relance.status == "scheduled",
            )
        ).exists()

        count_q = (
            select(func.count())
            .select_from(Customer)
            .where(Customer.tenant_id == tenant_id, Customer.is_active == True, pending_subq)  # noqa: E712
        )
        total = self.db.execute(count_q).scalar() or 0

        query = (
            select(Customer)
            .where(Customer.tenant_id == tenant_id, Customer.is_active == True, pending_subq)  # noqa: E712
            .order_by(Customer.company_name, Customer.last_name)
            .offset(skip)
            .limit(min(limit, 1000))
        )
        result = self.db.execute(query).scalars().all()
        return (list(result), total)


class AsyncCustomerRepository(AsyncBaseRepository[Customer]):
    """Version async de CustomerRepository pour FastAPI."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Customer)

    async def get_by_email(
        self, email: str, tenant_id: int, include_inactive: bool = False
    ) -> Optional[Customer]:
        query = select(Customer).filter(Customer.email.ilike(email.lower().strip()))
        query = self._apply_tenant_filter(query, tenant_id)
        if not include_inactive:
            query = self._apply_active_filter(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def email_exists(
        self, email: str, tenant_id: int, exclude_id: Optional[int] = None
    ) -> bool:
        query = select(Customer).filter(Customer.email.ilike(email.lower().strip()))
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if exclude_id:
            query = query.filter(Customer.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def list_by_type(
        self, customer_type: str, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> list[Customer]:
        items, _ = await self.list(
            tenant_id=tenant_id, skip=skip, limit=limit,
            filters={"customer_type": customer_type},
        )
        return items

    async def search(
        self,
        search_term: str,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        customer_type: Optional[str] = None,
    ) -> tuple[list[Customer], int]:
        search_pattern = f"%{search_term.lower()}%"
        text_filter = (
            (Customer.first_name.ilike(search_pattern)) |
            (Customer.last_name.ilike(search_pattern)) |
            (Customer.company_name.ilike(search_pattern)) |
            (Customer.email.ilike(search_pattern))
        )

        count_query = select(func.count()).select_from(Customer).filter(text_filter)
        count_query = self._apply_tenant_filter(count_query, tenant_id)
        count_query = self._apply_active_filter(count_query)
        if customer_type:
            count_query = count_query.filter(Customer.customer_type == customer_type)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = select(Customer).filter(text_filter)
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if customer_type:
            query = query.filter(Customer.customer_type == customer_type)
        query = query.order_by(Customer.id).offset(skip).limit(min(limit, 1000))
        result = await self.db.execute(query)
        return (list(result.scalars().all()), total)

    async def get_customer_history(self, customer_id: int, tenant_id: int) -> dict:
        res_result = await self.db.execute(
            select(Reservation)
            .filter(
                Reservation.tenant_id == tenant_id,
                Reservation.customer_id == customer_id,
            )
            .order_by(Reservation.event_date.desc())
        )
        reservations = res_result.scalars().all()
        reservation_ids = [r.id for r in reservations]

        invoices: list[Invoice] = []
        if reservation_ids:
            inv_result = await self.db.execute(
                select(Invoice)
                .filter(
                    Invoice.tenant_id == tenant_id,
                    Invoice.reservation_id.in_(reservation_ids),
                )
                .order_by(Invoice.issue_date.desc())
            )
            invoices = list(inv_result.scalars().all())

        total_revenue_cents = sum(r.total_amount_cents for r in reservations if r.total_amount_cents)
        last_event_date: Optional[date] = reservations[0].event_date if reservations else None
        return {
            "reservations": list(reservations),
            "invoices": invoices,
            "stats": {
                "total_reservations": len(reservations),
                "total_revenue_cents": total_revenue_cents,
                "last_event_date": last_event_date,
            },
        }

    async def list_with_pending_relances(
        self, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> tuple[list[Customer], int]:
        pending_subq = (
            select(Relance.id)
            .join(Invoice, Relance.invoice_id == Invoice.id)
            .join(Reservation, Invoice.reservation_id == Reservation.id)
            .where(
                Reservation.customer_id == Customer.id,
                Relance.tenant_id == tenant_id,
                Relance.status == "scheduled",
            )
        ).exists()

        count_q = (
            select(func.count())
            .select_from(Customer)
            .where(Customer.tenant_id == tenant_id, Customer.is_active == True, pending_subq)  # noqa: E712
        )
        total_result = await self.db.execute(count_q)
        total = total_result.scalar() or 0

        query = (
            select(Customer)
            .where(Customer.tenant_id == tenant_id, Customer.is_active == True, pending_subq)  # noqa: E712
            .order_by(Customer.company_name, Customer.last_name)
            .offset(skip)
            .limit(min(limit, 1000))
        )
        result = await self.db.execute(query)
        return (list(result.scalars().all()), total)
