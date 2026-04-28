"""Add variant_id to devis_lines

Revision ID: dev01_add_variant_id_dl
Revises: img01_add_image_url_pv
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa

revision = "dev01_add_variant_id_dl"
down_revision = "img01_add_image_url_pv"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devis_lines",
        sa.Column(
            "variant_id",
            sa.BigInteger(),
            sa.ForeignKey("product_variants.id", ondelete="RESTRICT"),
            nullable=True,
            comment="ID de la variante choisie (NULL si bundle ou libre)",
        ),
    )
    op.create_index(
        "ix_devis_lines_tenant_variant",
        "devis_lines",
        ["tenant_id", "variant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_devis_lines_tenant_variant", table_name="devis_lines")
    op.drop_column("devis_lines", "variant_id")
