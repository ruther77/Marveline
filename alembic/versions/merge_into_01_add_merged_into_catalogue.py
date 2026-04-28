"""add merged_into_id to catalogue_produits

Revision ID: merge_into_01
Revises: merge02
Create Date: 2026-04-10 00:00:00.000000

Quand un conflit est résolu en MERGED, le produit catalogue entrant
pointe vers le produit cible via merged_into_id.
Le sync skip les produits avec merged_into_id != NULL.
"""
from alembic import op
import sqlalchemy as sa

revision = "merge_into_01"
down_revision = "merge02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "catalogue_produits",
        sa.Column("merged_into_id", sa.BigInteger(), nullable=True,
                  comment="Si fusionné, pointe vers le produit catalogue cible"),
    )
    op.create_index(
        "idx_catalogue_merged_into", "catalogue_produits", ["merged_into_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_catalogue_merged_into", table_name="catalogue_produits")
    op.drop_column("catalogue_produits", "merged_into_id")
