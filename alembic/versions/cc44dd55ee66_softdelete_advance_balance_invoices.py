"""soft-delete advance/balance invoices, keep only full

Revision ID: cc44dd55ee66
Revises: bb33cc44dd55
Create Date: 2026-03-04 00:00:00.000000

Data-only migration: sets is_active=False on invoices with
invoice_type IN ('advance', 'balance'). New reservations will
generate a single 'full' invoice instead.

Reversible: downgrade restores is_active=True on those rows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cc44dd55ee66"
down_revision: Union[str, None] = "bb33cc44dd55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ajouter is_active (SoftDeleteMixin) — manquait sur invoices
    op.add_column(
        "invoices",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # 2. Soft-delete les factures advance/balance existantes
    op.execute(
        sa.text(
            "UPDATE invoices SET is_active = FALSE "
            "WHERE invoice_type IN ('advance', 'balance') AND is_active = TRUE"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE invoices SET is_active = TRUE "
            "WHERE invoice_type IN ('advance', 'balance') AND is_active = FALSE"
        )
    )
    op.drop_column("invoices", "is_active")
