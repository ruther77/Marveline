"""Tests unitaires pour UserService."""
import pytest
import uuid
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from app.models.account import Account
from app.models.auth_role import AuthRole
from app.models.tenant_membership import TenantMembership
from app.models.tenant import Tenant
from app.core.deps import UserCompat
from app.services.user import UserService
from app.schemas.user import UserProfileUpdate
from app.core.security import get_password_hash, verify_password
from app.core.exceptions import NotFound
from app.constants import ErrorMessages


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

_DEFAULT_ROLE_LEVELS = {"super_admin": 1, "tenant_admin": 2, "manager": 3, "staff": 4, "viewer": 5}


async def _ensure_role(db, name: str) -> None:
    """Garantit que le AuthRole existe en DB (FK tenant_memberships.role_name)."""
    existing = await db.execute(select(AuthRole).where(AuthRole.name == name))
    if existing.scalar_one_or_none() is None:
        db.add(AuthRole(
            name=name,
            level=_DEFAULT_ROLE_LEVELS.get(name, 4),
            is_system=False,
            mfa_required=False,
            description=f"{name} role (test fixture)",
        ))
        await db.flush()


async def _make_user(db, email="user@test.com", first_name="John",
                     last_name="Doe", role="manager"):
    """Cree un utilisateur de test (IAM v2 — Account + TenantMembership)."""
    await _ensure_role(db, role)
    tenant = Tenant(
        external_id=str(uuid.uuid4()),
        name=f"Tenant-{email}",
        domain=f"{email.replace('@', '-').replace('.', '-')}.test",
        contact_email=email,
        app_code="marveline",
        status="active",
        is_active=True,
    )
    db.add(tenant)
    await db.flush()
    account = Account(
        email=email,
        first_name=first_name,
        last_name=last_name,
        hashed_password=get_password_hash("password123"),
        is_active=True,
    )
    db.add(account)
    await db.flush()
    membership = TenantMembership(
        account_id=account.id,
        tenant_id=tenant.id,
        role_name=role,
        status="active",
    )
    db.add(membership)
    await db.flush()
    await db.refresh(account)
    await db.refresh(membership)
    return UserCompat(account=account, membership=membership)


