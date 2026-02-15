"""Service d'authentification pour login, refresh tokens, gestion users."""
from dataclasses import dataclass
from typing import Optional, Union
import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User
from app.core.security import (
    DUMMY_HASH,
    verify_password,
    get_password_hash,
    needs_rehash,
    decode_token,
    validate_password_strength,
)
from app.core.config import settings
from app.core.exceptions import (
    AccountLocked,
    TokenExpired,
    TokenInvalid,
    TokenRevoked,
    TokenReplayDetected,
)
from app.services.audit import AuditService
from app.services.bruteforce import brute_force_service, BruteForceStatus
from app.services.token import token_service
from app.services.session import session_service
from app.services.mfa import mfa_service
from app.constants import ErrorMessages, SecurityHeaders, SYSTEM_TENANT_ID, TokenType, UserRole


@dataclass
class MFARequiredResult:
    """Résultat intermédiaire quand MFA est requis après vérification du password.

    Retourné par login() à la place du tuple (access_token, refresh_token, expires_in)
    quand l'utilisateur a MFA activé. Le client doit ensuite appeler POST /mfa/verify.
    """
    mfa_session_token: str


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
    ) -> Union[tuple[str, str, int], MFARequiredResult]:
        """Authentifie un utilisateur et retourne les tokens JWT ou un MFARequiredResult.

        Args:
            email: Email de l'utilisateur
            password: Mot de passe en clair
            ip_address: IP du client (pour audit log + brute force)
            user_agent: User-Agent du client (pour audit log)
            request_id: UUID corrélation (auto-généré si absent)

        Returns:
            - Tuple (access_token, refresh_token, expires_in_seconds) si pas de MFA
            - MFARequiredResult si MFA activé (client doit appeler /mfa/verify)

        Raises:
            AccountLocked: Si compte verrouillé par brute force (403)
            HTTPException 401: Si credentials invalides
            HTTPException 403: Si compte inactif

        Security:
            - Brute force check AVANT toute vérification de credentials
            - Email normalisé en lowercase
            - Password vérifié avec bcrypt (DUMMY_HASH si user inexistant = fix M20)
            - Escalation: normal → captcha → delay → lock → lock+alert
            - Compteurs reset après login réussi
            - Si MFA activé: retourne mfa_session_token (pas de tokens JWT émis)
        """
        # Normaliser email
        email = email.lower().strip()
        effective_ip = ip_address or "unknown"

        # Générer request_id si absent
        if not request_id:
            request_id = str(uuid.uuid4())

        audit_service = AuditService(self.db)

        # ── Brute force check AVANT authentification ──
        bf_status = brute_force_service.check_and_enforce(email, effective_ip)
        if not bf_status.allowed:
            audit_service.log_login(
                user_id=None,
                tenant_id=SYSTEM_TENANT_ID,
                ip_address=effective_ip,
                user_agent=user_agent or "unknown",
                request_id=request_id,
                success=False,
                email=email,
            )
            self.db.commit()
            raise AccountLocked(minutes=bf_status.locked_until_seconds // 60)

        # ── Recherche user + vérification password ──
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            # Timing-safe: vérifier contre DUMMY_HASH (fix M20)
            verify_password(password, DUMMY_HASH)

            bf_status = brute_force_service.record_failed_attempt(email, effective_ip)

            audit_service.log_login(
                user_id=None,
                tenant_id=SYSTEM_TENANT_ID,
                ip_address=effective_ip,
                user_agent=user_agent or "unknown",
                request_id=request_id,
                success=False,
                email=email,
            )
            self.db.commit()

            if not bf_status.allowed:
                raise AccountLocked(minutes=bf_status.locked_until_seconds // 60)
            self._raise_invalid_credentials(bf_status)

        if not verify_password(password, user.hashed_password):
            bf_status = brute_force_service.record_failed_attempt(email, effective_ip)

            audit_service.log_login(
                user_id=None,
                tenant_id=user.tenant_id,
                ip_address=effective_ip,
                user_agent=user_agent or "unknown",
                request_id=request_id,
                success=False,
                email=email,
            )
            self.db.commit()

            if not bf_status.allowed:
                raise AccountLocked(minutes=bf_status.locked_until_seconds // 60)
            self._raise_invalid_credentials(bf_status)

        # ── Migration transparente bcrypt → Argon2id ──
        if needs_rehash(user.hashed_password):
            user.hashed_password = get_password_hash(password)
            self.db.flush()

        # Vérifier compte actif
        if not user.is_active:
            audit_service.log_login(
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=effective_ip,
                user_agent=user_agent or "unknown",
                request_id=request_id,
                success=False,
                email=email,
            )
            self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorMessages.ACCOUNT_INACTIVE,
            )

        # ── Succès password — reset brute force ──
        brute_force_service.record_successful_login(email, effective_ip)

        # ── Check MFA — si activé, retourner un mfa_session_token ──
        if mfa_service.is_mfa_enabled(self.db, user.id, user.tenant_id):
            mfa_token = mfa_service.create_mfa_session(
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                role=user.role,
                ip_address=effective_ip,
            )
            # Pas d'audit LOGIN_SUCCESS ici — il sera loggé après /mfa/verify
            self.db.commit()
            return MFARequiredResult(mfa_session_token=mfa_token)

        # ── Pas de MFA — émettre tokens directement ──
        audit_service.log_login(
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=effective_ip,
            user_agent=user_agent or "unknown",
            request_id=request_id,
            success=True,
            email=email,
        )
        self.db.commit()

        access_token, refresh_token, expires_in = token_service.issue_tokens(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            role=user.role,
        )

        # ── Créer session Redis ──
        refresh_payload = decode_token(refresh_token)
        family_id = refresh_payload.get("family_id", "")
        session_service.create_session(
            user_id=user.id,
            tenant_id=user.tenant_id,
            family_id=family_id,
            ip_address=effective_ip,
            user_agent=user_agent or "unknown",
        )

        return access_token, refresh_token, expires_in

    @staticmethod
    def _raise_invalid_credentials(bf_status: "BruteForceStatus") -> None:
        """Lève HTTPException 401 avec détails brute force si escalation active."""
        if bf_status.captcha_required or bf_status.delay_seconds > 0:
            detail = {
                "message": ErrorMessages.INVALID_CREDENTIALS,
                "captcha_required": bf_status.captcha_required,
                "delay_seconds": bf_status.delay_seconds,
                "attempts": bf_status.attempts,
            }
        else:
            detail = ErrorMessages.INVALID_CREDENTIALS

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
        )

    def refresh_access_token(self, refresh_token: str) -> tuple[str, str, int]:
        """Effectue une rotation de refresh token et émet un nouveau access token.

        Args:
            refresh_token: Refresh token JWT valide

        Returns:
            Tuple (new_access_token, new_refresh_token, expires_in_seconds)

        Raises:
            HTTPException 401: Si refresh token invalide, expiré, révoqué, ou replay détecté

        Security:
            - Valide signature + expiration du refresh token
            - Vérifie JTI dans whitelist Redis
            - Rotation: ancien refresh invalidé, nouveau émis (même famille)
            - Replay detection: si ancien JTI réutilisé → toute la famille révoquée
            - Charge user depuis DB (vérifie existence + is_active)
        """
        # Décoder refresh token — lève TokenExpired ou TokenInvalid
        try:
            payload = decode_token(refresh_token)
        except (TokenExpired, TokenInvalid):
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
                detail=ErrorMessages.INVALID_TOKEN_PAYLOAD,
            )

        # Charger user depuis DB
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.USER_NOT_FOUND,
            )

        # Vérifier compte actif
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorMessages.ACCOUNT_INACTIVE,
            )

        # Rotation via TokenService (whitelist check + replay detection + new tokens)
        try:
            new_access, new_refresh, expires_in = token_service.rotate_refresh_token(
                old_refresh_token=refresh_token,
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                role=user.role,
            )
        except TokenRevoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.REFRESH_TOKEN_REVOKED,
                headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
            )
        except TokenReplayDetected:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.REFRESH_TOKEN_REPLAY,
                headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
            )

        return new_access, new_refresh, expires_in

    def logout(
        self,
        access_token: str,
        user: "User",
        refresh_token: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> bool:
        """Effectue le logout : révoque tokens + CSRF + audit log.

        Args:
            access_token: Access token JWT actuel (sera blacklisté)
            user: Utilisateur authentifié (depuis get_current_user)
            refresh_token: Refresh token JWT (optionnel, sera supprimé de whitelist)
            ip_address: IP du client (pour audit log)
            user_agent: User-Agent du client (pour audit log)
            request_id: UUID corrélation (auto-généré si absent)

        Returns:
            True si logout réussi

        Security:
            - Access token blacklisté (JTI + TTL restant)
            - Refresh token supprimé de whitelist + famille désactivée
            - Tous les tokens CSRF du user révoqués
            - Audit log LOGOUT créé
        """
        from app.core.redis import redis_client

        if not request_id:
            request_id = str(uuid.uuid4())

        # 1. Révoquer tokens JWT via TokenService
        token_service.revoke_on_logout(
            access_token=access_token,
            refresh_token=refresh_token,
        )

        # 2. Supprimer la session associée (via family_id du refresh token)
        if refresh_token:
            try:
                refresh_payload = decode_token(refresh_token)
                family_id = refresh_payload.get("family_id")
                if family_id:
                    session_data = session_service.get_session_by_family(user.id, family_id)
                    if session_data:
                        session_service.revoke_session(session_data["session_id"], user.id)
            except (TokenExpired, TokenInvalid):
                pass  # Token peut être expiré, session sera nettoyée par TTL

        # 3. Révoquer tous les tokens CSRF du user
        redis_client.revoke_all_csrf_tokens(user.id)

        # 4. Audit log LOGOUT
        audit_service = AuditService(self.db)
        audit_service.log_logout(
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown",
            request_id=request_id,
        )
        self.db.commit()

        return True

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
        first_name: str,
        last_name: str,
        role: str,
        tenant_id: int
    ) -> User:
        """Crée un nouvel utilisateur (admin only).

        Args:
            email: Email unique
            password: Mot de passe en clair
            first_name: Prenom
            last_name: Nom de famille
            role: Rôle RBAC (admin, manager, staff)
            tenant_id: ID du tenant

        Returns:
            Utilisateur créé

        Raises:
            HTTPException 400: Si email existe déjà ou password faible
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
            first_name=first_name,
            last_name=last_name,
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
