"""add frontend_url and mfa_issuer_name to tenant_settings

Revision ID: d2b3c4d5e6f7
Revises: d1a2b3c4d5e6
Create Date: 2026-04-16

Permet a chaque tenant d'avoir son propre MFA issuer (QR code authenticator)
et son propre frontend_url (liens emails). Remplace les constantes globales
MFA_ISSUER_NAME et FRONTEND_URL pour les contextes tenant-scoped.
"""
from alembic import op
import sqlalchemy as sa


revision = "d2b3c4d5e6f7"
down_revision = "d1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_settings",
        sa.Column(
            "frontend_url",
            sa.String(500),
            nullable=True,
            comment="URL frontend du tenant (emails, OAuth callbacks). NULL = fallback settings.FRONTEND_URL",
        ),
    )
    op.add_column(
        "tenant_settings",
        sa.Column(
            "mfa_issuer_name",
            sa.String(100),
            nullable=True,
            comment="Nom issuer TOTP affiche dans l'authenticator app. NULL = fallback settings.MFA_ISSUER_NAME",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant_settings", "mfa_issuer_name")
    op.drop_column("tenant_settings", "frontend_url")
