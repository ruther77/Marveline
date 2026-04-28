"""Modeles du module Fidelite (Loyalty).

11 tables :
- LoyaltyProgram     : configuration d'un programme (POINTS ou TIERED_DISCOUNT)
- LoyaltyMember      : membre inscrit a un programme
- PointsLedger       : journal immuable des points (L'Incontournable)
- RevenueLedger      : journal immuable du CA (Marveline)
- TierHistory        : historique des changements de palier
- WalletPass         : passes Apple/Google Wallet enregistres
- RewardsCatalog     : catalogue des rewards par tier
- RewardRedemption   : historique d'utilisation des rewards
- ReferralLink       : liens de parrainage
- FlashOffer         : offres flash (multiplicateur temporaire)
- LoyaltyNotificationLog : log des notifications envoyees
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


# ── LoyaltyProgram ────────────────────────────────────────────────────────────


class LoyaltyProgram(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Configuration d'un programme de fidelite.

    Deux instances en prod :
    - L'Incontournable (type=points, tenant restau+epicerie)
    - Marveline (type=tiered_discount, tenant location)
    """

    __tablename__ = "loyalty_programs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Nom du programme (L'Incontournable, Marveline)"
    )

    program_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Type: points | tiered_discount"
    )

    config: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, default=None,
        comment="Configuration specifique en JSON"
    )

    members: Mapped[list["LoyaltyMember"]] = relationship(
        back_populates="program", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(
            "program_type IN ('points', 'tiered_discount')",
            name="ck_loyalty_programs_type"
        ),
        UniqueConstraint("tenant_id", "name", name="uq_loyalty_program_tenant_name"),
    )


# ── LoyaltyMember ────────────────────────────────────────────────────────────


