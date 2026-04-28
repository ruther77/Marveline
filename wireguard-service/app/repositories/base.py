"""Base Repository pour le microservice WireGuard.

Pattern TenantAwareBaseRepository : chaque requête est automatiquement
filtrée par tenant_id pour garantir l'isolation multi-tenant.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.base import Base

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=Base)

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


@dataclass
class PaginatedResult(Generic[ModelType]):
    """Résultat paginé avec métadonnées."""

    items: List[ModelType]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


class RepositoryException(Exception):
    """Exception de base pour les repositories."""
    pass


class PaginationError(RepositoryException):
    """Erreur de pagination (page/page_size invalide)."""
    pass


class TenantIsolationError(RepositoryException):
    """Tentative de violation de l'isolation tenant."""
    pass


class TenantAwareBaseRepository(Generic[ModelType]):
    """Repository de base avec isolation multi-tenant automatique.

    Toutes les requêtes sont filtrées par tenant_id.
    Le tenant_id est forcé à la création et interdit à la modification.
    """

    model: Type[ModelType]

    def __init__(self, session: Session, tenant_id: int) -> None:
        if tenant_id <= 0:
            raise TenantIsolationError(
                f"tenant_id must be positive, got {tenant_id}"
            )
        self.session = session
        self._tenant_id = tenant_id

    @property
    def tenant_id(self) -> int:
        return self._tenant_id

    def _tenant_query(self):
        """Requête de base pré-filtrée par tenant_id."""
        return select(self.model).where(
            self.model.tenant_id == self._tenant_id
        )

    def get(self, id: Any) -> Optional[ModelType]:
        """Récupère une entité par ID dans le tenant courant."""
        stmt = self._tenant_query().where(self.model.id == id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_all(
        self, skip: int = 0, limit: int = DEFAULT_PAGE_SIZE
    ) -> List[ModelType]:
        """Liste les entités du tenant avec offset/limit."""
        limit = min(limit, MAX_PAGE_SIZE)
        stmt = self._tenant_query().offset(skip).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def create(self, data: Dict[str, Any]) -> ModelType:
        """Crée une entité en forçant le tenant_id."""
        data.pop("tenant_id", None)
        entity = self.model(**data, tenant_id=self._tenant_id)
        self.session.add(entity)
        self.session.flush()
        return entity

    def update(
        self, id: Any, data: Dict[str, Any]
    ) -> Optional[ModelType]:
        """Met à jour une entité. Interdit de changer le tenant_id."""
        if "tenant_id" in data:
            raise TenantIsolationError(
                "Cannot modify tenant_id on an existing entity"
            )

        entity = self.get(id)
        if entity is None:
            return None

        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)

        self.session.flush()
        return entity

    def soft_delete(self, id: Any) -> bool:
        """Suppression logique (is_active = False)."""
        entity = self.get(id)
        if entity is None:
            return False

        if hasattr(entity, "soft_delete"):
            entity.soft_delete()
        else:
            entity.is_active = False

        self.session.flush()
        return True

    def count(self) -> int:
        """Compte les entités du tenant."""
        stmt = select(func.count()).select_from(self.model).where(
            self.model.tenant_id == self._tenant_id
        )
        return self.session.execute(stmt).scalar() or 0

    def exists(self, id: Any) -> bool:
        """Vérifie si une entité existe dans le tenant."""
        return self.get(id) is not None

    def paginate(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        query=None,
    ) -> PaginatedResult[ModelType]:
        """Pagination générique avec comptage total."""
        if page < 1:
            raise PaginationError("page must be >= 1")
        if page_size < 1:
            raise PaginationError("page_size must be >= 1")

        page_size = min(page_size, MAX_PAGE_SIZE)

        if query is None:
            query = self._tenant_query()

        count_stmt = select(func.count()).select_from(query.subquery())
        total = self.session.execute(count_stmt).scalar() or 0

        offset = (page - 1) * page_size
        items_stmt = query.offset(offset).limit(page_size)
        items = list(self.session.execute(items_stmt).scalars().all())

        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
