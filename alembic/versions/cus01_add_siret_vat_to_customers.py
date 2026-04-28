"""Add siret and vat_number to customers table.

Revision ID: cus01_siret_vat
Revises: a3b4c5d6e7f8
Create Date: 2026-04-02

CUS-01: champs B2B manquants pour facturation pro.
Expand-only — aucune donnee detruite, rollback safe.
"""
from alembic import op
import sqlalchemy as sa

revision = "cus01_siret_vat"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("siret", sa.String(14), nullable=True, comment="SIRET (14 chiffres)"),
    )
    op.add_column(
        "customers",
        sa.Column("vat_number", sa.String(20), nullable=True, comment="TVA intracommunautaire"),
    )


def downgrade() -> None:
    op.drop_column("customers", "vat_number")
    op.drop_column("customers", "siret")
