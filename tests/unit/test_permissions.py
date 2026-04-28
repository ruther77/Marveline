"""Tests unitaires pour le systeme de permissions RBAC hierarchique."""
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from app.core.permissions import (
    Permission,
    ROLE_HIERARCHY,
    ROLE_PERMISSIONS,
    get_effective_permissions,
    get_effective_permissions_cached,
    has_permission,
    _EFFECTIVE_CACHE,
)
from app.core.deps import require_permission


# ---------------------------------------------------------------------------
# Permission enum
# ---------------------------------------------------------------------------

class TestPermissionEnum:
    """Verification de la structure de l'enum Permission."""

    def test_permission_values_are_resource_action_format(self):
        for perm in Permission:
            assert ":" in perm.value, f"{perm.name} should have format resource:action"
            resource, action = perm.value.split(":")
            assert len(resource) > 0
            assert action in ("read", "write", "delete", "admin")

    def test_permission_is_str_enum(self):
        assert isinstance(Permission.PRODUCTS_READ, str)
        assert Permission.PRODUCTS_READ == "products:read"

    def test_all_resources_have_at_least_read(self):
        resources = {p.value.split(":")[0] for p in Permission}
        for resource in resources:
            read_perm = f"{resource}:read"
            has_read = any(p.value == read_perm for p in Permission)
            # Certaines resources n'ont que :admin (ex: sessions, users)
            has_any = any(p.value.startswith(f"{resource}:") for p in Permission)
            assert has_any, f"Resource {resource} has no permissions"


# ---------------------------------------------------------------------------
# Role hierarchy
# ---------------------------------------------------------------------------

class TestRoleHierarchy:
    """Verification de la hierarchie des roles."""

    def test_hierarchy_order(self):
        assert ROLE_HIERARCHY == ["staff", "manager", "admin"]

    def test_hierarchy_has_three_roles(self):
        assert len(ROLE_HIERARCHY) == 3

    def test_all_roles_have_permissions_defined(self):
        for role in ROLE_HIERARCHY:
            assert role in ROLE_PERMISSIONS, f"Role {role} missing from ROLE_PERMISSIONS"
            assert len(ROLE_PERMISSIONS[role]) > 0, f"Role {role} has empty permissions"

    def test_role_permissions_are_delta_not_cumulative(self):
        """Chaque role ne definit que ses permissions PROPRES, pas celles heritees."""
        staff_perms = ROLE_PERMISSIONS["staff"]
        manager_perms = ROLE_PERMISSIONS["manager"]
        admin_perms = ROLE_PERMISSIONS["admin"]

        # Manager ne doit pas contenir de permissions staff
        assert staff_perms.isdisjoint(manager_perms), (
            f"Manager contains staff permissions: {staff_perms & manager_perms}"
        )
        # Admin ne doit pas contenir de permissions staff ou manager
        assert staff_perms.isdisjoint(admin_perms), (
            f"Admin contains staff permissions: {staff_perms & admin_perms}"
        )
        assert manager_perms.isdisjoint(admin_perms), (
            f"Admin contains manager permissions: {manager_perms & admin_perms}"
        )


# ---------------------------------------------------------------------------
# get_effective_permissions
# ---------------------------------------------------------------------------

