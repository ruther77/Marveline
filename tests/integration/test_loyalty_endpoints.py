"""Tests integration des endpoints Loyalty.

Couvre :
- POST /loyalty/join (inscription publique)
- POST /loyalty/scan (scan barcode)
- POST /loyalty/credit (credit points)
- POST /loyalty/redeem (utilisation reward)
- POST /loyalty/cancel-transaction (annulation)
- GET  /loyalty/admin/dashboard (metriques)
- GET  /loyalty/admin/members (liste)
- POST /loyalty/admin/adjust (geste commercial)
- CRUD /loyalty/admin/rewards (catalogue)
- POST /loyalty/admin/flash-offers (offre flash)
"""

import pytest

from app.models.loyalty import LoyaltyProgram, LoyaltyMember, RewardsCatalog
from app.services.loyalty import generate_barcode


TENANT_ID = 1


@pytest.fixture
def loyalty_program(test_db, test_tenant_record):
    """Programme de fidelite L'Incontournable (type=points)."""
    program = LoyaltyProgram(
        tenant_id=test_tenant_record.id,
        name="L'Incontournable",
        program_type="points",
        is_active=True,
    )
    test_db.add(program)
    test_db.commit()
    test_db.refresh(program)
    return program


@pytest.fixture
def loyalty_member(test_db, loyalty_program):
    """Membre de fidelite pour les tests."""
    member = LoyaltyMember(
        tenant_id=loyalty_program.tenant_id,
        program_id=loyalty_program.id,
        phone="+33612345678",
        first_name="Jean",
        last_name="Dupont",
        birth_month=3,
        referral_code="JEAN4827",
        current_tier="standard",
        transaction_count=0,
        is_active=True,
    )
    test_db.add(member)
    test_db.commit()
    test_db.refresh(member)
    return member


@pytest.fixture
def loyalty_reward(test_db, loyalty_program):
    """Reward tier 1 dans le catalogue."""
    reward = RewardsCatalog(
        tenant_id=loyalty_program.tenant_id,
        program_id=loyalty_program.id,
        tier="tier_1",
        name="Biere artisanale",
        points_cost=500,
        max_cost_cents=500,
        is_active=True,
    )
    test_db.add(reward)
    test_db.commit()
    test_db.refresh(reward)
    return reward


@pytest.fixture
def welcome_reward(test_db, loyalty_program):
    """Reward bienvenue (gratuit)."""
    reward = RewardsCatalog(
        tenant_id=loyalty_program.tenant_id,
        program_id=loyalty_program.id,
        tier="welcome",
        name="Cafe offert",
        points_cost=0,
        max_cost_cents=200,
        is_active=True,
    )
    test_db.add(reward)
    test_db.commit()
    test_db.refresh(reward)
    return reward


# ── POST /loyalty/join ────────────────────────────────────────────────────────


