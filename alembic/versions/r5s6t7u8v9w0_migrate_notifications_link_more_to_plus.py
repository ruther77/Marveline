"""Migrate notifications.link /more → /plus

Revision ID: r5s6t7u8v9w0
Revises: q1r2s3t4u5v6
Create Date: 2026-03-06

Strategy: DATA PATCH — UPDATE idempotent sur la colonne nullable link.
  Toute notification dont le lien commence par '/more' est mise à jour vers '/plus'.

Rollback: Replace('/plus', '/more') — inverse exact.
Impact: notifications.link (nullable VARCHAR 500) — aucune colonne structurelle modifiée.
"""
from alembic import op
import sqlalchemy as sa


revision = "r5s6t7u8v9w0"
down_revision = "q1r2s3t4u5v6"
branch_labels = None
depends_on = None

_UPDATE_SQL = sa.text(
    "UPDATE notifications "
    "SET link = '/plus' || SUBSTR(link, 6) "
    "WHERE link LIKE '/more%'"
)

_ROLLBACK_SQL = sa.text(
    "UPDATE notifications "
    "SET link = '/more' || SUBSTR(link, 6) "
    "WHERE link LIKE '/plus%'"
)


def upgrade() -> None:
    op.execute(_UPDATE_SQL)


def downgrade() -> None:
    op.execute(_ROLLBACK_SQL)
