"""Tests securite — isolation tenant sur les endpoints Loyalty.

Verifie qu'un utilisateur du tenant 2 ne peut PAS acceder aux donnees
du tenant 1 (et inversement). Violation = P0 immediat.

Couvre :
- POST /loyalty/scan : ne retourne pas un membre d'un autre tenant
- POST /loyalty/credit : ne credite pas un membre d'un autre tenant
- POST /loyalty/redeem : ne redemption pas pour un autre tenant
- GET  /loyalty/admin/dashboard : ne montre pas les metriques d'un autre tenant
- GET  /loyalty/admin/members : ne liste pas les membres d'un autre tenant
- POST /loyalty/admin/adjust : ne peut pas ajuster les points d'un autre tenant
"""

import pytest

from app.models.loyalty import LoyaltyProgram, LoyaltyMember, RewardsCatalog
from app.services.loyalty import generate_barcode


@pytest.fixture
def program_t1(test_db, test_tenant_record):
    """Programme fidelite tenant 1."""
    p = LoyaltyProgram(
        tenant_id=test_tenant_record.id,
        name="Programme T1",
        program_type="points",
        is_active=True,
    )
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    return p


@pytest.fixture
def program_t2(test_db, test_tenant_record2):
    """Programme fidelite tenant 2."""
    p = LoyaltyProgram(
        tenant_id=test_tenant_record2.id,
        name="Programme T2",
        program_type="points",
        is_active=True,
    )
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    return p


@pytest.fixture
def member_t1(test_db, program_t1):
    """Membre du tenant 1."""
    m = LoyaltyMember(
        tenant_id=program_t1.tenant_id,
        program_id=program_t1.id,
        phone="+33600000001",
        first_name="Alice",
        last_name="T1",
        referral_code="ALICE0001",
        current_tier="standard",
        transaction_count=0,
        is_active=True,
    )
    test_db.add(m)
    test_db.commit()
    test_db.refresh(m)
    return m


@pytest.fixture
def member_t2(test_db, program_t2):
    """Membre du tenant 2."""
    m = LoyaltyMember(
        tenant_id=program_t2.tenant_id,
        program_id=program_t2.id,
        phone="+33600000002",
        first_name="Bob",
        last_name="T2",
        referral_code="BOB00002",
        current_tier="standard",
        transaction_count=0,
        is_active=True,
    )
    test_db.add(m)
    test_db.commit()
    test_db.refresh(m)
    return m


@pytest.fixture
def reward_t1(test_db, program_t1):
    r = RewardsCatalog(
        tenant_id=program_t1.tenant_id,
        program_id=program_t1.id,
        tier="tier_1",
        name="Reward T1",
        points_cost=500,
        max_cost_cents=500,
        is_active=True,
    )
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)
    return r


# ── Scan : cross-tenant interdit ─────────────────────────────────────────────


class TestScanCrossTenant:
    def test_user_t2_cannot_scan_member_t1(
        self, client, auth_headers_tenant2, member_t1
    ):
        """Utilisateur tenant 2 scanne le barcode d'un membre tenant 1 → 404."""
        barcode = generate_barcode(member_t1.id)
        resp = client.post("/api/v1/loyalty/scan",
            json={"barcode": barcode},
            headers=auth_headers_tenant2,
        )
        # Le membre n'existe pas dans le tenant 2
        assert resp.status_code == 404


# ── Credit : cross-tenant interdit ───────────────────────────────────────────


class TestCreditCrossTenant:
    def test_user_t2_cannot_credit_member_t1(
        self, client, auth_headers_tenant2, member_t1
    ):
        """Utilisateur tenant 2 tente de crediter un membre tenant 1 → 404."""
        resp = client.post("/api/v1/loyalty/credit",
            json={
                "member_id": member_t1.id,
                "amount_cents": 2000,
                "source": "restaurant",
                "order_id": 9001,
            },
            headers=auth_headers_tenant2,
        )
        assert resp.status_code == 404


# ── Redeem : cross-tenant interdit ───────────────────────────────────────────


class TestRedeemCrossTenant:
    def test_user_t2_cannot_redeem_for_member_t1(
        self, client, auth_headers_tenant2, member_t1, reward_t1
    ):
        """Utilisateur tenant 2 tente de redeem un reward du tenant 1 → 404."""
        resp = client.post("/api/v1/loyalty/redeem",
            json={
                "member_id": member_t1.id,
                "reward_id": reward_t1.id,
            },
            headers=auth_headers_tenant2,
        )
        assert resp.status_code == 404


# ── Admin dashboard : cross-tenant interdit ──────────────────────────────────


class TestDashboardCrossTenant:
    def test_admin_t2_sees_zero_for_t1_program(
        self, client, auth_headers_admin_tenant2, program_t1, member_t1
    ):
        """Admin tenant 2 demande le dashboard du programme tenant 1.

        Le programme n'est pas visible pour le tenant 2 → metriques a zero
        (le programme n'est pas trouve dans le tenant 2).
        """
        resp = client.get(
            f"/api/v1/loyalty/admin/dashboard?program_id={program_t1.id}",
            headers=auth_headers_admin_tenant2,
        )
        # Soit 404 (programme non trouve), soit metriques a zero
        if resp.status_code == 200:
            data = resp.json()
            assert data["total_members"] == 0


# ── Admin members : cross-tenant interdit ─────────────────────────────────────


class TestMembersCrossTenant:
    def test_admin_t2_cannot_list_t1_members(
        self, client, auth_headers_admin_tenant2, program_t1, member_t1
    ):
        """Admin tenant 2 ne voit pas les membres du tenant 1."""
        resp = client.get(
            f"/api/v1/loyalty/admin/members?program_id={program_t1.id}",
            headers=auth_headers_admin_tenant2,
        )
        if resp.status_code == 200:
            data = resp.json()
            member_ids = [m["id"] for m in data["items"]]
            assert member_t1.id not in member_ids


# ── Admin adjust : cross-tenant interdit ──────────────────────────────────────


class TestAdjustCrossTenant:
    def test_admin_t2_cannot_adjust_t1_member(
        self, client, auth_headers_admin_tenant2, member_t1
    ):
        """Admin tenant 2 tente d'ajuster les points d'un membre tenant 1 → 404."""
        resp = client.post("/api/v1/loyalty/admin/adjust",
            json={
                "member_id": member_t1.id,
                "amount": 500,
                "reason": "Cross-tenant attack test",
            },
            headers=auth_headers_admin_tenant2,
        )
        assert resp.status_code == 404


# ── RBAC : staff cannot access admin endpoints ────────────────────────────────


class TestRBACScopes:
    def test_staff_cannot_access_dashboard(
        self, client, auth_headers_real, program_t1
    ):
        """Staff (non admin) ne peut pas acceder au dashboard fidelite."""
        resp = client.get(
            f"/api/v1/loyalty/admin/dashboard?program_id={program_t1.id}",
            headers=auth_headers_real,
        )
        assert resp.status_code == 403

    def test_staff_cannot_adjust_points(
        self, client, auth_headers_real, member_t1
    ):
        """Staff ne peut pas faire un geste commercial."""
        resp = client.post("/api/v1/loyalty/admin/adjust",
            json={
                "member_id": member_t1.id,
                "amount": 100,
                "reason": "Staff attempt",
            },
            headers=auth_headers_real,
        )
        assert resp.status_code == 403

    def test_unauthenticated_cannot_scan(self, client):
        """Sans auth, scan → 401."""
        resp = client.post("/api/v1/loyalty/scan", json={"barcode": "test"})
        assert resp.status_code in (401, 403)
