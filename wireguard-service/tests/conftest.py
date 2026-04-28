"""Configuration pytest pour le microservice WireGuard.

Deux modes :
- LOCAL (pas de fastapi/sqlalchemy) : seuls les tests structurels tournent.
  Les fixtures DB/client sont marquees skip.
- DOCKER (tout installe) : fixtures DB SAVEPOINT + TestClient disponibles.

Fixtures :
- test_engine : Engine SQLAlchemy (session-scoped, tables wg)
- test_db : Session DB avec isolation SAVEPOINT (function-scoped)
- client : TestClient FastAPI avec DB override + auth bypass
- client_tenant2 : TestClient pour tenant_id=2 (tests anti-cross-tenant)
- internal_headers : Headers X-Internal-API-Key + X-Tenant-ID valides
- internal_headers_tenant2 : Headers pour tenant_id=2
"""

import os

import pytest

# Constantes toujours disponibles (meme sans fastapi)
VALID_INTERNAL_API_KEY = "CHANGE_ME_IN_PRODUCTION_MIN_32_CHARS"
TENANT_1 = 1
TENANT_2 = 2
ACTOR_1 = 100
ACTOR_2 = 200

# Imports conditionnels — ne pas casser les tests structurels en local
try:
    from sqlalchemy import create_engine, event, text
    from sqlalchemy.orm import sessionmaker
    from fastapi.testclient import TestClient
    from app.main import create_application
    from app.models.base import Base
    from app.models import WgPeer, WgIpPool, WgAuditLog  # noqa: F401
    from app.core.database import get_db
    from app.core.deps import get_internal_auth, InternalAuth

    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False

_requires_deps = pytest.mark.skipif(
    not _HAS_DEPS,
    reason="Requires fastapi/sqlalchemy (Docker only)",
)


def _skip_without_deps():
    """Skip la fixture si les deps ne sont pas installees."""
    if not _HAS_DEPS:
        pytest.skip("Requires fastapi/sqlalchemy (Docker only)")


# ── Database ──────────────────────────────────────────────────────────

if _HAS_DEPS:
    _base_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://caro:6L9dVl9hxpWylE8YQfNUNA@localhost:5433/CaroCorp",
    )
    TEST_DATABASE_URL = os.environ.get(
        "TEST_DATABASE_URL",
        _base_url.rsplit("/", 1)[0] + "/wg_test",
    )

    def ensure_test_db_exists():
        base_engine = create_engine(_base_url, isolation_level="AUTOCOMMIT")
        try:
            with base_engine.connect() as conn:
                result = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = 'wg_test'")
                )
                if not result.fetchone():
                    conn.execute(text("CREATE DATABASE wg_test"))
        finally:
            base_engine.dispose()

    def ensure_wg_schema(engine):
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS wg"))
            conn.execute(text("SET search_path TO wg, public"))
            conn.commit()


@pytest.fixture(scope="session")
def test_engine():
    """Engine de test — etat propre garanti."""
    _skip_without_deps()
    ensure_test_db_exists()
    engine = create_engine(TEST_DATABASE_URL)

    @event.listens_for(engine, "connect")
    def set_search_path(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("SET search_path TO wg, public")
        cursor.close()

    ensure_wg_schema(engine)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Session DB avec isolation SAVEPOINT."""
    _skip_without_deps()
    connection = test_engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    db = TestSession(bind=connection)

    nested = connection.begin_nested()

    @event.listens_for(db, "after_transaction_end")
    def restart_savepoint(session, transaction_context):
        nonlocal nested
        if transaction_context._parent is None and not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


# ── FastAPI TestClient ────────────────────────────────────────────────


@pytest.fixture(scope="function")
def client(test_db):
    """TestClient FastAPI avec DB override et auth interne mockee (tenant_id=1)."""
    _skip_without_deps()
    app = create_application()

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    def override_internal_auth():
        return InternalAuth(tenant_id=TENANT_1, actor_id=ACTOR_1)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_internal_auth] = override_internal_auth

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client_tenant2(test_db):
    """TestClient FastAPI pour tenant_id=2 (tests anti-cross-tenant)."""
    _skip_without_deps()
    app = create_application()

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    def override_internal_auth():
        return InternalAuth(tenant_id=TENANT_2, actor_id=ACTOR_2)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_internal_auth] = override_internal_auth

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ── Headers (toujours disponibles) ───────────────────────────────────


@pytest.fixture
def internal_headers():
    """Headers d'auth interne valides (tenant_id=1)."""
    return {
        "X-Internal-API-Key": VALID_INTERNAL_API_KEY,
        "X-Tenant-ID": str(TENANT_1),
        "X-Actor-ID": str(ACTOR_1),
    }


@pytest.fixture
def internal_headers_tenant2():
    """Headers d'auth interne pour tenant_id=2."""
    return {
        "X-Internal-API-Key": VALID_INTERNAL_API_KEY,
        "X-Tenant-ID": str(TENANT_2),
        "X-Actor-ID": str(ACTOR_2),
    }
