"""Service metier pour la gestion des utilisateurs."""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException, status
from app.models.user import User
from app.schemas.user import UserProfileUpdate
from app.core.security import validate_password_strength, get_password_hash
from app.core.exceptions import NotFound
from app.constants import ErrorMessages


class UserService:
    """Service metier pour gestion des utilisateurs.

    Responsibilities:
        - Mise à jour profil utilisateur (email, nom, password)
        - Validation unicité email par tenant
        - Validation password policy

    Security:
        - Email doit être unique par tenant
        - Password doit respecter password policy
        - Validation XSS/SQL injection sur first_name/last_name (fait par schema)
    """

    def __init__(self, db: Session):
        """Initialise le service user.

        Args:
            db: Session SQLAlchemy active
        """
        self.db = db

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
