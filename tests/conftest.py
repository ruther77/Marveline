"""Configuration pytest pour les tests CaroCorp."""
import asyncio
import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from fastapi.testclient import TestClient

from app.main import app
from app.models.base import Base
from app.models.account import Account
from app.models.tenant_membership import TenantMembership
from app.models.tenant import Tenant as TenantModel
from app.models.auth_role import AuthRole
from app.core.deps import UserCompat
from app.core.database import get_db, get_async_db
from app.core.config import settings
from app.core.security import get_password_hash, create_access_token, decode_token
from app.middleware.security import CSRFProtectionMiddleware


# Database de test — priorité aux variables exportées, sinon reprendre la config
# applicative qui charge déjà `.env`.
_base_url = os.environ.get("DATABASE_URL") or settings.DATABASE_URL
# Remplacer le nom de la DB par CaroCorp_test pour isolation
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    _base_url.rsplit("/", 1)[0] + "/CaroCorp_test"
)
TEST_DATABASE_NAME = TEST_DATABASE_URL.rsplit("/", 1)[1]
# URL async pour les endpoints qui utilisent get_async_db (asyncpg driver)
ASYNC_TEST_DATABASE_URL = TEST_DATABASE_URL.replace(
    "postgresql+psycopg2://", "postgresql+asyncpg://"
)


def ensure_test_db_exists():
    """Crée la DB CaroCorp_test si elle n'existe pas encore."""
    base_engine = create_engine(_base_url, isolation_level="AUTOCOMMIT")
    try:
        with base_engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": TEST_DATABASE_NAME},
            )
            if not result.fetchone():
                conn.execute(text(f'CREATE DATABASE "{TEST_DATABASE_NAME}"'))
    finally:
        base_engine.dispose()


def _reset_schema(engine):
    """Réinitialise le schéma public (gère les FK circulaires entre tables).

    Ne termine pas les autres backends ici: forcer pg_terminate_backend au setup
    peut tuer des connexions encore en phase de nettoyage et rendre le cluster
    instable (OperationalError: server closed the connection unexpectedly).
    """
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO PUBLIC"))
        conn.commit()


@pytest.fixture(scope="session")
def test_engine():
    """Engine de test pour la session — état propre garanti.

    NullPool : évite les connexions poolées qui peuvent garder des verrous
    et bloquer les TRUNCATE / DROP SCHEMA entre les runs de tests.

    Le teardown ne détruit PAS le schéma : supprimer les tables en fin de session
    peut causer des "relation does not exist" sur des tests encore en cours
    d'initialisation dans d'autres modules. Le prochain setup (run suivant)
    fera le clean slate via _reset_schema().
    """
    from sqlalchemy.pool import NullPool
    ensure_test_db_exists()
    engine = create_engine(TEST_DATABASE_URL, poolclass=NullPool)
    _reset_schema(engine)               # Clean slate au démarrage uniquement
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()                    # Libère les connexions, ne détruit pas les tables


@pytest.fixture(scope="function")
def async_test_engine():
    """Engine async isolé par test pour éviter les fuites cross-event-loop."""
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture(scope="function")
def test_db(test_engine, clean_db):
    """Session sync pour chaque test — commits réels (pas de SAVEPOINT).

    Les données committées via test_db.commit() sont visibles par les sessions
    async (override_get_async_db / asyncpg, connexion physique séparée).
    L'isolation entre tests est assurée par clean_db (autouse=True) qui truncate
    AVANT et APRÈS chaque test, AVANT que test_db (et les fixtures de données)
    ne soient créés — garantit l'ordre correct.
    """
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


async def _truncate_all_business_tables(engine) -> None:
    """Truncate toutes les tables métier pour isolation entre tests.

    Appelé par clean_db (autouse=True) AVANT et APRÈS chaque test.
    """
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename != 'alembic_version' "
            "ORDER BY tablename"
        ))
        tables = [row[0] for row in result.fetchall()]
        if tables:
            await conn.execute(text(
                f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"
            ))
        await conn.commit()


