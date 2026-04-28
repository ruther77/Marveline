"""add tva_rate to products and reservation_lines

Revision ID: t1u2v3w4x5y6
Revises: s5t6u7v8w9x0
Create Date: 2026-02-23

Strategy: EXPAND — ajout de colonnes nullable avec DEFAULT.
Rollback: DROP COLUMN products.tva_rate, DROP COLUMN reservation_lines.tva_rate
"""
from alembic import op
import sqlalchemy as sa

revision = "t1u2v3w4x5y6"
down_revision = "s5t6u7v8w9x0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Expand: colonnes ajoutées avec DEFAULT — rétro-compatibles
    op.add_column(
        "products",
        sa.Column(
            "tva_rate",
            sa.Float(),
            nullable=False,
            server_default="0.20",
            comment="Taux TVA appliqué à ce produit (ex: 0.20 = 20%)",
        ),
    )
    op.add_column(
        "reservation_lines",
        sa.Column(
            "tva_rate",
            sa.Float(),
            nullable=False,
            server_default="0.20",
            comment="Snapshot du taux TVA au moment de la réservation",
        ),
    )


def downgrade() -> None:
    op.drop_column("reservation_lines", "tva_rate")
    op.drop_column("products", "tva_rate")
