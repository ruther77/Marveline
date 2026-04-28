"""add restaurant_ingredient_epicerie_mappings

Mapping durable ingrédient restaurant ↔ produits épicerie sources avec ordre
de préférence et facteur de conversion (cascade mixte de résolution).

Revision ID: map_ingr_epi_20260421
Revises: d5e6f7a8b9c0
Create Date: 2026-04-21

Strategy: EXPAND — nouvelle table uniquement, aucune colonne existante touchée.
Rollback: DROP TABLE restaurant_ingredient_epicerie_mappings.
"""
from alembic import op
import sqlalchemy as sa

revision = "map_ingr_epi_20260421"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "restaurant_ingredient_epicerie_mappings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("ingredient_id", sa.BigInteger(), nullable=False),
        sa.Column("produit_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "ordre", sa.Integer(), nullable=False, server_default="0",
        ),
        sa.Column(
            "facteur_conv", sa.Numeric(10, 4), nullable=False, server_default="1",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ingredient_id"], ["restaurant_ingredients.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["produit_id"], ["epicerie_produits.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ingredient_id", "produit_id",
            name="uq_ingr_epi_mapping_ingr_prod",
        ),
        sa.CheckConstraint("ordre >= 0", name="ck_ingr_epi_mapping_ordre_positif"),
        sa.CheckConstraint(
            "facteur_conv > 0", name="ck_ingr_epi_mapping_facteur_positif",
        ),
    )
    op.create_index(
        "ix_ingr_epi_mapping_tenant",
        "restaurant_ingredient_epicerie_mappings",
        ["tenant_id"],
    )
    op.create_index(
        "ix_ingr_epi_mapping_ingredient_ordre",
        "restaurant_ingredient_epicerie_mappings",
        ["ingredient_id", "ordre"],
    )
    op.create_index(
        "ix_ingr_epi_mapping_produit",
        "restaurant_ingredient_epicerie_mappings",
        ["produit_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ingr_epi_mapping_produit",
        table_name="restaurant_ingredient_epicerie_mappings",
    )
    op.drop_index(
        "ix_ingr_epi_mapping_ingredient_ordre",
        table_name="restaurant_ingredient_epicerie_mappings",
    )
    op.drop_index(
        "ix_ingr_epi_mapping_tenant",
        table_name="restaurant_ingredient_epicerie_mappings",
    )
    op.drop_table("restaurant_ingredient_epicerie_mappings")
