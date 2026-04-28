"""add inventory_movement_damages table

Revision ID: aa11bb22cc33
Revises: z7a8b9c0d1e2
Create Date: 2026-02-24

Expand-only : ajout de la table inventory_movement_damages pour tracer
les dommages constatés à la restitution d'un mouvement de stock.
"""
from alembic import op
import sqlalchemy as sa

revision = "aa11bb22cc33"
down_revision = "z7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_movement_damages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "movement_id",
            sa.Integer(),
            sa.ForeignKey("inventory_movements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "damage_type_id",
            sa.Integer(),
            sa.ForeignKey("damage_types.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("qty_damaged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("estimated_cost_cents", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("qty_damaged >= 0", name="ck_movement_damage_qty_nn"),
    )
    op.create_index(
        "ix_inventory_movement_damages_tenant_id",
        "inventory_movement_damages",
        ["tenant_id"],
    )
    op.create_index(
        "ix_inventory_movement_damages_movement_id",
        "inventory_movement_damages",
        ["movement_id"],
    )
    op.create_index(
        "ix_inventory_movement_damages_tenant_movement",
        "inventory_movement_damages",
        ["tenant_id", "movement_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_movement_damages_tenant_movement",
        table_name="inventory_movement_damages",
    )
    op.drop_index(
        "ix_inventory_movement_damages_movement_id",
        table_name="inventory_movement_damages",
    )
    op.drop_index(
        "ix_inventory_movement_damages_tenant_id",
        table_name="inventory_movement_damages",
    )
    op.drop_table("inventory_movement_damages")