def _truncate_all_sync(engine) -> None:
    """Truncate sync via psycopg2 — sans dépendance asyncio.

    Termine d'abord les connexions asyncpg résiduelles (laissées par TestClient
    lors de l'arrêt des coroutines) pour éviter que le TRUNCATE bloque sur un
    verrou posé par une connexion zombie.

    INFRA-TESTDB-01 : le TRUNCATE peut rater sporadiquement avec UndefinedTable
    si une table est droppée entre le SELECT pg_tables et le TRUNCATE (race avec
    _reset_schema d'un autre event-loop). On catch et retry une fois.
    """
    from psycopg2.errors import UndefinedTable

    with engine.connect() as conn:
        conn.execute(text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid != pg_backend_pid()"
        ))
        conn.execute(text("SET lock_timeout = '5s'"))
        result = conn.execute(text(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename != 'alembic_version' "
            "ORDER BY tablename"
        ))
        tables = [row[0] for row in result.fetchall()]
        if tables:
            try:
                conn.execute(text(
                    f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"
                ))
            except Exception:
                conn.rollback()
                result2 = conn.execute(text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename != 'alembic_version' "
                    "ORDER BY tablename"
                ))
                tables2 = [row[0] for row in result2.fetchall()]
                if tables2:
                    conn.execute(text(
                        f"TRUNCATE {', '.join(tables2)} RESTART IDENTITY CASCADE"
                    ))
        conn.commit()


@pytest.fixture(scope="function", autouse=True)
def clean_db(test_engine):
    """Purge toutes les tables avant ET après chaque test.

    autouse=True garantit que le truncate s'exécute EN PREMIER, avant toute
    fixture de données. test_db en dépend explicitement pour forcer l'ordre :
    clean_db (truncate) → test_db → fixtures locales (insèrent) → test → teardown.

    Utilise le test_engine SYNC (psycopg2) pour éviter tout conflit asyncio/event loop
    avec pytest-asyncio 0.24 (mode AUTO).
    """
    _truncate_all_sync(test_engine)
    yield
    _truncate_all_sync(test_engine)


@pytest.fixture(scope="function")
def client(test_db, async_test_engine):
    """Client de test FastAPI — override get_db (sync) ET get_async_db (async).

    L'isolation entre tests est assurée par clean_db (autouse=True) :
    truncate AVANT (setup) et APRÈS (teardown) chaque test.
    """
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    AsyncTestSession = async_sessionmaker(
        async_test_engine, class_=AsyncSession, expire_on_commit=False
    )
    from app.core import database as db_module
    original_async_engine = db_module.async_engine
    original_async_session_local = db_module.AsyncSessionLocal
    db_module.async_engine = async_test_engine
    db_module.AsyncSessionLocal = AsyncTestSession

    async def override_get_async_db():
        session = AsyncTestSession()
        try:
            yield session
        finally:
            if session.in_transaction():
                await session.rollback()
            await session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_async_db] = override_get_async_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        db_module.AsyncSessionLocal = original_async_session_local
        db_module.async_engine = original_async_engine


@pytest.fixture(autouse=True)
def cleanup_redis_between_tests():
    """Nettoie toutes les clés Redis-SEC entre chaque test pour éviter le flaky.

    Patterns alignés sur app/constants/security.py §RedisKeys.
    Utilise un client Redis synchrone (redis.from_url) car cette fixture est sync.
    redis_client.client est AsyncRedis (scan_iter = async generator, non itérable ici).
    """
    import redis as _sync_redis

    r = _sync_redis.from_url(settings.REDIS_SEC_URL, decode_responses=True)
    r_cache = _sync_redis.from_url(settings.REDIS_CACHE_URL, decode_responses=True)
    patterns = [
        # Rate limiting
        "rate_limit:*",
        # Tokens auth (préfixes v3 exacts)
        "whitelist:refresh:*",
        "blacklist:jti:*",
        "jti:meta:*",
        "family:*",
        # Sessions
        "session:*",
        "user_sessions_index:*",
        # Brute force (brute:* couvre user, ip et device)
        "brute:*",
        "bf_lock:*",
        "bf_alert:*",
        # Credential stuffing global
        "credential_stuffing:*",
        "captcha:*",
        "login:*",
        # MFA / TOTP
        "mfa_session:*",
        "stepup:*",
        "totp:used:*",
        # CSRF
        "csrf:*",
        # Password reset
        "pwd_reset:*",
        "pwd_reset_rate:*",
    ]

    from app.core.redis import redis_sec, redis_cache

    def _reset_redis_singletons() -> None:
        # Chaque test a son propre event loop anyio; ne pas réutiliser un client lié
        # à une loop fermée.
        redis_sec._client = None
        redis_cache._client = None

    def _flush():
        for pattern in patterns:
            keys = list(r.scan_iter(pattern))
            if keys:
                r.delete(*keys)
        # Important pour l'isolation tests: évite le stale cache ORM entre tests
        # quand les IDs sont réutilisés (TRUNCATE ... RESTART IDENTITY).
        r_cache.flushdb()

    _reset_redis_singletons()
    _flush()
    yield
    _flush()
    _reset_redis_singletons()


