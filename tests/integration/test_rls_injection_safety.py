"""Tests intégration — F01 RLS f-string → set_config paramétré (B1.S1.T1).

Couvre la friction F01 (cf. `01-core-foundations.md` §F01 ligne 244) :
  - Avant fix : `cursor.execute(f"SET LOCAL app.current_tenant_id = '{tid}'")`
    → injection SQL possible si caller oublie cast int côté deps.py.
  - Après fix : `conn.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(int(tid))})`
    → impossible d'injecter (param lié + cast int defense-in-depth).

Tests :
  1. Injection payload string non-castable → cast int échoue, fonction retourne
     sans SET, table cible NON-droppée (defense-in-depth holds).
  2. tenant_id int valide → set_config bien appelé, current_setting retourne la
     valeur attendue.
  3. tenant_id None → no-op (comportement nominal hors contexte tenant).
  4. Audit pré-merge : 0 f-string SQL dans app/core/.

NOTE : ces tests ne dépendent PAS de RLS enabled (B1.S2). Ils valident
uniquement la sécurité du SET de la variable de session.
"""
import re
from pathlib import Path

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import (
    _current_tenant_id,
    _inject_rls_tenant,
    clear_tenant_context,
    set_tenant_context,
)

from tests.conftest import ASYNC_TEST_DATABASE_URL


@pytest.fixture
async def async_db(test_engine):
    """Session async avec listener 'begin' attaché — réplique exacte du listener
    production `_inject_rls_tenant` pour test isolé.

    Le listener prod est bindé à `async_engine.sync_engine` (engine global).
    Notre engine test est une instance distincte → on attache la même fonction
    pour exécuter le code prod identique sur un engine local.
    """
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    event.listen(engine.sync_engine, "before_cursor_execute", _inject_rls_tenant)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
    event.remove(engine.sync_engine, "before_cursor_execute", _inject_rls_tenant)
    await engine.dispose()


# ── F01 — sécurité paramétrisation ───────────────────────────────────────────


class TestRLSInjectionSafety:
    @pytest.mark.asyncio
    async def test_injection_payload_string_safe_table_not_dropped(
        self, async_db: AsyncSession
    ):
        """F01 : payload malveillant non-castable en int → SET LOCAL skip, table sûre."""
        malicious_payload = "1; DROP TABLE customers; --"
        token = _current_tenant_id.set(malicious_payload)
        try:
            # Force le déclenchement du listener 'begin' via une vraie requête SQL.
            # Le cast int() côté listener doit échouer silencieusement (log error).
            await async_db.execute(text("SELECT 1"))
            await async_db.commit()
        finally:
            _current_tenant_id.reset(token)

        # Vérification critique : la table customers existe toujours.
        result = await async_db.execute(text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'customers'"
        ))
        assert result.scalar() == 1, (
            "F01 régression CRITIQUE : table customers droppée par injection SQL"
        )

    @pytest.mark.asyncio
    async def test_valid_int_tenant_id_set_correctly(self, async_db: AsyncSession):
        """tenant_id int valide → current_setting retourne la valeur."""
        token = _current_tenant_id.set(42)
        try:
            await async_db.execute(text("SELECT 1"))  # trigger begin event
            result = await async_db.execute(text(
                "SELECT current_setting('app.current_tenant_id', true)"
            ))
            value = result.scalar()
            assert value == "42", f"Expected '42', got {value!r}"
        finally:
            _current_tenant_id.reset(token)

    @pytest.mark.asyncio
    async def test_none_tenant_context_noop(self, async_db: AsyncSession):
        """tenant_id None → SET LOCAL skip (nominal hors contexte tenant)."""
        clear_tenant_context()
        await async_db.execute(text("SELECT 1"))
        result = await async_db.execute(text(
            "SELECT current_setting('app.current_tenant_id', true)"
        ))
        # current_setting('...', true) retourne '' si pas défini (missing_ok=true)
        value = result.scalar()
        assert value in ("", None), f"Expected unset, got {value!r}"

    @pytest.mark.asyncio
    async def test_int_castable_string_accepted(self, async_db: AsyncSession):
        """tenant_id passé comme string '7' (castable int) → set_config OK."""
        token = _current_tenant_id.set("7")
        try:
            await async_db.execute(text("SELECT 1"))
            result = await async_db.execute(text(
                "SELECT current_setting('app.current_tenant_id', true)"
            ))
            assert result.scalar() == "7"
        finally:
            _current_tenant_id.reset(token)

    @pytest.mark.asyncio
    async def test_set_tenant_context_after_first_query_applies_to_next(
        self, async_db: AsyncSession
    ):
        """Régression : pattern auth réel — set_tenant_context APRÈS la 1ère query.

        Reproduit le scénario _resolve_api_key_async :
          1. Query #1 (lookup ApiKey) : pas de tenant connu → contextvar None
          2. Tenant résolu → set_tenant_context(api_key.tenant_id)
          3. Query #2 (endpoint logic) : doit voir le contexte tenant set

        Avec event 'begin', ce 2ème query rate le set_config (TX déjà ouverte,
        begin ne re-fire pas). Avec 'before_cursor_execute', le hook re-fire
        et applique set_config sur la TX en cours. Test fail si on régresse
        vers 'begin'.
        """
        clear_tenant_context()
        await async_db.execute(text("SELECT 1"))

        token = _current_tenant_id.set(123)
        try:
            result = await async_db.execute(text(
                "SELECT current_setting('app.current_tenant_id', true)"
            ))
            assert result.scalar() == "123", (
                "F01 régression : set_tenant_context post-1ère-query non appliqué "
                "à la 2ème query de la même TX (event 'begin' au lieu de "
                "'before_cursor_execute' ?)"
            )
        finally:
            _current_tenant_id.reset(token)


class TestF01AuditFstringEradicated:
    """Garde-fou : empêche la régression de l'anti-pattern f-string SQL en core."""

    def test_no_fstring_sql_in_app_core(self):
        """Aucun f-string contenant SET/SELECT/INSERT/UPDATE/DELETE dans app/core/."""
        repo_root = Path(__file__).resolve().parents[2]
        core_dir = repo_root / "app" / "core"
        assert core_dir.is_dir(), f"app/core/ introuvable: {core_dir}"

        # Pattern : f-string littéral contenant un mot SQL réservé.
        # Tolère les usages légitimes en log/comment (non-SQL).
        sql_keywords = r"(\bSET\b|\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b)"
        fstring_sql_re = re.compile(rf'f["\'][^"\']*{sql_keywords}[^"\']*["\']')

        offending: list[tuple[Path, int, str]] = []
        for py_file in core_dir.rglob("*.py"):
            for lineno, line in enumerate(py_file.read_text().splitlines(), 1):
                # Ignore les logs (logger.warning/info/debug/error) qui ont des SET/SELECT
                # comme tokens humains, pas comme SQL exécuté.
                if "logger." in line:
                    continue
                if fstring_sql_re.search(line):
                    offending.append((py_file.relative_to(repo_root), lineno, line.strip()))

        assert not offending, (
            "F01 régression : f-string SQL détecté dans app/core/ — "
            "utiliser text() + bind ou exec_driver_sql avec params.\n"
            + "\n".join(f"  {p}:{l}: {s}" for p, l, s in offending)
        )
