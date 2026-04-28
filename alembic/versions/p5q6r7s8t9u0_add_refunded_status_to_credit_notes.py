"""add refunded status to credit notes

Revision ID: p5q6r7s8t9u0
Revises: e9f0a1b2c3d4
Create Date: 2026-03-04

Expand-only : ajoute 'refunded' à la contrainte CHECK sur invoice_credit_notes.status.
Le downgrade retire 'refunded' de la contrainte (safe si aucune ligne refunded existante).
"""
from alembic import op

revision = 'p5q6r7s8t9u0'
down_revision = 'e9f0a1b2c3d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE invoice_credit_notes "
        "DROP CONSTRAINT IF EXISTS check_credit_note_status_valid"
    )
    op.execute(
        "ALTER TABLE invoice_credit_notes "
        "ADD CONSTRAINT check_credit_note_status_valid "
        "CHECK (status IN ('draft','issued','applied','refunded'))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE invoice_credit_notes "
        "DROP CONSTRAINT IF EXISTS check_credit_note_status_valid"
    )
    op.execute(
        "ALTER TABLE invoice_credit_notes "
        "ADD CONSTRAINT check_credit_note_status_valid "
        "CHECK (status IN ('draft','issued','applied'))"
    )
