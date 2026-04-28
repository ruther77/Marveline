"""Service metier pour la gestion des utilisateurs — IAM v2 (Account + TenantMembership)."""
import logging
import secrets
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.models.account import Account
from app.models.tenant_membership import TenantMembership
from app.core.deps import UserCompat
from app.schemas.user import UserProfileUpdate, UserCreate, UserUpdate, UserInviteRequest
from app.core.security import validate_password_strength, get_password_hash
from app.core.exceptions import NotFound
from app.constants import ErrorMessages, UserRole
from app.services.rbac import can_manage_role
from app.repositories.account import AsyncAccountRepository
from app.repositories.tenant_membership import AsyncTenantMembershipRepository
from app.services.audit import AuditService

logger = logging.getLogger(__name__)

_CANNOT_DEACTIVATE_SELF = "Cannot deactivate your own account"
_CANNOT_PROMOTE_SELF = "Cannot promote yourself to admin"


class UserService:
    """Service metier pour gestion des utilisateurs (IAM v2).

    Responsibilities:
        - Mise à jour profil utilisateur (email, nom, password)
        - CRUD admin : create, list, get, update, deactivate
        - Validation unicité email globale (Account)
        - Validation password policy
        - Audit logging des actions admin

    Security:
        - Isolation multi-tenant via TenantMembership.tenant_id
        - Email unique globalement (Account)
        - Auto-promotion admin interdite
        - Auto-suppression interdite
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.account_repo = AsyncAccountRepository(db)
        self.membership_repo = AsyncTenantMembershipRepository(db)
        self.audit = AuditService(db)

    # ── Helpers internes ───────────────────────────────────────────────

    async def _get_usercompat(self, account_id: int, tenant_id: int) -> UserCompat:
        """Charge Account + TenantMembership et retourne un UserCompat."""
        account = await self.account_repo.get_by_id(account_id)
        if not account:
            raise NotFound(f"User {account_id} not found")
        membership = await self.membership_repo.get_active_or_suspended(account_id, tenant_id)
        if not membership:
            raise NotFound(f"User {account_id} not found in tenant {tenant_id}")
        return UserCompat(account=account, membership=membership)

    # ── Profil (utilisateur lui-même) ──────────────────────────────────

    async def update_profile(
        self,
        user_id: int,
        tenant_id: int,
        data: UserProfileUpdate,
    ) -> UserCompat:
        """Met à jour le profil d'un utilisateur (PATCH partiel)."""
        user = await self._get_usercompat(user_id, tenant_id)
        update_data = data.model_dump(exclude_unset=True)

        if "email" in update_data:
            new_email = update_data["email"].lower().strip()
            existing = await self.account_repo.get_by_email(new_email)
            if existing and existing.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.EMAIL_ALREADY_EXISTS,
                )
            user.email = new_email

        if "password" in update_data:
            is_valid, error_msg = validate_password_strength(update_data["password"])
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg or "Password does not meet security requirements",
                )
            user.hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            update_data.pop("email", None)

        for key, value in update_data.items():
            if key not in ("password",) and hasattr(user._account, key):
                setattr(user._account, key, value)

        await self.db.commit()
        await self.db.refresh(user._account)
        await self.db.refresh(user._membership)
        return user

    # ── Admin CRUD ─────────────────────────────────────────────────────

    async def list_users(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 50,
        include_inactive: bool = False,
    ) -> tuple[list[UserCompat], int]:
        """Liste les membres d'un tenant avec pagination (sans N+1).

        Sélectionne Account explicitement via JOIN pour éviter le lazy="noload"
        de la relation TenantMembership.account.
        """
        stmt = (
            select(TenantMembership, Account, func.count().over().label("_total"))
            .join(Account, TenantMembership.account_id == Account.id)
            .where(TenantMembership.tenant_id == tenant_id)
            .where(TenantMembership.revoked_at.is_(None))
        )
        if not include_inactive:
            stmt = stmt.where(
                TenantMembership.status == "active",
                Account.is_active.is_(True),
            )
        stmt = stmt.order_by(TenantMembership.id).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        rows = result.all()
        if not rows:
            return [], 0
        total = rows[0][2]
        items = [UserCompat(account=row[1], membership=row[0]) for row in rows]
        return items, total

    async def get_user(self, tenant_id: int, user_id: int) -> UserCompat:
        """Récupère un utilisateur par ID dans un tenant."""
        return await self._get_usercompat(user_id, tenant_id)

    async def create_user(
        self,
        admin_user: UserCompat,
        data: UserCreate,
    ) -> UserCompat:
        """Crée un utilisateur dans le tenant de l'admin (IAM v2)."""
        email = data.email.lower().strip()
        role = data.role.value if isinstance(data.role, UserRole) else data.role

        if not can_manage_role(admin_user.role, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot assign role '{role}': insufficient privileges",
            )

        is_valid, error_msg = validate_password_strength(data.password, role=role)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg or "Password does not meet security requirements",
            )

        account = await self.account_repo.get_by_email(email)
        if account:
            existing_m = await self.membership_repo.get_active_or_suspended(
                account.id, admin_user.tenant_id
            )
            if existing_m:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.EMAIL_ALREADY_EXISTS,
                )
        else:
            account = Account(
                email=email,
                hashed_password=get_password_hash(data.password),
                first_name=data.first_name,
                last_name=data.last_name,
                is_active=True,
            )
            self.db.add(account)
            await self.db.flush()

        membership = TenantMembership(
            account_id=account.id,
            tenant_id=admin_user.tenant_id,
            role_name=role,
            status="active",
        )
        self.db.add(membership)
        await self.db.flush()

        await self.audit.log_action(
            action="USER_CREATED",
            tenant_id=admin_user.tenant_id,
            user_id=admin_user.id,
            entity_type="User",
            entity_id=account.id,
            description=f"User {email} created with role {role}",
        )

        await self.db.commit()
        await self.db.refresh(account)
        await self.db.refresh(membership)
        return UserCompat(account=account, membership=membership)

    async def update_user(
        self,
        admin_user: UserCompat,
        user_id: int,
        data: UserUpdate,
    ) -> UserCompat:
        """Met à jour un utilisateur (admin/manager)."""
        user = await self._get_usercompat(user_id, admin_user.tenant_id)
        update_data = data.model_dump(exclude_unset=True)

        if "role" in update_data:
            new_role = update_data["role"]
            new_role_str = new_role.value if isinstance(new_role, UserRole) else new_role
            if admin_user.id == user_id and new_role_str != user._membership.role_name:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_CANNOT_PROMOTE_SELF,
                )
            if not can_manage_role(admin_user.role, new_role_str):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cannot assign role '{new_role_str}': insufficient privileges",
                )

        if "email" in update_data:
            new_email = update_data["email"].lower().strip()
            existing = await self.account_repo.get_by_email(new_email)
            if existing and existing.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.EMAIL_ALREADY_EXISTS,
                )
            user.email = new_email

        if "role" in update_data:
            role_val = update_data["role"]
            user.role = role_val.value if isinstance(role_val, UserRole) else role_val

        if "first_name" in update_data:
            user.first_name = update_data["first_name"]
        if "last_name" in update_data:
            user.last_name = update_data["last_name"]
        if "is_active" in update_data:
            user.is_active = update_data["is_active"]
            if not update_data["is_active"]:
                user.membership_status = "suspended"

        await self.audit.log_action(
            action="USER_UPDATED",
            tenant_id=admin_user.tenant_id,
            user_id=admin_user.id,
            entity_type="User",
            entity_id=user_id,
            description=f"User {user.email} updated: {list(update_data.keys())}",
        )

        await self.db.commit()
        await self.db.refresh(user._account)
        await self.db.refresh(user._membership)
        return user

    async def invite_user(
        self,
        admin_user: UserCompat,
        data: UserInviteRequest,
    ) -> tuple[UserCompat, bool]:
        """Invite un utilisateur par email (crée Account si nécessaire)."""
        from app.services.auth_v2 import AuthV2Service

        email = data.email.lower().strip()
        role = data.role.value if isinstance(data.role, UserRole) else data.role

        account = await self.account_repo.get_by_email(email)
        if account:
            existing_m = await self.membership_repo.get_active_or_suspended(
                account.id, admin_user.tenant_id
            )
            if existing_m:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=ErrorMessages.EMAIL_ALREADY_EXISTS,
                )
        else:
            tmp_password = secrets.token_urlsafe(12) + "Xb2@"
            account = Account(
                email=email,
                hashed_password=get_password_hash(tmp_password),
                first_name=data.first_name or "",
                last_name=data.last_name or "",
                is_active=True,
            )
            self.db.add(account)
            await self.db.flush()

        membership = TenantMembership(
            account_id=account.id,
            tenant_id=admin_user.tenant_id,
            role_name=role,
            status="active",
        )
        self.db.add(membership)
        await self.db.flush()

        # invite_sent = False si SMTP non disponible (ex: env de test sans mailpit).
        # Les tests ne doivent vérifier que la présence du champ, pas la valeur True.
        auth_service = AuthV2Service(self.db)
        invite_sent = bool(await auth_service.forgot_password(email))

        await self.audit.log_action(
            action="USER_INVITED",
            tenant_id=admin_user.tenant_id,
            user_id=admin_user.id,
            entity_type="User",
            entity_id=account.id,
            description=f"User {email} invited with role {role}",
        )

        await self.db.commit()
        await self.db.refresh(account)
        await self.db.refresh(membership)
        return UserCompat(account=account, membership=membership), invite_sent

    async def deactivate_user(
        self,
        admin_user: UserCompat,
        user_id: int,
    ) -> UserCompat:
        """Désactive un utilisateur (soft delete — suspend membership + désactive account)."""
        if admin_user.id == user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_CANNOT_DEACTIVATE_SELF,
            )

        user = await self._get_usercompat(user_id, admin_user.tenant_id)
        user.is_active = False
        user.membership_status = "suspended"

        await self.audit.log_action(
            action="USER_DEACTIVATED",
            tenant_id=admin_user.tenant_id,
            user_id=admin_user.id,
            entity_type="User",
            entity_id=user_id,
            description=f"User {user.email} deactivated",
        )

        await self.db.commit()
        await self.db.refresh(user._account)
        await self.db.refresh(user._membership)
        return user
