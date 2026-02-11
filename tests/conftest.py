"""Configuration pytest pour les tests CaroCorp."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.models.base import Base
from app.core.database import get_db
from app.core.config import settings


# Database de test
TEST_DATABASE_URL = "postgresql+psycopg2://caro:6L9dVl9hxpWylE8YQfNUNA@localhost:5433/CaroCorp_test"


@pytest.fixture(scope="session")
def test_engine():
    """Engine de test pour la session."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Session de base de données pour chaque test."""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


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


@pytest.fixture
def auth_headers():
    """Headers d'authentification pour les tests."""
    # TODO: Générer un vrai token JWT
    return {
        "Authorization": "Bearer test_token",
        "X-CSRF-Token": "test_csrf_token",
    }
