"""add etl_import_id to restaurant_mouvements_stock (symétrie avec épicerie)

Permet de retrouver les mouvements générés par une facture ETL → revert + idempotence.

Revision ID: resto_mvt_etl_20260421
Revises: etl_tgt_tenant_20260421
Create Date: 2026-04-21

Strategy: EXPAND — colonne nullable, aucune donnée existante impactée.
Rollback: DROP COLUMN etl_import_id.
"""
from alembic import op
import sqlalchemy as sa

revision = "resto_mvt_etl_20260421"
down_revision = "etl_tgt_tenant_20260421"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "restaurant_mouvements_stock",
        sa.Column(
            "etl_import_id",
            sa.BigInteger(),
            nullable=True,
            comment="FK vers etl_imports.id pour tracer l'origine ETL du mouvement.",
        ),
    )
    op.create_foreign_key(
        "fk_resto_mvt_etl_import",
        "restaurant_mouvements_stock",
        "etl_imports",
        ["etl_import_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_mvt_stock_resto_etl_import",
        "restaurant_mouvements_stock",
        ["etl_import_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_mvt_stock_resto_etl_import", table_name="restaurant_mouvements_stock")
    op.drop_constraint("fk_resto_mvt_etl_import", "restaurant_mouvements_stock", type_="foreignkey")
    op.drop_column("restaurant_mouvements_stock", "etl_import_id")