class LoyaltyMember(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Membre inscrit a un programme de fidelite.

    Identifiant unique = telephone (par tenant).
    Lie a un Customer existant via customer_id FK.
    """

    __tablename__ = "loyalty_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    program_id: Mapped[int] = mapped_column(
        ForeignKey("loyalty_programs.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Programme de fidelite"
    )

    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        comment="Lien vers le client existant (nullable si pas encore lie)"
    )

    phone: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Numero de telephone (identifiant unique par tenant)"
    )

    first_name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Prenom du membre"
    )

    last_name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Nom du membre"
    )

    birth_month: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Mois de naissance (1-12) pour offre anniversaire"
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
        comment="Email (demande apres 2 transactions ou premier reward)"
    )

    referral_code: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Code parrain unique (PRENOM + 4 chiffres)"
    )

    current_tier: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Palier actuel du membre"
    )

    tier_evaluated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Derniere evaluation du palier"
    )

    grace_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Date limite de la periode de grace avant downgrade"
    )

    transaction_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Nombre total de transactions (pour trigger email prompt)"
    )

    wallet_serial_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Serial number du pass wallet principal"
    )

    wallet_platform: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True,
        comment="Plateforme wallet: apple | google"
    )

    # Relations
    program: Mapped["LoyaltyProgram"] = relationship(back_populates="members")

    points_entries: Mapped[list["PointsLedger"]] = relationship(
        back_populates="member", passive_deletes=True
    )

    revenue_entries: Mapped[list["RevenueLedger"]] = relationship(
        back_populates="member", passive_deletes=True
    )

    tier_changes: Mapped[list["TierHistory"]] = relationship(
        back_populates="member", passive_deletes=True
    )

    redemptions: Mapped[list["RewardRedemption"]] = relationship(
        back_populates="member", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(
            "birth_month IS NULL OR (birth_month >= 1 AND birth_month <= 12)",
            name="ck_loyalty_members_birth_month"
        ),
        CheckConstraint(
            "transaction_count >= 0",
            name="ck_loyalty_members_transaction_count"
        ),
        CheckConstraint(
            "wallet_platform IS NULL OR wallet_platform IN ('apple', 'google')",
            name="ck_loyalty_members_wallet_platform"
        ),
        UniqueConstraint("tenant_id", "phone", "program_id", name="uq_loyalty_member_tenant_phone_program"),
        UniqueConstraint("tenant_id", "referral_code", name="uq_loyalty_member_tenant_referral"),
        Index("ix_loyalty_members_tenant_phone", "tenant_id", "phone"),
        Index("ix_loyalty_members_program_id", "program_id"),
        Index("ix_loyalty_members_customer_id", "customer_id"),
    )


# ── PointsLedger ──────────────────────────────────────────────────────────────


class PointsLedger(Base, TimestampMixin, TenantMixin):
    """Journal immuable des points (L'Incontournable).

    Regles :
    - JAMAIS d'UPDATE ou DELETE sur cette table
    - Corrections via nouvelle ligne de type ADJUST
    - balance_after = snapshot du solde apres cette entree
    - expires_at : 12 mois pour EARN, 6 mois pour BONUS
    """

    __tablename__ = "points_ledger"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    member_id: Mapped[int] = mapped_column(
        ForeignKey("loyalty_members.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Membre concerne"
    )

    order_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="ID de la commande associee (nullable pour ajustements)"
    )

    amount: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Montant de points (positif=gain, negatif=depense/expiration)"
    )

    entry_type: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="Type: earn | redeem | expire | adjust | bonus"
    )

    source: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Source: restaurant | epicerie | referral | promo | welcome | manual | flash"
    )

    balance_after: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Solde total apres cette entree"
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Date d'expiration (12 mois EARN, 6 mois BONUS)"
    )

    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, default=None,
        comment="Contexte libre (promo_id, flash_offer_id, admin_reason...)"
    )

    # Relations
    member: Mapped["LoyaltyMember"] = relationship(back_populates="points_entries")

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('earn', 'redeem', 'expire', 'adjust', 'bonus')",
            name="ck_points_ledger_type"
        ),
        CheckConstraint(
            "source IS NULL OR source IN "
            "('restaurant', 'epicerie', 'referral', 'promo', 'welcome', 'manual', 'flash')",
            name="ck_points_ledger_source"
        ),
        Index("ix_points_ledger_member_id", "member_id"),
        Index("ix_points_ledger_expires_at", "expires_at",
              postgresql_where="expires_at IS NOT NULL"),
        Index("ix_points_ledger_order_id", "order_id",
              postgresql_where="order_id IS NOT NULL"),
    )


# ── RevenueLedger ─────────────────────────────────────────────────────────────


class RevenueLedger(Base, TimestampMixin, TenantMixin):
    """Journal immuable du CA (Marveline location).

    Memes regles d'immutabilite que PointsLedger.
    cumulative_after_cents = CA cumule apres cette entree.
    """

    __tablename__ = "revenue_ledger"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    member_id: Mapped[int] = mapped_column(
        ForeignKey("loyalty_members.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Membre concerne"
    )

    reservation_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="ID de la reservation associee"
    )

    amount_cents: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="Montant en centimes (positif=CA, negatif=remboursement)"
    )

    entry_type: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="Type: purchase | refund | adjust"
    )

    cumulative_after_cents: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="CA cumule en centimes apres cette entree"
    )

    # Relations
    member: Mapped["LoyaltyMember"] = relationship(back_populates="revenue_entries")

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('purchase', 'refund', 'adjust')",
            name="ck_revenue_ledger_type"
        ),
        Index("ix_revenue_ledger_member_id", "member_id"),
    )


# ── TierHistory ───────────────────────────────────────────────────────────────


class TierHistory(Base, TimestampMixin):
    """Historique des changements de palier d'un membre."""

    __tablename__ = "tier_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    member_id: Mapped[int] = mapped_column(
        ForeignKey("loyalty_members.id", ondelete="CASCADE"),
        nullable=False
    )

    from_tier: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Palier avant le changement"
    )

    to_tier: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Palier apres le changement"
    )

    reason: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Raison du changement (upgrade, downgrade, grace_expired, manual)"
    )

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="Date de l'evaluation"
    )

    # Relations
    member: Mapped["LoyaltyMember"] = relationship(back_populates="tier_changes")

    __table_args__ = (
        Index("ix_tier_history_member_id", "member_id"),
    )


