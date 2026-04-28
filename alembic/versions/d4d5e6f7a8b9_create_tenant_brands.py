"""create tenant_brands table

Revision ID: d4d5e6f7a8b9
Revises: d3c4d5e6f7a8
Create Date: 2026-04-16

Table dediee pour l'identite marque tenant-scoped (nom affiche, legal, logo,
palette, tagline, contact). Remplace/complete tenant_settings.company_* pour
une vraie separation des concerns : tenant_settings = config metier,
tenant_brands = habillage/identite.

Design :
- PK sur tenant_id (1:1 avec tenants)
- palette_json stocke les 11 shades 50..950 en JSONB (flexibilite)
- logo_url / favicon_url / logo_square_url : chemins statiques ou URL absolue
- Populated via script seed ou admin UI (plus tard)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d4d5e6f7a8b9"
down_revision = "d3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_brands",
        sa.Column("tenant_id", sa.BigInteger, sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("legal_name", sa.String(200), nullable=False),
        sa.Column("tagline", sa.String(300), nullable=True),
        sa.Column("primary_color", sa.String(16), nullable=False, server_default="#b96cc4"),
        sa.Column("primary_rgb", sa.String(32), nullable=False, server_default="185 108 196"),
        sa.Column("palette_json", postgresql.JSONB, nullable=True, comment="Shades 50..950 JSON map"),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("logo_square_url", sa.String(500), nullable=True),
        sa.Column("favicon_url", sa.String(500), nullable=True),
        sa.Column("contact_email", sa.String(200), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("tenant_brands")
