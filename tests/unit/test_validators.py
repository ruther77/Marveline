"""Tests unitaires pour app.core.validators.

Verifie :
- Fix M5 : apostrophe acceptee ("O'Brien", "l'Ile")
- Fix M16 : pas de validate_password_safe
- SQL injection patterns detectes (OR 1=1, UNION SELECT, etc.)
- XSS patterns detectes (<script>, javascript:, etc.)
- Path traversal detectes (../, ..\, etc.)
- Strings normales acceptees
- sanitize_string strip HTML mais garde apostrophes
- Fonctions Pydantic (validate_email_safe, validate_text_safe, etc.)
"""

import pytest

from app.core.validators import (
    SecurityValidators,
    validate_email_safe,
    validate_path_safe,
    validate_text_safe,
    validate_username_safe,
)


# ===================================================================
# Fix M5 : apostrophe autorisee
# ===================================================================

class TestApostropheAccepted:
    """Fix M5 : l'apostrophe ne doit plus etre bloquee."""

    def test_obrien_accepted(self):
        """Le nom "O'Brien" est accepte (fix M5)."""
        result = SecurityValidators.validate_no_sql_injection("O'Brien", "name")
        assert result == "O'Brien"

    def test_lile_accepted(self):
        """Le mot "l'Ile" est accepte (fix M5)."""
        result = SecurityValidators.validate_no_sql_injection("l'Ile", "name")
        assert result == "l'Ile"

    def test_apostrophe_in_text(self):
        """Un texte avec apostrophes est accepte."""
        text = "C'est l'anniversaire de Jean-Pierre d'Artagnan"
        result = SecurityValidators.validate_safe_string(text, "description")
        assert result == text

    def test_guillemets_accepted(self):
        """Les guillemets simples dans du texte sont acceptes."""
        text = 'Il a dit "bonjour" puis est parti'
        result = SecurityValidators.validate_safe_string(text, "note")
        assert result == text

    def test_semicolon_alone_accepted(self):
        """Un point-virgule seul est accepte (pas un pattern SQL complet)."""
        text = "Chaise longue; Table ronde"
        result = SecurityValidators.validate_no_sql_injection(text, "description")
        assert result == text

    def test_double_dash_comment_accepted_in_middle(self):
        """'--' au milieu d'un texte n'est pas un commentaire SQL."""
        text = "ref--2024-001"
        result = SecurityValidators.validate_no_sql_injection(text, "ref")
        assert result == text


# ===================================================================
# SQL Injection detection
# ===================================================================

