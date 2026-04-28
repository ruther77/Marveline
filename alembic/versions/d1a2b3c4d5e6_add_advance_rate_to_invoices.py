"""add advance_rate to invoices

Revision ID: d1a2b3c4d5e6
Revises: merge_isoapp_rstxfer
Create Date: 2026-04-16

Alignement schéma/modèle : advance_rate existait dans Pydantic InvoiceResponse
mais pas sur le modèle SQLAlchemy Invoice. Causait AttributeError au render
PDF. Default 0.40 aligne les factures legacy sur la CGV Marveline.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d1a2b3c4d5e6"
down_revision = "merge_isoapp_rstxfer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "advance_rate",
            sa.Float(),
            nullable=False,
            server_default="0.40",
            comment="Taux d'acompte CGV appliqué (0.40 = 40%) — capturé à la création facture",
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "advance_rate")
