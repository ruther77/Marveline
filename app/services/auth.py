"""Service d'authentification pour login, refresh tokens, gestion users."""
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    validate_password_strength,
)
from app.core.config import settings


class AuthService:
    """Service d'authentification et gestion des utilisateurs.

    Responsibilities:
        - Login (email + password → JWT tokens)
        - Refresh tokens (refresh_token → new access_token)
        - Change password
        - Create user (admin only)

    Security:
        - Password hashing avec bcrypt
        - JWT tokens (access: 30min, refresh: 7 jours)
        - Validation robustesse passwords
    """

    def __init__(self, db: Session):
        """Initialise le service auth.

        Args:
            db: Session SQLAlchemy active
        """
        self.db = db

    def login(
        self,
        email: str,
        password: str
    ) -> tuple[str, str, int]:
        """Authentifie un utilisateur et retourne les tokens JWT.

        Args:
            email: Email de l'utilisateur
            password: Mot de passe en clair

        Returns:
            Tuple (access_token, refresh_token, expires_in_seconds)

        Raises:
            HTTPException 401: Si credentials invalides ou compte inactif

        Example:
            access_token, refresh_token, expires_in = auth_service.login(
                "user@example.com",
                "secretpass123"
            )

        Security:
            - Email normalisé en lowercase
            - Password vérifié avec bcrypt
            - Compte doit être actif (is_active=True)
        """
        # Normaliser email
        email = email.lower().strip()

        # Trouver user par email
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Vérifier password
        if not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Vérifier compte actif
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )

        # Créer JWT claims
        claims = {
            "sub": user.id,
            "tenant_id": user.tenant_id,
            "email": user.email,
            "role": user.role,
        }

        # Générer tokens
        access_token = create_access_token(claims)
        refresh_token = create_refresh_token({
            "sub": user.id,
            "tenant_id": user.tenant_id
        })

        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return access_token, refresh_token, expires_in

    def refresh_access_token(self, refresh_token: str) -> tuple[str, int]:
        """Génère un nouveau access token depuis un refresh token.

        Args:
            refresh_token: Refresh token JWT valide

        Returns:
            Tuple (new_access_token, expires_in_seconds)

        Raises:
            HTTPException 401: Si refresh token invalide ou expiré

        Example:
            new_access_token, expires_in = auth_service.refresh_access_token(
                refresh_token
            )

        Security:
            - Valide signature + expiration du refresh token
            - Charge user depuis DB (vérifie existence + is_active)
            - Génère nouveau access token avec claims à jour
        """
        # Décoder refresh token
        payload = decode_token(refresh_token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Vérifier type de token
        token_type = payload.get("type")
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type (expected refresh token)",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extraire user_id
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

        # Charger user depuis DB
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        # Vérifier compte actif
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )

        # Créer nouveau access token avec claims à jour
        claims = {
            "sub": user.id,
            "tenant_id": user.tenant_id,
            "email": user.email,
            "role": user.role,
        }

        access_token = create_access_token(claims)
        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return access_token, expires_in

    def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str
    ) -> bool:
        """Change le mot de passe d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            current_password: Mot de passe actuel (pour vérification)
            new_password: Nouveau mot de passe

        Returns:
            True si changement réussi

        Raises:
            HTTPException 401: Si current_password incorrect
            HTTPException 400: Si new_password trop faible

        Security:
            - Vérifie current_password avant changement
            - Valide robustesse du nouveau password
            - Hash avec bcrypt
            - Pas de commit automatique (géré par endpoint)

        Example:
            auth_service.change_password(
                user_id=1,
                current_password="oldpass",
                new_password="newpass123"
            )
            db.commit()
        """
        # Charger user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Vérifier current password
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect"
            )

        # Valider robustesse nouveau password
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

        # Hash et assigner nouveau password
        user.hashed_password = get_password_hash(new_password)
        self.db.flush()

        return True

    def create_user(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str,
        tenant_id: int
    ) -> User:
        """Crée un nouvel utilisateur (admin only).

        Args:
            email: Email unique
            password: Mot de passe en clair
            full_name: Nom complet
            role: Rôle RBAC (admin, manager, staff)
            tenant_id: ID du tenant

        Returns:
            Utilisateur créé

        Raises:
            HTTPException 400: Si email existe déjà ou password faible

        Security:
            - Email normalisé + validation unicité
            - Password validé pour robustesse
            - Hash avec bcrypt
            - Pas de commit automatique

        Example:
            user = auth_service.create_user(
                email="new@example.com",
                password="secure123",
                full_name="Jean Dupont",
                role="manager",
                tenant_id=1
            )
            db.commit()
        """
        # Normaliser email
        email = email.lower().strip()

        # Vérifier unicité email
        existing_user = self.db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Valider robustesse password
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

        # Valider rôle
        if role not in ("admin", "manager", "staff"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role. Must be: admin, manager, or staff"
            )

        # Créer user
        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            role=role,
            tenant_id=tenant_id,
            is_active=True
        )

        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)

        return user

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Récupère un utilisateur par email.

        Args:
            email: Email de l'utilisateur

        Returns:
            User ou None si non trouvé

        Note:
            - Email normalisé en lowercase
            - Inclut les comptes inactifs
        """
        email = email.lower().strip()
        return self.db.query(User).filter(User.email == email).first()
