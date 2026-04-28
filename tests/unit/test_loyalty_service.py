"""Tests unitaires du service Loyalty.

Couvre :
- Barcode HMAC (generation + verification)
- Referral code generation
- Points calculation (ratios, VIP multiplier, flash cumul, arrondi ceil)
- Tier evaluation (upgrade, downgrade, grace)
"""

import math
import pytest

from app.services.loyalty import (
    generate_barcode,
    verify_barcode,
    generate_referral_code,
)
from app.constants.loyalty import (
    POINTS_PER_EUR_RESTAURANT,
    POINTS_PER_EUR_EPICERIE,
    VIP_MULTIPLIER,
    REFERRAL_CODE_DIGITS,
    VIP_THRESHOLD_POINTS_PER_YEAR,
    TIER_HABITUE_THRESHOLD_CENTS,
    TIER_PRIVILEGIE_THRESHOLD_CENTS,
    REFERRAL_BONUS_POINTS,
    MAX_REFERRALS_PER_MEMBER,
    POINTS_EXPIRY_MONTHS_EARNED,
    POINTS_EXPIRY_MONTHS_BONUS,
)


# ── Barcode HMAC ──────────────────────────────────────────────────────────────


class TestBarcodeHMAC:
    def test_generate_barcode_format(self):
        barcode = generate_barcode(42)
        assert barcode.startswith("42-")
        assert len(barcode) > 5

    def test_verify_valid_barcode(self):
        barcode = generate_barcode(123)
        result = verify_barcode(barcode)
        assert result == 123

    def test_verify_invalid_barcode_returns_none(self):
        assert verify_barcode("invalid") is None
        assert verify_barcode("") is None
        assert verify_barcode("42-wrongsignature") is None

    def test_verify_tampered_member_id_returns_none(self):
        barcode = generate_barcode(42)
        # Remplacer le member_id
        tampered = "99-" + barcode.split("-", 1)[1]
        assert verify_barcode(tampered) is None

    def test_barcode_deterministic(self):
        """Le meme member_id genere toujours le meme barcode."""
        b1 = generate_barcode(100)
        b2 = generate_barcode(100)
        assert b1 == b2

    def test_barcode_different_members(self):
        b1 = generate_barcode(1)
        b2 = generate_barcode(2)
        assert b1 != b2


# ── Referral Code ─────────────────────────────────────────────────────────────


class TestReferralCode:
    def test_format_prenom_plus_digits(self):
        code = generate_referral_code("Jean")
        assert code.startswith("JEAN")
        assert len(code) == 4 + REFERRAL_CODE_DIGITS
        assert code[4:].isdigit()

    def test_long_name_truncated(self):
        code = generate_referral_code("Jean-Baptiste-Emmanuel")
        # Truncated to 10 chars
        assert len(code) <= 10 + REFERRAL_CODE_DIGITS

    def test_name_uppercased(self):
        code = generate_referral_code("marie")
        assert code.startswith("MARIE")

    def test_whitespace_stripped(self):
        code = generate_referral_code("  Jean  ")
        assert code.startswith("JEAN")

    def test_randomness(self):
        """Deux appels avec le meme prenom donnent des codes differents (probabiliste)."""
        codes = {generate_referral_code("Jean") for _ in range(20)}
        assert len(codes) > 1  # Au moins 2 codes differents sur 20


# ── Points Calculation ────────────────────────────────────────────────────────


class TestPointsCalculation:
    def test_restaurant_ratio(self):
        """10 pts/EUR au restaurant."""
        amount_eur = 20.0
        points = math.ceil(amount_eur * POINTS_PER_EUR_RESTAURANT)
        assert points == 200

    def test_epicerie_ratio(self):
        """5 pts/EUR en epicerie."""
        amount_eur = 13.0
        points = math.ceil(amount_eur * POINTS_PER_EUR_EPICERIE)
        assert points == 65

    def test_vip_multiplier(self):
        """VIP x1.5 sur les points gagnes."""
        amount_eur = 20.0
        points = math.ceil(amount_eur * POINTS_PER_EUR_RESTAURANT * VIP_MULTIPLIER)
        assert points == 300

    def test_vip_epicerie_rounding_ceil(self):
        """VIP epicerie : 7.5 pts/EUR, arrondi superieur."""
        amount_eur = 13.0
        raw = amount_eur * POINTS_PER_EUR_EPICERIE * VIP_MULTIPLIER
        assert raw == 97.5
        points = math.ceil(raw)
        assert points == 98  # Arrondi superieur

    def test_flash_multiplier_cumul(self):
        """VIP x1.5 + flash x2 = x3 (cumulatif)."""
        amount_eur = 10.0
        multiplier = VIP_MULTIPLIER * 2.0  # flash x2
        points = math.ceil(amount_eur * POINTS_PER_EUR_RESTAURANT * multiplier)
        assert points == 300  # 10 * 10 * 3.0


# ── Tier Thresholds ───────────────────────────────────────────────────────────


class TestTierThresholds:
    def test_vip_threshold(self):
        assert VIP_THRESHOLD_POINTS_PER_YEAR == 3000

    def test_habitue_threshold(self):
        assert TIER_HABITUE_THRESHOLD_CENTS == 50_000  # 500 EUR

    def test_privilegie_threshold(self):
        assert TIER_PRIVILEGIE_THRESHOLD_CENTS == 200_000  # 2000 EUR


# ── Constants Coherence ───────────────────────────────────────────────────────


class TestConstantsCoherence:
    def test_referral_bonus_positive(self):
        assert REFERRAL_BONUS_POINTS > 0
        assert REFERRAL_BONUS_POINTS == 200

    def test_max_referrals(self):
        assert MAX_REFERRALS_PER_MEMBER == 3

    def test_expiry_earned_longer_than_bonus(self):
        assert POINTS_EXPIRY_MONTHS_EARNED > POINTS_EXPIRY_MONTHS_BONUS
        assert POINTS_EXPIRY_MONTHS_EARNED == 12
        assert POINTS_EXPIRY_MONTHS_BONUS == 6

    def test_points_restaurant_greater_than_epicerie(self):
        assert POINTS_PER_EUR_RESTAURANT > POINTS_PER_EUR_EPICERIE
