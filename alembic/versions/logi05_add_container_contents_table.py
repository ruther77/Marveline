"""Add container_contents table for persistent container inventory.

Revision ID: logi05
Revises: logi04
Create Date: 2026-04-01

Expand-only migration. Rollback = DROP TABLE container_contents.
No existing columns touched.
"""
from alembic import op
import sqlalchemy as sa


revision = "logi05"
down_revision = "logi04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "container_contents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "container_id",
            sa.Integer(),
            sa.ForeignKey("containers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "variant_id",
            sa.Integer(),
            sa.ForeignKey("product_variants.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="check_container_content_qty_positive"),
        sa.UniqueConstraint(
            "tenant_id", "container_id", "product_id", "variant_id",
            name="uq_container_content_product",
        ),
        sa.Index("ix_container_contents_tenant_id", "tenant_id", "id"),
    )

    # Index partiel pour le cas variant_id IS NULL (PostgreSQL traite NULL
    # comme distinct dans les contraintes UNIQUE classiques).
    op.create_index(
        "uq_container_content_no_variant",
        "container_contents",
        ["tenant_id", "container_id", "product_id"],
        unique=True,
        postgresql_where=sa.text("variant_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_container_content_no_variant", table_name="container_contents")
    op.drop_table("container_contents")
