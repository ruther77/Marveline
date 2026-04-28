"""Add weight_grams and volume_cm3 to products and product_variants.

Revision ID: logi01
Revises: ab12cd34ef56, c1d2e3f4a5b6, c9d0e1f2a3b4, cc33dd44ee55, n3o4t5e6s7r8, q4r5s6t7u8v9, q6r7s8t9u0v1, y7z8a9b0c1d2
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa


revision = "logi01"
down_revision = (
    "ab12cd34ef56",
    "c1d2e3f4a5b6",
    "c9d0e1f2a3b4",
    "cc33dd44ee55",
    "n3o4t5e6s7r8",
    "q4r5s6t7u8v9",
    "q6r7s8t9u0v1",
    "y7z8a9b0c1d2",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Products
    op.add_column(
        "products",
        sa.Column(
            "weight_grams",
            sa.Integer(),
            nullable=True,
            comment="Poids unitaire en grammes (NULL = non renseigné)",
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "volume_cm3",
            sa.Integer(),
            nullable=True,
            comment="Volume unitaire en cm³ (NULL = non renseigné)",
        ),
    )
    op.create_check_constraint(
        "check_product_weight_grams_positive",
        "products",
        "weight_grams IS NULL OR weight_grams >= 0",
    )
    op.create_check_constraint(
        "check_product_volume_cm3_positive",
        "products",
        "volume_cm3 IS NULL OR volume_cm3 >= 0",
    )

    # Product variants (override parent)
    op.add_column(
        "product_variants",
        sa.Column(
            "weight_grams",
            sa.Integer(),
            nullable=True,
            comment="Override poids unitaire en grammes (NULL = hérite parent)",
        ),
    )
    op.add_column(
        "product_variants",
        sa.Column(
            "volume_cm3",
            sa.Integer(),
            nullable=True,
            comment="Override volume unitaire en cm³ (NULL = hérite parent)",
        ),
    )
    op.create_check_constraint(
        "check_variant_weight_grams_positive",
        "product_variants",
        "weight_grams IS NULL OR weight_grams >= 0",
    )
    op.create_check_constraint(
        "check_variant_volume_cm3_positive",
        "product_variants",
        "volume_cm3 IS NULL OR volume_cm3 >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("check_variant_volume_cm3_positive", "product_variants", type_="check")
    op.drop_constraint("check_variant_weight_grams_positive", "product_variants", type_="check")
    op.drop_column("product_variants", "volume_cm3")
    op.drop_column("product_variants", "weight_grams")

    op.drop_constraint("check_product_volume_cm3_positive", "products", type_="check")
    op.drop_constraint("check_product_weight_grams_positive", "products", type_="check")
    op.drop_column("products", "volume_cm3")
    op.drop_column("products", "weight_grams")
