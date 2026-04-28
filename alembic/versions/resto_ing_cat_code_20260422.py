"""add categorie_code to restaurant_ingredients (91 codes METRO unifiés)

Permet d'utiliser la même taxonomie que l'épicerie (91 codes alimentaires)
pour tous les ingrédients créés par l'ETL. Le champ categorie_id existant
(15 catégories resto) reste pour compat avec l'UI restaurant, mais n'est
plus renseigné automatiquement par le pipeline ETL.

Revision ID: resto_ing_code_20260422
Revises: resto_mvt_etl_20260421
Create Date: 2026-04-22

Strategy: EXPAND — colonne nullable, aucune donnée existante impactée.
Rollback: DROP COLUMN categorie_code.
"""
from alembic import op
import sqlalchemy as sa

revision = "resto_ing_code_20260422"
down_revision = "resto_mvt_etl_20260421"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "restaurant_ingredients",
        sa.Column(
            "categorie_code",
            sa.String(50),
            nullable=True,
            comment=(
                "Code catégorie unifié (91 codes alimentaires, même taxonomie "
                "que epicerie_produits.categorie). Rempli par le pipeline ETL. "
                "categorie_id (15 cats resto) reste pour compat UI."
            ),
        ),
    )
    op.create_index(
        "idx_resto_ingredients_categorie_code",
        "restaurant_ingredients",
        ["categorie_code"],
    )


def downgrade() -> None:
    op.drop_index("idx_resto_ingredients_categorie_code", table_name="restaurant_ingredients")
    op.drop_column("restaurant_ingredients", "categorie_code")
