"""create_delivery_zones_table

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-02-17 00:00:00.000000

Crée la table delivery_zones pour la Phase 4F (Livraison).
7 départements couverts par Marveline :
    Oise (60), Somme (80), Aisne (02), Val d'Oise (95),
    Seine-Maritime (76), Eure (27), Pas-de-Calais (62).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "delivery_zones",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("department_code", sa.String(length=3), nullable=False),
        sa.Column("department_name", sa.String(length=100), nullable=False),
        sa.Column(
            "delivery_fee_cents",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "sunday_surcharge_cents",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "department_code",
            name="uq_delivery_zone_tenant_dept",
        ),
    )
    op.create_index(
        "ix_delivery_zones_tenant_id", "delivery_zones", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_delivery_zones_tenant_id", table_name="delivery_zones")
    op.drop_table("delivery_zones")
