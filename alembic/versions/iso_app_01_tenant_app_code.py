"""ISO-APP-01 — Ajout Tenant.app_code pour isolation app↔tenant

Revision ID: iso_app_01
Revises: etl_ux_07
Create Date: 2026-04-14

Chaque tenant est rattaché à une app unique parmi :
  - marveline   : location événementielle
  - epicerie    : MassaCorp Épicerie
  - restaurant  : MassaCorp Restaurant

Backfill statique en dev :
  id=1 → marveline | id=2 → epicerie | id=3 → restaurant

En prod, vérifier le mapping avant migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "iso_app_01"
down_revision: Union[str, None] = "etl_ux_07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


APP_CODES = ("marveline", "epicerie", "restaurant")
BACKFILL_MAP = {1: "marveline", 2: "epicerie", 3: "restaurant"}


def upgrade() -> None:
    # Expand : colonne nullable d'abord
    op.add_column(
        "tenants",
        sa.Column("app_code", sa.String(length=20), nullable=True),
    )

    # Backfill statique (dev/démo). Les rows hors mapping resteront NULL
    # et l'ALTER NOT NULL échouera si prod a des tenants imprévus — comportement voulu.
    for tenant_id, code in BACKFILL_MAP.items():
        op.execute(
            sa.text("UPDATE tenants SET app_code = :code WHERE id = :id").bindparams(
                code=code, id=tenant_id
            )
        )

    # Contract : NOT NULL + check constraint
    op.alter_column("tenants", "app_code", nullable=False)
    op.create_check_constraint(
        "ck_tenants_app_code_valid",
        "tenants",
        f"app_code IN {APP_CODES!r}",
    )
    op.create_index("idx_tenants_app_code", "tenants", ["app_code"])


def downgrade() -> None:
    op.drop_index("idx_tenants_app_code", table_name="tenants")
    op.drop_constraint("ck_tenants_app_code_valid", "tenants", type_="check")
    op.drop_column("tenants", "app_code")
