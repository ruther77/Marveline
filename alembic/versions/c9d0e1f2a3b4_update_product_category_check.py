"""Update product category CHECK constraint to 20 categories.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-02-16 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_CATEGORIES = "category IN ('assiette', 'verre', 'couvert', 'nappe', 'deco', 'autre')"

NEW_CATEGORIES = (
    "category IN ("
    "'accessoires_transport', 'assiettes', 'bancs', 'candy_bar', "
    "'chaises', 'couverts', 'decorations', 'housses', 'machines', "
    "'mange_debout', 'mobilier', 'nappages', 'nappes', 'porcelaine', "
    "'serviettes', 'tables', 'vaisselle', 'vaisselle_service', "
    "'vaisselle_enfants', 'verres')"
)


def upgrade() -> None:
    op.drop_constraint("check_product_category_valid", "products", type_="check")
    op.create_check_constraint("check_product_category_valid", "products", NEW_CATEGORIES)


def downgrade() -> None:
    op.drop_constraint("check_product_category_valid", "products", type_="check")
    op.create_check_constraint("check_product_category_valid", "products", OLD_CATEGORIES)
