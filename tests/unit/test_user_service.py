"""Tests unitaires pour UserService."""
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.models.user import User, UserRole
from app.services.user import UserService
from app.schemas.user import UserProfileUpdate
from app.core.security import get_password_hash, verify_password
from app.core.exceptions import NotFound
from app.constants import ErrorMessages


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _make_user(db, tenant_id=1, email="user@test.com", first_name="John", last_name="Doe", role=UserRole.MANAGER):
    """Cree un utilisateur de test."""
    user = User(
        tenant_id=tenant_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        hashed_password=get_password_hash("password123"),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ─────────────────────────────────────────────────────────────────────
# Update Profile
# ─────────────────────────────────────────────────────────────────────

class TestUpdateProfile:
    """Tests pour UserService.update_profile."""

    def test_update_email_success(self, test_db):
        """Test: mise à jour email vers nouveau email unique."""
        user = _make_user(test_db, email="old@test.com")
        service = UserService(test_db)

        data = UserProfileUpdate(email="new@test.com")
        updated = service.update_profile(user.id, user.tenant_id, data)

        assert updated.email == "new@test.com"
        assert updated.first_name == "John"  # Inchangé
        assert updated.last_name == "Doe"  # Inchangé

    def test_update_email_duplicate_same_tenant(self, test_db):
        """Test: mise à jour email vers email déjà utilisé dans même tenant → 400."""
        user1 = _make_user(test_db, email="user1@test.com")
        user2 = _make_user(test_db, email="user2@test.com")
        service = UserService(test_db)

        data = UserProfileUpdate(email="user2@test.com")
        with pytest.raises(HTTPException) as exc_info:
            service.update_profile(user1.id, user1.tenant_id, data)

        assert exc_info.value.status_code == 400
        assert ErrorMessages.EMAIL_ALREADY_EXISTS in exc_info.value.detail

    def test_update_email_duplicate_different_tenant_ok(self, test_db):
        """Test: email dupliqué dans autre tenant → OK (isolation multi-tenant)."""
        user1 = _make_user(test_db, tenant_id=1, email="user@test.com")
        user2 = _make_user(test_db, tenant_id=2, email="other@test.com")
        service = UserService(test_db)

        # Tenant 2 peut utiliser un email déjà pris dans tenant 1
        data = UserProfileUpdate(email="user@test.com")
        updated = service.update_profile(user2.id, user2.tenant_id, data)

        assert updated.email == "user@test.com"
        assert updated.tenant_id == 2

    def test_update_email_normalization(self, test_db):
        """Test: email normalisé en lowercase."""
        user = _make_user(test_db, email="user@test.com")
        service = UserService(test_db)

        data = UserProfileUpdate(email="NewEmail@TEST.COM")
        updated = service.update_profile(user.id, user.tenant_id, data)

        assert updated.email == "newemail@test.com"

    def test_update_first_name_last_name(self, test_db):
        """Test: mise à jour prénom et nom."""
        user = _make_user(test_db, first_name="John", last_name="Doe")
        service = UserService(test_db)

        data = UserProfileUpdate(first_name="Jane", last_name="Smith")
        updated = service.update_profile(user.id, user.tenant_id, data)

        assert updated.first_name == "Jane"
        assert updated.last_name == "Smith"
        assert updated.full_name == "Jane Smith"
        assert updated.email == "user@test.com"  # Inchangé

    def test_update_password_success(self, test_db):
        """Test: mise à jour password avec policy valide."""
        user = _make_user(test_db)
        service = UserService(test_db)

        new_password = "NewSecureP@ssw0rd123"
        data = UserProfileUpdate(password=new_password)
        updated = service.update_profile(user.id, user.tenant_id, data)

        # Vérifier que le hash a changé et est valide
        test_db.refresh(updated)
        assert verify_password(new_password, updated.hashed_password)

    def test_update_password_too_short(self, test_db):
        """Test: password trop court → ValidationError (Pydantic schema)."""
        user = _make_user(test_db)

        # Pydantic valide min_length dans le schema avant que le service soit appelé
        with pytest.raises(ValidationError) as exc_info:
            UserProfileUpdate(password="short")

        # Vérifier que l'erreur concerne bien la longueur du password
        errors = exc_info.value.errors()
        assert any(err["loc"] == ("password",) for err in errors)

    def test_update_password_no_uppercase(self, test_db):
        """Test: password sans majuscule → 400 (password policy)."""
        user = _make_user(test_db)
        service = UserService(test_db)

        data = UserProfileUpdate(password="nouppercase123!")
        with pytest.raises(HTTPException) as exc_info:
            service.update_profile(user.id, user.tenant_id, data)

        assert exc_info.value.status_code == 400

    def test_update_password_no_number(self, test_db):
        """Test: password sans chiffre → 400 (password policy)."""
        user = _make_user(test_db)
        service = UserService(test_db)

        data = UserProfileUpdate(password="NoNumberHere!")
        with pytest.raises(HTTPException) as exc_info:
            service.update_profile(user.id, user.tenant_id, data)

        assert exc_info.value.status_code == 400

    def test_update_partial_patch(self, test_db):
        """Test: PATCH partiel (uniquement certains champs fournis)."""
        user = _make_user(test_db, first_name="John", last_name="Doe", email="john@test.com")
        service = UserService(test_db)

        # Mise à jour seulement du first_name
        data = UserProfileUpdate(first_name="Jane")
        updated = service.update_profile(user.id, user.tenant_id, data)

        assert updated.first_name == "Jane"
        assert updated.last_name == "Doe"  # Inchangé
        assert updated.email == "john@test.com"  # Inchangé

    def test_update_user_not_found(self, test_db):
        """Test: utilisateur inexistant → NotFound."""
        service = UserService(test_db)

        data = UserProfileUpdate(first_name="Jane")
        with pytest.raises(NotFound) as exc_info:
            service.update_profile(user_id=9999, tenant_id=1, data=data)

        assert "User 9999 not found" in str(exc_info.value)

    def test_update_user_wrong_tenant(self, test_db):
        """Test: utilisateur d'un autre tenant → NotFound (isolation multi-tenant)."""
        user = _make_user(test_db, tenant_id=1, email="user@test.com")
        service = UserService(test_db)

        data = UserProfileUpdate(first_name="Jane")
        with pytest.raises(NotFound):
            # Tentative d'accès avec wrong tenant_id
            service.update_profile(user.id, tenant_id=2, data=data)

    def test_update_multiple_fields(self, test_db):
        """Test: mise à jour de plusieurs champs simultanément."""
        user = _make_user(test_db, first_name="John", last_name="Doe", email="john@test.com")
        service = UserService(test_db)

        data = UserProfileUpdate(
            email="jane.smith@test.com",
            first_name="Jane",
            last_name="Smith"
        )
        updated = service.update_profile(user.id, user.tenant_id, data)

        assert updated.email == "jane.smith@test.com"
        assert updated.first_name == "Jane"
        assert updated.last_name == "Smith"
        assert updated.full_name == "Jane Smith"

    def test_update_email_same_as_current(self, test_db):
        """Test: mise à jour email vers email actuel → OK (pas de conflit)."""
        user = _make_user(test_db, email="user@test.com")
        service = UserService(test_db)

        # Changer l'email vers la même valeur (normalisée)
        data = UserProfileUpdate(email="USER@test.com")
        updated = service.update_profile(user.id, user.tenant_id, data)

        assert updated.email == "user@test.com"
