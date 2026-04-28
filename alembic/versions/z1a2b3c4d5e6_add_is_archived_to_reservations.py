"""add_is_archived_to_reservations

Revision ID: z1a2b3c4d5e6
Revises: n0p1q2r3s4t5
Create Date: 2026-03-07 00:00:00.000000

Lot 4 — Archivage Option A.
Ajoute is_archived BOOLEAN NOT NULL DEFAULT FALSE sur la table reservations.
Non-destructif (expand-only). Rollback : drop column.
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "z1a2b3c4d5e6"
down_revision: Union[str, None] = "n0p1q2r3s4t5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reservations",
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="Réservation archivée (masquée des listes courantes)",
        ),
    )
    op.create_index(
        "ix_reservations_tenant_archived",
        "reservations",
        ["tenant_id", "is_archived"],
    )


def downgrade() -> None:
    op.drop_index("ix_reservations_tenant_archived", table_name="reservations")
    op.drop_column("reservations", "is_archived")
