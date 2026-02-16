"""add_reservation_id_to_movements

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-02-16 10:00:00.000000

Add reservation_id FK column to inventory_movements table.
Expand-only migration (nullable column + index).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inventory_movements",
        sa.Column("reservation_id", sa.Integer(), nullable=True),
    )

    op.create_foreign_key(
        "fk_movement_reservation",
        "inventory_movements",
        "reservations",
        ["reservation_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_inventory_movement_reservation",
        "inventory_movements",
        ["tenant_id", "reservation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_movement_reservation", table_name="inventory_movements")
    op.drop_constraint("fk_movement_reservation", "inventory_movements", type_="foreignkey")
    op.drop_column("inventory_movements", "reservation_id")
