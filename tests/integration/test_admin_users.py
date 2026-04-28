"""Tests d'integration Phase 3 : Admin users CRUD.

Couvre les endpoints admin pour gestion des utilisateurs :
- GET    /api/v1/users          (list, pagination, admin-only)
- GET    /api/v1/users/{id}     (get user, admin-only, tenant isolation)
- POST   /api/v1/users          (create, admin-only)
- PATCH  /api/v1/users/{id}     (update, admin-only)
- DELETE /api/v1/users/{id}     (soft delete, admin-only)

Security:
- RBAC: staff/manager -> 403, admin -> 200
- Multi-tenant isolation: user de tenant 2 invisible pour admin tenant 1
- Anti-self-promotion: admin ne peut pas se promouvoir lui-meme
- Anti-self-deletion: admin ne peut pas se desactiver lui-meme
"""
import secrets

import pytest
from fastapi.testclient import TestClient

from app.core.redis import redis_client
from app.core.security import create_access_token, get_password_hash
from app.core.deps import UserCompat
from app.models.account import Account
from app.models.tenant_membership import TenantMembership
from tests.conftest import csrf_token_for_user


# ── Fixtures locales ────────────────────────────────────────────────────


@pytest.fixture
def test_manager(test_db, test_tenant_record, _role_manager):
    """Utilisateur manager de test (tenant_id=1) — IAM v2."""
    account = Account(
        email="manager@carocorp.com",
        hashed_password=get_password_hash("manager123"),
        first_name="Manager",
        last_name="User",
        is_active=True,
    )
    test_db.add(account)
    test_db.flush()
    membership = TenantMembership(
        account_id=account.id,
        tenant_id=test_tenant_record.id,
        role_name="manager",
        status="active",
    )
    test_db.add(membership)
    test_db.commit()
    test_db.refresh(account)
    test_db.refresh(membership)
    return UserCompat(account=account, membership=membership)


@pytest.fixture
def auth_headers_manager(test_manager):
    """Headers d'authentification pour manager (tenant_id=1) — IAM v2 (claim 'tid')."""
    import uuid as _uuid
    sid = str(_uuid.uuid4())
    token = create_access_token({
        "sub": test_manager.id,
        "tid": str(test_manager.tenant_id),
        "email": test_manager.email,
        "role": test_manager.role,
        "sid": sid,
    })
    csrf = csrf_token_for_user(test_manager.id, session_id=sid)
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf,
    }


@pytest.fixture
def extra_users(test_db, test_tenant_record, _role_staff):
    """Cree 3 utilisateurs supplementaires dans le tenant 1 — IAM v2."""
    result = []
    for i in range(3):
        account = Account(
            email=f"extra{i}@carocorp.com",
            hashed_password=get_password_hash("testpass123"),
            first_name=f"Extra{i}",
            last_name="User",
            is_active=True,
        )
        test_db.add(account)
        test_db.flush()
        membership = TenantMembership(
            account_id=account.id,
            tenant_id=test_tenant_record.id,
            role_name="staff",
            status="active",
        )
        test_db.add(membership)
        test_db.flush()
        result.append(UserCompat(account=account, membership=membership))
    test_db.commit()
    for uc in result:
        test_db.refresh(uc._account)
        test_db.refresh(uc._membership)
    return result


# ── CREATE ──────────────────────────────────────────────────────────────


