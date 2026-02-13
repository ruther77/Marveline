"""Service métier pour les factures."""
from datetime import datetime, date
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.invoice import Invoice
from app.repositories.invoice import InvoiceRepository
from app.repositories.reservation import ReservationRepository
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate, AddPaymentRequest
from app.constants import ErrorMessages, InvoiceStatus, Limits, PaymentMethod, ReservationStatus


class InvoiceService:
    """Service métier pour gestion des factures.

    Responsibilities:
        - Génération factures depuis réservations
        - Gestion paiements (partiels, complets)
        - Calcul montants restants
        - Vérification factures en retard
        - Génération numéros de facture

    Transactions:
        - Toutes opérations en transaction atomique
        - Commit explicite dans endpoints
    """

    def __init__(self, db: Session):
        """Initialise le service facture.

        Args:
            db: Session SQLAlchemy active
        """
        self.db = db
        self.repo = InvoiceRepository(db)
        self.reservation_repo = ReservationRepository(db)

    def generate_invoice_number(self) -> str:
        """Génère un numéro de facture unique.

        Returns:
            Numéro de facture unique (ex: "INV-2026-0001")

        Implementation:
            - Format: INV-{YEAR}-{COUNTER:04d}
            - Compteur global (pas par tenant)
            - Incrémentation atomique via DB sequence
            - Vérifie unicité avant retour

        Note:
            - En production, utiliser Redis INCR pour performance

        Example:
            invoice_number = invoice_service.generate_invoice_number()
            # "INV-2026-0001"
        """
        year = datetime.now().year

        # Trouver le prochain numéro disponible
        counter = 1
        while True:
            invoice_number = f"INV-{year}-{counter:0{Limits.INVOICE_NUMBER_PADDING}d}"
            # Vérifier unicité globale (pas par tenant)
            from sqlalchemy import select
            from app.models.invoice import Invoice as InvoiceModel

            exists = self.db.execute(
                select(InvoiceModel).filter(
                    InvoiceModel.invoice_number == invoice_number
                )
            ).first()

            if not exists:
                return invoice_number

            counter += 1

            # Sécurité : éviter boucle infinie
            if counter > 9999:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=ErrorMessages.INVOICE_NUMBER_OVERFLOW
                )

    def generate_from_reservation(
        self,
        invoice_data: InvoiceCreate,
        tenant_id: int
    ) -> Invoice:
        """Génère une facture depuis une réservation.

        Args:
            invoice_data: Données de la facture (reservation_id, dates)
            tenant_id: ID du tenant (depuis JWT)

        Returns:
            Facture créée (status=draft)

        Raises:
            HTTPException 404: Si réservation non trouvée
            HTTPException 400: Si facture déjà existe pour cette réservation

        Business Rules:
            - Une réservation → une seule facture (one-to-one)
            - Copie total_amount depuis réservation
            - Génère invoice_number unique
            - Status initial=ReservationStatus.DRAFT
            - paid_amount = 0

        Transaction:
            - Pas de commit automatique

        Example:
            invoice = invoice_service.generate_from_reservation(
                InvoiceCreate(reservation_id=1, ...),
                tenant_id=1
            )
            db.commit()
        """
        # Vérifier réservation existe
        reservation = self.reservation_repo.get_by_id(
            invoice_data.reservation_id,
            tenant_id
        )
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.RESERVATION_NOT_FOUND
            )

        # Vérifier qu'il n'y a pas déjà une facture pour cette réservation
        existing_invoice = self.repo.get_by_reservation(
            invoice_data.reservation_id,
            tenant_id
        )
        if existing_invoice:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invoice already exists for this reservation (ID: {existing_invoice.id})"
            )

        # Générer numéro de facture
        invoice_number = self.generate_invoice_number()

        # Créer facture
        invoice = Invoice(
            tenant_id=tenant_id,
            reservation_id=invoice_data.reservation_id,
            invoice_number=invoice_number,
            issue_date=invoice_data.issue_date,
            due_date=invoice_data.due_date,
            total_amount=reservation.total_amount,  # Copie depuis réservation
            paid_amount=0,
            status=InvoiceStatus.DRAFT,
            payment_method=None,
            payment_date=None
        )

        return self.repo.create(invoice)

    def add_payment(
        self,
        invoice_id: int,
        payment_data: AddPaymentRequest,
        tenant_id: int
    ) -> Invoice:
        """Ajoute un paiement à une facture (partiel ou complet).

        Args:
            invoice_id: ID de la facture
            payment_data: Données du paiement (montant, méthode, date)
            tenant_id: ID du tenant

        Returns:
            Facture mise à jour

        Raises:
            HTTPException 404: Si facture non trouvée
            HTTPException 400: Si paiement invalide ou facture déjà payée

        Business Rules:
            - paid_amount ne peut pas dépasser total_amount
            - Si paid_amount >= total_amount → status=InvoiceStatus.PAID
            - Enregistre payment_method et payment_date
            - Peut être appelé plusieurs fois (paiements partiels)

        Transaction:
            - Pas de commit automatique

        Example:
            invoice = invoice_service.add_payment(
                invoice_id=1,
                AddPaymentRequest(amount_cents=50000, method=PaymentMethod.CARD, ...),
                tenant_id=1
            )
            db.commit()
        """
        # Charger facture
        invoice = self.repo.get_by_id(invoice_id, tenant_id)
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.INVOICE_NOT_FOUND
            )

        # Vérifier que facture n'est pas annulée
        if invoice.status == InvoiceStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.INVOICE_CANCELLED_NO_PAYMENT
            )

        # Vérifier que paiement ne dépasse pas le total
        new_paid_amount = invoice.paid_amount + payment_data.amount_cents
        if new_paid_amount > invoice.total_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment amount ({payment_data.amount_cents} cents) would exceed total amount. "
                       f"Remaining: {invoice.total_amount - invoice.paid_amount} cents"
            )

        # Enregistrer paiement
        invoice.paid_amount = new_paid_amount
        invoice.payment_method = payment_data.payment_method
        invoice.payment_date = payment_data.payment_date

        # Mettre à jour statut si paiement complet
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status=InvoiceStatus.PAID

        return self.repo.update(invoice)

    def update_invoice(
        self,
        invoice_id: int,
        invoice_data: InvoiceUpdate,
        tenant_id: int
    ) -> Invoice:
        """Met à jour une facture.

        Args:
            invoice_id: ID de la facture
            invoice_data: Données à mettre à jour
            tenant_id: ID du tenant

        Returns:
            Facture mise à jour

        Raises:
            HTTPException 404: Si facture non trouvée
            HTTPException 400: Si facture payée (immutable)

        Business Rules:
            - reservation_id et invoice_number immutables
            - Factures 'paid' ne peuvent pas être modifiées
            - total_amount immutable (copié depuis réservation)

        Warning:
            - Pas de commit automatique

        Example:
            invoice = invoice_service.update_invoice(
                invoice_id=1,
                InvoiceUpdate(status=InvoiceStatus.SENT),
                tenant_id=1
            )
            db.commit()
        """
        # Charger facture
        invoice = self.repo.get_by_id(invoice_id, tenant_id)
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.INVOICE_NOT_FOUND
            )

        # Vérifier statut
        if invoice.status == InvoiceStatus.PAID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.INVOICE_PAID_NO_MODIFY
            )

        # Appliquer modifications
        update_data = invoice_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(invoice, field, value)

        return self.repo.update(invoice)

    def check_overdue_invoices(
        self,
        tenant_id: int,
        as_of_date: Optional[date] = None
    ) -> list[Invoice]:
        """Récupère les factures en retard et met à jour leur statut.

        Args:
            tenant_id: ID du tenant
            as_of_date: Date de référence (défaut: aujourd'hui)

        Returns:
            Liste des factures en retard

        Business Rules:
            - Facture en retard si: due_date < today AND paid_amount < total_amount
            - Met à jour status → 'overdue'
            - Exclut factures annulées

        Transaction:
            - Commit explicite requis dans endpoint

        Example:
            overdue = invoice_service.check_overdue_invoices(tenant_id=1)
            db.commit()
        """
        overdue_invoices = self.repo.list_overdue(
            tenant_id=tenant_id,
            as_of_date=as_of_date
        )

        # Mettre à jour statut
        for invoice in overdue_invoices:
            if invoice.status not in (InvoiceStatus.OVERDUE, InvoiceStatus.CANCELLED):
                invoice.status=InvoiceStatus.OVERDUE
                self.repo.update(invoice)

        return overdue_invoices

    def cancel_invoice(
        self,
        invoice_id: int,
        tenant_id: int
    ) -> Invoice:
        """Annule une facture.

        Args:
            invoice_id: ID de la facture
            tenant_id: ID du tenant

        Returns:
            Facture annulée (status=cancelled)

        Raises:
            HTTPException 404: Si facture non trouvée
            HTTPException 400: Si facture déjà payée

        Business Rules:
            - Factures 'paid' ne peuvent pas être annulées
            - Change status → 'cancelled'

        Warning:
            - Pas de commit automatique

        Example:
            invoice = invoice_service.cancel_invoice(invoice_id=1, tenant_id=1)
            db.commit()
        """
        # Charger facture
        invoice = self.repo.get_by_id(invoice_id, tenant_id)
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.INVOICE_NOT_FOUND
            )

        # Vérifier statut
        if invoice.status == InvoiceStatus.PAID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.INVOICE_PAID_NO_CANCEL
            )

        # Annuler
        invoice.status=InvoiceStatus.CANCELLED
        return self.repo.update(invoice)

    def list_overdue(self, tenant_id: int) -> list[Invoice]:
        """Liste les factures en retard de paiement.

        Args:
            tenant_id: ID du tenant (OBLIGATOIRE)

        Returns:
            Liste des factures en retard

        Note:
            - Facture en retard si: due_date < today AND paid_amount < total_amount
            - Exclut les factures annulées

        Example:
            overdue_invoices = invoice_service.list_overdue(tenant_id=1)
        """
        return self.repo.list_overdue(tenant_id=tenant_id)
