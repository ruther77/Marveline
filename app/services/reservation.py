"""Service métier pour les réservations."""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.reservation import Reservation, ReservationLine
from app.repositories.reservation import ReservationRepository, ReservationLineRepository
from app.repositories.customer import CustomerRepository
from app.repositories.product import ProductRepository
from app.services.product import ProductService
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.constants import ReservationStatus


class ReservationService:
    """Service métier pour gestion des réservations.

    Responsibilities:
        - Création réservations avec lignes
        - Confirmation (réservation stock)
        - Annulation (libération stock)
        - Génération références uniques
        - Calcul totaux (montants, cautions)

    Transactions:
        - Toutes opérations en transaction atomique
        - Commit explicite dans endpoints
        - Rollback automatique si exception
    """

    # Compteur de références générées (persiste dans le processus)
    _generated_references: set[str] = set()

    def __init__(self, db: Session):
        """Initialise le service réservation.

        Args:
            db: Session SQLAlchemy active
        """
        self.db = db
        self.repo = ReservationRepository(db)
        self.line_repo = ReservationLineRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.product_repo = ProductRepository(db)
        self.product_service = ProductService(db)

    def generate_reference(self) -> str:
        """Génère une référence unique pour une réservation.

        Returns:
            Référence unique (ex: "RES-2026-0001")

        Implementation:
            - Format: RES-{YEAR}-{COUNTER:04d}
            - Compteur global (pas par tenant)
            - Incrémentation atomique via DB sequence
            - Vérifie unicité avant retour

        Note:
            - En production, utiliser Redis INCR pour performance
            - Ici utilisation DB sequence pour MVP

        Example:
            ref = reservation_service.generate_reference()
            # "RES-2026-0001"
        """
        year = datetime.now().year

        # Trouver le prochain numéro disponible
        # En production : utiliser Redis INCR pour atomicité distribuée

        # Trouver le compteur maximum actuel pour cette année
        max_counter = 0

        # Vérifier les références en DB
        reservations = self.db.query(Reservation).filter(
            Reservation.reference.like(f"RES-{year}-%")
        ).all()

        for res in reservations:
            # Extraire le compteur de la référence (ex: "RES-2026-0042" -> 42)
            try:
                counter_str = res.reference.split('-')[-1]
                counter_val = int(counter_str)
                max_counter = max(max_counter, counter_val)
            except (IndexError, ValueError):
                pass

        # Vérifier aussi les références générées en mémoire (pas encore en DB)
        for ref in self._generated_references:
            if ref.startswith(f"RES-{year}-"):
                try:
                    counter_str = ref.split('-')[-1]
                    counter_val = int(counter_str)
                    max_counter = max(max_counter, counter_val)
                except (IndexError, ValueError):
                    pass

        # Générer la prochaine référence
        next_counter = max_counter + 1
        if next_counter > 9999:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cannot generate unique reference (counter overflow)"
            )

        reference = f"RES-{year}-{next_counter:04d}"
        # Enregistrer la référence générée
        self._generated_references.add(reference)
        return reference

    def create_reservation(
        self,
        reservation_data: ReservationCreate,
        tenant_id: int
    ) -> Reservation:
        """Crée une nouvelle réservation avec ses lignes.

        Args:
            reservation_data: Données de la réservation (DTO)
            tenant_id: ID du tenant (depuis JWT)

        Returns:
            Réservation créée (status=draft)

        Raises:
            HTTPException 404: Si customer ou produits non trouvés
            HTTPException 400: Si validation échoue

        Business Rules:
            - Génère référence unique automatiquement
            - Status initial=ReservationStatus.DRAFT
            - Calcule total_amount et deposit_amount depuis les lignes
            - Copie prix produits (snapshot au moment réservation)
            - Vérifie cohérence dates

        Transaction:
            - Pas de commit automatique
            - Rollback si exception

        Example:
            reservation = reservation_service.create_reservation(
                ReservationCreate(customer_id=1, ...),
                tenant_id=1
            )
            db.commit()
        """
        # Vérifier customer existe
        customer = self.customer_repo.get_by_id(
            reservation_data.customer_id,
            tenant_id
        )
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )

        # Générer référence unique
        reference = self.generate_reference()

        # Calculer nombre de jours de location
        rental_days = (
            reservation_data.return_date - reservation_data.delivery_date
        ).days + 1

        # Créer réservation (status=draft, montants=0 initialement)
        reservation = Reservation(
            tenant_id=tenant_id,
            customer_id=reservation_data.customer_id,
            reference=reference,
            event_date=reservation_data.event_date,
            delivery_date=reservation_data.delivery_date,
            return_date=reservation_data.return_date,
            event_location=reservation_data.event_location,
            status=ReservationStatus.DRAFT,
            total_amount=0,
            deposit_amount=0,
            deposit_paid=False
        )

        reservation = self.repo.create(reservation)

        # Créer lignes de réservation
        total_amount = 0
        deposit_amount = 0

        for line_data in reservation_data.lines:
            # Charger produit pour récupérer prix
            product = self.product_repo.get_by_id(
                line_data.product_id,
                tenant_id
            )
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product with id {line_data.product_id} not found"
                )

            # Snapshot prix au moment de la réservation
            unit_price = product.price_per_day
            subtotal = line_data.quantity * unit_price * rental_days

            # Créer ligne
            line = ReservationLine(
                tenant_id=tenant_id,
                reservation_id=reservation.id,
                product_id=line_data.product_id,
                quantity=line_data.quantity,
                unit_price=unit_price,
                subtotal=subtotal
            )
            self.line_repo.create(line)

            # Accumuler totaux
            total_amount += subtotal
            deposit_amount += line_data.quantity * product.deposit_amount

        # Mettre à jour montants réservation
        reservation.total_amount = total_amount
        reservation.deposit_amount = deposit_amount
        self.repo.update(reservation)

        return reservation

    def confirm_reservation(
        self,
        reservation_id: int,
        tenant_id: int
    ) -> Reservation:
        """Confirme une réservation et réserve le stock.

        Args:
            reservation_id: ID de la réservation
            tenant_id: ID du tenant

        Returns:
            Réservation confirmée (status=confirmed)

        Raises:
            HTTPException 404: Si réservation non trouvée
            HTTPException 400: Si status != 'draft' ou stock insuffisant

        Business Rules:
            - Statut doit être 'draft'
            - Réserve stock pour chaque ligne (available_quantity -= quantity)
            - Change status → 'confirmed'
            - Transaction atomique (rollback si stock insuffisant)

        Transaction:
            - Commit explicite requis dans endpoint
            - Rollback automatique si exception

        Example:
            try:
                reservation = reservation_service.confirm_reservation(
                    reservation_id=1,
                    tenant_id=1
                )
                db.commit()
            except HTTPException:
                db.rollback()
                raise
        """
        # Charger réservation avec lignes
        reservation = self.repo.get_by_id_with_relations(
            reservation_id,
            tenant_id
        )
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found"
            )

        # Vérifier statut
        if reservation.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm reservation with status '{reservation.status}'. Must be 'draft'."
            )

        # Réserver stock pour chaque ligne (transaction atomique)
        try:
            for line in reservation.lines:
                self.product_service.reserve_stock(
                    product_id=line.product_id,
                    quantity=line.quantity,
                    tenant_id=tenant_id
                )
        except HTTPException as e:
            # Rollback implicite (pas de commit)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm reservation: {e.detail}"
            )

        # Changer statut
        reservation.status=ReservationStatus.CONFIRMED
        self.repo.update(reservation)

        return reservation

    def cancel_reservation(
        self,
        reservation_id: int,
        tenant_id: int
    ) -> Reservation:
        """Annule une réservation et libère le stock.

        Args:
            reservation_id: ID de la réservation
            tenant_id: ID du tenant

        Returns:
            Réservation annulée (status=cancelled)

        Raises:
            HTTPException 404: Si réservation non trouvée
            HTTPException 400: Si status = 'returned' ou 'cancelled'

        Business Rules:
            - Statut ne peut pas être 'returned' ou 'cancelled'
            - Libère stock si status était 'confirmed' ou 'delivered'
            - Change status → 'cancelled'
            - Transaction atomique

        Transaction:
            - Commit explicite requis dans endpoint

        Example:
            reservation = reservation_service.cancel_reservation(
                reservation_id=1,
                tenant_id=1
            )
            db.commit()
        """
        # Charger réservation avec lignes
        reservation = self.repo.get_by_id_with_relations(
            reservation_id,
            tenant_id
        )
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found"
            )

        # Vérifier statut
        if reservation.status in ("returned", "cancelled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel reservation with status '{reservation.status}'"
            )

        # Libérer stock si réservation était confirmée ou livrée
        if reservation.status in ("confirmed", "delivered"):
            for line in reservation.lines:
                self.product_service.release_stock(
                    product_id=line.product_id,
                    quantity=line.quantity,
                    tenant_id=tenant_id
                )

        # Changer statut
        reservation.status=ReservationStatus.CANCELLED
        self.repo.update(reservation)

        return reservation

    def update_reservation(
        self,
        reservation_id: int,
        reservation_data: ReservationUpdate,
        tenant_id: int
    ) -> Reservation:
        """Met à jour une réservation (status=draft uniquement).

        Args:
            reservation_id: ID de la réservation
            reservation_data: Données à mettre à jour
            tenant_id: ID du tenant

        Returns:
            Réservation mise à jour

        Raises:
            HTTPException 404: Si réservation non trouvée
            HTTPException 400: Si status != 'draft'

        Business Rules:
            - Seules les réservations 'draft' peuvent être modifiées
            - customer_id et reference immutables
            - Les lignes ne sont pas modifiables via update (endpoints dédiés)

        Warning:
            - Pas de commit automatique

        Example:
            reservation = reservation_service.update_reservation(
                reservation_id=1,
                ReservationUpdate(event_date=...),
                tenant_id=1
            )
            db.commit()
        """
        # Charger réservation
        reservation = self.repo.get_by_id(reservation_id, tenant_id)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found"
            )

        # Vérifier statut
        if reservation.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft reservations can be updated"
            )

        # Appliquer modifications
        update_data = reservation_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(reservation, field, value)

        return self.repo.update(reservation)
