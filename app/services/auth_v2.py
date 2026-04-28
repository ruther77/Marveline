"""Service AuthV2 — flux login/refresh IAM v2 (accounts + memberships).

Remplace AuthService (v1 user-centric) pour les nouveaux endpoints.
Principe : AccountService.verify_credentials → MembershipService.require_active
           → AccountSessionService.open → TokenService.issue_tokens(membership_id=...)

Directives :
    - Aucun import User / UserSession / session_service (legacy)
    - tenant_id requis au login (multi-tenant, pas d'auto-résolution)
    - mfa_service.is_mfa_enabled() accepte user_id=account.id (en attendant mfa_v2)
"""
import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from typing import Optional, Union

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import TokenExpired, TokenInvalid
from app.core.redis import redis_sec
from app.core.security import (
    decode_token,
    get_password_hash,
    validate_password_strength,
    verify_password,
)
from app.constants import ErrorMessages, Limits, RedisKeys, SecurityHeaders, TokenType
from app.models.account import Account
from app.repositories.account_session import AsyncAccountSessionRepository
from app.repositories.password_reset_token import AsyncPasswordResetTokenRepository
from app.repositories.tenant_membership import AsyncTenantMembershipRepository
from app.services.account import AccountService
from app.services.account_session import AccountSessionService
from app.services.audit import AuditService
from app.services.bruteforce import brute_force_service, BruteForceStatus
from app.services.hibp import is_password_compromised
from app.services.membership import MembershipService
from app.services.mfa import mfa_service
from app.services.notification import notification_service
from app.services.session import generate_device_id
from app.services.token import token_service

logger = logging.getLogger(__name__)


@dataclass
class MFARequiredResult:
    """Résultat intermédiaire : MFA requis après vérification password."""

    mfa_session_token: str