class TestAdminCreateUser:
    """POST /api/v1/users — creation utilisateur par admin."""

    def test_create_user_success(
        self, client: TestClient, test_db, test_admin, auth_headers_admin, _role_staff
    ):
        """Admin cree un staff -> 201 avec donnees correctes."""
        response = client.post(
            "/api/v1/users",
            json={
                "email": "newuser@carocorp.com",
                "password": "SecurePass123!",
                "first_name": "New",
                "last_name": "User",
                "role": "staff",
            },
            headers=auth_headers_admin,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@carocorp.com"
        assert data["first_name"] == "New"
        assert data["last_name"] == "User"
        assert data["role"] == "staff"
        assert data["tenant_id"] == test_admin.tenant_id
        assert data["is_active"] is True
        assert "id" in data

    def test_create_user_manager_role(
        self, client: TestClient, test_admin, auth_headers_admin, _role_manager
    ):
        """Admin cree un manager -> 201."""
        response = client.post(
            "/api/v1/users",
            json={
                "email": "newmanager@carocorp.com",
                "password": "SecurePass123!",
                "first_name": "New",
                "last_name": "Manager",
                "role": "manager",
            },
            headers=auth_headers_admin,
        )

        assert response.status_code == 201
        assert response.json()["role"] == "manager"

    def test_create_user_duplicate_email(
        self, client: TestClient, test_admin, test_user, auth_headers_admin
    ):
        """Email deja utilise dans le meme tenant -> 400."""
        response = client.post(
            "/api/v1/users",
            json={
                "email": "test@carocorp.com",  # test_user.email
                "password": "SecurePass123!",
                "first_name": "Dup",
                "last_name": "User",
            },
            headers=auth_headers_admin,
        )

        assert response.status_code == 400

    def test_create_user_same_email_different_tenant(
        self,
        client: TestClient,
        test_admin,
        test_user_tenant2,
        auth_headers_admin,
    ):
        """Email utilise dans un autre tenant -> 201 (email unique par tenant)."""
        response = client.post(
            "/api/v1/users",
            json={
                "email": "test@tenant2.com",  # existe dans tenant 2 seulement
                "password": "SecurePass123!",
                "first_name": "Same",
                "last_name": "Email",
            },
            headers=auth_headers_admin,
        )

        assert response.status_code == 201
        assert response.json()["tenant_id"] == test_admin.tenant_id

    def test_create_user_weak_password(
        self, client: TestClient, test_admin, auth_headers_admin
    ):
        """Mot de passe faible -> 400 ou 422."""
        response = client.post(
            "/api/v1/users",
            json={
                "email": "weakpwd@carocorp.com",
                "password": "weak",
                "first_name": "Weak",
                "last_name": "Password",
            },
            headers=auth_headers_admin,
        )

        assert response.status_code in (400, 422)

    def test_create_user_staff_forbidden(
        self, client: TestClient, test_user, auth_headers_real
    ):
        """Staff ne peut pas creer d'utilisateur -> 403."""
        response = client.post(
            "/api/v1/users",
            json={
                "email": "nope@carocorp.com",
                "password": "SecurePass123!",
                "first_name": "Nope",
                "last_name": "Staff",
            },
            headers=auth_headers_real,
        )

        assert response.status_code == 403

    def test_create_user_manager_forbidden(
        self, client: TestClient, test_manager, auth_headers_manager
    ):
        """Manager ne peut pas creer d'utilisateur -> 403."""
        response = client.post(
            "/api/v1/users",
            json={
                "email": "nope@carocorp.com",
                "password": "SecurePass123!",
                "first_name": "Nope",
                "last_name": "Manager",
            },
            headers=auth_headers_manager,
        )

        assert response.status_code == 403

    def test_create_user_no_auth(self, client: TestClient):
        """Sans authentification -> 401."""
        response = client.post(
            "/api/v1/users",
            json={
                "email": "noauth@carocorp.com",
                "password": "SecurePass123!",
                "first_name": "No",
                "last_name": "Auth",
            },
        )

        assert response.status_code == 401


# ── LIST ────────────────────────────────────────────────────────────────


class TestAdminListUsers:
    """GET /api/v1/users — liste paginee des utilisateurs."""

    def test_list_users_success(
        self,
        client: TestClient,
        test_admin,
        test_user,
        extra_users,
        auth_headers_admin,
    ):
        """Admin liste les utilisateurs -> 200 avec pagination."""
        response = client.get(
            "/api/v1/users",
            headers=auth_headers_admin,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        # test_admin + test_user + 3 extra = 5
        assert data["total"] >= 5
        assert len(data["items"]) >= 5

    def test_list_users_pagination(
        self,
        client: TestClient,
        test_admin,
        test_user,
        extra_users,
        auth_headers_admin,
    ):
        """Pagination skip/limit fonctionnelle."""
        response = client.get(
            "/api/v1/users?skip=0&limit=2",
            headers=auth_headers_admin,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["skip"] == 0
        assert data["limit"] == 2
        assert data["total"] >= 5  # Total non affecte par limit

    def test_list_users_tenant_isolation(
        self,
        client: TestClient,
        test_admin,
        test_user,
        test_user_tenant2,
        auth_headers_admin,
    ):
        """Admin tenant 1 ne voit PAS les users du tenant 2."""
        response = client.get(
            "/api/v1/users",
            headers=auth_headers_admin,
        )

        assert response.status_code == 200
        data = response.json()
        tenant_ids = {item["tenant_id"] for item in data["items"]}
        assert tenant_ids == {1}  # Que des users du tenant 1
        emails = {item["email"] for item in data["items"]}
        assert "test@tenant2.com" not in emails

    def test_list_users_include_inactive(
        self,
        client: TestClient,
        test_db,
        test_admin,
        auth_headers_admin,
        _role_staff,
    ):
        """include_inactive=True inclut les comptes desactives."""
        # Creer un user inactif — IAM v2
        tenant_id = 1  # tenant par defaut des tests
        inactive_account = Account(
            email="inactive@carocorp.com",
            hashed_password=get_password_hash("testpass123"),
            first_name="Inactive",
            last_name="User",
            is_active=False,
        )
        test_db.add(inactive_account)
        test_db.flush()
        inactive_membership = TenantMembership(
            account_id=inactive_account.id,
            tenant_id=tenant_id,
            role_name="staff",
            status="suspended",
        )
        test_db.add(inactive_membership)
        test_db.commit()

        # Sans include_inactive
        resp_default = client.get(
            "/api/v1/users",
            headers=auth_headers_admin,
        )
        emails_default = {item["email"] for item in resp_default.json()["items"]}

        # Avec include_inactive=true
        resp_incl = client.get(
            "/api/v1/users?include_inactive=true",
            headers=auth_headers_admin,
        )
        emails_incl = {item["email"] for item in resp_incl.json()["items"]}

        assert "inactive@carocorp.com" not in emails_default
        assert "inactive@carocorp.com" in emails_incl

    def test_list_users_staff_forbidden(
        self, client: TestClient, test_user, auth_headers_real
    ):
        """Staff ne peut pas lister les utilisateurs -> 403."""
        response = client.get(
            "/api/v1/users",
            headers=auth_headers_real,
        )

        assert response.status_code == 403

    def test_list_users_manager_allowed(
        self, client: TestClient, test_manager, auth_headers_manager
    ):
        """Manager peut lister les utilisateurs (users:read dans RBAC) -> 200."""
        response = client.get(
            "/api/v1/users",
            headers=auth_headers_manager,
        )

        assert response.status_code == 200


# ── GET ─────────────────────────────────────────────────────────────────


class TestAdminGetUser:
    """GET /api/v1/users/{user_id} — recup utilisateur par ID."""

    def test_get_user_success(
        self, client: TestClient, test_admin, test_user, auth_headers_admin
    ):
        """Admin recup un user de son tenant -> 200."""
        response = client.get(
            f"/api/v1/users/{test_user.id}",
            headers=auth_headers_admin,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_user.id
        assert data["email"] == test_user.email
        assert data["tenant_id"] == 1

    def test_get_user_cross_tenant_not_found(
        self,
        client: TestClient,
        test_admin,
        test_user_tenant2,
        auth_headers_admin,
    ):
        """Admin tenant 1 ne peut pas voir un user du tenant 2 -> 404."""
        response = client.get(
            f"/api/v1/users/{test_user_tenant2.id}",
            headers=auth_headers_admin,
        )

        assert response.status_code == 404

    def test_get_user_nonexistent(
        self, client: TestClient, test_admin, auth_headers_admin
    ):
        """User inexistant -> 404."""
        response = client.get(
            "/api/v1/users/99999",
            headers=auth_headers_admin,
        )

        assert response.status_code == 404

    def test_get_user_staff_forbidden(
        self, client: TestClient, test_user, auth_headers_real
    ):
        """Staff ne peut pas recup un user par ID -> 403."""
        response = client.get(
            f"/api/v1/users/{test_user.id}",
            headers=auth_headers_real,
        )

        assert response.status_code == 403


# ── UPDATE ──────────────────────────────────────────────────────────────


class TestAdminUpdateUser:
    """PATCH /api/v1/users/{user_id} — mise a jour utilisateur."""

    def test_update_user_first_name(
        self, client: TestClient, test_db, test_admin, test_user, auth_headers_admin
    ):
        """Admin modifie le prenom d'un user -> 200."""
        response = client.patch(
            f"/api/v1/users/{test_user.id}",
            json={"first_name": "Updated"},
            headers=auth_headers_admin,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["last_name"] == test_user.last_name  # Inchange

    def test_update_user_role(
        self, client: TestClient, test_db, test_admin, test_user, auth_headers_admin, _role_manager
    ):
        """Admin change le role d'un user staff -> manager -> 200."""
        response = client.patch(
            f"/api/v1/users/{test_user.id}",
            json={"role": "manager"},
            headers=auth_headers_admin,
        )

        assert response.status_code == 200
        assert response.json()["role"] == "manager"

    def test_update_user_email(
        self, client: TestClient, test_db, test_admin, test_user, auth_headers_admin
    ):
        """Admin change l'email d'un user -> 200."""
        response = client.patch(
            f"/api/v1/users/{test_user.id}",
            json={"email": "updated@carocorp.com"},
            headers=auth_headers_admin,
        )

        assert response.status_code == 200
        assert response.json()["email"] == "updated@carocorp.com"

    def test_update_user_email_duplicate(
        self,
        client: TestClient,
        test_db,
        test_admin,
        test_user,
        extra_users,
        auth_headers_admin,
    ):
        """Changer vers un email deja pris dans le meme tenant -> 400."""
        response = client.patch(
            f"/api/v1/users/{test_user.id}",
            json={"email": "extra0@carocorp.com"},  # extra_users[0].email
            headers=auth_headers_admin,
        )

        assert response.status_code == 400

    def test_update_self_promotion_forbidden(
        self, client: TestClient, test_db, test_admin, auth_headers_admin, _role_manager
    ):
        """Admin ne peut pas se promouvoir lui-meme (deja admin, test le guard)."""
        # Creer un manager puis essayer de s'auto-promouvoir — IAM v2
        mgr_account = Account(
            email="selfpromo@carocorp.com",
            hashed_password=get_password_hash("testpass123"),
            first_name="Self",
            last_name="Promo",
            is_active=True,
        )
        test_db.add(mgr_account)
        test_db.flush()
        mgr_membership = TenantMembership(
            account_id=mgr_account.id,
            tenant_id=1,
            role_name="manager",
            status="active",
        )
        test_db.add(mgr_membership)
        test_db.commit()
        test_db.refresh(mgr_account)
        test_db.refresh(mgr_membership)
        manager = UserCompat(account=mgr_account, membership=mgr_membership)

        # Creer token pour ce manager — IAM v2 (claim 'tid')
        import uuid as _uuid2
        sid2 = str(_uuid2.uuid4())
        token = create_access_token({
            "sub": manager.id,
            "tid": str(manager.tenant_id),
            "email": manager.email,
            "role": manager.role,
            "sid": sid2,
        })
        csrf = csrf_token_for_user(manager.id, session_id=sid2)
        manager_headers = {
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": csrf,
        }

        # Le manager ne peut pas acceder a PATCH /users/{id} (pas USERS_WRITE)
        response = client.patch(
            f"/api/v1/users/{manager.id}",
            json={"role": "admin"},
            headers=manager_headers,
        )

        assert response.status_code == 403

    def test_update_user_cross_tenant_not_found(
        self,
        client: TestClient,
        test_admin,
        test_user_tenant2,
        auth_headers_admin,
    ):
        """Admin tenant 1 ne peut pas modifier un user du tenant 2 -> 404."""
        response = client.patch(
            f"/api/v1/users/{test_user_tenant2.id}",
            json={"first_name": "Hacked"},
            headers=auth_headers_admin,
        )

        assert response.status_code == 404

    def test_update_user_nonexistent(
        self, client: TestClient, test_admin, auth_headers_admin
    ):
        """User inexistant -> 404."""
        response = client.patch(
            "/api/v1/users/99999",
            json={"first_name": "Ghost"},
            headers=auth_headers_admin,
        )

        assert response.status_code == 404

    def test_update_user_staff_forbidden(
        self, client: TestClient, test_user, auth_headers_real
    ):
        """Staff ne peut pas modifier un utilisateur -> 403."""
        response = client.patch(
            f"/api/v1/users/{test_user.id}",
            json={"first_name": "Hacked"},
            headers=auth_headers_real,
        )

        assert response.status_code == 403


# ── DELETE (soft delete) ────────────────────────────────────────────────


class TestAdminDeleteUser:
    """DELETE /api/v1/users/{user_id} — desactivation (soft delete)."""

    def test_delete_user_success(
        self,
        client: TestClient,
        test_db,
        test_admin,
        test_user,
        auth_headers_admin,
    ):
        """Admin desactive un user -> 200 + is_active=False."""
        response = client.delete(
            f"/api/v1/users/{test_user.id}",
            headers=auth_headers_admin,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

        # Verifier en DB
        test_db.refresh(test_user._account)
        assert test_user._account.is_active is False

    def test_delete_self_forbidden(
        self, client: TestClient, test_admin, auth_headers_admin
    ):
        """Admin ne peut pas se desactiver lui-meme -> 403."""
        response = client.delete(
            f"/api/v1/users/{test_admin.id}",
            headers=auth_headers_admin,
        )

        assert response.status_code == 403

    def test_delete_user_cross_tenant_not_found(
        self,
        client: TestClient,
        test_admin,
        test_user_tenant2,
        auth_headers_admin,
    ):
        """Admin tenant 1 ne peut pas desactiver un user du tenant 2 -> 404."""
        response = client.delete(
            f"/api/v1/users/{test_user_tenant2.id}",
            headers=auth_headers_admin,
        )

        assert response.status_code == 404

    def test_delete_user_nonexistent(
        self, client: TestClient, test_admin, auth_headers_admin
    ):
        """User inexistant -> 404."""
        response = client.delete(
            "/api/v1/users/99999",
            headers=auth_headers_admin,
        )

        assert response.status_code == 404

    def test_delete_user_staff_forbidden(
        self, client: TestClient, test_user, auth_headers_real
    ):
        """Staff ne peut pas desactiver un utilisateur -> 403."""
        response = client.delete(
            f"/api/v1/users/{test_user.id}",
            headers=auth_headers_real,
        )

        assert response.status_code == 403

    def test_delete_user_manager_forbidden(
        self, client: TestClient, test_user, test_manager, auth_headers_manager
    ):
        """Manager ne peut pas desactiver un utilisateur -> 403."""
        response = client.delete(
            f"/api/v1/users/{test_user.id}",
            headers=auth_headers_manager,
        )

        assert response.status_code == 403


# ── Me endpoints (non-regression) ──────────────────────────────────────


class TestMeEndpoints:
    """GET/PATCH /api/v1/users/me — verification non-regression."""

    def test_get_my_profile(
        self, client: TestClient, test_user, auth_headers_real
    ):
        """Tout utilisateur peut voir son propre profil."""
        response = client.get(
            "/api/v1/users/me",
            headers=auth_headers_real,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["id"] == test_user.id

    def test_update_my_profile(
        self, client: TestClient, test_db, test_user, auth_headers_real
    ):
        """Tout utilisateur peut modifier son propre profil."""
        response = client.patch(
            "/api/v1/users/me",
            json={"first_name": "UpdatedMe"},
            headers=auth_headers_real,
        )

        assert response.status_code == 200
        assert response.json()["first_name"] == "UpdatedMe"


# ── POST /users/invite ────────────────────────────────────────────────


class TestInviteUser:
    """Tests pour POST /api/v1/users/invite."""

    def test_invite_ok(self, client: TestClient, auth_headers_admin: dict, _role_staff):
        """Admin invite un nouvel utilisateur → 201 + invite_sent True."""
        import uuid
        email = f"invite-{uuid.uuid4().hex[:8]}@example.com"
        resp = client.post(
            "/api/v1/users/invite",
            json={"email": email, "role": "staff", "first_name": "Invite", "last_name": "Test"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["email"] == email
        assert data["role"] == "staff"
        assert "invite_sent" in data  # True si SMTP dispo, False sinon — on vérifie la présence
        assert "id" in data

    def test_invite_duplicate_email_409(
        self, client: TestClient, auth_headers_admin: dict, test_db, _role_staff
    ):
        """Inviter un email déjà existant dans le tenant → 409 (IAM v2)."""
        import uuid

        email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
        # Créer Account + TenantMembership dans tenant 1
        dup_account = Account(
            email=email,
            hashed_password=get_password_hash("Test1234!@#$"),
            first_name="Dup", last_name="User",
            is_active=True,
        )
        test_db.add(dup_account)
        test_db.flush()
        dup_membership = TenantMembership(
            account_id=dup_account.id,
            tenant_id=1,
            role_name="staff",
            status="active",
        )
        test_db.add(dup_membership)
        test_db.commit()

        resp = client.post(
            "/api/v1/users/invite",
            json={"email": email, "role": "manager"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 409

    def test_invite_non_admin_403(self, client: TestClient, auth_headers_real: dict):
        """Un utilisateur non-admin ne peut pas inviter → 403."""
        import uuid
        resp = client.post(
            "/api/v1/users/invite",
            json={"email": f"noadmin-{uuid.uuid4().hex[:8]}@example.com", "role": "staff"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 403

    def test_invite_cross_tenant_isolation(
        self, client: TestClient, auth_headers_admin_tenant2: dict, test_db, _role_staff
    ):
        """Un email de tenant1 peut être invité dans tenant2 (Account partagé, IAM v2)."""
        import uuid

        email = f"cross-{uuid.uuid4().hex[:8]}@example.com"
        # Créer Account + TenantMembership dans tenant 1
        cross_account = Account(
            email=email,
            hashed_password=get_password_hash("Test1234!@#$"),
            first_name="Cross", last_name="T1",
            is_active=True,
        )
        test_db.add(cross_account)
        test_db.flush()
        cross_membership = TenantMembership(
            account_id=cross_account.id,
            tenant_id=1,
            role_name="staff",
            status="active",
        )
        test_db.add(cross_membership)
        test_db.commit()

        # Le même email peut être invité dans tenant2 (même Account, nouveau membership)
        resp2 = client.post(
            "/api/v1/users/invite",
            json={"email": email, "role": "staff"},
            headers=auth_headers_admin_tenant2,
        )
        assert resp2.status_code == 201, resp2.text
        assert resp2.json()["email"] == email
        # En IAM v2, l'Account est partagé entre tenants ; l'isolation est garantie par le membership