class TestGetEffectivePermissions:
    """Tests pour la resolution des permissions avec heritage."""

    def test_staff_permissions_match_defined_delta(self):
        """Staff : permissions effectives = delta staff (pas d'heritage en dessous)."""
        perms = get_effective_permissions("staff")
        assert perms == ROLE_PERMISSIONS["staff"]
        # Staff a des :read + :write operationnels (reservations, invoices, customers, inventory, ventes, evenements)
        read_perms = {p for p in perms if p.value.endswith(":read")}
        write_perms = {p for p in perms if p.value.endswith(":write")}
        assert len(read_perms) > 0, "Staff doit avoir des permissions :read"
        assert len(write_perms) > 0, "Staff doit avoir des permissions :write operationnelles"
        # Staff ne doit pas avoir de permissions :delete ni :admin
        for p in perms:
            assert not p.value.endswith(":delete"), f"Staff ne doit pas avoir :delete, got {p.value}"
            assert not p.value.endswith(":admin"), f"Staff ne doit pas avoir :admin, got {p.value}"

    def test_manager_inherits_staff_permissions(self):
        manager_perms = get_effective_permissions("manager")
        staff_perms = get_effective_permissions("staff")
        assert staff_perms.issubset(manager_perms), (
            f"Manager should inherit all staff permissions. Missing: {staff_perms - manager_perms}"
        )

    def test_manager_has_own_permissions(self):
        manager_perms = get_effective_permissions("manager")
        for perm in ROLE_PERMISSIONS["manager"]:
            assert perm in manager_perms

    def test_admin_inherits_all_permissions(self):
        admin_perms = get_effective_permissions("admin")
        staff_perms = get_effective_permissions("staff")
        manager_perms = get_effective_permissions("manager")
        assert staff_perms.issubset(admin_perms)
        assert manager_perms.issubset(admin_perms)

    def test_admin_has_all_defined_permissions(self):
        admin_perms = get_effective_permissions("admin")
        all_perms = set()
        for role_perms in ROLE_PERMISSIONS.values():
            all_perms |= role_perms
        assert admin_perms == all_perms, (
            f"Admin should have ALL permissions. Missing: {all_perms - admin_perms}"
        )

    def test_unknown_role_raises_value_error(self):
        with pytest.raises(ValueError, match="Role inconnu: 'superadmin'"):
            get_effective_permissions("superadmin")

    def test_empty_string_role_raises_value_error(self):
        with pytest.raises(ValueError, match="Role inconnu"):
            get_effective_permissions("")

    def test_permission_count_increases_with_hierarchy(self):
        staff_count = len(get_effective_permissions("staff"))
        manager_count = len(get_effective_permissions("manager"))
        admin_count = len(get_effective_permissions("admin"))
        assert staff_count < manager_count < admin_count


# ---------------------------------------------------------------------------
# has_permission
# ---------------------------------------------------------------------------

class TestHasPermission:
    """Tests pour la verification de permission."""

    # --- Staff ---
    def test_staff_can_read_products(self):
        assert has_permission("staff", Permission.PRODUCTS_READ) is True

    def test_staff_cannot_write_products(self):
        assert has_permission("staff", Permission.PRODUCTS_WRITE) is False

    def test_staff_cannot_read_audit(self):
        assert has_permission("staff", Permission.AUDIT_READ) is False

    def test_staff_cannot_admin_users(self):
        assert has_permission("staff", Permission.USERS_ADMIN) is False

    # --- Manager ---
    def test_manager_can_read_products(self):
        """Manager herite de staff."""
        assert has_permission("manager", Permission.PRODUCTS_READ) is True

    def test_manager_can_write_reservations(self):
        assert has_permission("manager", Permission.RESERVATIONS_WRITE) is True

    def test_manager_can_write_customers(self):
        assert has_permission("manager", Permission.CUSTOMERS_WRITE) is True

    def test_manager_cannot_write_products(self):
        assert has_permission("manager", Permission.PRODUCTS_WRITE) is False

    def test_manager_cannot_read_audit(self):
        assert has_permission("manager", Permission.AUDIT_READ) is False

    # --- Admin ---
    def test_admin_can_write_products(self):
        assert has_permission("admin", Permission.PRODUCTS_WRITE) is True

    def test_admin_can_read_audit(self):
        assert has_permission("admin", Permission.AUDIT_READ) is True

    def test_admin_can_admin_users(self):
        assert has_permission("admin", Permission.USERS_ADMIN) is True

    def test_admin_inherits_manager_write(self):
        assert has_permission("admin", Permission.RESERVATIONS_WRITE) is True

    def test_admin_inherits_staff_read(self):
        assert has_permission("admin", Permission.PRODUCTS_READ) is True

    # --- Erreurs ---
    def test_unknown_role_raises(self):
        with pytest.raises(ValueError):
            has_permission("visitor", Permission.PRODUCTS_READ)


# ---------------------------------------------------------------------------
# get_effective_permissions_cached
# ---------------------------------------------------------------------------

