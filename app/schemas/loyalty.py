"""Schemas Pydantic pour le module Fidelite (Loyalty)."""

import re
from datetime import datetime
from typing import Optional

from pydantic import Field, field_validator, model_validator

from app.schemas.base import BaseSchema, EntityResponseSchema, IDSchema, TimestampSchema


# ── Member ────────────────────────────────────────────────────────────────────


class LoyaltyMemberCreate(BaseSchema):
    """Inscription d'un nouveau membre fidelite."""

    phone: str = Field(..., min_length=6, max_length=20, description="Numero de telephone")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    birth_month: Optional[int] = Field(None, ge=1, le=12, description="Mois de naissance (1-12)")
    referral_code_used: Optional[str] = Field(None, max_length=50, description="Code parrain saisi")
    program_id: int = Field(..., description="ID du programme de fidelite")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-\.\(\)]", "", v)
        if not re.match(r"^\+?\d{6,20}$", cleaned):
            raise ValueError("Numero de telephone invalide")
        return cleaned


class LoyaltyMemberUpdate(BaseSchema):
    """Mise a jour partielle d'un membre."""

    email: Optional[str] = Field(None, max_length=255)
    birth_month: Optional[int] = Field(None, ge=1, le=12)
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)


class LoyaltyMemberList(IDSchema, TimestampSchema):
    """Schema liste simplifiee d'un membre."""

    phone: str
    first_name: str
    last_name: str
    current_tier: str
    transaction_count: int
    referral_code: str
    is_active: bool

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class LoyaltyMemberResponse(EntityResponseSchema):
    """Schema reponse complete d'un membre."""

    program_id: int
    customer_id: Optional[int] = None
    phone: str
    first_name: str
    last_name: str
    birth_month: Optional[int] = None
    email: Optional[str] = None
    referral_code: str
    current_tier: str
    tier_evaluated_at: Optional[datetime] = None
    grace_until: Optional[datetime] = None
    transaction_count: int
    wallet_serial_number: Optional[str] = None
    wallet_platform: Optional[str] = None


class LoyaltyMemberProfile(BaseSchema):
    """Profil fidelite affiche au caissier apres scan."""

    member_id: int
    first_name: str
    last_name: str
    current_tier: str
    points_balance: int = Field(0, description="Solde de points actuel (programme POINTS)")
    cumulative_ca_cents: int = Field(0, description="CA cumule en centimes (programme TIERED_DISCOUNT)")
    discount_percent: int = Field(0, description="Remise applicable en %")
    available_rewards: list["RewardAvailable"] = Field(default_factory=list)
    has_welcome_reward: bool = Field(False, description="True si le reward bienvenue est disponible")


# ── Points Ledger ─────────────────────────────────────────────────────────────


class PointsLedgerEntry(IDSchema, TimestampSchema):
    """Entree du journal de points."""

    member_id: int
    order_id: Optional[int] = None
    amount: int
    entry_type: str
    source: Optional[str] = None
    balance_after: int
    expires_at: Optional[datetime] = None


# ── Revenue Ledger ────────────────────────────────────────────────────────────


class RevenueLedgerEntry(IDSchema, TimestampSchema):
    """Entree du journal de CA."""

    member_id: int
    reservation_id: Optional[int] = None
    amount_cents: int
    entry_type: str
    cumulative_after_cents: int


# ── Rewards ───────────────────────────────────────────────────────────────────


class RewardsCatalogCreate(BaseSchema):
    """Creation d'un reward dans le catalogue."""

    tier: str = Field(..., pattern=r"^(welcome|tier_1|tier_2|tier_3)$")
    product_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    points_cost: int = Field(0, ge=0)
    max_cost_cents: int = Field(0, ge=0)


