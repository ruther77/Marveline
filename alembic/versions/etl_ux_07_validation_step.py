"""Add validation_step column to etl_imports for progress tracking.

Revision ID: etl_ux_07
Revises: etl_ux_06
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = "etl_ux_07"
down_revision = "etl_ux_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("etl_imports", sa.Column(
        "validation_step", sa.String(50), nullable=True,
        comment="Étape courante de validation (catalogue, stock, invoice, prix)",
    ))


def downgrade() -> None:
    op.drop_column("etl_imports", "validation_step")
