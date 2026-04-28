"""Alembic environment configuration pour le service WireGuard.

Utilise le schema PostgreSQL 'wg' séparé du monolithe.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

# Ajouter le répertoire parent pour les imports app.*
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.base import Base
from app.models.peer import WgPeer
from app.models.ip_pool import WgIpPool
from app.models.audit_log import WgAuditLog

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Obtient l'URL de la base depuis l'environnement ou alembic.ini."""
    return os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="alembic_version",
        version_table_schema="wg",
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Créer le schema wg s'il n'existe pas
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS wg"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="alembic_version",
            version_table_schema="wg",
            include_schemas=True,
        )

        with context.begin_transaction():
            connection.execute(text("SET search_path TO wg, public"))
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
