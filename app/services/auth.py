"""Service d'authentification pour login, refresh tokens, gestion users."""
from typing import Optional
import uuid
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
from app.services.audit import AuditService
from app.constants import ErrorMessages, SecurityHeaders, TokenType, UserRole


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
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> tuple[str, str, int]:
        """Authentifie un utilisateur et retourne les tokens JWT.

        Args:
            email: Email de l'utilisateur
            password: Mot de passe en clair
            ip_address: IP du client (pour audit log)
            user_agent: User-Agent du client (pour audit log)
            request_id: UUID corrélation (auto-généré si absent)

        Returns:
            Tuple (access_token, refresh_token, expires_in_seconds)

        Raises:
            HTTPException 401: Si credentials invalides ou compte inactif

        Example:
            access_token, refresh_token, expires_in = auth_service.login(
                "user@example.com",
                "secretpass123",
                ip_address="192.168.1.100",
                user_agent="Mozilla/5.0...",
                request_id="550e8400-..."
            )

        Security:
            - Email normalisé en lowercase
            - Password vérifié avec bcrypt
            - Compte doit être actif (is_active=True)
            - Audit log pour login success/failed (conformité RGPD/SOC2)
        """
        # Normaliser email
        email = email.lower().strip()

        # Générer request_id si absent
        if not request_id:
            request_id = str(uuid.uuid4())

        # Initialiser AuditService
        audit_service = AuditService(self.db)

        # Trouver user par email (case-insensitive)
        user = self.db.query(User).filter(User.email.ilike(email)).first()
        if not user:
            # Audit log LOGIN_FAILED (user_id=None car user non trouvé)
            # Utiliser tenant_id=1 par défaut pour login failed (pas de tenant associé)
            audit_service.log_login(
                user_id=None,
                tenant_id=1,  # Tenant par défaut pour login failed
                ip_address=ip_address or "unknown",
                user_agent=user_agent or "unknown",
                request_id=request_id,
                success=False,
                email=email
            )
            self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.INVALID_CREDENTIALS,
                headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
            )

        # Vérifier password
        if not verify_password(password, user.hashed_password):
            # Audit log LOGIN_FAILED (user trouvé mais password incorrect)
            audit_service.log_login(
                user_id=None,
                tenant_id=user.tenant_id,
                ip_address=ip_address or "unknown",
                user_agent=user_agent or "unknown",
                request_id=request_id,
                success=False,
                email=email
            )
            self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.INVALID_CREDENTIALS,
                headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
            )

        # Vérifier compte actif
        if not user.is_active:
            # Audit log LOGIN_FAILED (compte inactif)
            audit_service.log_login(
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=ip_address or "unknown",
                user_agent=user_agent or "unknown",
                request_id=request_id,
                success=False,
                email=email
            )
            self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorMessages.ACCOUNT_INACTIVE
            )

        # Audit log LOGIN_SUCCESS
        audit_service.log_login(
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown",
            request_id=request_id,
            success=True,
            email=email
        )
        self.db.commit()

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
                detail=ErrorMessages.INVALID_REFRESH_TOKEN,
                headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
            )

        # Vérifier type de token
        token_type = payload.get("type")
        if token_type != TokenType.REFRESH:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.INVALID_REFRESH_TOKEN_TYPE,
                headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
            )

        # Extraire user_id
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.INVALID_TOKEN_PAYLOAD
            )

        # Charger user depuis DB
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.USER_NOT_FOUND
            )

        # Vérifier compte actif
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorMessages.ACCOUNT_INACTIVE
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
                detail=ErrorMessages.USER_NOT_FOUND
            )

        # Vérifier current password
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.CURRENT_PASSWORD_INCORRECT
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
                detail=ErrorMessages.EMAIL_ALREADY_EXISTS
            )

        # Valider robustesse password
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

        # Valider rôle
        if role not in (UserRole.ADMIN, UserRole.MANAGER, UserRole.STAFF):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.INVALID_ROLE
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