class RewardsCatalogUpdate(BaseSchema):
    """Mise a jour d'un reward."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    points_cost: Optional[int] = Field(None, ge=0)
    max_cost_cents: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class RewardsCatalogResponse(IDSchema, TimestampSchema):
    """Reponse reward catalogue."""

    program_id: int
    tier: str
    product_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    points_cost: int
    max_cost_cents: int
    is_active: bool


class RewardAvailable(BaseSchema):
    """Reward disponible pour un membre (affichage caissier/client)."""

    reward_id: int
    name: str
    tier: str
    points_cost: int


# ── Redemption ────────────────────────────────────────────────────────────────


class RedeemRequest(BaseSchema):
    """Demande d'utilisation d'un reward."""

    member_id: int
    reward_id: int
    order_id: Optional[int] = None


class RewardRedemptionResponse(IDSchema, TimestampSchema):
    """Reponse utilisation de reward."""

    member_id: int
    reward_id: int
    order_id: Optional[int] = None
    points_spent: int
    status: str
    redeemed_at: datetime
    revoked_at: Optional[datetime] = None


# ── Scan / Credit ─────────────────────────────────────────────────────────────


class ScanRequest(BaseSchema):
    """Scan du barcode en caisse."""

    barcode: str = Field(..., min_length=1, max_length=200)


class CreditRequest(BaseSchema):
    """Credit de points apres transaction."""

    member_id: int
    amount_cents: int = Field(..., gt=0, description="Montant TTC de la transaction en centimes")
    source: str = Field(..., pattern=r"^(restaurant|epicerie)$")
    order_id: int


class CreditResponse(BaseSchema):
    """Reponse au credit de points."""

    points_added: int
    new_balance: int
    tier: str
    flash_multiplier: Optional[float] = None


class RevenueCreditRequest(BaseSchema):
    """Credit de CA pour le programme location."""

    member_id: int
    amount_cents: int = Field(..., description="Montant TTC en centimes (positif=CA, negatif=remboursement)")
    reservation_id: Optional[int] = None


# ── Flash Offers ──────────────────────────────────────────────────────────────


class FlashOfferCreate(BaseSchema):
    """Creation d'une offre flash."""

    name: str = Field(..., min_length=1, max_length=200)
    multiplier: float = Field(..., gt=0, le=10)
    target: str = Field("all", pattern=r"^(all|vip)$")
    starts_at: datetime
    ends_at: datetime
    program_id: int

    @model_validator(mode="after")
    def validate_dates(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at doit etre apres starts_at")
        return self


class FlashOfferResponse(IDSchema, TimestampSchema):
    """Reponse offre flash."""

    program_id: int
    name: str
    multiplier: float
    target: str
    starts_at: datetime
    ends_at: datetime
    status: str
    push_sent_at: Optional[datetime] = None


# ── Adjust (geste commercial) ────────────────────────────────────────────────


class AdjustPointsRequest(BaseSchema):
    """Ajustement manuel de points (geste commercial)."""

    member_id: int
    amount: int = Field(..., description="Montant de points (positif=credit, negatif=debit)")
    reason: str = Field(..., min_length=1, max_length=500)


# ── Dashboard ─────────────────────────────────────────────────────────────────


class LoyaltyDashboardMetrics(BaseSchema):
    """Metriques du dashboard fidelite."""

    total_members: int
    active_members: int
    vip_members: int
    total_points_in_circulation: int
    points_earned_this_month: int
    points_redeemed_this_month: int
    redemption_rate: float = Field(description="Taux de redemption (0.0 - 1.0)")
    churn_risk_count: int = Field(description="Membres a risque (21-35j sans visite)")
    top_referrers: list["TopReferrer"] = Field(default_factory=list)


class TopReferrer(BaseSchema):
    """Top parrain pour le dashboard."""

    member_id: int
    display_name: str
    referral_count: int


# ── Wallet join response ─────────────────────────────────────────────────────


class JoinResponse(BaseSchema):
    """Reponse a l'inscription fidelite."""

    member_id: int
    referral_code: str
    wallet_url: Optional[str] = Field(None, description="URL pour ajouter la carte au wallet")
    welcome_reward_available: bool = False


# Rebuild forward refs
LoyaltyMemberProfile.model_rebuild()
LoyaltyDashboardMetrics.model_rebuild()
