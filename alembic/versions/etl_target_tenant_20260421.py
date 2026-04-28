"""add target_tenant_id to etl_imports (TAIYAT multi-tenant routing)

Ajoute une colonne optionnelle pour router la validation vers le bon tenant
(2=épicerie NOUTAM, 3=restaurant INCONTOURNABLE pour les factures TAIYAT).

Revision ID: etl_tgt_tenant_20260421
Revises: map_ingr_epi_20260421
Create Date: 2026-04-21

Strategy: EXPAND — colonne nullable ajoutée, aucune donnée existante impactée.
Rollback: DROP COLUMN target_tenant_id.
"""
from alembic import op
import sqlalchemy as sa

revision = "etl_tgt_tenant_20260421"
down_revision = "map_ingr_epi_20260421"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "etl_imports",
        sa.Column(
            "target_tenant_id",
            sa.BigInteger(),
            nullable=True,
            comment=(
                "Tenant de destination pour la validation (routing multi-tenant). "
                "NULL = fallback sur tenant de l'opérateur. "
                "Rempli automatiquement par le parser pour TAIYAT "
                "(INCONTOURNABLE→3, NOUTAM→2)."
            ),
        ),
    )
    op.add_column(
        "etl_imports",
        sa.Column(
            "client_name",
            sa.String(100),
            nullable=True,
            comment="Nom client extrait par le parser (TAIYAT : INCONTOURNABLE|NOUTAM).",
        ),
    )
    op.create_index(
        "idx_etl_imports_target_tenant",
        "etl_imports",
        ["target_tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_etl_imports_target_tenant", table_name="etl_imports")
    op.drop_column("etl_imports", "client_name")
    op.drop_column("etl_imports", "target_tenant_id")
