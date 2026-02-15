"""Modèle User - Utilisateurs du système avec authentification."""
from typing import Optional
from sqlalchemy import BigInteger, CheckConstraint, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin
from app.constants import UserRole


class User(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Utilisateur du système avec authentification JWT.

    Attributes:
        email: Email unique (utilisé pour login)
        hashed_password: Mot de passe haché (bcrypt)
        full_name: Nom complet de l'utilisateur
        role: Rôle RBAC (admin, manager, staff)
        tenant_id: Tenant auquel appartient l'utilisateur
        is_active: Compte actif (False = compte désactivé)

    Roles:
        - admin: Tous droits + gestion users
        - manager: CRUD réservations/factures/clients/produits
        - staff: Read-only (consultation uniquement)

    Security:
        - Email unique par tenant (UniqueConstraint tenant_id + email)
        - Password stocké haché (bcrypt/argon2id)
        - Isolation multi-tenant via tenant_id
    """

    __tablename__ = "users"

    # Clé primaire
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Authentification
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Email unique par tenant (login)"
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Mot de passe haché (bcrypt)"
    )

    # Informations utilisateur
    full_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Nom complet de l'utilisateur"
    )

    # RBAC
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.STAFF,
        comment="Rôle RBAC (admin, manager, staff)"
    )

    # Contraintes
    __table_args__ = (
        # Email unique PAR tenant (pas globalement) — fix M17
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        # Rôle valide
        CheckConstraint(
            "role IN ('admin', 'manager', 'staff')",
            name="check_user_role_valid"
        ),
    )

    @property
    def is_admin(self) -> bool:
        """Vérifie si l'utilisateur est admin."""
        return self.role == UserRole.ADMIN

    @property
    def is_manager(self) -> bool:
        """Vérifie si l'utilisateur est manager ou admin."""
        return self.role in (UserRole.ADMIN, UserRole.MANAGER)

    @property
    def can_write(self) -> bool:
        """Vérifie si l'utilisateur a les droits d'écriture."""
        return self.role in (UserRole.ADMIN, UserRole.MANAGER)

    @property
    def can_read(self) -> bool:
        """Vérifie si l'utilisateur a les droits de lecture (tous les rôles)."""
        return True  # Tous les utilisateurs peuvent lire

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"


@event.listens_for(User.email, "set", retval=True)
def _normalize_email(target, value, oldvalue, initiator):
    """Normalise l'email en lowercase + strip avant stockage (fix M22)."""
    if value is not None:
        return value.lower().strip()
    return value
