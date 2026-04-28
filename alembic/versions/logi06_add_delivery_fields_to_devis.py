"""Add delivery/logistics fields to devis table.

Revision ID: logi06
Revises: logi05
Create Date: 2026-04-02

Expand-only migration. All columns nullable or with server_default.
Rollback = DROP COLUMN each added column + DROP constraints.
"""
from alembic import op
import sqlalchemy as sa


revision = "logi06"
down_revision = "logi05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devis", sa.Column(
        "delivery_method", sa.String(20), nullable=True,
        comment="Methode : self, carrier, pickup",
    ))
    op.add_column("devis", sa.Column(
        "delivery_fee_cents", sa.BigInteger(), nullable=False,
        server_default="0",
        comment="Frais de livraison en centimes",
    ))
    op.add_column("devis", sa.Column(
        "carrier_name", sa.String(100), nullable=True,
        comment="Nom du transporteur (si delivery_method=carrier)",
    ))
    op.add_column("devis", sa.Column(
        "carrier_code", sa.String(20), nullable=True,
        comment="Code transporteur Boxtal (si delivery_method=carrier)",
    ))
    op.add_column("devis", sa.Column(
        "delivery_address", sa.String(500), nullable=True,
        comment="Adresse de livraison (rue, numero)",
    ))
    op.add_column("devis", sa.Column(
        "delivery_city", sa.String(100), nullable=True,
        comment="Ville de livraison",
    ))
    op.add_column("devis", sa.Column(
        "delivery_postal_code", sa.String(10), nullable=True,
        comment="Code postal de livraison",
    ))
    op.add_column("devis", sa.Column(
        "delivery_zone_id", sa.Integer(), nullable=True,
        comment="Zone de livraison (FK)",
    ))
    op.add_column("devis", sa.Column(
        "delivery_instructions", sa.Text(), nullable=True,
        comment="Instructions de livraison",
    ))

    op.create_foreign_key(
        "fk_devis_delivery_zone_id",
        "devis", "delivery_zones",
        ["delivery_zone_id"], ["id"],
        ondelete="SET NULL",
    )

    op.create_check_constraint(
        "check_devis_delivery_fee_positive",
        "devis",
        "delivery_fee_cents >= 0",
    )
    op.create_check_constraint(
        "check_devis_delivery_method_valid",
        "devis",
        "delivery_method IS NULL OR delivery_method IN ('self', 'carrier', 'pickup')",
    )


def downgrade() -> None:
    op.drop_constraint("check_devis_delivery_method_valid", "devis", type_="check")
    op.drop_constraint("check_devis_delivery_fee_positive", "devis", type_="check")
    op.drop_constraint("fk_devis_delivery_zone_id", "devis", type_="foreignkey")
    op.drop_column("devis", "delivery_instructions")
    op.drop_column("devis", "delivery_zone_id")
    op.drop_column("devis", "delivery_postal_code")
    op.drop_column("devis", "delivery_city")
    op.drop_column("devis", "delivery_address")
    op.drop_column("devis", "carrier_code")
    op.drop_column("devis", "carrier_name")
    op.drop_column("devis", "delivery_fee_cents")
    op.drop_column("devis", "delivery_method")