class TestCachedPermissions:
    """Tests pour la version cached."""

    def test_cached_matches_uncached_for_all_roles(self):
        for role in ROLE_HIERARCHY:
            cached = get_effective_permissions_cached(role)
            uncached = get_effective_permissions(role)
            assert cached == uncached, f"Cache mismatch for role {role}"

    def test_cached_returns_same_object(self):
        """Le cache retourne le meme set (pas une copie)."""
        result1 = get_effective_permissions_cached("admin")
        result2 = get_effective_permissions_cached("admin")
        assert result1 is result2

    def test_cache_has_all_roles(self):
        for role in ROLE_HIERARCHY:
            assert role in _EFFECTIVE_CACHE

    def test_cached_unknown_role_returns_empty_set(self):
        """Role v3 inconnu du vieux systeme -> set vide (FAIL-OPEN, gere par require_scope)."""
        result = get_effective_permissions_cached("hacker")
        assert result == set()


# ---------------------------------------------------------------------------
# require_permission (FastAPI dependency)
# ---------------------------------------------------------------------------

class TestRequirePermission:
    """Tests pour la dependency FastAPI require_permission()."""

    def _make_user(self, role: str, tenant_id: int = 1) -> MagicMock:
        user = MagicMock()
        user.role = role
        user.tenant_id = tenant_id
        user.id = 1
        user.email = "test@example.com"
        user.is_active = True
        return user

    def test_admin_passes_write_check(self):
        dep_func = require_permission(Permission.PRODUCTS_WRITE)
        user = self._make_user("admin")
        result = dep_func(principal=user)
        assert result is user

    def test_staff_fails_write_check(self):
        dep_func = require_permission(Permission.PRODUCTS_WRITE)
        user = self._make_user("staff")
        with pytest.raises(HTTPException) as exc_info:
            dep_func(principal=user)
        assert exc_info.value.status_code == 403
        assert "products:write" in exc_info.value.detail

    def test_manager_passes_reservation_write(self):
        dep_func = require_permission(Permission.RESERVATIONS_WRITE)
        user = self._make_user("manager")
        result = dep_func(principal=user)
        assert result is user

    def test_staff_passes_read_check(self):
        dep_func = require_permission(Permission.PRODUCTS_READ)
        user = self._make_user("staff")
        result = dep_func(principal=user)
        assert result is user

    def test_multiple_permissions_all_required(self):
        dep_func = require_permission(Permission.PRODUCTS_WRITE, Permission.AUDIT_READ)
        user = self._make_user("admin")
        result = dep_func(principal=user)
        assert result is user

    def test_multiple_permissions_partial_fails(self):
        dep_func = require_permission(Permission.PRODUCTS_READ, Permission.AUDIT_READ)
        user = self._make_user("staff")  # has products:read but not audit:read
        with pytest.raises(HTTPException) as exc_info:
            dep_func(principal=user)
        assert exc_info.value.status_code == 403
        assert "audit:read" in exc_info.value.detail

    def test_error_message_lists_missing_permissions(self):
        dep_func = require_permission(Permission.PRODUCTS_WRITE, Permission.AUDIT_READ)
        user = self._make_user("staff")
        with pytest.raises(HTTPException) as exc_info:
            dep_func(principal=user)
        detail = exc_info.value.detail
        assert "products:write" in detail
        assert "audit:read" in detail


# ---------------------------------------------------------------------------
# Securite : anti cross-tenant (permissions ne dependent pas du tenant)
# ---------------------------------------------------------------------------

class TestPermissionsAreTenantAgnostic:
    """Les permissions sont basees sur le role, pas le tenant_id."""

    def test_same_role_same_perms_different_tenants(self):
        perms_t1 = get_effective_permissions("manager")
        perms_t2 = get_effective_permissions("manager")
        assert perms_t1 == perms_t2

    def test_require_permission_ignores_tenant(self):
        dep_func = require_permission(Permission.PRODUCTS_WRITE)
        user_t1 = MagicMock(role="admin", tenant_id=1)
        user_t2 = MagicMock(role="admin", tenant_id=999)
        assert dep_func(principal=user_t1) is user_t1
        assert dep_func(principal=user_t2) is user_t2
