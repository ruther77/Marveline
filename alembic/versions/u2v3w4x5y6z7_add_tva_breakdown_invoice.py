"""add tva_breakdown JSON to invoices

Revision ID: u2v3w4x5y6z7
Revises: t1u2v3w4x5y6
Create Date: 2026-02-23

Strategy: EXPAND — colonne JSON nullable (rétro-compat factures existantes = NULL).
Rollback: DROP COLUMN invoices.tva_breakdown
"""
from alembic import op
import sqlalchemy as sa

revision = "u2v3w4x5y6z7"
down_revision = "t1u2v3w4x5y6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "tva_breakdown",
            sa.JSON(),
            nullable=True,
            comment=(
                "Détail TVA multi-taux [{'rate':0.20,'base_ht_cents':8000,"
                "'tva_cents':1600,'ttc_cents':9600}]. NULL = taux unique."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "tva_breakdown")
