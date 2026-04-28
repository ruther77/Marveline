"""Add delivery logistics columns to reservations + DELIVERY charge type.

Revision ID: logi03
Revises: logi02
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa


revision = "logi03"
down_revision = "logi02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Colonnes livraison sur reservations
    op.add_column(
        "reservations",
        sa.Column(
            "delivery_zone_id",
            sa.Integer(),
            sa.ForeignKey("delivery_zones.id", ondelete="SET NULL"),
            nullable=True,
            comment="Zone de livraison (FK)",
        ),
    )
    op.add_column(
        "reservations",
        sa.Column(
            "delivery_fee_cents",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Frais de livraison en centimes",
        ),
    )
    op.add_column(
        "reservations",
        sa.Column(
            "delivery_method",
            sa.String(20),
            nullable=True,
            comment="Méthode : self, carrier, pickup",
        ),
    )
    op.add_column(
        "reservations",
        sa.Column(
            "delivery_instructions",
            sa.Text(),
            nullable=True,
            comment="Instructions de livraison",
        ),
    )
    op.add_column(
        "reservations",
        sa.Column(
            "carrier_name",
            sa.String(100),
            nullable=True,
            comment="Nom du transporteur (si delivery_method=carrier)",
        ),
    )
    op.add_column(
        "reservations",
        sa.Column(
            "carrier_code",
            sa.String(50),
            nullable=True,
            comment="Code transporteur Boxtal (si delivery_method=carrier)",
        ),
    )
    op.create_check_constraint(
        "check_reservation_delivery_fee_positive",
        "reservations",
        "delivery_fee_cents >= 0",
    )
    op.create_check_constraint(
        "check_reservation_delivery_method_valid",
        "reservations",
        "delivery_method IS NULL OR delivery_method IN ('self', 'carrier', 'pickup')",
    )
    op.create_index(
        "ix_reservations_delivery_zone_id",
        "reservations",
        ["delivery_zone_id"],
    )

    # Étendre le CHECK charge_type pour inclure DELIVERY
    op.drop_constraint("check_charge_type_valid", "invoice_charges", type_="check")
    op.create_check_constraint(
        "check_charge_type_valid",
        "invoice_charges",
        "charge_type IN ('DAMAGE', 'LABOR', 'DELIVERY')",
    )


def downgrade() -> None:
    # Restaurer ancien CHECK charge_type
    op.drop_constraint("check_charge_type_valid", "invoice_charges", type_="check")
    op.create_check_constraint(
        "check_charge_type_valid",
        "invoice_charges",
        "charge_type IN ('DAMAGE', 'LABOR')",
    )

    op.drop_index("ix_reservations_delivery_zone_id", "reservations")
    op.drop_constraint("check_reservation_delivery_method_valid", "reservations", type_="check")
    op.drop_constraint("check_reservation_delivery_fee_positive", "reservations", type_="check")
    op.drop_column("reservations", "carrier_code")
    op.drop_column("reservations", "carrier_name")
    op.drop_column("reservations", "delivery_instructions")
    op.drop_column("reservations", "delivery_method")
    op.drop_column("reservations", "delivery_fee_cents")
    op.drop_column("reservations", "delivery_zone_id")