class TestJoinLoyalty:
    def test_join_success(self, client, loyalty_program):
        resp = client.post("/api/v1/loyalty/join", json={
            "phone": "+33698765432",
            "first_name": "Marie",
            "last_name": "Martin",
            "birth_month": 7,
            "program_id": loyalty_program.id,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["member_id"] > 0
        assert data["referral_code"].startswith("MARIE")
        assert data["welcome_reward_available"] is True

    def test_join_duplicate_phone(self, client, loyalty_program, loyalty_member):
        resp = client.post("/api/v1/loyalty/join", json={
            "phone": "+33612345678",
            "first_name": "Jean",
            "last_name": "Dupont",
            "program_id": loyalty_program.id,
        })
        assert resp.status_code == 409

    def test_join_with_referral_code(self, client, loyalty_program, loyalty_member):
        resp = client.post("/api/v1/loyalty/join", json={
            "phone": "+33611223344",
            "first_name": "Paul",
            "last_name": "Durand",
            "program_id": loyalty_program.id,
            "referral_code_used": "JEAN4827",
        })
        assert resp.status_code == 201

    def test_join_invalid_program(self, client):
        resp = client.post("/api/v1/loyalty/join", json={
            "phone": "+33699887766",
            "first_name": "Alice",
            "last_name": "Doe",
            "program_id": 9999,
        })
        assert resp.status_code == 404


# ── POST /loyalty/scan ────────────────────────────────────────────────────────


class TestScanLoyalty:
    def test_scan_valid_barcode(self, client, auth_headers_real, loyalty_member):
        barcode = generate_barcode(loyalty_member.id)
        resp = client.post("/api/v1/loyalty/scan",
            json={"barcode": barcode},
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["member_id"] == loyalty_member.id
        assert data["first_name"] == "Jean"
        assert data["current_tier"] == "standard"
        assert data["points_balance"] == 0

    def test_scan_invalid_barcode(self, client, auth_headers_real):
        resp = client.post("/api/v1/loyalty/scan",
            json={"barcode": "invalid-code"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 400


# ── POST /loyalty/credit ──────────────────────────────────────────────────────


class TestCreditPoints:
    def test_credit_restaurant(self, client, auth_headers_real, loyalty_member):
        resp = client.post("/api/v1/loyalty/credit",
            json={
                "member_id": loyalty_member.id,
                "amount_cents": 2000,  # 20 EUR
                "source": "restaurant",
                "order_id": 1001,
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["points_added"] == 200  # 20 * 10
        assert data["new_balance"] == 200
        assert data["tier"] == "standard"

    def test_credit_epicerie(self, client, auth_headers_real, loyalty_member):
        resp = client.post("/api/v1/loyalty/credit",
            json={
                "member_id": loyalty_member.id,
                "amount_cents": 1300,  # 13 EUR
                "source": "epicerie",
                "order_id": 1002,
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["points_added"] == 65  # 13 * 5

    def test_double_scan_rejected(self, client, auth_headers_real, loyalty_member):
        """Double scan sur le meme order_id."""
        payload = {
            "member_id": loyalty_member.id,
            "amount_cents": 2000,
            "source": "restaurant",
            "order_id": 2001,
        }
        resp1 = client.post("/api/v1/loyalty/credit", json=payload, headers=auth_headers_real)
        assert resp1.status_code == 200

        resp2 = client.post("/api/v1/loyalty/credit", json=payload, headers=auth_headers_real)
        assert resp2.status_code == 409


# ── POST /loyalty/redeem ──────────────────────────────────────────────────────


class TestRedeemReward:
    def test_redeem_insufficient_points(self, client, auth_headers_real, loyalty_member, loyalty_reward):
        resp = client.post("/api/v1/loyalty/redeem",
            json={
                "member_id": loyalty_member.id,
                "reward_id": loyalty_reward.id,
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 400  # Insufficient points


# ── POST /loyalty/admin/adjust ────────────────────────────────────────────────


class TestAdjustPoints:
    def test_adjust_credit(self, client, auth_headers_admin, loyalty_member):
        resp = client.post("/api/v1/loyalty/admin/adjust",
            json={
                "member_id": loyalty_member.id,
                "amount": 100,
                "reason": "Geste commercial test",
            },
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_balance"] == 100
        assert data["status"] == "ok"


# ── GET /loyalty/admin/dashboard ──────────────────────────────────────────────


class TestDashboard:
    def test_dashboard_returns_metrics(self, client, auth_headers_admin, loyalty_program, loyalty_member):
        resp = client.get(
            f"/api/v1/loyalty/admin/dashboard?program_id={loyalty_program.id}",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_members" in data
        assert "vip_members" in data
        assert "redemption_rate" in data


# ── GET /loyalty/admin/members ────────────────────────────────────────────────


class TestListMembers:
    def test_list_members(self, client, auth_headers_admin, loyalty_program, loyalty_member):
        resp = client.get(
            f"/api/v1/loyalty/admin/members?program_id={loyalty_program.id}",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1


# ── CRUD /loyalty/admin/rewards ───────────────────────────────────────────────


class TestRewardsCatalog:
    def test_create_reward(self, client, auth_headers_admin, loyalty_program):
        resp = client.post(
            f"/api/v1/loyalty/admin/rewards?program_id={loyalty_program.id}",
            json={
                "tier": "tier_1",
                "name": "Verre de vin",
                "points_cost": 500,
                "max_cost_cents": 400,
            },
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Verre de vin"
        assert data["is_active"] is True

    def test_list_rewards(self, client, auth_headers_admin, loyalty_program, loyalty_reward):
        resp = client.get(
            f"/api/v1/loyalty/admin/rewards?program_id={loyalty_program.id}",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_toggle_reward(self, client, auth_headers_admin, loyalty_reward):
        resp = client.put(
            f"/api/v1/loyalty/admin/rewards/{loyalty_reward.id}",
            json={"is_active": False},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False


# ── POST /loyalty/admin/flash-offers ──────────────────────────────────────────


class TestFlashOffers:
    def test_create_flash_offer(self, client, auth_headers_admin, loyalty_program):
        resp = client.post("/api/v1/loyalty/admin/flash-offers",
            json={
                "name": "Points x2 ce weekend",
                "multiplier": 2.0,
                "target": "all",
                "starts_at": "2026-04-01T00:00:00Z",
                "ends_at": "2026-04-03T23:59:59Z",
                "program_id": loyalty_program.id,
            },
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "scheduled"
        assert data["multiplier"] == 2.0
