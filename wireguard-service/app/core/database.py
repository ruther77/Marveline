"""Configuration de la base de données pour le service WireGuard.

Utilise le schema PostgreSQL 'wg' pour isoler les tables du monolithe.
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def create_db_engine(database_url: str | None = None):
    """Crée le moteur SQLAlchemy avec search_path sur le schema wg."""
    settings = get_settings()
    url = database_url or settings.DATABASE_URL

    engine = create_engine(
        url,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_recycle=settings.DATABASE_POOL_RECYCLE,
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def set_search_path(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("SET search_path TO wg, public")
        cursor.close()

    return engine


engine = create_db_engine()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """Dependency injection pour obtenir une session DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
