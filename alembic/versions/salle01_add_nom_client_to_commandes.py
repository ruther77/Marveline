"""Add nom_client to restaurant_commandes.

Revision ID: salle01_nom_client
Revises: menu01_variante_sides
Create Date: 2026-04-01

Expand phase: colonne nullable, aucun impact existant.
"""
from alembic import op
import sqlalchemy as sa

revision = "salle01_nom_client"
down_revision = "menu01_variante_sides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "restaurant_commandes",
        sa.Column("nom_client", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("restaurant_commandes", "nom_client")
