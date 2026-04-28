"""Conftest pour tests unitaires — pas de DB, Redis cleanup actif."""
import inspect
import pytest
from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.core.redis import redis_client


def pytest_collection_modifyitems(items):
    """Auto-marque @pytest.mark.asyncio sur tous les tests async sans marqueur.

    En pytest-asyncio 0.24.0 strict mode, @pytest.mark.asyncio sur une classe
    ne propage pas aux méthodes. Ce hook comble ce comportement pour les tests
    unitaires, équivalent à asyncio_mode="auto" mais localisé à tests/unit/.
    """
    for item in items:
        if hasattr(item, "obj") and inspect.iscoroutinefunction(item.obj):
            if item.get_closest_marker("asyncio") is None:
                item.add_marker(pytest.mark.asyncio)


def _truncate_all_tables_sync(engine) -> None:
    """TRUNCATE toutes les tables métier via engine sync (psycopg2, sans event loop)."""
    with engine.connect() as conn:
        result = conn.execute(_text(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename != 'alembic_version' "
            "ORDER BY tablename"
        ))
        tables = [row[0] for row in result.fetchall()]
        if tables:
            conn.execute(_text(
                f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"
            ))
        conn.commit()


@pytest.fixture(scope="function", autouse=True)
def clean_db(test_engine):
    """Surcharge sync de clean_db pour les tests unitaires.

    Utilise test_engine (psycopg2/sync) au lieu de asyncio.run() pour éviter
    le conflit RuntimeError "cannot run nested event loop" avec pytest-asyncio
    en mode strict (les tests async ont un event loop actif pendant clean_db).
    """
    _truncate_all_tables_sync(test_engine)
    yield
    _truncate_all_tables_sync(test_engine)


@pytest.fixture(autouse=True)
async def cleanup_redis_between_tests():
    """Nettoie les clés Redis entre chaque test unitaire (async — redis.asyncio)."""
    patterns = [
        "rate_limit:*", "refresh_wl:*", "access_bl:*", "token_family:*",
        "bf_email:*", "bf_ip:*", "bf_lock:*", "bf_alert:*",
        "session:*", "session_idx:*",
        "mfa_session:*",
        "pwd_reset:*", "pwd_reset_rate:*",
        "csrf:*",
        "whitelist:refresh:*", "blacklist:jti:*", "jti:meta:*", "family:*",
        "user_sessions_index:*", "brute:*", "stepup:*", "totp:used:*",
    ]

    async def _flush(patterns):
        try:
            for pattern in patterns:
                async for key in redis_client.client.scan_iter(pattern):
                    await redis_client.client.delete(key)
        except RuntimeError:
            # Event loop mismatch entre tests (asyncio_default_fixture_loop_scope=function)
            # Le singleton redis_client peut avoir des connexions liées à un ancien event loop.
            # La DB est nettoyée par clean_db (TRUNCATE), donc on peut ignorer cette erreur.
            pass

    await _flush(patterns)
    yield
    await _flush(patterns)


@pytest.fixture
async def async_db(async_test_engine):
    """Fixture AsyncSession pour les tests unitaires services async."""
    async_session = async_sessionmaker(async_test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
