"""add invoice timeline columns (sent_at, opened_at, reminders, cancelled_at)

Revision ID: z7a8b9c0d1e2
Revises: y6z7a8b9c0d1
Create Date: 2026-02-24

Strategy: EXPAND — nouvelles colonnes nullable uniquement, aucune contrainte NOT NULL.
Rollback: DROP COLUMN sent_at, opened_at, first_reminder_sent_at, last_reminder_sent_at, cancelled_at FROM invoices
"""
from alembic import op
import sqlalchemy as sa


revision = "z7a8b9c0d1e2"
down_revision = "y6z7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("first_reminder_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("last_reminder_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "cancelled_at")
    op.drop_column("invoices", "last_reminder_sent_at")
    op.drop_column("invoices", "first_reminder_sent_at")
    op.drop_column("invoices", "opened_at")
    op.drop_column("invoices", "sent_at")
