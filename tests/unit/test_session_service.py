"""Tests unitaires pour SessionService — gestion sessions Redis.

Couvre :
    - Création de session (metadata, UUID)
    - Enforcement max sessions (éviction plus ancienne)
    - Listing sessions (tri par date)
    - Révocation session (+ tokens associés)
    - Révocation toutes sessions
    - Mise à jour last_activity
    - Recherche par family_id (pour logout)
    - Vérification ownership (pas de cross-user)

Fichier service testé : app/services/session.py
Fichier constants : app/constants/security.py (SessionConfig, RedisKeys)
Fichier Redis : app/core/redis.py (méthodes session)
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, call

import pytest

from app.services.session import SessionService, session_service
from app.constants import SessionConfig, RedisKeys


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def svc():
    """Instance fraîche du service (pas le singleton)."""
    return SessionService()


@pytest.fixture
def mock_redis():
    """Mock du redis_client pour tests unitaires purs."""
    with patch("app.services.session.redis_client") as mock:
        # Defaults
        mock.store_session.return_value = True
        mock.get_session.return_value = None
        mock.delete_session.return_value = True
        mock.list_user_sessions.return_value = []
        mock.delete_all_user_sessions.return_value = 0
        mock.update_session_activity.return_value = True
        mock.revoke_token_family.return_value = True
        yield mock


# ─────────────────────────────────────────────────────────────────────
# create_session
# ─────────────────────────────────────────────────────────────────────

class TestCreateSession:
    """Tests pour create_session()."""

    def test_returns_uuid_string(self, svc, mock_redis):
        """create_session retourne un UUID valide."""
        session_id = svc.create_session(
            user_id=1, tenant_id=1, family_id="fam-1",
            ip_address="1.2.3.4", user_agent="Chrome/120",
        )
        # Doit être un UUID valide
        parsed = uuid.UUID(session_id)
        assert str(parsed) == session_id

    def test_stores_session_in_redis(self, svc, mock_redis):
        """create_session appelle store_session avec les bonnes données."""
        session_id = svc.create_session(
            user_id=42, tenant_id=3, family_id="fam-abc",
            ip_address="10.0.0.1", user_agent="Firefox/130",
        )
        mock_redis.store_session.assert_called_once()
        call_args = mock_redis.store_session.call_args
        assert call_args.kwargs["session_id"] == session_id
        data = call_args.kwargs["data"]
        assert data["session_id"] == session_id
        assert data["user_id"] == 42
        assert data["tenant_id"] == 3
        assert data["family_id"] == "fam-abc"
        assert data["ip_address"] == "10.0.0.1"
        assert data["user_agent"] == "Firefox/130"
        assert "created_at" in data
        assert "last_activity" in data
        assert call_args.kwargs["ttl_seconds"] == SessionConfig.SESSION_TTL_SECONDS

    def test_session_has_timestamps(self, svc, mock_redis):
        """Session data contient created_at et last_activity."""
        svc.create_session(
            user_id=1, tenant_id=1, family_id="fam-1",
            ip_address="1.2.3.4", user_agent="Chrome",
        )
        data = mock_redis.store_session.call_args.kwargs["data"]
        # Les timestamps doivent être des ISO strings valides
        created = datetime.fromisoformat(data["created_at"])
        activity = datetime.fromisoformat(data["last_activity"])
        assert created == activity  # Égaux à la création

    def test_enforces_max_sessions(self, svc, mock_redis):
        """Si user a MAX sessions, la plus ancienne est évincée."""
        # Simuler 5 sessions existantes
        existing_sessions = [
            {"session_id": f"old-{i}", "user_id": 1, "family_id": f"fam-{i}",
             "created_at": f"2026-02-{10+i:02d}T00:00:00+00:00"}
            for i in range(5)
        ]
        mock_redis.list_user_sessions.return_value = existing_sessions

        svc.create_session(
            user_id=1, tenant_id=1, family_id="fam-new",
            ip_address="1.2.3.4", user_agent="Chrome",
        )

        # La plus ancienne (old-0, 2026-02-10) doit être supprimée
        mock_redis.delete_session.assert_called_with("old-0", 1)
        mock_redis.revoke_token_family.assert_called_with("fam-0")

    def test_no_eviction_under_max(self, svc, mock_redis):
        """Pas d'éviction si user a < MAX sessions."""
        existing = [
            {"session_id": f"s-{i}", "user_id": 1, "family_id": f"f-{i}",
             "created_at": f"2026-02-{10+i:02d}T00:00:00+00:00"}
            for i in range(3)
        ]
        mock_redis.list_user_sessions.return_value = existing

        svc.create_session(
            user_id=1, tenant_id=1, family_id="fam-new",
            ip_address="1.2.3.4", user_agent="Chrome",
        )

        mock_redis.delete_session.assert_not_called()
        mock_redis.revoke_token_family.assert_not_called()