@pytest.fixture
def test_tenant():
    """Tenant de test (tenant_id=1).

    Notes:
        - CaroCorp n'a pas de table tenants séparée
        - tenant_id est juste une colonne BigInteger
        - Cette fixture retourne un objet simple avec .id pour compatibilité
    """
    class Tenant:
        def __init__(self, id: int):
            self.id = id

    return Tenant(id=1)


@pytest.fixture
def test_tenant2():
    """Tenant de test alternatif (tenant_id=2) pour tests anti-cross-tenant."""
    class Tenant:
        def __init__(self, id: int):
            self.id = id

    return Tenant(id=2)


@pytest.fixture
def csrf_token():
    """Token CSRF valide pour les tests (≥32 chars).

    NOTE: Ce token n'est PAS stocké dans Redis automatiquement.
    Utiliser csrf_token_for_user() pour tests integration avec Redis.
    """
    return CSRFProtectionMiddleware.generate_csrf_token()


def csrf_token_for_user(user_id: int, session_id: str | None = None) -> str:
    """Helper pour générer ET stocker un token CSRF dans Redis.

    Args:
        user_id: ID de l'utilisateur (conservé pour backward compat signature)
        session_id: claim 'sid' du JWT (spec §04 §4.3). Si None, génère un UUID
                    aléatoire (les JWTs sans 'sid' → middleware skip CSRF).

    Returns:
        Token CSRF valide stocké dans Redis sous csrf:{session_id}
    """
    import redis as _sync_redis
    import secrets

    sid = session_id if session_id is not None else str(uuid.uuid4())
    csrf_token = secrets.token_urlsafe(32)
    # Client Redis sync — redis_client.client est AsyncRedis (non compatible avec fixture sync)
    r = _sync_redis.from_url(settings.REDIS_SEC_URL, decode_responses=True)
    r.setex(f"csrf:{sid}", 900, csrf_token)
    return csrf_token


@pytest.fixture
def auth_headers(csrf_token):
    """Headers d'authentification pour les tests (token fake, deprecated)."""
    # TODO: Générer un vrai token JWT
    return {
        "Authorization": "Bearer test_token",
        "X-CSRF-Token": csrf_token,
    }


@pytest.fixture
def test_tenant_record(test_db):
    """Tenant de test persisté en DB (id=1 après RESTART IDENTITY).

    Requis par TenantMembership.tenant_id FK → tenants.id.
    """
    tenant = TenantModel(
        external_id=str(uuid.uuid4()),
        name="Test Tenant",
        domain="test.carocorp.local",
        contact_email="ops@test.carocorp.local",
        app_code="marveline",
        status="active",
        is_active=True,
    )
    test_db.add(tenant)
    test_db.commit()
    test_db.refresh(tenant)
    return tenant


@pytest.fixture
def test_tenant_record2(test_db, test_tenant_record):
    """2ème Tenant de test persisté en DB (id=2).

    Dépend de test_tenant_record pour garantir que tenant 1 est créé avant tenant 2.
    Requis par tests anti-cross-tenant.
    """
    tenant = TenantModel(
        external_id=str(uuid.uuid4()),
        name="Test Tenant 2",
        domain="test2.carocorp.local",
        contact_email="ops@test2.carocorp.local",
        app_code="epicerie",
        status="active",
        is_active=True,
    )
    test_db.add(tenant)
    test_db.commit()
    test_db.refresh(tenant)
    return tenant


@pytest.fixture
def _role_staff(test_db):
    """AuthRole 'staff' — créé en DB pour les TenantMembership FK."""
    from sqlalchemy import select as _select
    existing = test_db.execute(_select(AuthRole).filter(AuthRole.name == "staff")).scalars().first()
    if existing:
        return existing
    role = AuthRole(name="staff", level=4, is_system=False, mfa_required=False, description="Staff role")
    test_db.add(role)
    test_db.commit()
    return role


