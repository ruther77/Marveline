"""Tests unitaires — app/services/hibp.py — HIBP k-anonymity SHA-1.

Couverture (CaroCorp §7.2 NIVEAU 5) :
  - Mot de passe présent dans HIBP → True
  - Mot de passe absent → False
  - API HIBP down → False (FAIL-OPEN)
  - Erreur HTTP API → False (FAIL-OPEN)
  - Seul le préfixe 5-chars SHA-1 est transmis (k-anonymity)
  - Header Add-Padding: true envoyé

Note : import isolé via importlib pour éviter le chargement de app/services/__init__.py
qui tire app/models/* avec un bug SQLAlchemy 2.0 sur UniqueConstraint(postgresql_where).
Voir BUG-SQLALCHEMY-01 dans MEMORY.md.
"""
import hashlib
import importlib.util
import secrets
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

# Import isolé de hibp.py — ne charge pas app/services/__init__.py
_hibp_path = Path(__file__).parent.parent.parent / "app" / "services" / "hibp.py"
_spec = importlib.util.spec_from_file_location("app.services.hibp", _hibp_path)
_hibp_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hibp_module)
is_password_compromised = _hibp_module.is_password_compromised


class TestIsPasswordCompromised:
    """Tests unitaires pour is_password_compromised()."""

    def _sha1_upper(self, password: str) -> str:
        return hashlib.sha1(
            password.encode("utf-8"), usedforsecurity=False
        ).hexdigest().upper()

    def _make_client_mock(self, response_text: str):
        """Construit un mock httpx.Client contextmanager retournant response_text."""
        mock_resp = MagicMock()
        mock_resp.text = response_text
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        mock_client_cls = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        return mock_client_cls, mock_client

    def test_compromised_password_returns_true(self):
        """Mot de passe dans la base HIBP → True."""
        password = "password"
        sha1 = self._sha1_upper(password)
        suffix = sha1[5:]
        response_text = f"AAAAA:1\n{suffix}:17394\nBBBBB:2\n"

        mock_client_cls, _ = self._make_client_mock(response_text)
        with patch("httpx.Client", mock_client_cls):
            result = is_password_compromised(password)

        assert result is True

    def test_safe_password_returns_false(self):
        """Mot de passe absent de HIBP → False."""
        password = secrets.token_hex(32)
        sha1 = self._sha1_upper(password)
        suffix = sha1[5:]
        # Réponse qui ne contient PAS ce suffix
        other_suffix = "AAAAA" if suffix != "AAAAA" else "BBBBB"
        response_text = f"{other_suffix}:1\n"

        mock_client_cls, _ = self._make_client_mock(response_text)
        with patch("httpx.Client", mock_client_cls):
            result = is_password_compromised(password)

        assert result is False

    def test_empty_response_returns_false(self):
        """Réponse vide de HIBP → False."""
        mock_client_cls, _ = self._make_client_mock("")
        with patch("httpx.Client", mock_client_cls):
            result = is_password_compromised("uniquepassword123!")

        assert result is False

    def test_api_connection_error_fail_open(self):
        """API HIBP inaccessible (ConnectionError) → False (FAIL-OPEN)."""
        mock_client_cls = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(
            side_effect=ConnectionError("timeout")
        )
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch("httpx.Client", mock_client_cls):
            result = is_password_compromised("anypassword")

        assert result is False

    def test_api_http_error_fail_open(self):
        """API HIBP retourne HTTP 503 → False (FAIL-OPEN)."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=MagicMock(),
            response=MagicMock(),
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client_cls = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch("httpx.Client", mock_client_cls):
            result = is_password_compromised("anypassword")

        assert result is False

    def test_only_prefix_5_chars_transmitted(self):
        """Seul le préfixe SHA-1 (5 chars) est envoyé — k-anonymity garantie."""
        password = "testpassword123"
        sha1 = self._sha1_upper(password)
        prefix = sha1[:5]

        mock_client_cls, mock_client = self._make_client_mock("")
        with patch("httpx.Client", mock_client_cls):
            is_password_compromised(password)

        called_url = mock_client.get.call_args[0][0]
        assert called_url == f"https://api.pwnedpasswords.com/range/{prefix}"
        assert len(prefix) == 5
        # Le mot de passe complet n'apparaît PAS dans l'URL
        assert password not in called_url
        assert sha1[5:] not in called_url

    def test_add_padding_header_sent(self):
        """Header Add-Padding: true envoyé pour anti-timing attack."""
        mock_client_cls, _ = self._make_client_mock("")

        with patch("httpx.Client", mock_client_cls):
            is_password_compromised("test")

        call_kwargs = mock_client_cls.call_args
        headers = (
            call_kwargs.kwargs.get("headers")
            or (call_kwargs[1].get("headers") if len(call_kwargs) > 1 else {})
            or {}
        )
        assert headers.get("Add-Padding") == "true"

    def test_timeout_configured(self):
        """Timeout 3s configuré sur le client httpx."""
        mock_client_cls, _ = self._make_client_mock("")

        with patch("httpx.Client", mock_client_cls):
            is_password_compromised("test")

        call_kwargs = mock_client_cls.call_args
        timeout = (
            call_kwargs.kwargs.get("timeout")
            or (call_kwargs[1].get("timeout") if len(call_kwargs) > 1 else None)
        )
        assert timeout == 3.0
