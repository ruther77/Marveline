"""Add image_url to restaurant entities.

Revision ID: img02_restaurant
Revises: img01_add_image_url_to_product_variants
Create Date: 2026-03-30

Expand phase: ajoute image_url nullable à 5 tables restaurant.
Rollback safe: DROP COLUMN.
"""
from alembic import op
import sqlalchemy as sa

revision = "img02_restaurant"
down_revision = "add_signed_at_res01"
branch_labels = None
depends_on = None

TABLES = [
    "restaurant_variantes_plat",
    "restaurant_ingredients",
    "restaurant_sides",
    "restaurant_types_preparation",
    "restaurant_categories_ingredient",
]


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("image_url", sa.String(500), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "image_url")
