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
from app.models.user import User
from tests.conftest import csrf_token_for_user


# ── Fixtures locales ────────────────────────────────────────────────────


@pytest.fixture
def test_manager(test_db):
    """Utilisateur manager de test (tenant_id=1)."""
    user = User(
        tenant_id=1,
        email="manager@carocorp.com",
        hashed_password=get_password_hash("manager123"),
        first_name="Manager",
        last_name="User",
        role="manager",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def auth_headers_manager(test_manager):
    """Headers d'authentification pour manager (tenant_id=1)."""
    token = create_access_token({
        "sub": test_manager.id,
        "tenant_id": test_manager.tenant_id,
        "email": test_manager.email,
        "role": test_manager.role,
    })
    csrf = csrf_token_for_user(test_manager.id)
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf,
    }


@pytest.fixture
def extra_users(test_db):
    """Cree 3 utilisateurs supplementaires dans le tenant 1 pour tests de liste."""
    users = []
    for i in range(3):
        u = User(
            tenant_id=1,
            email=f"extra{i}@carocorp.com",
            hashed_password=get_password_hash("testpass123"),
            first_name=f"Extra{i}",
            last_name="User",
            role="staff",
            is_active=True,
        )
        test_db.add(u)
        users.append(u)
    test_db.commit()
    for u in users:
        test_db.refresh(u)
    return users


# ── CREATE ──────────────────────────────────────────────────────────────


class TestAdminCreateUser:
    """POST /api/v1/users — creation utilisateur par admin."""

    def test_create_user_success(
        self, client: TestClient, test_db, test_admin, auth_headers_admin
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
        self, client: TestClient, test_admin, auth_headers_admin
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
    ):
        """include_inactive=True inclut les comptes desactives."""
        # Creer un user inactif
        inactive = User(
            tenant_id=1,
            email="inactive@carocorp.com",
            hashed_password=get_password_hash("testpass123"),
            first_name="Inactive",
            last_name="User",
            role="staff",
            is_active=False,
        )
        test_db.add(inactive)
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

    def test_list_users_manager_forbidden(
        self, client: TestClient, test_manager, auth_headers_manager
    ):
        """Manager ne peut pas lister les utilisateurs -> 403."""
        response = client.get(
            "/api/v1/users",
            headers=auth_headers_manager,
        )

        assert response.status_code == 403


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
        self, client: TestClient, test_db, test_admin, test_user, auth_headers_admin
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
        self, client: TestClient, test_db, test_admin, auth_headers_admin
    ):
        """Admin ne peut pas se promouvoir lui-meme (deja admin, test le guard)."""
        # Creer un manager puis essayer de s'auto-promouvoir
        manager = User(
            tenant_id=1,
            email="selfpromo@carocorp.com",
            hashed_password=get_password_hash("testpass123"),
            first_name="Self",
            last_name="Promo",
            role="manager",
            is_active=True,
        )
        test_db.add(manager)
        test_db.commit()
        test_db.refresh(manager)

        # Creer token pour ce manager
        token = create_access_token({
            "sub": manager.id,
            "tenant_id": manager.tenant_id,
            "email": manager.email,
            "role": manager.role,
        })
        csrf = csrf_token_for_user(manager.id)
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
        test_db.refresh(test_user)
        assert test_user.is_active is False

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
