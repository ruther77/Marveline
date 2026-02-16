"""Repository pour accès aux données utilisateurs avec isolation multi-tenant."""
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository pour les opérations CRUD sur les utilisateurs.

    Hérite de BaseRepository[User] pour bénéficier de:
        - Isolation multi-tenant automatique
        - Support soft delete (is_active)
        - Pagination
        - Cache Redis

    Méthodes additionnelles:
        - get_by_email: Recherche par email dans un tenant
    """

    def __init__(self, db: Session):
        super().__init__(db, User)

    def get_by_email(
        self,
        tenant_id: int,
        email: str,
        include_inactive: bool = False,
    ) -> Optional[User]:
        """Récupère un utilisateur par email dans un tenant.

        Args:
            tenant_id: ID du tenant (isolation stricte)
            email: Email recherché (normalisé en lowercase)
            include_inactive: Inclure les comptes désactivés

        Returns:
            User trouvé ou None
        """
        email = email.lower().strip()
        query = select(User).filter(
            and_(
                User.tenant_id == tenant_id,
                User.email == email,
            )
        )

        if not include_inactive:
            query = query.filter(User.is_active == True)  # noqa: E712

        return self.db.execute(query).scalar_one_or_none()
