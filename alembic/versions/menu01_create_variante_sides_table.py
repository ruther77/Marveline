"""Create restaurant_variante_sides table.

Revision ID: menu01_variante_sides
Revises: img02_restaurant
Create Date: 2026-03-30

Liaison many-to-many VariantePlat ↔ Side avec supplement_cts.
Expand phase: nouvelle table, aucun impact existant.
Rollback safe: DROP TABLE.
"""
from alembic import op
import sqlalchemy as sa

revision = "menu01_variante_sides"
down_revision = "img02_restaurant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "restaurant_variante_sides",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("variante_plat_id", sa.BigInteger, sa.ForeignKey("restaurant_variantes_plat.id", ondelete="CASCADE"), nullable=False),
        sa.Column("side_id", sa.BigInteger, sa.ForeignKey("restaurant_sides.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplement_cts", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("variante_plat_id", "side_id", name="uq_variante_side"),
    )
    op.create_index("ix_variante_side_variante", "restaurant_variante_sides", ["variante_plat_id"])
    op.create_index("ix_variante_side_side", "restaurant_variante_sides", ["side_id"])
    op.create_index("ix_variante_side_tenant", "restaurant_variante_sides", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("restaurant_variante_sides")
