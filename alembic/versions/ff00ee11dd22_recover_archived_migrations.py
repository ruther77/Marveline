"""Recover archived migrations — objets DB manquants dus à collisions d'IDs

Revision ID: ff00ee11dd22
Revises: b5c6d7e8f9a1
Create Date: 2026-03-01

Contexte :
    Plusieurs migrations ont été archivées dans alembic/versions/archive/ suite à des
    refactorings, mais leurs IDs ont été réutilisés pour d'autres migrations. Les objets
    DB qu'elles devaient créer manquent en DB de dev, causant des ProgrammingError 500.

    Objets recréés (expand uniquement, toutes colonnes nullable) :
    1. Table notifications
    2. reservations.advance_payment_amount_cents (BigInteger nullable)
    3. reservations.balance_due_date (Date nullable)
    4. reservations.advance_paid_at (DateTime nullable)
    5. reservations.assigned_user_id (Integer nullable, FK→users)
    6. devis.conditions_paiement (String(50) nullable)
    7. devis.message_accompagnement (Text nullable)
    8. relances.message (Text nullable)

Stratégie expand/contract :
    Toutes les modifications sont non-destructives (ADD COLUMN nullable ou CREATE TABLE).
    Rollback: drop créations.
"""
from alembic import op
import sqlalchemy as sa

revision = "ff00ee11dd22"
down_revision = "b5c6d7e8f9a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Table notifications
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_tenant_id",
        "notifications",
        ["tenant_id"],
    )
    op.create_index(
        "ix_notifications_tenant_id_composite",
        "notifications",
        ["tenant_id", "id"],
    )

    # 2–4. Colonnes acompte sur reservations
    op.add_column(
        "reservations",
        sa.Column(
            "advance_payment_amount_cents",
            sa.BigInteger(),
            nullable=True,
            comment="Montant acompte 40% en centimes (calculé à la confirmation)",
        ),
    )
    op.add_column(
        "reservations",
        sa.Column(
            "balance_due_date",
            sa.Date(),
            nullable=True,
            comment="Date échéance solde (event_date - BALANCE_DUE_DAYS_BEFORE_EVENT)",
        ),
    )
    op.add_column(
        "reservations",
        sa.Column(
            "advance_paid_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Horodatage encaissement acompte (NULL si non encaissé)",
        ),
    )

    # 5. assigned_user_id sur reservations
    op.add_column(
        "reservations",
        sa.Column(
            "assigned_user_id",
            sa.Integer(),
            nullable=True,
            comment="Utilisateur affecté à cette réservation (équipe terrain)",
        ),
    )
    op.create_foreign_key(
        "fk_reservations_assigned_user_id",
        "reservations",
        "users",
        ["assigned_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_reservations_assigned_user_id",
        "reservations",
        ["assigned_user_id"],
    )

    # 6–7. Colonnes devis
    op.add_column(
        "devis",
        sa.Column(
            "conditions_paiement",
            sa.String(50),
            nullable=True,
            comment="Conditions de paiement (30_acompte, 50_50, comptant, fin_evenement)",
        ),
    )
    op.add_column(
        "devis",
        sa.Column(
            "message_accompagnement",
            sa.Text(),
            nullable=True,
            comment="Message d'accompagnement envoyé avec le devis",
        ),
    )

    # 8. message sur relances
    op.add_column(
        "relances",
        sa.Column(
            "message",
            sa.Text(),
            nullable=True,
            comment="Message personnalisé (optionnel)",
        ),
    )


def downgrade() -> None:
    op.drop_column("relances", "message")
    op.drop_column("devis", "message_accompagnement")
    op.drop_column("devis", "conditions_paiement")
    op.drop_index("ix_reservations_assigned_user_id", table_name="reservations")
    op.drop_constraint(
        "fk_reservations_assigned_user_id", "reservations", type_="foreignkey"
    )
    op.drop_column("reservations", "assigned_user_id")
    op.drop_column("reservations", "advance_paid_at")
    op.drop_column("reservations", "balance_due_date")
    op.drop_column("reservations", "advance_payment_amount_cents")
    op.drop_index("ix_notifications_tenant_id_composite", table_name="notifications")
    op.drop_index("ix_notifications_tenant_id", table_name="notifications")
    op.drop_table("notifications")
