"""Service metier pour la gestion des utilisateurs."""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException, status
from app.models.user import User
from app.schemas.user import UserProfileUpdate, UserCreate, UserUpdate
from app.core.security import validate_password_strength, get_password_hash
from app.core.exceptions import NotFound
from app.constants import ErrorMessages, UserRole
from app.repositories.user import UserRepository
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


class UserService:
    """Service metier pour gestion des utilisateurs.

    Responsibilities:
        - Mise à jour profil utilisateur (email, nom, password)
        - CRUD admin : create, list, get, update, deactivate
        - Validation unicité email par tenant
        - Validation password policy
        - Audit logging des actions admin

    Security:
        - Isolation multi-tenant stricte sur toutes les opérations
        - Email unique par tenant
        - Auto-promotion admin interdite
        - Auto-suppression interdite
    """

    def __init__(self, db: Session):
        """Initialise le service user.

        Args:
            db: Session SQLAlchemy active
        """
        self.db = db
        self.repo = UserRepository(db)
        self.audit = AuditService(db)

    def update_profile(
        self,
        user_id: int,
        tenant_id: int,
        data: UserProfileUpdate
    ) -> User:
        """Met à jour le profil d'un utilisateur (PATCH partiel).

        Args:
            user_id: ID de l'utilisateur à mettre à jour
            tenant_id: ID du tenant (isolation multi-tenant)
            data: Données de mise à jour (tous champs optionnels)

        Returns:
            Utilisateur mis à jour

        Raises:
            NotFound: Si utilisateur inexistant ou autre tenant
            HTTPException 400: Si email déjà utilisé par un autre user du tenant
            HTTPException 400: Si password ne respecte pas la policy

        Example:
            >>> user_service = UserService(db)
            >>> updated_user = user_service.update_profile(
            ...     user_id=42,
            ...     tenant_id=1,
            ...     data=UserProfileUpdate(
            ...         email="newemail@example.com",
            ...         first_name="Jean",
            ...         last_name="Dupont"
            ...     )
            ... )

        Security:
            - Email normalisé en lowercase
            - Email unique par tenant validé
            - Password policy validée si password fourni
            - Password hashé avec Argon2id
            - XSS/SQL injection déjà validés par schema validators
        """
        # Récupérer l'utilisateur
        user = self.db.query(User).filter(
            and_(
                User.id == user_id,
                User.tenant_id == tenant_id
            )
        ).first()

        if not user:
            raise NotFound(f"User {user_id} not found in tenant {tenant_id}")

        # Extraire les champs fournis (exclude_unset pour PATCH partiel)
        update_data = data.model_dump(exclude_unset=True)

        # Valider unicité email si changé
        if "email" in update_data:
            new_email = update_data["email"].lower().strip()

            # Vérifier qu'aucun autre utilisateur du tenant n'a déjà cet email
            existing_user = self.db.query(User).filter(
                and_(
                    User.tenant_id == tenant_id,
                    User.email == new_email,
                    User.id != user_id  # Exclure l'utilisateur lui-même
                )
            ).first()

            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.EMAIL_ALREADY_EXISTS,
                )

            # Normaliser l'email
            update_data["email"] = new_email

        # Valider et hasher password si fourni
        if "password" in update_data:
            password = update_data["password"]

            # Valider la robustesse du password
            is_valid, error_msg = validate_password_strength(password)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg or "Password does not meet security requirements"
                )

            # Hasher le password
            update_data["hashed_password"] = get_password_hash(password)

            # Retirer le password en clair de update_data
            del update_data["password"]

        # Mettre à jour les champs
        for key, value in update_data.items():
            setattr(user, key, value)

        # Commit et refresh
        self.db.commit()
        self.db.refresh(user)

        return user

    # ── Admin CRUD ─────────────────────────────────────────────────────

    def create_user(
        self,
        admin_user: User,
        data: UserCreate,
    ) -> User:
        """Crée un utilisateur dans le tenant de l'admin.

        Args:
            admin_user: Admin effectuant la création
            data: Données de création

        Returns:
            Utilisateur créé

        Raises:
            HTTPException 400: Email déjà utilisé ou password faible
        """
        from app.services.auth import AuthService

        auth_service = AuthService(self.db)
        user = auth_service.create_user(
            email=data.email,
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name,
            role=data.role.value if isinstance(data.role, UserRole) else data.role,
            tenant_id=admin_user.tenant_id,
        )

        self.audit.log_action(
            action="USER_CREATED",
            tenant_id=admin_user.tenant_id,
            user_id=admin_user.id,
            entity_type="User",
            entity_id=user.id,
            description=f"User {user.email} created with role {user.role}",
        )

        self.db.commit()
        self.db.refresh(user)
        return user

    def list_users(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 50,
        include_inactive: bool = False,
    ) -> tuple[list[User], int]:
        """Liste les utilisateurs d'un tenant avec pagination.

        Args:
            tenant_id: ID du tenant
            skip: Offset de pagination
            limit: Limite de pagination
            include_inactive: Inclure les comptes désactivés

        Returns:
            Tuple (items, total)
        """
        return self.repo.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            include_inactive=include_inactive,
            order_by="id",
        )

    def get_user(self, tenant_id: int, user_id: int) -> User:
        """Récupère un utilisateur par ID dans un tenant.

        Args:
            tenant_id: ID du tenant (isolation stricte)
            user_id: ID de l'utilisateur

        Returns:
            Utilisateur trouvé

        Raises:
            NotFound: Si utilisateur inexistant ou autre tenant
        """
        user = self.repo.get_by_id(user_id, tenant_id)
        if not user:
            raise NotFound(f"User {user_id} not found")
        return user

    def update_user(
        self,
        admin_user: User,
        user_id: int,
        data: UserUpdate,
    ) -> User:
        """Met à jour un utilisateur (admin/manager).

        Args:
            admin_user: Utilisateur effectuant la modification
            user_id: ID de l'utilisateur à modifier
            data: Données de modification (PATCH partiel)

        Returns:
            Utilisateur mis à jour

        Raises:
            NotFound: Si utilisateur inexistant ou autre tenant
            HTTPException 400: Email déjà utilisé
            HTTPException 403: Auto-promotion admin interdite
        """
        user = self.repo.get_by_id(user_id, admin_user.tenant_id)
        if not user:
            raise NotFound(f"User {user_id} not found")

        update_data = data.model_dump(exclude_unset=True)

        # Empêcher auto-promotion à admin
        if "role" in update_data and admin_user.id == user_id:
            if update_data["role"] == UserRole.ADMIN and user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot promote yourself to admin",
                )

        # Valider unicité email si changé
        if "email" in update_data:
            new_email = update_data["email"].lower().strip()
            existing = self.repo.get_by_email(
                admin_user.tenant_id, new_email
            )
            if existing and existing.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.EMAIL_ALREADY_EXISTS,
                )
            update_data["email"] = new_email

        # Convertir UserRole enum en string pour setattr
        if "role" in update_data and isinstance(update_data["role"], UserRole):
            update_data["role"] = update_data["role"].value

        for key, value in update_data.items():
            setattr(user, key, value)

        self.repo.update(user)

        self.audit.log_action(
            action="USER_UPDATED",
            tenant_id=admin_user.tenant_id,
            user_id=admin_user.id,
            entity_type="User",
            entity_id=user.id,
            description=f"User {user.email} updated: {list(update_data.keys())}",
        )

        self.db.commit()
        self.db.refresh(user)
        return user

    def deactivate_user(
        self,
        admin_user: User,
        user_id: int,
    ) -> User:
        """Désactive un utilisateur (soft delete).

        Args:
            admin_user: Admin effectuant la désactivation
            user_id: ID de l'utilisateur à désactiver

        Returns:
            Utilisateur désactivé

        Raises:
            NotFound: Si utilisateur inexistant ou autre tenant
            HTTPException 403: Impossible de se désactiver soi-même
        """
        if admin_user.id == user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot deactivate your own account",
            )

        user = self.repo.get_by_id(user_id, admin_user.tenant_id)
        if not user:
            raise NotFound(f"User {user_id} not found")

        success = self.repo.soft_delete(user_id, admin_user.tenant_id)
        if not success:
            raise NotFound(f"User {user_id} not found")

        self.audit.log_action(
            action="USER_DEACTIVATED",
            tenant_id=admin_user.tenant_id,
            user_id=admin_user.id,
            entity_type="User",
            entity_id=user.id,
            description=f"User {user.email} deactivated",
        )

        self.db.commit()
        self.db.refresh(user)
        return user
