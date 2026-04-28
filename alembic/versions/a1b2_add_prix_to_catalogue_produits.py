"""Add prix_unitaire_cts and taux_tva_centieme to catalogue_produits.

Revision ID: a1b2prix0001
Revises: v1w2x3y4z5a6
Create Date: 2026-03-15

Expand phase: ajout de colonnes nullable, aucun impact sur l'existant.
Rollback safe: drop columns.
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2prix0001"
down_revision = "b2print3conf4ts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "catalogue_produits",
        sa.Column(
            "prix_unitaire_cts",
            sa.BigInteger(),
            nullable=True,
            comment="Dernier prix unitaire HT en centimes (ADR-25).",
        ),
    )
    op.add_column(
        "catalogue_produits",
        sa.Column(
            "taux_tva_centieme",
            sa.Integer(),
            nullable=True,
            comment="Taux TVA en centiemes (2000=20%, 550=5.5%).",
        ),
    )


def downgrade() -> None:
    op.drop_column("catalogue_produits", "taux_tva_centieme")
    op.drop_column("catalogue_produits", "prix_unitaire_cts")
