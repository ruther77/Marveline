"""Service métier pour la gestion des clients."""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.customer import Customer
from app.repositories.customer import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.constants import ErrorMessages


logger = logging.getLogger(__name__)


class CustomerService:
    """Service métier pour gestion des clients (particuliers et entreprises).

    Responsibilities:
        - CRUD clients avec validation métier
        - Validation unicité email par tenant
        - Recherche et filtrage clients
        - Gestion soft delete / hard delete

    Transactions:
        - Pas de commit automatique
        - Rollback automatique en cas d'exception
    """

    def __init__(self, db: Session):
        """Initialise le service customer.

        Args:
            db: Session SQLAlchemy active
        """
        self.db = db
        self.repo = CustomerRepository(db)

    def list_customers(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        search_query: Optional[str] = None,
        customer_type: Optional[str] = None,
        include_inactive: bool = False,
    ) -> tuple[list[Customer], int]:
        """Liste les clients avec filtres et pagination.

        Args:
            tenant_id: ID du tenant
            skip: Offset pagination
            limit: Limite pagination
            search_query: Recherche textuelle (nom, prénom, entreprise)
            customer_type: Filtre par type (individual, company)
            include_inactive: Inclure clients soft-deleted

        Returns:
            Tuple (items, total) où items est la liste paginée

        Example:
            customers, total = customer_service.list_customers(
                tenant_id=1,
                skip=0,
                limit=20,
                search_query="dupont"
            )
        """
        # Recherche textuelle si fournie
        if search_query:
            return self.repo.search(
                search_term=search_query,
                tenant_id=tenant_id,
                skip=skip,
                limit=limit,
            )

        # Liste standard avec filtres
        filters = {}
        if customer_type:
            filters["customer_type"] = customer_type
        if include_inactive:
            filters["include_inactive"] = True

        return self.repo.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters=filters if filters else None,
        )

    def get_customer(
        self,
        customer_id: int,
        tenant_id: int,
    ) -> Customer:
        """Récupère un client par ID.

        Args:
            customer_id: ID du client
            tenant_id: ID du tenant

        Returns:
            Client trouvé

        Raises:
            HTTPException 404: Si client non trouvé
        """
        customer = self.repo.get_by_id(customer_id, tenant_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.CUSTOMER_NOT_FOUND,
            )
        return customer

    def create_customer(
        self,
        customer_data: CustomerCreate,
        tenant_id: int,
    ) -> Customer:
        """Crée un nouveau client.

        Args:
            customer_data: Données du client (DTO)
            tenant_id: ID du tenant

        Returns:
            Client créé

        Raises:
            HTTPException 400: Si email déjà existant ou données invalides

        Business Rules:
            - Type "individual": first_name + last_name obligatoires
            - Type "company": company_name + siret obligatoires
            - Email unique par tenant (si fourni)
            - is_active = True par défaut

        Transaction:
            - Pas de commit automatique
            - Rollback si exception
        """
        # Validation unicité email si fourni
        if customer_data.email:
            if self.repo.email_exists(customer_data.email, tenant_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Customer with email '{customer_data.email}' already exists",
                )

        # Créer modèle Customer
        customer = Customer(
            tenant_id=tenant_id,
            customer_type=customer_data.customer_type,
            first_name=customer_data.first_name,
            last_name=customer_data.last_name,
            email=customer_data.email,
            phone=customer_data.phone,
            address=customer_data.address,
            city=customer_data.city,
            postal_code=customer_data.postal_code,
            country=customer_data.country,
            company_name=customer_data.company_name,
            is_active=True,
        )

        # Créer en DB
        customer = self.repo.create(customer)
        return customer

    def update_customer(
        self,
        customer_id: int,
        customer_data: CustomerUpdate,
        tenant_id: int,
    ) -> Customer:
        """Met à jour un client existant (PATCH partiel).

        Args:
            customer_id: ID du client
            customer_data: Données à mettre à jour (PATCH)
            tenant_id: ID du tenant

        Returns:
            Client mis à jour

        Raises:
            HTTPException 404: Si client non trouvé
            HTTPException 400: Si email déjà utilisé

        Business Rules:
            - Email unique si modifié
            - Seuls champs fournis sont mis à jour

        Transaction:
            - Pas de commit automatique
        """
        # Charger client
        customer = self.get_customer(customer_id, tenant_id)

        # Validation unicité email si modifié
        if customer_data.email and customer_data.email != customer.email:
            if self.repo.email_exists(
                customer_data.email, tenant_id, exclude_id=customer_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email '{customer_data.email}' already used by another customer",
                )

        # Appliquer modifications (PATCH partiel)
        update_data = customer_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(customer, field, value)

        customer = self.repo.update(customer)
        return customer

    def delete_customer(
        self,
        customer_id: int,
        tenant_id: int,
        hard_delete: bool = False,
    ) -> bool:
        """Supprime un client (soft delete par défaut).

        Args:
            customer_id: ID du client
            tenant_id: ID du tenant
            hard_delete: Si True, suppression physique

        Returns:
            True si suppression réussie

        Raises:
            HTTPException 404: Si client non trouvé
            HTTPException 400: Si contraintes FK (hard delete)

        Business Rules:
            - Soft delete par défaut (is_active=False)
            - Hard delete seulement si aucune réservation liée

        Transaction:
            - Pas de commit automatique
        """
        if hard_delete:
            success = self.repo.hard_delete(customer_id, tenant_id)
        else:
            success = self.repo.soft_delete(customer_id, tenant_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.CUSTOMER_NOT_FOUND,
            )

        return True