class AuthV2Service:
    """Service d'authentification IAM v2 (accounts + memberships).

    Responsabilités :
        - Login email+password → tokens JWT v3 (avec claim mid=membership_id)
        - Refresh token rotation (TokenService atomique Lua)
        - Délégation MFA au service existant (migration mfa_v2 ultérieure)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._account_svc = AccountService(db)
        self._membership_svc = MembershipService(db)
        self._session_svc = AccountSessionService(db)

    async def login(
        self,
        email: str,
        password: str,
        tenant_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        captcha_token: Optional[str] = None,
    ) -> Union[tuple[str, str, int, bool], MFARequiredResult]:
        """Authentifie un account dans un tenant et retourne les tokens JWT v3."""
        email = email.lower().strip()
        effective_ip = ip_address or "unknown"
        device_id = generate_device_id(user_agent or "unknown", effective_ip)
        request_id = request_id or str(uuid.uuid4())

        bf_status = await self._check_global_and_brute_force(
            email, effective_ip, device_id, captcha_token
        )

        account = await self._authenticate_account(
            email, password, tenant_id, effective_ip, device_id, user_agent, request_id, bf_status
        )

        membership = await self._membership_svc.require_active(account.id, tenant_id)

        await self._maybe_flag_hibp(account, password)

        mfa_enabled = await mfa_service.is_mfa_enabled(self.db, account.id, membership.tenant_id)

        # M-05 : adaptive MFA — forcer step-up si device ou IP inconnus
        adaptive_trigger = False
        if not mfa_enabled:
            adaptive_trigger = await self._check_adaptive_mfa(account.id, effective_ip, device_id)
            if adaptive_trigger:
                logger.info(
                    "Adaptive MFA triggered: account=%d ip=%s device=%s",
                    account.id, effective_ip, device_id,
                )

        # Ne pas forcer adaptive MFA si aucun device MFA n'est configuré
        # (mfa_enabled=False implique pas de device) — sinon le login est bloqué
        if adaptive_trigger and not mfa_enabled:
            adaptive_trigger = False
            logger.info("Adaptive MFA skipped: no MFA device for account=%d", account.id)

        if mfa_enabled or adaptive_trigger:
            mfa_token = await mfa_service.create_mfa_session(
                user_id=account.id,
                tenant_id=membership.tenant_id,
                email=account.email,
                role=membership.role_name,
                ip_address=effective_ip,
            )
            await self.db.commit()
            return MFARequiredResult(mfa_session_token=mfa_token)

        return await self._open_session_and_issue(
            account, membership, device_id, effective_ip, user_agent, request_id
        )

    async def switch_membership(
        self,
        refresh_token: str,
        target_tenant_id: int,
    ) -> tuple[str, int]:
        """Émet un access token pour un autre tenant sans rotation du refresh cookie.

        Lit le refresh cookie → extrait account_id/device_id/session_id
        → valide membership actif dans target_tenant_id
        → émet access token avec tid=target_tenant_id.
        Le refresh cookie (tid=tenant d'origine) reste inchangé.

        Raises:
            401: token invalide/expiré/compte inactif.
            403: pas de membership actif dans le tenant cible.
        """
        payload = self._decode_refresh_or_raise(refresh_token)

        account_id = self._extract_int_claim(payload, "sub", ErrorMessages.INVALID_TOKEN_PAYLOAD)
        device_id: str = payload.get("did") or ""
        session_id: str = payload.get("sid") or ""

        account = await self._account_svc.get_active_by_id(account_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.USER_NOT_FOUND,
                headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
            )

        membership = await self._membership_svc.require_active(account_id, target_tenant_id)

        return await token_service.issue_access_only(
            user_id=account_id,
            tenant_id=membership.tenant_id,
            role=membership.role_name,
            device_id=device_id,
            session_id=session_id,
            membership_id=membership.id,
        )

    async def refresh(self, refresh_token: str) -> tuple[str, str, int]:
        """Rotation atomique du refresh token (Lua §2.6) — IAM v2."""
        payload = self._decode_refresh_or_raise(refresh_token)

        account_id = self._extract_int_claim(payload, "sub", ErrorMessages.INVALID_TOKEN_PAYLOAD)
        tenant_id = self._extract_int_claim(payload, "tid", ErrorMessages.INVALID_TOKEN_PAYLOAD)
        mid_raw = payload.get("mid")
        membership_id = int(mid_raw) if mid_raw else None

        account = await self._account_svc.get_active_by_id(account_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.USER_NOT_FOUND,
                headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
            )

        membership = await self._resolve_membership(account_id, tenant_id, membership_id)

        return await token_service.rotate_refresh_token(
            old_refresh_token=refresh_token,
            user_id=account.id,
            tenant_id=membership.tenant_id,
            role=membership.role_name,
            membership_id=membership.id,
        )

    async def logout(
        self,
        access_token: str,
        account_id: int,
        membership_id: int,
        tenant_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> bool:
        """Révoque tokens JWT + session DB + CSRF. Audit log logout IAM v2."""
        request_id = request_id or str(uuid.uuid4())

        try:
            access_payload = decode_token(access_token)
            device_id: str = access_payload.get("did", "")
            session_id: str = access_payload.get("sid", "")
        except (TokenExpired, TokenInvalid):
            device_id = ""
            session_id = ""

        await token_service.revoke_on_logout(
            access_token=access_token,
            user_id=account_id,
            device_id=device_id,
            session_id=session_id,
        )

        if session_id:
            try:
                await self._session_svc.revoke(session_id, membership_id, reason="logout")
            except HTTPException as e:
                if e.status_code == 404:
                    logger.debug("Session deja revoquee (idempotent) sid=%s", session_id)
                else:
                    logger.warning("Revocation session echouee: %s %s sid=%s", e.status_code, e.detail, session_id)

            await redis_sec.revoke_csrf_token(session_id)

        audit_service = AuditService(self.db)
        await audit_service.log_logout(
            user_id=account_id,
            tenant_id=tenant_id,
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown",
            request_id=request_id,
        )
        await self.db.commit()
        return True

    async def change_password(
        self,
        account_id: int,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change le mot de passe d'un account IAM v2.

        Séquence spec §4.5 S-09.3 : brute check → vérif ancien → nouveau ≠ ancien
        → force + HIBP bloquant → hash + persist → reset compteur.
        """
        brute_key = RedisKeys.brute_force_pwd_change(account_id)
        attempts = await redis_sec.get_brute_force_count(brute_key)
        if attempts >= Limits.PASSWORD_CHANGE_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=ErrorMessages.PASSWORD_CHANGE_RATE_LIMITED,
            )

        account = await self._account_svc.get_active_by_id(account_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.USER_NOT_FOUND,
            )

        if not verify_password(current_password, account.hashed_password):
            await redis_sec.increment_brute_force(brute_key, Limits.PASSWORD_CHANGE_WINDOW_SECONDS)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.CURRENT_PASSWORD_INCORRECT,
            )

        if verify_password(new_password, account.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.PASSWORD_SAME_AS_CURRENT,
            )

        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

        if is_password_compromised(new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.PASSWORD_COMPROMISED,
            )

        account.hashed_password = get_password_hash(new_password)
        account.password_change_required = False
        await self.db.flush()
        await redis_sec.reset_brute_force(brute_key)

        # P1-17 : revoquer toutes les sessions (les anciens tokens ne doivent plus etre valides)
        sessions_key = f"user_sessions_index:{account_id}"
        session_ids = await redis_sec.client.smembers(sessions_key)
        revoked = 0
        for sid_raw in session_ids:
            sid = sid_raw.decode() if isinstance(sid_raw, bytes) else sid_raw
            try:
                await redis_sec.revoke_single_session_by_id(account_id, sid)
                revoked += 1
            except Exception:
                pass
        if revoked:
            logger.info(
                "Password changed: %d sessions revoked for account=%d",
                revoked, account_id,
            )
        return True

    async def forgot_password(
        self,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> bool:
        """Demande de réinitialisation — anti-énumération, rate-limiting par email."""
        from app.core.redis import redis_client

        email = email.lower().strip()
        request_id = request_id or str(uuid.uuid4())

        rate_count = await redis_client.increment_password_reset_rate(email)
        if rate_count > Limits.PASSWORD_RESET_MAX_PER_EMAIL:
            return True  # silencieux — anti-énumération

        account = await self.db.scalar(
            select(Account).filter(Account.email == email, Account.is_active == True)  # noqa: E712
        )
        if not account:
            return True  # anti-énumération

        memberships = await AsyncTenantMembershipRepository(self.db).list_by_account(account.id)
        audit_tenant_id = memberships[0].tenant_id if memberships else 0

        raw_bytes = secrets.token_bytes(32)
        raw_token = raw_bytes.hex()
        token_hash = hashlib.sha256(raw_bytes).hexdigest()

        await AsyncPasswordResetTokenRepository(self.db).create(
            token_hash=token_hash,
            account_id=account.id,
            email=email,
        )

        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
        notification_service.send_password_reset_email(email, reset_url)

        audit_service = AuditService(self.db)
        await audit_service.log_action(
            action="PASSWORD_RESET_REQUESTED",
            tenant_id=audit_tenant_id,
            user_id=account.id,
            entity_type="Account",
            entity_id=account.id,
            description="Password reset email sent",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        await self.db.commit()
        return True

    async def reset_password(
        self,
        token: str,
        new_password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> bool:
        """Réinitialise le mot de passe — consume atomique + révocation sessions (spec §4.4)."""
        request_id = request_id or str(uuid.uuid4())

        try:
            raw_bytes = bytes.fromhex(token)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.PASSWORD_RESET_TOKEN_INVALID,
            )
        token_hash = hashlib.sha256(raw_bytes).hexdigest()

        reset_token = await AsyncPasswordResetTokenRepository(self.db).consume(token_hash)
        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.PASSWORD_RESET_TOKEN_INVALID,
            )

        account_id = reset_token.account_id
        memberships = await AsyncTenantMembershipRepository(self.db).list_by_account(account_id)
        audit_tenant_id = memberships[0].tenant_id if memberships else 0

        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

        if is_password_compromised(new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.PASSWORD_COMPROMISED,
            )

        account = await self._account_svc.get_active_by_id(account_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.PASSWORD_RESET_TOKEN_INVALID,
            )

        account.hashed_password = get_password_hash(new_password)
        account.password_change_required = False

        await AsyncAccountSessionRepository(self.db).revoke_all_by_account(
            account_id, reason="password_reset"
        )
        await redis_sec.revoke_all_csrf_tokens(account_id)
        await self.db.flush()

        audit_service = AuditService(self.db)
        await audit_service.log_action(
            action="PASSWORD_RESET_COMPLETED",
            tenant_id=audit_tenant_id,
            user_id=account_id,
            entity_type="Account",
            entity_id=account_id,
            description="Password reset completed via email token",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        await self.db.commit()
        return True

    # ── Helpers privés ──────────────────────────────────────────────────────

    async def _check_global_and_brute_force(
        self,
        email: str,
        effective_ip: str,
        device_id: str,
        captcha_token: Optional[str],
    ) -> BruteForceStatus:
        """Vérifie lockout global + brute force + CAPTCHA (§7.2). Retourne bf_status."""
        if await redis_sec.is_login_blocked():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=ErrorMessages.LOGIN_GLOBALLY_BLOCKED,
            )

        bf_status = await brute_force_service.check_and_enforce(email, effective_ip, device_id)

        captcha_needed = bf_status.captcha_required or await redis_sec.is_captcha_required()
        if captcha_needed and not await brute_force_service.validate_captcha_token(captcha_token):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.CAPTCHA_REQUIRED,
            )

        return bf_status

    async def _authenticate_account(
        self,
        email: str,
        password: str,
        tenant_id: int,
        effective_ip: str,
        device_id: str,
        user_agent: Optional[str],
        request_id: str,
        bf_status: BruteForceStatus,
    ):
        """Vérifie credentials — lève 401 si invalide, 403 si inactif."""
        audit_service = AuditService(self.db)

        account = await self._account_svc.verify_credentials(email, password)

        if not account:
            await brute_force_service.record_failed_attempt(email, effective_ip, device_id)
            await brute_force_service.record_global_failure()
            await audit_service.log_login(
                user_id=None,
                tenant_id=tenant_id,
                ip_address=effective_ip,
                user_agent=user_agent or "unknown",
                request_id=request_id,
                success=False,
                email=email,
            )
            await self.db.commit()
            self._raise_invalid_credentials(bf_status)

        await brute_force_service.record_successful_login(email, effective_ip, device_id)

        if not account.is_active:
            await audit_service.log_login(
                user_id=account.id,
                tenant_id=tenant_id,
                ip_address=effective_ip,
                user_agent=user_agent or "unknown",
                request_id=request_id,
                success=False,
                email=email,
            )
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorMessages.ACCOUNT_INACTIVE,
            )

        return account

    async def _maybe_flag_hibp(self, account, password: str) -> None:
        """Marque password_change_required si HIBP détecte une compromission (non-bloquant)."""
        if not settings.DEBUG and is_password_compromised(password):
            account.password_change_required = True
            await self.db.flush()

    async def _open_session_and_issue(
        self,
        account,
        membership,
        device_id: str,
        effective_ip: str,
        user_agent: Optional[str],
        request_id: str,
    ) -> tuple[str, str, int, bool]:
        """Ouvre session IAM v2, audit log, émet tokens JWT v3."""
        audit_service = AuditService(self.db)

        session = await self._session_svc.open(
            account_id=account.id,
            membership_id=membership.id,
            tenant_id=membership.tenant_id,
            device_id=device_id,
            ip_address=effective_ip,
            user_agent=user_agent,
        )
        await self.db.flush()

        await audit_service.log_login(
            user_id=account.id,
            tenant_id=membership.tenant_id,
            ip_address=effective_ip,
            user_agent=user_agent or "unknown",
            request_id=request_id,
            success=True,
            email=account.email,
        )
        await self.db.commit()

        # ISO-APP-01 : charger app_code du tenant pour dériver l'audience JWT
        from app.models.tenant import Tenant
        tenant_app_code = await self.db.scalar(
            select(Tenant.app_code).where(Tenant.id == membership.tenant_id)
        )

        access_token, refresh_token, expires_in = await token_service.issue_tokens(
            user_id=account.id,
            tenant_id=membership.tenant_id,
            role=membership.role_name,
            device_id=device_id,
            session_id=session.session_id,
            membership_id=membership.id,
            app_code=tenant_app_code,
        )

        return access_token, refresh_token, expires_in, account.password_change_required

    async def _resolve_membership(self, account_id: int, tenant_id: int, membership_id: Optional[int]):
        """Résout le membership — par ID si fourni, sinon par (account, tenant)."""
        if membership_id is None:
            return await self._membership_svc.require_active(account_id, tenant_id)

        membership = await self._membership_svc.get_by_id(membership_id)
        if (
            not membership
            or membership.account_id != account_id
            or membership.revoked_at is not None
            or membership.status != "active"
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.ACCESS_DENIED,
                headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
            )
        return membership

    def _decode_refresh_or_raise(self, refresh_token: str) -> dict:
        """Décode le refresh token ou lève 401."""
        try:
            payload = decode_token(refresh_token)
        except (TokenExpired, TokenInvalid):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.INVALID_REFRESH_TOKEN,
                headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
            )

        if payload.get("type") != TokenType.REFRESH:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.INVALID_REFRESH_TOKEN_TYPE,
                headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
            )

        return payload

    @staticmethod
    def _extract_int_claim(payload: dict, key: str, error_msg: str) -> int:
        """Extrait un claim entier du payload JWT ou lève 401."""
        raw = payload.get(key)
        if raw is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_msg,
            )
        try:
            return int(raw)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_msg,
            )

    @staticmethod
    def _raise_invalid_credentials(bf_status: BruteForceStatus) -> None:
        """Lève 400 avec captcha_required ou 401 standard."""
        if bf_status.captcha_required:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": ErrorMessages.INVALID_CREDENTIALS,
                    "captcha_required": True,
                    "delay_seconds": bf_status.delay_seconds,
                },
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.INVALID_CREDENTIALS,
            headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
        )

    async def _check_adaptive_mfa(self, account_id: int, ip: str, device_id: str) -> bool:
        """M-05 : detecte si MFA step-up est necessaire (nouveau device ou IP inhabituelle).

        Verifie les sessions recentes (30 jours) :
        - Si le device_id n'a jamais ete vu → trigger MFA
        - Si le subnet IP /24 est inconnu → trigger MFA

        Returns:
            True si MFA doit etre force.
        """
        import ipaddress as ipmod

        try:
            # Recuperer les sessions recentes de ce compte
            from app.repositories.account_session import AsyncAccountSessionRepository
            session_repo = AsyncAccountSessionRepository(self.db)
            recent_sessions = await session_repo.list_recent(account_id, days=30)

            if not recent_sessions:
                # Premier login ever → trigger MFA si disponible
                return True

            # Check device connu
            known_devices = {s.device_id for s in recent_sessions}
            if device_id not in known_devices:
                logger.info("Adaptive MFA: unknown device %s for account %d", device_id, account_id)
                return True

            # Check subnet IP connu
            try:
                current_subnet = str(ipmod.IPv4Network(f"{ip}/24", strict=False))
            except ValueError:
                current_subnet = ip
            known_subnets = set()
            for s in recent_sessions:
                try:
                    known_subnets.add(str(ipmod.IPv4Network(f"{s.ip_address}/24", strict=False)))
                except ValueError:
                    known_subnets.add(s.ip_address)

            if current_subnet not in known_subnets:
                logger.info("Adaptive MFA: unknown subnet %s for account %d", current_subnet, account_id)
                return True

            return False
        except Exception as e:
            logger.warning("Adaptive MFA check failed (FAIL-OPEN): %s", e)
            return False
