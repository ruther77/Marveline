"""Tests RBAC scopes — 6 rôles × 62 scopes, hiérarchie, cross-tenant (Phase 9).

Couvre spec §06-RBAC-SESSIONS §6.1-6.4 :
  - Mapping role → scopes (matrice complète)
  - Hiérarchie stricte (super_admin ⊇ tenant_admin ⊇ manager ⊇ staff ⊇ viewer)
  - Anti-escalade (can_manage_role)
  - Cross-tenant TENANT_MISMATCH
  - Backward compat alias 'admin' → tenant_admin
"""
import pytest
from unittest.mock import patch

from app.services.rbac import (
    get_role_scopes_sync,
    has_scope,
    can_manage_role,
    ROLE_SCOPES_FALLBACK,
)


# ── Constantes spec (§06 §6.2 + M5) ─────────────────────────────────────────

EXPECTED_COUNTS = {
    "super_admin":   62,
    "platform_ops":   5,
    "tenant_admin":  60,
    "manager":       36,
    "staff":         21,
    "viewer":        12,
}

# Scopes infra §06 §6.2 (25 — seuls les 25 originaux)
INFRA_SCOPE_SAMPLES = {
    "reservations:read", "reservations:write",
    "stock:read", "stock:write", "stock:adjust",
    "users:read", "users:write", "users:manage", "users:delete",
    "sessions:read", "sessions:revoke",
    "audit:read", "audit:verify",
}

# Scopes que platform_ops ne doit PAS avoir (il a audit:read + audit:verify en lecture seule cross-tenant)
PLATFORM_OPS_FORBIDDEN = {
    "reservations:write", "stock:write", "users:manage", "reservations:delete",
}

# Scopes que viewer doit avoir
VIEWER_MUST_HAVE = {"reservations:read", "stock:read", "reports:read"}

# Scopes que viewer ne doit PAS avoir
VIEWER_MUST_NOT_HAVE = {"users:write", "users:manage", "stock:write", "sessions:revoke"}


# ── Counts par rôle ──────────────────────────────────────────────────────────

class TestRoleScopeCounts:
    """Vérifie le nombre de scopes par rôle (matrice §06 + M5)."""

    @pytest.mark.parametrize("role,expected", EXPECTED_COUNTS.items())
    def test_role_scope_count(self, role, expected):
        scopes = get_role_scopes_sync(role)
        assert len(scopes) == expected, (
            f"Rôle '{role}' : {len(scopes)} scopes, attendu {expected}"
        )


# ── Hiérarchie d'inclusion ───────────────────────────────────────────────────

class TestScopeHierarchy:
    """Un rôle supérieur doit inclure tous les scopes des rôles inférieurs."""

    def test_super_admin_includes_tenant_admin(self):
        sa = set(get_role_scopes_sync("super_admin"))
        ta = set(get_role_scopes_sync("tenant_admin"))
        assert ta.issubset(sa), f"super_admin manque : {ta - sa}"

    def test_tenant_admin_includes_manager(self):
        ta = set(get_role_scopes_sync("tenant_admin"))
        mg = set(get_role_scopes_sync("manager"))
        assert mg.issubset(ta), f"tenant_admin manque : {mg - ta}"

    def test_manager_includes_staff(self):
        mg = set(get_role_scopes_sync("manager"))
        st = set(get_role_scopes_sync("staff"))
        assert st.issubset(mg), f"manager manque : {st - mg}"

    def test_staff_includes_viewer(self):
        st = set(get_role_scopes_sync("staff"))
        vw = set(get_role_scopes_sync("viewer"))
        assert vw.issubset(st), f"staff manque : {vw - st}"

    def test_platform_ops_is_not_subset_of_viewer(self):
        """platform_ops est cross-tenant — hors hiérarchie normale."""
        po = set(get_role_scopes_sync("platform_ops"))
        vw = set(get_role_scopes_sync("viewer"))
        # platform_ops a des scopes que viewer n'a pas (audit:verify, etc.)
        assert not po.issubset(vw)


# ── Scopes spécifiques par rôle ──────────────────────────────────────────────

