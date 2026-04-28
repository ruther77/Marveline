"""Create containers, container_assignments, container_items tables.

Revision ID: logi02
Revises: logi01
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa


revision = "logi02"
down_revision = "logi01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "containers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("container_type", sa.String(50), nullable=False),
        sa.Column("length_cm", sa.Integer(), nullable=True),
        sa.Column("width_cm", sa.Integer(), nullable=True),
        sa.Column("height_cm", sa.Integer(), nullable=True),
        sa.Column("max_weight_grams", sa.Integer(), nullable=True),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "container_type IN ('bac', 'carton', 'palette', 'housse', 'caisse')",
            name="check_container_type_valid",
        ),
        sa.CheckConstraint("length_cm IS NULL OR length_cm > 0", name="check_container_length_positive"),
        sa.CheckConstraint("width_cm IS NULL OR width_cm > 0", name="check_container_width_positive"),
        sa.CheckConstraint("height_cm IS NULL OR height_cm > 0", name="check_container_height_positive"),
        sa.CheckConstraint("max_weight_grams IS NULL OR max_weight_grams > 0", name="check_container_max_weight_positive"),
        sa.UniqueConstraint("tenant_id", "serial_number", name="uq_container_tenant_serial"),
        sa.Index("ix_container_tenant_id", "tenant_id", "id"),
    )

    op.create_table(
        "container_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("container_id", sa.Integer(), sa.ForeignKey("containers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("movement_id", sa.Integer(), sa.ForeignKey("inventory_movements.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Index("ix_container_assignment_tenant_id", "tenant_id", "id"),
        sa.UniqueConstraint("tenant_id", "container_id", "movement_id", name="uq_assignment_container_movement"),
    )

    op.create_table(
        "container_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("container_assignment_id", sa.Integer(), sa.ForeignKey("container_assignments.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("movement_item_id", sa.Integer(), sa.ForeignKey("movement_items.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="check_container_item_quantity_positive"),
        sa.Index("ix_container_item_tenant_id", "tenant_id", "id"),
    )


def downgrade() -> None:
    op.drop_table("container_items")
    op.drop_table("container_assignments")
    op.drop_table("containers")
