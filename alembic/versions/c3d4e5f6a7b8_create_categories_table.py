"""create_categories_table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-13 23:30:00.000000

Create categories table with self-referencing hierarchy.
Seed 20 existing product categories for tenant_id=1.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 20 categories du catalogue Marveline
SEED_CATEGORIES = [
    ("Accessoires Transport", "accessoires_transport", 1),
    ("Assiettes", "assiettes", 2),
    ("Bancs", "bancs", 3),
    ("Candy Bar", "candy_bar", 4),
    ("Chaises", "chaises", 5),
    ("Couverts", "couverts", 6),
    ("Decorations", "decorations", 7),
    ("Housses", "housses", 8),
    ("Machines", "machines", 9),
    ("Mange-debout", "mange_debout", 10),
    ("Mobilier", "mobilier", 11),
    ("Nappages", "nappages", 12),
    ("Nappes", "nappes", 13),
    ("Porcelaine", "porcelaine", 14),
    ("Serviettes", "serviettes", 15),
    ("Tables", "tables", 16),
    ("Vaisselle", "vaisselle", 17),
    ("Vaisselle Service", "vaisselle_service", 18),
    ("Vaisselle Enfants", "vaisselle_enfants", 19),
    ("Verres", "verres", 20),
]


def upgrade() -> None:
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('description', sa.String(1000), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['categories.id'], name='fk_category_parent'),
        sa.UniqueConstraint('tenant_id', 'slug', name='uq_category_tenant_slug'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_category_tenant_name'),
        sa.CheckConstraint('display_order >= 0', name='check_category_display_order'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_categories_tenant_id', 'categories', ['tenant_id'])
    op.create_index('ix_categories_tenant_slug', 'categories', ['tenant_id', 'slug'])
    op.create_index('ix_categories_tenant_parent', 'categories', ['tenant_id', 'parent_id'])

    # Seed les 20 categories pour tenant_id=1
    categories_table = sa.table(
        'categories',
        sa.column('tenant_id', sa.BigInteger),
        sa.column('name', sa.String),
        sa.column('slug', sa.String),
        sa.column('display_order', sa.Integer),
    )
    op.bulk_insert(categories_table, [
        {"tenant_id": 1, "name": name, "slug": slug, "display_order": order}
        for name, slug, order in SEED_CATEGORIES
    ])


def downgrade() -> None:
    op.drop_index('ix_categories_tenant_parent', table_name='categories')
    op.drop_index('ix_categories_tenant_slug', table_name='categories')
    op.drop_index('ix_categories_tenant_id', table_name='categories')
    op.drop_table('categories')
