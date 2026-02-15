"""Repository pour les Feature Flags (entite globale, pas de TenantMixin)."""
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.feature_flag import FeatureFlag


class FeatureFlagRepository:
    """Repository pour CRUD des feature flags.

    Les feature flags sont GLOBAUX (pas de TenantMixin).
    Le ciblage par tenant se fait via le champ target_tenants.
    Pas de BaseRepository car pas d'isolation multi-tenant automatique.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, flag_id: int) -> Optional[FeatureFlag]:
        """Recupere un feature flag par ID.

        Args:
            flag_id: ID du flag

        Returns:
            FeatureFlag ou None
        """
        return self.db.get(FeatureFlag, flag_id)

    def get_by_name(self, name: str) -> Optional[FeatureFlag]:
        """Recupere un feature flag par nom unique.

        Args:
            name: Nom du flag (snake_case)

        Returns:
            FeatureFlag ou None
        """
        stmt = select(FeatureFlag).where(FeatureFlag.name == name)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[FeatureFlag], int]:
        """Liste tous les feature flags avec pagination.

        Args:
            skip: Offset pour pagination
            limit: Nombre max de resultats

        Returns:
            Tuple (liste de flags, total count)
        """
        total = self.db.execute(
            select(func.count()).select_from(FeatureFlag)
        ).scalar() or 0

        stmt = (
            select(FeatureFlag)
            .order_by(FeatureFlag.name)
            .offset(skip)
            .limit(min(limit, 1000))
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def create(self, flag: FeatureFlag) -> FeatureFlag:
        """Cree un nouveau feature flag.

        Args:
            flag: Instance FeatureFlag a creer

        Returns:
            FeatureFlag avec ID assigne
        """
        self.db.add(flag)
        self.db.flush()
        self.db.refresh(flag)
        return flag

    def update(self, flag: FeatureFlag) -> FeatureFlag:
        """Met a jour un feature flag existant.

        Args:
            flag: Instance FeatureFlag modifiee

        Returns:
            FeatureFlag mis a jour
        """
        self.db.flush()
        self.db.refresh(flag)
        return flag

    def delete(self, flag: FeatureFlag) -> None:
        """Supprime physiquement un feature flag (hard delete).

        Args:
            flag: Instance FeatureFlag a supprimer
        """
        self.db.delete(flag)
        self.db.flush()

    def name_exists(self, name: str, exclude_id: Optional[int] = None) -> bool:
        """Verifie si un nom de flag existe deja.

        Args:
            name: Nom a verifier
            exclude_id: ID a exclure (pour update)

        Returns:
            True si le nom existe
        """
        stmt = select(func.count()).select_from(FeatureFlag).where(
            FeatureFlag.name == name
        )
        if exclude_id is not None:
            stmt = stmt.where(FeatureFlag.id != exclude_id)
        count = self.db.execute(stmt).scalar() or 0
        return count > 0
