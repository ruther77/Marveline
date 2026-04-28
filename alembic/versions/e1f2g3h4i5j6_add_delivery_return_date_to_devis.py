"""add delivery_date and return_date to devis

Revision ID: e1f2g3h4i5j6
Revises: cc44dd55ee66
Create Date: 2026-03-07

Strategy: EXPAND — ajout de colonnes nullable uniquement (non-destructif).

Rollback: DROP COLUMN delivery_date, DROP COLUMN return_date (safe, nullable).
"""
from alembic import op
import sqlalchemy as sa

revision = "e1f2g3h4i5j6"
down_revision = "cc44dd55ee66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devis", sa.Column("delivery_date", sa.Date(), nullable=True,
                  comment="Date de livraison prévue (propagée à la réservation lors de la conversion)"))
    op.add_column("devis", sa.Column("return_date", sa.Date(), nullable=True,
                  comment="Date de retour prévue (propagée à la réservation lors de la conversion)"))


def downgrade() -> None:
    op.drop_column("devis", "return_date")
    op.drop_column("devis", "delivery_date")
