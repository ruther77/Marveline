"""Repository pour l'entité Invoice."""
from datetime import date
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import Session, joinedload
from app.models.invoice import Invoice
from app.models.reservation import Reservation
from app.repositories.base import BaseRepository
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
            joinedload(Invoice.reservation).joinedload(Reservation.customer)
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
            - Facture en retard si: due_date < today AND paid_amount < total_amount
            - Exclut les factures annulées

        Security:
            - Filtre tenant_id automatique
        """
        reference_date = as_of_date or date.today()

        query = select(Invoice).filter(
            and_(
                Invoice.due_date < reference_date,
                Invoice.paid_amount < Invoice.total_amount,
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
        """Liste les factures non payées (paid_amount < total_amount).

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
                Invoice.paid_amount < Invoice.total_amount,
                Invoice.status != InvoiceStatus.CANCELLED
            )
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        query = query.order_by(Invoice.due_date, Invoice.id)
        query = query.offset(skip).limit(min(limit, 1000))

        result = self.db.execute(query).scalars().all()
        return list(result)

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