@pytest.fixture
def _role_admin(test_db):
    """AuthRole 'admin' — créé en DB pour les TenantMembership FK."""
    from sqlalchemy import select as _select
    existing = test_db.execute(_select(AuthRole).filter(AuthRole.name == "admin")).scalars().first()
    if existing:
        return existing
    role = AuthRole(name="admin", level=2, is_system=False, mfa_required=False, description="Admin role")
    test_db.add(role)
    test_db.commit()
    return role


@pytest.fixture
def _role_manager(test_db):
    """AuthRole 'manager' — créé en DB pour les TenantMembership FK."""
    from sqlalchemy import select as _select
    existing = test_db.execute(_select(AuthRole).filter(AuthRole.name == "manager")).scalars().first()
    if existing:
        return existing
    role = AuthRole(name="manager", level=3, is_system=False, mfa_required=False, description="Manager role")
    test_db.add(role)
    test_db.commit()
    return role


# ── GOTCHA:IAM:03 — flush() vs commit() avec double moteur ────────────────────
# Les fixtures IAM v2 utilisent le pattern flush() → commit() obligatoire.
# `test_db` (psycopg2 sync) et `async_test_engine` (asyncpg) sont deux connexions
# physiques distinctes. Un flush() sans commit() sur test_db n'est PAS visible
# par l'async engine qui consulte la DB via sa propre connexion.
# Règle : toujours terminer par test_db.commit() avant d'appeler un endpoint via client.
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def test_user(test_db, test_tenant_record, _role_staff):
    """Utilisateur de test — IAM v2 : Account + TenantMembership (tenant 1, staff).

    Retourne UserCompat (drop-in replacement pour l'ancien User).
    Attributs compatibles : .id, .email, .role, .tenant_id, .first_name, .last_name, .is_active
    """
    account = Account(
        email="test@carocorp.com",
        hashed_password=get_password_hash("testpass123"),
        first_name="Test",
        last_name="User",
        is_active=True,
    )
    test_db.add(account)
    test_db.flush()
    membership = TenantMembership(
        account_id=account.id,
        tenant_id=test_tenant_record.id,
        role_name="staff",
        status="active",
    )
    test_db.add(membership)
    test_db.commit()
    test_db.refresh(account)
    test_db.refresh(membership)
    return UserCompat(account=account, membership=membership)


@pytest.fixture
def test_admin(test_db, test_tenant_record, _role_admin):
    """Utilisateur admin de test — IAM v2 : Account + TenantMembership (tenant 1, admin).

    Retourne UserCompat (drop-in replacement pour l'ancien User admin).
    """
    account = Account(
        email="admin@carocorp.com",
        hashed_password=get_password_hash("admin123"),
        first_name="Admin",
        last_name="User",
        is_active=True,
    )
    test_db.add(account)
    test_db.flush()
    membership = TenantMembership(
        account_id=account.id,
        tenant_id=test_tenant_record.id,
        role_name="admin",
        status="active",
    )
    test_db.add(membership)
    test_db.commit()
    test_db.refresh(account)
    test_db.refresh(membership)
    return UserCompat(account=account, membership=membership)


@pytest.fixture
def test_user_tenant2(test_db, test_tenant_record2, _role_staff):
    """Utilisateur de test pour tenant 2 — IAM v2 (tests anti-cross-tenant).

    Retourne UserCompat avec tenant_id = test_tenant_record2.id.
    """
    account = Account(
        email="test@tenant2.com",
        hashed_password=get_password_hash("testpass123"),
        first_name="Tenant 2",
        last_name="User",
        is_active=True,
    )
    test_db.add(account)
    test_db.flush()
    membership = TenantMembership(
        account_id=account.id,
        tenant_id=test_tenant_record2.id,
        role_name="staff",
        status="active",
    )
    test_db.add(membership)
    test_db.commit()
    test_db.refresh(account)
    test_db.refresh(membership)
    return UserCompat(account=account, membership=membership)


@pytest.fixture
def test_admin_tenant2(test_db, test_tenant_record2, _role_admin):
    """Utilisateur admin pour tenant 2 — IAM v2 (tests anti-cross-tenant).

    Retourne UserCompat avec tenant_id = test_tenant_record2.id.
    """
    account = Account(
        email="admin@tenant2.com",
        hashed_password=get_password_hash("admin123"),
        first_name="Admin",
        last_name="Tenant 2",
        is_active=True,
    )
    test_db.add(account)
    test_db.flush()
    membership = TenantMembership(
        account_id=account.id,
        tenant_id=test_tenant_record2.id,
        role_name="admin",
        status="active",
    )
    test_db.add(membership)
    test_db.commit()
    test_db.refresh(account)
    test_db.refresh(membership)
    return UserCompat(account=account, membership=membership)


