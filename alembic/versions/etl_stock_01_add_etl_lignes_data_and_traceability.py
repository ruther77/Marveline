"""add_etl_lignes_data_and_traceability

Revision ID: etl_stock_01
Revises: z9a0b1c2d3e4
Create Date: 2026-04-07 00:00:00.000000

Expand-only : ajoute 3 colonnes nullable sans impact sur les donnees existantes.
  - etl_imports.lignes_data (JSON) : persistance des lignes parsees entre PREVIEW et VALIDATED
  - finance_invoices.etl_import_id (BigInteger) : tracabilite ETL -> facture
  - epicerie_stock_movements.etl_import_id (BigInteger) : tracabilite ETL -> mouvement ENTREE

Rollback : suppression des colonnes et index (aucune perte de donnees metier).
"""
from alembic import op
import sqlalchemy as sa

revision = "etl_stock_01"
down_revision = "merge01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. EtlImport : lignes parsees en JSON
    op.add_column(
        "etl_imports",
        sa.Column("lignes_data", sa.JSON(), nullable=True,
                  comment="Lignes parsees serialisees (list[dict])"),
    )

    # 2. FinanceInvoice : lien vers ETL import
    op.add_column(
        "finance_invoices",
        sa.Column("etl_import_id", sa.BigInteger(), nullable=True,
                  comment="FK etl_imports — factures creees via ETL pipeline"),
    )
    op.create_index(
        "idx_finance_invoice_etl_import", "finance_invoices", ["etl_import_id"],
    )

    # 3. EpicerieStockMovement : lien vers ETL import
    op.add_column(
        "epicerie_stock_movements",
        sa.Column("etl_import_id", sa.BigInteger(), nullable=True,
                  comment="FK etl_imports — type=ENTREE via ETL validation"),
    )
    op.create_index(
        "idx_epicerie_mvt_etl_import", "epicerie_stock_movements", ["etl_import_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_epicerie_mvt_etl_import", table_name="epicerie_stock_movements")
    op.drop_column("epicerie_stock_movements", "etl_import_id")

    op.drop_index("idx_finance_invoice_etl_import", table_name="finance_invoices")
    op.drop_column("finance_invoices", "etl_import_id")

    op.drop_column("etl_imports", "lignes_data")
