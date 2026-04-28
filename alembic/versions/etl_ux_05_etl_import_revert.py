"""Add REVERTED status + prix_snapshot + revert columns to etl_imports.

Revision ID: etl_ux_05
Revises: etl_ux_04
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa

revision = "etl_ux_05"
down_revision = "etl_ux_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Nouvelles colonnes
    op.add_column("etl_imports", sa.Column("prix_snapshot", sa.JSON(), nullable=True,
        comment="Snapshot {catalogue_produit_id: prix_unitaire_cts} avant validation"))
    op.add_column("etl_imports", sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True,
        comment="Date/heure du revert"))
    op.add_column("etl_imports", sa.Column("reverted_by_id", sa.BigInteger(), nullable=True,
        comment="ID du compte qui a reverté"))

    # 2. DROP + re-CREATE du CHECK constraint statut pour inclure REVERTED
    op.drop_constraint("ck_etl_imports_statut", "etl_imports", type_="check")
    op.create_check_constraint(
        "ck_etl_imports_statut",
        "etl_imports",
        "statut IN ('PENDING', 'RUNNING', 'PREVIEW', 'VALIDATED', 'REJECTED', "
        "'SUCCES', 'PARTIEL', 'ECHEC', 'REVERTED')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_etl_imports_statut", "etl_imports", type_="check")
    op.create_check_constraint(
        "ck_etl_imports_statut",
        "etl_imports",
        "statut IN ('PENDING', 'RUNNING', 'PREVIEW', 'VALIDATED', 'REJECTED', "
        "'SUCCES', 'PARTIEL', 'ECHEC')",
    )
    op.drop_column("etl_imports", "reverted_by_id")
    op.drop_column("etl_imports", "reverted_at")
    op.drop_column("etl_imports", "prix_snapshot")
