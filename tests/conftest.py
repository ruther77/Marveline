"""Configuration pytest pour les tests CaroCorp."""
import os
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.models.base import Base
from app.models import User  # noqa: F401 — importe aussi tous les modèles pour Base.metadata.create_all()
from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_password_hash, create_access_token
from app.middleware.security import CSRFProtectionMiddleware


# Database de test — utilise DATABASE_URL de l'environnement (Docker: db:5432, host: localhost:5433)
_base_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://caro:6L9dVl9hxpWylE8YQfNUNA@localhost:5433/CaroCorp"
)
# Remplacer le nom de la DB par CaroCorp_test pour isolation
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    _base_url.rsplit("/", 1)[0] + "/CaroCorp_test"
)


def ensure_test_db_exists():
    """Crée la DB CaroCorp_test si elle n'existe pas encore."""
    base_engine = create_engine(_base_url, isolation_level="AUTOCOMMIT")
    try:
        with base_engine.connect() as conn:
            result = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = 'CaroCorp_test'"))
            if not result.fetchone():
                conn.execute(text('CREATE DATABASE "CaroCorp_test"'))
    finally:
        base_engine.dispose()


@pytest.fixture(scope="session")
def test_engine():
    """Engine de test pour la session — état propre garanti."""
    ensure_test_db_exists()
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(bind=engine)     # Clean slate (supprime état sale d'un run précédent)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Session de base de données pour chaque test avec isolation SAVEPOINT.

    Utilise une transaction imbriquée (SAVEPOINT) pour garantir que tous
    les commits pendant le test sont rollback à la fin du test.
    Cela assure une isolation complète entre les tests.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    db = TestSessionLocal(bind=connection)

    # Créer une nested transaction (SAVEPOINT)
    nested = connection.begin_nested()

    # Intercepter les commits pour restart automatiquement le SAVEPOINT
    @event.listens_for(db, "after_transaction_end")
    def restart_savepoint(session, transaction_context):
        """Recréer un SAVEPOINT après chaque commit."""
        nonlocal nested
        if transaction_context._parent is None and not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield db
    finally:
        db.close()
        # Rollback la transaction principale (annule tout)
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def client(test_db):
    """Client de test FastAPI."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def cleanup_redis_between_tests():
    """Nettoie rate_limit + token keys entre chaque test pour éviter le flaky."""
    from app.core.redis import redis_client
    patterns = [
        "rate_limit:*", "refresh_wl:*", "access_bl:*", "token_family:*",
        "bf_email:*", "bf_ip:*", "bf_lock:*", "bf_alert:*",
        "session:*", "session_idx:*",
        "mfa_session:*",
    ]
    for pattern in patterns:
        for key in redis_client.client.scan_iter(pattern):
            redis_client.client.delete(key)
    yield
    for pattern in patterns:
        for key in redis_client.client.scan_iter(pattern):
            redis_client.client.delete(key)


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


def csrf_token_for_user(user_id: int) -> str:
    """Helper pour générer ET stocker un token CSRF dans Redis pour un user.

    Args:
        user_id: ID de l'utilisateur

    Returns:
        Token CSRF valide stocké dans Redis
    """
    from app.core.redis import redis_client
    import secrets

    csrf_token = secrets.token_urlsafe(32)
    redis_client.store_csrf_token(
        user_id=user_id,
        token=csrf_token,
        ttl_seconds=900  # 15 minutes
    )
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
def test_user(test_db):
    """Utilisateur de test avec mot de passe 'testpass123'."""
    user = User(
        tenant_id=1,
        email="test@carocorp.com",
        hashed_password=get_password_hash("testpass123"),
        full_name="Test User",
        role="staff",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_admin(test_db):
    """Utilisateur admin de test avec mot de passe 'admin123'."""
    admin = User(
        tenant_id=1,
        email="admin@carocorp.com",
        hashed_password=get_password_hash("admin123"),
        full_name="Admin User",
        role="admin",
        is_active=True
    )
    test_db.add(admin)
    test_db.commit()
    test_db.refresh(admin)
    return admin


@pytest.fixture
def test_user_tenant2(test_db):
    """Utilisateur de test pour tenant_id=2 (tests anti-cross-tenant)."""
    user = User(
        tenant_id=2,
        email="test@tenant2.com",
        hashed_password=get_password_hash("testpass123"),
        full_name="Tenant 2 User",
        role="staff",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_admin_tenant2(test_db):
    """Utilisateur admin de test pour tenant_id=2 (tests anti-cross-tenant)."""
    admin = User(
        tenant_id=2,
        email="admin@tenant2.com",
        hashed_password=get_password_hash("admin123"),
        full_name="Admin Tenant 2",
        role="admin",
        is_active=True
    )
    test_db.add(admin)
    test_db.commit()
    test_db.refresh(admin)
    return admin


@pytest.fixture
def auth_token(test_user):
    """Token JWT valide pour test_user."""
    claims = {
        "sub": test_user.id,
        "tenant_id": test_user.tenant_id,
        "email": test_user.email,
        "role": test_user.role,
    }
    return create_access_token(claims)


@pytest.fixture
def auth_token_admin(test_admin):
    """Token JWT valide pour test_admin."""
    claims = {
        "sub": test_admin.id,
        "tenant_id": test_admin.tenant_id,
        "email": test_admin.email,
        "role": test_admin.role,
    }
    return create_access_token(claims)


@pytest.fixture
def auth_token_tenant2(test_user_tenant2):
    """Token JWT valide pour test_user_tenant2."""
    claims = {
        "sub": test_user_tenant2.id,
        "tenant_id": test_user_tenant2.tenant_id,
        "email": test_user_tenant2.email,
        "role": test_user_tenant2.role,
    }
    return create_access_token(claims)


@pytest.fixture
def auth_token_admin_tenant2(test_admin_tenant2):
    """Token JWT valide pour test_admin_tenant2."""
    claims = {
        "sub": test_admin_tenant2.id,
        "tenant_id": test_admin_tenant2.tenant_id,
        "email": test_admin_tenant2.email,
        "role": test_admin_tenant2.role,
    }
    return create_access_token(claims)


@pytest.fixture
def auth_headers_real(test_user, auth_token):
    """Headers d'authentification avec vrai token JWT (test_user, tenant_id=1).

    Génère ET stocke le token CSRF dans Redis pour test_user.
    """
    csrf_token = csrf_token_for_user(test_user.id)
    return {
        "Authorization": f"Bearer {auth_token}",
        "X-CSRF-Token": csrf_token,
    }


@pytest.fixture
def auth_headers_admin(test_admin, auth_token_admin):
    """Headers d'authentification avec vrai token JWT admin.

    Génère ET stocke le token CSRF dans Redis pour test_admin.
    """
    csrf_token = csrf_token_for_user(test_admin.id)
    return {
        "Authorization": f"Bearer {auth_token_admin}",
        "X-CSRF-Token": csrf_token,
    }


@pytest.fixture
def auth_headers_tenant2(test_user_tenant2, auth_token_tenant2):
    """Headers d'authentification pour tenant_id=2 (tests anti-cross-tenant).

    Génère ET stocke le token CSRF dans Redis pour test_user_tenant2.
    """
    csrf_token = csrf_token_for_user(test_user_tenant2.id)
    return {
        "Authorization": f"Bearer {auth_token_tenant2}",
        "X-CSRF-Token": csrf_token,
    }


@pytest.fixture
def auth_headers_admin_tenant2(test_admin_tenant2, auth_token_admin_tenant2):
    """Headers d'authentification admin pour tenant_id=2 (tests anti-cross-tenant).

    Génère ET stocke le token CSRF dans Redis pour test_admin_tenant2.
    """
    csrf_token = csrf_token_for_user(test_admin_tenant2.id)
    return {
        "Authorization": f"Bearer {auth_token_admin_tenant2}",
        "X-CSRF-Token": csrf_token,
    }
