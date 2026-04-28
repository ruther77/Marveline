"""add catalogue_produit_eans (multi-EAN cross-pays)

Revision ID: cat_eans_20260424
Revises: ep_vol_20260424
Create Date: 2026-04-24

Contexte : un même produit logique peut avoir plusieurs EANs selon le pays
d'origine ou le packaging régional (ex: Coca Cola 33cL FR vs autre marché).
L'audit end-to-end 2026-04-24 a montré que 29% des lignes factures étaient
perdues silencieusement par la dédup Jaro-Winkler quand l'EAN entrant différait
de celui stocké, même pour des variantes pays du même produit.

Table pivot : un produit catalogue peut avoir 1 EAN principal (colonne
`catalogue_produits.ean`, préservée) + N EANs secondaires (cette table).

La règle de dédup utilise maintenant :
  1. Match par EAN (principal ou secondaire) → produit trouvé
  2. Match désignation + attributs physiques identiques → ajouter EAN secondaire
  3. Match désignation mais attributs physiques différents → créer produit distinct
  4. Pas de match → créer nouveau

Rollback : DROP TABLE non destructif (l'EAN principal reste dans
catalogue_produits.ean, les secondaires sont juste perdus).
"""
from alembic import op
import sqlalchemy as sa


revision = 'cat_eans_20260424'
down_revision = 'ep_vol_20260424'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalogue_produit_eans",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "catalogue_produit_id", sa.BigInteger(),
            sa.ForeignKey("catalogue_produits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ean", sa.String(20), nullable=False,
            comment="EAN secondaire (cross-pays, cross-packaging).",
        ),
        sa.Column(
            "source_fournisseur", sa.String(50), nullable=True,
            comment="Fournisseur d'origine de cet EAN.",
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index(
        "ix_catalogue_produit_eans_produit",
        "catalogue_produit_eans", ["catalogue_produit_id"],
    )
    op.create_index(
        "uq_catalogue_produit_eans_ean",
        "catalogue_produit_eans", ["ean"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_catalogue_produit_eans_ean", table_name="catalogue_produit_eans")
    op.drop_index("ix_catalogue_produit_eans_produit", table_name="catalogue_produit_eans")
    op.drop_table("catalogue_produit_eans")
