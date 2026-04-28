"""alter_signature_url_to_text

Revision ID: bddb5278ef23
Revises: dd55ee66ff77
Create Date: 2026-02-25 20:44:42.245061

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bddb5278ef23'
down_revision: Union[str, None] = 'dd55ee66ff77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'reservations',
        'signature_url',
        type_=sa.Text(),
        existing_type=sa.String(500),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'reservations',
        'signature_url',
        type_=sa.String(500),
        existing_type=sa.Text(),
        existing_nullable=True,
        postgresql_using='signature_url::varchar(500)',
    )
