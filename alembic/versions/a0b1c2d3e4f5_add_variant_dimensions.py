"""add_variant_dimensions — color nullable, size, gamme, label, price_per_day

Revision ID: a0b1c2d3e4f5
Revises: y7z8a9b0c1d2
Create Date: 2026-03-02 00:00:00.000000

Stratégie expand/contract non-destructive :
  1. Rendre color nullable (expand)
  2. Ajouter size, gamme, label (nullable d'abord), price_per_day (expand)
  3. Backfill label depuis color (données existantes)
  4. Contraindre label NOT NULL (contract)
  5. Remplacer unique constraint color → label
  6. Ajouter CheckConstraint price_per_day >= 0
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, None] = "y7z8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Rendre color nullable ───────────────────────────────────────────────
    op.alter_column(
        "product_variants",
        "color",
        existing_type=sa.String(50),
        nullable=True,
    )

    # ── 2. Ajouter nouvelles colonnes nullable ─────────────────────────────────
    op.add_column(
        "product_variants",
        sa.Column(
            "size",
            sa.String(50),
            nullable=True,
            comment="Taille/format (ex: 21cm, 240cm)",
        ),
    )
    op.add_column(
        "product_variants",
        sa.Column(
            "gamme",
            sa.String(50),
            nullable=True,
            comment="Gamme/finition (ex: classique, elegance)",
        ),
    )
    op.add_column(
        "product_variants",
        sa.Column(
            "label",
            sa.String(100),
            nullable=True,  # nullable d'abord pour le backfill
            comment="Label affiché — clé d'unicité par produit",
        ),
    )
    op.add_column(
        "product_variants",
        sa.Column(
            "price_per_day",
            sa.BigInteger(),
            nullable=True,
            comment="Override prix parent en centimes (NULL = hérite parent)",
        ),
    )

    # ── 3. Backfill label depuis color ─────────────────────────────────────────
    op.execute(
        "UPDATE product_variants SET label = color WHERE label IS NULL"
    )

    # ── 4. Contraindre label NOT NULL ──────────────────────────────────────────
    op.alter_column(
        "product_variants",
        "label",
        existing_type=sa.String(100),
        nullable=False,
    )

    # ── 5. Remplacer unique constraint color → label ───────────────────────────
    op.drop_constraint(
        "uq_product_variant_tenant_product_color",
        "product_variants",
        type_="unique",
    )
    op.create_index(
        "uq_product_variant_tenant_product_label",
        "product_variants",
        ["tenant_id", "product_id", "label"],
        unique=True,
    )

    # ── 6. CheckConstraint price_per_day >= 0 ──────────────────────────────────
    op.create_check_constraint(
        "check_variant_price_per_day_positive",
        "product_variants",
        "price_per_day IS NULL OR price_per_day >= 0",
    )


def downgrade() -> None:
    # Inverse — contract/expand
    op.drop_constraint(
        "check_variant_price_per_day_positive",
        "product_variants",
        type_="check",
    )
    op.drop_index(
        "uq_product_variant_tenant_product_label",
        table_name="product_variants",
    )
    op.create_unique_constraint(
        "uq_product_variant_tenant_product_color",
        "product_variants",
        ["tenant_id", "product_id", "color"],
    )
    op.drop_column("product_variants", "price_per_day")
    op.drop_column("product_variants", "label")
    op.drop_column("product_variants", "gamme")
    op.drop_column("product_variants", "size")
    op.alter_column(
        "product_variants",
        "color",
        existing_type=sa.String(50),
        nullable=False,
    )
