"""Add relance.email_send_error + status='failed' for F1058 fix tracking

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-04-28 14:30:00.000000

Sprint 1 PROD FIRE-DRILL - RELANCE-FAKE-SENT-01 (TR-80 / F1058)

Avant ce fix, app/tasks/relances.py marquait status='sent' sans appeler
de gateway email. Cette migration prepare le tracking d'echec :
- nouvelle colonne email_send_error (VARCHAR 500 nullable)
- nouvelle valeur 'failed' acceptee par le CHECK constraint sur status
"""
from alembic import op
import sqlalchemy as sa


revision = "x4y5z6a7b8c9"
down_revision = "w3x4y5z6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "relances",
        sa.Column(
            "email_send_error",
            sa.String(length=500),
            nullable=True,
            comment="F1058 - message d'erreur si l'envoi gateway a echoue",
        ),
    )

    # CHECK constraint : ajouter 'failed' aux statuts acceptes
    op.drop_constraint("check_relance_status_valid", "relances", type_="check")
    op.create_check_constraint(
        "check_relance_status_valid",
        "relances",
        "status IN ('scheduled', 'sent', 'cancelled', 'failed')",
    )


def downgrade() -> None:
    # Avant rollback, normaliser les rows 'failed' -> 'scheduled' (retry au prochain cycle)
    op.execute("UPDATE relances SET status = 'scheduled' WHERE status = 'failed'")

    op.drop_constraint("check_relance_status_valid", "relances", type_="check")
    op.create_check_constraint(
        "check_relance_status_valid",
        "relances",
        "status IN ('scheduled', 'sent', 'cancelled')",
    )

    op.drop_column("relances", "email_send_error")
