"""Add devis_attachments table (G7).

Pieces jointes devis (PDF, images).

Revision ID: devis02
Revises: devis01
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa

revision = "devis02"
down_revision = "devis01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devis_attachments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("devis_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(50), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["devis_id"], ["devis.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "mime_type IN ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')",
            name="ck_devis_attachments_mime",
        ),
        sa.CheckConstraint("file_size > 0 AND file_size <= 10485760", name="ck_devis_attachments_size"),
    )
    op.create_index("ix_devis_attachments_devis", "devis_attachments", ["devis_id"])


def downgrade() -> None:
    op.drop_table("devis_attachments")
