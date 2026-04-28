"""add brand_code to tenants

Revision ID: d3c4d5e6f7a8
Revises: d2b3c4d5e6f7
Create Date: 2026-04-16

Separe app_code (bundle features backend, enforcement ISO-APP-01) de
brand_code (habillage frontend — couleur, logo, nom affiche). Permet au
meme app_code d'avoir plusieurs brands (ex : app=marveline avec
brand=marveline OU brand=lesplendid).
"""
from alembic import op
import sqlalchemy as sa


revision = "d3c4d5e6f7a8"
down_revision = "d2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ajout colonne avec default provisoire pour pouvoir la mettre NOT NULL
    op.add_column(
        "tenants",
        sa.Column(
            "brand_code",
            sa.String(30),
            nullable=False,
            server_default="marveline",
            comment="Code brand (habillage frontend). Ind\u00e9pendant de app_code.",
        ),
    )
    # Backfill : brand_code = app_code pour les tenants existants (comportement legacy)
    op.execute("UPDATE tenants SET brand_code = app_code")
    # Index
    op.create_index("idx_tenants_brand_code", "tenants", ["brand_code"])


def downgrade() -> None:
    op.drop_index("idx_tenants_brand_code", table_name="tenants")
    op.drop_column("tenants", "brand_code")
