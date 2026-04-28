"""Add structured delivery address to reservations + origin_postal_code to tenant_settings.

Revision ID: logi04
Revises: logi03
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "logi04"
down_revision = "logi03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reservations — adresse de livraison structurée
    op.add_column(
        "reservations",
        sa.Column("delivery_address", sa.String(500), nullable=True,
                  comment="Adresse de livraison (rue, numéro)"),
    )
    op.add_column(
        "reservations",
        sa.Column("delivery_city", sa.String(100), nullable=True,
                  comment="Ville de livraison"),
    )
    op.add_column(
        "reservations",
        sa.Column("delivery_postal_code", sa.String(20), nullable=True,
                  comment="Code postal de livraison"),
    )

    # TenantSettings — code postal d'origine (entrepôt)
    op.add_column(
        "tenant_settings",
        sa.Column("origin_postal_code", sa.String(20), nullable=True,
                  comment="Code postal d'origine pour les devis transporteurs"),
    )


def downgrade() -> None:
    op.drop_column("tenant_settings", "origin_postal_code")
    op.drop_column("reservations", "delivery_postal_code")
    op.drop_column("reservations", "delivery_city")
    op.drop_column("reservations", "delivery_address")
