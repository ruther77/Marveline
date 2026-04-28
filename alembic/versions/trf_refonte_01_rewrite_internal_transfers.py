"""rewrite_internal_transfers — refonte transferts internes

Revision ID: trf_refonte_01
Revises: etl_stock_01
Create Date: 2026-04-08 00:00:00.000000

Refonte InternalTransfer : entity_source_id/entity_dest_id → tenant_id + dest_tenant_id.
InternalTransferLine : produit_id NOT NULL + designation snapshot.

Expand/contract :
  - Phase 1 : add new columns with defaults (non-destructif)
  - Phase 2 : drop old columns + FK
  - Phase 3 : add new constraints + indexes

Rollback : reverse (add back entity columns, drop new columns).
Donnees existantes : feature cassee et inutilisee, pas de data en prod.
"""
from alembic import op
import sqlalchemy as sa

revision = "trf_refonte_01"
down_revision = "etl_stock_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Phase 1 : add new columns ──────────────────────────────────────────

    # InternalTransfer : tenant_id + dest_tenant_id
    op.add_column(
        "internal_transfers",
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, server_default="2",
                  comment="Tenant source (epicerie)"),
    )
    op.add_column(
        "internal_transfers",
        sa.Column("dest_tenant_id", sa.BigInteger(), nullable=False, server_default="3",
                  comment="Tenant destinataire (restaurant)"),
    )

    # InternalTransferLine : designation snapshot
    op.add_column(
        "internal_transfer_lines",
        sa.Column("designation", sa.String(255), nullable=False, server_default="",
                  comment="Snapshot designation produit au moment du transfert"),
    )

    # ── Phase 2 : drop old columns + FK + constraints ──────────────────────

    # Drop old indexes first
    op.drop_index("idx_internal_transfer_source", table_name="internal_transfers")
    op.drop_index("idx_internal_transfer_dest", table_name="internal_transfers")

    # Drop old CHECK constraint
    op.drop_constraint("check_internal_transfer_source_ne_dest", "internal_transfers")

    # Drop old FK constraints (actual names from DB inspection)
    op.drop_constraint(
        "fk_internal_transfer_source", "internal_transfers", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_internal_transfer_dest", "internal_transfers", type_="foreignkey"
    )

    # Drop old columns
    op.drop_column("internal_transfers", "entity_source_id")
    op.drop_column("internal_transfers", "entity_dest_id")

    # ── Phase 3 : produit_id NOT NULL + new constraints ────────────────────

    # Make produit_id NOT NULL (backfill not needed — no production data)
    op.alter_column(
        "internal_transfer_lines", "produit_id",
        existing_type=sa.BigInteger(), nullable=False,
    )

    # Change produit_id FK from SET NULL to RESTRICT
    op.drop_constraint(
        "fk_transfer_line_produit", "internal_transfer_lines", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_transfer_line_produit",
        "internal_transfer_lines", "epicerie_produits",
        ["produit_id"], ["id"], ondelete="RESTRICT",
    )

    # New CHECK constraint
    op.create_check_constraint(
        "check_internal_transfer_source_ne_dest",
        "internal_transfers",
        "tenant_id != dest_tenant_id",
    )

    # New indexes
    op.create_index("idx_transfer_tenant_status", "internal_transfers", ["tenant_id", "status"])
    op.create_index("idx_transfer_dest_tenant", "internal_transfers", ["dest_tenant_id"])

    # Remove server_defaults (only needed for backfill)
    op.alter_column("internal_transfers", "tenant_id", server_default=None)
    op.alter_column("internal_transfers", "dest_tenant_id", server_default=None)
    op.alter_column("internal_transfer_lines", "designation", server_default=None)


def downgrade() -> None:
    # Remove new indexes + constraints
    op.drop_index("idx_transfer_dest_tenant", table_name="internal_transfers")
    op.drop_index("idx_transfer_tenant_status", table_name="internal_transfers")
    op.drop_constraint("check_internal_transfer_source_ne_dest", "internal_transfers")

    # Revert produit_id to nullable + SET NULL
    op.drop_constraint(
        "fk_transfer_line_produit", "internal_transfer_lines", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_transfer_line_produit",
        "internal_transfer_lines", "epicerie_produits",
        ["produit_id"], ["id"], ondelete="SET NULL",
    )
    op.alter_column(
        "internal_transfer_lines", "produit_id",
        existing_type=sa.BigInteger(), nullable=True,
    )

    # Drop designation
    op.drop_column("internal_transfer_lines", "designation")

    # Re-add entity columns
    op.add_column(
        "internal_transfers",
        sa.Column("entity_source_id", sa.BigInteger(), nullable=False, server_default="1"),
    )
    op.add_column(
        "internal_transfers",
        sa.Column("entity_dest_id", sa.BigInteger(), nullable=False, server_default="2"),
    )
    op.create_foreign_key(
        "fk_internal_transfer_source",
        "internal_transfers", "finance_entities",
        ["entity_source_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_internal_transfer_dest",
        "internal_transfers", "finance_entities",
        ["entity_dest_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index("idx_internal_transfer_source", "internal_transfers", ["entity_source_id"])
    op.create_index("idx_internal_transfer_dest", "internal_transfers", ["entity_dest_id"])
    op.create_check_constraint(
        "check_internal_transfer_source_ne_dest",
        "internal_transfers",
        "entity_source_id != entity_dest_id",
    )

    # Drop new columns
    op.drop_column("internal_transfers", "dest_tenant_id")
    op.drop_column("internal_transfers", "tenant_id")