# ─────────────────────────────────────────────────────────────────────
# get_session
# ─────────────────────────────────────────────────────────────────────

class TestGetSession:
    """Tests pour get_session()."""

    def test_returns_session_data(self, svc, mock_redis):
        """get_session retourne les données de session."""
        mock_redis.get_session.return_value = {"session_id": "abc", "user_id": 1}
        result = svc.get_session("abc")
        assert result == {"session_id": "abc", "user_id": 1}
        mock_redis.get_session.assert_called_once_with("abc")

    def test_returns_none_if_not_found(self, svc, mock_redis):
        """get_session retourne None si session inexistante."""
        mock_redis.get_session.return_value = None
        assert svc.get_session("nonexistent") is None


# ─────────────────────────────────────────────────────────────────────
# get_session_by_family
# ─────────────────────────────────────────────────────────────────────

class TestGetSessionByFamily:
    """Tests pour get_session_by_family()."""

    def test_finds_matching_session(self, svc, mock_redis):
        """Trouve la session avec le bon family_id."""
        sessions = [
            {"session_id": "s-1", "user_id": 1, "family_id": "fam-A"},
            {"session_id": "s-2", "user_id": 1, "family_id": "fam-B"},
        ]
        mock_redis.list_user_sessions.return_value = sessions

        result = svc.get_session_by_family(user_id=1, family_id="fam-B")
        assert result["session_id"] == "s-2"

    def test_returns_none_if_not_found(self, svc, mock_redis):
        """Retourne None si aucune session ne match."""
        mock_redis.list_user_sessions.return_value = [
            {"session_id": "s-1", "user_id": 1, "family_id": "fam-A"},
        ]
        result = svc.get_session_by_family(user_id=1, family_id="fam-Z")
        assert result is None

    def test_returns_none_if_no_sessions(self, svc, mock_redis):
        """Retourne None si user n'a aucune session."""
        mock_redis.list_user_sessions.return_value = []
        result = svc.get_session_by_family(user_id=1, family_id="fam-X")
        assert result is None


# ─────────────────────────────────────────────────────────────────────
# list_sessions
# ─────────────────────────────────────────────────────────────────────

class TestListSessions:
    """Tests pour list_sessions()."""

    def test_returns_sorted_by_created_at_desc(self, svc, mock_redis):
        """Sessions triées par created_at décroissant (plus récente en premier)."""
        sessions = [
            {"session_id": "s-1", "created_at": "2026-02-10T00:00:00+00:00"},
            {"session_id": "s-3", "created_at": "2026-02-12T00:00:00+00:00"},
            {"session_id": "s-2", "created_at": "2026-02-11T00:00:00+00:00"},
        ]
        mock_redis.list_user_sessions.return_value = sessions

        result = svc.list_sessions(user_id=1)
        assert [s["session_id"] for s in result] == ["s-3", "s-2", "s-1"]

    def test_empty_list_for_no_sessions(self, svc, mock_redis):
        """Retourne liste vide si pas de sessions."""
        mock_redis.list_user_sessions.return_value = []
        assert svc.list_sessions(user_id=1) == []


# ─────────────────────────────────────────────────────────────────────
# revoke_session
# ─────────────────────────────────────────────────────────────────────

class TestRevokeSession:
    """Tests pour revoke_session()."""

    def test_revokes_session_and_tokens(self, svc, mock_redis):
        """Révoque la session + famille de tokens."""
        mock_redis.get_session.return_value = {
            "session_id": "s-1", "user_id": 1, "family_id": "fam-A",
        }

        result = svc.revoke_session("s-1", user_id=1)
        assert result is True
        mock_redis.revoke_token_family.assert_called_once_with("fam-A")
        mock_redis.delete_session.assert_called_once_with("s-1", 1)

    def test_returns_false_if_not_found(self, svc, mock_redis):
        """Retourne False si session inexistante."""
        mock_redis.get_session.return_value = None
        result = svc.revoke_session("nonexistent", user_id=1)
        assert result is False
        mock_redis.delete_session.assert_not_called()

    def test_denies_cross_user_revoke(self, svc, mock_redis):
        """Interdit de révoquer la session d'un autre utilisateur."""
        mock_redis.get_session.return_value = {
            "session_id": "s-1", "user_id": 99, "family_id": "fam-X",
        }
        result = svc.revoke_session("s-1", user_id=1)
        assert result is False
        mock_redis.delete_session.assert_not_called()
        mock_redis.revoke_token_family.assert_not_called()

    def test_handles_session_without_family_id(self, svc, mock_redis):
        """Session sans family_id (edge case) — supprime quand même la session."""
        mock_redis.get_session.return_value = {
            "session_id": "s-1", "user_id": 1,
        }
        result = svc.revoke_session("s-1", user_id=1)
        assert result is True
        mock_redis.revoke_token_family.assert_not_called()
        mock_redis.delete_session.assert_called_once_with("s-1", 1)


# ─────────────────────────────────────────────────────────────────────
# revoke_all_sessions
# ─────────────────────────────────────────────────────────────────────

