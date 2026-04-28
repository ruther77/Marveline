import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useRestaurantScopes } from './useRestaurantScopes'
import { useMassaCorpAuthStore } from '@shared/stores/massacorpAuthStore'

function setUser(user: { role: string; scopes: string[] } | null) {
  useMassaCorpAuthStore.setState({
    user: user
      ? { id: 1, email: 'x@x', first_name: 'A', last_name: 'B', tenant_id: 3, role: user.role, scopes: user.scopes }
      : null,
  })
}

describe('useRestaurantScopes', () => {
  beforeEach(() => {
    useMassaCorpAuthStore.setState({ user: null, isAuthenticated: false, csrfToken: null, isLoading: false, activeTenant: 'restaurant' })
    vi.clearAllMocks()
  })

  it('manager via rôle → canEdit=true, isManager=true', () => {
    setUser({ role: 'manager', scopes: [] })
    const { result } = renderHook(() => useRestaurantScopes())
    expect(result.current.canEdit).toBe(true)
    expect(result.current.isManager).toBe(true)
    expect(result.current.canRead).toBe(true)
  })

  it('admin/superadmin/owner sont aussi managers', () => {
    for (const role of ['admin', 'superadmin', 'owner']) {
      setUser({ role, scopes: [] })
      const { result } = renderHook(() => useRestaurantScopes())
      expect(result.current.isManager, role).toBe(true)
      expect(result.current.canEdit, role).toBe(true)
    }
  })

  it('staff via rôle → canRead=true mais canEdit=false', () => {
    setUser({ role: 'staff', scopes: ['restaurant:read'] })
    const { result } = renderHook(() => useRestaurantScopes())
    expect(result.current.isStaff).toBe(true)
    expect(result.current.canRead).toBe(true)
    expect(result.current.canEdit).toBe(false)
    expect(result.current.isManager).toBe(false)
  })

  it('scope restaurant:write sans rôle manager → canEdit=true quand même', () => {
    setUser({ role: 'unknown_role', scopes: ['restaurant:write'] })
    const { result } = renderHook(() => useRestaurantScopes())
    expect(result.current.canEdit).toBe(true)
    expect(result.current.isManager).toBe(true)
  })

  it('user null → aucun droit', () => {
    setUser(null)
    const { result } = renderHook(() => useRestaurantScopes())
    expect(result.current.canEdit).toBe(false)
    expect(result.current.canRead).toBe(false)
    expect(result.current.isManager).toBe(false)
    expect(result.current.isStaff).toBe(false)
  })

  it('rôle inconnu sans scopes → lectures seule minimale', () => {
    setUser({ role: 'inconnu', scopes: [] })
    const { result } = renderHook(() => useRestaurantScopes())
    expect(result.current.canEdit).toBe(false)
    expect(result.current.isManager).toBe(false)
    expect(result.current.isStaff).toBe(false)
  })
})
