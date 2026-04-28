"""BACK-TRANSFER-RESTO-01 MVP — Création des tables transfer_requests + lignes.

Revision ID: rstxfer
Revises: rst5c1fin
Create Date: 2026-04-15 00:00:00.000000

Tables :
  - restaurant_transfer_requests : demandes émises par le restaurant vers l'épicerie
  - restaurant_transfer_request_lines : lignes (designation + quantity)

Multi-tenant strict :
  - tenant_id = restaurant émetteur (filtre OBLIGATOIRE dans les repos)
  - target_tenant_id = épicerie cible
  - CHECK contrainte tenant_id != target_tenant_id (anti self-target)

Workflow status :
  PENDING (initial) → APPROVED → FULFILLED ou REJECTED ou CANCELLED
"""
from typing import Sequence, Union

from alembic import op

revision: str = "rstxfer"
down_revision: Union[str, None, tuple] = "rst5c1fin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table principale
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS restaurant_transfer_requests (
            id BIGSERIAL PRIMARY KEY,
            tenant_id BIGINT NOT NULL,
            target_tenant_id BIGINT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
            notes TEXT NULL,
            created_by BIGINT NOT NULL,
            fulfilled_transfer_id BIGINT NULL,
            rejection_reason TEXT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_transfer_request_status_valide
                CHECK (status IN ('PENDING', 'APPROVED', 'FULFILLED', 'REJECTED', 'CANCELLED')),
            CONSTRAINT ck_transfer_request_self_target
                CHECK (tenant_id != target_tenant_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transfer_request_tenant_id "
        "ON restaurant_transfer_requests(tenant_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transfer_request_tenant_status "
        "ON restaurant_transfer_requests(tenant_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transfer_request_target "
        "ON restaurant_transfer_requests(target_tenant_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transfer_request_created_by "
        "ON restaurant_transfer_requests(created_by)"
    )

    # Table lignes
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS restaurant_transfer_request_lines (
            id BIGSERIAL PRIMARY KEY,
            request_id BIGINT NOT NULL REFERENCES restaurant_transfer_requests(id) ON DELETE CASCADE,
            designation VARCHAR(200) NOT NULL,
            quantity NUMERIC(10, 3) NOT NULL,
            unit VARCHAR(20) NOT NULL DEFAULT 'kg',
            ingredient_restaurant_id BIGINT NULL,
            notes TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_transfer_request_line_qty_positive CHECK (quantity > 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transfer_request_line_request "
        "ON restaurant_transfer_request_lines(request_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transfer_request_line_ingredient "
        "ON restaurant_transfer_request_lines(ingredient_restaurant_id) "
        "WHERE ingredient_restaurant_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS restaurant_transfer_request_lines")
    op.execute("DROP TABLE IF EXISTS restaurant_transfer_requests")