class TestRevokeAllSessions:
    """Tests pour revoke_all_sessions()."""

    def test_revokes_all_and_returns_count(self, svc, mock_redis):
        """Révoque toutes les sessions et retourne le count."""
        mock_redis.list_user_sessions.return_value = [
            {"session_id": "s-1", "user_id": 1, "family_id": "fam-A"},
            {"session_id": "s-2", "user_id": 1, "family_id": "fam-B"},
        ]
        mock_redis.delete_all_user_sessions.return_value = 2

        count = svc.revoke_all_sessions(user_id=1)
        assert count == 2
        assert mock_redis.revoke_token_family.call_count == 2
        mock_redis.revoke_token_family.assert_any_call("fam-A")
        mock_redis.revoke_token_family.assert_any_call("fam-B")
        mock_redis.delete_all_user_sessions.assert_called_once_with(1)

    def test_returns_zero_if_no_sessions(self, svc, mock_redis):
        """Retourne 0 si pas de sessions."""
        mock_redis.list_user_sessions.return_value = []
        mock_redis.delete_all_user_sessions.return_value = 0
        assert svc.revoke_all_sessions(user_id=1) == 0


# ─────────────────────────────────────────────────────────────────────
# update_activity
# ─────────────────────────────────────────────────────────────────────

class TestUpdateActivity:
    """Tests pour update_activity()."""

    def test_updates_activity(self, svc, mock_redis):
        """update_activity délègue à redis_client."""
        mock_redis.update_session_activity.return_value = True
        assert svc.update_activity("s-1") is True
        mock_redis.update_session_activity.assert_called_once_with("s-1")

    def test_returns_false_if_not_found(self, svc, mock_redis):
        """Retourne False si session inexistante."""
        mock_redis.update_session_activity.return_value = False
        assert svc.update_activity("nonexistent") is False


# ─────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────

class TestSessionConstants:
    """Tests pour les constantes de session."""

    def test_max_sessions_per_user(self):
        """MAX_SESSIONS_PER_USER = 5."""
        assert SessionConfig.MAX_SESSIONS_PER_USER == 5

    def test_session_ttl(self):
        """SESSION_TTL = 7 jours."""
        assert SessionConfig.SESSION_TTL_SECONDS == 7 * 24 * 3600

    def test_redis_keys_exist(self):
        """Les clés Redis session existent."""
        assert RedisKeys.SESSION == "session:"
        assert RedisKeys.SESSION_USER_INDEX == "session_idx:"

    def test_session_user_index_helper(self):
        """Helper génère la bonne clé."""
        assert RedisKeys.session_user_index(42) == "session_idx:42"


# ─────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────

class TestSingleton:
    """Tests pour le singleton session_service."""

    def test_singleton_is_session_service(self):
        """session_service est une instance de SessionService."""
        assert isinstance(session_service, SessionService)

    def test_singleton_identity(self):
        """Imports multiples retournent le même objet."""
        from app.services.session import session_service as svc2
        assert session_service is svc2


# ─────────────────────────────────────────────────────────────────────
# Eviction — cas avancés
# ─────────────────────────────────────────────────────────────────────

class TestEvictionAdvanced:
    """Tests avancés pour l'éviction de sessions."""

    def test_evicts_multiple_when_over_max(self, svc, mock_redis):
        """Si user a 6 sessions (>MAX), évince les 2 plus anciennes."""
        existing = [
            {"session_id": f"s-{i}", "user_id": 1, "family_id": f"f-{i}",
             "created_at": f"2026-02-{10+i:02d}T00:00:00+00:00"}
            for i in range(6)
        ]
        mock_redis.list_user_sessions.return_value = existing

        svc.create_session(
            user_id=1, tenant_id=1, family_id="fam-new",
            ip_address="1.2.3.4", user_agent="Chrome",
        )

        # 6 existantes + 1 nouvelle = 7, max = 5. Doit évincer 7 - 5 = 2 plus anciennes.
        # Les appels delete_session doivent être pour s-0 et s-1
        delete_calls = mock_redis.delete_session.call_args_list
        assert len(delete_calls) == 2
        assert delete_calls[0] == call("s-0", 1)
        assert delete_calls[1] == call("s-1", 1)

    def test_eviction_revokes_token_families(self, svc, mock_redis):
        """L'éviction révoque aussi les familles de tokens."""
        existing = [
            {"session_id": "s-old", "user_id": 1, "family_id": "fam-old",
             "created_at": "2026-02-01T00:00:00+00:00"},
        ] * 5  # 5 sessions identiques (simplification)
        mock_redis.list_user_sessions.return_value = existing

        svc.create_session(
            user_id=1, tenant_id=1, family_id="fam-new",
            ip_address="1.2.3.4", user_agent="Chrome",
        )

        # Au moins 1 famille révoquée
        assert mock_redis.revoke_token_family.call_count >= 1
