"""Repository pour l'entité Customer."""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.customer import Customer
from app.repositories.base import BaseRepository


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

    def search_by_name(
        self,
        search_term: str,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> list[Customer]:
        """Recherche des clients par nom/prénom/raison sociale.

        Args:
            search_term: Terme de recherche (case-insensitive)
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Offset pour pagination
            limit: Limite pour pagination

        Returns:
            Liste des clients correspondants

        Security:
            - Filtre tenant_id automatique
        """
        search_pattern = f"%{search_term.lower()}%"

        query = select(Customer).filter(
            (Customer.first_name.ilike(search_pattern)) |
            (Customer.last_name.ilike(search_pattern)) |
            (Customer.company_name.ilike(search_pattern))
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        query = query.order_by(Customer.id)
        query = query.offset(skip).limit(min(limit, 1000))

        result = self.db.execute(query).scalars().all()
        return list(result)
