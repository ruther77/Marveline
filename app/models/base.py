"""Modèles de base SQLAlchemy avec mixins pour timestamps et multi-tenant."""
from datetime import datetime
from typing import Any
from sqlalchemy import BigInteger, Boolean, DateTime, func, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Classe de base pour tous les modèles SQLAlchemy.

    Fournit méthodes de sérialisation pour cache Redis :
    - to_dict() : ORM → dict JSON-serializable
    - from_dict() : dict → ORM instance
    """

    def to_dict(self, exclude_relations: bool = True) -> dict[str, Any]:
        """Convertit instance ORM en dict JSON-serializable.

        Args:
            exclude_relations: Exclure relations lazy-loaded (défaut: True)

        Returns:
            Dict avec toutes les colonnes (pas les relations)

        Example:
            >>> product = Product(id=1, name="Assiette", price_cents=250)
            >>> product.to_dict()
            {"id": 1, "name": "Assiette", "price_cents": 250, "created_at": "2024-01-15T10:30:00"}

        Notes:
            - datetime converti en ISO format string
            - Relations exclues par défaut (évite N+1 queries)
            - Compatible cache Redis (JSON serializable)
        """
        result = {}

        # Itérer sur colonnes de la table (pas relations)
        mapper = inspect(self.__class__)
        for column in mapper.columns:
            value = getattr(self, column.name)

            # Convertir datetime en ISO string pour JSON
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Crée instance ORM depuis dict.

        Args:
            data: Dict avec colonnes (depuis cache ou API)

        Returns:
            Instance ORM (non attachée à session)

        Example:
            >>> data = {"id": 1, "name": "Assiette", "price_cents": 250}
            >>> product = Product.from_dict(data)

        Notes:
            - Instance créée mais PAS ajoutée à session DB
            - Datetime ISO strings convertis en datetime objects
            - Colonnes inconnues ignorées (safety)
        """
        # Filtrer uniquement colonnes valides
        mapper = inspect(cls)
        valid_columns = {c.name for c in mapper.columns}

        # Filtrer data pour garder uniquement colonnes existantes
        filtered_data = {k: v for k, v in data.items() if k in valid_columns}

        # Convertir ISO strings en datetime
        for column in mapper.columns:
            if column.name in filtered_data and isinstance(column.type, DateTime):
                if isinstance(filtered_data[column.name], str):
                    filtered_data[column.name] = datetime.fromisoformat(
                        filtered_data[column.name]
                    )

        # Créer instance (sans l'ajouter à session)
        return cls(**filtered_data)


class TimestampMixin:
    """Mixin pour ajouter created_at et updated_at à tous les modèles."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Date de création de l'enregistrement"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Date de dernière modification"
    )


class TenantMixin:
    """Mixin pour multi-tenant - toutes les tables métier doivent l'inclure."""

    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="ID du tenant (organisation cliente)"
    )


class SoftDeleteMixin:
    """Mixin pour suppression logique (soft delete)."""

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Actif (False = supprimé logiquement)"
    )

    def soft_delete(self) -> None:
        """Suppression logique."""
        self.is_active = False

    def restore(self) -> None:
        """Restaurer après suppression logique."""
        self.is_active = True