@pytest.fixture
def auth_token(test_user):
    """Token JWT valide pour test_user (avec claim 'sid' pour CSRF §04 §4.3)."""
    claims = {
        "sub": test_user.id,
        "tid": str(test_user.tenant_id),
        "email": test_user.email,
        "role": test_user.role,
        "sid": str(uuid.uuid4()),
    }
    return create_access_token(claims)


@pytest.fixture
def auth_token_admin(test_admin):
    """Token JWT valide pour test_admin (avec claim 'sid' pour CSRF §04 §4.3)."""
    claims = {
        "sub": test_admin.id,
        "tid": str(test_admin.tenant_id),
        "email": test_admin.email,
        "role": test_admin.role,
        "sid": str(uuid.uuid4()),
    }
    return create_access_token(claims)


@pytest.fixture
def auth_token_tenant2(test_user_tenant2):
    """Token JWT valide pour test_user_tenant2 (avec claim 'sid' pour CSRF §04 §4.3)."""
    claims = {
        "sub": test_user_tenant2.id,
        "tid": str(test_user_tenant2.tenant_id),
        "email": test_user_tenant2.email,
        "role": test_user_tenant2.role,
        "sid": str(uuid.uuid4()),
    }
    return create_access_token(claims)


@pytest.fixture
def auth_token_admin_tenant2(test_admin_tenant2):
    """Token JWT valide pour test_admin_tenant2 (avec claim 'sid' pour CSRF §04 §4.3)."""
    claims = {
        "sub": test_admin_tenant2.id,
        "tid": str(test_admin_tenant2.tenant_id),
        "email": test_admin_tenant2.email,
        "role": test_admin_tenant2.role,
        "sid": str(uuid.uuid4()),
    }
    return create_access_token(claims)


@pytest.fixture
def auth_headers_real(test_user, auth_token):
    """Headers d'authentification avec vrai token JWT (test_user, tenant_id=1).

    Génère ET stocke le token CSRF dans Redis lié au claim 'sid' du JWT (§04 §4.3).
    """
    sid = decode_token(auth_token).get("sid")
    csrf_token = csrf_token_for_user(test_user.id, session_id=sid)
    return {
        "Authorization": f"Bearer {auth_token}",
        "X-CSRF-Token": csrf_token,
    }


@pytest.fixture
def auth_headers_admin(test_admin, auth_token_admin):
    """Headers d'authentification avec vrai token JWT admin.

    Génère ET stocke le token CSRF dans Redis lié au claim 'sid' du JWT (§04 §4.3).
    """
    sid = decode_token(auth_token_admin).get("sid")
    csrf_token = csrf_token_for_user(test_admin.id, session_id=sid)
    return {
        "Authorization": f"Bearer {auth_token_admin}",
        "X-CSRF-Token": csrf_token,
    }


@pytest.fixture
def auth_headers_tenant2(test_user_tenant2, auth_token_tenant2):
    """Headers d'authentification pour tenant_id=2 (tests anti-cross-tenant).

    Génère ET stocke le token CSRF dans Redis lié au claim 'sid' du JWT (§04 §4.3).
    """
    sid = decode_token(auth_token_tenant2).get("sid")
    csrf_token = csrf_token_for_user(test_user_tenant2.id, session_id=sid)
    return {
        "Authorization": f"Bearer {auth_token_tenant2}",
        "X-CSRF-Token": csrf_token,
    }


@pytest.fixture
def auth_headers_admin_tenant2(test_admin_tenant2, auth_token_admin_tenant2):
    """Headers d'authentification admin pour tenant_id=2 (tests anti-cross-tenant).

    Génère ET stocke le token CSRF dans Redis lié au claim 'sid' du JWT (§04 §4.3).
    """
    sid = decode_token(auth_token_admin_tenant2).get("sid")
    csrf_token = csrf_token_for_user(test_admin_tenant2.id, session_id=sid)
    return {
        "Authorization": f"Bearer {auth_token_admin_tenant2}",
        "X-CSRF-Token": csrf_token,
    }
