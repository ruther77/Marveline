"""Tests unitaires pour app.core.logging.

Verifie :
- JSONFormatter produit du JSON valide avec les bons champs
- Sanitization masque password/token/secret
- ContextVars propagent request_id/tenant_id/user_id
- mask_email fonctionne correctement
- ConsoleFormatter produit un format lisible
- clear_request_context remet a None (fix M6)
"""

import json
import logging

import pytest

from app.core.logging import (
    REDACTED,
    ConsoleFormatter,
    JSONFormatter,
    clear_request_context,
    configure_logging,
    get_logger,
    mask_email,
    request_id_var,
    sanitize_dict,
    sanitize_value,
    set_request_context,
    tenant_id_var,
    user_id_var,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_context():
    """Nettoie les ContextVars avant et apres chaque test."""
    clear_request_context()
    yield
    clear_request_context()


@pytest.fixture()
def json_formatter():
    return JSONFormatter()


@pytest.fixture()
def console_formatter():
    return ConsoleFormatter()


def _make_record(message: str = "test", level: int = logging.INFO, **extra) -> logging.LogRecord:
    """Cree un LogRecord synthetique pour les tests."""
    record = logging.LogRecord(
        name="test.logger",
        level=level,
        pathname="test.py",
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for k, v in extra.items():
        setattr(record, k, v)
    return record


# ===================================================================
# sanitize_value / sanitize_dict
# ===================================================================

class TestSanitizeValue:
    """Tests pour sanitize_value."""

    def test_champ_normal_non_masque(self):
        """Un champ non sensible reste inchange."""
        assert sanitize_value("username", "alice") == "alice"

    def test_password_court_masque_completement(self):
        """Un password court (<=8 chars) est entierement masque."""
        assert sanitize_value("password", "short") == REDACTED

    def test_password_long_garde_4_premiers(self):
        """Un password long garde les 4 premiers chars pour debug."""
        result = sanitize_value("password", "MySecretPassword123")
        assert result.startswith("MySe")
        assert REDACTED in result

    def test_token_masque(self):
        """Le champ token est detecte comme sensible."""
        assert sanitize_value("access_token", "abc") == REDACTED

    def test_api_key_masque(self):
        """Le champ api_key est detecte comme sensible."""
        result = sanitize_value("api_key", "sk-1234567890abcdef")
        assert result.startswith("sk-1")
        assert REDACTED in result

    def test_sous_chaine_sensitive(self):
        """Un champ contenant un mot sensible est masque (ex: user_password_hash)."""
        assert sanitize_value("user_password_hash", "short") == REDACTED

    def test_case_insensitive(self):
        """La detection est insensible a la casse."""
        assert sanitize_value("PASSWORD", "short") == REDACTED
        assert sanitize_value("Password", "short") == REDACTED


class TestSanitizeDict:
    """Tests pour sanitize_dict."""

    def test_dict_simple(self):
        """Masque les champs sensibles dans un dict plat."""
        data = {"username": "alice", "password": "secret123456"}
        result = sanitize_dict(data)
        assert result["username"] == "alice"
        assert REDACTED in result["password"]

    def test_dict_imbrique(self):
        """Masque recursivement dans les dicts imbriques."""
        data = {"user": {"name": "alice", "token": "abc123def456"}}
        result = sanitize_dict(data)
        assert result["user"]["name"] == "alice"
        assert REDACTED in result["user"]["token"]

    def test_liste_dans_dict(self):
        """Traite les listes contenant des dicts."""
        data = {"users": [{"password": "s"}, {"name": "bob"}]}
        result = sanitize_dict(data)
        assert result["users"][0]["password"] == REDACTED
        assert result["users"][1]["name"] == "bob"

    def test_non_dict_retourne_tel_quel(self):
        """Un non-dict est retourne inchange."""
        assert sanitize_dict("not a dict") == "not a dict"


# ===================================================================
# mask_email
# ===================================================================

class TestMaskEmail:
    """Tests pour mask_email."""

    def test_email_standard(self):
        """john@example.com -> j***n@example.com"""
        assert mask_email("john@example.com") == "j**n@example.com"

    def test_email_court(self):
        """ab@x.com -> a*@x.com"""
        assert mask_email("ab@x.com") == "a*@x.com"

    def test_email_un_char(self):
        """a@x.com -> a*@x.com"""
        assert mask_email("a@x.com") == "a*@x.com"

    def test_email_vide(self):
        """Chaine vide retourne chaine vide."""
        assert mask_email("") == ""

    def test_email_none(self):
        """None retourne chaine vide."""
        assert mask_email(None) == ""

    def test_pas_de_arobase(self):
        """Sans @ retourne tel quel."""
        assert mask_email("notanemail") == "notanemail"


# ===================================================================
# JSONFormatter
# ===================================================================

class TestJSONFormatter:
    """Tests pour JSONFormatter."""

    def test_produit_json_valide(self, json_formatter):
        """Le formatter produit du JSON parsable."""
        record = _make_record("hello world")
        output = json_formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "hello world"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert "timestamp" in parsed

    def test_inclut_request_id_quand_set(self, json_formatter):
        """request_id apparait dans le JSON quand il est set."""
        set_request_context(request_id="abc-123")
        record = _make_record("test")
        parsed = json.loads(json_formatter.format(record))
        assert parsed["request_id"] == "abc-123"

    def test_inclut_tenant_id_quand_set(self, json_formatter):
        """tenant_id apparait dans le JSON quand il est set."""
        set_request_context(tenant_id=42)
        record = _make_record("test")
        parsed = json.loads(json_formatter.format(record))
        assert parsed["tenant_id"] == 42

    def test_inclut_user_id_quand_set(self, json_formatter):
        """user_id apparait dans le JSON quand il est set."""
        set_request_context(user_id=7)
        record = _make_record("test")
        parsed = json.loads(json_formatter.format(record))
        assert parsed["user_id"] == 7

    def test_pas_de_context_vars_quand_non_set(self, json_formatter):
        """Les context vars sont absents du JSON quand non set (None)."""
        record = _make_record("test")
        parsed = json.loads(json_formatter.format(record))
        assert "request_id" not in parsed
        assert "tenant_id" not in parsed
        assert "user_id" not in parsed

    def test_extra_fields_sanitized(self, json_formatter):
        """Les champs extra sont sanitizes."""
        record = _make_record("test", password="supersecretpassword")
        parsed = json.loads(json_formatter.format(record))
        assert REDACTED in parsed["extra"]["password"]

    def test_exception_info(self, json_formatter):
        """Les exceptions sont incluses dans le JSON."""
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            record = _make_record("error")
            record.exc_info = sys.exc_info()

        parsed = json.loads(json_formatter.format(record))
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]


# ===================================================================
# ConsoleFormatter
# ===================================================================

class TestConsoleFormatter:
    """Tests pour ConsoleFormatter."""

    def test_format_lisible(self, console_formatter):
        """Le formatter console produit un format lisible."""
        record = _make_record("hello", level=logging.INFO)
        output = console_formatter.format(record)
        assert "[INFO]" in output
        assert "test.logger" in output
        assert "hello" in output

    def test_inclut_request_id(self, console_formatter):
        """Le request_id tronque apparait entre parentheses."""
        set_request_context(request_id="abcdefgh-1234-5678")
        record = _make_record("test")
        output = console_formatter.format(record)
        assert "(request_id=abcdefgh...)" in output

    def test_pas_de_request_id_quand_non_set(self, console_formatter):
        """Pas de parenthese request_id quand non set."""
        record = _make_record("test")
        output = console_formatter.format(record)
        assert "request_id" not in output


# ===================================================================
# ContextVars / set_request_context / clear_request_context
# ===================================================================

class TestRequestContext:
    """Tests pour set/clear request context."""

    def test_set_request_context(self):
        """set_request_context positionne les 3 vars."""
        set_request_context(request_id="req-1", tenant_id=5, user_id=10)
        assert request_id_var.get() == "req-1"
        assert tenant_id_var.get() == 5
        assert user_id_var.get() == 10

    def test_clear_remet_a_none(self):
        """clear_request_context remet a None (fix M6 — pas 0 ni '')."""
        set_request_context(request_id="req-1", tenant_id=5, user_id=10)
        clear_request_context()
        assert request_id_var.get() is None
        assert tenant_id_var.get() is None
        assert user_id_var.get() is None

    def test_set_partiel(self):
        """On peut set un seul champ sans affecter les autres."""
        set_request_context(request_id="only-this")
        assert request_id_var.get() == "only-this"
        assert tenant_id_var.get() is None
        assert user_id_var.get() is None

    def test_defaults_sont_none(self):
        """Les defaults des ContextVars sont None (fix M6)."""
        # Apres le clear dans la fixture, tout est None
        assert request_id_var.get() is None
        assert tenant_id_var.get() is None
        assert user_id_var.get() is None


# ===================================================================
# configure_logging / get_logger
# ===================================================================

class TestConfigureLogging:
    """Tests pour configure_logging et get_logger."""

    def test_configure_json(self):
        """configure_logging en mode JSON installe un JSONFormatter."""
        configure_logging(level="DEBUG", json_format=True)
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_configure_console(self):
        """configure_logging en mode console installe un ConsoleFormatter."""
        configure_logging(level="DEBUG", json_format=False)
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, ConsoleFormatter)

    def test_get_logger_retourne_logger(self):
        """get_logger retourne un logger standard."""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_libs_tierces_reduites(self):
        """Les loggers de libs tierces sont positionnes a WARNING."""
        configure_logging(level="DEBUG", json_format=True)
        assert logging.getLogger("uvicorn.access").level == logging.WARNING
        assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING
