"""Add epicerie_prix_historique table for price change tracking.

Revision ID: etl_ux_04
Revises: etl_ux_03
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa

revision = "etl_ux_04"
down_revision = ("etl_ux_03", "merge_into_01")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "epicerie_prix_historique",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("produit_id", sa.BigInteger(), sa.ForeignKey("epicerie_produits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prix_achat_cts", sa.BigInteger(), nullable=False, comment="Prix achat HT centimes au moment du changement"),
        sa.Column("prix_vente_cts", sa.BigInteger(), nullable=False, comment="Prix vente TTC centimes au moment du changement"),
        sa.Column("taux_marge_centieme", sa.Integer(), nullable=True, comment="Marge appliquée (centièmes %)"),
        sa.Column("source", sa.String(50), nullable=False, server_default="etl", comment="etl | manual | recalcul"),
        sa.Column("reference", sa.String(200), nullable=True, comment="Ref facture ou note libre"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_prix_hist_produit", "epicerie_prix_historique", ["tenant_id", "produit_id"])
    op.create_index("idx_prix_hist_date", "epicerie_prix_historique", ["created_at"])


def downgrade() -> None:
    op.drop_table("epicerie_prix_historique")
