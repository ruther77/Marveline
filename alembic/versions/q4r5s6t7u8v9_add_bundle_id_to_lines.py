"""Add bundle_id to reservation_lines and devis_lines.

Expand-only migration:
- reservation_lines.product_id: NOT NULL → nullable (existing rows keep product_id)
- reservation_lines.bundle_id: new nullable FK → product_bundles
- Replace uq_reservation_line_reservation_product with partial unique indexes
- Add XOR check constraint (product_id XOR bundle_id)
- devis_lines.bundle_id: new nullable FK → product_bundles

Rollback: safe — drops new columns/constraints, restores NOT NULL + old unique constraint.

Revision ID: q4r5s6t7u8v9
Revises: z0a1b2c3d4e5
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = "q4r5s6t7u8v9"
down_revision = "z0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── reservation_lines ──

    # 1. product_id: drop NOT NULL
    op.alter_column(
        "reservation_lines",
        "product_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )

    # 2. Add bundle_id column
    op.add_column(
        "reservation_lines",
        sa.Column(
            "bundle_id",
            sa.BigInteger(),
            sa.ForeignKey("product_bundles.id", ondelete="RESTRICT", name="fk_resa_line_bundle"),
            nullable=True,
            comment="ID du bundle (NULL si ligne produit)",
        ),
    )
    op.create_index("ix_reservation_lines_bundle_id", "reservation_lines", ["bundle_id"])

    # 3. Drop old unique constraint, replace with partial unique indexes
    op.drop_constraint(
        "uq_reservation_line_reservation_product",
        "reservation_lines",
        type_="unique",
    )
    op.execute(
        'CREATE UNIQUE INDEX uq_resa_line_product '
        'ON reservation_lines(reservation_id, product_id) '
        'WHERE product_id IS NOT NULL'
    )
    op.execute(
        'CREATE UNIQUE INDEX uq_resa_line_bundle '
        'ON reservation_lines(reservation_id, bundle_id) '
        'WHERE bundle_id IS NOT NULL'
    )

    # 4. XOR check constraint: exactly one of product_id or bundle_id
    op.create_check_constraint(
        "ck_resa_line_product_xor_bundle",
        "reservation_lines",
        "(product_id IS NOT NULL AND bundle_id IS NULL) "
        "OR (product_id IS NULL AND bundle_id IS NOT NULL)",
    )

    # ── devis_lines ──

    op.add_column(
        "devis_lines",
        sa.Column(
            "bundle_id",
            sa.BigInteger(),
            sa.ForeignKey("product_bundles.id", ondelete="SET NULL", name="fk_devis_line_bundle"),
            nullable=True,
            comment="ID du bundle (NULL si ligne produit ou libre)",
        ),
    )
    op.create_index("ix_devis_lines_bundle_id", "devis_lines", ["bundle_id"])


def downgrade() -> None:
    # ── devis_lines ──
    op.drop_index("ix_devis_lines_bundle_id", "devis_lines")
    op.drop_constraint("fk_devis_line_bundle", "devis_lines", type_="foreignkey")
    op.drop_column("devis_lines", "bundle_id")

    # ── reservation_lines ──
    op.drop_constraint("ck_resa_line_product_xor_bundle", "reservation_lines", type_="check")
    op.execute("DROP INDEX IF EXISTS uq_resa_line_bundle")
    op.execute("DROP INDEX IF EXISTS uq_resa_line_product")

    # Restore old unique constraint
    op.create_unique_constraint(
        "uq_reservation_line_reservation_product",
        "reservation_lines",
        ["reservation_id", "product_id"],
    )

    # Drop bundle_id
    op.drop_index("ix_reservation_lines_bundle_id", "reservation_lines")
    op.drop_constraint("fk_resa_line_bundle", "reservation_lines", type_="foreignkey")
    op.drop_column("reservation_lines", "bundle_id")

    # Restore NOT NULL on product_id
    op.alter_column(
        "reservation_lines",
        "product_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
