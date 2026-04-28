"""add damage_type_id to movement_item_units

Revision ID: dd44ee55ff66
Revises: cc33dd44ee55
Create Date: 2026-02-25

"""
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dd44ee55ff66"
down_revision: Union[str, None] = "cc33dd44ee55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "movement_item_units",
        sa.Column(
            "damage_type_id",
            sa.Integer(),
            sa.ForeignKey("damage_types.id", ondelete="SET NULL"),
            nullable=True,
            comment="Type de dommage constaté au retour (FK damage_types)",
        ),
    )
    op.create_index(
        "ix_movement_item_unit_damage_type",
        "movement_item_units",
        ["damage_type_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_movement_item_unit_damage_type", table_name="movement_item_units")
    op.drop_column("movement_item_units", "damage_type_id")
