"""Add 'completed' to reservation status CHECK constraint.

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-03-04

Stratégie expand-only : DROP + ADD constraint (non-destructif — on ajoute une valeur).
Aucune donnée existante n'est impactée.
Rollback : DROP + ADD la contrainte sans 'completed'.
"""
from alembic import op


revision = "f0a1b2c3d4e5"
down_revision = "e9f0a1b2c3d4"
branch_labels = None
depends_on = None

_CONSTRAINT_NAME = "check_reservation_status_valid"
_TABLE = "reservations"

_STATUS_WITH_COMPLETED = (
    "'draft', 'confirmed', 'pre_check', 'confirmed_risk', "
    "'delivered', 'extended', 'returned', 'returned_dispute', "
    "'completed', 'cancelled'"
)

_STATUS_WITHOUT_COMPLETED = (
    "'draft', 'confirmed', 'pre_check', 'confirmed_risk', "
    "'delivered', 'extended', 'returned', 'returned_dispute', "
    "'cancelled'"
)


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT_NAME, _TABLE, type_="check")
    op.create_check_constraint(
        _CONSTRAINT_NAME,
        _TABLE,
        f"status IN ({_STATUS_WITH_COMPLETED})",
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT_NAME, _TABLE, type_="check")
    op.create_check_constraint(
        _CONSTRAINT_NAME,
        _TABLE,
        f"status IN ({_STATUS_WITHOUT_COMPLETED})",
    )
