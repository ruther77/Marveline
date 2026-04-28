"""create epicerie_produit_eans table

Revision ID: multi_ean_01
Revises: trf_refonte_01
Create Date: 2026-04-10 00:00:00.000000

Table pivot multi-EAN : un produit epicerie peut avoir plusieurs EAN
(fournisseurs differents, meme produit reel).

Expand-only, non-destructif.
"""
from alembic import op
import sqlalchemy as sa

revision = "multi_ean_01"
down_revision = "trf_refonte_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "epicerie_produit_eans",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("produit_id", sa.BigInteger(),
                  sa.ForeignKey("epicerie_produits.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("ean", sa.String(20), nullable=False),
        sa.Column("source_fournisseur", sa.String(50), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "uq_epicerie_produit_ean_tenant",
        "epicerie_produit_eans", ["tenant_id", "ean"], unique=True,
    )
    op.create_index(
        "idx_epicerie_produit_ean_produit",
        "epicerie_produit_eans", ["produit_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_epicerie_produit_ean_produit", table_name="epicerie_produit_eans")
    op.drop_index("uq_epicerie_produit_ean_tenant", table_name="epicerie_produit_eans")
    op.drop_table("epicerie_produit_eans")