# ─────────────────────────────────────────────────────────────────────
# Update Profile
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestUpdateProfile:
    """Tests pour UserService.update_profile."""

    async def test_update_email_success(self, async_db):
        """Test: mise à jour email vers nouveau email unique."""
        user = await _make_user(async_db, email="old@test.com")
        service = UserService(async_db)

        data = UserProfileUpdate(email="new@test.com")
        updated = await service.update_profile(user.id, user.tenant_id, data)

        assert updated.email == "new@test.com"
        assert updated.first_name == "John"  # Inchangé
        assert updated.last_name == "Doe"  # Inchangé

    async def test_update_email_duplicate_same_tenant(self, async_db):
        """Test: mise à jour email vers email déjà utilisé dans même tenant → 400."""
        user1 = await _make_user(async_db, email="user1@test.com")
        await _make_user(async_db, email="user2@test.com")
        service = UserService(async_db)

        data = UserProfileUpdate(email="user2@test.com")
        with pytest.raises(HTTPException) as exc_info:
            await service.update_profile(user1.id, user1.tenant_id, data)

        assert exc_info.value.status_code == 400
        assert ErrorMessages.EMAIL_ALREADY_EXISTS in exc_info.value.detail

    async def test_update_email_duplicate_different_tenant_ok(self, async_db):
        """Test: même Account avec 2 TenantMemberships peut updater son email (IAM v2, option c).

        En IAM v2, Account.email est globalement unique. La contrainte d'unicité s'applique
        à tous les tenants. Cependant, un même Account peut avoir des memberships dans
        plusieurs tenants — il peut donc updater son email depuis n'importe quel contexte.
        """
        await _ensure_role(async_db, "manager")
        tenant1 = Tenant(
            external_id=str(uuid.uuid4()), name="T1-shared", domain="t1-shared.test",
            contact_email="t1@shared.test", app_code="marveline", status="active", is_active=True,
        )
        tenant2 = Tenant(
            external_id=str(uuid.uuid4()), name="T2-shared", domain="t2-shared.test",
            contact_email="t2@shared.test", app_code="epicerie", status="active", is_active=True,
        )
        async_db.add(tenant1)
        async_db.add(tenant2)
        await async_db.flush()

        account = Account(
            email="shared@test.com", first_name="Shared", last_name="User",
            hashed_password=get_password_hash("password123"), is_active=True,
        )
        async_db.add(account)
        await async_db.flush()

        m1 = TenantMembership(
            account_id=account.id, tenant_id=tenant1.id, role_name="manager", status="active"
        )
        m2 = TenantMembership(
            account_id=account.id, tenant_id=tenant2.id, role_name="manager", status="active"
        )
        async_db.add(m1)
        async_db.add(m2)
        await async_db.flush()

        service = UserService(async_db)

        # Le même Account peut updater son email depuis le contexte tenant1
        data = UserProfileUpdate(email="newemail@test.com")
        updated = await service.update_profile(account.id, tenant1.id, data)

        assert updated.email == "newemail@test.com"
        assert updated.tenant_id == tenant1.id

    async def test_update_email_normalization(self, async_db):
        """Test: email normalisé en lowercase."""
        user = await _make_user(async_db, email="user@test.com")
        service = UserService(async_db)

        data = UserProfileUpdate(email="NewEmail@TEST.COM")
        updated = await service.update_profile(user.id, user.tenant_id, data)

        assert updated.email == "newemail@test.com"

    async def test_update_first_name_last_name(self, async_db):
        """Test: mise à jour prénom et nom."""
        user = await _make_user(async_db, first_name="John", last_name="Doe")
        service = UserService(async_db)

        data = UserProfileUpdate(first_name="Jane", last_name="Smith")
        updated = await service.update_profile(user.id, user.tenant_id, data)

        assert updated.first_name == "Jane"
        assert updated.last_name == "Smith"
        assert updated.full_name == "Jane Smith"
        assert updated.email == "user@test.com"  # Inchangé

    async def test_update_password_success(self, async_db):
        """Test: mise à jour password avec policy valide."""
        user = await _make_user(async_db)
        service = UserService(async_db)

        new_password = "NewSecureP@ssw0rd123"
        data = UserProfileUpdate(password=new_password)
        updated = await service.update_profile(user.id, user.tenant_id, data)

        assert verify_password(new_password, updated.hashed_password)

    async def test_update_password_too_short(self, async_db):
        """Test: password trop court → ValidationError (Pydantic schema)."""
        await _make_user(async_db)

        # Pydantic valide min_length dans le schema avant que le service soit appelé
        with pytest.raises(ValidationError) as exc_info:
            UserProfileUpdate(password="short")

        # Vérifier que l'erreur concerne bien la longueur du password
        errors = exc_info.value.errors()
        assert any(err["loc"] == ("password",) for err in errors)

    async def test_update_password_no_uppercase(self, async_db):
        """Test: password sans majuscule → 400 (password policy)."""
        user = await _make_user(async_db)
        service = UserService(async_db)

        data = UserProfileUpdate(password="nouppercase123!")
        with pytest.raises(HTTPException) as exc_info:
            await service.update_profile(user.id, user.tenant_id, data)

        assert exc_info.value.status_code == 400

    async def test_update_password_no_number(self, async_db):
        """Test: password sans chiffre → 400 (password policy)."""
        user = await _make_user(async_db)
        service = UserService(async_db)

        data = UserProfileUpdate(password="NoNumberHere!")
        with pytest.raises(HTTPException) as exc_info:
            await service.update_profile(user.id, user.tenant_id, data)

        assert exc_info.value.status_code == 400

    async def test_update_partial_patch(self, async_db):
        """Test: PATCH partiel (uniquement certains champs fournis)."""
        user = await _make_user(async_db, first_name="John", last_name="Doe",
                                email="john@test.com")
        service = UserService(async_db)

        # Mise à jour seulement du first_name
        data = UserProfileUpdate(first_name="Jane")
        updated = await service.update_profile(user.id, user.tenant_id, data)

        assert updated.first_name == "Jane"
        assert updated.last_name == "Doe"  # Inchangé
        assert updated.email == "john@test.com"  # Inchangé

    async def test_update_user_not_found(self, async_db):
        """Test: utilisateur inexistant → NotFound."""
        service = UserService(async_db)

        data = UserProfileUpdate(first_name="Jane")
        with pytest.raises(NotFound) as exc_info:
            await service.update_profile(user_id=9999, tenant_id=1, data=data)

        assert "User 9999 not found" in str(exc_info.value)

    async def test_update_user_wrong_tenant(self, async_db):
        """Test: utilisateur d'un autre tenant → NotFound (isolation multi-tenant)."""
        user = await _make_user(async_db, email="user@test.com")
        service = UserService(async_db)

        data = UserProfileUpdate(first_name="Jane")
        with pytest.raises(NotFound):
            # Tentative d'accès avec wrong tenant_id (inexistant)
            await service.update_profile(user.id, tenant_id=9999, data=data)

    async def test_update_multiple_fields(self, async_db):
        """Test: mise à jour de plusieurs champs simultanément."""
        user = await _make_user(async_db, first_name="John", last_name="Doe",
                                email="john@test.com")
        service = UserService(async_db)

        data = UserProfileUpdate(
            email="jane.smith@test.com",
            first_name="Jane",
            last_name="Smith"
        )
        updated = await service.update_profile(user.id, user.tenant_id, data)

        assert updated.email == "jane.smith@test.com"
        assert updated.first_name == "Jane"
        assert updated.last_name == "Smith"
        assert updated.full_name == "Jane Smith"

    async def test_update_email_same_as_current(self, async_db):
        """Test: mise à jour email vers email actuel → OK (pas de conflit)."""
        user = await _make_user(async_db, email="user@test.com")
        service = UserService(async_db)

        # Changer l'email vers la même valeur (normalisée)
        data = UserProfileUpdate(email="USER@test.com")
        updated = await service.update_profile(user.id, user.tenant_id, data)

        assert updated.email == "user@test.com"
