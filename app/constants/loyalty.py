"""Constantes du module Fidelite (Loyalty).

Deux programmes independants :
- "L'Incontournable" (restau + epicerie) : systeme a points
- "Marveline" (location) : remise par palier de CA cumule

Spec complete : memory/loyalty-spec.md
"""

from enum import Enum


# ── Programme type ────────────────────────────────────────────────────────────

class LoyaltyProgramType(str, Enum):
    """Type de programme de fidelite.

    POINTS : L'Incontournable (restau + epicerie)
    TIERED_DISCOUNT : Marveline (location, remise par palier CA)
    """

    POINTS = "points"
    TIERED_DISCOUNT = "tiered_discount"


# ── Paliers ───────────────────────────────────────────────────────────────────

class LoyaltyTier(str, Enum):
    """Paliers de fidelite (les deux programmes).

    Programme POINTS (L'Incontournable) :
        STANDARD → VIP (3000 pts/an)

    Programme TIERED_DISCOUNT (Marveline) :
        NOUVEAU → HABITUE (500 EUR) → PRIVILEGIE (2000 EUR)
    """

    # Programme 1 — L'Incontournable
    STANDARD = "standard"
    VIP = "vip"

    # Programme 2 — Marveline
    NOUVEAU = "nouveau"
    HABITUE = "habitue"
    PRIVILEGIE = "privilegie"


# ── Ledger types ──────────────────────────────────────────────────────────────

class LedgerType(str, Enum):
    """Type d'entree dans le points_ledger (append-only).

    EARN    : points gagnes par achat
    REDEEM  : points depenses pour un reward
    EXPIRE  : points expires (FIFO)
    ADJUST  : correction manuelle (geste commercial, annulation)
    BONUS   : points bonus (parrainage, offre flash)
    """

    EARN = "earn"
    REDEEM = "redeem"
    EXPIRE = "expire"
    ADJUST = "adjust"
    BONUS = "bonus"


class LedgerSource(str, Enum):
    """Source d'une entree ledger (provenance des points).

    Utilise dans :
        - points_ledger.source
        - Calcul du ratio pts/EUR selon la source
    """

    RESTAURANT = "restaurant"
    EPICERIE = "epicerie"
    REFERRAL = "referral"
    PROMO = "promo"
    WELCOME = "welcome"
    MANUAL = "manual"
    FLASH = "flash"


class RevenueLedgerType(str, Enum):
    """Type d'entree dans le revenue_ledger (Marveline location).

    PURCHASE : CA ajoute (location facturee)
    REFUND   : CA deduit (annulation remboursee)
    ADJUST   : correction manuelle
    """

    PURCHASE = "purchase"
    REFUND = "refund"
    ADJUST = "adjust"


# ── Rewards ───────────────────────────────────────────────────────────────────

class RewardTier(str, Enum):
    """Niveau du reward dans le catalogue.

    WELCOME : offert a la 1ere transaction (0 pts)
    TIER_1  : 500 pts — 10 produits au choix
    TIER_2  : 1500 pts — 5 choix
    TIER_3  : 3000 pts — 5 choix
    """

    WELCOME = "welcome"
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class RedemptionStatus(str, Enum):
    """Statut d'une utilisation de reward.

    USED    : reward consomme
    REVOKED : reward annule (transaction annulee)
    """

    USED = "used"
    REVOKED = "revoked"


# ── Wallet ────────────────────────────────────────────────────────────────────

class WalletPlatform(str, Enum):
    """Plateforme wallet mobile."""

    APPLE = "apple"
    GOOGLE = "google"


class WalletPassStatus(str, Enum):
    """Statut d'un pass wallet."""

    ACTIVE = "active"
    INACTIVE = "inactive"


# ── Flash offers ──────────────────────────────────────────────────────────────

class FlashOfferTarget(str, Enum):
    """Cible d'une offre flash.

    ALL : tous les membres
    VIP : VIP uniquement
    """

    ALL = "all"
    VIP = "vip"


class FlashOfferStatus(str, Enum):
    """Statut d'une offre flash.

    SCHEDULED : programmee (starts_at dans le futur)
    ACTIVE    : en cours
    ENDED     : terminee (ends_at depasse)
    """

    SCHEDULED = "scheduled"
    ACTIVE = "active"
    ENDED = "ended"


# ── Notifications ─────────────────────────────────────────────────────────────

class LoyaltyNotifType(str, Enum):
    """Type de notification fidelite."""

    EXPIRATION_J14 = "expiration_j14"
    EXPIRATION_J3 = "expiration_j3"
    GRACE_VIP = "grace_vip"
    FLASH = "flash"
    BIRTHDAY = "birthday"
    EMAIL_PROMPT = "email_prompt"


