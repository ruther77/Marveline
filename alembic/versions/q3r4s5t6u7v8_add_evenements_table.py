"""Add evenements, event_incidents, incident_actions tables.

Revision ID: q3r4s5t6u7v8
Revises: p2q3r4s5t6u7
Create Date: 2026-02-20 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "q3r4s5t6u7v8"
down_revision = "p2q3r4s5t6u7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evenements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("reference", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="planned"),
        sa.Column("reservation_id", sa.Integer(), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_evenements_tenant_composite", "evenements", ["tenant_id", "id"])
    op.create_index("ix_evenements_tenant_status", "evenements", ["tenant_id", "status"])

    op.create_table(
        "event_incidents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("declared_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("declared_by", sa.Integer(), nullable=False),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("affected_items", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["evenements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["declared_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_event_incidents_tenant_event", "event_incidents", ["tenant_id", "event_id"])

    op.create_table(
        "incident_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="todo"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["incident_id"], ["event_incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_incident_actions_tenant_incident", "incident_actions", ["tenant_id", "incident_id"])


def downgrade() -> None:
    op.drop_index("ix_incident_actions_tenant_incident", "incident_actions")
    op.drop_table("incident_actions")
    op.drop_index("ix_event_incidents_tenant_event", "event_incidents")
    op.drop_table("event_incidents")
    op.drop_index("ix_evenements_tenant_status", "evenements")
    op.drop_index("ix_evenements_tenant_composite", "evenements")
    op.drop_table("evenements")
