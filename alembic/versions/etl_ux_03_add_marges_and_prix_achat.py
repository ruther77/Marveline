"""Add prix_achat_cts to epicerie_produits + create epicerie_marges_categories.

Revision ID: etl_ux_03
Revises: etl_ux_02
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa

revision = "etl_ux_03"
down_revision = "etl_ux_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Ajouter prix_achat_cts sur epicerie_produits
    op.add_column(
        "epicerie_produits",
        sa.Column(
            "prix_achat_cts",
            sa.BigInteger(),
            nullable=True,
            server_default="0",
            comment="Prix d'achat HT en centimes (facture fournisseur)",
        ),
    )

    # 2. Copier les prix actuels (qui sont des prix d'achat) dans prix_achat_cts
    op.execute("UPDATE epicerie_produits SET prix_achat_cts = prix_unitaire_cts")

    # 3. Table de marges par catégorie
    op.create_table(
        "epicerie_marges_categories",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "categorie",
            sa.String(100),
            nullable=False,
            comment="Code catégorie (ALC_BIERE, BOIS_SODA, etc.)",
        ),
        sa.Column(
            "taux_marge_centieme",
            sa.Integer(),
            nullable=False,
            server_default="3000",
            comment="Taux de marge en centièmes de pourcent (3000 = 30%)",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "categorie", name="uq_epicerie_marges_tenant_cat"),
    )
    op.create_index(
        "idx_epicerie_marges_tenant",
        "epicerie_marges_categories",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_table("epicerie_marges_categories")
    op.drop_column("epicerie_produits", "prix_achat_cts")
