"""Create loyalty tables (11 tables).

Programme L'Incontournable (restau+epicerie) + Marveline (location).
Tables : loyalty_programs, loyalty_members, points_ledger, revenue_ledger,
         tier_history, wallet_passes, rewards_catalog, reward_redemptions,
         referral_links, flash_offers, loyalty_notifications_log.

Revision ID: loyalty01
Revises: z9a0b1c2d3e4
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "loyalty01"
down_revision = "z9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── loyalty_programs ──────────────────────────────────────────────────
    op.create_table(
        "loyalty_programs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("program_type", sa.String(20), nullable=False),
        sa.Column("config", JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("program_type IN ('points', 'tiered_discount')", name="ck_loyalty_programs_type"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_loyalty_program_tenant_name"),
    )
    op.create_index("ix_loyalty_programs_tenant_id", "loyalty_programs", ["tenant_id"])

    # ── loyalty_members ───────────────────────────────────────────────────
    op.create_table(
        "loyalty_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("birth_month", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("referral_code", sa.String(50), nullable=False),
        sa.Column("current_tier", sa.String(20), nullable=False),
        sa.Column("tier_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("wallet_serial_number", sa.String(100), nullable=True),
        sa.Column("wallet_platform", sa.String(10), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["program_id"], ["loyalty_programs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.CheckConstraint("birth_month IS NULL OR (birth_month >= 1 AND birth_month <= 12)", name="ck_loyalty_members_birth_month"),
        sa.CheckConstraint("transaction_count >= 0", name="ck_loyalty_members_transaction_count"),
        sa.CheckConstraint("wallet_platform IS NULL OR wallet_platform IN ('apple', 'google')", name="ck_loyalty_members_wallet_platform"),
        sa.UniqueConstraint("tenant_id", "phone", "program_id", name="uq_loyalty_member_tenant_phone_program"),
        sa.UniqueConstraint("tenant_id", "referral_code", name="uq_loyalty_member_tenant_referral"),
    )
    op.create_index("ix_loyalty_members_tenant_id", "loyalty_members", ["tenant_id"])
    op.create_index("ix_loyalty_members_tenant_phone", "loyalty_members", ["tenant_id", "phone"])
    op.create_index("ix_loyalty_members_program_id", "loyalty_members", ["program_id"])
    op.create_index("ix_loyalty_members_customer_id", "loyalty_members", ["customer_id"])

    # ── points_ledger ─────────────────────────────────────────────────────
    op.create_table(
        "points_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(10), nullable=False),
        sa.Column("source", sa.String(20), nullable=True),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["member_id"], ["loyalty_members.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("entry_type IN ('earn', 'redeem', 'expire', 'adjust', 'bonus')", name="ck_points_ledger_type"),
        sa.CheckConstraint("source IS NULL OR source IN ('restaurant', 'epicerie', 'referral', 'promo', 'welcome', 'manual', 'flash')", name="ck_points_ledger_source"),
    )
    op.create_index("ix_points_ledger_tenant_id", "points_ledger", ["tenant_id"])
    op.create_index("ix_points_ledger_member_id", "points_ledger", ["member_id"])
    op.create_index("ix_points_ledger_expires_at", "points_ledger", ["expires_at"], postgresql_where=sa.text("expires_at IS NOT NULL"))
    op.create_index("ix_points_ledger_order_id", "points_ledger", ["order_id"], postgresql_where=sa.text("order_id IS NOT NULL"))

    # ── revenue_ledger ────────────────────────────────────────────────────
    op.create_table(
        "revenue_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=True),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("entry_type", sa.String(10), nullable=False),
        sa.Column("cumulative_after_cents", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["member_id"], ["loyalty_members.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("entry_type IN ('purchase', 'refund', 'adjust')", name="ck_revenue_ledger_type"),
    )
    op.create_index("ix_revenue_ledger_tenant_id", "revenue_ledger", ["tenant_id"])
    op.create_index("ix_revenue_ledger_member_id", "revenue_ledger", ["member_id"])

    # ── tier_history ──────────────────────────────────────────────────────
    op.create_table(
        "tier_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("from_tier", sa.String(20), nullable=False),
        sa.Column("to_tier", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["member_id"], ["loyalty_members.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_tier_history_member_id", "tier_history", ["member_id"])

    # ── wallet_passes ─────────────────────────────────────────────────────
    op.create_table(
        "wallet_passes",
        sa.Column("serial_number", sa.String(100), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(10), nullable=False),
        sa.Column("device_id", sa.String(200), nullable=True),
        sa.Column("push_token", sa.Text(), nullable=True),
        sa.Column("auth_token", sa.String(300), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default=sa.text("'active'")),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("serial_number"),
        sa.ForeignKeyConstraint(["member_id"], ["loyalty_members.id"], ondelete="CASCADE"),
        sa.CheckConstraint("platform IN ('apple', 'google')", name="ck_wallet_passes_platform"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_wallet_passes_status"),
    )
    op.create_index("ix_wallet_passes_member_id", "wallet_passes", ["member_id"])
    op.create_index("ix_wallet_passes_device_id", "wallet_passes", ["device_id"], postgresql_where=sa.text("device_id IS NOT NULL"))

    # ── rewards_catalog ───────────────────────────────────────────────────
    op.create_table(
        "rewards_catalog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(10), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("points_cost", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_cost_cents", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["program_id"], ["loyalty_programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.CheckConstraint("tier IN ('welcome', 'tier_1', 'tier_2', 'tier_3')", name="ck_rewards_catalog_tier"),
        sa.CheckConstraint("points_cost >= 0", name="ck_rewards_catalog_cost"),
    )
    op.create_index("ix_rewards_catalog_tenant_id", "rewards_catalog", ["tenant_id"])
    op.create_index("ix_rewards_catalog_program_tier", "rewards_catalog", ["program_id", "tier"])

    # ── reward_redemptions ────────────────────────────────────────────────
    op.create_table(
        "reward_redemptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("reward_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("points_spent", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default=sa.text("'used'")),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["member_id"], ["loyalty_members.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reward_id"], ["rewards_catalog.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('used', 'revoked')", name="ck_reward_redemptions_status"),
        sa.CheckConstraint("points_spent >= 0", name="ck_reward_redemptions_points"),
    )
    op.create_index("ix_reward_redemptions_member_id", "reward_redemptions", ["member_id"])
    op.create_index("ix_reward_redemptions_order_id", "reward_redemptions", ["order_id"], postgresql_where=sa.text("order_id IS NOT NULL"))

    # ── referral_links ────────────────────────────────────────────────────
    op.create_table(
        "referral_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sponsor_member_id", sa.Integer(), nullable=False),
        sa.Column("referred_member_id", sa.Integer(), nullable=False),
        sa.Column("credited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["sponsor_member_id"], ["loyalty_members.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["referred_member_id"], ["loyalty_members.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("sponsor_member_id", "referred_member_id", name="uq_referral_link_pair"),
    )
    op.create_index("ix_referral_links_sponsor", "referral_links", ["sponsor_member_id"])
    op.create_index("ix_referral_links_referred", "referral_links", ["referred_member_id"])

    # ── flash_offers ──────────────────────────────────────────────────────
    op.create_table(
        "flash_offers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("multiplier", sa.Numeric(4, 2), nullable=False),
        sa.Column("target", sa.String(10), nullable=False, server_default=sa.text("'all'")),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default=sa.text("'scheduled'")),
        sa.Column("push_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["program_id"], ["loyalty_programs.id"], ondelete="CASCADE"),
        sa.CheckConstraint("target IN ('all', 'vip')", name="ck_flash_offers_target"),
        sa.CheckConstraint("status IN ('scheduled', 'active', 'ended')", name="ck_flash_offers_status"),
        sa.CheckConstraint("multiplier > 0", name="ck_flash_offers_multiplier"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_flash_offers_dates"),
    )
    op.create_index("ix_flash_offers_tenant_id", "flash_offers", ["tenant_id"])
    op.create_index("ix_flash_offers_program_status", "flash_offers", ["program_id", "status"])

    # ── loyalty_notifications_log ─────────────────────────────────────────
    op.create_table(
        "loyalty_notifications_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("notif_type", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["member_id"], ["loyalty_members.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "notif_type IN ('expiration_j14', 'expiration_j3', 'grace_vip', 'flash', 'birthday', 'email_prompt')",
            name="ck_loyalty_notif_log_type",
        ),
        sa.CheckConstraint("channel IN ('wallet', 'sms', 'email')", name="ck_loyalty_notif_log_channel"),
    )
    op.create_index("ix_loyalty_notif_log_member_type", "loyalty_notifications_log", ["member_id", "notif_type"])


def downgrade() -> None:
    op.drop_table("loyalty_notifications_log")
    op.drop_table("flash_offers")
    op.drop_table("referral_links")
    op.drop_table("reward_redemptions")
    op.drop_table("rewards_catalog")
    op.drop_table("wallet_passes")
    op.drop_table("tier_history")
    op.drop_table("revenue_ledger")
    op.drop_table("points_ledger")
    op.drop_table("loyalty_members")
    op.drop_table("loyalty_programs")
