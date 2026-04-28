"""Add image_url to product_variants

Revision ID: img01_add_image_url_pv
Revises: h5i6j7k8l9m0
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa

revision = "img01_add_image_url_pv"
down_revision = "h5i6j7k8l9m0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_variants",
        sa.Column(
            "image_url",
            sa.String(500),
            nullable=True,
            comment="Override image URL de la variante (NULL = herite parent)",
        ),
    )


def downgrade() -> None:
    op.drop_column("product_variants", "image_url")