class TestSQLInjection:
    """Tests pour la detection de SQL injection."""

    def test_or_1_equals_1(self):
        """'OR 1=1' est rejete."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection("admin' OR 1=1", "username")

    def test_and_1_equals_1(self):
        """'AND 1=1' est rejete."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection("test AND 1=1", "field")

    def test_union_select(self):
        """'UNION SELECT' est rejete."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection(
                "1 UNION SELECT * FROM users", "id"
            )

    def test_union_all_select(self):
        """'UNION ALL SELECT' est rejete."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection(
                "1 UNION ALL SELECT username FROM users", "id"
            )

    def test_drop_table(self):
        """'; DROP TABLE' est rejete."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection(
                "test; DROP TABLE users", "name"
            )

    def test_delete_from(self):
        """'; DELETE FROM' est rejete."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection(
                "x; DELETE FROM customers", "name"
            )

    def test_update_set(self):
        """'; UPDATE ... SET' est rejete."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection(
                "x; UPDATE users SET admin=1", "name"
            )

    def test_insert_into(self):
        """'; INSERT INTO' est rejete."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection(
                "x; INSERT INTO users VALUES('hack')", "name"
            )

    def test_exec_parenthesis(self):
        """'EXEC(' est rejete."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection(
                "EXEC(sp_executesql)", "name"
            )

    def test_waitfor_delay(self):
        """'WAITFOR DELAY' (time-based) est rejete."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection(
                "WAITFOR DELAY '0:0:5'", "name"
            )

    def test_sleep_function(self):
        """'SLEEP(' (MySQL time-based) est rejete."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection(
                "SELECT SLEEP(5)", "name"
            )

    def test_information_schema(self):
        """'information_schema' est rejete."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection(
                "SELECT * FROM information_schema.tables", "name"
            )

    def test_sql_comment_end_of_line(self):
        """'-- ' en fin de ligne est rejete (commentaire SQL)."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection("admin'--", "username")

    def test_block_comment(self):
        """'/* */' (commentaire bloc SQL) est rejete."""
        with pytest.raises(ValueError, match="malicious SQL"):
            SecurityValidators.validate_no_sql_injection(
                "admin/**/password", "field"
            )

    def test_normal_string_accepted(self):
        """Une string normale passe la validation SQL."""
        result = SecurityValidators.validate_no_sql_injection(
            "Jean-Pierre Dupont", "name"
        )
        assert result == "Jean-Pierre Dupont"

    def test_non_string_passthrough(self):
        """Un non-string est retourne tel quel."""
        result = SecurityValidators.validate_no_sql_injection(42, "field")
        assert result == 42


# ===================================================================
# XSS detection
# ===================================================================

class TestXSSDetection:
    """Tests pour la detection XSS."""

    def test_script_tag(self):
        """'<script>' est rejete."""
        with pytest.raises(ValueError, match="malicious HTML"):
            SecurityValidators.validate_no_xss("<script>alert(1)</script>", "text")

    def test_script_tag_with_spaces(self):
        """'< script >' est rejete."""
        with pytest.raises(ValueError, match="malicious HTML"):
            SecurityValidators.validate_no_xss("< script >alert(1)", "text")

    def test_iframe_tag(self):
        """'<iframe>' est rejete."""
        with pytest.raises(ValueError, match="malicious HTML"):
            SecurityValidators.validate_no_xss('<iframe src="evil.com">', "text")

    def test_javascript_protocol(self):
        """'javascript:' est rejete."""
        with pytest.raises(ValueError, match="malicious HTML"):
            SecurityValidators.validate_no_xss("javascript:alert(1)", "url")

    def test_vbscript_protocol(self):
        """'vbscript:' est rejete."""
        with pytest.raises(ValueError, match="malicious HTML"):
            SecurityValidators.validate_no_xss("vbscript:msgbox", "url")

    def test_onerror_attribute(self):
        """'onerror=\"...\"' est rejete."""
        with pytest.raises(ValueError, match="malicious HTML"):
            SecurityValidators.validate_no_xss('onerror="alert(1)"', "text")

    def test_onclick_attribute(self):
        """'onclick=\"...\"' est rejete."""
        with pytest.raises(ValueError, match="malicious HTML"):
            SecurityValidators.validate_no_xss('onclick="hack()"', "text")

    def test_img_onerror(self):
        """'<img onerror=...>' est rejete."""
        with pytest.raises(ValueError, match="malicious HTML"):
            SecurityValidators.validate_no_xss(
                '<img src=x onerror="alert(1)">', "text"
            )

    def test_svg_onload(self):
        """'<svg onload=...>' est rejete."""
        with pytest.raises(ValueError, match="malicious HTML"):
            SecurityValidators.validate_no_xss(
                '<svg onload="alert(1)">', "text"
            )

    def test_data_text_html(self):
        """'data:text/html' est rejete."""
        with pytest.raises(ValueError, match="malicious HTML"):
            SecurityValidators.validate_no_xss(
                "data:text/html,<script>alert(1)</script>", "url"
            )

    def test_embed_tag(self):
        """'<embed>' est rejete."""
        with pytest.raises(ValueError, match="malicious HTML"):
            SecurityValidators.validate_no_xss('<embed src="evil.swf">', "text")

    def test_object_tag(self):
        """'<object>' est rejete."""
        with pytest.raises(ValueError, match="malicious HTML"):
            SecurityValidators.validate_no_xss('<object data="evil">', "text")

    def test_normal_html_entities_accepted(self):
        """Du texte avec &amp; est accepte (pas un tag)."""
        result = SecurityValidators.validate_no_xss(
            "Tom &amp; Jerry", "text"
        )
        assert result == "Tom &amp; Jerry"

    def test_angle_brackets_in_math_accepted(self):
        """'2 < 3 > 1' accepte (pas un tag HTML complet)."""
        result = SecurityValidators.validate_no_xss("2 < 3 and 3 > 1", "text")
        assert result == "2 < 3 and 3 > 1"

    def test_non_string_passthrough(self):
        """Un non-string est retourne tel quel."""
        result = SecurityValidators.validate_no_xss(42, "field")
        assert result == 42


# ===================================================================
# Path traversal detection
# ===================================================================

class TestPathTraversal:
    """Tests pour la detection de path traversal."""

    def test_dot_dot_slash(self):
        """'../' est rejete."""
        with pytest.raises(ValueError, match="path traversal"):
            SecurityValidators.validate_no_path_traversal("../etc/passwd", "file")

    def test_dot_dot_backslash(self):
        """'..\\' est rejete."""
        with pytest.raises(ValueError, match="path traversal"):
            SecurityValidators.validate_no_path_traversal("..\\windows\\system32", "file")

    def test_url_encoded(self):
        """'%2e%2e/' (URL encoded) est rejete."""
        with pytest.raises(ValueError, match="path traversal"):
            SecurityValidators.validate_no_path_traversal(
                "%2e%2e/etc/passwd", "file"
            )

    def test_dot_dot_percent_2f(self):
        """'..%2f' est rejete."""
        with pytest.raises(ValueError, match="path traversal"):
            SecurityValidators.validate_no_path_traversal("..%2fetc/passwd", "file")

    def test_normal_path_accepted(self):
        """Un chemin normal est accepte."""
        result = SecurityValidators.validate_no_path_traversal(
            "uploads/photo.jpg", "file"
        )
        assert result == "uploads/photo.jpg"

    def test_single_dot_accepted(self):
        """Un seul '.' est accepte (pas un traversal)."""
        result = SecurityValidators.validate_no_path_traversal("file.txt", "file")
        assert result == "file.txt"

    def test_non_string_passthrough(self):
        """Un non-string est retourne tel quel."""
        result = SecurityValidators.validate_no_path_traversal(42, "field")
        assert result == 42


# ===================================================================
# validate_safe_string (combinaison)
# ===================================================================

class TestValidateSafeString:
    """Tests pour validate_safe_string (validation combinee)."""

    def test_sql_only(self):
        """Verifie uniquement SQL si check_xss=False."""
        # XSS passe car check_xss=False
        result = SecurityValidators.validate_safe_string(
            "text with <b>bold</b>",
            check_sql=True,
            check_xss=False,
        )
        assert "bold" in result

    def test_xss_only(self):
        """Verifie uniquement XSS si check_sql=False."""
        # SQL passe car check_sql=False
        with pytest.raises(ValueError, match="malicious HTML"):
            SecurityValidators.validate_safe_string(
                '<script>alert("xss")</script>',
                check_sql=False,
                check_xss=True,
            )

    def test_path_check_when_enabled(self):
        """Path traversal detecte si check_path=True."""
        with pytest.raises(ValueError, match="path traversal"):
            SecurityValidators.validate_safe_string(
                "../etc/passwd",
                check_path=True,
            )

    def test_path_not_checked_by_default(self):
        """Path traversal ignore par defaut (check_path=False)."""
        result = SecurityValidators.validate_safe_string("../file.txt")
        assert result == "../file.txt"

    def test_non_string_passthrough(self):
        """Un non-string est retourne tel quel."""
        result = SecurityValidators.validate_safe_string(None, "field")
        assert result is None


# ===================================================================
# sanitize_string
# ===================================================================

class TestSanitizeString:
    """Tests pour sanitize_string."""

    def test_strip_html_tags(self):
        """Les tags HTML sont retires."""
        result = SecurityValidators.sanitize_string("<b>bold</b> text")
        assert result == "bold text"

    def test_strip_script_tags(self):
        """Les tags script sont retires."""
        result = SecurityValidators.sanitize_string(
            "<script>alert(1)</script>Hello"
        )
        assert result == "alert(1)Hello"

    def test_keep_apostrophes(self):
        """Les apostrophes sont gardees (fix M5)."""
        result = SecurityValidators.sanitize_string("O'Brien l'Ile")
        assert result == "O'Brien l'Ile"

    def test_keep_guillemets(self):
        """Les guillemets sont gardes (fix M5)."""
        result = SecurityValidators.sanitize_string('Il a dit "bonjour"')
        assert result == 'Il a dit "bonjour"'

    def test_max_length(self):
        """La longueur est limitee."""
        result = SecurityValidators.sanitize_string("a" * 2000, max_length=100)
        assert len(result) == 100

    def test_strip_control_chars(self):
        """Les caracteres de controle sont retires."""
        result = SecurityValidators.sanitize_string("hello\x00\x07world")
        assert result == "helloworld"

    def test_keep_newlines_tabs(self):
        """Newlines et tabs sont gardes."""
        result = SecurityValidators.sanitize_string("line1\nline2\ttab")
        assert result == "line1\nline2\ttab"

    def test_strip_whitespace(self):
        """Les espaces en debut/fin sont retires."""
        result = SecurityValidators.sanitize_string("  hello  ")
        assert result == "hello"

    def test_non_string_passthrough(self):
        """Un non-string est retourne tel quel."""
        result = SecurityValidators.sanitize_string(42)
        assert result == 42


# ===================================================================
# Fonctions Pydantic validators
# ===================================================================

class TestPydanticValidators:
    """Tests pour les fonctions Pydantic (validate_*_safe)."""

    def test_email_safe_accepts_normal(self):
        """Email normale acceptee."""
        result = validate_email_safe("user@example.com")
        assert result == "user@example.com"

    def test_email_safe_rejects_xss(self):
        """Email avec XSS rejetee."""
        with pytest.raises(ValueError):
            validate_email_safe('<script>alert("xss")</script>@evil.com')

    def test_email_safe_rejects_sql(self):
        """Email avec SQL injection rejetee."""
        with pytest.raises(ValueError):
            validate_email_safe("admin' OR 1=1--@evil.com")

    def test_text_safe_accepts_normal(self):
        """Texte normal accepte."""
        result = validate_text_safe("Bonjour, comment allez-vous ?")
        assert result == "Bonjour, comment allez-vous ?"

    def test_text_safe_accepts_apostrophes(self):
        """Texte avec apostrophes accepte (fix M5)."""
        result = validate_text_safe("L'equipe d'O'Brien")
        assert result == "L'equipe d'O'Brien"

    def test_username_safe_accepts_normal(self):
        """Username normal accepte."""
        result = validate_username_safe("jean.dupont")
        assert result == "jean.dupont"

    def test_username_safe_rejects_sql(self):
        """Username avec SQL injection rejete."""
        with pytest.raises(ValueError):
            validate_username_safe("admin' OR 1=1--")

    def test_path_safe_rejects_traversal(self):
        """Path avec traversal rejete."""
        with pytest.raises(ValueError):
            validate_path_safe("../etc/passwd")

    def test_path_safe_accepts_normal(self):
        """Path normal accepte."""
        result = validate_path_safe("uploads/photo.jpg")
        assert result == "uploads/photo.jpg"


# ===================================================================
# Fix M16 : pas de validate_password_safe
# ===================================================================

class TestFixM16:
    """Fix M16 : verify que validate_password_safe n'existe pas."""

    def test_no_validate_password_safe(self):
        """Le module ne contient PAS validate_password_safe."""
        from app.core import validators
        assert not hasattr(validators, "validate_password_safe")

    def test_password_with_special_chars_not_blocked(self):
        """Les passwords complexes ne doivent PAS etre bloques par les validators.

        Si quelqu'un utilise validate_safe_string sur un password (ce qu'on
        ne devrait pas faire), les caracteres speciaux comme ' et " sont
        acceptes grace au fix M5.
        """
        # Un password complexe est accepte par validate_safe_string
        password = "P@$$w0rd'with\"special;chars!"
        result = SecurityValidators.validate_safe_string(password, "test")
        assert result == password