class NotifChannel(str, Enum):
    """Canal de notification."""

    WALLET = "wallet"
    SMS = "sms"
    EMAIL = "email"


# ── Constantes metier programme L'Incontournable ─────────────────────────────

POINTS_PER_EUR_RESTAURANT: int = 10
"""Points gagnes par euro TTC depense au restaurant."""

POINTS_PER_EUR_EPICERIE: int = 5
"""Points gagnes par euro TTC depense en epicerie."""

VIP_MULTIPLIER: float = 1.5
"""Multiplicateur VIP sur les points gagnes."""

VIP_THRESHOLD_POINTS_PER_YEAR: int = 3000
"""Seuil de points/an pour atteindre le palier VIP."""

VIP_GRACE_DAYS: int = 90
"""Jours de grace avant downgrade VIP → STANDARD."""

POINTS_EXPIRY_MONTHS_EARNED: int = 12
"""Duree de vie des points gagnes (EARN) en mois."""

POINTS_EXPIRY_MONTHS_BONUS: int = 6
"""Duree de vie des points bonus (parrainage, flash) en mois."""

REFERRAL_BONUS_POINTS: int = 200
"""Points bonus parrain + filleul au parrainage."""

MAX_REFERRALS_PER_MEMBER: int = 3
"""Nombre maximum de filleuls par parrain."""

REWARD_TIER_1_COST: int = 500
"""Cout en points du reward tier 1."""

REWARD_TIER_2_COST: int = 1500
"""Cout en points du reward tier 2."""

REWARD_TIER_3_COST: int = 3000
"""Cout en points du reward tier 3."""

EXPIRY_WARNING_DAYS_FIRST: int = 14
"""Premiere notification d'expiration (J-14)."""

EXPIRY_WARNING_DAYS_SECOND: int = 3
"""Seconde notification d'expiration (J-3)."""

CHURN_RISK_MIN_DAYS: int = 21
"""Fenetre de risque de churn : minimum jours sans visite."""

CHURN_RISK_MAX_DAYS: int = 35
"""Fenetre de risque de churn : maximum jours sans visite."""

# ── Constantes metier programme Marveline ─────────────────────────────────────

TIER_HABITUE_THRESHOLD_CENTS: int = 50_000
"""Seuil HABITUE : 500 EUR (en centimes) CA cumule 24 mois."""

TIER_PRIVILEGIE_THRESHOLD_CENTS: int = 200_000
"""Seuil PRIVILEGIE : 2000 EUR (en centimes) CA cumule 24 mois."""

DISCOUNT_HABITUE_PERCENT: int = 5
"""Remise HABITUE : 5% tout le panier."""

DISCOUNT_PRIVILEGIE_PERCENT: int = 10
"""Remise PRIVILEGIE : 10% tout le panier + livraison offerte."""

REVENUE_WINDOW_MONTHS: int = 24
"""Fenetre glissante pour le CA cumule (Marveline)."""

# ── Referral code ─────────────────────────────────────────────────────────────

REFERRAL_CODE_DIGITS: int = 4
"""Nombre de chiffres dans le code parrain (PRENOM + N chiffres)."""


__all__ = [
    # Enums
    "LoyaltyProgramType",
    "LoyaltyTier",
    "LedgerType",
    "LedgerSource",
    "RevenueLedgerType",
    "RewardTier",
    "RedemptionStatus",
    "WalletPlatform",
    "WalletPassStatus",
    "FlashOfferTarget",
    "FlashOfferStatus",
    "LoyaltyNotifType",
    "NotifChannel",
    # Constantes L'Incontournable
    "POINTS_PER_EUR_RESTAURANT",
    "POINTS_PER_EUR_EPICERIE",
    "VIP_MULTIPLIER",
    "VIP_THRESHOLD_POINTS_PER_YEAR",
    "VIP_GRACE_DAYS",
    "POINTS_EXPIRY_MONTHS_EARNED",
    "POINTS_EXPIRY_MONTHS_BONUS",
    "REFERRAL_BONUS_POINTS",
    "MAX_REFERRALS_PER_MEMBER",
    "REWARD_TIER_1_COST",
    "REWARD_TIER_2_COST",
    "REWARD_TIER_3_COST",
    "EXPIRY_WARNING_DAYS_FIRST",
    "EXPIRY_WARNING_DAYS_SECOND",
    "CHURN_RISK_MIN_DAYS",
    "CHURN_RISK_MAX_DAYS",
    # Constantes Marveline
    "TIER_HABITUE_THRESHOLD_CENTS",
    "TIER_PRIVILEGIE_THRESHOLD_CENTS",
    "DISCOUNT_HABITUE_PERCENT",
    "DISCOUNT_PRIVILEGIE_PERCENT",
    "REVENUE_WINDOW_MONTHS",
    # Referral
    "REFERRAL_CODE_DIGITS",
]
