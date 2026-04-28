"""Add fichier_path to etl_imports for PDF persistence.

Revision ID: etl_ux_01
Revises: etl_stock_01
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa

revision = "etl_ux_01"
down_revision = "trf_refonte_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "etl_imports",
        sa.Column(
            "fichier_path",
            sa.Text(),
            nullable=True,
            comment="Chemin relatif du PDF persisté. Ex: 'etl/42.pdf'",
        ),
    )


def downgrade() -> None:
    op.drop_column("etl_imports", "fichier_path")
