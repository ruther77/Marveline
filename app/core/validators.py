"""Validators de securite pour prevenir injections et attaques.

Utilises dans les schemas Pydantic pour rejeter les inputs dangereux
AVANT qu'ils n'atteignent la couche business/database.

Corrections vs ancien CaroCorp :
- Fix M5 : l'apostrophe n'est plus bloquee (accepte "O'Brien", "l'Ile")
- Fix M16 : pas de validation SQL/XSS sur passwords (hashes, jamais affiches)
- Philosophie : les parameterized queries (SQLAlchemy) sont la protection
  SQL principale. Ces validators sont une defense supplementaire (defense
  en profondeur), pas la seule ligne de defense.
- Approche patterns complets au lieu de char blacklist pour SQL.

Protections :
- SQL Injection (patterns seulement, pas de char blacklist)
- XSS (Cross-Site Scripting)
- Path Traversal
"""

import re
from typing import Optional


class SecurityValidators:
    """Validators de securite reutilisables pour Pydantic.

    Usage dans un schema Pydantic :
        from pydantic import field_validator
        from app.core.validators import SecurityValidators

        class MySchema(BaseModel):
            name: str

            @field_validator('name')
            @classmethod
            def validate_name(cls, v: str) -> str:
                return SecurityValidators.validate_safe_string(v, 'name')
    """

    # -----------------------------------------------------------------------
    # Patterns SQL injection (case-insensitive)
    # Note : PAS de char blacklist (fix M5). On detecte uniquement les
    # patterns complets d'attaque. L'apostrophe seule est autorisee.
    # -----------------------------------------------------------------------

    SQL_INJECTION_PATTERNS = [
        r"(\bor\b|\band\b)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?",  # OR 1=1, AND 1=1
        r"union\s+(all\s+)?select",                                      # UNION SELECT
        r";\s*drop\s+(table|database)",                                  # ; DROP TABLE
        r";\s*delete\s+from",                                            # ; DELETE FROM
        r";\s*update\s+\w+\s+set",                                      # ; UPDATE ... SET
        r";\s*insert\s+into",                                            # ; INSERT INTO
        r";\s*alter\s+table",                                            # ; ALTER TABLE
        r";\s*create\s+(table|database)",                                # ; CREATE TABLE
        r"\bexec\s*\(",                                                  # EXEC(
        r"\bexecute\s*\(",                                               # EXECUTE(
        r"'\s*;\s*--",                                                   # '; --
        r"'\s*or\s+'",                                                   # ' OR '
        r"--\s*$",                                                       # commentaire SQL en fin
        r"/\*.*?\*/",                                                    # commentaire /* */
        r"\bwaitfor\s+delay",                                            # WAITFOR DELAY (time-based)
        r"\bbenchmark\s*\(",                                             # BENCHMARK( (MySQL)
        r"\bsleep\s*\(",                                                 # SLEEP( (MySQL)
        r"information_schema",                                           # information_schema
        r"\bload_file\s*\(",                                             # LOAD_FILE(
        r"\binto\s+(out|dump)file",                                      # INTO OUTFILE
    ]

    # -----------------------------------------------------------------------
    # Patterns XSS (Cross-Site Scripting)
    # -----------------------------------------------------------------------

    XSS_PATTERNS = [
        r"<\s*script[^>]*>",           # <script>
        r"<\s*/\s*script\s*>",         # </script>
        r"<\s*iframe[^>]*>",           # <iframe>
        r"<\s*embed[^>]*>",            # <embed>
        r"<\s*object[^>]*>",           # <object>
        r"<\s*svg[^>]*on\w+\s*=",      # <svg onload=
        r"<\s*img[^>]*on\w+\s*=",      # <img onerror=
        r"javascript\s*:",             # javascript:
        r"vbscript\s*:",               # vbscript:
        r"on\w+\s*=\s*[\"']",          # onclick="...", onerror='...'
        r"data\s*:\s*text/html",        # data:text/html
        r"<\s*meta[^>]*http-equiv",    # <meta http-equiv=
    ]

    # -----------------------------------------------------------------------
    # Patterns Path Traversal
    # -----------------------------------------------------------------------

    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",           # ../
        r"\.\.\\",          # ..\
        r"%2e%2e[/\\%]",    # URL encoded ../
        r"\.\.%2f",         # ..%2f
        r"%2e%2e%2f",       # %2e%2e%2f
    ]

    @staticmethod
    def validate_no_sql_injection(value: str, field_name: str = "field") -> str:
        """Valide qu'une string ne contient pas de patterns SQL injection.

        Contrairement a l'ancien code, ne bloque PAS les caracteres isoles
        comme l'apostrophe (fix M5). Detecte uniquement les patterns complets.

        Args:
            value: Valeur a valider.
            field_name: Nom du champ (pour message d'erreur).

        Returns:
            La valeur si valide.

        Raises:
            ValueError: Si un pattern SQL injection est detecte.
        """
        if not isinstance(value, str):
            return value

        for pattern in SecurityValidators.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValueError(
                    f"Invalid {field_name}: contains potentially malicious SQL pattern. "
                    f"Please use only safe characters."
                )

        return value

    @staticmethod
    def validate_no_xss(value: str, field_name: str = "field") -> str:
        """Valide qu'une string ne contient pas de patterns XSS.

        Args:
            value: Valeur a valider.
            field_name: Nom du champ (pour message d'erreur).

        Returns:
            La valeur si valide.

        Raises:
            ValueError: Si un pattern XSS est detecte.
        """
        if not isinstance(value, str):
            return value

        for pattern in SecurityValidators.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValueError(
                    f"Invalid {field_name}: contains potentially malicious HTML/script content. "
                    f"HTML tags and script code are not allowed."
                )

        return value

    @staticmethod
    def validate_no_path_traversal(value: str, field_name: str = "field") -> str:
        """Valide qu'une string ne contient pas de patterns path traversal.

        Args:
            value: Valeur a valider.
            field_name: Nom du champ (pour message d'erreur).

        Returns:
            La valeur si valide.

        Raises:
            ValueError: Si un pattern path traversal est detecte.
        """
        if not isinstance(value, str):
            return value

        for pattern in SecurityValidators.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValueError(
                    f"Invalid {field_name}: contains path traversal pattern. "
                    f"Relative paths with '..' are not allowed."
                )

        return value

    @staticmethod
    def validate_safe_string(
        value: str,
        field_name: str = "field",
        check_sql: bool = True,
        check_xss: bool = True,
        check_path: bool = False,
    ) -> str:
        """Validation combinee pour une string securisee.

        Args:
            value: Valeur a valider.
            field_name: Nom du champ (pour message d'erreur).
            check_sql: Verifier SQL injection (defaut: True).
            check_xss: Verifier XSS (defaut: True).
            check_path: Verifier path traversal (defaut: False).

        Returns:
            La valeur si valide.

        Raises:
            ValueError: Si un pattern malveillant est detecte.
        """
        if not isinstance(value, str):
            return value

        if check_sql:
            SecurityValidators.validate_no_sql_injection(value, field_name)

        if check_xss:
            SecurityValidators.validate_no_xss(value, field_name)

        if check_path:
            SecurityValidators.validate_no_path_traversal(value, field_name)

        return value

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize une string (version permissive — strip HTML tags).

        Moins securise que validate_* car modifie silencieusement l'input.
        Preferer validate_* qui rejettent.

        Contrairement a l'ancien code, ne retire PAS les apostrophes/guillemets
        isoles (fix M5). Retire uniquement les tags HTML et caracteres de controle.

        Args:
            value: Valeur a sanitizer.
            max_length: Longueur maximale (defaut: 1000).

        Returns:
            La valeur sanitizee.
        """
        if not isinstance(value, str):
            return value

        # Limiter longueur
        value = value[:max_length]

        # Retirer HTML tags
        value = re.sub(r"<[^>]*>", "", value)

        # Retirer caracteres de controle (sauf newline, tab, carriage return)
        value = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", value)

        return value.strip()


# ---------------------------------------------------------------------------
# Fonctions Pydantic validators
# ---------------------------------------------------------------------------


def validate_email_safe(value: str) -> str:
    """Validator Pydantic pour email (anti-SQL/XSS).

    Usage :
        @field_validator('email')
        @classmethod
        def check_email(cls, v: str) -> str:
            return validate_email_safe(v)
    """
    return SecurityValidators.validate_safe_string(
        value,
        field_name="email",
        check_sql=True,
        check_xss=True,
        check_path=False,
    )


def validate_text_safe(value: str) -> str:
    """Validator Pydantic pour texte generique (anti-SQL/XSS)."""
    return SecurityValidators.validate_safe_string(
        value,
        field_name="text",
        check_sql=True,
        check_xss=True,
        check_path=False,
    )


def validate_username_safe(value: str) -> str:
    """Validator Pydantic pour username (anti-SQL/XSS)."""
    return SecurityValidators.validate_safe_string(
        value,
        field_name="username",
        check_sql=True,
        check_xss=True,
        check_path=False,
    )


def validate_path_safe(value: str) -> str:
    """Validator Pydantic pour chemins de fichiers (anti-SQL/XSS/path traversal)."""
    return SecurityValidators.validate_safe_string(
        value,
        field_name="path",
        check_sql=True,
        check_xss=True,
        check_path=True,
    )


# Note : PAS de validate_password_safe (fix M16).
# Les passwords sont hashes par bcrypt et jamais affiches.
# La validation SQL/XSS sur passwords est inutile et nuit a l'UX
# (bloque les passwords contenant des apostrophes, guillemets, etc.).
