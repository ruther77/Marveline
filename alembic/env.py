"""Configuration Alembic pour les migrations CaroCorp."""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import des modèles et configuration
from app.core.config import settings
from app.models.base import Base
# CRITIQUE: Importer tous les modèles pour autogenerate (fix B5)
from app.models import (  # noqa: F401
    # IAM v2
    Account, AccountOAuthIdentity, TenantMembership, AccountSession,
    # Core
    Customer, Product, Reservation, ReservationLine, Invoice,
    AuditLog, MFADevice, Category, ProductBundle, BundleItem,
    ApiKey, FeatureFlag, InventoryMovement, MovementItem,
    AuthRole, AuthScope, AuthRoleScope, UserRole,
    PasswordResetToken,
)

# Configuration Alembic
config = context.config

# Configurer logging depuis alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Métadonnées des modèles pour autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
