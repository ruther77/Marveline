"""Configuration de la base de données SQLAlchemy."""
import contextvars
import logging

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import contextmanager, asynccontextmanager
from typing import Generator, AsyncGenerator

from app.core.config import settings

logger = logging.getLogger(__name__)

# ─── RLS tenant context (P1-01) ──────────────────────────────────────────────

_current_tenant_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "_current_tenant_id", default=None
)


def set_tenant_context(tenant_id: int) -> None:
    """Setter le tenant_id pour le RLS PostgreSQL (appele par deps.py)."""
    _current_tenant_id.set(tenant_id)


def clear_tenant_context() -> None:
    """Reset le tenant context apres la requete."""
    _current_tenant_id.set(None)


# ─── Sync (Celery + migration en cours) ──────────────────────────────────────

# Engine SQLAlchemy avec pool de connexions
_engine_kwargs: dict = {
    "pool_size": settings.DB_POOL_SIZE,
    "max_overflow": settings.DB_MAX_OVERFLOW,
    "pool_pre_ping": True,
    "pool_recycle": 3600,  # P3-16 : recycler connexions toutes les heures
    "echo": settings.DEBUG,
}

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

# Slow query + N+1 detection
from app.core.slow_query import install_slow_query_listener
install_slow_query_listener(engine)

# Factory pour les sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# ─── Async (FastAPI — migration en cours) ────────────────────────────────────

async_engine = create_async_engine(
    settings.DATABASE_ASYNC_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG,
)


install_slow_query_listener(async_engine.sync_engine)

# ─── RLS : injecter tenant_id dans chaque transaction PostgreSQL ──────────────

@event.listens_for(async_engine.sync_engine, "before_cursor_execute")
def _inject_rls_tenant(conn, cursor, statement, parameters, context, executemany):
    """SET LOCAL app.current_tenant_id avant chaque requete SQL.

    Le RLS PostgreSQL utilise current_setting('app.current_tenant_id') dans
    les policies USING pour filtrer par tenant.
    SET LOCAL = valide uniquement dans la transaction courante.
    """
    tid = _current_tenant_id.get()
    if tid is not None:
        cursor.execute(f"SET LOCAL app.current_tenant_id = '{tid}'")

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency pour obtenir une session de base de données.

    Usage avec FastAPI:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager pour utilisation en dehors de FastAPI (Celery).

    Usage:
        with get_db_context() as db:
            db.query(...)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def get_async_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager async pour middleware (hors FastAPI Depends)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency async pour obtenir une session de base de données.

    Usage avec FastAPI:
        @app.get("/items")
        async def read_items(db: AsyncSession = Depends(get_async_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