class TestRoleScopeContent:
    """Vérifie la présence/absence de scopes clés par rôle."""

    def test_viewer_has_required_scopes(self):
        scopes = set(get_role_scopes_sync("viewer"))
        missing = VIEWER_MUST_HAVE - scopes
        assert not missing, f"viewer manque : {missing}"

    def test_viewer_lacks_write_scopes(self):
        scopes = set(get_role_scopes_sync("viewer"))
        forbidden_present = VIEWER_MUST_NOT_HAVE & scopes
        assert not forbidden_present, f"viewer a des scopes interdits : {forbidden_present}"

    def test_platform_ops_lacks_write_scopes(self):
        scopes = set(get_role_scopes_sync("platform_ops"))
        forbidden_present = PLATFORM_OPS_FORBIDDEN & scopes
        assert not forbidden_present, f"platform_ops a des scopes interdits : {forbidden_present}"

    def test_super_admin_has_vpn_admin(self):
        """super_admin doit avoir vpn:admin."""
        scopes = set(get_role_scopes_sync("super_admin"))
        assert "vpn:admin" in scopes

    def test_tenant_admin_lacks_vpn_admin(self):
        """tenant_admin n'a pas vpn:admin (spec §06 — exclu)."""
        scopes = set(get_role_scopes_sync("tenant_admin"))
        assert "vpn:admin" not in scopes

    def test_manager_has_vpn_read_only(self):
        """manager a vpn:read mais pas vpn:write ni vpn:admin."""
        scopes = set(get_role_scopes_sync("manager"))
        assert "vpn:read" in scopes
        assert "vpn:write" not in scopes
        assert "vpn:admin" not in scopes

    def test_all_roles_have_reservations_read(self):
        """reservations:read doit être dans tous les rôles (sauf platform_ops)."""
        for role in ("super_admin", "tenant_admin", "manager", "staff", "viewer"):
            scopes = set(get_role_scopes_sync(role))
            assert "reservations:read" in scopes, f"{role} manque reservations:read"

    def test_infra_samples_in_super_admin(self):
        """Tous les scopes infra de l'échantillon sont dans super_admin."""
        scopes = set(get_role_scopes_sync("super_admin"))
        missing = INFRA_SCOPE_SAMPLES - scopes
        assert not missing, f"super_admin manque les scopes infra : {missing}"


# ── Anti-escalade can_manage_role ────────────────────────────────────────────

class TestCanManageRole:
    """§6.4 — Un executor ne peut gérer que des rôles de level inférieur au sien."""

    def test_super_admin_can_manage_tenant_admin(self):
        assert can_manage_role("super_admin", "tenant_admin") is True

    def test_super_admin_can_manage_all(self):
        for target in ("platform_ops", "tenant_admin", "manager", "staff", "viewer"):
            assert can_manage_role("super_admin", target) is True

    def test_tenant_admin_can_manage_manager(self):
        assert can_manage_role("tenant_admin", "manager") is True

    def test_manager_cannot_manage_tenant_admin(self):
        """Un manager (level 3) ne peut pas gérer un tenant_admin (level 2)."""
        assert can_manage_role("manager", "tenant_admin") is False

    def test_cannot_manage_own_level(self):
        """Un rôle ne peut pas gérer son propre level."""
        assert can_manage_role("manager", "manager") is False
        assert can_manage_role("tenant_admin", "tenant_admin") is False

    def test_viewer_cannot_manage_anyone(self):
        for target in ("manager", "staff", "viewer"):
            assert can_manage_role("viewer", target) is False

    def test_tenant_admin_cannot_manage_super_admin(self):
        assert can_manage_role("tenant_admin", "super_admin") is False


# ── has_scope helper ─────────────────────────────────────────────────────────

class TestHasScope:
    """Vérifie la fonction has_scope()."""

    def test_has_scope_positive(self):
        scopes = get_role_scopes_sync("staff")
        assert has_scope(scopes, "reservations:read") is True

    def test_has_scope_negative(self):
        scopes = get_role_scopes_sync("staff")
        assert has_scope(scopes, "users:manage") is False

    def test_has_scope_empty(self):
        assert has_scope([], "reservations:read") is False

    def test_has_scope_exact_match_only(self):
        """Pas de wildcard — correspondance exacte uniquement."""
        scopes = get_role_scopes_sync("manager")
        # "reservations" ne doit pas matcher "reservations:read"
        assert has_scope(scopes, "reservations") is False


# ── Backward compat alias 'admin' ────────────────────────────────────────────

class TestBackwardCompatAlias:
    """L'alias 'admin' → tenant_admin doit fonctionner pour les fixtures (MEMORY.md)."""

    def test_admin_alias_resolves_to_tenant_admin_scopes(self):
        admin_scopes = set(get_role_scopes_sync("admin"))
        ta_scopes = set(get_role_scopes_sync("tenant_admin"))
        assert admin_scopes == ta_scopes

    def test_fallback_contains_admin_key(self):
        assert "admin" in ROLE_SCOPES_FALLBACK