# ── WalletPass ────────────────────────────────────────────────────────────────


class WalletPass(Base, TimestampMixin):
    """Pass enregistre dans Apple/Google Wallet.

    Un membre peut avoir plusieurs devices (multi-device).
    Le serial_number est le PK (unique globalement).
    """

    __tablename__ = "wallet_passes"

    serial_number: Mapped[str] = mapped_column(
        String(100), primary_key=True,
        comment="Serial number unique du pass"
    )

    member_id: Mapped[int] = mapped_column(
        ForeignKey("loyalty_members.id", ondelete="CASCADE"),
        nullable=False,
        comment="Membre proprietaire"
    )

    platform: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="Plateforme: apple | google"
    )

    device_id: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
        comment="ID du device (fourni par Apple/Google au registration)"
    )

    push_token: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Token APNs/FCM pour push silencieux"
    )

    auth_token: Mapped[str] = mapped_column(
        String(300), nullable=False,
        comment="Token d'authentification pour les callbacks wallet"
    )

    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="active",
        comment="Statut: active | inactive"
    )

    last_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Derniere mise a jour du pass envoyee"
    )

    __table_args__ = (
        CheckConstraint(
            "platform IN ('apple', 'google')",
            name="ck_wallet_passes_platform"
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_wallet_passes_status"
        ),
        Index("ix_wallet_passes_member_id", "member_id"),
        Index("ix_wallet_passes_device_id", "device_id",
              postgresql_where="device_id IS NOT NULL"),
    )


# ── RewardsCatalog ────────────────────────────────────────────────────────────


class RewardsCatalog(Base, TimestampMixin, TenantMixin):
    """Catalogue des rewards par tier.

    - Tier 1 : FK vers products (produits reels). 10 produits.
    - Tier 2/3 : rewards abstraits possibles (product_id nullable). 5 choix.
    - Welcome : produits tagges welcome_eligible.
    """

    __tablename__ = "rewards_catalog"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    program_id: Mapped[int] = mapped_column(
        ForeignKey("loyalty_programs.id", ondelete="CASCADE"),
        nullable=False,
        comment="Programme de fidelite"
    )

    tier: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="Niveau: welcome | tier_1 | tier_2 | tier_3"
    )

    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        comment="Produit reel associe (nullable pour rewards abstraits)"
    )

    name: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Nom du reward affiche"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Description du reward"
    )

    points_cost: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Cout en points (0 pour welcome)"
    )

    max_cost_cents: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Cout max pour l'entreprise en centimes"
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="Actif dans le catalogue (toggle admin)"
    )

    __table_args__ = (
        CheckConstraint(
            "tier IN ('welcome', 'tier_1', 'tier_2', 'tier_3')",
            name="ck_rewards_catalog_tier"
        ),
        CheckConstraint("points_cost >= 0", name="ck_rewards_catalog_cost"),
        Index("ix_rewards_catalog_program_tier", "program_id", "tier"),
    )


# ── RewardRedemption ──────────────────────────────────────────────────────────


class RewardRedemption(Base, TimestampMixin):
    """Historique d'utilisation des rewards."""

    __tablename__ = "reward_redemptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    member_id: Mapped[int] = mapped_column(
        ForeignKey("loyalty_members.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Membre qui utilise le reward"
    )

    reward_id: Mapped[int] = mapped_column(
        ForeignKey("rewards_catalog.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Reward utilise"
    )

    order_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="ID de la commande associee"
    )

    points_spent: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Points depenses (0 pour welcome)"
    )

    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="used",
        comment="Statut: used | revoked"
    )

    redeemed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="Date d'utilisation"
    )

    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Date de revocation (si annulation transaction)"
    )

    # Relations
    member: Mapped["LoyaltyMember"] = relationship(back_populates="redemptions")

    __table_args__ = (
        CheckConstraint(
            "status IN ('used', 'revoked')",
            name="ck_reward_redemptions_status"
        ),
        CheckConstraint("points_spent >= 0", name="ck_reward_redemptions_points"),
        Index("ix_reward_redemptions_member_id", "member_id"),
        Index("ix_reward_redemptions_order_id", "order_id",
              postgresql_where="order_id IS NOT NULL"),
    )


