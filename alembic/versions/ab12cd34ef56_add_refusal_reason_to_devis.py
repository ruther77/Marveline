"""Add refusal_reason to devis.

Revision ID: ab12cd34ef56
Revises: dd55ee66ff77
Create Date: 2026-03-04

Expand-only: ajoute colonne nullable TEXT.
Rollback: DROP COLUMN refusal_reason.
"""
from alembic import op
import sqlalchemy as sa


revision = "ab12cd34ef56"
down_revision = "dd55ee66ff77"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devis",
        sa.Column(
            "refusal_reason",
            sa.Text(),
            nullable=True,
            comment="Raison du refus (renseignée lors du passage en status refused)",
        ),
    )


def downgrade() -> None:
    op.drop_column("devis", "refusal_reason")
