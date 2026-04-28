"""create product_maintenances table

Revision ID: dd66ee77ff88
Revises: cc44dd55ee66
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = "dd66ee77ff88"
down_revision = "cc44dd55ee66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_maintenances",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger, nullable=False),
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("scheduled_date", sa.Date, nullable=True),
        sa.Column("completed_date", sa.Date, nullable=True),
        sa.Column("cost_cents", sa.BigInteger, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_maintenance_tenant_product",
        "product_maintenances",
        ["tenant_id", "product_id"],
    )
    op.create_index(
        "idx_maintenance_tenant_id",
        "product_maintenances",
        ["tenant_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("idx_maintenance_tenant_id", table_name="product_maintenances")
    op.drop_index("idx_maintenance_tenant_product", table_name="product_maintenances")
    op.drop_table("product_maintenances")