# ── ReferralLink ──────────────────────────────────────────────────────────────


class ReferralLink(Base, TimestampMixin):
    """Lien de parrainage entre deux membres.

    Le credit est effectue a la 1ere transaction du filleul.
    credited_at = NULL tant que le filleul n'a pas fait sa 1ere transaction.
    """

    __tablename__ = "referral_links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    sponsor_member_id: Mapped[int] = mapped_column(
        ForeignKey("loyalty_members.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Parrain"
    )

    referred_member_id: Mapped[int] = mapped_column(
        ForeignKey("loyalty_members.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Filleul"
    )

    credited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Date de credit des points (NULL = en attente)"
    )

    __table_args__ = (
        UniqueConstraint(
            "sponsor_member_id", "referred_member_id",
            name="uq_referral_link_pair"
        ),
        Index("ix_referral_links_sponsor", "sponsor_member_id"),
        Index("ix_referral_links_referred", "referred_member_id"),
    )


# ── FlashOffer ────────────────────────────────────────────────────────────────


class FlashOffer(Base, TimestampMixin, TenantMixin):
    """Offre flash temporaire (multiplicateur de points).

    Cible : tous les membres ou VIP uniquement.
    Multiplicateurs cumulatifs : VIP x1.5 + flash x2 = x3.
    """

    __tablename__ = "flash_offers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    program_id: Mapped[int] = mapped_column(
        ForeignKey("loyalty_programs.id", ondelete="CASCADE"),
        nullable=False,
        comment="Programme de fidelite"
    )

    name: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Nom de l'offre (ex: Points x2 ce weekend)"
    )

    multiplier: Mapped[float] = mapped_column(
        Numeric(4, 2), nullable=False,
        comment="Multiplicateur de points (ex: 2.0)"
    )

    target: Mapped[str] = mapped_column(
        String(10), nullable=False, default="all",
        comment="Cible: all | vip"
    )

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="Debut de l'offre"
    )

    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="Fin de l'offre"
    )

    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="scheduled",
        comment="Statut: scheduled | active | ended"
    )

    push_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Date d'envoi de la notification push"
    )

    __table_args__ = (
        CheckConstraint(
            "target IN ('all', 'vip')",
            name="ck_flash_offers_target"
        ),
        CheckConstraint(
            "status IN ('scheduled', 'active', 'ended')",
            name="ck_flash_offers_status"
        ),
        CheckConstraint("multiplier > 0", name="ck_flash_offers_multiplier"),
        CheckConstraint("ends_at > starts_at", name="ck_flash_offers_dates"),
        Index("ix_flash_offers_program_status", "program_id", "status"),
    )


# ── LoyaltyNotificationLog ───────────────────────────────────────────────────


class LoyaltyNotificationLog(Base):
    """Log des notifications fidelite envoyees.

    Evite de renvoyer la meme notification deux fois.
    """

    __tablename__ = "loyalty_notifications_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    member_id: Mapped[int] = mapped_column(
        ForeignKey("loyalty_members.id", ondelete="CASCADE"),
        nullable=False,
        comment="Membre notifie"
    )

    notif_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Type de notification"
    )

    channel: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="Canal: wallet | sms | email"
    )

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="Date d'envoi"
    )

    __table_args__ = (
        CheckConstraint(
            "notif_type IN ('expiration_j14', 'expiration_j3', 'grace_vip', "
            "'flash', 'birthday', 'email_prompt')",
            name="ck_loyalty_notif_log_type"
        ),
        CheckConstraint(
            "channel IN ('wallet', 'sms', 'email')",
            name="ck_loyalty_notif_log_channel"
        ),
        Index("ix_loyalty_notif_log_member_type", "member_id", "notif_type"),
    )
