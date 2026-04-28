"""Repository pour l'entité Reservation."""
from datetime import date, timedelta
from typing import Optional
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.bundle import BundleItem, ProductBundle
from app.models.reservation import Reservation, ReservationLine
from app.repositories.base import BaseRepository, AsyncBaseRepository


class ReservationRepository(BaseRepository[Reservation]):
    """Repository pour les réservations avec méthodes spécialisées."""

    def __init__(self, db: Session):
        """Initialise le repository Reservation.

        Args:
            db: Session SQLAlchemy active
        """
        super().__init__(db, Reservation)

    def get_by_id_with_relations(
        self,
        id: int,
        tenant_id: int,
        include_inactive: bool = False
    ) -> Optional[Reservation]:
        """Récupère une réservation avec ses relations (customer + lines).

        Args:
            id: ID de la réservation
            tenant_id: ID du tenant (OBLIGATOIRE)
            include_inactive: Inclure les réservations soft-deleted

        Returns:
            La réservation avec relations chargées ou None

        Note:
            - Utilise joinedload pour éviter N+1 queries
            - Charge: customer, lines, lines.product
        """
        query = select(Reservation).options(
            joinedload(Reservation.customer),
            joinedload(Reservation.invoices),
            joinedload(Reservation.lines).joinedload(ReservationLine.product),
            joinedload(Reservation.lines).joinedload(ReservationLine.bundle).joinedload(ProductBundle.items).joinedload(BundleItem.product),
            joinedload(Reservation.lines).joinedload(ReservationLine.variant),
        ).filter(Reservation.id == id)

        query = self._apply_tenant_filter(query, tenant_id)

        if not include_inactive:
            query = self._apply_active_filter(query)

        result = self.db.execute(query).unique().scalar_one_or_none()
        return result

    def get_by_reference(
        self,
        reference: str,
        tenant_id: int,
        include_inactive: bool = False
    ) -> Optional[Reservation]:
        """Récupère une réservation par sa référence (unique global).

        Args:
            reference: Référence de la réservation (ex: "RES-2026-0001")
            tenant_id: ID du tenant (OBLIGATOIRE)
            include_inactive: Inclure les réservations soft-deleted

        Returns:
            La réservation trouvée ou None

        Security:
            - Filtre tenant_id automatique
        """
        query = select(Reservation).filter(
            Reservation.reference == reference.upper().strip()
        )
        query = self._apply_tenant_filter(query, tenant_id)

        if not include_inactive:
            query = self._apply_active_filter(query)

        result = self.db.execute(query).scalar_one_or_none()
        return result

    def reference_exists(self, reference: str) -> bool:
        """Vérifie si une référence existe déjà (unique global, pas par tenant).

        Args:
            reference: Référence à vérifier

        Returns:
            True si la référence existe déjà, False sinon

        Note:
            - Pas de filtre tenant_id car référence unique globalement
        """
        query = select(Reservation).filter(
            Reservation.reference == reference.upper().strip()
        )
        result = self.db.execute(query).scalar_one_or_none()
        return result is not None

    def list_by_status(
        self,
        status: str,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[list[Reservation], int]:
        """Liste les réservations filtrées par statut.

        Args:
            status: Statut ('draft', 'confirmed', 'delivered', 'returned', 'cancelled')
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination

        Returns:
            Tuple (items, total) des réservations du statut spécifié
        """
        return self.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters={"status": status}
        )

    def list_by_date_range(
        self,
        start_date: date,
        end_date: date,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> tuple[list[Reservation], int]:
        """Liste les réservations dans une plage de dates (event_date).

        Args:
            start_date: Date de début (inclusive)
            end_date: Date de fin (inclusive)
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination
            status: Filtrer par statut (optionnel)

        Returns:
            Tuple (items, total) des réservations dans la plage de dates

        Security:
            - Filtre tenant_id automatique
        """
        # Compter le total d'abord
        count_query = select(func.count()).select_from(Reservation).filter(
            and_(
                Reservation.event_date >= start_date,
                Reservation.event_date <= end_date
            )
        )
        count_query = self._apply_tenant_filter(count_query, tenant_id)
        count_query = self._apply_active_filter(count_query)

        if status:
            count_query = count_query.filter(Reservation.status == status)

        total = self.db.execute(count_query).scalar() or 0

        # Requête paginée
        query = select(Reservation).filter(
            and_(
                Reservation.event_date >= start_date,
                Reservation.event_date <= end_date
            )
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)

        if status:
            query = query.filter(Reservation.status == status)

        query = query.order_by(Reservation.event_date, Reservation.id)
        query = query.offset(skip).limit(min(limit, 1000))

        result = self.db.execute(query).scalars().all()
        return (list(result), total)

    def list_by_customer(
        self,
        customer_id: int,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> list[Reservation]:
        """Liste les réservations d'un client.

        Args:
            customer_id: ID du client
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination
            status: Filtrer par statut (optionnel)

        Returns:
            Liste des réservations du client

        Security:
            - Filtre tenant_id automatique
        """
        filters = {"customer_id": customer_id}
        if status:
            filters["status"] = status

        return self.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters=filters,
            order_by="event_date"
        )

    def list_for_display(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_id: Optional[int] = None,
    ) -> tuple[list[Reservation], int]:
        """Liste les réservations avec joinedload(customer) pour affichage en liste.

        Args:
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination
            status: Filtrer par statut (optionnel)
            start_date: Date début event_date inclusive (optionnel)
            end_date: Date fin event_date inclusive (optionnel)
            customer_id: Filtrer par client (optionnel)

        Returns:
            Tuple (items, total) avec customer chargé via joinedload

        Security:
            - Filtre tenant_id automatique
        """
        # Requête COUNT
        count_query = select(func.count()).select_from(Reservation)
        count_query = self._apply_tenant_filter(count_query, tenant_id)
        count_query = self._apply_active_filter(count_query)

        if status:
            count_query = count_query.filter(Reservation.status == status)
        if start_date:
            count_query = count_query.filter(Reservation.event_date >= start_date)
        if end_date:
            count_query = count_query.filter(Reservation.event_date <= end_date)
        if customer_id:
            count_query = count_query.filter(Reservation.customer_id == customer_id)

        total = self.db.execute(count_query).scalar() or 0

        # Requête paginée avec joinedload
        query = select(Reservation).options(
            joinedload(Reservation.customer),
            joinedload(Reservation.invoices),
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)

        if status:
            query = query.filter(Reservation.status == status)
        if start_date:
            query = query.filter(Reservation.event_date >= start_date)
        if end_date:
            query = query.filter(Reservation.event_date <= end_date)
        if customer_id:
            query = query.filter(Reservation.customer_id == customer_id)

        query = query.order_by(Reservation.event_date, Reservation.id)
        query = query.offset(skip).limit(min(limit, 1000))

        result = self.db.execute(query).unique().scalars().all()
        return (list(result), total)

    def list_upcoming(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        days_ahead: int = 30
    ) -> list[Reservation]:
        """Liste les réservations à venir (event_date dans les X jours).

        Args:
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination
            days_ahead: Nombre de jours à l'avance (défaut: 30)

        Returns:
            Liste des réservations à venir

        Security:
            - Filtre tenant_id automatique
            - Exclut les réservations annulées et complétées
        """
        from datetime import timedelta
        today = date.today()
        future_date = today + timedelta(days=days_ahead)

        query = select(Reservation).filter(
            and_(
                Reservation.event_date >= today,
                Reservation.event_date <= future_date,
                Reservation.status.in_([
                    "draft", "confirmed", "confirmed_risk",
                    "pre_check", "delivered", "extended",
                ])
            )
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        query = query.order_by(Reservation.event_date, Reservation.id)
        query = query.offset(skip).limit(min(limit, 1000))

        result = self.db.execute(query).scalars().all()
        return list(result)


class ReservationLineRepository(BaseRepository[ReservationLine]):
    """Repository pour les lignes de réservation."""

    def __init__(self, db: Session):
        """Initialise le repository ReservationLine.

        Args:
            db: Session SQLAlchemy active
        """
        super().__init__(db, ReservationLine)

    def list_by_reservation(
        self,
        reservation_id: int,
        tenant_id: int
    ) -> list[ReservationLine]:
        """Liste les lignes d'une réservation.

        Args:
            reservation_id: ID de la réservation
            tenant_id: ID du tenant (OBLIGATOIRE)

        Returns:
            Liste des lignes de la réservation

        Security:
            - Filtre tenant_id automatique
        """
        return self.list(
            tenant_id=tenant_id,
            filters={"reservation_id": reservation_id}
        )

    def list_by_product(
        self,
        product_id: int,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> list[ReservationLine]:
        """Liste les lignes contenant un produit spécifique.

        Args:
            product_id: ID du produit
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination

        Returns:
            Liste des lignes de réservation pour ce produit

        Use cases:
            - Historique des locations d'un produit
            - Vérification disponibilité sur période
        """
        return self.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters={"product_id": product_id}
        )


class AsyncReservationRepository(AsyncBaseRepository[Reservation]):
    """Version async de ReservationRepository pour FastAPI."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Reservation)

    async def get_by_id_with_relations(
        self, id: int, tenant_id: int, include_inactive: bool = False
    ) -> Optional[Reservation]:
        query = select(Reservation).options(
            joinedload(Reservation.customer),
            joinedload(Reservation.invoices),
            joinedload(Reservation.lines).joinedload(ReservationLine.product),
            joinedload(Reservation.lines).joinedload(ReservationLine.bundle).joinedload(ProductBundle.items).joinedload(BundleItem.product),
            joinedload(Reservation.lines).joinedload(ReservationLine.variant),
        ).filter(Reservation.id == id)
        query = self._apply_tenant_filter(query, tenant_id)
        if not include_inactive:
            query = self._apply_active_filter(query)
        result = await self.db.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_by_reference(
        self, reference: str, tenant_id: int, include_inactive: bool = False
    ) -> Optional[Reservation]:
        query = select(Reservation).filter(
            Reservation.reference == reference.upper().strip()
        )
        query = self._apply_tenant_filter(query, tenant_id)
        if not include_inactive:
            query = self._apply_active_filter(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def reference_exists(self, reference: str) -> bool:
        query = select(Reservation).filter(
            Reservation.reference == reference.upper().strip()
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def list_by_status(
        self, status: str, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> tuple[list[Reservation], int]:
        return await self.list(
            tenant_id=tenant_id, skip=skip, limit=limit, filters={"status": status}
        )

    async def list_by_date_range(
        self,
        start_date: date,
        end_date: date,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> tuple[list[Reservation], int]:
        date_filter = and_(
            Reservation.event_date >= start_date, Reservation.event_date <= end_date
        )
        count_query = select(func.count()).select_from(Reservation).filter(date_filter)
        count_query = self._apply_tenant_filter(count_query, tenant_id)
        count_query = self._apply_active_filter(count_query)
        if status:
            count_query = count_query.filter(Reservation.status == status)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = select(Reservation).filter(date_filter)
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if status:
            query = query.filter(Reservation.status == status)
        query = query.order_by(Reservation.event_date, Reservation.id)
        query = query.offset(skip).limit(min(limit, 1000))
        result = await self.db.execute(query)
        return (list(result.scalars().all()), total)

    async def list_by_customer(
        self, customer_id: int, tenant_id: int, skip: int = 0, limit: int = 100,
        status: Optional[str] = None
    ) -> list[Reservation]:
        filters: dict = {"customer_id": customer_id}
        if status:
            filters["status"] = status
        items, _ = await self.list(
            tenant_id=tenant_id, skip=skip, limit=limit, filters=filters, order_by="event_date"
        )
        return items

    async def list_for_display(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_id: Optional[int] = None,
        assigned_user_id: Optional[int] = None,
        include_archived: bool = False,
    ) -> tuple[list[Reservation], int]:
        def _apply_filters(q):
            q = self._apply_tenant_filter(q, tenant_id)
            q = self._apply_active_filter(q)
            if not include_archived:
                q = q.filter(Reservation.is_archived.is_(False))
            if status:
                q = q.filter(Reservation.status == status)
            if start_date:
                q = q.filter(Reservation.event_date >= start_date)
            if end_date:
                q = q.filter(Reservation.event_date <= end_date)
            if customer_id:
                q = q.filter(Reservation.customer_id == customer_id)
            if assigned_user_id is not None:
                q = q.filter(Reservation.assigned_user_id == assigned_user_id)
            return q

        count_query = _apply_filters(select(func.count()).select_from(Reservation))
        total = (await self.db.execute(count_query)).scalar() or 0

        query = _apply_filters(
            select(Reservation).options(
                joinedload(Reservation.customer),
                joinedload(Reservation.invoices),
            )
        )
        query = query.order_by(Reservation.event_date, Reservation.id)
        query = query.offset(skip).limit(min(limit, 1000))
        result = await self.db.execute(query)
        return (list(result.unique().scalars().all()), total)

    async def list_upcoming(
        self, tenant_id: int, skip: int = 0, limit: int = 100, days_ahead: int = 30
    ) -> list[Reservation]:
        today = date.today()
        future_date = today + timedelta(days=days_ahead)
        query = select(Reservation).filter(
            and_(
                Reservation.event_date >= today,
                Reservation.event_date <= future_date,
                Reservation.status.in_([
                    "draft", "confirmed", "confirmed_risk",
                    "pre_check", "delivered", "extended",
                ]),
            )
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        query = query.order_by(Reservation.event_date, Reservation.id)
        query = query.offset(skip).limit(min(limit, 1000))
        result = await self.db.execute(query)
        return list(result.scalars().all())


class AsyncReservationLineRepository(AsyncBaseRepository[ReservationLine]):
    """Version async de ReservationLineRepository pour FastAPI."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, ReservationLine)

    async def list_by_reservation(
        self, reservation_id: int, tenant_id: int
    ) -> list[ReservationLine]:
        items, _ = await self.list(
            tenant_id=tenant_id, filters={"reservation_id": reservation_id}
        )
        return items

    async def list_by_product(
        self, product_id: int, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> list[ReservationLine]:
        items, _ = await self.list(
            tenant_id=tenant_id, skip=skip, limit=limit, filters={"product_id": product_id}
        )
        return items
