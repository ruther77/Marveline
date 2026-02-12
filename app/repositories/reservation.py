"""Repository pour l'entité Reservation."""
from datetime import date
from typing import Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session, joinedload
from app.models.reservation import Reservation, ReservationLine
from app.repositories.base import BaseRepository


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
            joinedload(Reservation.lines).joinedload(ReservationLine.product)
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
    ) -> list[Reservation]:
        """Liste les réservations filtrées par statut.

        Args:
            status: Statut ('draft', 'confirmed', 'in_progress', 'completed', 'cancelled')
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination

        Returns:
            Liste des réservations du statut spécifié
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
    ) -> list[Reservation]:
        """Liste les réservations dans une plage de dates (event_date).

        Args:
            start_date: Date de début (inclusive)
            end_date: Date de fin (inclusive)
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination
            status: Filtrer par statut (optionnel)

        Returns:
            Liste des réservations dans la plage de dates

        Security:
            - Filtre tenant_id automatique
        """
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
        return list(result)

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
                Reservation.status.in_(["draft", "confirmed", "in_progress"])
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
